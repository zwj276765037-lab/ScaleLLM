#!/usr/bin/env python3
"""Version only the local launcher hashes after a recorded script repair."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


for name in ("dsp_raw_only", "dsp_all"):
    work = ROOT / "runs" / name
    cfg_path = work / "build.json"
    manifest_path = work / "candidate_manifest.json"
    cfg = json.loads(cfg_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    if cfg["candidate"] != name or manifest["candidate"] != name:
        raise ValueError("Candidate mismatch: " + name)
    accepted = work / "synth_acceptance.json"
    if json.loads(accepted.read_text()).get("status") != "PASS":
        raise ValueError("Fresh synthesized checkpoint has not been qualified: " + name)
    original_inputs = json.loads((work / "synth/stage_inputs.json").read_text())
    if (original_inputs["build_json_sha256"] != sha(cfg_path) or
            original_inputs["candidate_manifest_sha256"] != sha(manifest_path) or
            original_inputs["candidate_driver_sha256"] != cfg["candidate_driver_sha256"] or
            original_inputs["stage_tcl_sha256"] != cfg["candidate_tcl_sha256"]):
        raise ValueError("Prior candidate identity differs from the preserved synthesis attempt: " + name)
    history = work / "identity_history"
    history.mkdir(exist_ok=True)
    current = sorted(history.glob("revision_*"))
    revision = history / ("revision_%03d" % len(current))
    revision.mkdir()
    shutil.copy2(cfg_path, revision / "build.json")
    shutil.copy2(manifest_path, revision / "candidate_manifest.json")
    new_driver = sha(ROOT / "scripts" / "run_board.py")
    new_tcl = sha(ROOT / "scripts" / "build_board.tcl")
    record = {"candidate": name,
              "prior_build_json_sha256": sha(revision / "build.json"),
              "prior_candidate_manifest_sha256": sha(revision / "candidate_manifest.json"),
              "prior_driver_sha256": cfg["candidate_driver_sha256"],
              "prior_tcl_sha256": cfg["candidate_tcl_sha256"],
              "new_driver_sha256": new_driver,
              "new_tcl_sha256": new_tcl,
              "post_opt_hook_sha256": sha(ROOT / "scripts" / "post_opt_guard.tcl"),
              "qualified_synth_acceptance_sha256": sha(accepted),
              "reason": "Literal recovery DSP attribution and zero-blackbox post-opt gate after exact synthesis debug-placeholder qualification"}
    cfg["candidate_driver_sha256"] = new_driver
    cfg["candidate_tcl_sha256"] = new_tcl
    manifest["driver_sha256"] = new_driver
    manifest["tcl_sha256"] = new_tcl
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    record["new_build_json_sha256"] = sha(cfg_path)
    record["new_candidate_manifest_sha256"] = sha(manifest_path)
    (revision / "revision.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))
