import hashlib
import json
from pathlib import Path
import socket
from datetime import datetime, timezone

root = Path(r"D:/ScaleLLM_final_model/dsp_all_board_20261115_001")
closure = json.loads((root / "board_stage_closure.json").read_text())
owner = json.loads((root / "board_owner.json").read_text())
if closure["status"] != "PASS" or owner["state"] != "CLOSED" or not owner["lease_released"]:
    raise RuntimeError("Final evidence inventory requires completed board-stage closure")
files = []
for directory in ("program", "health", "replay", "inference", "environment", "scripts"):
    files.extend(path for path in (root / directory).rglob("*") if path.is_file())
for relative in ("board_owner.json", "board_stage_closure.json", "candidate_execution_config.json",
                 "active_processes.json", "guardian.stop", "runtime/candidate_source_identity.json",
                 "runtime/parent_source_identity.json", "reference/reference_manifest.json"):
    files.append(root / relative)
source_identity = json.loads((root / "runtime/candidate_source_identity.json").read_text())
files.extend(root / "runtime" / relative for relative in source_identity["candidate_files"])
records = []
for path in sorted(set(files)):
    before = path.stat()
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1 << 20), b""):
            hasher.update(data)
    after = path.stat()
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise RuntimeError("Evidence changed during final inventory " + str(path))
    records.append(dict(path=path.relative_to(root).as_posix(), bytes=after.st_size, sha256=hasher.hexdigest()))
inventory = dict(schema="scalellm_dsp_board_evidence_inventory_v1", host=socket.gethostname(), root=str(root),
                 created_utc=datetime.now(timezone.utc).isoformat(), status="PASS",
                 file_count=len(records), total_bytes=sum(record["bytes"] for record in records), files=records)
(root / "evidence_inventory.json").write_text(json.dumps(inventory, indent=2))
print(json.dumps({key: inventory[key] for key in ("status", "file_count", "total_bytes")}))
