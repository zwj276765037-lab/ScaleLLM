"""Production-shape diagnostic data, independent of the DUT and model catalog.

Only the wire codecs/backend are reused by the executable driver. The sparse
integer source and numerical oracle in this file do not import RTL or backend.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import numpy as np

ROWS, GROUPS, N, LANES = 16, 128, 14336, 32
TILES, RECORDS = 896, 229376
SIZES = {"mlp_gate_up_c0": 29360128, "mlp_gate_up_c1": 29360128,
         "mlp_gate_meta": 7340032, "input_rec576": 73728,
         "gold_gu_s24": 1376256}
KIND = "scalellm_gu_production_shape_diagnostic_v1"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def active_groups(case):
    if case == "structured":
        return (0, 1, 126, 127)
    if case == "s37_cancellation":
        return tuple(range(16)) + (127,)
    raise ValueError(f"unknown diagnostic case {case}")


def activation(case, group):
    """Return independent q, zp, ScaleCode and shift for one active group."""
    row = np.arange(16, dtype=np.int64)[:, None]
    lane = np.arange(32, dtype=np.int64)[None, :]
    if case == "structured":
        if group == 0:
            q = 128 + ((row * 7 + lane * 11) % 31 - 15)
            return q, np.full(16, 128), 71 + np.arange(16) * 7, np.full(16, 10)
        if group == 1:
            q = np.zeros((16, 32), dtype=np.int64)
            q[:, 0] = 1
            return q, np.zeros(16, dtype=np.int64), np.full(16, 128), np.full(16, 12)
        if group == 126:
            return np.full((16, 32), 255), np.zeros(16, dtype=np.int64), np.full(16, 255), np.full(16, 10)
        if group == 127:
            q = 128 + ((row * 13 + lane * 3) % 255 - 127)
            return q, np.full(16, 128), np.full(16, 255), np.full(16, 22)
    elif case == "s37_cancellation":
        if group < 15:
            return np.full((16, 32), 255), np.zeros(16, dtype=np.int64), np.full(16, 255), np.full(16, 10)
        if group in (15, 127):
            q = np.zeros((16, 32), dtype=np.int64)
            q[:, 0] = np.arange(16) + 1
            return q, np.zeros(16, dtype=np.int64), np.full(16, 128), np.full(16, 12)
    raise ValueError((case, group))


def weights(case, matrix, columns, group):
    """Return per-column S4[32], U8 code and U6 shift, no dense matrix."""
    col = np.asarray(columns, dtype=np.int64)
    lane = np.arange(32, dtype=np.int64)[None, :]
    w = np.zeros((len(col), 32), dtype=np.int64)
    code, shift = np.zeros(len(col), dtype=np.int64), np.zeros(len(col), dtype=np.int64)
    if case == "structured":
        regular = ~np.isin(col, (0, 1, 7, 8))
        if group == 0:
            w[regular] = ((col[regular, None] * 3 + lane * 5 + matrix * 7) % 16) - 8
            code[regular] = 3 + (col[regular] * 11 + matrix * 17) % 127
            shift[regular] = 10
        elif group == 1:
            w[regular, 0] = (col[regular] * 5 + matrix * 3) % 15 - 7
            code[regular] = 5 + (col[regular] * 3 + matrix * 11) % 251
            shift[regular] = 13
            # Exact +/-0.5 F16 ties, independent of the other three groups.
            for column, sign in ((0, 1), (1, -1)):
                mask = col == column
                w[mask, 0], code[mask], shift[mask] = sign, 1, 12
        elif group == 126:
            for column, sign in ((7, 7), (8, -8)):
                mask = col == column
                w[mask], code[mask], shift[mask] = sign, 255, 10
        elif group == 127:
            w[regular] = ((col[regular, None] * 7 + lane * 3 + matrix * 5) % 16) - 8
            code[regular] = 129 + (col[regular] + matrix * 29) % 127
            shift[regular] = 22
    elif case == "s37_cancellation":
        if group < 15:
            # 8*(+7) + 7*(-8) = 0. Both magnitudes exceed signed S36.
            w[:] = 7 if group < 8 else -8
            code[:], shift[:] = 255, 10
        elif group == 15:
            w[:, 0] = 1 + (col + matrix * 3) % 7
            code[:], shift[:] = 2 + (col * 5 + matrix * 7) % 127, 12
        elif group == 127:
            w[:, 0] = -1 - (col + matrix) % 8
            code[:], shift[:] = 1, 12
    # Enforce the weight zero-code contract even when all q multiply zero.
    assert np.all(w[code == 0] == 0) and np.all(shift[code == 0] == 0)
    return w, code, shift


def signed_bound(value, bits, name):
    values = np.asarray(value)
    if np.any(values < -(1 << (bits - 1))) or np.any(values >= (1 << (bits - 1))):
        raise AssertionError(f"{name} exceeds S{bits}")


def finish(accumulator):
    signed_bound(accumulator, 44, "GU sum")
    magnitude = (np.abs(accumulator) + 128) // 256
    rounded = np.where(accumulator < 0, -magnitude, magnitude)
    return np.clip(rounded, -(1 << 23), (1 << 23) - 1)


def source_gold(case):
    """Exact int64 sparse oracle before any wire encoding or DUT execution."""
    outputs = np.zeros((2, 16, N), dtype=np.int64)
    guard_min = guard_max = 0
    outside_s36 = 0
    shift_counts = {}
    peak_sum = 0
    for tile in range(TILES):
        cols = np.arange(tile * 16, tile * 16 + 16)
        for matrix in (0, 1):
            total = np.zeros((16, 16), dtype=np.int64)
            for group in active_groups(case):
                q, zp, acode, ashift = activation(case, group)
                w, wcode, wshift = weights(case, matrix, cols, group)
                dot = (q - zp[:, None]) @ w.T
                signed_bound(dot, 17, "dot")
                raw = dot * acode[:, None] * wcode[None, :]
                signed_bound(raw, 33, "raw")
                nonzero = (acode[:, None] != 0) & (wcode[None, :] != 0)
                shifts = ashift[:, None] + wshift[None, :]
                assert np.all((shifts[nonzero] >= 20) & (shifts[nonzero] <= 44))
                left, right = np.maximum(24 - shifts, 0), np.maximum(shifts - 24, 0)
                guard = np.where(nonzero, np.left_shift(raw, left) >> right, 0)
                signed_bound(guard, 37, "guard")
                total += guard
                signed_bound(total, 44, "partial sum")
                guard_min, guard_max = min(guard_min, int(guard.min())), max(guard_max, int(guard.max()))
                outside_s36 += int(np.count_nonzero((guard < -(1 << 35)) | (guard >= (1 << 35))))
                peak_sum = max(peak_sum, int(np.abs(total).max()))
                for value, count in zip(*np.unique(shifts[nonzero], return_counts=True)):
                    shift_counts[str(int(value))] = shift_counts.get(str(int(value)), 0) + int(count)
            outputs[matrix, :, tile * 16:tile * 16 + 16] = finish(total)
    return outputs, {"guard_min": guard_min, "guard_max": guard_max,
                     "guard_outside_s36_count": outside_s36,
                     "peak_absolute_partial_s44": peak_sum, "nonzero_total_shift_counts": shift_counts}


def pack_output(outputs):
    values = outputs.reshape(2, 16, 896, 16).transpose(2, 0, 1, 3)
    unsigned = values & 0xFFFFFF
    return np.stack([(unsigned >> (8 * byte)) & 255 for byte in range(3)], axis=-1).astype(np.uint8).tobytes()


def decode_output(payload):
    data = np.frombuffer(payload, np.uint8).reshape(896, 2, 16, 16, 3).astype(np.int64)
    unsigned = data[..., 0] + 256 * data[..., 1] + 65536 * data[..., 2]
    signed = np.where(unsigned >= 8388608, unsigned - 16777216, unsigned)
    return signed.transpose(1, 2, 0, 3).reshape(2, 16, N)


def output_statistics(outputs):
    return {"values": int(outputs.size), "nonzero": int(np.count_nonzero(outputs)),
            "negative": int(np.count_nonzero(outputs < 0)), "positive": int(np.count_nonzero(outputs > 0)),
            "min": int(outputs.min()), "max": int(outputs.max()),
            "saturation_endpoint_count": int(np.count_nonzero((outputs == -8388608) | (outputs == 8388607))),
            "per_matrix_nonzero": [int(np.count_nonzero(x)) for x in outputs],
            "per_row_nonzero": [int(np.count_nonzero(outputs[:, row])) for row in range(16)],
            "tail_block_columns": [14304, 14335],
            "tail_block_nonzero": int(np.count_nonzero(outputs[:, :, 14304:])),
            "tail_column_14335": outputs[:, :, 14335].tolist(),
            "row_markers_0_7_8_15_column_14335": outputs[:, [0, 7, 8, 15], 14335].tolist()}


@dataclass(frozen=True)
class DiagnosticRecord:
    path: Path
    size: int
    sha256: str

    def read_verified(self):
        data = self.path.read_bytes()
        if len(data) != self.size or digest(data) != self.sha256:
            raise ValueError(f"diagnostic artifact size/SHA mismatch: {self.path}")
        return data


class DiagnosticArtifacts:
    """Explicit one-layer diagnostic provider; never a production model catalog."""
    def __init__(self, bundle):
        self.bundle = Path(bundle).resolve()
        self.manifest = json.loads((self.bundle / "manifest.json").read_text(encoding="utf-8"))
        if self.manifest.get("schema_kind") != KIND or self.manifest.get("diagnostic_only") is not True:
            raise ValueError("not an explicitly identified GU diagnostic bundle")
        if self.manifest.get("shape") != {"rows": 16, "groups": 128, "k": 4096, "n": 14336}:
            raise ValueError("diagnostic shape mismatch")
        self.records = {}
        for name, size in SIZES.items():
            entry = self.manifest["files"][name]
            path = (self.bundle / entry["path"]).resolve()
            if path.parent != self.bundle or entry["size"] != size:
                raise ValueError(f"diagnostic path/size mismatch: {name}")
            self.records[name] = DiagnosticRecord(path, size, entry["sha256"])
        self.original = self

    def layer_artifact(self, layer, name):
        if type(layer) is not int or layer != 0 or name not in ("mlp_gate_up_c0", "mlp_gate_up_c1", "mlp_gate_meta"):
            raise ValueError("diagnostic provider supports only diagnostic layer0 GU artifacts")
        return self.records[name]
