"""Exact blocked primitives for real artifacts; no device or model execution."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys

import numpy as np

sys.dont_write_bytecode = True


def root_path():
    return next(p for p in Path(__file__).resolve().parents if (p / "project/hardware/model/fixbit_v2.py").is_file())


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


HW = Path(os.environ["SCALELLM_REFERENCE_HARDWARE_ROOT"]).resolve() if os.environ.get("SCALELLM_REFERENCE_HARDWARE_ROOT") else root_path() / "project/hardware"
FIX = load_module("real_attention_frozen_fixbit", HW / "model/fixbit_v2.py")
MLP = load_module("real_gu_mlp_fixed", HW / "model/mlp_fixed.py")
assert hashlib.sha256((HW / "model/fixbit_v2.py").read_bytes()).hexdigest() == "fb4b34397edc9d14ed3ef4f0b46d60a61b545a52a7a47d15c2eec8ba7b6db271"
LUT = np.array([int(value, 16) for value in (HW / "data/softmax_exp_u17.mem").read_text().split()], dtype=np.int64)
assert LUT.tolist() == list(FIX.build_softmax_exp_lut_u17())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bound(values, width, label):
    values = np.asarray(values)
    low, high = -(1 << (width - 1)), (1 << (width - 1)) - 1
    if np.any(values < low) or np.any(values > high):
        raise ValueError(f"{label} outsideS{width}: [{int(values.min())},{int(values.max())}]")


def round_away(values, shift):
    values = np.asarray(values, dtype=np.int64)
    half = 1 << (shift - 1)
    mag = (np.abs(values) + half) >> shift
    return np.where(values < 0, -mag, mag)


def terminal_s24(accumulator):
    rounded = round_away(accumulator, 8)
    saturated = np.clip(rounded, -8388608, 8388607)
    return saturated, int(np.count_nonzero(saturated != rounded))


def encode_s24(values):
    values = np.asarray(values, dtype=np.int64)
    bound(values, 24, "S24 output")
    return np.stack([(values >> (8 * b)) & 255 for b in range(3)], axis=-1).astype(np.uint8).tobytes()


def decode_s24(payload, columns=4096):
    if len(payload) != 16 * columns * 3:
        raise ValueError("invalid S24 production payload length")
    b = np.frombuffer(payload, np.uint8).reshape(16, columns, 3).astype(np.int64)
    u = b[..., 0] | (b[..., 1] << 8) | (b[..., 2] << 16)
    return (u ^ 8388608) - 8388608


def stats(values):
    values = np.asarray(values)
    return {"count": int(values.size), "nonzero": int(np.count_nonzero(values)),
            "positive": int(np.count_nonzero(values > 0)), "negative": int(np.count_nonzero(values < 0)),
            "min": int(values.min()), "max": int(values.max())}


def read_record(mapping, name, size):
    value = mapping[name]
    expected_sha = None
    if hasattr(value, "path"):
        path = Path(value.path)
        expected_sha = getattr(value, "sha256", None)
    elif isinstance(value, dict):
        path = Path(value["path"])
        expected_sha = value.get("sha256")
    else:
        path = Path(value)
    payload = path.read_bytes()
    if len(payload) != size or (expected_sha is not None and sha(payload) != expected_sha):
        raise ValueError(f"real artifact size/SHA mismatch: {name}")
    return payload, {"name": name, "path": str(path.resolve()), "size": size, "sha256": sha(payload)}


def prepare_attention_a8(values):
    values = np.asarray(values, dtype=np.int64).reshape(16, 128, 32)
    q = np.zeros(values.shape, dtype=np.int64)
    code, shift, zp = [np.zeros((16, 128), dtype=np.int64) for _ in range(3)]
    saturated = 0
    for row in range(16):
        for group in range(128):
            h = FIX.hadamard32_normalized(values[row, group])
            a = FIX.minmax_a8_quantize(h.values)
            q[row, group], code[row, group], shift[row, group], zp[row, group] = a.values, a.scale_code, a.scale_shift, a.zero_point
            saturated += h.saturation_count
    return (q, code, shift, zp), {"hadamard_saturation": saturated,
             "nonzero_activation_groups": int(np.count_nonzero(code)), "shift_min": int(shift[code != 0].min()) if np.any(code) else 0,
             "shift_max": int(shift.max()), "a8_sha256": sha(q.astype(np.uint8).tobytes())}


def decode_rec576(payload):
    if len(payload) != 73728:
        raise ValueError("GU input must be73728B")
    b = np.frombuffer(payload, np.uint8).reshape(128, 576)
    if np.any(b[:, 560:]):
        raise ValueError("GU REC576 padding nonzero")
    q = b[:, :512].reshape(128, 16, 32).transpose(1, 0, 2).astype(np.int64)
    meta = b[:, 512:560].reshape(128, 16, 3).astype(np.int64)
    meta = (meta[..., 0] | meta[..., 1] << 8 | meta[..., 2] << 16).T
    if np.any(meta & 0xC00000):
        raise ValueError("GU reserved metadata bits")
    zp, code, shift = meta & 255, meta >> 8 & 255, meta >> 16 & 63
    zero = code == 0
    if np.any(meta[zero]) or np.any(q[zero]):
        raise ValueError("noncanonical zero activation")
    return q, code, shift, zp


def group_projection(prepared, weights, codes, shifts, *, gu=False, name="projection", block_columns=128):
    """Weights shape(tile16,128,16,32); all scaling stays signed integer.

    CPU FP32 is used only for each32-term integer dot. Every product and any
    partial sum is an exactly representable integer: Attention abs sum <=
    32*255*127=1036320<2^24; GU<=32*255*8=65280. Cast to int64 immediately;
    no scale/guard/group reduction is floating point. Scalar primitive checks
    cover selected output coordinates through all128 groups.
    """
    q, ac, ash, zp = prepared
    act = (q - zp[:, :, None]).transpose(1, 0, 2)
    if np.any(act < -255) or np.any(act > 255):
        raise ValueError("A8 centered value outside[-255,255]")
    if np.any(weights < (-8 if gu else -127)) or np.any(weights > (7 if gu else 127)):
        raise ValueError("weight range violation")
    columns = weights.shape[0] * 16
    result = np.zeros((16, columns), dtype=np.int64)
    guard_bits, sum_bits, raw_bits = (37, 44, 33) if gu else (42, 42, 37)
    min_shift, max_shift = (20, 44) if gu else (26, 47)
    audit = {"name": name, "saturation": 0, "guard_abs_max": 0, "sum_abs_max": 0,
             "nonzero_total_shift_min": None, "nonzero_total_shift_max": None, "scalar_samples": [],
             "dot_implementation": "CPU FP32 group32 integer matmul exact by absolute-partial-sum bound<2^24; immediately int64"}
    a32 = act.astype(np.float32)
    for start in range(0, columns, block_columns):
        count = min(block_columns, columns - start)
        first, last = start // 16, (start + count) // 16
        wb = weights[first:last].transpose(1, 3, 0, 2).reshape(128, 32, count)
        wc = codes[first:last].transpose(1, 0, 2).reshape(128, count).astype(np.int64)
        wsh = shifts[first:last].transpose(1, 0, 2).reshape(128, count).astype(np.int64)
        dots_float = np.matmul(a32, wb.astype(np.float32))
        dots = dots_float.astype(np.int64)
        if np.any(dots_float != dots):
            raise AssertionError("group dot did not remain integral")
        bound(dots, 17 if gu else 21, name + " dot")
        raw = dots * ac.T[:, :, None] * wc[:, None, :]
        bound(raw, raw_bits, name + " scaled raw")
        active = (ac.T[:, :, None] != 0) & (wc[:, None, :] != 0)
        total_shift = ash.T[:, :, None] + wsh[:, None, :]
        if np.any((total_shift[active] < min_shift) | (total_shift[active] > max_shift)):
            where = np.argwhere(active & ((total_shift < min_shift) | (total_shift > max_shift)))[0]
            g, row, c = map(int, where)
            raise ValueError(f"{name} illegal total_shift={total_shift[g,row,c]} row={row} column={start+c} group={g}")
        if np.any(active):
            current_min, current_max = int(total_shift[active].min()), int(total_shift[active].max())
            audit["nonzero_total_shift_min"] = min(current_min, audit["nonzero_total_shift_min"]) if audit["nonzero_total_shift_min"] is not None else current_min
            audit["nonzero_total_shift_max"] = max(current_max, audit["nonzero_total_shift_max"]) if audit["nonzero_total_shift_max"] is not None else current_max
        if gu:
            left = np.maximum(24 - total_shift, 0)
            right = np.maximum(total_shift - 24, 0)
            guard = np.where(active, np.left_shift(raw, left) >> right, 0)
        else:
            guard = np.where(active, raw >> np.maximum(total_shift - 24, 0), 0)
        bound(guard, guard_bits, name + " guard")
        partial = np.cumsum(guard, axis=0, dtype=np.int64)
        bound(partial, sum_bits, name + " ordered group accumulation")
        projected, saturated = terminal_s24(partial[-1])
        result[:, start:start + count] = projected
        audit["saturation"] += saturated
        audit["guard_abs_max"] = max(audit["guard_abs_max"], int(np.abs(guard).max()))
        audit["sum_abs_max"] = max(audit["sum_abs_max"], int(np.abs(partial).max()))
        for row, column in ((0, 0), (0, 7), (7, 8), (8, 15), (15, columns - 1)):
            if not start <= column < start + count:
                continue
            accumulator = 0
            for group in range(128):
                local = column - start
                vector = wb[group, :, local]
                if not ac[row, group] or not wc[group, local]:
                    value = 0
                elif gu:
                    dot = sum(int(act[group, row, lane]) * int(vector[lane]) for lane in range(32))
                    raw_scalar = MLP.require_signed(dot * int(ac[row, group]) * int(wc[group, local]), 33, "scalarGU raw")
                    value = MLP.mlp_recover_guard_s37(raw_scalar, int(total_shift[group, row, local]))
                else:
                    value = FIX.a8w8_group32_guard_s42(q[row, group], vector, int(zp[row, group]),
                        int(ac[row, group]), int(ash[row, group]), int(wc[group, local]), int(wsh[group, local]))
                assert value == int(guard[group, row, local]), (name, row, column, group)
                accumulator += value
            value, _ = FIX.round_sat_guard_s42_to_s24(accumulator) if not gu else (None, None)
            if gu:
                value = max(-8388608, min(8388607, MLP.round_shift_away_zero(accumulator, 8)))
            assert value == int(result[row, column])
            audit["scalar_samples"].append({"row": row, "column": column, "sum": accumulator, "s24": value, "all_groups": 128})
    audit["output_statistics"] = stats(result)
    return result, audit
