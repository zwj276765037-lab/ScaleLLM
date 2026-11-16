"""Board-side inspection and complete fresh-snapshot restoration."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys

from portable_source import BIT_SHA, KV_BYTES, SNAPSHOT_SHA, require, sha_file


def require_launcher():
    require(sys.platform == "win32", "Board operations require Windows XDMA")
    require(os.environ.get("SCALELLM_POWER_OWNER_PID")
            and os.environ.get("SCALELLM_RUN_ID") and os.environ.get("SCALELLM_BOOT_UTC"),
            "Use run_power.ps1 to hold the exclusive board lease and record its owner")


def inspect_or_restore(args, source, work):
    require_launcher()
    from deploy.final.common import read_program_receipt
    programming = read_program_receipt(args.program_receipt, "all-dsp")
    require(sha_file(args.bit_file) == BIT_SHA
            and Path(args.bit_file).stat().st_size == 80159263, "Released bit file differs")
    snapshot = source["snapshot"]
    require(snapshot.stat().st_size == KV_BYTES and sha_file(snapshot) == SNAPSHOT_SHA,
            "Fresh full snapshot differs")
    api = work.bind_runtime(args.runtime_root)
    work.cpu_budget(8)
    guard = api["ResourceGuard"](rss_limit=8 << 30, available_floor=2 << 30)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    restore = args.command == "restore"
    report = {"schema": "scalellm_portable_kv128_inspection_v1", "status": "RUNNING",
              "source_main_run_sha256": source["main_run_sha256"],
              "source_receipt_sha256": source["source_receipt_sha256"],
              "source_capture_schema": source["capture"]["schema"],
              "source_bit_sha256": source["capture"]["run_bitstream_sha256"],
              "bit_sha256": BIT_SHA, "programming_receipt": programming,
              "snapshot_file": str(snapshot), "snapshot_bytes": KV_BYTES,
              "snapshot_sha256": SNAPSHOT_SHA, "read_only": not restore,
              "restored_layers": 0, "layers": [],
              "observed_boot_utc": os.environ["SCALELLM_BOOT_UTC"],
              "run_id": os.environ["SCALELLM_RUN_ID"],
              "lease_owner_pid": int(os.environ["SCALELLM_POWER_OWNER_PID"]),
              "history_provenance": "fresh_128_step_benchmark_and_published_full_snapshot_digest",
              "independent_full_model_oracle": "NOT_ESTABLISHED"}
    session = None
    try:
        with api["WindowsXdmaSession"](timeout_ms=5000, log_path=str(out / "xdma.jsonl")) as session:
            backend = api["FinalBoardBackend"](session, timeout_s=120)
            backend.require_quiescent()
            before = work.csr_snapshot(session, api)
            require(before["STATUS"] == before["ADMISSION_ERROR"] == before["DONE_ERROR"] == 0,
                    "Board must be quiescent and error-free")
            if not restore:
                work.assert_benchmark_csr(before, source)
            report["csr_before"] = before
            digest = hashlib.sha256()
            for layer, reference in work.snapshot_layers(snapshot):
                guard()
                backend.require_quiescent()
                address = api["KV_BASE"] + layer * work.LAYER_BYTES
                if restore:
                    require(session.h2c_write_local(0, reference, address, 1 << 20) == work.LAYER_BYTES,
                            f"Short complete snapshot write at layer {layer}")
                    report["restored_layers"] += 1
                live = session.c2h_read_local(0, work.LAYER_BYTES, address, 1 << 20)
                require(live == reference, f"Fresh snapshot readback differs at layer {layer}")
                detail = work.validate_kv_layer(live)
                digest.update(live)
                report["layers"].append(dict(layer=layer, byte_exact=True, **detail))
            require(digest.hexdigest() == SNAPSHOT_SHA, "Complete 256 MiB readback hash differs")
            backend.require_quiescent()
            require(work.csr_snapshot(session, api) == before, "CSR changed during snapshot access")
            report.update(status="PASS_WITH_LIMITS", csr=before,
                          full_snapshot_readback_sha256=digest.hexdigest(), full_snapshot_byteexact=True)
    except BaseException as error:
        report.update(status="FAIL", error=repr(error))
        raise
    finally:
        report["handles_closed"] = bool(session is not None and not session.handles and not session.quarantine)
        if not report["handles_closed"]:
            report.update(status="FAIL", error=report.get("error", "XDMA handles did not close"))
        report["resources"] = guard.summary()
        work.save_new(out / "inspection.json", report)
    require(report["handles_closed"], "XDMA handles did not close")
    return report
