#!/usr/bin/env python3

import hashlib
import json
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest import mock
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
    CURRENT_PROFILE,
    CURRENT_REFERENCE_ID,
    CURRENT_REFERENCE_SCHEMA,
    CURRENT_NUMERIC_CONTRACT,
    LEGACY_PROFILE,
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
    _current_parse_physical,
    _validate_current_reference_evidence,
    run_board,
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


TARGET_MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"
EXPECTED_CURRENT_NUMERIC_CONTRACT = {
    "hadamard_group": 32,
    "hadamard_inverse_sqrt32_q16": 11585,
    "activation_quantizer": "raw_minmax_including_zero_no_source_preclip",
    "activation_scale_rounding": "nearest_even",
    "scalecode_division_rounding": "nearest_even",
    "folded_weight_rounding": "half_away_terminal_w8_w4_saturation",
    "gate_up": {"input_width": 24, "group_guard_width": 37,
                "accumulator_width": 44, "output_width": 24,
                "total_shift_range": [20, 44]},
    "down": {"input_width": 32, "hadamard_width": 35,
             "group_guard_width": 45, "accumulator_width": 54,
             "output_width": 32, "total_shift_range": [12, 44]},
    "swiglu": "signed_packed_s24_internal_s32",
    "attention": "integer_rope_kv12_qk_softmax_pv_legitimate_clamps",
}


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
        channel = 1 if engine is Engine.MLP else 0
        offset = activation_base_for_buffer(identity.buffer_id, engine.value, output=True)
        payload_bytes = (ACTIVATION_OUTPUT_PAYLOAD_BYTES
                         if engine is Engine.MLP
                         else ACTIVATION_INPUT_PAYLOAD_BYTES)
        with self.session.lock:
            self.session.memory[(channel, offset)] = bytes(payload_bytes)
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

    @staticmethod
    def _current_id(path):
        path = path.resolve(strict=True)
        return {"path": str(path), "bytes": path.stat().st_size,
                "sha256": sha256_file(path)}

    @staticmethod
    def _current_write(path, text="fixture\n"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def _current_package_fixture(self):
        # These files model a signed package; no installed Vivado scripts or
        # board store are needed to test path, hash and physical-report gates.
        hardware = self.root / "current_hardware"
        source = hardware / "host/scalellm_board.py"
        self._current_write(source, "# synthetic Host source identity fixture\n")
        patcher = mock.patch("host.scalellm_board.__file__", str(source))
        patcher.start()
        self.addCleanup(patcher.stop)
        (hardware / "vivado/reports").mkdir(parents=True, exist_ok=True)
        (hardware / "vivado/project").mkdir(parents=True, exist_ok=True)
        report_temp = tempfile.TemporaryDirectory(
            dir=hardware / "vivado/reports", prefix="host_current_fixture_")
        project_temp = tempfile.TemporaryDirectory(
            dir=hardware / "vivado/project", prefix="host_current_fixture_")
        self.addCleanup(report_temp.cleanup)
        self.addCleanup(project_temp.cleanup)
        base = Path(report_temp.name)
        project = Path(project_temp.name)
        route = base / "route"
        audit = base / "audit"
        bitgen = base / "bitgen"
        for directory in (route, audit, bitgen):
            directory.mkdir()
        self._current_write(project / "scalellm_vcu118_f05.xpr")

        identity = self._current_write(route / "build_identity.txt", "\n".join((
            "vivado=2025.2", "part=xcvu9p-flga2104-2L-e",
            "board=xilinx.com:vcu118:part0:2.0",
            "top=scalellm_vcu118_f05_bd_wrapper", "project=scalellm_vcu118_f05",
            "defines=HAP_BOARD_BUILD HAP_BOARD_V5 "
            "HAP_MLP_FULL_COMMAND_V5_MODULE=hap_mlp_full_command16_s54 "
            "HAP_ATTENTION_BOARD_MODULE=hap_attention_board_cohort16_core",
        )) + "\n")
        source = hardware / "host/scalellm_board.py"
        route_sources = (
            source, hardware / "vivado/scripts/build_vcu118_board.tcl",
            hardware / "vivado/scripts/emit_current_board_evidence.py",
            hardware / "vivado/manifests/attention_mlp_production_v5_cohort16_sources.list",
            hardware / "vivado/constraints/attention_mlp_vcu118_board_v5.xdc",
            hardware / "vivado/constraints/mission0005_coordinated_partition.xdc",
        )
        for path in route_sources:
            if not path.exists():
                self._current_write(path, "# synthetic source identity fixture\n")
        route_manifest = self._current_write(
            route / "inputs.sha256",
            "".join(f"{sha256_file(path)}  {path.resolve()}\n"
                    for path in route_sources))
        checkpoint = self._current_write(route / "routed.dcp", "routed checkpoint\n")
        self._current_write(route / "routed_checkpoint.sha256",
                            f"{sha256_file(checkpoint)}  {checkpoint.resolve()}\n")

        def launcher(path, stage, reports):
            return self._current_write(path, "\n".join((
                f"stage={stage}", "exit_code=0", "native_exit_code=0",
                f"project={project}", f"reports={reports}",
            )) + "\n")

        route_launcher = launcher(route / "launcher_status.txt", "route", route)
        audit_launcher = launcher(audit / "launcher_status.txt", "audit", audit)
        route_envelope_path = route / "board_evidence.json"
        for name in (
                "timing_post_route.rpt", "check_timing_post_route.rpt",
                "clocks_post_route.rpt", "clock_interaction_post_route.rpt",
                "cdc_post_route.rpt", "drc_post_route.rpt",
                "route_status_post_route.rpt", "exceptions_post_route.rpt"):
            self._current_write(route / name)
        route_envelope_path.write_text(json.dumps({
            "schema": "scalellm_board_build_evidence_v2",
            "profile": CURRENT_PROFILE, "stage": "route", "qualification": "HOLD",
            "physical_signoff": False, "bitstream": None,
            "reports": {name: self._current_id(route / name) for name in (
                "timing_post_route.rpt", "check_timing_post_route.rpt",
                "clocks_post_route.rpt", "clock_interaction_post_route.rpt",
                "cdc_post_route.rpt", "drc_post_route.rpt",
                "route_status_post_route.rpt", "exceptions_post_route.rpt",
                "routed.dcp", "routed_checkpoint.sha256")},
        }, indent=2) + "\n", encoding="utf-8")

        timing = """Design Timing Summary
WNS(ns) TNS(ns) TNS Failing Endpoints TNS Total Endpoints WHS(ns) THS(ns) THS Failing Endpoints THS Total Endpoints WPWS(ns) TPWS(ns) TPWS Failing Endpoints TPWS Total Endpoints
------- ------- --------------------- ------------------- ------- ------- --------------------- ------------------- -------- -------- ---------------------- --------------------
0.125 0.000 0 1000 0.075 0.000 0 1000 0.050 0.000 0 100
Timing constraints are met.
"""
        check = "\n".join(
            f"{index}. checking {name} (0)" for index, name in enumerate((
                "no_clock", "unconstrained_internal_endpoints", "multiple_clock",
                "generated_clocks", "loops", "latch_loops"), 1)) + "\n"
        clocks = ("pcie_refclk 10.000\n"
                  "default_250mhz_clk1_clk_p 4.000 generated 5.000\n"
                  "default_250mhz_clk2_clk_p 4.000 generated 5.000\n")
        route_status = """Design Route Status
# of routable nets..........................: 100
# of fully routed nets......................: 100
# of nets with routing errors...............: 0
# of unrouted nets..........................: 0
# of nets with some unrouted pins...........: 0
# of nets with resource conflicts...........: 0
# of nets with antenna violations...........: 0
# of nets with partial antenna violations...: 0
"""
        physical = {
            "timing_reopened.rpt": timing,
            "check_timing_reopened.rpt": check,
            "clocks_reopened.rpt": clocks,
            "clock_interaction_reopened.rpt": "Clock Interaction SAFE\n",
            "route_status_reopened.rpt": route_status,
            "drc_reopened.rpt": "No DRC violations found.\n",
            "cdc_reopened.rpt": "CDC-10 Critical 0 synchronized\n",
            "pulse_width_reopened.rpt": "Pulse Width Report\n",
            "pulse_width_violators_reopened.rpt": "No pulse-width violations found.\n",
            "bus_skew_reopened.rpt":
                "Bus Skew Report\nAll user specified bus skew constraints are met.\n",
        }
        for name, payload in physical.items():
            self._current_write(audit / name, payload)
        for name in ("exceptions_reopened.rpt", "io_reopened.rpt",
                     "dsp_status_paths_reopened.rpt"):
            self._current_write(audit / name)
        self._current_write(audit / "package_pins_reopened.txt", "port pin\n")
        audit_summary = self._current_write(audit / "audit_summary.txt", "\n".join((
            "status=REOPENED_REPORTS_READY_SIGNOFF_HOLD", "bitstream_generated=0",
            f"checkpoint_sha256={sha256_file(checkpoint)}",
            "part=xcvu9p-flga2104-2L-e", "core_generated_ns=10.000",
            "ddr_generated_ns=5.000", "ddr_reference_ns=4.000",
            "package_pin_count=234", "worst_setup_slack_ns=0.125",
            "worst_hold_slack_ns=0.075",
        )) + "\n")
        audit_inputs = (route_manifest, identity, checkpoint)
        audit_manifest = self._current_write(
            audit / "audit_inputs.sha256", "".join(
                f"{sha256_file(path)}  {path.resolve()}\n" for path in audit_inputs))
        audit_report_names = (
            "audit_summary.txt", "package_pins_reopened.txt",
            "timing_reopened.rpt", "check_timing_reopened.rpt",
            "clocks_reopened.rpt", "clock_interaction_reopened.rpt",
            "route_status_reopened.rpt", "drc_reopened.rpt", "cdc_reopened.rpt",
            "exceptions_reopened.rpt", "io_reopened.rpt", "pulse_width_reopened.rpt",
            "pulse_width_violators_reopened.rpt", "bus_skew_reopened.rpt",
            "dsp_status_paths_reopened.rpt",
        )
        audit_envelope_path = audit / "audit_evidence.json"
        audit_envelope_path.write_text(json.dumps({
            "schema": "scalellm_board_audit_evidence_v2",
            "profile": CURRENT_PROFILE, "stage": "audit", "qualification": "HOLD",
            "physical_signoff": False, "bitstream": None, "project": str(project),
            "build": {"vivado": "2025.2", "part": "xcvu9p-flga2104-2L-e",
                      "board": "xilinx.com:vcu118:part0:2.0",
                      "top": "scalellm_vcu118_f05_bd_wrapper",
                      "defines": "HAP_BOARD_BUILD HAP_BOARD_V5 "
                      "HAP_MLP_FULL_COMMAND_V5_MODULE=hap_mlp_full_command16_s54 "
                      "HAP_ATTENTION_BOARD_MODULE=hap_attention_board_cohort16_core"},
            "original_stage_exits": {}, "input_manifest": self._current_id(audit_manifest),
            "input_count": len(audit_inputs),
            "reports": {name: self._current_id(audit / name)
                        for name in audit_report_names},
            "source_synthesis": {},
            "source_route": {"input_manifest": self._current_id(route_manifest),
                             "build_identity": self._current_id(identity),
                             "board_evidence": self._current_id(route_envelope_path)},
            "routed_checkpoint": self._current_id(checkpoint),
        }, indent=2) + "\n", encoding="utf-8")

        joint = self._current_write(base / "joint.json", "{}\n")
        full32 = self._current_write(base / "full32.json", "{}\n")
        norm = self._current_write(base / "norm.json", "{}\n")
        preflight_path = bitgen / "bitgen_preflight.json"
        preflight = {
            "schema": "scalellm_mission0005_bitgen_preflight_v1",
            "status": "ELIGIBLE_FOR_LIVE_VIVADO_SIGNOFF_NOT_BITSTREAM",
            "profile": CURRENT_PROFILE, "part": "xcvu9p-flga2104-2L-e",
            "clocks": {"core_mhz": 100, "ddr0_ui_mhz": 200,
                       "ddr1_ui_mhz": 200, "reference_ps": 4000},
            "format_id": "0x48384605", "abi": "0x00050000",
            "project": str(project), "route_dir": str(route), "audit_dir": str(audit),
            "checkpoint": self._current_id(checkpoint),
            "route_input_manifest": self._current_id(route_manifest),
            "route_input_count": len(route_sources),
            "audit_input_manifest": self._current_id(audit_manifest),
            "audit_envelope": self._current_id(audit_envelope_path),
            "route_envelope": self._current_id(route_envelope_path),
            "route_launcher": self._current_id(route_launcher),
            "audit_launcher": self._current_id(audit_launcher),
            "build_identity": {"vivado": "2025.2", "part": "xcvu9p-flga2104-2L-e",
                               "board": "xilinx.com:vcu118:part0:2.0",
                               "top": "scalellm_vcu118_f05_bd_wrapper",
                               "defines": "HAP_BOARD_BUILD HAP_BOARD_V5 "
                               "HAP_MLP_FULL_COMMAND_V5_MODULE=hap_mlp_full_command16_s54 "
                               "HAP_ATTENTION_BOARD_MODULE=hap_attention_board_cohort16_core"},
            "physical": _current_parse_physical(audit, final=False),
            "joint": {"path": str(joint), "sha256": sha256_file(joint), "boundaries": 4,
                      "norm_adoption": {"path": str(norm), "sha256": sha256_file(norm),
                                        "cases": 6, "max_abs_error": 0.0,
                                        "reuse_only": True}},
            "full32": {"path": str(full32), "sha256": sha256_file(full32),
                       "comparisons": 128},
            "host_sources": [self._current_id(source)],
            "global_deadline_epoch": 1792022147.0, "created_epoch": time.time(),
        }
        preflight_path.write_text(json.dumps(preflight, indent=2) + "\n", encoding="utf-8")

        final_names = {
            "timing_bitgen.rpt": timing, "check_timing_bitgen.rpt": check,
            "clocks_bitgen.rpt": clocks,
            "clock_interaction_bitgen.rpt": "Clock Interaction SAFE\n",
            "route_status_bitgen.rpt": route_status,
            "drc_bitgen.rpt": "No DRC violations found.\n",
            "cdc_bitgen.rpt": "CDC-10 Critical 0 synchronized\n",
            "pulse_width_bitgen.rpt": "Pulse Width Report\n",
            "pulse_width_violators_bitgen.rpt": "No pulse-width violations found.\n",
            "bus_skew_bitgen.rpt":
                "Bus Skew Report\nAll user specified bus skew constraints are met.\n",
        }
        for name, payload in final_names.items():
            self._current_write(bitgen / name, payload)
        bitstream = self._current_write(
            bitgen / "scalellm_vcu118_f05_mission0005.bit", "bitstream\n")
        facts = self._current_write(bitgen / "bitgen_facts.txt", "\n".join((
            "status=MISSION0005_BITGEN_VIVADO_PASS", "part=xcvu9p-flga2104-2L-e",
            f"profile={CURRENT_PROFILE}", "format_id=0x48384605", "abi=0x00050000",
            "core_mhz=100", "ddr0_ui_mhz=200", "ddr1_ui_mhz=200",
            "reference_ps=4000", "board_accessed=0",
            f"preflight={preflight_path}", f"preflight_sha256={sha256_file(preflight_path)}",
            f"checkpoint={checkpoint}", f"checkpoint_sha256={sha256_file(checkpoint)}",
            f"bitstream={bitstream}", f"bitstream_sha256={sha256_file(bitstream)}",
            "worst_setup_slack_ns=0.125", "worst_hold_slack_ns=0.075",
        )) + "\n")
        evidence_path = bitgen / "bitstream_evidence.json"
        evidence_path.write_text(json.dumps({
            "schema": "scalellm_mission0005_bitstream_evidence_v1",
            "status": "BITSTREAM_GENERATED_NOT_BOARD_TESTED", "profile": CURRENT_PROFILE,
            "part": "xcvu9p-flga2104-2L-e", "format_id": "0x48384605",
            "abi": "0x00050000", "clocks": preflight["clocks"],
            "preflight": self._current_id(preflight_path),
            "checkpoint": self._current_id(checkpoint),
            "bitstream": self._current_id(bitstream), "bitgen_facts": self._current_id(facts),
            "host_sources": preflight["host_sources"], "board_accessed": False,
        }, indent=2) + "\n", encoding="utf-8")
        pin_xml = self._current_write(hardware / "vivado/board_fixture/part0_pins.xml",
                                      "<synthetic_board_pin_fixture/>\n")
        bitgen_inputs = (
            hardware / "vivado/scripts/run_mission0005_bitgen.sh",
            hardware / "vivado/scripts/mission0005_post_route_gate.py",
            hardware / "vivado/scripts/mission0005_bitgen.tcl", preflight_path,
            checkpoint, hardware / "vivado/constraints/vcu118_ddr4_explicit_pins.xdc",
            pin_xml,
        )
        for path in bitgen_inputs:
            if not path.exists():
                self._current_write(path, "# synthetic bitgen identity fixture\n")
        self._current_write(bitgen / "bitgen_inputs.sha256", "".join(
            f"{sha256_file(path)}  {path.resolve()}\n" for path in bitgen_inputs))
        self._current_write(bitgen / "launcher_status.txt", "\n".join((
            "stage=bitgen", "exit_code=0", "native_exit_code=0", f"project={project}",
            f"reports={bitgen}", f"route_reports={route}", f"audit_reports={audit}",
            "bitstream_generated=1", "board_accessed=0",
        )) + "\n")
        return SimpleNamespace(bitgen=bitgen, audit=audit, evidence=evidence_path,
                               timing=audit / "timing_reopened.rpt")

    def _reference_evidence(self, samples, dataset_record):
        artifact = self.root / "scalecode_manifest.json"
        artifact_payload = json.dumps({
            "model_id": TARGET_MODEL_ID,
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
            "model_id": TARGET_MODEL_ID,
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
            "model_id": TARGET_MODEL_ID,
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

    def _current_workload_manifest(self):
        path = self._workload_manifest()
        raw = json.loads(path.read_text(encoding="ascii"))
        evidence_path = self.root / "reference.json"
        evidence = json.loads(evidence_path.read_text(encoding="ascii"))
        artifact_path = self.root / "scalecode_manifest.json"
        artifact = json.loads(artifact_path.read_text(encoding="ascii"))
        artifact.update({
            "schema_version": 2,
            "checkpoint_id": "a" * 64,
            "attention_format_id": 0x4838_4103,
            "attention_abi": 0x0002_0000,
            "mlp_format_id": 0x4838_4605,
            "mlp_abi": 0x0005_0000,
        })
        evidence["artifact_manifest"] = self._record(
            artifact_path, json.dumps(artifact).encode("ascii")
        )
        evidence["schema"] = CURRENT_REFERENCE_SCHEMA
        evidence["profile"] = CURRENT_PROFILE
        evidence["software_id"] = CURRENT_REFERENCE_ID
        evidence["quantization"]["fixedpoint"] = EXPECTED_CURRENT_NUMERIC_CONTRACT
        evidence["quantization"]["method"] = {
            "case": "v5_production_fullchain",
            "manifest": "vivado/manifests/attention_mlp_production_v5_cohort16_sources.list",
            "attention_format_id": "0x48384103",
            "mlp_full_format_id": "0x48384605",
            "layers": 32, "max_context": 128, "cohort_rows": 16,
            "attention_weight_bits": 8, "mlp_weight_bits": 4,
            "activation_bits": 8, "kv_bits": 12,
            "host_residual_rmsnorm": "FP32", "lm_head": "FP32 host",
            "strict_total_shift": True, "total_shift_policy": "strict_rtl",
            "software_reference_not_hardware": False,
            "node_trace_layers": [], "mlp_total_shift_range": [12, 44],
            "mlp_group_guard_compute_width": 45,
            "mlp_gate_up_accumulator_compute_width": 44,
            "mlp_down_accumulator_compute_width": 54,
            "mlp_down_output_width": 32,
        }
        counter_names = (
            "activation_elements", "fp_to_fixed_saturation",
            "hadamard_saturation", "activation_scale_format_error",
            "linear_total_shift_format_error", "linear_group_guard_overflow_s37",
            "linear_software_group_guard_overflow", "linear_accumulator_overflow",
            "linear_software_accumulator_overflow", "linear_output_saturation",
            "rope_output_saturation", "kv12_clip", "qk_score_clip",
            "pv_output_saturation", "swiglu_output_overflow",
        )
        counters = {name: 0 for name in counter_names}
        counters["activation_elements"] = 1
        linear = {}
        for layer in range(32):
            for scope, ops in (
                ("self_attn", ("q_proj", "k_proj", "v_proj", "o_proj")),
                ("mlp", ("gate_proj", "up_proj", "down_proj")),
            ):
                for op in ops:
                    linear[f"model.layers.{layer}.{scope}.{op}.weight"] = {
                        "linear_group_guard_overflow_s37": 0,
                        "linear_software_group_guard_overflow": 0,
                        "linear_accumulator_overflow": 0,
                        "linear_software_accumulator_overflow": 0,
                        "linear_output_saturation": 0,
                        "linear_total_shift_min": 12 if op == "down_proj" else 20,
                        "linear_total_shift_max": 44,
                    }
        evidence["audit"] = {"counters": counters, "linear": linear}
        hardware_root = Path(__file__).resolve().parents[1]
        software_root = hardware_root.parent / "software" / "0_Software"
        source_paths = (
            hardware_root / "model" / "generate_scalellm_workload_reference.py",
            hardware_root / "model" / "freeze_scalellm_workload.py",
            software_root / "FPtoQ" / "experiment" / "v5_fullchain.py",
            hardware_root / "model" / "export_scalellm_llama31_artifacts.py",
            hardware_root / "model" / "fixbit_v2.py",
        )
        evidence["source_files"] = [
            {"path": str(source.resolve(strict=True)),
             "size": source.stat().st_size, "sha256": sha256_file(source)}
            for source in source_paths
        ]
        raw["reference"]["software_id"] = CURRENT_REFERENCE_ID
        raw["reference"]["profile"] = CURRENT_PROFILE
        raw["reference"]["evidence"] = self._record(
            evidence_path, (json.dumps(evidence, sort_keys=True) + "\n").encode("ascii")
        )
        path.write_text(json.dumps(raw), encoding="ascii")
        return path

    def _rewrite_current_evidence(self, path, mutate):
        raw = json.loads(path.read_text(encoding="ascii"))
        evidence_path = self.root / "reference.json"
        evidence = json.loads(evidence_path.read_text(encoding="ascii"))
        mutate(evidence)
        raw["reference"]["evidence"] = self._record(
            evidence_path, (json.dumps(evidence, sort_keys=True) + "\n").encode("ascii")
        )
        path.write_text(json.dumps(raw), encoding="ascii")

    def test_current_workload_uses_exact_profile_and_approved_source_closure(self):
        self.assertEqual(CURRENT_NUMERIC_CONTRACT,
                         EXPECTED_CURRENT_NUMERIC_CONTRACT)
        path = self._current_workload_manifest()
        workload = FrozenWorkload.load(path)
        self.assertEqual(workload.profile, CURRENT_PROFILE)
        self.assertEqual(workload.reference.profile, CURRENT_PROFILE)
        self.assertEqual(workload.reference.software_id, CURRENT_REFERENCE_ID)
        self.assertEqual(workload.valid_tokens, 32)
        self.assertEqual(workload.identity()["profile"], CURRENT_PROFILE)
        self.assertEqual(workload.identity()["reference"]["profile"], CURRENT_PROFILE)
        with self.assertRaisesRegex(RuntimeContractError,
                                    "historical workload reference profile/ID"):
            FrozenWorkload.load(path, profile=LEGACY_PROFILE)

    def test_current_reference_fixture_passes_full_numeric_source_validator(self):
        path = self._current_workload_manifest()
        raw = json.loads(path.read_text(encoding="ascii"))
        ref = raw["reference"]
        reference = WorkloadReference(
            ref["software_id"], ref["quantization"], ref["metric"],
            ref["expected_mean_nll"], ref["absolute_tolerance"], ref["seed"],
            FrozenFile.parse(ref["evidence"], path.parent, "reference evidence"),
            CURRENT_PROFILE,
        )
        dataset = FrozenFile.parse(raw["dataset"], path.parent, "dataset")
        samples = tuple(WorkloadSample(
            item["sample_id"], tuple(item["input_token_ids"]),
            tuple(item["target_token_ids"]), item["valid_tokens"],
        ) for item in raw["samples"])
        _validate_current_reference_evidence(
            reference, raw["checkpoint_sha256"], dataset, samples
        )

    def test_historical_workload_requires_explicit_legacy_profile(self):
        path = self._workload_manifest()
        with self.assertRaisesRegex(RuntimeContractError,
                                    "workload reference fields mismatch"):
            FrozenWorkload.load(path)
        workload = FrozenWorkload.load(path, profile=LEGACY_PROFILE)
        self.assertEqual(workload.profile, LEGACY_PROFILE)
        self.assertEqual(workload.reference.software_id, SOFTWARE_REFERENCE_ID)
        self.assertEqual(workload.reference.profile, LEGACY_PROFILE)
        self.assertEqual(workload.identity()["profile"], LEGACY_PROFILE)

    def test_public_workload_load_rejects_mixed_reference_profiles_and_ids(self):
        cases = (
            (CURRENT_PROFILE, "profile", LEGACY_PROFILE,
             "current workload reference profile/ID"),
            (CURRENT_PROFILE, "software_id", SOFTWARE_REFERENCE_ID,
             "current workload reference profile/ID"),
            (LEGACY_PROFILE, "profile", CURRENT_PROFILE,
             "historical workload reference profile/ID"),
            (LEGACY_PROFILE, "software_id", CURRENT_REFERENCE_ID,
             "historical workload reference profile/ID"),
        )
        for profile, key, value, message in cases:
            with self.subTest(profile=profile, field=key):
                path = (self._current_workload_manifest() if profile == CURRENT_PROFILE
                        else self._workload_manifest())
                raw = json.loads(path.read_text(encoding="ascii"))
                raw["reference"][key] = value
                path.write_text(json.dumps(raw), encoding="ascii")
                with self.assertRaisesRegex(RuntimeContractError, message):
                    FrozenWorkload.load(path, profile=profile)

        path = self._current_workload_manifest()
        self._rewrite_current_evidence(path, lambda evidence: evidence.__setitem__(
            "profile", LEGACY_PROFILE
        ))
        with self.assertRaisesRegex(RuntimeContractError,
                                    "current software reference identity mismatch"):
            FrozenWorkload.load(path)

    def test_current_workload_rejects_numeric_descriptor_and_method_drift(self):
        descriptors = (
            ("hadamard_inverse_sqrt32_q16", 11584),
            ("activation_quantizer", "symmetric_per_token_preclip8"),
            ("activation_scale_rounding", "half_away"),
            ("scalecode_division_rounding", "half_away"),
            ("folded_weight_rounding", "nearest_even"),
            ("swiglu", "unsigned_packed_s24"),
            ("attention", "qk_softmax_without_clamps"),
        )
        for key, value in descriptors:
            with self.subTest(descriptor=key):
                path = self._current_workload_manifest()
                self._rewrite_current_evidence(path, lambda evidence: evidence[
                    "quantization"]["fixedpoint"].__setitem__(key, value))
                with self.assertRaisesRegex(RuntimeContractError,
                                            "numerical descriptor mismatch"):
                    FrozenWorkload.load(path)
        for stage, key, value in (
            ("gate_up", "accumulator_width", 46),
            ("down", "total_shift_range", [20, 44]),
            ("down", "group_guard_width", 37),
        ):
            with self.subTest(stage=stage, descriptor=key):
                path = self._current_workload_manifest()
                self._rewrite_current_evidence(path, lambda evidence: evidence[
                    "quantization"]["fixedpoint"][stage].__setitem__(key, value))
                with self.assertRaisesRegex(RuntimeContractError,
                                            "numerical descriptor mismatch"):
                    FrozenWorkload.load(path)
        for key, value in (
            ("strict_total_shift", False),
            ("software_reference_not_hardware", True),
            ("mlp_down_output_width", 24),
            ("mlp_total_shift_range", [20, 44]),
        ):
            with self.subTest(method=key):
                path = self._current_workload_manifest()
                self._rewrite_current_evidence(path, lambda evidence: evidence[
                    "quantization"]["method"].__setitem__(key, value))
                with self.assertRaisesRegex(RuntimeContractError,
                                            "not the exact V5 fullchain method"):
                    FrozenWorkload.load(path)

    def test_current_reference_rejects_schema_numeric_audit_and_source_drift(self):
        mutations = (
            ("schema", lambda evidence: evidence.__setitem__(
                "schema", SOFTWARE_REFERENCE_SCHEMA),
             "current software reference identity mismatch"),
            ("down_width", lambda evidence: evidence["quantization"][
                "fixedpoint"]["down"].__setitem__("output_width", 24),
             "current reference numerical descriptor mismatch"),
            ("linear_coverage", lambda evidence: evidence["audit"][
                "linear"].pop("model.layers.31.mlp.down_proj.weight"),
             "current reference linear audit coverage is not 224"),
            ("golden_hash", lambda evidence: evidence["source_files"][2]
             .__setitem__("sha256", "0" * 64),
             "current reference golden SHA256 is not approved"),
        )
        for label, mutate, message in mutations:
            with self.subTest(label=label):
                path = self._current_workload_manifest()
                self._rewrite_current_evidence(path, mutate)
                with self.assertRaisesRegex(RuntimeContractError, message):
                    FrozenWorkload.load(path)

    def test_current_reference_rejects_old_artifact_abi_even_when_rehashed(self):
        path = self._current_workload_manifest()
        raw = json.loads(path.read_text(encoding="ascii"))
        evidence_path = self.root / "reference.json"
        evidence = json.loads(evidence_path.read_text(encoding="ascii"))
        artifact_path = self.root / "scalecode_manifest.json"
        artifact = json.loads(artifact_path.read_text(encoding="ascii"))
        artifact["mlp_abi"] = 0x0004_0003
        evidence["artifact_manifest"] = self._record(
            artifact_path, json.dumps(artifact).encode("ascii")
        )
        raw["reference"]["evidence"] = self._record(
            evidence_path, (json.dumps(evidence, sort_keys=True) + "\n").encode("ascii")
        )
        path.write_text(json.dumps(raw), encoding="ascii")
        with self.assertRaisesRegex(RuntimeContractError,
                                    "current reference artifact format/model mismatch"):
            FrozenWorkload.load(path)

    def test_run_board_rejects_mixed_profiles_before_model_or_transport(self):
        args = SimpleNamespace(
            board_report_dir=self.root, board_audit_dir=self.root,
            program_report_dir=self.root, artifact_manifest=self.root,
            workload_manifest=self.root,
        )
        for mismatch in ("board", "audit", "programming", "workload"):
            with self.subTest(mismatch=mismatch):
                items = {
                    name: SimpleNamespace(profile=(
                        LEGACY_PROFILE if name == mismatch else CURRENT_PROFILE
                    )) for name in ("board", "audit", "programming", "workload")
                }
                with mock.patch("host.scalellm_board.BoardBuildEvidence.load",
                                return_value=items["board"]) as board_load, \
                        mock.patch("host.scalellm_board.BoardAuditEvidence.load",
                                   return_value=items["audit"]), \
                        mock.patch("host.scalellm_board.BoardProgrammingEvidence.load",
                                   return_value=items["programming"]), \
                        mock.patch("host.scalellm_board.ScaleCodeArtifactManifest.load",
                                   return_value=SimpleNamespace()), \
                        mock.patch("host.scalellm_board.FrozenWorkload.load",
                                   return_value=items["workload"]) as workload_load, \
                        mock.patch("host.scalellm_board.Llama31HostModel",
                                   side_effect=AssertionError("model initialized")):
                    with self.assertRaisesRegex(RuntimeContractError,
                                                "mixed or legacy profiles"):
                        run_board(args)
                board_load.assert_called_once_with(self.root,
                                                   profile=CURRENT_PROFILE)
                workload_load.assert_called_once_with(self.root,
                                                       profile=CURRENT_PROFILE)

    def test_current_programming_refuses_missing_bitstream_bound_receipt(self):
        current = SimpleNamespace(profile=CURRENT_PROFILE)
        with self.assertRaisesRegex(RuntimeContractError,
                                    "future bitstream-bound receipt"):
            BoardProgrammingEvidence.load(self.root, current, current)

    def test_run_board_rejects_old_layout_before_any_ddr_transfer(self):
        from host.scalellm_hardware import (
            ATTENTION_ABI, ATTENTION_FORMAT_ID, MLP_ABI, MLP_FORMAT_ID)
        package = SimpleNamespace(profile=CURRENT_PROFILE, as_dict=lambda: {})
        manifest_path = self._current_write(self.root / "manifest.json", "{}\n")
        artifacts = SimpleNamespace(model_id=TARGET_MODEL_ID,
                                    checkpoint_sha256="a" * 64,
                                    manifest_path=manifest_path)
        workload = SimpleNamespace(profile=CURRENT_PROFILE, model_id=TARGET_MODEL_ID,
                                   checkpoint_sha256="a" * 64,
                                   tokenizer_files=(), identity=lambda: {})
        model = SimpleNamespace(checkpoint=SimpleNamespace(tokenizer_paths=()),
                                checkpoint_identity={})
        session = mock.MagicMock()
        session.__enter__.return_value = session
        registers = {0x000: ATTENTION_FORMAT_ID, 0x004: ATTENTION_ABI,
                     0x100: MLP_FORMAT_ID, 0x104: MLP_ABI, 0x2B8: 0}
        session.read32.side_effect = lambda offset: registers.get(offset, 0)
        args = SimpleNamespace(
            board_report_dir="unused", board_audit_dir="unused",
            program_report_dir="unused", artifact_manifest="unused",
            workload_manifest="unused", model_dir="unused", lm_head_chunk_rows=1,
            power_input="unused", power_source_label="unused", power_scale_to_watts=1,
            power_sample_interval_s=1, output_dir=self.root / "old_layout_run",
            h2c="unused", c2h="unused", user="unused", event="none",
            metadata_chunk_bytes=4096, command_timeout_s=1, poll_interval_s=0)
        with mock.patch("host.scalellm_board.BoardBuildEvidence.load", return_value=package), \
             mock.patch("host.scalellm_board.BoardAuditEvidence.load", return_value=package), \
             mock.patch("host.scalellm_board.BoardProgrammingEvidence.load", return_value=package), \
             mock.patch("host.scalellm_board.ScaleCodeArtifactManifest.load", return_value=artifacts), \
             mock.patch("host.scalellm_board.FrozenWorkload.load", return_value=workload), \
             mock.patch("host.scalellm_board.Llama31HostModel", return_value=model), \
             mock.patch("host.scalellm_board.FilePowerSampler"), \
             mock.patch("host.scalellm_board.XdmaSession", return_value=session), \
             mock.patch("host.scalellm_board.preload_all_matrices") as preload:
            with self.assertRaisesRegex(RuntimeContractError, "0x2b8 identity mismatch"):
                run_board(args)
        preload.assert_not_called()
        session.write32.assert_not_called()
        session.h2c_write_local.assert_not_called()
        session.c2h_read_local.assert_not_called()

    def test_current_bitstream_and_reopened_audit_chain_is_accepted(self):
        fixture = self._current_package_fixture()
        board = BoardBuildEvidence.load(fixture.bitgen, profile=CURRENT_PROFILE)
        self.assertEqual(board.profile, CURRENT_PROFILE)
        self.assertEqual(board.rtl_variant, "FORMAT05_CURRENT")
        self.assertEqual(board.wns_ns, 0.125)
        audit = BoardAuditEvidence.load(fixture.audit, board)
        self.assertEqual(audit.profile, CURRENT_PROFILE)
        self.assertEqual(audit.bitstream_sha256, board.bitstream_sha256)
        self.assertEqual(audit.checkpoint_sha256, board.checkpoint_sha256)

    def test_current_bitstream_identity_drift_is_refused(self):
        fixture = self._current_package_fixture()
        raw = json.loads(fixture.evidence.read_text(encoding="utf-8"))
        raw["abi"] = "0x00040003"
        fixture.evidence.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeContractError,
                                    "bitstream evidence identity/status"):
            BoardBuildEvidence.load(fixture.bitgen, profile=CURRENT_PROFILE)

    def test_current_reopened_negative_timing_is_refused(self):
        fixture = self._current_package_fixture()
        fixture.timing.write_text(
            fixture.timing.read_text(encoding="utf-8").replace(
                "0.125 0.000", "-0.001 0.000"), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeContractError, "timing is not closed"):
            _current_parse_physical(fixture.audit, final=False)

    def test_workload_requires_hashed_unpadded_even_cohorts(self):
        path = self._workload_manifest()
        workload = FrozenWorkload.load(path, profile=LEGACY_PROFILE)
        self.assertEqual(workload.valid_tokens, 32)
        self.assertEqual(len(workload.samples), 2)
        raw = json.loads(path.read_text())
        raw["samples"][0]["valid_tokens"] = 15
        path.write_text(json.dumps(raw), encoding="ascii")
        with self.assertRaisesRegex(RuntimeContractError, "forbids padded"):
            FrozenWorkload.load(path, profile=LEGACY_PROFILE)

    def test_workload_rejects_base_model_identity(self):
        path = self._workload_manifest()
        raw = json.loads(path.read_text(encoding="ascii"))
        raw["model_id"] = "meta-llama/Llama-3.1-8B"
        path.write_text(json.dumps(raw), encoding="ascii")
        with self.assertRaisesRegex(RuntimeContractError, "workload model_id"):
            FrozenWorkload.load(path, profile=LEGACY_PROFILE)

    def test_reference_rejects_base_artifact_identity_even_when_rehashed(self):
        path = self._workload_manifest()
        raw = json.loads(path.read_text(encoding="ascii"))
        evidence_path = self.root / "reference.json"
        evidence = json.loads(evidence_path.read_text(encoding="ascii"))
        artifact_path = self.root / "scalecode_manifest.json"
        artifact = json.loads(artifact_path.read_text(encoding="ascii"))
        artifact["model_id"] = "meta-llama/Llama-3.1-8B"
        artifact_payload = json.dumps(artifact).encode("ascii")
        evidence["artifact_manifest"] = self._record(artifact_path, artifact_payload)
        evidence_payload = (json.dumps(evidence, sort_keys=True) + "\n").encode("ascii")
        raw["reference"]["evidence"] = self._record(evidence_path, evidence_payload)
        path.write_text(json.dumps(raw), encoding="ascii")
        with self.assertRaisesRegex(RuntimeContractError, "artifact manifest identity mismatch"):
            FrozenWorkload.load(path, profile=LEGACY_PROFILE)

    def test_workload_rejects_mutated_reference_evidence(self):
        path = self._workload_manifest()
        FrozenWorkload.load(path, profile=LEGACY_PROFILE)
        reference = self.root / "reference.json"
        payload = reference.read_bytes()
        reference.write_bytes(bytes([payload[0] ^ 1]) + payload[1:])
        with self.assertRaisesRegex(RuntimeContractError, "SHA256 mismatch"):
            FrozenWorkload.load(path, profile=LEGACY_PROFILE)

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
            FrozenWorkload.load(path, profile=LEGACY_PROFILE)

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
        # The legacy parser tests hash/identity semantics using a complete
        # synthetic package, independent of which historical scripts migrated.
        legacy_hardware = self.root / "legacy_hardware"
        legacy_module = legacy_hardware / "host/scalellm_board.py"
        patcher = mock.patch("host.scalellm_board.__file__", str(legacy_module))
        patcher.start()
        self.addCleanup(patcher.stop)
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
        evidence = BoardBuildEvidence.load(report, profile=LEGACY_PROFILE)
        self.assertEqual(evidence.rtl_variant, BOARD_RTL_VARIANT)
        self.assertEqual(evidence.bitstream_sha256, bit_hash)
        self.assertGreaterEqual(evidence.wns_ns, 0)
        (report / "summary.txt").write_text(
            summary_text.replace(BOARD_RTL_VARIANT, "P14_LEGACY"),
            encoding="ascii",
        )
        write_output_manifest()
        with self.assertRaisesRegex(RuntimeContractError, "not the frozen"):
            BoardBuildEvidence.load(report, profile=LEGACY_PROFILE)
        (report / "summary.txt").write_text(summary_text, encoding="ascii")
        write_output_manifest()
        region2_payload = p16_region2_summary.read_bytes()
        p16_region2_summary.write_bytes(region2_payload + b"drift=1\n")
        with self.assertRaisesRegex(RuntimeContractError, "lineage SHA256"):
            BoardBuildEvidence.load(report, profile=LEGACY_PROFILE)
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
            BoardBuildEvidence.load(report, profile=LEGACY_PROFILE)
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
        project = legacy_hardware
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
        scripts.mkdir(parents=True)
        for path in audit_inputs:
            if path.is_relative_to(scripts):
                path.write_text("# synthetic legacy identity fixture\n", encoding="ascii")
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
        for path in program_inputs:
            if path.is_relative_to(scripts):
                path.write_text("# synthetic programming identity fixture\n", encoding="ascii")
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
            BoardBuildEvidence.load(report, profile=LEGACY_PROFILE)
        (report / "summary.txt").write_text(summary_text, encoding="ascii")
        write_output_manifest()
        (report / "attention_mlp_vcu118_v5.bit").write_text(
            "mutated\n", encoding="ascii"
        )
        with self.assertRaisesRegex(RuntimeContractError, "SHA256 mismatch"):
            BoardBuildEvidence.load(report, profile=LEGACY_PROFILE)

    def test_three_run_executor_uses_32_layers_unique_ids_and_stable_result(self):
        manifest_path = self._workload_manifest()
        workload = FrozenWorkload.load(manifest_path, profile=LEGACY_PROFILE)
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
        workload = FrozenWorkload.load(self._workload_manifest(),
                                       profile=LEGACY_PROFILE)
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
