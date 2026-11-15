from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket

root = Path(r"D:/ScaleLLM_final_model/dsp_all_power_20261115_001")
closure = json.loads((root / "closure.json").read_text())
if closure["status"] != "PASS" or not closure["guardian"]["lease_released"]:
    raise RuntimeError("Collection closure is required before final inventory")

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1 << 20), b""):
            h.update(data)
    return h.hexdigest()

records = []
for directory in ("pilot_001", "restore_001", "main_001", "program", "health", "environment", "scripts"):
    for path in sorted((root / directory).rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            relative = path.relative_to(root).as_posix()
            local = "source_as_run/" + path.name if directory == "scripts" else relative
            records.append(dict(path=relative, local_path=local, bytes=path.stat().st_size, sha256=sha(path)))
for relative in ("closure.json", "board_owner.json", "active_processes.json", "power_config.json", "run_config.json",
                 "parent_runtime_identity.json", "pilot_frozen.json", "pilot_frozen_pre_correction.json", "reference/parent_inspection.json"):
    path = root / relative
    records.append(dict(path=relative, local_path=relative, bytes=path.stat().st_size, sha256=sha(path)))
identity = json.loads((root / "parent_runtime_identity.json").read_text())
for relative in identity["candidate_files"]:
    path = root / relative
    records.append(dict(path=relative, local_path="runtime_source/" + relative, bytes=path.stat().st_size, sha256=sha(path)))
snapshot = root / "reference/kv_snapshot.bin"
bit = root / "bitstream/ScaleLLM_Final_Decode16_80MHz.bit"
external = {"private_kv_snapshot": dict(path=str(snapshot), bytes=snapshot.stat().st_size, sha256=sha(snapshot), included_in_transfer=False),
            "programmed_bitstream": dict(path=str(bit), bytes=bit.stat().st_size, sha256=sha(bit), included_in_transfer=False)}
manifest = dict(schema="scalellm_dsp_power_raw_inventory_v1", status="PASS", host=socket.gethostname(), root=str(root),
                created_utc=datetime.now(timezone.utc).isoformat(), files=records, external_dependencies=external,
                file_count=len(records), total_bytes=sum(item["bytes"] for item in records))
(root / "raw_inventory.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({key: manifest[key] for key in ("status", "file_count", "total_bytes")}))
