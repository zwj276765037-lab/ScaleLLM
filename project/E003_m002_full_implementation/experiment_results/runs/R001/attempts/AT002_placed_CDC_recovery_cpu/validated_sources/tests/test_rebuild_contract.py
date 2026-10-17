#!/usr/bin/env python3
"""Independent finite contract vectors for the format05 rebuild.

The numerical authority is v5_fullchain.py SHA256
58a6bb7c769209925bd3bcd9d1a06414b0a25415a46591f70d8efd62db0b9898,
selected with down_shift12_candidate=True and down_output_width=32 as
specified in source/design.md. These tests do not qualify RTL without XSim.
"""

import ast
import hashlib
import unittest
from pathlib import Path
import tempfile

import numpy as np

from host.scalellm_artifacts import MANIFEST_SCHEMA_VERSION, MODEL_ID as ARTIFACT_MODEL_ID
from host.scalellm_hardware import (
    ATTENTION_ABI,
    ATTENTION_FORMAT_ID,
    MLP_ABI,
    MLP_ABORT_STATUS,
    MLP_COMPLETION_ACK,
    MLP_CONTROL,
    MLP_DMA_STATUS,
    MLP_FORMAT_ID,
    MLP_NUMERIC_STATUS,
    MLP_PAIRED_STATUS,
    MLP_TENSOR_INPUT_BEATS,
    MLP_TENSOR_INPUT_GROUPS,
    MLP_TENSOR_OUTPUT_BEATS,
    MLP_TENSOR_OUTPUT_TILES,
    HardwareResetRequired,
    ScaleLLMHardwareBackend,
)
from host.scalellm_hostops import (
    PinnedActivationPool,
    pack_mlp_input_s24_q16,
    unpack_mlp_output_s32_q16,
)
from host.scalellm_runtime import RuntimeContractError
from model.export_scalellm_llama31_artifacts import (
    MODEL_ID as EXPORT_MODEL_ID,
    SCHEMA_VERSION as EXPORT_SCHEMA_VERSION,
)
from model import generate_scalellm_workload_reference as reference_generator
from model.fixbit_v2 import score_finalize_s20, softmax_row_u16
from model.mlp_fixed import (
    a8w4_two_column_packed,
    hadamard32_product_normalized,
    minmax_a8_quantize_s35,
    mlp_recover_down_guard_s45,
    mlp_recover_guard_s37,
    round_shift_away_zero,
)
from tests.test_scalellm_hardware import FakeRegisterTransport, FakeStager
from vivado.scripts.check_rebuild_static import (
    BOARD_CLOCK_MODULES,
    ContractError,
    DEFAULT_MANIFEST,
    ROOT,
    board_clock_attributes,
    clock_periods,
    expand_manifest,
    module_names,
    port_width,
    py_string_constant,
    sv_tokens,
)


ROWS = 16
COLS = 4096
GROUP = 32
RAW_DOT = GROUP
CODE_PRODUCT = 100 * 141
RAW_PRODUCT = RAW_DOT * CODE_PRODUCT


def signed_limit(value, width):
    low = -(1 << (width - 1))
    high = (1 << (width - 1)) - 1
    return min(high, max(low, value))


def final_half_away(accumulator):
    magnitude = (abs(accumulator) + 128) // 256
    return magnitude if accumulator >= 0 else -magnitude


def recover(raw, shift):
    return raw * (1 << (24 - shift)) if shift < 24 else raw // (1 << (shift - 24))


def rne_div(numerator, denominator):
    quotient, remainder = divmod(numerator, denominator)
    if 2 * remainder > denominator or (2 * remainder == denominator and quotient % 2):
        quotient += 1
    return quotient


def signed24(raw):
    value = raw & 0xFFFFFF
    return value - 0x1000000 if value & 0x800000 else value


class CaptureSession:
    def __init__(self):
        self.payload = b""
        self.writes = []
        self.reads = []
        self.read_payload = b""

    def h2c_write_local(self, channel, data, local_offset, chunk_bytes):
        self.payload = bytes(data)
        self.writes.append((channel, local_offset, chunk_bytes, len(data)))
        return len(data)

    def c2h_read_into_local(self, channel, destination, local_offset, chunk_bytes):
        if len(self.read_payload) != len(destination):
            raise AssertionError("fixture C2H size mismatch")
        destination[:] = self.read_payload
        self.reads.append((channel, local_offset, chunk_bytes, len(destination)))
        return len(destination)


class IntegerContractTests(unittest.TestCase):
    def test_nonzero_gate_and_down_recovery_is_not_s24_clipped(self):
        self.assertEqual(RAW_PRODUCT, 451_200)
        gate_guard = recover(RAW_PRODUCT, 20)
        down_guard = recover(RAW_PRODUCT, 12)
        self.assertEqual(gate_guard, 7_219_200)
        self.assertEqual(down_guard, 1_848_115_200)
        self.assertEqual(mlp_recover_guard_s37(RAW_PRODUCT, 20), gate_guard)
        self.assertEqual(mlp_recover_down_guard_s45(RAW_PRODUCT, 12), down_guard)
        self.assertEqual(final_half_away(2 * gate_guard), 56_400)
        self.assertEqual(final_half_away(2 * down_guard), 14_438_400)
        self.assertEqual(final_half_away(-2 * down_guard), -14_438_400)
        self.assertGreater(14_438_400, (1 << 23) - 1)
        self.assertLess(14_438_400, (1 << 31) - 1)

    def test_down_legal_shift_edges_and_illegal_active_shifts(self):
        for shift in (12, 13, 19, 20, 24, 44):
            with self.subTest(shift=shift):
                self.assertEqual(
                    mlp_recover_down_guard_s45(RAW_PRODUCT, shift),
                    recover(RAW_PRODUCT, shift),
                )
                self.assertEqual(
                    mlp_recover_down_guard_s45(-RAW_PRODUCT, shift),
                    recover(-RAW_PRODUCT, shift),
                )
        for shift in (11, 45):
            with self.subTest(shift=shift):
                with self.assertRaises(ValueError):
                    mlp_recover_down_guard_s45(RAW_PRODUCT, shift)
        for shift in (19, 45):
            with self.subTest(gate_shift=shift):
                with self.assertRaises(ValueError):
                    mlp_recover_guard_s37(RAW_PRODUCT, shift)

    def test_signed_products_and_distinct_rounding_rules(self):
        for activation, w0, w1 in ((1, 1, -1), (-255, -8, 7), (255, 7, -8)):
            with self.subTest(activation=activation, weights=(w0, w1)):
                self.assertEqual(
                    a8w4_two_column_packed(activation, w0, w1),
                    (activation * w0, activation * w1),
                )
        self.assertEqual((rne_div(765, 10), final_half_away(128)), (76, 1))
        self.assertEqual((rne_div(775, 10), final_half_away(-128)), (78, -1))
        self.assertEqual(round_shift_away_zero(128, 8), 1)
        self.assertEqual(round_shift_away_zero(-128, 8), -1)
        self.assertEqual(final_half_away(-(1 << 53)), -(1 << 45))
        self.assertEqual(signed_limit((1 << 31), 32), (1 << 31) - 1)
        self.assertEqual(signed_limit(-(1 << 31) - 1, 32), -(1 << 31))

    def test_legal_group_extreme_fits_guards_and_accumulators_but_not_s32(self):
        raw = 32 * 255 * 8 * 255 * 255
        self.assertEqual(raw, 4_244_832_000)
        self.assertLess(raw, 1 << 32)
        gate_guard = raw << (24 - 20)
        down_guard = raw << (24 - 12)
        self.assertEqual(gate_guard, 67_917_312_000)
        self.assertEqual(down_guard, 17_386_831_872_000)
        self.assertLess(gate_guard, 1 << 36)
        self.assertLess(down_guard, 1 << 44)
        self.assertLess(gate_guard * 128, 1 << 43)
        self.assertLess(down_guard * 448, 1 << 53)
        rounded_down = final_half_away(down_guard * 448)
        self.assertGreater(rounded_down, (1 << 31) - 1)
        self.assertEqual(signed_limit(rounded_down, 32), (1 << 31) - 1)

    def test_hadamard_raw_minmax_zero_and_tie_even(self):
        impulse = hadamard32_product_normalized([1 << 16] + [0] * 31)
        self.assertEqual(impulse.values, (11_585,) * 32)
        self.assertEqual(impulse.saturation_count, 0)
        self.assertEqual(minmax_a8_quantize_s35([0] * 32).metadata, 0)

        positive = minmax_a8_quantize_s35([0, 3, 10] + [0] * 29)
        self.assertEqual((positive.clip_low, positive.clip_high), (0, 10))
        self.assertEqual(positive.zero_point, 0)
        self.assertEqual(positive.values[1], 76)  # 76.5 ties to even.
        negative = minmax_a8_quantize_s35([-10, -3] + [-1] * 30)
        self.assertEqual((negative.clip_low, negative.clip_high), (-10, 0))
        self.assertEqual(negative.zero_point, 255)
        self.assertEqual(negative.values[0], 0)
        self.assertEqual(negative.values[1], 178)  # 178.5 ties to even.
        mixed = minmax_a8_quantize_s35([-10, 0, 10] + [0] * 29)
        self.assertEqual((mixed.clip_low, mixed.clip_high), (-10, 10))
        self.assertEqual(mixed.values[:3], (0, 128, 255))

    def test_packed_s24_sign_extension_and_legitimate_saturation(self):
        self.assertEqual(
            tuple(signed24(word) for word in (0x000000, 0x7FFFFF, 0x800000, 0xFF10FF, 0xFFFFFF)),
            (0, 8_388_607, -8_388_608, -61_185, -1),
        )
        self.assertEqual(signed_limit(1 << 31, 32), (1 << 31) - 1)
        self.assertEqual(signed_limit(-(1 << 31) - 1, 32), -(1 << 31))


class HostBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.session = CaptureSession()
        self.pool = PinnedActivationPool(self.session, require_lock=False)

    def tearDown(self):
        self.pool.close()

    def test_before_mlp_is_group_major_and_attention_stays_row_major(self):
        raw = np.arange(ROWS * COLS, dtype=np.int32).reshape(ROWS, COLS)
        raw[2, 31] = -1
        raw[15, COLS - 1] = -(1 << 23)
        values = raw.astype(np.float32) / np.float32(1 << 16)
        self.pool.write(values, 0, 0, "before_mlp", 0)
        payload = self.session.payload
        self.assertEqual(len(payload), 128 * 48 * 32)
        self.assertEqual(len(payload) // 32, 6144)
        expected = bytearray(len(payload))
        for group in range(128):
            for row in range(ROWS):
                for lane in range(GROUP):
                    column = group * GROUP + lane
                    offset = ((group * ROWS + row) * GROUP + lane) * 3
                    expected[offset:offset + 3] = int(raw[row, column]).to_bytes(3, "little", signed=True)
        self.assertEqual(payload, bytes(expected))
        self.assertEqual(payload[96:99], int(raw[1, 0]).to_bytes(3, "little", signed=True))
        self.assertNotEqual(payload[96:99], int(raw[0, 32]).to_bytes(3, "little", signed=True))
        self.assertEqual(payload[285:288], b"\xff\xff\xff")
        self.assertEqual(payload[1536:1539], int(raw[0, 32]).to_bytes(3, "little", signed=True))
        self.assertEqual(payload[-3:], b"\x00\x00\x80")
        self.assertEqual(self.session.writes[-1][::3], (1, len(payload)))
        self.assertEqual(self.pool.transfers[-1].size, 6144 * 32)

        self.pool.write(values, 0, 0, "before_attention", 1)
        attention = self.session.payload
        self.assertEqual(attention[96:99], int(raw[0, 32]).to_bytes(3, "little", signed=True))
        self.assertEqual(attention[COLS * 3:COLS * 3 + 3], int(raw[1, 0]).to_bytes(3, "little", signed=True))
        self.assertEqual(self.pool.transfers[-1].stage, "before_attention")
        self.assertEqual(self.session.writes[-1][0], 0)

    def test_after_mlp_unpacks_tile_major_s32_with_high_bits(self):
        raw = np.arange(ROWS * COLS, dtype=np.int32).reshape(ROWS, COLS)
        raw[1, 0] = 14_438_400
        raw[1, 1] = -14_438_400
        raw[0, 16] = 9_830_400
        raw[15, COLS - 1] = -14_438_400
        payload = bytearray(256 * 32 * 32)
        for tile in range(256):
            for row in range(ROWS):
                for lane in range(16):
                    column = tile * 16 + lane
                    offset = ((tile * ROWS + row) * 16 + lane) * 4
                    payload[offset:offset + 4] = int(raw[row, column]).to_bytes(4, "little", signed=True)
        self.session.read_payload = bytes(payload)
        result = self.pool.read(0, 0, "after_mlp", 0)
        self.assertTrue(np.array_equal(result, raw.astype(np.float32) / np.float32(1 << 16)))
        self.assertEqual(len(payload) // 32, 8192)
        self.assertEqual(payload[64:68], (14_438_400).to_bytes(4, "little", signed=True))
        self.assertEqual(payload[68:72], (-14_438_400).to_bytes(4, "little", signed=True))
        self.assertEqual(payload[1024:1028], (9_830_400).to_bytes(4, "little", signed=True))
        self.assertEqual(payload[-4:], (-14_438_400).to_bytes(4, "little", signed=True))
        self.assertEqual(self.session.reads[-1][::3], (1, len(payload)))
        self.assertEqual(self.pool.transfers[-1].size, 8192 * 32)

    def test_unknown_stage_and_old_command_abi_fail_closed(self):
        with self.assertRaises(ValueError):
            self.pool.write(np.zeros((ROWS, COLS), dtype=np.float32), 0, 0, "before_unknown", 0)
        for offset, old_value in ((0x100, 0x4838_4603), (0x104, 0x0004_0003)):
            with self.subTest(offset=offset):
                transport = FakeRegisterTransport()
                transport.registers[offset] = old_value
                with self.assertRaises(RuntimeContractError):
                    ScaleLLMHardwareBackend(
                        transport, FakeStager(), poll_interval_s=0
                    ).initialize_shared_mode()


class HostFormalTests(unittest.TestCase):
    def test_generator_defaults_current_and_legacy_is_explicit(self):
        base = ["--dataset", "dataset.jsonl", "--model-dir", "checkpoint",
                "--artifact-manifest", "artifact.json", "--output-dir", "output"]
        current = reference_generator.build_parser().parse_args(base)
        self.assertEqual((current.reference_profile, current.dtype,
                          current.batch_size, current.cpu_threads,
                          current.fixedpoint_variant),
                         ("core100_ddr200_format05", "bfloat16", 2, 4, None))
        legacy = reference_generator.build_parser().parse_args(
            base + ["--reference-profile", "legacy_p16_fxp16_ddr300",
                    "--fixedpoint-variant", "FXP16-Q5.10"]
        )
        self.assertEqual((legacy.reference_profile, legacy.fixedpoint_variant),
                         ("legacy_p16_fxp16_ddr300", "FXP16-Q5.10"))

    def test_current_generator_binds_actual_golden_call_and_audit(self):
        root = Path(__file__).resolve().parents[1]
        generator = root / "model" / "generate_scalellm_workload_reference.py"
        golden = root.parent / "software" / "0_Software" / "FPtoQ" / "experiment" / "v5_fullchain.py"
        self.assertEqual(
            hashlib.sha256(golden.read_bytes()).hexdigest(),
            "58a6bb7c769209925bd3bcd9d1a06414b0a25415a46591f70d8efd62db0b9898",
        )
        module = ast.parse(generator.read_text(encoding="utf-8"))
        main = next(node for node in module.body
                    if isinstance(node, ast.FunctionDef) and node.name == "main")
        attachments = [node for node in ast.walk(main)
                       if isinstance(node, ast.Assign) and
                       isinstance(node.value, ast.Call) and
                       isinstance(node.value.func, ast.Name) and
                       node.value.func.id == "attach_current"]
        self.assertEqual(len(attachments), 1)
        assignment = attachments[0]
        self.assertEqual(
            [target.id for target in assignment.targets[0].elts],
            ["method", "audit"],
        )
        keywords = {item.arg: item.value for item in assignment.value.keywords}
        self.assertEqual(set(keywords), {
            "checkpoint_dir", "device", "strict_total_shift",
            "software_extended", "down_output_width", "down_shift12_candidate",
        })
        self.assertEqual((keywords["checkpoint_dir"].id, keywords["device"].id),
                         ("model_dir", "device"))
        for name, expected in (
            ("strict_total_shift", True), ("software_extended", False),
            ("down_output_width", 32), ("down_shift12_candidate", True),
        ):
            self.assertEqual(ast.literal_eval(keywords[name]), expected)
        validators = [node for node in ast.walk(main)
                      if isinstance(node, ast.Call) and
                      isinstance(node.func, ast.Name) and
                      node.func.id == "_validate_current_method"]
        self.assertEqual(len(validators), 1)
        self.assertEqual([arg.id for arg in validators[0].args],
                         ["method", "audit"])
        self.assertGreater(validators[0].lineno, assignment.lineno)

    def test_current_generator_numeric_helpers_match_approved_source_hashes(self):
        root = Path(__file__).resolve().parents[1]
        exporter = root / "model" / "export_scalellm_llama31_artifacts.py"
        fixbit = root / "model" / "fixbit_v2.py"
        tree = ast.parse(exporter.read_text(encoding="utf-8"))
        names = (
            "llama3_inv_freq", "round_away", "fwht32_normalized",
            "encode_scales", "quantize_folded_rows",
        )
        functions = {
            node.name: ast.dump(node, include_attributes=False)
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in names
        }
        self.assertEqual(set(functions), set(names))
        exporter_digest = hashlib.sha256(
            "\n".join(functions[name] for name in names).encode("utf-8")
        ).hexdigest()
        self.assertEqual(exporter_digest,
                         "a16d2b9f229ef1804e095243c96e62bae6cf0010efb6014609120a507372e196")
        self.assertEqual(hashlib.sha256(fixbit.read_bytes()).hexdigest(),
                         "fb4b34397edc9d14ed3ef4f0b46d60a61b545a52a7a47d15c2eec8ba7b6db271")
        self.assertEqual(reference_generator.APPROVED_EXPORTER_NUMERIC_AST_SHA256,
                         exporter_digest)
        self.assertEqual(reference_generator.APPROVED_FIXBIT_SHA256,
                         hashlib.sha256(fixbit.read_bytes()).hexdigest())

    def test_literal_instruct_schema_and_command_identities(self):
        self.assertEqual(
            (ARTIFACT_MODEL_ID, EXPORT_MODEL_ID),
            ("meta-llama/Llama-3.1-8B-Instruct",) * 2,
        )
        self.assertEqual((MANIFEST_SCHEMA_VERSION, EXPORT_SCHEMA_VERSION), (2, 2))
        self.assertEqual(
            (ATTENTION_FORMAT_ID, ATTENTION_ABI, MLP_FORMAT_ID, MLP_ABI),
            (0x4838_4103, 0x0002_0000, 0x4838_4605, 0x0005_0000),
        )
        self.assertEqual(
            (MLP_TENSOR_INPUT_BEATS, MLP_TENSOR_INPUT_GROUPS,
             MLP_TENSOR_OUTPUT_BEATS, MLP_TENSOR_OUTPUT_TILES),
            (6144, 128, 8192, 256),
        )

    def test_direct_mlp_wire_byte_offsets_without_roundtrip_oracle(self):
        raw = np.zeros((ROWS, COLS), dtype=np.int32)
        raw[0, 0] = 56_400
        raw[1, 0] = -56_400
        raw[0, 32] = -1
        raw[15, COLS - 1] = -(1 << 23)
        packed = pack_mlp_input_s24_q16(raw.astype(np.float32) / (1 << 16))
        self.assertEqual(len(packed), 6144 * 32)
        self.assertEqual(packed[0:3], (56_400).to_bytes(3, "little", signed=True))
        self.assertEqual(packed[96:99], (-56_400).to_bytes(3, "little", signed=True))
        self.assertEqual(packed[1536:1539], b"\xff\xff\xff")
        self.assertEqual(packed[-3:], b"\x00\x00\x80")
        self.assertEqual(packed[3:6], b"\x00\x00\x00")

        output = bytearray(8192 * 32)
        for offset, value in (
            (64, 14_438_400), (68, -14_438_400),
            (1024, 9_830_400), (len(output) - 4, -14_438_400),
        ):
            output[offset:offset + 4] = value.to_bytes(4, "little", signed=True)
        decoded = unpack_mlp_output_s32_q16(output)
        self.assertEqual(decoded.shape, (ROWS, COLS))
        self.assertEqual(decoded[1, 0], np.float32(14_438_400 / 65536))
        self.assertEqual(decoded[1, 1], np.float32(-14_438_400 / 65536))
        self.assertEqual(decoded[0, 16], np.float32(9_830_400 / 65536))
        self.assertEqual(decoded[15, COLS - 1], np.float32(-14_438_400 / 65536))
        self.assertEqual(decoded[0, 1], np.float32(0))

    def test_old_register_identities_refuse_before_shared_mode(self):
        for offset, old_value in (
            (0x000, 0x4838_4102),
            (0x004, 0x0001_0000),
            (0x100, 0x4838_4603),
            (0x100, 0x4838_4604),
            (0x104, 0x0004_0003),
        ):
            with self.subTest(offset=offset, old_value=old_value):
                transport = FakeRegisterTransport()
                transport.registers[offset] = old_value
                with self.assertRaisesRegex(RuntimeContractError, "identity mismatch"):
                    ScaleLLMHardwareBackend(
                        transport, FakeStager(), poll_interval_s=0
                    ).initialize_shared_mode()
                self.assertNotIn((0x108, 3), transport.writes)

    def test_unknown_numeric_status_requires_reset_without_clear_or_ack(self):
        transport = FakeRegisterTransport()
        backend = ScaleLLMHardwareBackend(
            transport, FakeStager(), timeout_s=0.05, poll_interval_s=0
        )
        backend.initialize_shared_mode()
        transport.mlp_counter_overrides[MLP_NUMERIC_STATUS] = 0x8
        transport.mlp_counter_overrides[MLP_DMA_STATUS] = 1
        transport.mlp_counter_overrides[MLP_PAIRED_STATUS] = 1 << 4
        from host.scalellm_runtime import CommandIdentity, Engine

        identity = CommandIdentity(73, 45, 0, 0, 0, 1)
        with self.assertRaisesRegex(HardwareResetRequired,
                                    r"(?i)reset[- ]required") as failure:
            backend.execute(Engine.MLP, identity)
        self.assertIn("unknown_numeric_status=0x00000008", str(failure.exception))
        self.assertNotIn((MLP_CONTROL, 1 << 1), transport.writes)
        self.assertEqual(transport.fault_maintenance_requests, 0)
        self.assertEqual(transport.fault_maintenance_accepted, 0)
        self.assertEqual(transport.maintenance_polls, 0)
        self.assertEqual(transport.registers.get(MLP_ABORT_STATUS, 0), 0)
        self.assertEqual(transport.registers[MLP_PAIRED_STATUS], 1 << 4)
        self.assertEqual(transport.registers[MLP_DMA_STATUS] & 1, 1)
        self.assertNotIn((MLP_COMPLETION_ACK, identity.command_id), transport.writes)
        self.assertEqual(transport.registers[0x29C], 1)
        self.assertEqual(len(backend.telemetry), 1)
        self.assertEqual(backend.telemetry[-1].counters["numeric_status"], 0x8)

    def test_short_activation_transfers_refuse_without_success_trace(self):
        class ShortSession(CaptureSession):
            def h2c_write_local(self, channel, data, local_offset, chunk_bytes):
                super().h2c_write_local(channel, data, local_offset, chunk_bytes)
                return len(data) - 1

            def c2h_read_into_local(self, channel, destination, local_offset, chunk_bytes):
                super().c2h_read_into_local(channel, destination, local_offset, chunk_bytes)
                return len(destination) - 1

        session = ShortSession()
        with PinnedActivationPool(session, require_lock=False) as pool:
            with self.assertRaisesRegex(RuntimeContractError, "short activation H2C write"):
                pool.write(np.zeros((ROWS, COLS), dtype=np.float32), 0, 0, "before_mlp", 0)
            self.assertEqual(pool.transfers, [])
            session.read_payload = bytes(8192 * 32)
            with self.assertRaisesRegex(RuntimeContractError, "short activation C2H read"):
                pool.read(0, 0, "after_mlp", 0)
            self.assertEqual(pool.transfers, [])


class AttentionPreservationTests(unittest.TestCase):
    def test_qk_clamp_is_intentional(self):
        self.assertEqual(score_finalize_s20([16 << 14] * 4), (16 << 14, True))
        self.assertEqual(score_finalize_s20([-(16 << 14)] * 4), (-(16 << 14), True))

    def test_softmax_delta_clamp_and_all_masked_refusal(self):
        scores = [-(16 << 14) - 1000] * 128
        scores[0] = 0
        masks = [False] * 128
        probabilities, exponents, _, _ = softmax_row_u16(scores, masks)
        self.assertEqual(exponents[0], 65536)
        self.assertEqual(exponents[1], exponents[-1])
        self.assertGreater(probabilities[0], probabilities[1])
        with self.assertRaises(ValueError):
            softmax_row_u16([0] * 128, [True] * 128)


class StaticGateTests(unittest.TestCase):
    def setUp(self):
        report_root = ROOT / "vivado/reports/rebuild_validation"
        report_root.mkdir(parents=True, exist_ok=True)
        self.scratch = tempfile.TemporaryDirectory(dir=report_root)
        self.root = Path(self.scratch.name)

    def tearDown(self):
        self.scratch.cleanup()

    def test_recursive_manifest_rejects_duplicate_symlink_and_parent_escape(self):
        (self.root / "leaf.sv").write_text("module leaf; endmodule\n", encoding="utf-8")
        (self.root / "child.list").write_text("leaf.sv\n", encoding="utf-8")
        main = self.root / "main.list"
        main.write_text("child.list\nleaf.sv\n", encoding="utf-8")
        with self.assertRaisesRegex(ContractError, "duplicate source"):
            expand_manifest(self.root, Path("main.list"))

        main.write_text("../outside.sv\n", encoding="utf-8")
        with self.assertRaisesRegex(ContractError, "parent traversal"):
            expand_manifest(self.root, Path("main.list"))

        (self.root / "linked.sv").symlink_to(self.root / "leaf.sv")
        main.write_text("linked.sv\n", encoding="utf-8")
        with self.assertRaisesRegex(ContractError, "symlink input"):
            expand_manifest(self.root, Path("main.list"))

        main.write_text("child.list\n", encoding="utf-8")
        manifests, leaves = expand_manifest(self.root, Path("main.list"))
        self.assertEqual(len(manifests), 2)
        self.assertEqual([item.name for item in leaves], ["leaf.sv"])

    def test_sv_port_width_parser_tracks_selected_numeric_ports(self):
        down = sv_tokens(ROOT / "rtl/mlp/hap_mlp_down_group_major_accum_s54.sv")
        self.assertEqual(port_width(down, "hap_mlp_down_group_major_accum_s54",
                                    "in_guard_s45", {"LANES": 128}), 5760)
        self.assertEqual(port_width(down, "hap_mlp_down_group_major_accum_s54",
                                    "out_projection_s32", {"LANES": 128}), 4096)

    def test_clock_parser_uses_declared_periods(self):
        xdc = self.root / "clocks.xdc"
        xdc.write_text(
            "create_clock -name core_clk -period 10.000 [get_ports core_clk]\n"
            "create_clock -name ddr0_clk -period 5.000 [get_ports ddr0_clk]\n"
            "create_clock -name ddr1_clk -period 5.000 [get_ports ddr1_clk]\n",
            encoding="utf-8",
        )
        self.assertEqual({name: str(period) for name, period in clock_periods(xdc).items()},
                         {"core_clk": "10.000", "ddr0_clk": "5.000", "ddr1_clk": "5.000"})
        with xdc.open("a", encoding="utf-8") as handle:
            handle.write("create_clock -name ddr1_clk -period 3.333 [get_ports ddr1_clk]\n")
        with self.assertRaisesRegex(ContractError, "duplicate clock"):
            clock_periods(xdc)

    def board_clock_fixture(self, ddr0_hz=200_000_000):
        path = self.root / "selected_board_clocks.sv"
        path.write_text(
            "// Unrelated FREQ_HZ 200000000 cannot override a port attribute.\n"
            "module selected_board_clocks (\n"
            '(* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 core_clk CLK" *)\n'
            '(* X_INTERFACE_PARAMETER = "ASSOCIATED_RESET core_rst_n, FREQ_HZ 100000000, ASSOCIATED_BUSIF S_AXIL:M_AXI_DATA" *) input wire core_clk,\n'
            '(* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 ddr0_clk CLK" *)\n'
            f'(* X_INTERFACE_PARAMETER = "FREQ_HZ {ddr0_hz}, ASSOCIATED_BUSIF M_AXI_WEIGHT_C0, ASSOCIATED_RESET ddr0_rst_n" *) input wire ddr0_clk,\n'
            '(* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 ddr1_clk CLK" *)\n'
            '(* X_INTERFACE_PARAMETER = "FREQ_HZ 200000000, ASSOCIATED_BUSIF M_AXI_WEIGHT_C1, ASSOCIATED_RESET ddr1_rst_n" *) input wire ddr1_clk\n'
            "); endmodule\n",
            encoding="utf-8",
        )
        return path

    def test_board_clock_attributes_parse_selected_ports_not_comments(self):
        path = self.board_clock_fixture()
        self.assertEqual(
            board_clock_attributes(
                sv_tokens(path, keep_strings=True), "selected_board_clocks"
            ),
            {"core_clk": 100_000_000, "ddr0_clk": 200_000_000,
             "ddr1_clk": 200_000_000},
        )
        path = self.board_clock_fixture(ddr0_hz=300_000_000)
        with self.assertRaisesRegex(ContractError, "FREQ_HZ mismatch: selected_board_clocks.ddr0_clk"):
            board_clock_attributes(
                sv_tokens(path, keep_strings=True), "selected_board_clocks"
            )

    def test_m002_board_clock_requires_dedicated_mlp_data_binding(self):
        path = self.board_clock_fixture()
        old = path.read_text().replace("selected_board_clocks", "hap_attention_mlp_board_core")
        path.write_text(old)
        with self.assertRaisesRegex(ContractError, "clock ASSOCIATED_BUSIF mismatch"):
            board_clock_attributes(sv_tokens(path, keep_strings=True),
                                   "hap_attention_mlp_board_core")
        path.write_text(old.replace("S_AXIL:M_AXI_DATA", "S_AXIL:M_AXI_DATA:M_AXI_MLP_DATA"))
        self.assertEqual(board_clock_attributes(sv_tokens(path, keep_strings=True),
                                               "hap_attention_mlp_board_core")["core_clk"],
                         100_000_000)

    def test_board_clock_attributes_reject_missing_duplicate_and_wrong_binding(self):
        path = self.board_clock_fixture()
        original = path.read_text(encoding="utf-8")
        cases = (
            (
                "FREQ_HZ 200000000, ASSOCIATED_BUSIF M_AXI_WEIGHT_C1",
                "ASSOCIATED_BUSIF M_AXI_WEIGHT_C1",
                "FREQ_HZ mismatch: selected_board_clocks.ddr1_clk",
            ),
            (
                "FREQ_HZ 200000000, ASSOCIATED_BUSIF M_AXI_WEIGHT_C1",
                "FREQ_HZ 200000000, FREQ_HZ 200000000, ASSOCIATED_BUSIF M_AXI_WEIGHT_C1",
                "duplicate clock parameter FREQ_HZ",
            ),
            (
                "xilinx.com:signal:clock:1.0 ddr0_clk CLK",
                "xilinx.com:signal:clock:1.0 wrong_clk CLK",
                "clock X_INTERFACE_INFO mismatch: selected_board_clocks.ddr0_clk",
            ),
            (
                "ASSOCIATED_RESET ddr0_rst_n",
                "ASSOCIATED_RESET wrong_rst_n",
                "clock ASSOCIATED_RESET mismatch: selected_board_clocks.ddr0_clk",
            ),
        )
        for old, new, message in cases:
            with self.subTest(message=message):
                path.write_text(original.replace(old, new), encoding="utf-8")
                with self.assertRaisesRegex(ContractError, message):
                    board_clock_attributes(
                        sv_tokens(path, keep_strings=True),
                        "selected_board_clocks",
                    )

    def test_selected_board_wrappers_have_core100_ddr200_attributes(self):
        _, leaves = expand_manifest(ROOT, DEFAULT_MANIFEST)
        defines = {
            "HAP_MLP_FULL_COMMAND_V5_MODULE": "hap_mlp_full_command16_s54",
            "HAP_ATTENTION_BOARD_MODULE": "hap_attention_board_cohort16_core",
        }
        owners = {
            name: path for path in leaves if path.suffix in {".sv", ".v"}
            for name in module_names(sv_tokens(path), defines)
        }
        expected = {
            "core_clk": 100_000_000,
            "ddr0_clk": 200_000_000,
            "ddr1_clk": 200_000_000,
        }
        for module in BOARD_CLOCK_MODULES:
            with self.subTest(module=module):
                self.assertIn(module, owners)
                self.assertEqual(
                    board_clock_attributes(
                        sv_tokens(owners[module], keep_strings=True), module
                    ),
                    expected,
                )

    def test_model_identity_parser_requires_literal_instruct_string(self):
        source = self.root / "identity.py"
        source.write_text(
            'MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"\n',
            encoding="utf-8",
        )
        self.assertEqual(py_string_constant(source, "MODEL_ID"),
                         "meta-llama/Llama-3.1-8B-Instruct")
        source.write_text("MODEL_ID = 1\n", encoding="utf-8")
        with self.assertRaisesRegex(ContractError, "not string"):
            py_string_constant(source, "MODEL_ID")


if __name__ == "__main__":
    unittest.main()
