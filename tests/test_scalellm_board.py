#!/usr/bin/env python3

import hashlib
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

import numpy as np

from host.scalellm_board import (
    BOARD_AUDIT_REQUIRED_FILES,
    BOARD_AUDIT_INPUT_COUNT,
    BOARD_COMPLETE_INPUT_COUNT,
    BOARD_IMMUTABLE_INPUT_COUNT,
    BOARD_PROGRAM_REQUIRED_FILES,
    BOARD_REQUIRED_FILES,
    BOARD_RTL_VARIANT,
    BOARD_SLR_DSP,
    BOARD_TOTAL_DSP,
    MODEL_ID,
    QUANTIZATION_ID,
    P16_QUANTIZER3_PRIMITIVES,
    P16_REGION2_PRIMITIVES,
    REFERENCE_FIXEDPOINT,
    REFERENCE_LINEAR_COUNTS,
    REFERENCE_WEIGHT_BITS,
    SOFTWARE_REFERENCE_ID,
    SOFTWARE_REFERENCE_SCHEMA,
    BoardAuditEvidence,
    BoardBuildEvidence,
    BoardProgrammingEvidence,
    FrozenFile,
    FrozenWorkload,
    ScaleLLMBoardExecutor,
    WorkloadReference,
    WorkloadSample,
    sha256_file,
    streaming_lm_head,
)
from host.scalellm_hardware import HardwareCommandTelemetry
from host.scalellm_hostops import (
    ACTIVATION_SHAPE,
    LlamaNormWeights,
    PinnedActivationPool,
)
from host.scalellm_memory import (
    ACTIVATION_INPUT_PAYLOAD_BYTES,
    ACTIVATION_OUTPUT_PAYLOAD_BYTES,
    activation_base_for_buffer,
)
from host.scalellm_runtime import (
    Completion, CompletionStatus, Engine, RuntimeContractError,
)


class MemorySession:
    def __init__(self):
        self.memory = {}
        self.lock = threading.Lock()

    def h2c_write_local(self, channel, data, local_offset, chunk_bytes):
        with self.lock:
            self.memory[(channel, local_offset)] = bytes(data)
        return len(data)

    def c2h_read_into_local(
        self, channel, destination, local_offset, chunk_bytes
    ):
        with self.lock:
            data = self.memory[(channel, local_offset)]
        destination[:] = data
        return len(data)


class ZeroOutputBackend:
    def __init__(self, session):
        self.session = session
        self._telemetry = []
        self.lock = threading.Lock()

    @property
    def telemetry(self):
        with self.lock:
            return tuple(self._telemetry)

    def execute(self, engine, identity):
        time.sleep(0.003)
        offset = activation_base_for_buffer(identity.buffer_id)
        payload_bytes = (ACTIVATION_OUTPUT_PAYLOAD_BYTES
                         if engine is Engine.MLP
                         else ACTIVATION_INPUT_PAYLOAD_BYTES)
        with self.session.lock:
            self.session.memory[(0, offset)] = bytes(payload_bytes)
        completion = Completion(identity, CompletionStatus.SUCCESS)
        item = HardwareCommandTelemetry(
            engine.value, identity, "SUCCESS", time.monotonic_ns(),
            {"error_code": 0, "cycle_count": 1},
        )
        with self.lock:
            self._telemetry.append(item)
        return completion


class FakeHostModel:
    def __init__(self):
        self.norm_weights = LlamaNormWeights(
            np.ones((32, 4096), dtype=np.float32),
            np.ones((32, 4096), dtype=np.float32),
            np.ones(4096, dtype=np.float32),
        )

    def embed(self, token_ids):
        return np.full(
            ACTIVATION_SHAPE, token_ids[0] / 16.0, dtype=np.float32
        )

    def evaluate(self, hidden, target_token_ids, top_k=5):
        rows = hidden.shape[0]
        digest = hashlib.sha256(
            np.ascontiguousarray(hidden, dtype="<f4").tobytes()
        ).hexdigest()
        return {
            "rows": rows,
            "nll_sum": rows * 1.25,
            "mean_nll": 1.25,
            "per_row_nll": [1.25] * rows,
            "target_logits": [0.5] * rows,
            "top_token_ids": [[1, 2, 3, 4, 5] for _ in range(rows)],
            "top_logits": [[5.0, 4.0, 3.0, 2.0, 1.0] for _ in range(rows)],
            "final_normalized_sha256": digest,
        }


class DriftingHostModel(FakeHostModel):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def evaluate(self, hidden, target_token_ids, top_k=5):
        result = super().evaluate(hidden, target_token_ids, top_k)
        result["top_logits"][0][0] += self.calls
        self.calls += 1
        return result


class ScaleLLMBoardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _record(self, path, payload):
        path.write_bytes(payload)
        return {
            "path": str(path), "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }

    def _reference_evidence(self, samples, dataset_record):
        artifact = self.root / "scalecode_manifest.json"
        artifact_payload = json.dumps({
            "model_id": MODEL_ID,
            "layer_count": 32,
            "checkpoint_sha256": "a" * 64,
        }).encode("ascii")
        artifact_record = self._record(artifact, artifact_payload)
        source_records = []
        for name in (
            "generate_scalellm_workload_reference.py",
            "freeze_scalellm_workload.py",
            "fixedpoint_ops.py",
            "mlp4_fixedpoint_inference.py",
            "mlp4_method_inference.py",
            "scalepath4_method_inference.py",
        ):
            source_records.append(self._record(
                self.root / name, f"fixture:{name}\n".encode("ascii")
            ))
        records = []
        for sample in samples:
            records.append({
                "sample_id": sample["sample_id"],
                "input_token_ids": sample["input_token_ids"],
                "target_token_ids": sample["target_token_ids"],
                "nll_sum": 20.0,
                "mean_nll": 1.25,
                "per_row_nll": [1.25] * 16,
                "target_logits": [0.5] * 16,
                "top_token_ids": [[1, 2, 3, 4, 5] for _ in range(16)],
                "top_logits": [
                    [5.0, 4.0, 3.0, 2.0, 1.0] for _ in range(16)
                ],
            })
        evidence = {
            "schema": SOFTWARE_REFERENCE_SCHEMA,
            "software_id": SOFTWARE_REFERENCE_ID,
            "model_id": MODEL_ID,
            "checkpoint_sha256": "a" * 64,
            "artifact_manifest": artifact_record,
            "dataset": dataset_record,
            "seed": 7,
            "sample_count": len(samples),
            "valid_token_rows": len(samples) * 16,
            "quantization": {
                "attention": "Hadamard32 ScaleCode A8W8",
                "mlp": "Hadamard32 ScaleCode A8W4 SwiGLU",
                "fixedpoint": REFERENCE_FIXEDPOINT,
                "method": {
                    "case": "iah_scale_code_mlp_w4_fixedpoint_nonlinear",
                    "target_scope": "fixture",
                    "module_count": 32,
                    "per_arch": {"LlamaMLP": 32},
                    "linear_summary": {
                        "case": "iah_scale_code_mlp_w4_qdq_reference",
                        "target_scope": "fixture",
                        "module_count": 224,
                        "per_op": REFERENCE_LINEAR_COUNTS,
                        "per_op_weight_bits": REFERENCE_WEIGHT_BITS,
                        "hadamard_block": 32,
                        "group_size": 32,
                        "act_bits": 8,
                        "attention_weight_bits": 8,
                        "mlp_weight_bits": 4,
                        "scale_code_bits": 8,
                        "payload_format": "fixture",
                        "invariant": "fixture",
                    },
                    "fixedpoint_config": REFERENCE_FIXEDPOINT,
                    "nonlinear_modules": [
                        f"model.layers.{index}.mlp" for index in range(32)
                    ],
                },
            },
            "runtime": {
                "torch": "fixture",
                "cuda": "fixture",
                "device": "cuda:0",
                "gpu": "fixture",
                "dtype": "bfloat16",
                "batch_size": 2,
                "cpu_threads": 4,
                "deterministic_algorithms": True,
                "allow_tf32": False,
                "cublas_workspace_config": ":4096:8",
                "model_attach_ns": 1,
                "evaluation_ns": 1,
            },
            "source_files": source_records,
            "metric": "causal_nll",
            "nll_sum": 20.0 * len(samples),
            "mean_nll": 1.25,
            "records": records,
        }
        path = self.root / "reference.json"
        payload = (json.dumps(evidence, sort_keys=True) + "\n").encode("ascii")
        return self._record(path, payload)

    def _workload_manifest(self):
        dataset = self.root / "dataset.jsonl"
        dataset_record = self._record(dataset, b'{"text":"fixture"}\n')
        tokenizer_records = []
        for index in range(3):
            tokenizer_records.append(self._record(
                self.root / f"tokenizer{index}.json", f"tokenizer{index}".encode()
            ))
        samples = []
        for index in range(2):
            samples.append({
                "sample_id": f"sample-{index}",
                "input_token_ids": [index + 1] * 16,
                "target_token_ids": [index + 2] * 16,
                "valid_tokens": 16,
            })
        reference_record = self._reference_evidence(samples, dataset_record)
        raw = {
            "schema_version": 1,
            "model_id": MODEL_ID,
            "checkpoint_sha256": "a" * 64,
            "dataset": dataset_record,
            "tokenizer_files": tokenizer_records,
            "sample_count": 2,
            "profile": {
                "max_tokens": 128,
                "cohort_rows": 16,
                "attention_query_count": 16,
                "padding": "none",
                "truncation": "contiguous-17-token-window-to-16-causal-pairs",
                "valid_tokens_per_sample": 16,
            },
            "reference": {
                "software_id": SOFTWARE_REFERENCE_ID,
                "quantization": QUANTIZATION_ID,
                "metric": "causal_nll",
                "expected_mean_nll": 1.25,
                "absolute_tolerance": 0.0,
                "seed": 7,
                "evidence": reference_record,
            },
            "samples": samples,
        }
        path = self.root / "workload.json"
        path.write_text(json.dumps(raw), encoding="ascii")
        return path

    def test_workload_requires_hashed_unpadded_even_cohorts(self):
        path = self._workload_manifest()
        workload = FrozenWorkload.load(path)
        self.assertEqual(workload.valid_tokens, 32)
        self.assertEqual(len(workload.samples), 2)
        raw = json.loads(path.read_text())
        raw["samples"][0]["valid_tokens"] = 15
        path.write_text(json.dumps(raw), encoding="ascii")
        with self.assertRaisesRegex(RuntimeContractError, "forbids padded"):
            FrozenWorkload.load(path)

    def test_workload_rejects_mutated_reference_evidence(self):
        path = self._workload_manifest()
        FrozenWorkload.load(path)
        reference = self.root / "reference.json"
        payload = reference.read_bytes()
        reference.write_bytes(bytes([payload[0] ^ 1]) + payload[1:])
        with self.assertRaisesRegex(RuntimeContractError, "SHA256 mismatch"):
            FrozenWorkload.load(path)

    def test_workload_rejects_rehashed_partial_quantization_evidence(self):
        path = self._workload_manifest()
        raw = json.loads(path.read_text(encoding="ascii"))
        reference_path = self.root / "reference.json"
        evidence = json.loads(reference_path.read_text(encoding="ascii"))
        evidence["quantization"]["method"]["linear_summary"]["per_op"][
            "q_proj"
        ] = 31
        payload = (json.dumps(evidence, sort_keys=True) + "\n").encode("ascii")
        raw["reference"]["evidence"] = self._record(reference_path, payload)
        path.write_text(json.dumps(raw), encoding="ascii")
        with self.assertRaisesRegex(RuntimeContractError, "linear per_op drifted"):
            FrozenWorkload.load(path)

    def test_streaming_lm_head_matches_materialized_logits(self):
        hidden = np.array([
            [1.0, -2.0, 0.5, 3.0],
            [0.0, 1.0, -1.0, 2.0],
            [1.0, 1.0, 1.0, 1.0],
        ], dtype=np.float32)
        weights = np.array([
            [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0],
            [0, 0, 0, 1], [1, 1, 0, 0], [0, 0, 1, 1],
            [1, -1, 1, -1],
        ], dtype=np.float32)
        targets = [0, 4, 6]
        result = streaming_lm_head(
            hidden, targets, len(weights),
            lambda start, stop: weights[start:stop], chunk_rows=3, top_k=3,
        )
        logits = hidden @ weights.T
        expected_nll = (
            np.log(np.sum(np.exp(logits.astype(np.float64)), axis=1))
            - logits[np.arange(3), targets]
        )
        np.testing.assert_allclose(result["per_row_nll"], expected_nll,
                                   rtol=0, atol=1e-12)
        expected_ids = np.lexsort((
            np.broadcast_to(np.arange(7), logits.shape), -logits
        ), axis=1)[:, :3]
        self.assertEqual(result["top_token_ids"], expected_ids.tolist())

    def test_board_build_evidence_requires_exact_hash_and_signoff(self):
        report = self.root / "board"
        report.mkdir()
        for name in BOARD_REQUIRED_FILES:
            if name != "OUTPUT_SHA256SUMS":
                (report / name).write_text("fixture\n", encoding="ascii")
        physical_report_texts = {
            "p9_postprocess_plan_post_route.txt": "\n".join((
                "status=V5_BOARD_POST_ROUTE_P9_POSTPROCESS_PLAN_PASS",
                "contract=P9_POSTPROCESS_SPLIT_6_4_6",
                "row_bank_count=16", "all_row_primitives=42784",
                "slr0_row_primitives=16044", "center_row_primitives=10696",
                "slr2_row_primitives=16044", "per_row_primitives=2674",
                "per_row_lut=994", "per_row_ff=1536",
            )) + "\n",
            "p9_postprocess_pblocks_post_route.txt": "\n".join((
                "status=V5_BOARD_POST_ROUTE_P9_POSTPROCESS_PBLOCKS_PASS",
                "ok=1", "require_placed=1", "pblock_count=2",
                "center_missing=0", "center_outer_overlap=0",
                "center_wrong=0", "outer_wrong=0", "outer_extras=0",
                "slr0_name=pb_v5_p9_postprocess_rows0_5_slr0",
                "slr0_target=0", "slr0_expected=16044",
                "slr0_members=16044", "slr0_missing=0", "slr0_extras=0",
                "slr0_wrong=0", "slr0_hard=dsp 0 uram 0 ramb36 0 ramb18 0",
                "slr2_name=pb_v5_p9_postprocess_rows10_15_slr2",
                "slr2_target=2", "slr2_expected=16044",
                "slr2_members=16044", "slr2_missing=0", "slr2_extras=0",
                "slr2_wrong=0", "slr2_hard=dsp 0 uram 0 ramb36 0 ramb18 0",
            )) + "\n",
            "p9_quantizer3_plan_post_route.txt": "\n".join((
                "status=V5_BOARD_POST_ROUTE_P9_QUANTIZER3_PLAN_PASS",
                "contract=P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6",
                f"primitive_count={P16_QUANTIZER3_PRIMITIVES}",
                "lut=9959", "ff=3794",
                "pblock_name=pb_v5_p9_swiglu_quantizer3_cr_x2y5_x3y6",
                "grid_range=CLOCKREGION_X2Y5:CLOCKREGION_X3Y6",
                "allowed_regions=X2Y5 X2Y6 X3Y5 X3Y6", "dsp=0",
                "uram=0", "ramb36=0", "ramb18=0",
            )) + "\n",
            "p9_quantizer3_pblock_post_route.txt": "\n".join((
                "status=V5_BOARD_POST_ROUTE_P9_QUANTIZER3_PBLOCK_PASS",
                "ok=1", "require_placed=1",
                "name=pb_v5_p9_swiglu_quantizer3_cr_x2y5_x3y6",
                "contract=P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6",
                "grid_range=CLOCKREGION_X2Y5:CLOCKREGION_X3Y6",
                f"expected={P16_QUANTIZER3_PRIMITIVES}",
                f"members={P16_QUANTIZER3_PRIMITIVES}",
                "missing=0", "extras=0",
                "wrong=0", "unplaced=0",
            )) + "\n",
            "p14_region2_relief_plan_post_route.txt": "\n".join((
                "status=V5_BOARD_POST_ROUTE_P14_REGION2_RELIEF_PLAN_PASS",
                "contract=P14_ATTN_REGION2_SHARED_X0_X2",
                "pblock_name=p3_pb_projection_center_region2_shared_cr_x0y5_x1y9",
                "base_range=CLOCKREGION_X0Y5:CLOCKREGION_X1Y9",
                "relief_range=CLOCKREGION_X2Y5:CLOCKREGION_X2Y9",
                "expected_range=CLOCKREGION_X0Y5:CLOCKREGION_X2Y9",
                f"primitive_count={P16_REGION2_PRIMITIVES}",
                "lut=35269", "ff=34743", "dsp=544",
            )) + "\n",
            "p14_region2_relief_pblock_post_route.txt": "\n".join((
                "status=V5_BOARD_POST_ROUTE_P14_REGION2_RELIEF_PBLOCK_PASS",
                "ok=1", "contract=P14_ATTN_REGION2_SHARED_X0_X2",
                "require_placed=1",
                "name=p3_pb_projection_center_region2_shared_cr_x0y5_x1y9",
                f"primitive_count={P16_REGION2_PRIMITIVES}",
                "lut=35269", "ff=34743", "dsp=544",
                "missing=0", "wrong=0", "unplaced=0", "relief_placed=100",
            )) + "\n",
            "p8_parent_ingress_boundary_post_route.txt": "\n".join((
                "V5_BOARD_POST_ROUTE_P8_PARENT_INGRESS_BOUNDARY_PASS",
                "ok=1", "parent_head_ff=6560", "parent_tail_ff=6560",
                "parent_count_ff=2", "parent_count_physical_ff=16",
                "parent_count_replica_ff=14",
                "parent_count_bit0_physical_ff=8",
                "parent_count_bit1_physical_ff=8",
                "parent_count_replica_equivalence_ok=1", "parent_pointer_ff=0",
                "local_clear_ff=2", "branch_ingress_count_ff=4",
                "local_clear_shared_upstream_ready_paths=0",
                "branch_credit_shared_upstream_ready_paths=0",
                "local_clear_gate_compute_ready_paths=0",
                "branch_credit_gate_compute_ready_paths=0",
                "local_clear_down_compute_ready_paths=0",
                "branch_credit_down_compute_ready_paths=0",
                "local_clear_input_cache_ready_paths=0",
                "branch_credit_input_cache_ready_paths=0",
            )) + "\n",
        }
        for name, report_text in physical_report_texts.items():
            (report / name).write_text(report_text, encoding="ascii")
        p16_post_opt_summary = self.root / "p16_post_opt_summary.txt"
        p16_post_opt_summary.write_text("\n".join((
            "status=PASS", "attention_lane_instances=128",
            "local_dual_accumulator_instances=6",
            "local_accumulator_contexts=12", "dut_dsp48e2=2240",
            "array_dsp48e2=2176", "frontend_dsp48e2=64",
            "frontend_quantizer_dsp48e2=0", "place_authorized=0",
            "route_authorized=0",
        )) + "\n", encoding="ascii")
        production_dcp_sha = "b" * 64
        p16_region2_summary = self.root / "p16_region2_summary.txt"
        p16_region2_summary.write_text("\n".join((
            "status=V5_P16_PRODUCTION_REGION2_POST_OPT_PROBE_PASS",
            f"input_dcp_sha256={production_dcp_sha}",
            "attention_lane_instances=128",
            "local_dual_accumulator_instances=6",
            "local_accumulator_contexts=12", "dut_dsp48e2=2240",
            "frontend_quantizer_dsp48e2=0", "region2_lane_instances=32",
            f"region2_primitives={P16_REGION2_PRIMITIVES}",
            "region2_dsp48e2=544", "region2_rows0_3_primitives=26800",
            "region2_rows0_3_dsp48e2=272",
            "region2_rows4_7_primitives=26800",
            "region2_rows4_7_dsp48e2=272",
            "region2_residual_primitives=19296",
            "region2_residual_dsp48e2=0", "partition_exact_cover=1",
            "drc_errors=0", "implementation_commands_run=0",
            "checkpoint_written=0",
        )) + "\n", encoding="ascii")
        p16_post_opt_sha = sha256_file(p16_post_opt_summary)
        p16_region2_sha = sha256_file(p16_region2_summary)
        region2_signature = (
            f"P16_PRODUCTION_POST_OPT_SHA256:{p16_region2_sha}"
        )
        bit_hash = sha256_file(report / "attention_mlp_vcu118_v5.bit")
        dcp_hash = sha256_file(report / "attention_mlp_vcu118_v5_post_route.dcp")
        (report / "launcher_status.txt").write_text("\n".join((
            "status=PASS", "final_exit_code=0", "vivado_exit_code=0",
            "vivado_invoked=1", "complete_input_manifest_sha_match=1",
            f"immutable_input_count={BOARD_IMMUTABLE_INPUT_COUNT}",
            "immutable_input_manifest_sha_match=1",
            "immutable_input_postcheck=1",
            "recursive_source_post_build_sha_verified=1",
            "ooc_route_authorization_post_build_verified=1",
            "bitstream_generated=1", f"rtl_variant={BOARD_RTL_VARIANT}",
        )) + "\n", encoding="ascii")
        common_post_route = (
            "evidence_class=FULL_VCU118_BOARD_POST_ROUTE",
            f"rtl_variant={BOARD_RTL_VARIANT}",
            f"rtl_resource_variant={BOARD_RTL_VARIANT}",
            f"region2_signature_source={region2_signature}",
            "core_clock_mhz=100", "ddr0_clock_mhz=300",
            "ddr1_clock_mhz=300", "v5_serial_instances=1",
            "old_serial_instances=0", "v5_shared_instances=1",
            "v5_branch_instances=2", "v5_kernel12_instances=2",
            "v4_kernel16_instances=0", "history2_repack_instances=2",
            "generic_repack_instances=0", f"dsp48e2={BOARD_TOTAL_DSP}",
            "mlp_kernel_dsp48e2=3072", "uram288=752",
            "projection_weight_capture_ok=1", "architecture_boundary_ok=1",
            "unplaced_primitives=0", "wrong_slr_primitives=0",
            "compute_clock_buffer_none_ok=1", "no_clock_endpoints=0",
            "unconstrained_paths=0", "timing_coverage_ok=1",
            "route_error_nets=0",
            "explicit_gap_nets=0", "unrouted_nets=0",
            "some_unrouted_pin_nets=0", "resource_conflict_nets=0",
            "antenna_island_nets=0", "route_status_partial=0",
            "route_status_conflicts=0", "route_clean=1", "drc_errors=0",
            "cdc_critical=0", "data_bufg=0",
            "congestion_level6_or_higher_windows=0",
            "exception_scope_policy_ok=1", "live_post_route_rediscovery_ok=1",
            "base_contract_variant=P2_COHORT16_COL2_12_2",
            "p5_contract=P5_INPUT_HALF_LOCAL_8_8",
            "p9_postprocess_contract=P9_POSTPROCESS_SPLIT_6_4_6",
            "p9_quantizer3_contract=P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6",
            "p14_region2_relief_contract=P14_ATTN_REGION2_SHARED_X0_X2",
            "pblock_contract_variant=P2_COHORT16_COL2_12_2",
            "pblock_contract_ok=1", "pblock_require_placed=1",
            "pblock_count=26", "canonical_pblock_count=11",
            "geometry_pblock_count=10", "p5_added_pblock_count=2",
            "p9_postprocess_added_pblock_count=2",
            "p9_quantizer3_added_pblock_count=1",
            "p14_region2_relief_added_pblock_count=0",
            "total_pblock_count=26",
            "completed_u8_ff=4096",
            "completed_meta_ff=352", "input_capture_ff=12288",
            "input_capture_controls=48", "p5_center_wrong_slr=0",
            "p5_outer_wrong_slr=0",
            "p9_postprocess_center_wrong_slr=0",
            "p9_postprocess_outer_wrong_slr=0",
            "p9_slr0_row_primitives=16044",
            "p9_center_row_primitives=10696",
            "p9_slr2_row_primitives=16044",
            f"p9_quantizer3_primitives={P16_QUANTIZER3_PRIMITIVES}",
            "p9_quantizer3_grid_range=CLOCKREGION_X2Y5:CLOCKREGION_X3Y6",
            "p9_quantizer3_wrong_region=0", "p9_quantizer3_unplaced=0",
            f"p14_region2_relief_primitives={P16_REGION2_PRIMITIVES}",
            "p14_region2_relief_base_range=CLOCKREGION_X0Y5:CLOCKREGION_X1Y9",
            "p14_region2_relief_range=CLOCKREGION_X2Y5:CLOCKREGION_X2Y9",
            "p14_region2_expected_range=CLOCKREGION_X0Y5:CLOCKREGION_X2Y9",
            "p14_region2_relief_placed=100",
            "p14_region2_relief_wrong=0", "p14_region2_relief_unplaced=0",
            "parent_head_ff=6560", "parent_tail_ff=6560",
            "parent_count_ff=2", "parent_count_physical_ff=16",
            "parent_count_replica_ff=14",
            "parent_count_replica_equivalence_ok=1", "parent_pointer_ff=0",
            "local_clear_shared_upstream_ready_paths=0",
            "branch_credit_shared_upstream_ready_paths=0",
            "local_clear_gate_compute_ready_paths=0",
            "branch_credit_gate_compute_ready_paths=0",
            "local_clear_down_compute_ready_paths=0",
            "branch_credit_down_compute_ready_paths=0",
            "local_clear_input_cache_ready_paths=0",
            "branch_credit_input_cache_ready_paths=0",
            "geometry_region0_input_primitives=3136",
            "geometry_region3_input_primitives=2112",
            "geometry_owner_region2_weight_primitives=2048",
            "geometry_region0_input_ok=1", "geometry_region3_input_ok=1",
            "geometry_owner_region2_weight_ok=1",
            f"projected_slr_dsp48e2={' '.join(map(str, BOARD_SLR_DSP))}",
            "projected_slr_uram288=224 224 304",
            "slr0_dsp48e2=1862", f"slr1_dsp48e2={BOARD_SLR_DSP[1]}",
            "slr2_dsp48e2=1810", "slr0_uram288=224",
            "slr1_uram288=224", "slr2_uram288=304",
            f"pblock_dsp_coverage={BOARD_TOTAL_DSP}",
            "pblock_uram_coverage=752", "pblock_wrong_slr=0",
            "physical_placement_ok=1", "physical_ok=1",
            "floorplan_contract_ok=1",
            "wns_ns=0.001", "whs_ns=0.002",
            f"bitstream={report / 'attention_mlp_vcu118_v5.bit'}",
            f"bitstream_sha256={bit_hash}",
        )
        summary_text = "\n".join((
            "status=V5_BOARD_BITSTREAM_PASS",
            "post_route_gate_status=V5_BOARD_POST_ROUTE_PASS",
            "complete_input_sha_verified=1",
            f"complete_input_count={BOARD_COMPLETE_INPUT_COUNT}",
            f"immutable_input_count={BOARD_IMMUTABLE_INPUT_COUNT}",
            "immutable_input_sha_verified=1",
            "recursive_source_sha_verified=1",
            "ooc_route_authorization_verified=1",
            f"checkpoint_sha256={dcp_hash}",
            f"p16_post_opt_summary={p16_post_opt_summary}",
            f"p16_post_opt_summary_sha256={p16_post_opt_sha}",
            f"p16_production_region2_summary={p16_region2_summary}",
            f"p16_production_region2_summary_sha256={p16_region2_sha}",
            f"p16_production_dcp_sha256={production_dcp_sha}",
            *common_post_route,
        )) + "\n"
        (report / "summary.txt").write_text(summary_text, encoding="ascii")
        (report / "post_route_gate_summary.txt").write_text("\n".join((
            "status=V5_BOARD_POST_ROUTE_PASS", *common_post_route,
        )) + "\n", encoding="ascii")

        def write_output_manifest():
            files = sorted(
                path for path in report.iterdir()
                if path.is_file() and path.name != "OUTPUT_SHA256SUMS"
            )
            (report / "OUTPUT_SHA256SUMS").write_text("".join(
                f"{sha256_file(path)}  {path}\n" for path in files
            ), encoding="ascii")

        write_output_manifest()
        evidence = BoardBuildEvidence.load(report)
        self.assertEqual(evidence.rtl_variant, BOARD_RTL_VARIANT)
        self.assertEqual(evidence.bitstream_sha256, bit_hash)
        self.assertGreaterEqual(evidence.wns_ns, 0)
        (report / "summary.txt").write_text(
            summary_text.replace(BOARD_RTL_VARIANT, "P14_LEGACY"),
            encoding="ascii",
        )
        write_output_manifest()
        with self.assertRaisesRegex(RuntimeContractError, "not the frozen"):
            BoardBuildEvidence.load(report)
        (report / "summary.txt").write_text(summary_text, encoding="ascii")
        write_output_manifest()
        region2_payload = p16_region2_summary.read_bytes()
        p16_region2_summary.write_bytes(region2_payload + b"drift=1\n")
        with self.assertRaisesRegex(RuntimeContractError, "lineage SHA256"):
            BoardBuildEvidence.load(report)
        p16_region2_summary.write_bytes(region2_payload)
        p14_plan_path = report / "p14_region2_relief_plan_post_route.txt"
        p14_plan_path.write_text(
            physical_report_texts[p14_plan_path.name].replace(
                f"primitive_count={P16_REGION2_PRIMITIVES}",
                f"primitive_count={P16_REGION2_PRIMITIVES - 2}",
            ),
            encoding="ascii",
        )
        write_output_manifest()
        with self.assertRaisesRegex(
            RuntimeContractError, "P16 report invariant failed"
        ):
            BoardBuildEvidence.load(report)
        p14_plan_path.write_text(
            physical_report_texts[p14_plan_path.name], encoding="ascii"
        )
        write_output_manifest()

        audit = self.root / "board_audit"
        audit.mkdir()
        for name in BOARD_AUDIT_REQUIRED_FILES:
            if name != "OUTPUT_SHA256SUMS":
                (audit / name).write_text("fixture\n", encoding="ascii")
        for name, report_text in physical_report_texts.items():
            (audit / name).write_text(report_text, encoding="ascii")
        project = Path(__file__).resolve().parents[1]
        scripts = project / "vivado" / "scripts"
        audit_inputs = (
            report / "attention_mlp_vcu118_v5_post_route.dcp",
            report / "attention_mlp_vcu118_v5.bit",
            report / "XDC_SOURCE_INVENTORY",
            report / "summary.txt",
            scripts / "audit_attention_mlp_vcu118_v5_post_route.tcl",
            scripts / "attention_mlp_vcu118_v5_post_route_gate.tcl",
            scripts / "v5_production_floorplan_selectors.tcl",
            scripts /
            "projection_core16x16_w8_reuse_ooc_p16_bound_floorplan.tcl",
            scripts / "v5_production_p5_input_partition_floorplan.tcl",
            scripts / "v5_production_p9_postprocess_partition_floorplan.tcl",
            scripts /
            "v5_production_p16_noclip_quantizer3_locality_floorplan.tcl",
            scripts /
            "v5_production_p16_noclip_region2_x2_relief_floorplan.tcl",
            scripts / "audit_mlp_p8_parent_ingress_boundary_replica_aware.tcl",
            scripts / "projection_core16x16_w8_reuse_ooc_p16_floorplan.tcl",
            scripts / "projection_core16x16_w8_reuse_ooc_floorplan.tcl",
            scripts / "v5_production_p9_quantizer3_locality_floorplan.tcl",
            scripts / "v5_production_p14_region2_x2_relief_floorplan.tcl",
            p16_post_opt_summary,
            p16_region2_summary,
            scripts / "run_attention_mlp_vcu118_v5_post_route_audit.sh",
        )
        (audit / "INPUT_FILES").write_text(
            "".join(f"{path.resolve()}\n" for path in audit_inputs),
            encoding="ascii",
        )
        (audit / "INPUT_SHA256SUMS").write_text(
            "".join(
                f"{sha256_file(path)}  {path.resolve()}\n"
                for path in audit_inputs
            ), encoding="ascii",
        )
        audit_input_sha = sha256_file(audit / "INPUT_SHA256SUMS")
        (audit / "launcher_status.txt").write_text("\n".join((
            "status=PASS", "final_exit_code=0", "vivado_exit_code=0",
            "vivado_invoked=1", "input_sha_precheck=1",
            "input_sha_postcheck=1", "input_manifest_sha_match=1",
            f"input_manifest_sha256={audit_input_sha}",
            f"rtl_variant={BOARD_RTL_VARIANT}",
        )) + "\n", encoding="ascii")
        (audit / "summary.txt").write_text("\n".join((
            "status=V5_BOARD_INDEPENDENT_AUDIT_PASS",
            "post_route_gate_status=V5_BOARD_POST_ROUTE_PASS",
            f"audit_input_manifest_entries={BOARD_AUDIT_INPUT_COUNT}",
            f"audit_input_manifest_sha256={audit_input_sha}",
            "audit_input_manifests_verified=1",
            f"checkpoint={report / 'attention_mlp_vcu118_v5_post_route.dcp'}",
            f"checkpoint_sha256={dcp_hash}",
            f"p16_post_opt_summary={p16_post_opt_summary}",
            f"p16_post_opt_summary_sha256={p16_post_opt_sha}",
            f"p16_production_region2_summary={p16_region2_summary}",
            f"p16_production_region2_summary_sha256={p16_region2_sha}",
            f"p16_production_dcp_sha256={production_dcp_sha}",
            *common_post_route,
        )) + "\n", encoding="ascii")
        (audit / "post_route_gate_summary.txt").write_text("\n".join((
            "status=V5_BOARD_POST_ROUTE_PASS", *common_post_route,
        )) + "\n", encoding="ascii")

        def write_audit_output_manifest():
            files = sorted(
                path for path in audit.iterdir()
                if path.is_file() and path.name != "OUTPUT_SHA256SUMS"
            )
            (audit / "OUTPUT_SHA256SUMS").write_text("".join(
                f"{sha256_file(path)}  {path}\n" for path in files
            ), encoding="ascii")

        write_audit_output_manifest()
        audit_evidence = BoardAuditEvidence.load(audit, evidence)
        self.assertEqual(audit_evidence.bitstream_sha256, bit_hash)

        program = self.root / "board_program"
        program.mkdir()
        for name in BOARD_PROGRAM_REQUIRED_FILES:
            if name != "OUTPUT_SHA256SUMS":
                (program / name).write_text("fixture\n", encoding="ascii")
        program_inputs = (
            report / "attention_mlp_vcu118_v5.bit",
            report / "OUTPUT_SHA256SUMS",
            audit / "OUTPUT_SHA256SUMS",
            scripts / "program_attention_mlp_vcu118_v5_bitstream.tcl",
            scripts / "run_program_attention_mlp_vcu118_v5_bitstream.sh",
        )
        (program / "INPUT_FILES").write_text(
            "".join(f"{path.resolve()}\n" for path in program_inputs),
            encoding="ascii",
        )
        (program / "INPUT_SHA256SUMS").write_text(
            "".join(
                f"{sha256_file(path)}  {path.resolve()}\n"
                for path in program_inputs
            ), encoding="ascii",
        )
        program_input_sha = sha256_file(program / "INPUT_SHA256SUMS")
        (program / "launcher_status.txt").write_text("\n".join((
            "status=PASS", "vivado_exit_code=0", "input_sha_postcheck=1",
            "input_manifest_sha_match=1", "board_output_sha_postcheck=1",
            "audit_output_sha_postcheck=1",
            f"input_manifest_sha256={program_input_sha}",
        )) + "\n", encoding="ascii")
        program_summary = "\n".join((
            "status=V5_VCU118_PROGRAM_PASS", "tool=2025.2",
            "hw_server_url=localhost:3121", "hw_target=fixture-target",
            "device=xcvu9p_0", "part=xcvu9p",
            f"program_file={report / 'attention_mlp_vcu118_v5.bit'}",
            f"bitstream_size_bytes={(report / 'attention_mlp_vcu118_v5.bit').stat().st_size}",
            f"bitstream_sha256={bit_hash}", "program_done=1",
        )) + "\n"
        (program / "summary.txt").write_text(
            program_summary, encoding="ascii"
        )

        def write_program_output_manifest():
            files = sorted(
                path for path in program.iterdir()
                if path.is_file() and path.name != "OUTPUT_SHA256SUMS"
            )
            (program / "OUTPUT_SHA256SUMS").write_text("".join(
                f"{sha256_file(path)}  {path}\n" for path in files
            ), encoding="ascii")

        write_program_output_manifest()
        program_evidence = BoardProgrammingEvidence.load(
            program, evidence, audit_evidence
        )
        self.assertEqual(program_evidence.bitstream_sha256, bit_hash)
        (program / "summary.txt").write_text(
            program_summary.replace(bit_hash, "0" * 64), encoding="ascii"
        )
        write_program_output_manifest()
        with self.assertRaisesRegex(RuntimeContractError, "disagrees with audit"):
            BoardProgrammingEvidence.load(program, evidence, audit_evidence)

        (audit / "summary.txt").write_text(
            (audit / "summary.txt").read_text(encoding="ascii").replace(
                f"checkpoint_sha256={dcp_hash}",
                f"checkpoint_sha256={'0' * 64}",
            ), encoding="ascii",
        )
        write_audit_output_manifest()
        with self.assertRaisesRegex(RuntimeContractError, "hashes disagree"):
            BoardAuditEvidence.load(audit, evidence)

        (report / "summary.txt").write_text(
            summary_text.replace("route_clean=1", "route_clean=0"),
            encoding="ascii",
        )
        write_output_manifest()
        with self.assertRaisesRegex(RuntimeContractError, "invariant failed"):
            BoardBuildEvidence.load(report)
        (report / "summary.txt").write_text(summary_text, encoding="ascii")
        write_output_manifest()
        (report / "attention_mlp_vcu118_v5.bit").write_text(
            "mutated\n", encoding="ascii"
        )
        with self.assertRaisesRegex(RuntimeContractError, "SHA256 mismatch"):
            BoardBuildEvidence.load(report)

    def test_three_run_executor_uses_32_layers_unique_ids_and_stable_result(self):
        manifest_path = self._workload_manifest()
        workload = FrozenWorkload.load(manifest_path)
        session = MemorySession()
        backend = ZeroOutputBackend(session)
        with PinnedActivationPool(session, require_lock=True) as transfers:
            result = ScaleLLMBoardExecutor(
                backend, transfers, FakeHostModel(), workload
            ).run(repetitions=3)
        self.assertEqual(result["repetitions"], 3)
        self.assertEqual(len(result["runs"]), 3)
        self.assertEqual(
            [run["commands"] for run in result["runs"]], [128, 128, 128]
        )
        self.assertEqual(len(backend.telemetry), 384)
        command_ids = [item.identity.command_id for item in backend.telemetry]
        request_ids = [item.identity.request_id for item in backend.telemetry]
        self.assertEqual(sorted(command_ids), list(range(1, 385)))
        self.assertEqual(set(request_ids), set(range(1, 7)))
        self.assertTrue(all(run["metric_pass"] for run in result["runs"]))
        self.assertEqual(
            len({run["result_signature"] for run in result["runs"]}), 1
        )
        self.assertTrue(all(
            run["attention_mlp_overlap_ns"] > 0 for run in result["runs"]
        ))

    def test_three_run_signature_covers_complete_lm_head_metrics(self):
        workload = FrozenWorkload.load(self._workload_manifest())
        session = MemorySession()
        backend = ZeroOutputBackend(session)
        with PinnedActivationPool(session, require_lock=True) as transfers:
            with self.assertRaisesRegex(
                RuntimeContractError, "result signatures disagree"
            ):
                ScaleLLMBoardExecutor(
                    backend, transfers, DriftingHostModel(), workload
                ).run(repetitions=3)


if __name__ == "__main__":
    unittest.main()
