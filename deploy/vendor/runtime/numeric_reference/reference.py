"""Real-artifact blocked Attention/GU expected outputs, independent of DUT.

Public bytes APIs: attention(input_s24, layer_artifacts, rope),
gu(input_rec576, layer_artifacts), both return (gold_bytes, audit).
ReferenceLayer caches one layer's verified decode for two cohorts.
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from core import (FIX, LUT, HW, bound, decode_s24, encode_s24, decode_rec576,
                  group_projection, prepare_attention_a8, read_record,
                  round_away, sha, stats, terminal_s24)

REFERENCE_SOURCES = [{"path": str(path), "sha256": sha(path.read_bytes())} for path in
                     (Path(__file__), Path(__file__).with_name("core.py"), HW / "model/fixbit_v2.py",
                      HW / "model/mlp_fixed.py", HW / "data/softmax_exp_u17.mem")]


def _rope(values, rope):
    words = np.frombuffer(rope, dtype="<u8").reshape(16, 64)
    if len(rope) != 8192 or np.any(words >> 36):
        raise ValueError("invalid RoPE bytes/reserved bits")
    cos = ((words & 0x3FFFF).astype(np.int64) ^ 0x20000) - 0x20000
    sin = (((words >> 18 & 0x3FFFF).astype(np.int64)) ^ 0x20000) - 0x20000
    if np.any(np.abs(cos) > 65536) or np.any(np.abs(sin) > 65536):
        raise ValueError("RoPE coefficient magnitude>1")
    heads = values.shape[1] // 128
    pairs = values.reshape(16, heads, 64, 2)
    x0, x1 = pairs[..., 0], pairs[..., 1]
    a = round_away(x0 * cos[:, None, :], 16)
    b = round_away(x1 * sin[:, None, :], 16)
    c = round_away(x0 * sin[:, None, :], 16)
    d = round_away(x1 * cos[:, None, :], 16)
    for item in (a, b, c, d):
        bound(item, 25, "RoPE separately rounded product")
    y = np.stack((a - b, c + d), axis=-1)
    result = np.clip(y, -8388608, 8388607)
    samples = []
    for row, head, pair in ((0, 0, 0), (7, heads - 1, 31), (8, 0, 32), (15, heads - 1, 63)):
        first, second, _ = FIX.rope_pair_s24(int(x0[row, head, pair]), int(x1[row, head, pair]), int(cos[row, pair]), int(sin[row, pair]))
        assert (first, second) == tuple(map(int, result[row, head, pair]))
        samples.append({"row": row, "head": head, "pair": pair, "s24": [first, second]})
    return result.reshape(values.shape), {"saturation": int(np.count_nonzero(result != y)), "scalar_samples": samples}


def _kv12(values):
    values = values.reshape(16, 8, 4, 32)
    quantized = np.zeros_like(values)
    codes, shifts = np.zeros((16, 8, 4), dtype=np.int64), np.zeros((16, 8, 4), dtype=np.int64)
    clips = 0
    for row in range(16):
        for head in range(8):
            for group in range(4):
                record = FIX.kv12_quantize_s24(values[row, head, group])
                quantized[row, head, group] = record.values
                codes[row, head, group], shifts[row, head, group] = record.scale_code, record.scale_shift
                clips += record.clip_count
    return (quantized, codes, shifts), {"clip_count": clips, "nonzero_groups": int(np.count_nonzero(codes)),
             "shift_min": int(shifts[codes != 0].min()) if np.any(codes) else 0, "shift_max": int(shifts.max())}


def _qk_softmax(query, keys):
    key_values, key_codes, key_shifts = keys
    q = query.reshape(16, 32, 4, 32)
    k = np.repeat(key_values, 4, axis=1)
    codes = np.repeat(key_codes, 4, axis=1)
    shifts = np.repeat(key_shifts, 4, axis=1)
    # Exact int64 Q24*K12 dot across32lanes for every query/head/group/key.
    dots = np.matmul(q.transpose(1, 2, 0, 3), k.transpose(1, 2, 3, 0)).transpose(2, 0, 1, 3)
    bound(dots, 40, "QK group dot")
    kc = codes.transpose(1, 2, 0)[None, :, :, :]
    ks = shifts.transpose(1, 2, 0)[None, :, :, :]
    raw = dots * kc
    bound(raw, 48, "QK dot times code")
    scaled = raw * 5793
    bound(scaled, 61, "QK head scale")
    group_scores = np.where(kc != 0, scaled >> (ks + 18), 0)
    bound(group_scores, 35, "QK group score")
    score_sum = np.sum(group_scores, axis=2, dtype=np.int64)
    bound(score_sum, 37, "QK four-group sum")
    scores = np.clip(score_sum, -(16 << 14), 16 << 14)
    bound(scores, 20, "QK clipped score")
    valid = np.arange(16)[None, None, :] <= np.arange(16)[:, None, None]
    maximum = np.where(valid, scores, -(1 << 19)).max(axis=-1, keepdims=True)
    delta = np.clip(scores - maximum, -(16 << 14), 0)
    magnitude = -delta
    index, fraction = magnitude >> 10, magnitude & 1023
    high, low = LUT[index], LUT[np.minimum(index + 1, 256)]
    exponents = np.where(valid, high - (((high - low) * fraction + 512) >> 10), 0)
    total = exponents.sum(axis=-1, keepdims=True, dtype=np.int64)
    if np.any(total < 65536) or np.any(total > (1 << 23)):
        raise ValueError("Softmax row sum invalid")
    reciprocal = ((1 << 32) + total // 2) // total
    probability = np.minimum(65535, (exponents * reciprocal + 32768) >> 16)
    scalar_samples = []
    for row, head in ((0, 0), (7, 31), (8, 0), (15, 31)):
        kv_head = head // 4
        kg = [key_values[key, kv_head].tolist() if key < 16 else [[0] * 32 for _ in range(4)] for key in range(128)]
        kc_scalar = [key_codes[key, kv_head].tolist() if key < 16 else [0] * 4 for key in range(128)]
        ks_scalar = [key_shifts[key, kv_head].tolist() if key < 16 else [0] * 4 for key in range(128)]
        mask = [key > row for key in range(128)]
        scalar_scores, _ = FIX.qk_score_row_s20(q[row, head], kg, kc_scalar, ks_scalar, mask)
        assert list(scalar_scores[:16]) == scores[row, head].tolist()
        scalar_probability, _, scalar_total, scalar_recip = FIX.softmax_row_u16(scalar_scores, mask)
        assert list(scalar_probability[:16]) == probability[row, head].tolist() and not any(scalar_probability[16:])
        assert scalar_total == int(total[row, head, 0]) and scalar_recip == int(reciprocal[row, head, 0])
        scalar_samples.append({"row": row, "head": head, "kv_head": kv_head,
                               "probability_u16": probability[row, head].tolist()})
    return probability, {"qk_score_clip": int(np.count_nonzero(scores != score_sum)),
             "score_statistics": stats(scores), "probability_statistics": stats(probability),
             "softmax_row_sum_min": int(total.min()), "softmax_row_sum_max": int(total.max()),
             "scalar_samples": scalar_samples}


def _pv(probability, values):
    value, code, shift = values
    value = np.repeat(value, 4, axis=1)  # key,query-head,group,lane
    code = np.repeat(code, 4, axis=1)
    shift = np.repeat(shift, 4, axis=1)
    output = np.zeros((16, 32, 4, 32), dtype=np.int64)
    saturation = 0
    for head in range(0, 32, 4):
        vcode = value[:, head:head + 4] * code[:, head:head + 4, :, None]
        bound(vcode, 20, "PV V*code")
        p = probability[:, head:head + 4, :].transpose(0, 2, 1)[:, :, :, None, None]
        raw = p * vcode[None, :, :, :, :]
        bound(raw, 36, "PV raw")
        sh = np.where(code[:, head:head + 4] != 0, shift[:, head:head + 4] - 8, 0)
        guard = raw >> sh[None, :, :, :, None]
        partial = np.cumsum(guard, axis=1, dtype=np.int64)
        bound(partial, 43, "PV ordered key accumulator")
        projected, count = terminal_s24(partial[:, -1])
        output[:, head:head + 4] = projected
        saturation += count
    samples = []
    for row, head, group, half in ((0, 0, 0, 0), (7, 31, 3, 1), (8, 0, 1, 0), (15, 31, 2, 1)):
        probs = probability[row, head].tolist() + [0] * 112
        vectors, codes, shifts = [], [], []
        for key in range(128):
            if key < 16:
                vectors.append(value[key, head, group, half * 16:half * 16 + 16].tolist())
                codes.append(int(code[key, head, group]))
                shifts.append(int(shift[key, head, group]))
            else:
                vectors.append([0] * 16)
                codes.append(0)
                shifts.append(0)
        scalar, _ = FIX.pv_row_tile16_s24(probs, vectors, codes, shifts)
        assert list(scalar) == output[row, head, group, half * 16:half * 16 + 16].tolist()
        samples.append({"row": row, "head": head, "group": group, "half": half, "s24": list(scalar)})
    return output.reshape(16, 4096), {"saturation": saturation, "scalar_samples": samples}


class ReferenceLayer:
    def __init__(self, layer_artifacts):
        self.artifacts = layer_artifacts
        self.identities = {}
        self.attention_decoded = None
        self.gu_decoded = None

    def _load_attention(self):
        if self.attention_decoded is not None:
            return self.attention_decoded
        arrays = []
        for name in ("attention_c0", "attention_c1"):
            data, record = read_record(self.artifacts, name, 20971520)
            self.identities[name] = record
            arrays.append(np.frombuffer(data, np.int8).reshape(640, 128, 8, 32))
        w = np.concatenate(arrays, axis=2)
        data, record = read_record(self.artifacts, "attention_meta", 2621440)
        self.identities["attention_meta"] = record
        metadata = np.frombuffer(data, np.uint8).reshape(640, 128, 16, 2)
        code, shift = metadata[..., 0].copy(), metadata[..., 1].copy()
        if np.any(shift > 63):
            raise ValueError("Attention weight shift reserved bits")
        zero = code == 0
        if np.any(shift[zero]) or np.any(w[zero]):
            raise ValueError("Attention noncanonical weight zero")
        self.attention_decoded = w, code, shift
        return self.attention_decoded

    def _load_gu(self):
        if self.gu_decoded is not None:
            return self.gu_decoded
        weights = np.empty((1792, 128, 16, 32), dtype=np.int8)
        for half, name in enumerate(("mlp_gate_up_c0", "mlp_gate_up_c1")):
            data, record = read_record(self.artifacts, name, 29360128)
            self.identities[name] = record
            packed = np.frombuffer(data, np.uint8).reshape(1792, 128, 8, 16)
            weights[:, :, half * 8:half * 8 + 8, 0::2] = packed & 15
            weights[:, :, half * 8:half * 8 + 8, 1::2] = packed >> 4
        np.subtract(weights, 16, out=weights, where=weights >= 8)
        data, record = read_record(self.artifacts, "mlp_gate_meta", 7340032)
        self.identities["mlp_gate_meta"] = record
        metadata = np.frombuffer(data, np.uint8).reshape(229376, 32)
        if np.any(metadata[:, 28:]):
            raise ValueError("GU weight metadata padding")
        codes = metadata[:, :16].copy()
        shifts = np.empty((229376, 16), dtype=np.uint8)
        for column in range(16):
            byte, bit = divmod(column * 6, 8)
            word = metadata[:, 16 + byte].astype(np.uint16)
            if byte + 1 < 12:
                word |= metadata[:, 17 + byte].astype(np.uint16) << 8
            shifts[:, column] = (word >> bit) & 63
        codes, shifts = codes.reshape(1792, 128, 16), shifts.reshape(1792, 128, 16)
        zero = codes == 0
        if np.any(shifts[zero]) or np.any(weights[zero]):
            raise ValueError("GU noncanonical weight zero")
        self.gu_decoded = weights.reshape(896, 2, 128, 16, 32), codes.reshape(896, 2, 128, 16), shifts.reshape(896, 2, 128, 16)
        return self.gu_decoded

    def attention(self, input_s24, rope):
        started = time.monotonic()
        x = decode_s24(input_s24)
        prepared, front_audit = prepare_attention_a8(x)
        weights, codes, shifts = self._load_attention()
        projections, audits = {}, {}
        offset = 0
        for op, columns in (("Q", 4096), ("K", 1024), ("V", 1024)):
            tiles = columns // 16
            projections[op], audits[op] = group_projection(prepared, weights[offset:offset + tiles], codes[offset:offset + tiles], shifts[offset:offset + tiles], name=op)
            offset += tiles
        query, qrope = _rope(projections["Q"], rope)
        key, krope = _rope(projections["K"], rope)
        key_cache, key_audit = _kv12(key)
        value_cache, value_audit = _kv12(projections["V"])
        probability, score_audit = _qk_softmax(query, key_cache)
        context, pv_audit = _pv(probability, value_cache)
        context_prepared, context_audit = prepare_attention_a8(context)
        output, audits["Wo"] = group_projection(context_prepared, weights[384:640], codes[384:640], shifts[384:640], name="Wo")
        payload = encode_s24(output)
        return payload, {"kind": "real_artifact_blocked_attention_v1", "reference_sources": REFERENCE_SOURCES,
                    "numpy_version": np.__version__, "input_sha256": sha(input_s24), "rope_sha256": sha(rope),
                    "artifact_identity": {k: self.identities[k] for k in ("attention_c0", "attention_c1", "attention_meta")},
                    "input_frontend": front_audit, "projection": audits, "query_rope": qrope, "key_rope": krope,
                    "key_kv12": key_audit, "value_kv12": value_audit, "qk_softmax": score_audit,
                    "pv": pv_audit, "context_frontend": context_audit, "output_statistics": stats(output),
                    "output_sha256": sha(payload), "elapsed_seconds": time.monotonic() - started,
                    "shape": {"rows": 16, "query_start": 0, "valid_key_count": 16, "preserve_historical_kv": False},
                    "scope": "independent CPU expected output from supplied real artifacts and input; no DUT reads"}

    def gu(self, input_rec576):
        started = time.monotonic()
        prepared = decode_rec576(input_rec576)
        weights, codes, shifts = self._load_gu()
        values, audit = [], {}
        for matrix, name in ((0, "Gate"), (1, "Up")):
            result, audit[name] = group_projection(prepared, weights[:, matrix], codes[:, matrix], shifts[:, matrix], gu=True, name=name)
            values.append(result)
        wire = np.stack(values).reshape(2, 16, 896, 16).transpose(2, 0, 1, 3)
        payload = encode_s24(wire)
        assert len(payload) == 1376256
        return payload, {"kind": "real_artifact_blocked_gu_v1", "reference_sources": REFERENCE_SOURCES,
                 "numpy_version": np.__version__, "input_sha256": sha(input_rec576),
                 "artifact_identity": {k: self.identities[k] for k in ("mlp_gate_up_c0", "mlp_gate_up_c1", "mlp_gate_meta")},
                 "projection": audit, "output_statistics": stats(values), "output_sha256": sha(payload),
                 "elapsed_seconds": time.monotonic() - started,
                 "scope": "independent CPU expected output from supplied real artifacts and input; no DUT reads"}


def attention(input_s24, layer_artifacts, rope):
    return ReferenceLayer(layer_artifacts).attention(input_s24, rope)


def gu(input_rec576, layer_artifacts):
    return ReferenceLayer(layer_artifacts).gu(input_rec576)
