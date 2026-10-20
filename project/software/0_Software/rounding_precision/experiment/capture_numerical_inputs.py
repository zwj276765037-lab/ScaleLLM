"""Array input packaging; current CPU mode preserves legacy smoke provenance.

New clean-document GPU/production capture is not executed by this CPU tool.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import traceback
from run_numerical_fidelity import cpu_supervise, identity, write_json


def linear_arrays(artifact):
    import numpy as np
    qa = artifact["q_a"].astype(np.int64) - artifact["zero_point"].astype(np.int64)[..., None]
    qw = artifact["q_w"].astype(np.int64)
    dot = np.einsum("rgl,cgl->rcg", qa, qw)
    shape = dot.shape
    arrays = {"dot": dot.reshape(-1, shape[-1])}
    for key in ["act_code", "act_shift"]:
        arrays[key] = np.broadcast_to(artifact[key][:, None, :], shape).reshape(-1, shape[-1]).copy()
    for key in ["weight_code", "weight_shift"]:
        arrays[key] = np.broadcast_to(artifact[key][None, :, :], shape).reshape(-1, shape[-1]).copy()
    return arrays, list(shape[:-1])


def pack_worker(args):
    import numpy as np
    origin = args.legacy_capture_dir.resolve()
    captured = json.loads((origin / "input_identity.json").read_text())
    sources = json.loads((origin / "capture_manifest.json").read_text())
    production = next(item for item in sources["code"] if item["path"].endswith("/v5_fullchain.py"))
    doc_id = "engineering_smoke:" + captured["text_sha256"]
    directory = args.output_dir / "inputs"
    directory.mkdir()
    cases = []
    for path in sorted((origin / "integer_artifacts").glob("layer*_*.npz")):
        match = re.fullmatch(r"layer(\d+)_(.+)\.npz", path.name)
        layer, op = int(match[1]), match[2]
        with np.load(path, allow_pickle=False) as artifact:
            arrays, shape = linear_arrays(artifact)
            tokens, channels = artifact["token_rows"].tolist(), artifact["output_channels"].tolist()
        profile = "mlp_down" if op == "down_proj" else "mlp_gate_up" if op in ["gate_proj", "up_proj"] else "attention"
        expected = 448 if profile == "mlp_down" else 128
        if arrays["dot"].shape[-1] != expected:
            raise ValueError("incomplete Linear group geometry")
        target = directory / path.name
        with target.open("xb") as stream:
            np.savez_compressed(stream, **arrays)
        frozen = identity(target)
        cases.append({"doc_id": doc_id, "source_id": captured["line_index_zero_based"],
                      "domain": "legacy_mixed_smoke", "split": "engineering", "text_sha256": captured["text_sha256"],
                      "duplicate_cluster": doc_id, "evidence_role": "engineering_smoke", "trajectory": "bf16",
                      "layer": layer, "node": "linear", "op": op, "config": {"profile": profile},
                      "input_npz": frozen["path"], "sha256": frozen["sha256"], "output_shape": shape,
                      "output_selection": {"tokens": tokens, "channels": channels, "flatten_order": "row_major"},
                      "target_format": "0x48384103" if profile == "attention" else "0x48384605",
                      "production_source_hash": production["sha256"], "lut_or_coefficient_hash": None,
                      "source_files": [identity(path), identity(origin / "input_identity.json"), identity(origin / "capture_manifest.json")]})
    if not cases:
        raise ValueError("no actual source artifacts")
    write_json(args.output_dir / "array_input_manifest.json", {"schema": "m005_numerical_array_inputs_v1", "cases": cases,
               "document_count": 1, "tensor_count": len(cases), "source_scope": "legacy BF16 engineering smoke only",
               "formal_eval_documents": 0, "new_gpu_capture_performed": False,
               "limitation": "does not represent clean dev/eval or production/continuous paths"})
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-capture-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--wall-seconds", type=int, default=300)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    try:
        code = pack_worker(args) if args.worker else cpu_supervise(args, __file__, "pack")
    except Exception:
        traceback.print_exc()
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
