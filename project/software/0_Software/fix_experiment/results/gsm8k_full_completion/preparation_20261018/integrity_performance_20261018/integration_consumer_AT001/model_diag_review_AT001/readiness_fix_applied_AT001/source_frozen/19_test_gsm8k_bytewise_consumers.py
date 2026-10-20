"""Rehashed synthetic bytewise acceptance faults; no GPU/model execution."""
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

from gsm8k_protocol import (INTEGRITY_CONTRACT_ID, INTEGRITY_IMPLEMENTATION_ID,
    atomic_json, canonical_hash, integrity_implementation_id, sha256_file,
    validate_integrity_evidence)
from test_gsm8k_integrity_contract import attach_integrity, save_integrity, GPU0


MODE = INTEGRITY_IMPLEMENTATION_ID


def attach_bytewise(folder, manifest, data, *, tied=False, source_path=None):
    """Add explicitly synthetic method/capture/byte evidence to a CPU fixture."""
    manifest["identity"]["integrity_implementation_id"] = MODE
    data["identity"]["integrity_implementation_id"] = MODE
    code = source_path or folder / "gsm8k_integrity_bytewise.py"
    code.write_text("explicit synthetic CPU fixture source")
    manifest["identity"]["code_sha256"][str(code)] = sha256_file(code)
    data["runtime_comparison_implementation"] = {
        "method_id": MODE, "candidate_source_sha256": sha256_file(code),
        "legacy_source_sha256": data["source_sha256"],
        "loading_sha_policy": "unchanged_legacy_direct_sha_and_native_QDQ_reconstruction",
        "native_cache_policy": "unchanged_native_cache_call_parity_v2",
        "unsupported_tensor_policy": "fail_closed_noncontiguous_non_strided_quantized_conjugate_negative_or_non_CPU_CUDA"}
    sizes = {"torch.bfloat16": 2}
    baseline = data["baseline_manifest"]
    counts = {name: math.prod(desc["shape"]) * sizes[desc["dtype"]] for name, desc in baseline.items()}
    logical = sum(counts.values())
    storage = {}
    for index, (name, desc) in enumerate(sorted(baseline.items())):
        shape = desc["shape"]
        stride, product = [], 1
        for dimension in reversed(shape):
            stride.insert(0, product)
            product *= max(dimension, 1)
        pointer = 4096 + (0 if tied else index) * 1024 if counts[name] else 0
        storage[name] = {"object_id": 100 + (0 if tied else index), "data_ptr": pointer,
            "storage_base_ptr": pointer, "storage_offset": 0, "stride": stride,
            "device": "cuda:0", "shape": shape, "dtype": desc["dtype"]}
    unique = sum({(row["device"], row["data_ptr"], counts[name]): counts[name] for name, row in storage.items()}.values())
    data["runtime_storage_manifest"] = storage
    data["immutable_runtime_baseline"] = {"method_id": MODE, "byte_order": sys.byteorder,
        "chunk_bytes": 4, "logical_baseline_bytes": logical, "unique_immutable_baseline_bytes": unique,
        "staging_buffer_bytes": 4, "staging_buffer_pinned": True, "gpu_weight_replica_bytes": 0,
        "capture_sha_source": "actual_saved_immutable_chunk_bytes_in_logical_order",
        "per_tensor": {name: {"bytes": counts[name], "sha256": desc["sha256"],
            "sha_matches_verified_baseline": True} for name, desc in baseline.items()}}
    reserve = 80 * 2**30
    data["immutable_capture_resource_guard"] = {
        "schema": "scalellm_immutable_capture_memory_guard_v1", "measurement_source": "proc_meminfo_MemAvailable",
        "mem_available_before_capture_bytes": reserve + unique + 4 + 1024,
        "logical_static_bytes": logical, "unique_immutable_baseline_bytes": unique,
        "staging_buffer_bytes": 4, "projected_available_after_capture_bytes": reserve + 1024,
        "minimum_host_reserve_bytes": reserve, "passed": True, "checked_epoch_seconds": 1000.0}
    data["baseline_root_sha256"] = canonical_hash(baseline)
    for phase in data["phase_checks"]:
        label = phase["label"]
        if label in {"cpu_loaded", "gpu_loaded"}:
            root = canonical_hash(data["checkpoint_manifest"])
        elif label == "qdq_rebuild":
            root = canonical_hash({name: baseline[name] for name in data["coverage"]["qdq_expected_names"]})
        else:
            root = data["baseline_root_sha256"]
            phase["content_comparison"] = {"method_id": MODE, "direct_sha256_this_phase": False,
                "hash_derivation": "verified_immutable_baseline_sha_reused_only_after_full_exact_bytewise_inventory_and_storage_match",
                "inventory_exact": True, "full_coverage_exact": True, "expected_bytes": logical,
                "compared_bytes": logical, "equal_bytes": logical,
                "memcmp_byte_count_semantics": "submitted_chunk_lengths; equal chunks cover every byte; mismatch may short_circuit",
                "missing_names": [], "unexpected_names": [], "derived_root_sha256": root,
                "per_tensor": {name: {"expected_bytes": count, "compared_bytes": count, "equal_bytes": count,
                    "all_chunks_equal": True, "complete": True, "exact": True} for name, count in counts.items()}}
        phase["observed_root_sha256"] = root
        if "trusted_root_sha256" in phase:
            phase["trusted_root_sha256"] = root
    return data


class BytewiseAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bytewise_consumer_CPU_fixture_")
        self.folder = Path(self.temp.name)
        self.codes = {}
        for name in ("gsm8k_weight_integrity.py", "run_eval_worker.py", "run_gsm8k_worker.py", "gsm8k_protocol.py"):
            path = self.folder / name
            path.write_text("explicit synthetic CPU source " + name)
            self.codes[str(path)] = sha256_file(path)
        self.manifest = {"state": "complete", "identity": {"plan_sha256": "p" * 64,
            "stage": "smoke", "case": "bf16", "model_fingerprint_sha256": "f" * 64,
            "integrity_contract_id": INTEGRITY_CONTRACT_ID, "code_sha256": self.codes},
            "environment": {"device": "cuda:0", "gpu_uuid": GPU0, "CUDA_VISIBLE_DEVICES": GPU0}}
        self.summary, self.ids = {}, ["train:0000", "train:0001"]
        self.data = attach_integrity(self.folder, self.manifest, self.summary, self.ids)
        self.legacy_manifest, self.legacy_data = deepcopy(self.manifest), deepcopy(self.data)
        attach_bytewise(self.folder, self.manifest, self.data)
        self.save()

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        save_integrity(self.folder, self.manifest, self.summary, self.data)

    def validate(self, mode=MODE):
        return validate_integrity_evidence(self.folder, self.manifest, INTEGRITY_CONTRACT_ID,
            sample_ids=self.ids, expected_gpu=GPU0, summary=self.summary, expected_implementation=mode)

    def reject_mutations(self, mutations):
        original_data, original_manifest = deepcopy(self.data), deepcopy(self.manifest)
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                self.data, self.manifest = deepcopy(original_data), deepcopy(original_manifest)
                mutate(self.data, self.manifest)
                self.save()
                with self.assertRaises(ValueError):
                    self.validate()
        self.data, self.manifest = original_data, original_manifest

    def test_complete_bytewise_evidence_passes(self):
        self.assertEqual(self.validate(), self.manifest["integrity"])

    def test_qdq_cache_full_coverage_passes(self):
        self.manifest["identity"]["case"] = "reference_qdq"
        self.data = attach_integrity(self.folder, self.manifest, self.summary, self.ids, qdq=True)
        attach_bytewise(self.folder, self.manifest, self.data)
        self.save()
        self.validate()

    def test_alias_and_zero_length_positive_cases(self):
        attach_bytewise(self.folder, self.manifest, self.data, tied=True)
        self.save()
        self.validate()
        self.assertEqual(self.data["immutable_runtime_baseline"]["unique_immutable_baseline_bytes"], 8)
        for inventory in (self.data["checkpoint_manifest"], self.data["baseline_manifest"]):
            for desc in inventory.values():
                desc["shape"] = [0]
        attach_bytewise(self.folder, self.manifest, self.data)
        self.save()
        self.validate()

    def test_legacy_remains_valid_but_cannot_supply_fast_evidence(self):
        with self.assertRaisesRegex(ValueError, "implementation"):
            self.validate(None)
        self.manifest, self.data = self.legacy_manifest, self.legacy_data
        self.save()
        self.validate(None)
        with self.assertRaisesRegex(ValueError, "implementation"):
            self.validate()

    def test_fast_metadata_cannot_hide_under_legacy_identity(self):
        self.manifest["identity"].pop("integrity_implementation_id")
        self.data["identity"].pop("integrity_implementation_id")
        self.save()
        with self.assertRaisesRegex(ValueError, "mixed"):
            self.validate(None)

    def test_missing_null_wrong_and_inconsistent_modes_fail(self):
        self.reject_mutations({
            "missing_identity": lambda d,m: m["identity"].pop("integrity_implementation_id"),
            "null_identity": lambda d,m: m["identity"].update(integrity_implementation_id=None),
            "unknown_identity": lambda d,m: m["identity"].update(integrity_implementation_id="other"),
            "missing_data_identity": lambda d,m: d["identity"].pop("integrity_implementation_id"),
            "wrong_data_identity": lambda d,m: d["identity"].update(integrity_implementation_id="other"),
            "top_mode_only": lambda d,m: (d.pop("immutable_runtime_baseline"),d.pop("runtime_comparison_implementation")),
            "conflicting_manifest_top_mode": lambda d,m: m.update(integrity_implementation_id="other"),
        })

    def test_double_source_and_policies_are_bound(self):
        self.reject_mutations({
            "missing_candidate_source": lambda d,m: m["identity"]["code_sha256"].pop(str(self.folder/"gsm8k_integrity_bytewise.py")),
            "wrong_candidate_sha": lambda d,m: d["runtime_comparison_implementation"].update(candidate_source_sha256="b"*64),
            "wrong_legacy_sha": lambda d,m: d["runtime_comparison_implementation"].update(legacy_source_sha256="b"*64),
            "wrong_mode": lambda d,m: d["runtime_comparison_implementation"].update(method_id="other"),
            "wrong_loading_policy": lambda d,m: d["runtime_comparison_implementation"].update(loading_sha_policy="skip"),
            "wrong_v2_policy": lambda d,m: d["runtime_comparison_implementation"].update(native_cache_policy="skip"),
            "wrong_layout_policy": lambda d,m: d["runtime_comparison_implementation"].update(unsupported_tensor_policy="skip"),
        })

    def test_capture_required_fields_cannot_be_omitted(self):
        for key in list(self.data["immutable_runtime_baseline"]):
            self.reject_mutations({key: lambda d,m,k=key: d["immutable_runtime_baseline"].pop(k)})

    def test_capture_sha_bytes_names_pinning_alias_resources_fail(self):
        self.reject_mutations({
            "capture_sha": lambda d,m: d["immutable_runtime_baseline"]["per_tensor"]["linear.weight"].update(sha256="b"*64),
            "capture_bytes": lambda d,m: d["immutable_runtime_baseline"]["per_tensor"]["linear.weight"].update(bytes=7),
            "capture_names": lambda d,m: d["immutable_runtime_baseline"]["per_tensor"].pop("linear.weight"),
            "capture_unverified": lambda d,m: d["immutable_runtime_baseline"]["per_tensor"]["linear.weight"].update(sha_matches_verified_baseline=False),
            "pin_false": lambda d,m: d["immutable_runtime_baseline"].update(staging_buffer_pinned=False),
            "bad_byte_order": lambda d,m: d["immutable_runtime_baseline"].update(byte_order="other"),
            "bad_logical_bytes": lambda d,m: d["immutable_runtime_baseline"].update(logical_baseline_bytes=8),
            "bad_alias_bytes": lambda d,m: d["immutable_runtime_baseline"].update(unique_immutable_baseline_bytes=8),
            "bad_staging_bytes": lambda d,m: d["immutable_runtime_baseline"].update(staging_buffer_bytes=8),
            "replica": lambda d,m: d["immutable_runtime_baseline"].update(gpu_weight_replica_bytes=8),
            "bool_count": lambda d,m: d["immutable_runtime_baseline"].update(gpu_weight_replica_bytes=False),
            "zero_chunk": lambda d,m: d["immutable_runtime_baseline"].update(chunk_bytes=0),
        })

    def test_storage_identity_and_alias_accounting_are_required(self):
        self.reject_mutations({
            "missing_storage": lambda d,m: d.pop("runtime_storage_manifest"),
            "missing_name": lambda d,m: d["runtime_storage_manifest"].pop("linear.weight"),
            "wrong_device": lambda d,m: d["runtime_storage_manifest"]["linear.weight"].update(device="cuda:1"),
            "wrong_offset": lambda d,m: d["runtime_storage_manifest"]["linear.weight"].update(storage_offset=1),
            "bad_stride": lambda d,m: d["runtime_storage_manifest"]["linear.weight"].update(stride=[1,2]),
            "bad_pointer": lambda d,m: d["runtime_storage_manifest"]["linear.weight"].update(data_ptr=0),
            "bool_object": lambda d,m: d["runtime_storage_manifest"]["linear.weight"].update(object_id=True),
            "forged_alias": lambda d,m: d["runtime_storage_manifest"]["rotary.inv_freq"].update(object_id=100),
        })

    def test_capture_resource_guard_is_arithmetic_and_fail_closed(self):
        self.reject_mutations({
            "missing_guard": lambda d,m: d.pop("immutable_capture_resource_guard"),
            "failed_guard": lambda d,m: d["immutable_capture_resource_guard"].update(passed=False),
            "wrong_projection": lambda d,m: d["immutable_capture_resource_guard"].update(projected_available_after_capture_bytes=80*2**30),
            "lower_reserve": lambda d,m: d["immutable_capture_resource_guard"].update(minimum_host_reserve_bytes=79*2**30),
            "wrong_unique": lambda d,m: d["immutable_capture_resource_guard"].update(unique_immutable_baseline_bytes=8),
            "wrong_staging": lambda d,m: d["immutable_capture_resource_guard"].update(staging_buffer_bytes=8),
            "wrong_source": lambda d,m: d["immutable_capture_resource_guard"].update(measurement_source="guess"),
            "wrong_timestamp": lambda d,m: d["immutable_capture_resource_guard"].update(checked_epoch_seconds=-1),
        })

    def test_each_runtime_phase_requires_explicit_method_and_counts(self):
        for index, phase in enumerate(self.data["phase_checks"]):
            if "content_comparison" in phase:
                self.reject_mutations({phase["label"]: lambda d,m,i=index: d["phase_checks"][i].pop("content_comparison")})
        for key in list(self.data["phase_checks"][-1]["content_comparison"]):
            self.reject_mutations({key: lambda d,m,k=key: d["phase_checks"][-1]["content_comparison"].pop(k)})

    def test_derived_phase_and_byte_totals_cannot_be_forged(self):
        def change(**values):
            return lambda d,m: d["phase_checks"][-1]["content_comparison"].update(values)
        self.reject_mutations({
            "fresh_sha_claim": change(direct_sha256_this_phase=True),
            "wrong_method": change(method_id="other"),
            "wrong_derivation": change(hash_derivation="assumed"),
            "wrong_root": change(derived_root_sha256="b"*64),
            "partial_expected": change(expected_bytes=8),
            "partial_compared": change(compared_bytes=8),
            "partial_equal": change(equal_bytes=8),
            "false_inventory": change(inventory_exact=False),
            "false_coverage": change(full_coverage_exact=False),
            "hidden_missing": change(missing_names=["linear.weight"]),
            "extra_name": lambda d,m: d["phase_checks"][-1]["content_comparison"]["per_tensor"].update(extra={}),
            "missing_name": lambda d,m: d["phase_checks"][-1]["content_comparison"]["per_tensor"].pop("linear.weight"),
        })

    def test_per_tensor_counts_and_exactness_cannot_be_hidden_by_totals(self):
        for field, value in {"expected_bytes": 7, "compared_bytes": 7, "equal_bytes": 7,
                             "all_chunks_equal": False, "complete": False, "exact": False}.items():
            self.reject_mutations({field: lambda d,m,k=field,v=value: d["phase_checks"][-1]["content_comparison"]["per_tensor"]["linear.weight"].update({k:v})})

    def test_loading_phases_remain_direct_sha(self):
        for index in range(3):
            self.reject_mutations({str(index): lambda d,m,i=index: d["phase_checks"][i].update(content_comparison={})})


class ModePropagationTests(unittest.TestCase):
    def test_only_absence_is_legacy_and_fast_requires_semantic_contract(self):
        self.assertIsNone(integrity_implementation_id({"protocol": {}}))
        self.assertEqual(integrity_implementation_id({"protocol": {
            "integrity_contract_id": INTEGRITY_CONTRACT_ID, "integrity_implementation_id": MODE}}), MODE)
        for value in (None, "other", False, {}, []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                integrity_implementation_id({"protocol": {"integrity_contract_id": INTEGRITY_CONTRACT_ID,
                                                           "integrity_implementation_id": value}})
        with self.assertRaises(ValueError):
            integrity_implementation_id({"protocol": {"integrity_implementation_id": MODE}})

    def test_completed_attempt_cannot_downgrade_frozen_mode(self):
        import run_gsm8k_matrix as matrix
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            atomic_json(root/"frozen_contract.json", {"integrity_contract_id": INTEGRITY_CONTRACT_ID,
                "integrity_implementation_id": MODE})
            atomic_json(root/"manifest.json", {"identity": {"integrity_contract_id": INTEGRITY_CONTRACT_ID}})
            with self.assertRaisesRegex(ValueError, "implementation"):
                matrix.validate_completed_attempt(root, root, "smoke", {"case":"bf16"})

    def test_summary_rejects_mode_before_any_formal_rescore(self):
        import summarize_gsm8k as summary
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            atomic_json(folder/"manifest.json", {"identity": {"integrity_contract_id": INTEGRITY_CONTRACT_ID}})
            plan = {"protocol": {"integrity_contract_id": INTEGRITY_CONTRACT_ID, "integrity_implementation_id": MODE}}
            contract = {"integrity_contract_id": INTEGRITY_CONTRACT_ID, "integrity_implementation_id": MODE}
            with self.assertRaisesRegex(ValueError, "implementation"):
                summary.validate_group(folder,"synthetic","bf16",plan,"p",[],{}, {},contract,None)

    def test_fast_matrix_reuse_and_native_repeatability_positive(self):
        import run_gsm8k_matrix as matrix
        from test_gsm8k_matrix import MatrixSafetyTest
        MatrixSafetyTest.setUpClass()
        fixture = MatrixSafetyTest(methodName="runTest")
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        fixture.plan["protocol"].update(integrity_contract_id=INTEGRITY_CONTRACT_ID,
            integrity_implementation_id=MODE, verification_contract_id=matrix.NATIVE_VERIFICATION)
        atomic_json(fixture.plan_path, fixture.plan)
        fixture.contract.update(integrity_contract_id=INTEGRITY_CONTRACT_ID,
            integrity_implementation_id=MODE, verification_contract_id=matrix.NATIVE_VERIFICATION,
            plan_sha256=sha256_file(fixture.plan_path),
            protocol_sha256=canonical_hash(fixture.plan["protocol"]))
        # One explicitly synthetic implementation source is shared by both fixtures.
        source = fixture.directory / "gsm8k_integrity_bytewise.py"
        source.write_text("explicit synthetic CPU fixture source")
        fixture.sources[str(source)] = sha256_file(source)
        folders = [fixture.complete_attempt(stage) for stage in ("smoke", "pilot")]
        for folder in folders:
            fixture.convert_to_v2(folder)
            manifest, summary, data = fixture.enable_integrity(folder)
            attach_bytewise(folder, manifest, data, source_path=source)
            save_integrity(folder, manifest, summary, data)
            fixture.reidentify(folder, lambda identity: identity.update(integrity_implementation_id=MODE))
            manifest = json.loads((folder/"manifest.json").read_text())
            summary = json.loads((folder/"summary.json").read_text())
            save_integrity(folder, manifest, summary, data)
        for stage, folder in zip(("smoke", "pilot"), folders):
            matrix.validate_completed_attempt(fixture.root, folder, stage, fixture.group)
        repeat = matrix.paired_verification(*folders, expected_implementation=MODE)
        self.assertIs(repeat["passed"], True)
        self.assertEqual(repeat["integrity_implementation_id"], MODE)
        self.assertEqual(repeat["verification_contract_id"], matrix.NATIVE_VERIFICATION)
        gate = matrix.pilot_gate(fixture.root, [fixture.group], fixture.plan)
        self.assertEqual(gate["groups"][0]["repeatability"]["integrity_implementation_id"], MODE)
        with self.assertRaisesRegex(ValueError, "implementation"):
            matrix.paired_verification(*folders)

    def test_fast_formal_summary_positive_and_mode_bound(self):
        from test_summarize_gsm8k import IndependentTests
        fixture_test = IndependentTests(methodName="runTest")
        fixture_test.setUp()
        self.addCleanup(fixture_test.tearDown)
        fixture = fixture_test.fixture
        fixture.plan["protocol"]["integrity_implementation_id"] = MODE
        data = fixture_test.enable_integrity()
        fixture.contract["integrity_implementation_id"] = MODE
        attach_bytewise(fixture.attempt, fixture.manifest, data)
        fixture.identity_hash = canonical_hash(fixture.identity)
        fixture.manifest["identity_sha256"] = fixture.identity_hash
        for row in fixture.rows + fixture.scores:
            row["identity_sha256"] = fixture.identity_hash
        fixture.save()
        save_integrity(fixture.attempt, fixture.manifest, fixture.worker_summary, data)
        result, rescored, source = fixture.validate()
        self.assertEqual(result["n_completed"], 1319)
        self.assertEqual(len(rescored), 1319)
        self.assertEqual(source["integrity_implementation_id"], MODE)
        self.assertEqual(source["integrity"], fixture.manifest["integrity"])
        fixture.contract.pop("integrity_implementation_id")
        with self.assertRaisesRegex(ValueError, "implementation"):
            fixture.validate()


if __name__ == "__main__":
    unittest.main(verbosity=2)
