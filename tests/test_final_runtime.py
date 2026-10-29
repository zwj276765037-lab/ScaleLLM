"""Final runtime CPU/mock regression; no FPGA or licensed model files."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "project/hardware"))

import copy
import json
import struct
import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np

from host.scalellm_decode16 import DecodeRow
from host.scalellm_final_abi import ATTENTION, MLP, CSR, IDS, FinalDescriptor
from host.scalellm_final_layout import HIDDEN, INTERMEDIATE, pack_mlp_s32, pack_input_s24
from host.scalellm_final_runtime import FinalBoardBackend, FinalDecodeRuntime, FinalCommandError
from host.scalellm_final_assets import FinalAssetStore


def rows():
    return tuple(DecodeRow(True, slot + 10, slot * 3) if slot in (0, 3, 15)
                 else DecodeRow() for slot in range(16))


class Session:
    def __init__(self):
        self.regs = {CSR[name.upper()]: value for name, value in IDS.items()
                     if name.upper() in CSR}
        self.regs.update({CSR["STATUS"]: 0, CSR["ADMISSION_ERROR"]: 0})
        self.writes = []
        self.command = None
        self.stale = False
        self.h2c_calls = 0

    def read32(self, address):
        return self.regs.get(address, 0)

    def write32(self, address, value):
        self.writes.append((address, value))
        self.regs[address] = value
        if address == CSR["ACTION"] and value == 1:
            words = tuple(self.regs[CSR["DESCRIPTOR"] + 4 * i] for i in range(64))
            self.command = FinalDescriptor.unpack(struct.pack("<64I", *words))
            for i, word in enumerate(words):
                self.regs[CSR["COMPLETION_DESCRIPTOR"] + 4 * i] = word
            if self.stale:
                self.regs[CSR["COMPLETION_DESCRIPTOR"] + 33 * 4] ^= 1
            self.regs[CSR["STATUS"]] = 2
            self.regs[CSR["DONE_INPUT_BYTES"]] = self.command.input_bytes
            self.regs[CSR["DONE_OUTPUT_BYTES"]] = self.command.output_bytes
            self.regs[CSR["DONE_CYCLES"]] = 80_000_000
        if address == CSR["ACTION"] and value == 2:
            if self.regs[CSR["ACK_ID"]] != self.command.command_id:
                raise AssertionError("stale ACK reached mock transport")
            self.regs[CSR["STATUS"]] = 0

    def h2c_write_local(self, channel, payload, address, chunk):
        self.h2c_calls += 1
        return len(payload)

    def c2h_read_local(self, channel, length, address, chunk):
        return bytes(length)


class FinalAbiTests(unittest.TestCase):
    def test_descriptor_exact_bytes_and_roundtrip(self):
        d = FinalDescriptor.create(19, 4, MLP, 31, rows(), 8, 77, buffer_id=5)
        payload = d.pack()
        self.assertEqual(len(payload), 256)
        self.assertEqual(struct.unpack_from("<I", payload, 8)[0], 19)
        self.assertEqual(struct.unpack_from("<II", payload, (32 + 2 * 15) * 4), (45, 25))
        self.assertEqual(d.output_bytes, 917504)
        self.assertEqual(FinalDescriptor.unpack(payload), d)
        self.assertEqual(d.words()[12:16], (0, 0x1c00000, 0x2d900000, 0))

    def test_rejects_legacy_reserved_bad_rows_and_aliases(self):
        d = FinalDescriptor.create(19, 4, ATTENTION, 3, rows(), 8, 77)
        for word, value in ((0, 0x48384605), (1, 7), (20, 1), (32 + 2, 1),
                            (33, 0), (32, 128), (9, d.input_base), (10, 73728)):
            words = list(d.words()); words[word] = value
            with self.subTest(word=word), self.assertRaises(ValueError):
                FinalDescriptor.unpack(struct.pack("<64I", *words))

    def test_board_driver_checks_full_descriptor_before_ack(self):
        session = Session()
        backend = FinalBoardBackend(session, poll_s=0)
        d = FinalDescriptor.create(19, 4, MLP, 3, rows(), 8, 77)
        result = backend.run(d, bytes(d.input_bytes))
        self.assertEqual(len(result), 917504)
        self.assertEqual(backend.receipts[0]["seconds"], 1.0)
        self.assertIsNone(backend.pending)
        self.assertEqual(session.writes[-1], (CSR["ACTION"], 2))
        session.stale = True
        with self.assertRaisesRegex(FinalCommandError, "stale"):
            backend.run(d, bytes(d.input_bytes))
        self.assertIs(backend.pending, d)
        self.assertEqual(session.writes[-1], (CSR["ACTION"], 1))

    def test_legacy_bit_rejected_before_any_mutation(self):
        session = Session(); session.regs[CSR["MAGIC"]] = 0x48384605
        with self.assertRaises(FinalCommandError): FinalBoardBackend(session)
        self.assertEqual(session.writes, [])

    def test_diagnostic_gold_comparison_precedes_ack(self):
        session=Session();backend=FinalBoardBackend(session,poll_s=0)
        d=FinalDescriptor.create(19,4,MLP,3,rows(),8,77)
        calls=[]
        def compare(descriptor,output):
            self.assertIs(descriptor,d);self.assertEqual(len(output),d.output_bytes)
            self.assertEqual(session.regs[CSR['STATUS']],2)
            self.assertNotIn((CSR['ACK_ID'],d.command_id),session.writes)
            calls.append(True)
        backend.run(d,bytes(d.input_bytes),validate_output=compare)
        self.assertEqual(calls,[True]);self.assertIsNone(backend.pending)

    def test_failed_gold_retains_completion_and_pending(self):
        session=Session();backend=FinalBoardBackend(session,poll_s=0)
        d=FinalDescriptor.create(19,4,MLP,3,rows(),8,77)
        def compare(descriptor,output):raise AssertionError('independent gold differs')
        with self.assertRaisesRegex(AssertionError,'gold differs'):
            backend.run(d,bytes(d.input_bytes),validate_output=compare)
        self.assertIs(backend.pending,d);self.assertEqual(session.regs[CSR['STATUS']],2)
        self.assertNotIn((CSR['ACK_ID'],d.command_id),session.writes)
        self.assertEqual(backend.receipts,[])

    def test_completion_identity_rechecked_after_diagnostic_callback(self):
        session=Session();backend=FinalBoardBackend(session,poll_s=0)
        d=FinalDescriptor.create(19,4,MLP,3,rows(),8,77)
        def compare(descriptor,output):session.regs[CSR['COMPLETION_DESCRIPTOR']+8]^=1
        with self.assertRaisesRegex(FinalCommandError,'completion changed'):
            backend.run(d,bytes(d.input_bytes),validate_output=compare)
        self.assertIs(backend.pending,d)
        self.assertNotIn((CSR['ACK_ID'],d.command_id),session.writes)

    def test_invalid_output_validator_has_no_io(self):
        session=Session();backend=FinalBoardBackend(session,poll_s=0)
        d=FinalDescriptor.create(19,4,MLP,3,rows(),8,77)
        with self.assertRaisesRegex(ValueError,'callable'):
            backend.run(d,bytes(d.input_bytes),validate_output=42)
        self.assertEqual(session.writes,[]);self.assertEqual(session.h2c_calls,0)


class MockModel:
    def __init__(self): self.embeddings = []
    def embed(self, tokens):
        self.embeddings.append(tuple(tokens))
        return np.zeros((16, HIDDEN), dtype=np.float32)
    def attention_input(self, hidden, layer): return hidden
    def after_attention(self, hidden, output, layer, mask): return hidden, hidden
    def after_mlp(self, residual, product, layer, mask): return residual
    def predict(self, hidden, mask): return [1000 + slot for slot in range(16)]


class Assets:
    def __init__(self): self.calls = []
    def prepare_layer(self, layer, rows):
        self.calls.append((layer, rows))
        return len(self.calls)


class Backend:
    def __init__(self): self.commands = []; self.fail_at = None; self.pending = False; self.recovery_generation = 1
    def require_quiescent(self):
        if self.pending: raise FinalCommandError("retained pending command")
    def run(self, descriptor, payload):
        self.commands.append(descriptor)
        if self.fail_at == (descriptor.layer, descriptor.opcode):
            self.pending = True
            raise FinalCommandError("injected later layer failure")
        return bytes(descriptor.output_bytes)


class GlobalStepTests(unittest.TestCase):
    def test_all_sixteen_requests_complete_independently(self):
        backend, model, assets = Backend(), MockModel(), Assets()
        runtime = FinalDecodeRuntime(backend, model, assets)
        for slot in range(16):
            runtime.allocate(slot, [10 + slot] * (1 + slot % 4), 1 + slot % 3)
        output = runtime.run()
        self.assertEqual(len(output), 16)
        self.assertEqual(backend.commands[0].active_mask, 0xffff)
        for slot in range(16):
            self.assertEqual(output[slot], (1000 + slot,) * (1 + slot % 3))
            self.assertEqual(runtime.slots[slot].position, 1 + slot % 4 + slot % 3)
        self.assertTrue(any(d.active_mask != 0xffff for d in backend.commands))

    def test_full_reset_invalidates_old_runtime_and_assets_without_writes(self):
        session = Session(); backend = FinalBoardBackend(session)
        assets = FinalAssetStore(backend, None, None)
        runtime = FinalDecodeRuntime(backend, MockModel(), assets)
        runtime.allocate(0, [11, 12], 2)
        assets.resident, assets.prepared_layer, assets.down_weights = True, 4, object()
        backend.accept_quiescent_recovery()
        with self.assertRaisesRegex(FinalCommandError, "reset invalidated"):
            runtime.step()
        with self.assertRaisesRegex(RuntimeError, "reset invalidated"):
            assets.load_resident()
        self.assertFalse(assets.resident)
        self.assertIsNone(assets.prepared_layer)
        self.assertIsNone(assets.down_weights)
        self.assertEqual(session.h2c_calls, 0)
        self.assertEqual(session.writes, [])

    def test_pure_host_failure_retries_same_position_without_reset(self):
        class HostFailure(MockModel):
            def __init__(self): super().__init__(); self.first = True
            def predict(self, hidden, mask):
                if self.first:
                    self.first = False
                    raise RuntimeError("injected host LM-head failure")
                return super().predict(hidden, mask)
        backend, model, assets = Backend(), HostFailure(), Assets()
        runtime = FinalDecodeRuntime(backend, model, assets)
        runtime.allocate(5, [11], 2)
        with self.assertRaisesRegex(RuntimeError, "host LM-head"):
            runtime.step()
        self.assertEqual(runtime.slots[5].position, 0)
        self.assertEqual(runtime.slots[5].generated, [])
        original = backend.commands[0].rows
        runtime.step()
        self.assertEqual(backend.commands[64].rows, original)
        self.assertEqual(runtime.slots[5].position, 1)
        self.assertEqual(runtime.slots[5].generated, [1005])

    def test_pending_hardware_state_blocks_all_asset_mutation(self):
        for status in (1, 2, 4, 7):
            session, model, assets = Session(), MockModel(), Assets()
            backend = FinalBoardBackend(session, poll_s=0)
            runtime = FinalDecodeRuntime(backend, model, assets)
            runtime.allocate(0, [11], 2)
            session.regs[CSR["STATUS"]] = status
            with self.assertRaises(FinalCommandError): runtime.step()
            self.assertEqual(assets.calls, [])
            self.assertEqual(session.writes, [])
        backend, assets = Backend(), Assets()
        runtime = FinalDecodeRuntime(backend, MockModel(), assets)
        runtime.allocate(0, [11], 2)
        backend.pending = True
        with self.assertRaises(FinalCommandError): runtime.step()
        self.assertEqual(assets.calls, [])

    def test_later_layer_host_failure_preserves_every_position_token_then_retry(self):
        class LateHostFailure(MockModel):
            def __init__(self): super().__init__(); self.first = True
            def after_mlp(self, residual, product, layer, mask):
                if layer == 27 and self.first:
                    self.first = False
                    raise RuntimeError("injected late host Down failure")
                return residual
        backend, model, assets = Backend(), LateHostFailure(), Assets()
        runtime = FinalDecodeRuntime(backend, model, assets)
        runtime.allocate(0, [10, 11, 12], 2)
        runtime.allocate(3, [31], 2)
        before = copy.deepcopy(runtime.slots)
        with self.assertRaisesRegex(RuntimeError, "late host Down"): runtime.step()
        self.assertEqual(runtime.slots, before)
        self.assertTrue(runtime.step_pending)
        with self.assertRaises(FinalCommandError): runtime.allocate(15, [8], 1)
        first = backend.commands[0]
        boundary = len(backend.commands)
        runtime.step()
        retried = backend.commands[boundary]
        self.assertEqual(first.rows, retried.rows)
        self.assertGreater(retried.command_id, first.command_id)
        self.assertEqual(model.embeddings[0], model.embeddings[1])
        self.assertEqual(runtime.slots[0].position, 1)
        self.assertEqual(runtime.slots[0].generated, [])
        self.assertEqual(runtime.slots[3].generated, [1003])
        self.assertFalse(runtime.step_pending)

    def test_later_layer_hardware_failure_does_not_survive_reset_as_retry(self):
        backend, assets = Backend(), Assets()
        runtime = FinalDecodeRuntime(backend, MockModel(), assets)
        runtime.allocate(0, [11, 12], 2)
        backend.fail_at = (27, MLP)
        with self.assertRaises(FinalCommandError): runtime.step()
        self.assertEqual(runtime.slots[0].position, 0)
        count = len(assets.calls)
        with self.assertRaises(FinalCommandError): runtime.step()
        self.assertEqual(len(assets.calls), count)
        backend.recovery_generation += 1
        backend.pending = False
        with self.assertRaisesRegex(FinalCommandError, "reset invalidated"):
            runtime.step()
        self.assertEqual(len(assets.calls), count)

    def test_independent_prompts_eos_inactive_and_reuse_epoch(self):
        backend, model = Backend(), MockModel()
        runtime = FinalDecodeRuntime(backend, model, Assets(), eos_token_ids=[1003])
        runtime.allocate(0, [10, 11, 12], 2)
        runtime.allocate(3, [31], 9)
        runtime.step()
        self.assertTrue(runtime.slots[3].finished)
        self.assertEqual(runtime.slots[3].position, 1)
        old_epoch = runtime.slots[3].epoch
        runtime.allocate(3, [80, 81], 1)
        self.assertEqual(runtime.slots[3].epoch, old_epoch + 1)
        runtime.step()
        d = backend.commands[64]
        self.assertEqual((d.rows[0].position, d.rows[3].position), (1, 0))
        self.assertEqual(d.rows[3].epoch, old_epoch + 1)
        self.assertEqual(d.active_mask, 9)
        self.assertFalse(d.rows[15].active)
        results = runtime.run()
        self.assertEqual(results[0], (1000, 1000))
        self.assertEqual(results[3], (1003,))
        self.assertEqual(runtime.slots[15].position, 0)


if __name__ == "__main__": unittest.main()
