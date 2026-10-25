"""Contract-exact 128-active-group diagnostic and distinct artifact provider."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import numpy as np

KIND = "scalellm_gu_dense_active128_diagnostic_v1"
SHAPE = {"rows": 16, "groups": 128, "k": 4096, "n": 14336}
SIZES = {"mlp_gate_up_c0": 29360128, "mlp_gate_up_c1": 29360128,
         "mlp_gate_meta": 7340032, "input_rec576": 73728,
         "gold_gu_s24": 1376256}
BIT_SHA = "66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def root_path():
    return next(p for p in Path(__file__).resolve().parents if (p / "project/hardware/source/mlp_linear/abi_gu_only.json").is_file())


def activation(group):
    r, k = np.arange(16, dtype=np.int64)[:, None], np.arange(32, dtype=np.int64)[None, :]
    delta = np.where((k + r + group) % 2, -1, 1) * (1 + (k + 3 * r + group) % 7)
    return 128 + delta, 17 + (np.arange(16) + group) % 13, 14 + (np.arange(16) + group) % 3


def weight(matrix, group):
    c, k = np.arange(32, dtype=np.int64)[:, None], np.arange(32, dtype=np.int64)[None, :]
    w = np.where((k + c + group + matrix) % 2, -1, 1) * (1 + (3 * k + 5 * c + group + 2 * matrix) % 7)
    return w, 19 + (np.arange(32) + 3 * group + matrix) % 11, 14 + (np.arange(32) + group + matrix) % 3


def period_gold():
    """Independent exact integer source; only 2*16*32*128*32 MAC."""
    sums = np.zeros((2, 16, 32), dtype=np.int64)
    extrema = {"dot_abs_max": 0, "raw_abs_max": 0, "guard_abs_max": 0,
               "partial_sum_abs_max": 0, "actual_total_shifts": set()}
    for group in range(128):
        q, ac, ash = activation(group)
        for matrix in (0, 1):
            w, wc, wsh = weight(matrix, group)
            dots = (q - 128) @ w.T
            raw = dots * ac[:, None] * wc[None, :]
            shifts = ash[:, None] + wsh[None, :]
            assert np.all((shifts >= 28) & (shifts <= 32))
            # All shifts are right shifts here; np signed int64 preserves floor.
            guards = raw >> (shifts - 24)
            assert np.all((dots >= -65536) & (dots < 65536))
            assert np.all((raw >= -(1 << 32)) & (raw < (1 << 32)))
            assert np.all((guards >= -(1 << 36)) & (guards < (1 << 36)))
            sums[matrix] += guards
            assert np.all((sums >= -(1 << 43)) & (sums < (1 << 43)))
            extrema["dot_abs_max"] = max(extrema["dot_abs_max"], int(np.abs(dots).max()))
            extrema["raw_abs_max"] = max(extrema["raw_abs_max"], int(np.abs(raw).max()))
            extrema["guard_abs_max"] = max(extrema["guard_abs_max"], int(np.abs(guards).max()))
            extrema["partial_sum_abs_max"] = max(extrema["partial_sum_abs_max"], int(np.abs(sums).max()))
            extrema["actual_total_shifts"].update(map(int, np.unique(shifts)))
    magnitude = (np.abs(sums) + 128) >> 8
    output = np.where(sums < 0, -magnitude, magnitude)
    assert np.all((output > -8388608) & (output < 8388607)), "unexpected saturation"
    extrema["actual_total_shifts"] = sorted(extrema["actual_total_shifts"])
    return output, extrema


def encode_gold_period(values):
    wire = values.reshape(2, 16, 2, 16).transpose(2, 0, 1, 3)
    encoded = np.stack([(wire >> (8 * b)) & 255 for b in range(3)], axis=-1).astype(np.uint8)
    return encoded.tobytes()


def decode_output(payload):
    b = np.frombuffer(payload, np.uint8).reshape(896, 2, 16, 16, 3).astype(np.int64)
    u = b[..., 0] + 256 * b[..., 1] + 65536 * b[..., 2]
    return np.where(u >= 8388608, u - 16777216, u).transpose(1, 2, 0, 3).reshape(2, 16, 14336)


@dataclass(frozen=True)
class DenseRecord:
    path: Path
    size: int
    sha256: str

    def read_verified(self):
        data = self.path.read_bytes()
        if len(data) != self.size or sha(data) != self.sha256:
            raise ValueError(f"dense diagnostic identity mismatch: {self.path}")
        return data


class DenseArtifacts:
    """One explicit diagnostic layer; not a production model manifest."""
    def __init__(self, bundle):
        self.bundle = Path(bundle).resolve()
        self.manifest = json.loads((self.bundle / "manifest.json").read_text(encoding="utf-8"))
        if self.manifest.get("schema_kind") != KIND or self.manifest.get("diagnostic_only") is not True or self.manifest.get("shape") != SHAPE:
            raise ValueError("wrong dense diagnostic kind/shape")
        self.records = {}
        for name, size in SIZES.items():
            record = self.manifest["files"][name]
            path = (self.bundle / record["path"]).resolve()
            if path.parent != self.bundle or record["size"] != size:
                raise ValueError(f"dense diagnostic path/size mismatch: {name}")
            self.records[name] = DenseRecord(path, size, record["sha256"])
        self.original = self

    def layer_artifact(self, layer, name):
        if type(layer) is not int or layer != 0 or name not in ("mlp_gate_up_c0", "mlp_gate_up_c1", "mlp_gate_meta"):
            raise ValueError("dense diagnostic only supports layer0 GU")
        return self.records[name]
