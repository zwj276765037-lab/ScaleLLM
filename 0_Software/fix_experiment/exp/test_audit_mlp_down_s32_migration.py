"""Mutation tests of static migration checks, never of the live hardware tree."""

import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("audit_mlp_down_s32_migration.py")
SPEC = importlib.util.spec_from_file_location("migration_audit", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class MigrationAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = audit.build_report(audit.WORKSPACE)
        cls.paths = {Path(source) for row in cls.baseline["checks"] for source in row["sources"]}
        hap = audit.WORKSPACE / audit.HAP_REL
        manifests = []
        cls.paths.update(hap / path for path in audit.manifest_closure(
            hap, audit.PRODUCTION_MANIFEST, manifests))
        cls.paths.update(hap / path for path in manifests)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name)
        for source in self.paths:
            destination = self.workspace / source.relative_to(audit.WORKSPACE)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    def mutate(self, relative, old, new):
        path = self.workspace / audit.HAP_REL / relative
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new))

    def require_failed(self, check_id):
        report = audit.build_report(self.workspace)
        self.assertEqual(report["status"], "migration_incomplete")
        checks = {row["check_id"]: row["pass"] for row in report["checks"]}
        self.assertFalse(checks[check_id])

    def test_current_static_contract_and_scope(self):
        self.assertEqual(self.baseline["status"], "static_contract_pass")
        self.assertFalse(self.baseline["board_signoff"])
        self.assertFalse(self.baseline["model_and_reference_identity_verified"])
        self.assertEqual(self.baseline["target_format"]["format_id"], "0x48384605")

    def test_old_format_rejected(self):
        self.mutate("host/scalellm_hardware.py", "MLP_FORMAT_ID = 0x4838_4605",
                    "MLP_FORMAT_ID = 0x4838_4604")
        self.require_failed("format_id_v5_synchronized")

    def test_down_minimum_shift_rejected(self):
        self.mutate("rtl/mlp/hap_mlp_pkg.sv", "MLP_DOWN_TOTAL_SHIFT_MIN = 12",
                    "MLP_DOWN_TOTAL_SHIFT_MIN = 20")
        self.require_failed("final_v5_ranges_and_guards")

    def test_s55_overflow_check_required(self):
        self.mutate("rtl/mlp/hap_mlp_down_group_major_accum_s54.sv",
                    "lane_sum_ext[54] != lane_sum_ext[53]", "1'b0")
        self.require_failed("down_s54_s55_overflow")

    def test_unsigned_gate_rejected(self):
        self.mutate("rtl/mlp/hap_mlp_silu_mul.sv", "input  wire signed [23:0]   gate_s24",
                    "input  wire        [23:0]   gate_s24")
        self.require_failed("swiglu_signed_s24_to_s32")

    def test_old_dma_beat_count_rejected(self):
        self.mutate("rtl/integration/hap_mlp_tensor_dma_bridge.sv", "OUTPUT_TILES*32",
                    "OUTPUT_TILES*24")
        self.require_failed("tensor_dma_s32_payload")

    def test_central_output_bus_rejected(self):
        self.mutate("rtl/integration/hap_attention_mlp_production_core.sv",
                    "wire[255:0]mlp_out_data", "wire[8191:0]mlp_out_data")
        self.require_failed("production_core_s32")

    def test_old_output_size_rejected(self):
        self.mutate("host/scalellm_memory.py", "ACTIVATION_OUTPUT_ELEMENT_BYTES = 4",
                    "ACTIVATION_OUTPUT_ELEMENT_BYTES = 3")
        self.require_failed("host_s32_output_boundary")

    def test_missing_manifest_source_rejected(self):
        self.mutate("vivado/manifests/attention_mlp_resource_top_v5_sources.list",
                    "rtl/mlp/hap_mlp_down_pair_join_stream256.sv", "")
        self.require_failed("production_source_closure")

    def test_wrong_telemetry_register_rejected(self):
        self.mutate("host/scalellm_hardware.py", "MLP_DOWN_SATURATION_COUNT = 0x2AC",
                    "MLP_DOWN_SATURATION_COUNT = 0x2A8")
        self.require_failed("down_s32_saturation_telemetry")


if __name__ == "__main__":
    unittest.main()
