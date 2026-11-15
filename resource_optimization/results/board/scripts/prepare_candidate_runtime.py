import hashlib
import json
import shutil
from pathlib import Path

parent = Path(r"D:/ScaleLLM_final_model/final_96df1a5c_power_20261029_001")
root = Path(r"D:/ScaleLLM_final_model/dsp_all_board_20261115_001")
runtime = root / "runtime"
identity_path = parent / "source_identity.json"
identity_bytes = identity_path.read_bytes()
identity = json.loads(identity_bytes)
verified = {}
for relative, expected in identity.items():
    source = parent / relative
    source.resolve().relative_to(parent.resolve())
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != expected["bytes"] or digest != expected["sha256"]:
        raise ValueError("Original source identity mismatch " + relative)
    verified[relative] = {"bytes": len(data), "sha256": digest}
runtime.mkdir(exist_ok=False)
for relative in identity:
    destination = runtime / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(parent / relative, destination)
(runtime / "parent_source_identity.json").write_bytes(identity_bytes)
runner = runtime / "deploy/final/run.py"
source = runner.read_text()
changes = [
    ('    parser.add_argument("--wall-seconds", type=float, default=1800)\n', ''),
    ('                  wall_limit_seconds=args.wall_seconds)', '                  wall_limit_seconds=None, fixed_wall_time_termination=False)'),
    ('        if elapsed >= args.wall_seconds:\n            raise TimeoutError("model stage wall limit; no automatic reset/retry")\n', ''),
    ('                    if estimate > args.wall_seconds:\n                        raise TimeoutError("measured pilot exceeds stage budget; committed first round preserved")\n', ''),
]
for before, after in changes:
    if source.count(before) != 1:
        raise RuntimeError("Candidate runner patch expected exactly one match " + repr(before))
    source = source.replace(before, after)
runner.write_text(source)
compile(source, str(runner), "exec")
if "args.wall_seconds" in source:
    raise RuntimeError("Whole-run wall comparison remains")
candidate = {}
for relative, expected in identity.items():
    data = (runtime / relative).read_bytes()
    actual = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    candidate[relative] = actual
    if relative != "deploy/final/run.py" and actual != expected:
        raise RuntimeError("Unexpected candidate source difference " + relative)
receipt = {
    "schema": "scalellm_dsp_candidate_runtime_identity_v1",
    "status": "PASS", "parent_root": str(parent), "candidate_root": str(runtime),
    "parent_source_identity_sha256": hashlib.sha256(identity_bytes).hexdigest(),
    "verified_parent_files": verified, "candidate_files": candidate,
    "allowed_changes": {"deploy/final/run.py": "Remove fixed whole-run wall argument and two termination conditions, record null wall limit and fixed_wall_time_termination false"},
    "command_timeout_seconds": 120, "transport_timeout_ms": 5000,
    "fixed_wall_time_termination": False,
}
(runtime / "candidate_source_identity.json").write_text(json.dumps(receipt, indent=2))
config = {
    "schema": "scalellm_dsp_candidate_execution_config_v1",
    "bit_path": str(root / "bitstream/ScaleLLM_Final_Decode16_80MHz.bit"),
    "bit_sha256": "5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7",
    "runner": str(runner), "requests": str(runtime / "requests16.json"),
    "artifacts": "D:/ScaleLLM_inference/artifacts_8a09c60f3256_20261025T042725/scalecode_manifest.json",
    "assets": "D:/ScaleLLM_inference/artifacts_8a09c60f3256_20261025T042725/host_assets/manifest.json",
    "result": str(root / "inference"), "full_startup_hashes": True,
    "fixed_wall_time_termination": False, "command_timeout_seconds": 120,
    "transport_timeout_ms": 5000, "blas_threads": 1, "maximum_cpu_cores": 8,
}
(root / "candidate_execution_config.json").write_text(json.dumps(config, indent=2))
print(json.dumps({"status": "PASS", "parent_files": len(verified), "changed_files": [key for key in identity if verified[key] != candidate[key]], "runner": candidate["deploy/final/run.py"], "fixed_wall_time_termination": False}))
