#!/usr/bin/env python3

import unittest
from contextlib import contextmanager

from host.scalellm_hardware import (
    ATTENTION_ABI,
    ATTENTION_FORMAT_ID,
    MLP_ABI,
    MLP_COMPLETION_ACK,
    MLP_ABORT_STATUS,
    MLP_CONTROL,
    MLP_DMA_STATUS,
    MLP_DOWN_SATURATION_COUNT,
    MLP_DOWN_META_RECORDS,
    MLP_FORMAT_ID,
    MLP_GATE_META_RECORDS,
    MLP_NUMERIC_STATUS,
    MEMORY_LAYOUT_ID,
    MEMORY_LAYOUT_REGISTER,
    MLP_PAIRED_STATUS,
    MLP_TENSOR_INPUT_BEATS,
    MLP_TENSOR_INPUT_GROUPS,
    MLP_TENSOR_OUTPUT_BEATS,
    MLP_TENSOR_OUTPUT_TILES,
    MLP_TOTAL_SHIFT_FORMAT_ERROR_COUNT,
    HardwareResetRequired,
    ScaleLLMHardwareBackend,
)
from host.scalellm_runtime import (
    CommandIdentity,
    CompletionStatus,
    Engine,
    RuntimeContractError,
)


class FakeStager:
    def __init__(self):
        self.attention = []
        self.mlp = []
        self.rope = []
        self.weights = []

    @contextmanager
    def mlp_weights(self, layer_id):
        self.weights.append(layer_id)
        yield

    def stage_attention(self, layer_id, local_base, expected_bytes):
        self.attention.append((layer_id, local_base, expected_bytes))

    def stage_mlp(self, layer_id, bank, gate_local_base, gate_bytes,
                  down_local_base, down_bytes):
        self.mlp.append((layer_id, bank, gate_local_base, gate_bytes,
                         down_local_base, down_bytes))

    def stage_rope(self, local_base, expected_bytes):
        self.rope.append((local_base, expected_bytes))


class FakeRegisterTransport:
    def __init__(self):
        self.registers = {
            0x000: ATTENTION_FORMAT_ID,
            0x004: ATTENTION_ABI,
            0x00C: 0,
            0x100: MLP_FORMAT_ID,
            0x104: MLP_ABI,
            0x10C: 1 << 5,
            0x114: 0,
            0x144: 0,
            0x14C: 0,
            0x178: 0,
            0x29C: 0,
            0x2A0: 0,
            MEMORY_LAYOUT_REGISTER: MEMORY_LAYOUT_ID,
        }
        self.writes = []
        self.mlp_ready_after_reads = 0
        self.mlp_ready_pending_mask = 0
        self.mlp_ready_status_reads = []
        self.mlp_ready_read_write_count = None
        self.mlp_load_fault_dma = 0
        self.mlp_load_fault_status = 0
        self.mlp_store_arm_fault_dma = 0
        self.corrupt_next_mlp_completion = False
        self.next_mlp_completion_status = CompletionStatus.SUCCESS
        self.mlp_counter_overrides = {}
        self.maintenance_reads_remaining = 0
        self.maintenance_polls = 0
        self.maintenance_saw_dma_active = False
        self.maintenance_saw_paired_active = False
        self.reject_fault_maintenance_request = False
        self.fault_maintenance_requests = 0
        self.fault_maintenance_accepted = 0
        self.ack_before_maintenance_complete = False
        self.maintenance_stuck = False
        self.maintenance_leave_dma_active = False
        self.maintenance_leave_protocol_error = False
        self.maintenance_final_status = {}

    def read32(self, offset):
        if offset == 0x114 and self.mlp_ready_pending_mask:
            if len(self.mlp_ready_status_reads) >= self.mlp_ready_after_reads:
                self.registers[0x114] |= self.mlp_ready_pending_mask
                self.mlp_ready_pending_mask = 0
                self.mlp_ready_read_write_count = len(self.writes)
            self.mlp_ready_status_reads.append(self.registers[0x114])
        if offset == MLP_ABORT_STATUS and self.maintenance_reads_remaining:
            value = self.registers[offset]
            self.maintenance_polls += 1
            self.maintenance_saw_dma_active |= bool(
                self.registers.get(0x178, 0) & 0x1
            )
            self.maintenance_saw_paired_active |= bool(
                self.registers.get(MLP_PAIRED_STATUS, 0) & (1 << 4)
            )
            if self.maintenance_stuck:
                return value
            self.maintenance_reads_remaining -= 1
            if not self.maintenance_reads_remaining:
                self.registers[MLP_ABORT_STATUS] = 0
                self.registers[MLP_PAIRED_STATUS] = (1 << 5) | (
                    (1 << 3) if self.maintenance_leave_protocol_error else 0
                )
                self.registers[0x178] &= ~0x6
                if not self.maintenance_leave_dma_active:
                    self.registers[0x178] &= ~0x1
                self.registers.update(self.maintenance_final_status)
            return value
        return self.registers.get(offset, 0)

    def write32(self, offset, value):
        value &= 0xFFFF_FFFF
        self.writes.append((offset, value))
        if offset == 0x108:
            self.registers[0x10C] = (1 << 6) | (1 << 5) | (1 << 4) \
                | (1 << 3) | value
            return
        if offset == 0x008:
            if value & 1:
                self.registers[0x078] = self.registers[0x070]
                self.registers[0x07C] = self.registers[0x010]
                self.registers[0x080] = self.registers[0x074]
                self.registers[0x084] = self.registers[0x014]
                buffer_id = self.registers[0x074] >> 16
                self.registers[0x088] = buffer_id
                self.registers[0x00C] = (1 << 4) | (1 << 3) | (1 << 1)
            if value & (1 << 1):
                self.registers[0x00C] &= ~0x6
            return
        if offset == 0x154:
            bank = self.registers[0x150] & 1
            if value & 1:
                self.registers[0x14C] = (self.registers[0x14C] & 0x7) \
                    | (1 << (3 + bank))
                self.registers[0x160 if bank else 0x15C] = \
                    MLP_GATE_META_RECORDS
                self.registers[0x168 if bank else 0x164] = \
                    MLP_DOWN_META_RECORDS
                self.registers[0x178] &= ~(1 << 2)
            if value & 2:
                generation = self.registers[0x158]
                self.registers[0x144] = generation
                self.registers[0x114] &= ~((1 << 8) | (3 << 9))
                self.registers[0x114] |= (bank << 8) | (1 << (9 + bank))
                self.registers[0x14C] = bank | (1 << (1 + bank))
            return
        if offset == 0x174:
            if value & 1:
                self.registers[0x17C] = MLP_TENSOR_INPUT_BEATS
                self.registers[0x244] = MLP_TENSOR_INPUT_GROUPS
                bank = self.registers[0x13C] & 1
                if self.mlp_ready_after_reads:
                    self.mlp_ready_pending_mask = 1 << (6 + bank)
                else:
                    self.registers[0x114] |= 1 << (6 + bank)
                self.registers[0x114] |= self.mlp_load_fault_status
                self.registers[0x178] |= self.mlp_load_fault_dma
                self.registers[0x178] &= ~1
            if value & 2:
                self.registers[0x178] |= 1 << 1
                self.registers[0x178] |= self.mlp_store_arm_fault_dma
            return
        if offset == MLP_CONTROL and value & 1:
            request_id = self.registers[0x280]
            command_id = self.registers[0x118]
            owner = self.registers[0x284]
            layer_id = self.registers[0x11C]
            if self.corrupt_next_mlp_completion:
                command_id += 1
                self.corrupt_next_mlp_completion = False
            self.registers[0x288] = request_id
            self.registers[0x28C] = command_id
            self.registers[0x290] = owner
            self.registers[0x294] = layer_id
            buffer_id = owner >> 16
            status = self.next_mlp_completion_status
            self.next_mlp_completion_status = CompletionStatus.SUCCESS
            if status is CompletionStatus.SUCCESS:
                self.registers[0x178] &= ~0x7
                self.registers[0x248] = 8192
                self.registers[0x24C] = 256
            for counter_offset, counter_value in self.mlp_counter_overrides.items():
                self.registers[counter_offset] = counter_value
            self.registers[0x298] = (int(status) << 19) | (1 << 16) \
                | buffer_id
            self.registers[0x29C] = 1
            if status in (
                CompletionStatus.TIMEOUT,
                CompletionStatus.MAINTENANCE_ABORT,
            ):
                self.registers[MLP_ABORT_STATUS] = 1 << 1
                self.registers[MLP_PAIRED_STATUS] = 1 << 4
                self.registers[0x178] |= 0x1
                self.maintenance_reads_remaining = 2
            return
        if offset == MLP_CONTROL and value & (1 << 1):
            self.fault_maintenance_requests += 1
            if self.reject_fault_maintenance_request:
                return
            # Idle clear can remove a completed record without creating abort
            # pending; a sticky source fault does not thereby become drained.
            self.fault_maintenance_accepted += 1
            self.registers[0x29C] = 0
            self.registers[MLP_ABORT_STATUS] = 0
            self.registers[MLP_PAIRED_STATUS] = 1 << 4
            self.registers[0x178] |= 0x1
            self.maintenance_reads_remaining = 0
            return
        if offset == MLP_COMPLETION_ACK:
            if (self.registers.get(MLP_ABORT_STATUS, 0) & 0x3) or \
                    (self.registers.get(MLP_PAIRED_STATUS, 0) & (1 << 4)) or \
                    (self.registers.get(0x178, 0) & 0x1):
                self.ack_before_maintenance_complete = True
            if value == self.registers.get(0x28C):
                self.registers[0x29C] = 0
            return
        self.registers[offset] = value


class ScaleLLMHardwareTests(unittest.TestCase):
    def make_backend(self):
        transport = FakeRegisterTransport()
        stager = FakeStager()
        backend = ScaleLLMHardwareBackend(
            transport, stager, timeout_s=0.05, poll_interval_s=0
        )
        backend.initialize_shared_mode()
        return backend, transport, stager

    def test_initialize_requires_exact_abis_and_shared_mode(self):
        backend, transport, _ = self.make_backend()
        self.assertTrue(backend._initialized)
        self.assertIn((0x108, 3), transport.writes)
        bad = FakeRegisterTransport()
        bad.registers[0x104] ^= 1
        with self.assertRaises(RuntimeContractError):
            ScaleLLMHardwareBackend(
                bad, FakeStager(), poll_interval_s=0
            ).initialize_shared_mode()

        old_width_bitstream = FakeRegisterTransport()
        old_width_bitstream.registers[0x100] = 0x4838_4602
        with self.assertRaisesRegex(RuntimeContractError, "identity mismatch"):
            ScaleLLMHardwareBackend(
                old_width_bitstream, FakeStager(), poll_interval_s=0
            ).initialize_shared_mode()

    def test_old_or_unknown_memory_layout_is_rejected_before_writes(self):
        for layout_id in (0, 0x4D303031, 0xFFFFFFFF):
            transport = FakeRegisterTransport()
            transport.registers[0x2B8] = layout_id
            stager = FakeStager()
            backend = ScaleLLMHardwareBackend(transport, stager, poll_interval_s=0)
            with self.assertRaisesRegex(RuntimeContractError, "0x2b8 identity mismatch"):
                backend.initialize_shared_mode()
            self.assertEqual(transport.writes, [])
            self.assertEqual(stager.weights, [])

    def test_busy_or_unretired_mlp_does_not_stage_or_write(self):
        for register, bit in ((0x29C, 1), (0x29C, 2), (0x2A0, 1),
                              (0x114, 1), (0x178, 1), (0x178, 2),
                              (0x178, 4), (0x2A8, 1), (0x2A8, 2),
                              (0x260, 8), (0x260, 16)):
            with self.subTest(register=register, bit=bit):
                backend, transport, stager = self.make_backend()
                transport.registers[register] = transport.registers.get(register, 0) | bit
                before = len(transport.writes)
                with self.assertRaises(RuntimeContractError):
                    backend.execute(Engine.MLP, CommandIdentity(1, 1, 0, 0, 0, 1))
                self.assertEqual(stager.weights, [])
                self.assertEqual(stager.mlp, [])
                self.assertEqual(len(transport.writes), before)

    def test_attention_programs_frozen_addresses_and_reuses_metadata(self):
        backend, transport, stager = self.make_backend()
        first = CommandIdentity(7, 1, 0, 0, 0, 0)
        completion = backend.execute(Engine.ATTENTION, first)
        self.assertEqual(completion.identity, first)
        self.assertIs(completion.status, CompletionStatus.SUCCESS)
        self.assertEqual(transport.registers[0x020], 0x5600_0000)
        self.assertEqual(transport.registers[0x028], 0x0000_0000)
        self.assertEqual(transport.registers[0x02C], 20 << 20)
        self.assertEqual(transport.registers[0x024], 0x5608_0000)
        self.assertEqual(len(stager.attention), 1)
        self.assertEqual(len(stager.rope), 1)
        self.assertEqual(len(backend.telemetry), 1)
        self.assertEqual(backend.telemetry[0].engine, "attention")
        self.assertEqual(backend.telemetry[0].identity, first)
        self.assertEqual(
            backend.telemetry[0].counters["cycle_count"],
            transport.registers.get(0x038, 0),
        )

        second = CommandIdentity(8, 2, 1, 3, 0, 0)
        backend.execute(Engine.ATTENTION, second)
        self.assertEqual(transport.registers[0x020], 0x5630_0000)
        self.assertEqual(len(stager.attention), 1)
        self.assertEqual(len(stager.rope), 1)
        self.assertEqual(len(backend.telemetry), 2)

    def test_mlp_loads_commits_and_reuses_one_layer_metadata(self):
        self.assertEqual((MLP_TENSOR_OUTPUT_BEATS, MLP_TENSOR_OUTPUT_TILES),
                         (8192, 256))
        backend, transport, stager = self.make_backend()
        first = CommandIdentity(7, 3, 0, 0, 0, 1)
        completion = backend.execute(Engine.MLP, first)
        self.assertEqual(completion.identity, first)
        self.assertIs(completion.status, CompletionStatus.SUCCESS)
        self.assertEqual(len(stager.mlp), 1)
        self.assertEqual(stager.mlp[0][1], 1)
        self.assertEqual(transport.registers[0x12C], 0)
        self.assertEqual(transport.registers[0x134], 56 << 20)
        self.assertIn((MLP_COMPLETION_ACK, 3), transport.writes)
        self.assertNotIn((MLP_CONTROL, 2), transport.writes)

        second = CommandIdentity(8, 4, 1, 3, 0, 1)
        backend.execute(Engine.MLP, second)
        self.assertEqual(len(stager.mlp), 1)
        self.assertEqual(transport.registers[0x124], 0x0630_0000)
        self.assertEqual(transport.registers[0x128], 0x0638_0000)
        self.assertEqual([transport.registers[r] for r in (0x12C, 0x130, 0x134, 0x138)],
                         [0, 28 << 20, 56 << 20, 70 << 20])
        self.assertEqual(len(backend.telemetry), 2)
        self.assertEqual(backend.telemetry[0].engine, "mlp")
        self.assertEqual(backend.telemetry[0].identity, first)
        self.assertEqual(
            backend.telemetry[0].counters["tensor_input_beats"],
            6144,
        )
        self.assertEqual(backend.telemetry[0].counters["tensor_input_groups"], 128)
        self.assertEqual(backend.telemetry[0].counters["tensor_output_beats"], 8192)
        self.assertEqual(backend.telemetry[0].counters["tensor_output_tiles"], 256)

    def test_mlp_waits_for_selected_activation_bank_before_store_and_start(self):
        for bank in (0, 1):
            with self.subTest(bank=bank):
                backend, transport, _ = self.make_backend()
                transport.mlp_ready_after_reads = 4
                transport.registers[0x114] |= 1 << (6 + (1 - bank))
                identity = CommandIdentity(50 + bank, 30 + bank,
                                           bank, bank * 3, 0, 1)
                completion = backend.execute(Engine.MLP, identity)
                self.assertIs(completion.status, CompletionStatus.SUCCESS)
                selected = 1 << (6 + bank)
                self.assertGreaterEqual(len(transport.mlp_ready_status_reads), 5)
                self.assertTrue(all((status & selected) == 0 for status in
                                    transport.mlp_ready_status_reads[:4]))
                self.assertEqual(transport.mlp_ready_status_reads[4] & selected,
                                 selected)
                arm_index = transport.writes.index((0x174, 2))
                start_index = transport.writes.index((MLP_CONTROL, 1))
                self.assertGreaterEqual(arm_index,
                                        transport.mlp_ready_read_write_count)
                self.assertLess(arm_index, start_index)
                self.assertIn((0x13C, bank), transport.writes[:arm_index])
                self.assertIn((0x174, 1), transport.writes[:arm_index])
                self.assertIn((MLP_COMPLETION_ACK, identity.command_id),
                              transport.writes[start_index:])

    def test_mlp_opposite_bank_only_times_out_without_store_or_start(self):
        for bank in (0, 1):
            with self.subTest(bank=bank):
                backend, transport, _ = self.make_backend()
                backend.timeout_s = 0.002
                transport.mlp_ready_after_reads = 1_000_000
                transport.registers[0x114] |= 1 << (6 + (1 - bank))
                identity = CommandIdentity(60 + bank, 40 + bank,
                                           bank, bank * 3, 0, 1)
                with self.assertRaisesRegex(RuntimeContractError,
                                            "MLP tensor load"):
                    backend.execute(Engine.MLP, identity)
                self.assertTrue(transport.mlp_ready_status_reads)
                self.assertTrue(all((status & (1 << (6 + bank))) == 0
                                    for status in transport.mlp_ready_status_reads))
                self.assertNotIn((0x174, 2), transport.writes)
                self.assertNotIn((MLP_CONTROL, 1), transport.writes)
                before = len(transport.writes)
                with self.assertRaises(HardwareResetRequired):
                    backend.execute(Engine.MLP, identity)
                self.assertEqual(len(transport.writes), before)

    def test_mlp_readiness_wait_fails_closed_on_dma_and_status_faults(self):
        for name, attr, fault, message in (
            ("dma", "mlp_load_fault_dma", 1 << 3, "DMA error"),
            ("sticky", "mlp_load_fault_status", 1 << 2,
             "input preparation reported a fault"),
            ("owner", "mlp_load_fault_status", 1 << 11,
             "input preparation reported a fault"),
            ("meta", "mlp_load_fault_status", 1 << 12,
             "input preparation reported a fault"),
        ):
            with self.subTest(name=name):
                backend, transport, _ = self.make_backend()
                setattr(transport, attr, fault)
                identity = CommandIdentity(70, 50, 0, 0, 0, 1)
                with self.assertRaisesRegex(RuntimeContractError, message):
                    backend.execute(Engine.MLP, identity)
                self.assertNotIn((0x174, 2), transport.writes)
                self.assertNotIn((MLP_CONTROL, 1), transport.writes)

        backend, transport, _ = self.make_backend()
        transport.mlp_store_arm_fault_dma = 1 << 3
        with self.assertRaisesRegex(RuntimeContractError, "DMA error"):
            backend.execute(Engine.MLP, CommandIdentity(71, 51, 0, 0, 0, 1))
        self.assertIn((0x174, 2), transport.writes)
        self.assertNotIn((MLP_CONTROL, 1), transport.writes)

    def test_success_rejects_each_mlp_dma_count_mismatch(self):
        cases = (
            (0x17C, 6143, "MLP tensor input mismatch"),
            (0x244, 127, "MLP tensor input mismatch"),
            (0x248, 8191, "MLP tensor output mismatch"),
            (0x24C, 255, "MLP tensor output mismatch"),
        )
        for index, (offset, value, message) in enumerate(cases):
            with self.subTest(offset=offset):
                backend, transport, _ = self.make_backend()
                transport.mlp_counter_overrides[offset] = value
                identity = CommandIdentity(30 + index, 20 + index,
                                           0, 0, index, 1)
                with self.assertRaisesRegex(RuntimeContractError, message):
                    backend.execute(Engine.MLP, identity)
                self.assertIn((MLP_COMPLETION_ACK, identity.command_id),
                              transport.writes)

    def test_identity_mismatch_is_not_acknowledged(self):
        backend, transport, _ = self.make_backend()
        transport.corrupt_next_mlp_completion = True
        identity = CommandIdentity(9, 5, 0, 0, 1, 1)
        with self.assertRaises(RuntimeContractError):
            backend.execute(Engine.MLP, identity)
        self.assertEqual(transport.registers[0x29C], 1)
        self.assertNotIn((MLP_COMPLETION_ACK, identity.command_id),
                         transport.writes)

    def test_mlp_abort_waits_for_maintenance_before_ack(self):
        for status in (
            CompletionStatus.TIMEOUT,
            CompletionStatus.MAINTENANCE_ABORT,
        ):
            with self.subTest(status=status):
                backend, transport, _ = self.make_backend()
                transport.next_mlp_completion_status = status
                identity = CommandIdentity(10, 6, 1, 3, 2, 1)
                completion = backend.execute(Engine.MLP, identity)
                self.assertEqual(completion.identity, identity)
                self.assertIs(completion.status, status)
                self.assertFalse(transport.ack_before_maintenance_complete)
                self.assertEqual(transport.maintenance_reads_remaining, 0)
                self.assertEqual(transport.registers[MLP_ABORT_STATUS], 0)
                self.assertEqual(
                    transport.registers[MLP_PAIRED_STATUS], 1 << 5
                )
                self.assertEqual(transport.registers[MLP_DMA_STATUS] & 0x7, 0)
                self.assertIn((MLP_COMPLETION_ACK, identity.command_id),
                              transport.writes)
                self.assertEqual(transport.fault_maintenance_requests, 0)
                self.assertEqual(len(backend.telemetry), 1)
                self.assertEqual(backend.telemetry[0].completion_status,
                                 status.name)
                self.assertEqual(transport.registers.get(0x248, 0), 0)
                self.assertEqual(transport.registers.get(0x24C, 0), 0)

    def test_completed_numeric_fault_saves_telemetry_and_requires_reset(self):
        cases = (
            (MLP_DOWN_SATURATION_COUNT, 1, "down_output_saturation_count",
             "down_output_saturation_count"),
            (MLP_TOTAL_SHIFT_FORMAT_ERROR_COUNT, 2,
             "total_shift_format_error_count", "total_shift_format_error_count"),
            (MLP_NUMERIC_STATUS, 1, "guard_overflow", "numeric_status"),
            (MLP_NUMERIC_STATUS, 2, "accumulator_overflow", "numeric_status"),
            (MLP_NUMERIC_STATUS, 4, "format_error_status", "numeric_status"),
        )
        for index, (offset, value, message, counter_name) in enumerate(cases):
            with self.subTest(message=message):
                backend, transport, _ = self.make_backend()
                transport.mlp_counter_overrides[offset] = value
                transport.mlp_counter_overrides[MLP_DMA_STATUS] = 1
                transport.mlp_counter_overrides[MLP_PAIRED_STATUS] = 1 << 4
                identity = CommandIdentity(20 + index, 10 + index,
                                           0, 0, index, 1)
                with self.assertRaisesRegex(HardwareResetRequired,
                                            r"(?i)reset[- ]required") as failure:
                    backend.execute(Engine.MLP, identity)
                self.assertIn(message, str(failure.exception))
                self.assertEqual(transport.registers[0x29C], 1)
                self.assertNotIn((MLP_CONTROL, 1 << 1), transport.writes)
                self.assertEqual(transport.fault_maintenance_requests, 0)
                self.assertEqual(transport.fault_maintenance_accepted, 0)
                self.assertEqual(transport.maintenance_polls, 0)
                self.assertFalse(transport.ack_before_maintenance_complete)
                self.assertEqual(transport.registers.get(MLP_ABORT_STATUS, 0), 0)
                self.assertEqual(transport.registers[MLP_PAIRED_STATUS], 1 << 4)
                self.assertEqual(transport.registers[MLP_DMA_STATUS] & 1, 1)
                self.assertNotIn((MLP_COMPLETION_ACK, identity.command_id),
                                 transport.writes)
                self.assertEqual(len(backend.telemetry), 1)
                telemetry = backend.telemetry[0]
                self.assertEqual(telemetry.identity, identity)
                self.assertEqual(telemetry.completion_status, "SUCCESS")
                self.assertEqual(telemetry.counters[counter_name], value)
                writes_before_retry = len(transport.writes)
                with self.assertRaises(HardwareResetRequired):
                    backend.execute(Engine.MLP,
                                    CommandIdentity(40 + index, 30 + index,
                                                    0, 0, index, 1))
                self.assertEqual(len(transport.writes), writes_before_retry)
                self.assertEqual(len(backend.telemetry), 1)

    def test_sticky_protocol_fault_does_not_attempt_rejected_clear_or_ack(self):
        backend, transport, _ = self.make_backend()
        transport.next_mlp_completion_status = CompletionStatus.PROTOCOL_ERROR
        transport.mlp_counter_overrides[0x148] = 0x103
        transport.mlp_counter_overrides[MLP_PAIRED_STATUS] = (1 << 4) | (1 << 3)
        transport.reject_fault_maintenance_request = True
        identity = CommandIdentity(26, 16, 0, 0, 0, 1)
        with self.assertRaisesRegex(HardwareResetRequired,
                                    r"(?i)reset[- ]required"):
            backend.execute(Engine.MLP, identity)
        self.assertEqual(transport.fault_maintenance_requests, 0)
        self.assertEqual(transport.fault_maintenance_accepted, 0)
        self.assertEqual(transport.registers[0x29C], 1)
        self.assertEqual(transport.registers[MLP_PAIRED_STATUS] & (1 << 3), 1 << 3)
        self.assertEqual(len(backend.telemetry), 1)
        self.assertEqual(backend.telemetry[0].completion_status, "PROTOCOL_ERROR")
        self.assertEqual(backend.telemetry[0].counters["error_code"], 0x103)
        self.assertNotIn((MLP_CONTROL, 1 << 1), transport.writes)
        self.assertNotIn((MLP_COMPLETION_ACK, identity.command_id),
                         transport.writes)
        writes_before_retry = tuple(transport.writes)
        with self.assertRaises(HardwareResetRequired):
            backend.initialize_shared_mode()
        with self.assertRaises(HardwareResetRequired):
            backend.execute(Engine.ATTENTION,
                            CommandIdentity(50, 40, 0, 0, 0, 0))
        self.assertEqual(tuple(transport.writes), writes_before_retry)
        self.assertEqual(len(backend.telemetry), 1)

    def test_completed_source_errors_are_reset_required_with_active_sources(self):
        for index, status in enumerate((
            CompletionStatus.DDR_ERROR, CompletionStatus.FORMAT_ERROR,
            CompletionStatus.INTERNAL_ERROR,
        )):
            with self.subTest(status=status):
                backend, transport, _ = self.make_backend()
                transport.next_mlp_completion_status = status
                transport.mlp_counter_overrides[MLP_DMA_STATUS] = 1
                transport.mlp_counter_overrides[MLP_PAIRED_STATUS] = 1 << 4
                transport.mlp_counter_overrides[0x148] = 0x104 + index
                identity = CommandIdentity(27 + index, 17 + index, 0, 0, 1, 1)
                with self.assertRaisesRegex(HardwareResetRequired,
                                            r"(?i)reset[- ]required") as failure:
                    backend.execute(Engine.MLP, identity)
                self.assertIn(status.name, str(failure.exception))
                self.assertEqual(transport.fault_maintenance_requests, 0)
                self.assertEqual(transport.fault_maintenance_accepted, 0)
                self.assertEqual(transport.maintenance_polls, 0)
                self.assertEqual(transport.registers[0x29C], 1)
                self.assertEqual(transport.registers[MLP_DMA_STATUS] & 1, 1)
                self.assertEqual(transport.registers[MLP_PAIRED_STATUS], 1 << 4)
                self.assertEqual(len(backend.telemetry), 1)
                self.assertEqual(backend.telemetry[0].identity, identity)
                self.assertEqual(backend.telemetry[0].completion_status, status.name)
                self.assertEqual(backend.telemetry[0].counters["error_code"], 0x104 + index)
                self.assertNotIn((MLP_CONTROL, 1 << 1), transport.writes)
                self.assertNotIn((MLP_COMPLETION_ACK, identity.command_id),
                                 transport.writes)

    def test_abort_cannot_ack_while_paired_maintenance_is_active(self):
        backend, transport, _ = self.make_backend()
        backend.timeout_s = 0.005
        transport.next_mlp_completion_status = CompletionStatus.TIMEOUT
        transport.maintenance_stuck = True
        identity = CommandIdentity(28, 18, 0, 0, 0, 1)
        with self.assertRaisesRegex(RuntimeContractError,
                                    "MLP abort maintenance completion"):
            backend.execute(Engine.MLP, identity)
        self.assertGreater(transport.maintenance_polls, 0)
        self.assertTrue(transport.maintenance_saw_dma_active)
        self.assertTrue(transport.maintenance_saw_paired_active)
        self.assertEqual(transport.registers[0x29C], 1)
        self.assertNotIn((MLP_COMPLETION_ACK, identity.command_id),
                         transport.writes)

    def test_abort_cannot_ack_while_tensor_dma_remains_active(self):
        backend, transport, _ = self.make_backend()
        backend.timeout_s = 0.005
        transport.next_mlp_completion_status = CompletionStatus.TIMEOUT
        transport.maintenance_leave_dma_active = True
        identity = CommandIdentity(29, 19, 0, 0, 1, 1)
        with self.assertRaisesRegex(RuntimeContractError,
                                    "MLP abort maintenance completion"):
            backend.execute(Engine.MLP, identity)
        self.assertEqual(transport.registers[MLP_ABORT_STATUS], 0)
        self.assertEqual(transport.registers[MLP_PAIRED_STATUS], 1 << 5)
        self.assertEqual(transport.registers[0x178] & 0x1, 1)
        self.assertNotIn((MLP_COMPLETION_ACK, identity.command_id),
                         transport.writes)

    def test_abort_cannot_ack_while_owner_protocol_error_remains_sticky(self):
        backend, transport, _ = self.make_backend()
        backend.timeout_s = 0.005
        transport.next_mlp_completion_status = CompletionStatus.MAINTENANCE_ABORT
        transport.maintenance_leave_protocol_error = True
        identity = CommandIdentity(30, 20, 0, 0, 1, 1)
        with self.assertRaisesRegex(RuntimeContractError,
                                    "MLP abort maintenance completion"):
            backend.execute(Engine.MLP, identity)
        self.assertEqual(transport.registers[MLP_PAIRED_STATUS],
                         (1 << 5) | (1 << 3))
        self.assertEqual(transport.registers[0x29C], 1)
        self.assertNotIn((MLP_COMPLETION_ACK, identity.command_id),
                         transport.writes)

    def test_abort_refuses_each_independent_quiescence_predicate(self):
        cases = (
            (MLP_ABORT_STATUS, 1),
            (MLP_ABORT_STATUS, 2),
            (MLP_PAIRED_STATUS, 0),
            (MLP_PAIRED_STATUS, 1 << 4),
            (MLP_PAIRED_STATUS, (1 << 5) | (1 << 4)),
            (MLP_PAIRED_STATUS, (1 << 5) | (1 << 3)),
        ) + tuple((MLP_DMA_STATUS, mask) for mask in range(1, 8))
        for status in (CompletionStatus.TIMEOUT,
                       CompletionStatus.MAINTENANCE_ABORT):
            for index, (offset, value) in enumerate(cases):
                with self.subTest(status=status, offset=offset, value=value):
                    backend, transport, _ = self.make_backend()
                    backend.timeout_s = 0.005
                    transport.next_mlp_completion_status = status
                    transport.maintenance_final_status = {offset: value}
                    identity = CommandIdentity(60 + index, 80 + index,
                                               0, 0, 0, 1)
                    with self.assertRaisesRegex(RuntimeContractError,
                                                "MLP abort maintenance completion"):
                        backend.execute(Engine.MLP, identity)
                    self.assertEqual(transport.maintenance_reads_remaining, 0)
                    self.assertEqual(transport.registers[offset], value)
                    self.assertEqual(transport.registers[0x29C], 1)
                    self.assertNotIn((MLP_COMPLETION_ACK, identity.command_id),
                                     transport.writes)
                    self.assertNotIn((MLP_CONTROL, 1 << 1), transport.writes)
                    self.assertEqual(len(backend.telemetry), 1)
                    self.assertEqual(backend.telemetry[0].identity, identity)
                    self.assertEqual(backend.telemetry[0].completion_status,
                                     status.name)


if __name__ == "__main__":
    unittest.main()
