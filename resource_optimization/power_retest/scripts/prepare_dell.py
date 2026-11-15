import hashlib
import json
from pathlib import Path
import shutil
import socket
from datetime import datetime, timezone

root = Path(r"D:/ScaleLLM_final_model/dsp_all_power_20261115_001")
prior = Path(r"D:/ScaleLLM_final_model/dsp_all_board_20261115_001")
old = Path(r"D:/ScaleLLM_final_model/final_96df1a5c_power_20261029_001")
power = Path(r"D:/ScaleLLM_final_model/pmbus_kv128_sevenrail_20261102_001")
def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for data in iter(lambda: f.read(1 << 20), b""):
            h.update(data)
    return h.hexdigest()
identity = json.loads((prior / "runtime/candidate_source_identity.json").read_text())
for relative, expected in identity["candidate_files"].items():
    path = prior / "runtime" / relative
    if path.stat().st_size != expected["bytes"] or digest(path) != expected["sha256"]:
        raise RuntimeError("Previously board-tested runtime changed " + relative)
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    shutil.copyfile(path, destination)
shutil.copyfile(prior / "runtime/candidate_source_identity.json", root / "parent_runtime_identity.json")
bit = prior / "bitstream/ScaleLLM_Final_Decode16_80MHz.bit"
if bit.stat().st_size != 80159263 or digest(bit) != "5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7":
    raise RuntimeError("Candidate bit changed")
(root / "bitstream").mkdir()
shutil.copyfile(bit, root / "bitstream" / bit.name)
(root / "reference").mkdir()
snapshot = power / "readonly_inspection_002/kv_snapshot.bin"
if snapshot.stat().st_size != 268435456 or digest(snapshot) != "fa610d68fab6045573a355313f78808c93b7273dbf1edc2e8f61bc3ea1ad81c8":
    raise RuntimeError("Sealed full KV snapshot changed")
shutil.copyfile(snapshot, root / "reference/kv_snapshot.bin")
shutil.copyfile(power / "readonly_inspection_002/inspection.json", root / "reference/parent_inspection.json")
config = json.loads((old / "power_config.json").read_text(encoding="utf-8-sig"))
config["bit_path"] = str(root / "bitstream" / bit.name)
config["python"] = r"D:/ScaleLLM_inference/py312_20261025T042311/python/python.exe"
(root / "power_config.json").write_text(json.dumps(config, indent=2))
report = dict(schema="scalellm_dsp_power_preparation_v1", status="PASS", host=socket.gethostname(),
              created_utc=datetime.now(timezone.utc).isoformat(), target_bit_sha256=digest(bit),
              runtime_identity_sha256=digest(root / "parent_runtime_identity.json"), runtime_files=len(identity["candidate_files"]),
              snapshot_source=str(snapshot), snapshot_sha256=digest(snapshot), snapshot_bytes=snapshot.stat().st_size,
              copied_snapshot_sha256=digest(root / "reference/kv_snapshot.bin"),
              parent_inspection_sha256=digest(root / "reference/parent_inspection.json"),
              old_power_config_sha256=digest(old / "power_config.json"), adapter_serial=config["adapter_serial"],
              reference_main=r"D:/ScaleLLM_final_model/operator_kv128_20261101_001/run_002",
              powertool_runtime=r"D:/ScaleLLM_final_model/power_portable_cpu_20261029_001/official_runtime")
(root / "environment/preparation.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
