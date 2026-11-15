import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kv128_sevenrail_workload as work

root = Path(r"D:/ScaleLLM_final_model/dsp_all_power_20261115_001")
reference = Path(r"D:/ScaleLLM_final_model/operator_kv128_20261101_001/run_002")
snapshot = root / "reference/kv_snapshot.bin"
out = root / "restore_001"
out.mkdir(exist_ok=False)
report = dict(schema="scalellm_dsp_frozen_kv_restore_v1", status="RUNNING", read_only=False,
              bit_sha256=work.BIT_SHA, reference_bit_sha256=work.REFERENCE_BIT_SHA,
              snapshot_file=str(snapshot), snapshot_bytes=work.KV_BYTES,
              snapshot_sha256=work.sha_file(snapshot), layers=[],
              observed_boot_utc=os.environ.get("SCALELLM_BOOT_UTC"),
              history_provenance="5_layers_byteexact;27_layers_format_and_nonzero_only",
              independent_full_model_oracle="NOT_ESTABLISHED")
require = work.require
require(report["snapshot_sha256"] == "fa610d68fab6045573a355313f78808c93b7273dbf1edc2e8f61bc3ea1ad81c8", "Copied frozen KV snapshot identity differs")
parent = work.load(root / "reference/parent_inspection.json")
report["parent_inspection_sha256"] = work.sha_file(root / "reference/parent_inspection.json")
source = work.verify_source(reference)
require(source["main_run_sha256"] == parent["source_main_run_sha256"], "Sealed 128-round run changed")
require(source["source_receipt_sha256"] == parent["source_receipt_sha256"], "Sealed source receipt changed")
report["source_main_run_sha256"] = source["main_run_sha256"]
report["source_receipt_sha256"] = source["source_receipt_sha256"]
identity = work.load(root / "parent_runtime_identity.json")
for relative, expected in identity["candidate_files"].items():
    path = root / relative
    require(path.stat().st_size == expected["bytes"] and work.sha_file(path) == expected["sha256"], "Board-tested runtime changed " + relative)
program = work.load(root / "program/receipt.json")
require(program["status"] == "PASS" and program["bit_sha256"] == work.BIT_SHA, "New SRAM program receipt differs")
api = work.bind_runtime(root)
work.cpu_budget(8)
guard = api["ResourceGuard"](rss_limit=8 << 30, available_floor=2 << 30)
session = None
try:
    with api["WindowsXdmaSession"](timeout_ms=5000, log_path=str(out / "xdma.jsonl")) as session:
        backend = api["FinalBoardBackend"](session, timeout_s=120)
        backend.require_quiescent()
        before = work.csr_snapshot(session, api)
        require(before["STATUS"] == before["ADMISSION_ERROR"] == before["DONE_ERROR"] == 0, "Board is not clean idle")
        report["csr_before_restore"] = before
        readback = hashlib.sha256()
        for layer, data in work.snapshot_layers(snapshot):
            guard()
            backend.require_quiescent()
            address = api["KV_BASE"] + layer * work.LAYER_BYTES
            written = session.h2c_write_local(0, data, address, 1 << 20)
            observed = session.c2h_read_local(0, work.LAYER_BYTES, address, 1 << 20)
            require(written == work.LAYER_BYTES and observed == data, f"Complete L{layer} KV restore/readback differs")
            detail = work.validate_kv_layer(observed)
            if layer in work.LAYERS:
                sealed = source["targets"][work.ATTENTION_IDS[layer]]["kv_before"].read_bytes()
                for slot in range(16):
                    offset = slot * work.SLOT_BYTES
                    require(observed[offset:offset + work.HISTORY_BYTES] == sealed[offset:offset + work.HISTORY_BYTES], f"L{layer} slot{slot} history differs from sealed bytes")
                detail["sealed_history_comparison"] = "16_slots_x_127_positions_BYTEEXACT"
            else:
                detail["sealed_history_comparison"] = "NO_OLD_PER_LAYER_HASH"
            readback.update(observed)
            report["layers"].append(dict(layer=layer, write_bytes=written, read_bytes=len(observed), byte_exact=True, **detail))
            print(json.dumps(dict(layer=layer, status="PASS", bytes=len(observed))), flush=True)
        require(readback.hexdigest() == report["snapshot_sha256"], "Full 256MiB readback digest differs")
        backend.require_quiescent()
        after = work.csr_snapshot(session, api)
        require(after == before, "CSR changed during KV restore without commands")
        report.update(status="PASS_WITH_LIMITS", full_snapshot_readback_sha256=readback.hexdigest(),
                      full_snapshot_byteexact=True, restored_layers=32, csr=after)
except BaseException as error:
    report.update(status="FAIL", error=repr(error))
    raise
finally:
    report["handles_closed"] = bool(session is not None and not session.handles and not session.quarantine)
    report["resources"] = guard.summary()
    work.save_new(out / "inspection.json", report)
print(json.dumps(dict(status=report["status"], restored_layers=report.get("restored_layers"), snapshot_sha256=report["snapshot_sha256"], handles_closed=report["handles_closed"])), flush=True)
