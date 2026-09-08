#!/usr/bin/env python3

import unittest

from host.scalellm_hardware import (
    ATTENTION_ABI,
    ATTENTION_FORMAT_ID,
    MLP_ABI,
    MLP_COMPLETION_ACK,
    MLP_ABORT_STATUS,
    MLP_CONTROL,
    MLP_DOWN_META_RECORDS,
    MLP_FORMAT_ID,
    MLP_GATE_META_RECORDS,
    MLP_PAIRED_STATUS,
    MLP_TENSOR_INPUT_BEATS,
    MLP_TENSOR_INPUT_GROUPS,
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
        }
        self.writes = []
        self.corrupt_next_mlp_completion = False
        self.next_mlp_completion_status = CompletionStatus.SUCCESS
        self.maintenance_reads_remaining = 0
        self.ack_before_maintenance_complete = False

    def read32(self, offset):
        if offset == MLP_ABORT_STATUS and self.maintenance_reads_remaining:
            value = self.registers[offset]
            self.maintenance_reads_remaining -= 1
            if not self.maintenance_reads_remaining:
                self.registers[MLP_ABORT_STATUS] = 0
                self.registers[MLP_PAIRED_STATUS] = 1 << 5
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
                self.registers[0x114] |= 1 << (6 + bank)
                self.registers[0x178] &= ~1
            if value & 2:
                self.registers[0x178] |= 1 << 1
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
            self.registers[0x298] = (int(status) << 19) | (1 << 16) \
                | buffer_id
            self.registers[0x29C] = 1
            if status in (
                CompletionStatus.TIMEOUT,
                CompletionStatus.MAINTENANCE_ABORT,
            ):
                self.registers[MLP_ABORT_STATUS] = 1 << 1
                self.registers[MLP_PAIRED_STATUS] = 1 << 4
                self.maintenance_reads_remaining = 2
            return
        if offset == MLP_COMPLETION_ACK:
            if (self.registers.get(MLP_ABORT_STATUS, 0) & 0x3) or \
                    (self.registers.get(MLP_PAIRED_STATUS, 0) & (1 << 4)):
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

    def test_attention_programs_frozen_addresses_and_reuses_metadata(self):
        backend, transport, stager = self.make_backend()
        first = CommandIdentity(7, 1, 0, 0, 0, 0)
        completion = backend.execute(Engine.ATTENTION, first)
        self.assertEqual(completion.identity, first)
        self.assertIs(completion.status, CompletionStatus.SUCCESS)
        self.assertEqual(transport.registers[0x020], 0x7C00_0000)
        self.assertEqual(transport.registers[0x028], 0x0000_0000)
        self.assertEqual(transport.registers[0x02C], 0x0000_0000)
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
        self.assertEqual(transport.registers[0x020], 0x7C30_0000)
        self.assertEqual(len(stager.attention), 1)
        self.assertEqual(len(stager.rope), 1)
        self.assertEqual(len(backend.telemetry), 2)

    def test_mlp_loads_commits_and_reuses_one_layer_metadata(self):
        backend, transport, stager = self.make_backend()
        first = CommandIdentity(7, 3, 0, 0, 0, 1)
        completion = backend.execute(Engine.MLP, first)
        self.assertEqual(completion.identity, first)
        self.assertIs(completion.status, CompletionStatus.SUCCESS)
        self.assertEqual(len(stager.mlp), 1)
        self.assertEqual(stager.mlp[0][1], 1)
        self.assertEqual(transport.registers[0x12C], 0x0140_0000)
        self.assertEqual(transport.registers[0x134], 0x0300_0000)
        self.assertIn((MLP_COMPLETION_ACK, 3), transport.writes)
        self.assertNotIn((MLP_CONTROL, 2), transport.writes)

        second = CommandIdentity(8, 4, 1, 3, 0, 1)
        backend.execute(Engine.MLP, second)
        self.assertEqual(len(stager.mlp), 1)
        self.assertEqual(transport.registers[0x124], 0x7C30_0000)
        self.assertEqual(len(backend.telemetry), 2)
        self.assertEqual(backend.telemetry[0].engine, "mlp")
        self.assertEqual(backend.telemetry[0].identity, first)
        self.assertEqual(
            backend.telemetry[0].counters["tensor_input_beats"],
            MLP_TENSOR_INPUT_BEATS,
        )

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
                self.assertIn((MLP_COMPLETION_ACK, identity.command_id),
                              transport.writes)


if __name__ == "__main__":
    unittest.main()
