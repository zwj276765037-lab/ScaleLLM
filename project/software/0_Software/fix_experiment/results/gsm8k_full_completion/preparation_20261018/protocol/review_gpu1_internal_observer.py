#!/usr/bin/env python3
"""Bounded CPU-only independent review of GPU1 repair AT003 evidence."""
import datetime
import hashlib
import json
import os
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
ATTEMPT = HERE.parent / "gpu1_repair_20261018/AT003"
MAX64 = 2**64 - 1
CLEAN = [0, MAX64, 0, 0, MAX64]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def validate_observation(row, words, counter, pointers):
    assert row["counter_index"] == counter
    assert row["counter_ptr"] == pointers[counter]
    assert row["small_result_reads_equal"] is True
    assert row["small_result_words"] == row["small_result_repeated_words"] == words
    assert row["mismatch_byte_count"] == words[0]
    assert row["first_mismatch_byte_offset"] == (None if words[1] == MAX64 else words[1])
    assert row["set_bit_byte_count"] == words[2]
    assert row["cleared_bit_byte_count"] == words[3]
    assert row["first_observed_byte"] == (None if words[4] == MAX64 else words[4])


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
    assert set(os.sched_getaffinity(0)) == {8, 9}
    status_bytes = (ATTEMPT / "status.json").read_bytes()
    status = json.loads(status_bytes)
    assert status["execution_state"] == "completed" and status["stage"] == "complete"
    assert "error" not in status and status["context_destroy_return_code"] == 0
    assert len(status["allocation_free_return_codes"]) == 82
    assert status["allocation_free_return_codes"] == [0] * 82
    assert status["lock_released_at"] and status["cleanup_completed_at"]
    assert not Path(f"/proc/{status['pid']}").exists()
    terminal = read(ATTEMPT / "terminal.json")
    assert terminal["execution_state"] == "completed" and terminal["exit_code"] == 0
    assert terminal["stop_reason"] is None and terminal["worker_pid"] == status["pid"]
    library = read(ATTEMPT / "actual_cuda_library.json")
    assert library["worker_pid"] == status["pid"] and library["actual_identity_verified"] is True
    assert library["expected_sha256"] == read(ATTEMPT / "protocol.json")["actual_libcuda_required_sha256"]
    assert len(library["mapped_libraries"]) == 1
    assert library["mapped_libraries"][0]["path"] == library["expected_path"]
    assert library["mapped_libraries"][0]["sha256"] == library["expected_sha256"] == sha(library["expected_path"])
    assert status["cpu_affinity"] == [18, 19]
    assert status["requested_gpu_uuid"] == status["gpu_uuid_actual"] == status["cuda_visible_devices"] == "GPU-d87ce710-76bf-872d-9739-f0d7c9b52533"
    source_review = read(HERE / "gpu1_internal_observer_source_audit_AT001.json")
    for path, expected in source_review["source_sha256"].items():
        assert sha(path) == expected
    assert status["source_sha256"] == sha(ATTEMPT / "source_snapshot.py")
    observer = status["gpu_observer"]
    assert observer["kernel_source_sha256"] == sha(ATTEMPT / "observer.cu")
    assert observer["compiled_cubin_sha256"] == sha(ATTEMPT / "observer.cubin")
    assert observer["compiler_receipt_sha256"] == sha(ATTEMPT / "compile_receipt.json")
    assert observer["counter_size_bytes"] == 40
    pointers = observer["counter_ptrs"]
    assert len(set(pointers)) == 2
    assert abs(pointers[0] - pointers[1]) >= 40
    controls = observer["self_tests"]
    assert len(controls) == 2
    for control, value in zip(controls, [0, 255], strict=True):
        assert control["expected_byte"] == value
        assert control["injected_byte"] == 255 - value
        assert control["injected_byte_offset"] == 12345
        validate_observation(control["clean"], CLEAN, 0, pointers)
        validate_observation(control["injected"], [1, 12345, int(value == 0), int(value == 255), 255 - value], 1, pointers)
        assert control["passed"] is True
    allocations = status["allocations"]
    assert len(allocations) == 80
    chunk = 256 * 2**20
    assert status["allocated_bytes"] == 80 * chunk
    assert observer["actual_allocated_bytes"] == 80 * chunk + 80
    assert len({a["ptr"] for a in allocations}) == 80
    for index, allocation in enumerate(allocations):
        assert allocation["allocation_index"] == index
        assert allocation["size_bytes"] == chunk
        assert allocation["allocation_working_set_offset_bytes"] == index * chunk
    assert [t["test_id"] for t in status["tests"]] == ["device_memset_00", "device_memset_ff"]
    result = []
    artifacts = {}
    previous = {}
    for test, value in zip(status["tests"], [0, 255], strict=True):
        assert test["route"] == "device_memset" and test["pattern"] == f"{value:02x}"
        assert test["repeat_count_per_chunk"] == 2 and test["ended_at"]
        reads = test["reads"]
        assert [(r["allocation_index"], r["repeat"]) for r in reads] == [(i, r) for i in range(80) for r in range(2)]
        bads = []
        template = np.full(chunk, value, dtype=np.uint8)
        expected_sha = hashlib.sha256(template).hexdigest()
        for row in reads:
            index, repeat = row["allocation_index"], row["repeat"]
            assert row["ptr"] == allocations[index]["ptr"] and row["size_bytes"] == chunk
            assert row["exact_cpu_expected"] is (row["changed_bytes"] == 0)
            assert row["gpu_cpu_mismatch_counts_equal"] is True
            if repeat:
                assert row["changed_bytes_from_previous_read"] == 0
            if not row["changed_bytes"]:
                validate_observation(row["gpu_internal_observer"], CLEAN, repeat, pointers)
                continue
            path = ATTEMPT / row["raw_diff_file"]
            assert path.parent == ATTEMPT and path.name.endswith("_diff.npz")
            assert sha(path) == row["raw_diff_sha256"]
            assert row["raw_diff_coordinates_complete"] is True
            with np.load(path, allow_pickle=False) as data:
                assert set(data.files) == {"byte_offsets", "expected", "observed", "xor"}
                coords, expected, observed, xor = [data[k].copy() for k in ("byte_offsets", "expected", "observed", "xor")]
            count = row["changed_bytes"]
            assert all(a.ndim == 1 and len(a) == count for a in (coords, expected, observed, xor))
            assert np.issubdtype(coords.dtype, np.integer) and np.all(np.diff(coords) > 0)
            assert int(coords[0]) >= 0 and int(coords[-1]) < chunk
            assert all(a.dtype == np.uint8 for a in (expected, observed, xor))
            assert np.all(expected == value) and np.all(expected != observed)
            assert np.array_equal(xor, np.bitwise_xor(expected, observed))
            set_count = int(np.count_nonzero(observed & np.bitwise_not(expected)))
            clear_count = int(np.count_nonzero(expected & np.bitwise_not(observed)))
            assert row["set_bit_bytes"] == set_count and row["cleared_bit_bytes"] == clear_count
            words = [count, int(coords[0]), set_count, clear_count, int(observed[0])]
            validate_observation(row["gpu_internal_observer"], words, repeat, pointers)
            hist = {str(int(v)): int(c) for v, c in zip(*np.unique(xor, return_counts=True))}
            assert hist == row["xor_histogram"]
            for name, array in [("byte_offsets", coords), ("expected", expected), ("observed", observed), ("xor", xor)]:
                assert row["first_32_" + name] == array[:32].tolist()
            assert row["last_32_byte_offsets"] == coords[-32:].tolist()
            assert row["expected_sha256"] == expected_sha
            template[coords] = observed
            assert hashlib.sha256(template).hexdigest() == row["observed_sha256"]
            template[coords] = value
            pages, counts = np.unique(coords // 4096, return_counts=True)
            pagepath = ATTEMPT / path.name.replace("_diff.npz", "_pages.npz")
            with np.load(pagepath, allow_pickle=False) as data:
                assert set(data.files) == {"page_offset", "changed_byte_counts"}
                assert np.array_equal(data["page_offset"], pages)
                assert np.array_equal(data["changed_byte_counts"], counts)
            if repeat:
                assert all(np.array_equal(a, b) for a, b in zip(previous[(test["test_id"], index)], (coords, expected, observed, xor), strict=True))
            else:
                previous[(test["test_id"], index)] = (coords, expected, observed, xor)
            artifacts[str(path)] = sha(path)
            artifacts[str(pagepath)] = sha(pagepath)
            bads.append({"allocation_index": index, "repeat": repeat, "count": count, "first_offset": int(coords[0]), "first_observed": int(observed[0]), "set_byte_count": set_count, "clear_byte_count": clear_count, "gpu_words": words, "raw_diff_sha256": sha(path), "xor_histogram": hist})
        assert sum(r["changed_bytes"] for r in reads) == test["changed_bytes"]
        assert len(bads) == test["failing_reads"]
        result.append({"test_id": test["test_id"], "read_count": len(reads), "failing_reads": len(bads), "mismatch_bytes_counted_across_reads": sum(r["changed_bytes"] for r in reads), "failing_blocks": sorted({r["allocation_index"] for r in bads}), "bad_reads_independently_recomputed": bads})
    assert (ATTEMPT / "status.json").read_bytes() == status_bytes
    artifacts[str(ATTEMPT / "status.json")] = hashlib.sha256(status_bytes).hexdigest()
    for name in ("source_snapshot.py", "observer.cu", "observer.cubin", "compile_receipt.json", "protocol.json", "actual_cuda_library.json", "launch.json", "terminal.json"):
        artifacts[str(ATTEMPT / name)] = sha(ATTEMPT / name)
    evidence = {"schema": "scalellm_gpu1_internal_observer_independent_review_v1", "reviewed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "reviewer": "A010 /root/gsm8k_protocol", "CPU_only": True, "cpu_affinity": sorted(os.sched_getaffinity(0)), "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"), "review_source_sha256": sha(__file__), "attempt": str(ATTEMPT), "execution_state": "completed_independently_reviewed", "verdict": "bounded GPU1 raw CUDA byte preservation failed; native device observer corroborates mismatches before full-block readback", "all_four_clean_injection_control_vectors_exact": True, "all_320_two_small_read_vectors_validated": True, "two_counter_buffers_distinct": True, "ten_complete_diff_and_page_files_independently_recomputed": True, "full_observed_block_sha_reconstructed_from_complete_sparse_diffs": True, "cleanup_return_codes_all_zero": True, "worker_pid_absent": True, "started_at": status["started_at"], "ended_at": status["ended_at"], "cleanup_completed_at": status["cleanup_completed_at"], "tests": result, "artifact_sha256": artifacts, "source_review": str(HERE / "gpu1_internal_observer_source_audit_AT001.json"), "limitations": ["Clean full-block readbacks are represented by the runtime report; clean block contents were not retained for independent recomputation.", "Full-data and small-result copies still share the driver/D2H path; this is not an absolute transport-health proof.", "These results constrain explanations confined to full-block D2H corruption; they do not distinguish physical DRAM, memory-controller, address translation or driver/kernel faults.", "No GPU1 repair, model qualification or whole-card hardware diagnosis is established; GPU0 GSM8K qualification remains separate."]}
    output = HERE / "gpu1_internal_observer_review_AT001.json"
    with output.open("x") as stream:
        json.dump(evidence, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"execution_state": evidence["execution_state"], "tests": [{k: t[k] for k in ("test_id", "read_count", "failing_reads", "mismatch_bytes_counted_across_reads", "failing_blocks")} for t in result], "output": str(output)}))


if __name__ == "__main__":
    main()
