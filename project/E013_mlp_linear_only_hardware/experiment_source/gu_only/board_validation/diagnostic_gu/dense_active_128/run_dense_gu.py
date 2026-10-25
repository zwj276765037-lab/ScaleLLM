#!/usr/bin/env python3
"""Run the separate dense128 diagnostic through the unchanged GU backend."""
from __future__ import annotations

import argparse
from contextlib import nullcontext
from dataclasses import asdict
import datetime
import importlib
import json
from pathlib import Path
import platform
import sys
import time
import traceback

import numpy as np

from dense import DenseArtifacts as DiagnosticArtifacts, sha as digest, write_json as json_write, decode_output
from verify_dense import verify_bundle

CSRS = (0x000, 0x004, 0x100, 0x104, 0x10C, 0x144, 0x14C, 0x15C, 0x160,
        0x178, 0x260, 0x2A8, 0x2B8, 0x300, 0x304, 0x308, 0x324,
        0x328, 0x32C, 0x330, 0x334, 0x338, 0x33C, 0x340, 0x344,
        0x348, 0x34C, 0x350, 0x354, 0x358, 0x35C, 0x360, 0x364, 0x368, 0x370)


def snapshot(session):
    result = {}
    for csr in CSRS:
        try:
            result[f"0x{csr:03x}"] = session.read32(csr)
        except Exception as error:
            result[f"0x{csr:03x}"] = f"UNAVAILABLE:{type(error).__name__}:{error}"
    return result


def comparison(output, gold):
    actual, expected = decode_output(output), decode_output(gold)
    diff = np.argwhere(actual != expected)
    byte_diff = np.flatnonzero(np.frombuffer(output, np.uint8) != np.frombuffer(gold, np.uint8))
    witnesses = []
    for matrix, row, column in diff[:16]:
        matrix, row, column = int(matrix), int(row), int(column)
        offset = (((column // 16) * 2 + matrix) * 16 * 16 + row * 16 + column % 16) * 3
        witnesses.append({"matrix": "gate" if matrix == 0 else "up", "row": row,
                          "column": column, "byte_offset": offset,
                          "expected_s24": int(expected[matrix, row, column]),
                          "actual_s24": int(actual[matrix, row, column])})
    return {"verdict": "PASS" if not len(diff) else "FAIL", "compared_bytes": len(gold),
            "compared_s24_values": int(expected.size), "mismatched_values": len(diff),
            "mismatched_bytes": len(byte_diff),
            "first_mismatched_byte": int(byte_diff[0]) if len(byte_diff) else None,
            "coordinates": witnesses, "gold_sha256": digest(gold), "output_sha256": digest(output)}


def run(session, bundle, result_dir, *, cohorts=1, epoch=1, command_base=1,
        request_id=1, timeout_s=10.0, chunk_bytes=1 << 20, hardware_root=None):
    """Execute using an already-entered session; leave all failure state owned.

    A single-cohort success is ACKed and leaves the layer lease intentionally
    unreleased. Two cohorts are ACKed independently, then release the lease.
    The caller owns transport opening, closing and board exclusivity/preflight.
    """
    if cohorts not in (1, 2) or not 0 < epoch <= 0xFFFFFFFF or not 0 <= command_base <= 0xFFFFFFFE:
        raise ValueError("invalid diagnostic cohorts/epoch/command base")
    result_dir = Path(result_dir).resolve()
    result_dir.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    receipt = {"execution_state": "running", "verdict": "INCOMPLETE", "stage": "offline_input_verification",
               "scope": "GU dense128 periodic diagnostic; no real-model or worst-case switching claim",
               "bundle": str(Path(bundle).resolve()), "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "cohorts_requested": cohorts, "epoch": epoch, "command_base": command_base,
               "request_id": request_id, "timeout_s": timeout_s, "chunk_bytes": chunk_bytes,
               "python": sys.version, "platform": platform.platform(), "cohorts": [],
               "transport_class": f"{type(session).__module__}.{type(session).__name__}"}
    json_write(result_dir / "receipt.json", receipt)
    backend = None
    try:
        verified = verify_bundle(bundle)
        json_write(result_dir / "input_verification.json", verified)
        artifacts = DiagnosticArtifacts(bundle)
        (result_dir / "input_manifest.json").write_bytes((Path(bundle) / "manifest.json").read_bytes())
        payload = artifacts.records["input_rec576"].read_verified()
        gold = artifacts.records["gold_gu_s24"].read_verified()
        if hardware_root is None:
            hardware_root = next(parent / "project/hardware" for parent in Path(__file__).resolve().parents
                                 if (parent / "project/hardware/host").is_dir())
        hardware_root = Path(hardware_root).resolve()
        sys.path.insert(0, str(hardware_root))
        from host.scalellm_mlp_gu_only_backend import GuOnlyXdmaBackend
        from host.scalellm_mlp_gu_only_runtime import GuDescriptor
        code_files = [Path(__file__), Path(__file__).with_name("dense.py"), Path(__file__).with_name("verify_dense.py"),
                      hardware_root / "host/scalellm_mlp_gu_only_backend.py",
                      hardware_root / "host/scalellm_mlp_gu_only_runtime.py",
                      hardware_root / "host/scalellm_mlp_linear.py",
                      hardware_root / "source/mlp_linear/abi_gu_only.json"]
        receipt["code_identity"] = [{"path": str(path), "sha256": digest(path.read_bytes())} for path in code_files]
        receipt["stage"] = "stage_gu_layer"
        json_write(result_dir / "csr_before.json", snapshot(session))
        json_write(result_dir / "receipt.json", receipt)
        backend = GuOnlyXdmaBackend(session, artifacts, timeout_s=timeout_s, chunk_bytes=chunk_bytes)
        metadata_generation = backend.stage_gu_layer(0, epoch)
        receipt["metadata_generation"] = metadata_generation
        json_write(result_dir / "csr_after_stage.json", snapshot(session))
        for cohort in range(cohorts):
            command = command_base + cohort
            descriptor = GuDescriptor(command, request_id, cohort, 0, cohort * 3, 1, metadata_generation, epoch)
            prefix = f"cohort{cohort}"
            descriptor_info = {"fields": asdict(descriptor), "words_u32": list(descriptor.words()),
                               "packed_hex": descriptor.pack().hex()}
            json_write(result_dir / f"{prefix}_descriptor.json", descriptor_info)
            receipt["stage"] = f"{prefix}_run_gu"
            json_write(result_dir / "receipt.json", receipt)
            command_started = time.monotonic()
            completed = backend.run_gu(descriptor, payload)
            # Persist the owned complete output and DONE before any ACK.
            output = bytes(completed.payload)
            (result_dir / f"{prefix}_output.bin").write_bytes(output)
            done = snapshot(session)
            json_write(result_dir / f"{prefix}_done_before_ack.json", done)
            check = comparison(output, gold)
            check["descriptor"] = descriptor_info
            check["gu_seconds_including_io"] = time.monotonic() - command_started
            check["acked"] = False
            json_write(result_dir / f"{prefix}_comparison.json", check)
            receipt["cohorts"].append(check)
            receipt["stage"] = f"{prefix}_output_compared"
            json_write(result_dir / "receipt.json", receipt)
            if check["verdict"] != "PASS":
                raise AssertionError(f"GU numerical mismatch: {check['coordinates'][0]}")
            backend.ack_gu(command)
            check["acked"] = True
            json_write(result_dir / f"{prefix}_comparison.json", check)
            json_write(result_dir / f"{prefix}_csr_after_ack.json", snapshot(session))
            json_write(result_dir / "receipt.json", receipt)
        if cohorts == 2:
            backend.release_gu_layer(0, epoch)
        receipt.update(execution_state="completed", verdict="PASS", stage="completed",
                       layer_released=cohorts == 2, retained_layer_lease=backend.lease,
                       gold_statistics=verified["output_statistics"])
        print(f"GU_DIAGNOSTIC_PASS cohorts={cohorts} compared_bytes={cohorts * 1376256}")
        return receipt
    except BaseException as error:
        receipt.update(execution_state="failed", verdict="FAIL", error=f"{type(error).__name__}: {error}",
                       traceback=traceback.format_exc())
        if backend is not None:
            receipt.update(backend_diagnostics=backend.diagnostics, retained_layer_lease=backend.lease,
                           retained_pending=asdict(backend.pending) if backend.pending is not None else None,
                           backend_poisoned=backend.poisoned)
            json_write(result_dir / "csr_failure.json", snapshot(session))
        print(f"GU_DIAGNOSTIC_FAIL stage={receipt['stage']} error={receipt['error']}", file=sys.stderr)
        raise
    finally:
        receipt["ended_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        receipt["elapsed_seconds"] = time.monotonic() - started
        json_write(result_dir / "receipt.json", receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--session-factory", default="scalellm_windows_xdma:create_session")
    parser.add_argument("--cohorts", type=int, choices=(1, 2), default=2)
    parser.add_argument("--epoch", type=int, default=1)
    parser.add_argument("--command-base", type=int, default=1)
    parser.add_argument("--request-id", type=int, default=1)
    parser.add_argument("--timeout-s", type=float, default=10.0)
    parser.add_argument("--chunk-bytes", type=int, default=1 << 20)
    parser.add_argument("--hardware-root")
    args = parser.parse_args()
    module, function = args.session_factory.rsplit(":", 1)
    factory = getattr(importlib.import_module(module), function)
    session = factory()
    manager = session if hasattr(session, "__enter__") else nullcontext(session)
    with manager as opened:
        run(opened, args.bundle, args.result, cohorts=args.cohorts, epoch=args.epoch,
            command_base=args.command_base, request_id=args.request_id,
            timeout_s=args.timeout_s, chunk_bytes=args.chunk_bytes, hardware_root=args.hardware_root)


if __name__ == "__main__":
    main()
