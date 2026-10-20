"""Temporary CPU fixtures for static-integrity acceptance, never experiment runs."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from gsm8k_protocol import (INTEGRITY_CONTRACT_ID, atomic_json, canonical_hash,
                            sha256_file, validate_integrity_evidence)


GPU0 = "GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6"
GPU1 = "GPU-d87ce710-76bf-872d-9739-f0d7c9b52533"


def attach_integrity(folder, manifest, summary, sample_ids, *, qdq=False):
    """Attach explicitly synthetic complete integrity proof to a CPU fixture."""
    def desc(role, digest="1" * 64):
        return {"sha256": digest, "shape": [2, 2], "dtype": "torch.bfloat16", "role": role}
    checkpoint = {"linear.weight": desc("parameter"), "rotary.inv_freq": desc("derived_static_buffer")}
    baseline = deepcopy(checkpoint)
    qdq_names = []
    cache = "external_cache:scalepath4_method_inference._H_CACHE:fixture"
    if qdq:
        baseline["linear.weight"] = desc("qdq_buffer", "2" * 64)
        baseline[cache] = desc("external_cache", "3" * 64)
        qdq_names = ["linear.weight", cache]
    croot, root = canonical_hash(checkpoint), canonical_hash(baseline)
    phases = []
    def phase(label, inventory, trusted=False):
        r = canonical_hash(inventory)
        row = {"label": label, "complete": True, "exact": True,
               "checked_names": sorted(inventory), "observed_root_sha256": r}
        if trusted:
            row["trusted_root_sha256"] = r
        phases.append(row)
    phase("cpu_loaded", checkpoint, True)
    phase("gpu_loaded", checkpoint, True)
    phase("qdq_rebuild", {k: baseline[k] for k in qdq_names}, True)
    phase("setup_complete", baseline)
    if manifest["identity"]["stage"] in {"smoke", "pilot"}:
        phase("verification_before", baseline)
        phase("verification_after", baseline)
    for sid in sample_ids:
        phase(f"sample:{sid}:before", baseline)
        phase(f"sample:{sid}:after", baseline)
    phase("stage_complete", baseline)
    data = {"schema": "scalellm_gsm8k_weight_integrity_v1", "state": "complete", "qualified": True,
        "contract_id": INTEGRITY_CONTRACT_ID,
        "identity": {k: manifest["identity"][k] for k in ("plan_sha256", "stage", "case", "model_fingerprint_sha256")},
        "coverage": {"checkpoint_names": sorted(checkpoint), "checkpoint_tensor_names": ["linear.weight"],
            "cpu_checked_names": sorted(checkpoint), "gpu_checked_names": sorted(checkpoint),
            "effective_static_names": sorted(baseline), "qdq_expected_names": qdq_names,
            "qdq_rebuilt_names": qdq_names, "external_cache_names": [cache] if qdq else []},
        "checkpoint_key_map": {"linear.weight": "linear.weight", "rotary.inv_freq": None},
        "checkpoint_manifest": checkpoint, "baseline_manifest": baseline,
        "baseline_root_sha256": root, "phase_checks": phases, "qdq_reconstruction": [],
        "source_sha256": next(v for k,v in manifest["identity"]["code_sha256"].items() if Path(k).name == "gsm8k_weight_integrity.py")}
    if qdq:
        manifest["identity"]["method"] = {"live_qdq_projection_names": ["linear"], "module_count": 1}
        data["qdq_reconstruction"] = [{"module": "linear", "source_key": "linear.weight", "source_shape": [2,2],
            "device": "cuda:0", "class": "ScalePathIAHScaleCodeLinear", "fullshape": True,
            "tensors": {"linear.weight": baseline["linear.weight"]}}]
    data["identity"]["gpu_uuid"] = manifest["environment"]["gpu_uuid"]
    save_integrity(folder, manifest, summary, data)
    return data


def save_integrity(folder, manifest, summary, data):
    checks = folder / "integrity_checks.jsonl"
    checks.write_text("".join(json.dumps(p) + "\n" for p in data["phase_checks"]))
    data["checks_jsonl_sha256"] = sha256_file(checks)
    atomic_json(folder / "integrity.json", data)
    ref = {"path": "integrity.json", "sha256": sha256_file(folder / "integrity.json"),
           "contract_id": INTEGRITY_CONTRACT_ID, "qualified": True,
           "baseline_root_sha256": data["baseline_root_sha256"]}
    manifest["integrity"] = deepcopy(ref)
    manifest.setdefault("artifacts", {})["integrity.json"] = ref["sha256"]
    summary["integrity"] = deepcopy(ref)
    atomic_json(folder / "manifest.json", manifest)
    atomic_json(folder / "summary.json", summary)


class IntegrityContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gsm8k_integrity_cpu_fixture_")
        self.folder = Path(self.temp.name)
        codes = {str(self.folder / name): "a" * 64 for name in (
            "gsm8k_weight_integrity.py", "run_eval_worker.py", "run_gsm8k_worker.py", "gsm8k_protocol.py")}
        self.manifest = {"state": "complete", "identity": {"plan_sha256": "p" * 64, "stage": "smoke",
            "case": "bf16", "model_fingerprint_sha256": "f" * 64, "integrity_contract_id": INTEGRITY_CONTRACT_ID,
            "code_sha256": codes}, "environment": {"gpu_uuid": GPU0, "CUDA_VISIBLE_DEVICES": GPU0, "device": "cuda:0"}}
        self.summary = {}
        self.ids = ["train:0000", "train:0001"]
        self.data = attach_integrity(self.folder, self.manifest, self.summary, self.ids)

    def tearDown(self):
        self.temp.cleanup()

    def validate(self):
        return validate_integrity_evidence(self.folder, self.manifest, INTEGRITY_CONTRACT_ID,
            sample_ids=self.ids, expected_gpu=GPU0, summary=self.summary)

    def test_complete_cpu_copy_static_and_call_evidence_passes(self):
        self.assertEqual(self.validate(), self.manifest["integrity"])

    def test_qdq_and_nonpersistent_hadamard_coverage_passes(self):
        self.manifest["identity"]["case"] = "reference_qdq"
        self.data = attach_integrity(self.folder, self.manifest, self.summary, self.ids, qdq=True)
        self.validate()

    def test_missing_qdq_reconstruction_or_cache_cannot_pass_after_rehash(self):
        self.manifest["identity"]["case"] = "reference_qdq"
        original = attach_integrity(self.folder, self.manifest, self.summary, self.ids, qdq=True)
        for change in [lambda d: d["qdq_reconstruction"].clear(),
                       lambda d: d["qdq_reconstruction"][0].update(fullshape=False),
                       lambda d: d["coverage"]["external_cache_names"].clear()]:
            value = deepcopy(original)
            change(value)
            save_integrity(self.folder, self.manifest, self.summary, value)
            with self.assertRaises(ValueError):
                self.validate()

    def test_content_tampering_without_rehash_fails(self):
        (self.folder / "integrity.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "hash"):
            self.validate()

    def test_rehashed_incomplete_or_wrong_evidence_fails(self):
        mutations = {
            "missing_cpu_parameter": lambda d: d["coverage"]["cpu_checked_names"].pop(),
            "missing_gpu_parameter": lambda d: d["coverage"]["gpu_checked_names"].pop(),
            "omitted_checkpoint_tensor": lambda d: d["coverage"]["checkpoint_tensor_names"].append("missing.weight"),
            "missing_final_guard": lambda d: d["phase_checks"].pop(),
            "missing_sample_after": lambda d: d["phase_checks"].pop(-2),
            "missing_verification": lambda d: d["phase_checks"].pop(4),
            "wrong_expected_content": lambda d: d["phase_checks"][0].update(observed_root_sha256="f" * 64),
            "mutated_runtime_content": lambda d: d["phase_checks"][-1].update(observed_root_sha256="f" * 64),
            "false_phase": lambda d: d["phase_checks"][-1].update(exact=False),
            "hidden_storage_error": lambda d: d["phase_checks"][-1].update(identity_errors=["linear.weight"]),
            "source_relabel": lambda d: d.update(source_sha256="f" * 64),
            "phase_coverage_omission": lambda d: d["phase_checks"][-1]["checked_names"].pop(),
            "wrong_stage": lambda d: d["identity"].update(stage="pilot"),
            "wrong_gpu": lambda d: d["identity"].update(gpu_uuid=GPU1),
            "wrong_baseline_root": lambda d: d.update(baseline_root_sha256="f" * 64),
            "changed_baseline_tensor": lambda d: d["baseline_manifest"]["linear.weight"].update(sha256="f" * 64),
            "unqualified": lambda d: d.update(qualified=False),
        }
        original = deepcopy(self.data)
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                value = deepcopy(original)
                mutate(value)
                save_integrity(self.folder, self.manifest, self.summary, value)
                with self.assertRaises((ValueError, KeyError)):
                    self.validate()

    def test_checks_log_hash_and_content_both_bound(self):
        with (self.folder / "integrity_checks.jsonl").open("a") as stream:
            stream.write("{}\n")
        with self.assertRaisesRegex(ValueError, "log hash"):
            self.validate()
        self.data["checks_jsonl_sha256"] = sha256_file(self.folder / "integrity_checks.jsonl")
        atomic_json(self.folder / "integrity.json", self.data)
        digest = sha256_file(self.folder / "integrity.json")
        self.manifest["integrity"]["sha256"] = digest
        self.manifest["artifacts"]["integrity.json"] = digest
        self.summary["integrity"]["sha256"] = digest
        with self.assertRaisesRegex(ValueError, "phase contents"):
            self.validate()

    def test_partial_failed_or_legacy_identity_cannot_gain_new_qualification(self):
        for state in ["failed", "running"]:
            self.manifest["state"] = state
            with self.assertRaisesRegex(ValueError, "complete attempt"):
                self.validate()
        self.manifest["state"] = "complete"
        with self.assertRaisesRegex(ValueError, "mixed"):
            validate_integrity_evidence(self.folder, self.manifest, None, sample_ids=self.ids)
        self.manifest["identity"].pop("integrity_contract_id")
        with self.assertRaisesRegex(ValueError, "contract"):
            self.validate()

    def test_missing_source_or_summary_binding_fails(self):
        saved = deepcopy(self.summary)
        self.summary.pop("integrity")
        with self.assertRaisesRegex(ValueError, "summary"):
            self.validate()
        self.summary = saved
        self.manifest["identity"]["code_sha256"].pop(str(self.folder/"gsm8k_weight_integrity.py"))
        with self.assertRaisesRegex(ValueError, "source coverage"):
            self.validate()


if __name__ == "__main__":
    unittest.main(verbosity=2)
