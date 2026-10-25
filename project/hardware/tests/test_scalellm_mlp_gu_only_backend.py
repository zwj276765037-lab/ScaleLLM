"""Real CSR/XDMA adapter on a scripted CPU transport, never RTL or a board.

DONE packets are independent literal fixtures, not derived from the adapter's
descriptor writes. ArtifactRecord performs actual file size/SHA validation.
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from host.scalellm_artifacts import ArtifactRecord
from host.scalellm_mlp_gu_only import DownWeights
from host.scalellm_mlp_gu_only_backend import GuOnlyXdmaBackend
from host.scalellm_mlp_gu_only_runtime import GuDescriptor, GuOnlyPipeline
from host.scalellm_runtime import RuntimeContractError, XdmaSession


INPUT = bytes(73728)  #128 canonical-zero REC576 records, including all padding.
OUTPUT = bytes(1376256)
SIZES = {"mlp_gate_up_c0": 29360128, "mlp_gate_up_c1": 29360128,
         "mlp_gate_meta": 7340032}


def descriptor(cohort=0, *, command=None):
    return GuDescriptor(10 + cohort if command is None else command, 91, cohort,
                        0, cohort * 3, 1, 1, 7)


def done_packet(cohort=0, *, command=None):
    # Independent ABI byte/count fixture: not descriptor.words() or CSR replay.
    return {0x328: 1, 0x32C: 1, 0x330: 7, 0x334: 1,
            0x338: 10 + cohort if command is None else command, 0x33C: 91,
            0x340: 0x00030001 if cohort else 0, 0x344: 0,
            0x348: 73728, 0x34C: 1376256, 0x350: 0, 0x364: 1792}


class Catalog:
    def __init__(self, records):
        self.records = dict(records)
        self.requests = []

    def layer_artifact(self, layer, name):
        self.requests.append((layer, name))
        return self.records[name]


class ScriptedTransport:
    """Explicit state observations for method/address/order tests only.

    This intentionally supplies no admission algorithm, AXI model, numerical
    computation, or proof that real hardware produces these observations.
    """
    def __init__(self):
        self.csr = {0x000: 0x48384103, 0x004: 0x00020000,
                    0x100: 0x48384605, 0x104: 0x00070000,
                    0x2B8: 0x4D303032, 0x300: 0x4D4C0002,
                    0x304: 0x1D, 0x308: 1, 0x324: 8,
                    0x10C: 0x20, 0x260: 0x20}
        self.events = []
        self.done_packets = [done_packet(0), done_packet(1)]
        self.start_error = None
        self.admission = 0
        self.completion_status = 10
        self.metadata_error = False
        self.short_h2c = False
        self.short_c2h = False
        self.hold_busy = False
        self.load_pending = False
        self.output = bytearray(OUTPUT)
        self.output_copied = False

    def read32(self, address):
        if address == 0x178 and self.load_pending:
            bank = self.csr[0x150]
            self.csr[0x14C] = (self.csr.get(0x14C, 0) & ~(8 << bank)) | (2 << bank)
            self.csr[0x160 if bank else 0x15C] = 229376
            self.csr[0x178] = 0x10 if self.metadata_error else 0
            self.load_pending = False
        value = self.csr.get(address, 0)
        self.events.append(("read32", address, value))
        return value

    def write32(self, address, value):
        if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
            raise AssertionError("transport received a partial/out-of-range CSR value")
        self.events.append(("write32", address, value))
        self.csr[address] = value
        if address == 0x108:
            self.csr[0x10C] = 0x3B
            self.csr[0x260] = 0x23
        elif address == 0x154 and value == 1:
            bank = self.csr[0x150]
            self.csr[0x14C] = self.csr.get(0x14C, 0) | (8 << bank)
            self.csr[0x178] = 4
            self.csr[0x160 if bank else 0x15C] = 0
            self.load_pending = True
        elif address == 0x154 and value == 2:
            self.csr[0x144] = self.csr[0x158]
            self.csr[0x14C] = (self.csr[0x14C] & ~1) | self.csr[0x150]
        elif address == 0x374:
            self.csr[0x370] = 0
        elif address == 0x36C:
            self.csr[0x368] = value
        elif address == 0x320:
            self.csr[0x370] = self.admission
            if not self.admission:
                self.csr[0x324] = 1 if self.hold_busy else self.completion_status
                self.csr.update(self.done_packets.pop(0))
            self.output_copied = False
            if self.start_error:
                raise self.start_error
        elif address == 0x2A0:
            if not self.output_copied:
                raise AssertionError("ACK before C2H output copy")
            if value != self.csr[0x338]:
                raise AssertionError("ACK identity mismatch")
            self.csr[0x324] = 8
            self.output[0] = 0xFF  # Physical slot reuse must not change owned bytes.

    def h2c_write_local(self, channel, data, local_offset, chunk_bytes):
        if channel != 1 or not 0 <= local_offset < 0x80000000 or chunk_bytes <= 0:
            raise AssertionError("DDR1-local addressing or chunk contract violated")
        self.events.append(("h2c", channel, local_offset, len(data), hashlib.sha256(data).hexdigest()))
        return len(data) - int(self.short_h2c)

    def c2h_read_local(self, channel, size, local_offset, chunk_bytes):
        if (channel, size) != (1, 1376256) or not 0 <= local_offset < 0x80000000:
            raise AssertionError("incorrect GU output address/size")
        self.events.append(("c2h", channel, local_offset, size))
        self.output_copied = True
        return memoryview(self.output)[:-1] if self.short_c2h else memoryview(self.output)


class GuOnlyBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="gu_only_transport_")
        root = Path(cls.directory.name)
        cls.records = {}
        for name, size in SIZES.items():
            path = root / (name + ".bin")
            with path.open("wb") as stream:
                stream.truncate(size)
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                while chunk := stream.read(1 << 20):
                    digest.update(chunk)
            cls.records[name] = ArtifactRecord(path, size, digest.hexdigest())

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def make(self, **options):
        transport = ScriptedTransport()
        catalog = Catalog(self.records)
        backend = GuOnlyXdmaBackend(transport, SimpleNamespace(original=catalog),
                                    timeout_s=0.03, poll_interval_s=0, **options)
        return backend, transport, catalog

    def stage(self, **options):
        backend, transport, catalog = self.make(**options)
        self.assertEqual(backend.stage_gu_layer(0, 7), 1)
        return backend, transport, catalog

    def assert_retained(self, backend, transport):
        self.assertEqual(backend.lease, (0, 7, 1))
        self.assertIsNotNone(backend.poisoned)
        self.assertTrue(backend.diagnostics)
        self.assertFalse(any(x[0:2] == ("write32", 0x2A0) for x in transport.events))
        with self.assertRaisesRegex(RuntimeContractError, "retains failed lease"):
            backend.stage_gu_layer(1, 8)

    def test_actual_CSR_DMA_two_cohort_stage_copy_ACK_and_release_order(self):
        backend, transport, catalog = self.stage()
        self.assertEqual(catalog.requests, [(0, name) for name in SIZES])
        self.assertEqual([(x[2], x[3]) for x in transport.events if x[0] == "h2c"],
                         [(0, 29360128), (0x01C00000, 29360128), (0x07400000, 7340032)])
        self.assertEqual(backend.staged_identity[0]["artifacts"][2]["sha256"], self.records["mlp_gate_meta"].sha256)
        for cohort in (0, 1):
            result = backend.run_gu(descriptor(cohort), INPUT)
            self.assertIsInstance(result.payload, bytes)
            copied_first = result.payload[0]
            with self.assertRaises(RuntimeContractError):
                backend.release_gu_layer(0, 7)
            backend.ack_gu(10 + cohort)
            self.assertEqual(result.payload[0], copied_first)
        backend.release_gu_layer(0, 7)
        self.assertIsNone(backend.lease)
        self.assertTrue(backend.quiescent())
        writes = [x for x in transport.events if x[0] == "write32"]
        self.assertEqual([x[2] for x in writes if x[1] == 0x30C], [1, 1])
        self.assertEqual([x[2] for x in writes if x[1] in (0x134, 0x138, 0x170)], [0] * 7)
        self.assertFalse(any(x[1] in (0x110, 0x174) for x in writes))
        self.assertEqual(sum(x[1] == 0x36C for x in writes), 1)
        self.assertEqual([x[2] for x in writes if x[1] == 0x124], [0x10000000, 0x11800000])
        self.assertEqual([x[2] for x in writes if x[1] == 0x128], [0x10100000, 0x11900000])
        for index, event in enumerate(transport.events):
            if event[:2] == ("write32", 0x320):
                self.assertEqual(transport.events[index + 1][:2], ("read32", 0x370))
            if event[:2] == ("write32", 0x2A0):
                last_start = max(i for i in range(index) if transport.events[i][:2] == ("write32", 0x320))
                self.assertTrue(any(x[0] == "c2h" for x in transport.events[last_start:index]))
        with self.assertRaisesRegex(RuntimeContractError, "epoch was reused"):
            backend.stage_gu_layer(1, 7)
        target = os.environ.get("HOST_GU_ONLY_EVIDENCE_DIR")
        if target:
            (Path(target) / "backend_transport_trace.json").write_text(json.dumps({
                "scope": "scripted CPU observations; not hardware simulation",
                "artifact_sha256": {k: v.sha256 for k, v in self.records.items()},
                "events": transport.events,
            }, indent=2) + "\n")

    def test_ABI_and_Attention_identity_rejected_before_any_DMA_or_callback(self):
        for address, value in ((0x104, 0x60000), (0x300, 0x4D4C0001),
                               (0x304, 0x1F), (0x000, 0), (0x004, 0)):
            with self.subTest(address=address):
                calls = []
                backend, transport, _ = self.make(attention_callback=lambda *x: calls.append(x))
                transport.csr[address] = value
                with self.assertRaises(RuntimeContractError):
                    backend.run_attention(0, 0, None)
                self.assertFalse(calls)
                self.assertFalse(any(x[0] in ("h2c", "write32") for x in transport.events))

    def test_Attention_is_explicit_application_callback_after_real_discovery(self):
        calls = []
        backend, transport, _ = self.make(attention_callback=lambda *x: calls.append(x) or "normalized")
        self.assertEqual(backend.run_attention(1, 3, "previous"), "normalized")
        self.assertEqual(calls, [(1, 3, "previous")])
        self.assertTrue(any(x[:2] == ("read32", 0x000) for x in transport.events))
        backend.attention_callback = None
        with self.assertRaisesRegex(RuntimeContractError, "callback is required"):
            backend.run_attention(0, 0, None)

    def test_metadata_hash_size_and_padding_stop_before_any_H2C(self):
        for fault in ("hash", "size", "padding"):
            with self.subTest(fault=fault):
                backend, transport, catalog = self.make()
                old = self.records["mlp_gate_meta"]
                if fault == "padding":
                    path = Path(self.directory.name) / "bad_padding.bin"
                    payload = bytearray(old.path.read_bytes())
                    payload[32 * 113 + 31] = 1
                    path.write_bytes(payload)
                    bad = ArtifactRecord(path, old.size, hashlib.sha256(payload).hexdigest())
                else:
                    bad = ArtifactRecord(old.path, old.size - int(fault == "size"),
                                         "0" * 64 if fault == "hash" else old.sha256)
                catalog.records["mlp_gate_meta"] = bad
                with self.assertRaises(RuntimeContractError):
                    backend.stage_gu_layer(0, 7)
                self.assertFalse(any(x[0] == "h2c" for x in transport.events))
                self.assert_retained(backend, transport)

    def test_metadata_DMA_error_retains_epoch_without_COMMIT(self):
        backend, transport, _ = self.make()
        transport.metadata_error = True
        with self.assertRaisesRegex(RuntimeContractError, "metadata DMA"):
            backend.stage_gu_layer(0, 7)
        self.assertFalse(any(x == ("write32", 0x154, 2) for x in transport.events))
        self.assert_retained(backend, transport)

    def test_short_weight_H2C_stops_before_metadata_LOAD(self):
        backend, transport, _ = self.make()
        transport.short_h2c = True
        with self.assertRaisesRegex(RuntimeContractError, "short GU XDMA H2C"):
            backend.stage_gu_layer(0, 7)
        self.assertFalse(any(x[:2] == ("write32", 0x154) for x in transport.events))
        self.assert_retained(backend, transport)

    def test_invalid_REC576_is_rejected_before_input_DMA_or_START(self):
        backend, transport, _ = self.stage()
        count = len(transport.events)
        invalid = bytearray(INPUT)
        invalid[575] = 1
        with self.assertRaises(ValueError):
            backend.run_gu(descriptor(), invalid)
        self.assertFalse(any(x[0] == "h2c" or x[:2] == ("write32", 0x320) for x in transport.events[count:]))
        self.assertEqual(backend.lease, (0, 7, 1))
        self.assertIsNone(backend.pending)

    def test_short_input_H2C_retains_lease_without_START(self):
        backend, transport, _ = self.stage()
        transport.short_h2c = True
        with self.assertRaisesRegex(RuntimeContractError, "short GU XDMA H2C"):
            backend.run_gu(descriptor(), INPUT)
        self.assertFalse(any(x[:2] == ("write32", 0x320) for x in transport.events))
        self.assert_retained(backend, transport)

    def test_START_rejection_is_read_immediately_and_never_waits_or_ACKs(self):
        backend, transport, _ = self.stage()
        transport.admission = 0x1010
        transport.start_error = OSError("scripted SLVERR")
        with self.assertRaisesRegex(RuntimeContractError, "admission rejected:0x00001010"):
            backend.run_gu(descriptor(), INPUT)
        start = next(i for i, x in enumerate(transport.events) if x[:2] == ("write32", 0x320))
        self.assertEqual(transport.events[start + 1], ("read32", 0x370, 0x1010))
        self.assertFalse(any(x[0] == "c2h" for x in transport.events))
        self.assertEqual(backend.pending, descriptor())
        self.assert_retained(backend, transport)

    def test_unproven_START_MMIO_failure_is_not_reported_as_success(self):
        backend, transport, _ = self.stage()
        transport.start_error = OSError("scripted pwrite failure")
        with self.assertRaisesRegex(RuntimeContractError, "without acceptance proof"):
            backend.run_gu(descriptor(), INPUT)
        self.assertFalse(any(x[0] == "c2h" for x in transport.events))
        self.assert_retained(backend, transport)

    def test_wrong_DONE_identity_error_or_counts_prevents_C2H_and_ACK(self):
        for address, value in ((0x328, 2), (0x338, 99), (0x330, 8), (0x334, 2),
                               (0x348, 73727), (0x34C, 1376255), (0x350, 0x2103), (0x364, 1791)):
            with self.subTest(address=address):
                backend, transport, _ = self.stage()
                transport.done_packets[0][address] = value
                with self.assertRaisesRegex(RuntimeContractError, "DONE identity/error/count"):
                    backend.run_gu(descriptor(), INPUT)
                self.assertFalse(any(x[0] == "c2h" for x in transport.events))
                self.assert_retained(backend, transport)

    def test_reset_required_and_timeout_retain_failed_hardware_owner(self):
        for fault in ("reset", "timeout"):
            with self.subTest(fault=fault):
                backend, transport, _ = self.stage()
                transport.completion_status = 0x12 if fault == "reset" else 10
                transport.hold_busy = fault == "timeout"
                with self.assertRaisesRegex(RuntimeContractError, "reset_required" if fault == "reset" else "timeout"):
                    backend.run_gu(descriptor(), INPUT)
                self.assert_retained(backend, transport)

    def test_short_output_and_wrong_ACK_never_release_owned_epoch(self):
        backend, transport, _ = self.stage()
        transport.short_c2h = True
        with self.assertRaisesRegex(RuntimeContractError, "short GU XDMA C2H"):
            backend.run_gu(descriptor(), INPUT)
        self.assertFalse(backend.output_copied)
        self.assert_retained(backend, transport)
        backend, transport, _ = self.stage()
        backend.run_gu(descriptor(), INPUT)
        with self.assertRaisesRegex(RuntimeContractError, "matching identity"):
            backend.ack_gu(11)
        self.assertEqual(backend.pending, descriptor())
        self.assertFalse(any(x[:2] == ("write32", 0x2A0) for x in transport.events))

    def test_prefetch_only_GU_to_Host_and_immutable_payload_survives_file_change(self):
        backend, transport, catalog = self.make()
        backend.initialize_shared_mode()
        backend.prefetch_gu_layer(0)
        self.assertFalse(any(x[0] == "h2c" for x in transport.events))
        self.assertEqual(catalog.requests, [(0, name) for name in SIZES])
        # Prefetch stores owned, hash-checked bytes. A later catalog mutation
        # cannot substitute a new file into this already-owned stage payload.
        catalog.records["mlp_gate_meta"] = ArtifactRecord(Path("missing"), 7340032, "0" * 64)
        backend.stage_gu_layer(0, 7)
        self.assertEqual(len(catalog.requests), 3)
        self.assertEqual(backend.staged_identity[0]["artifacts"][2]["sha256"], self.records["mlp_gate_meta"].sha256)

    def test_pipeline_uses_real_adapter_methods_with_explicit_boundary_callbacks(self):
        calls = []
        backend, transport, _ = self.make(attention_callback=lambda c, l, p: calls.append((c, l, p)))
        transport.done_packets = [dict(done_packet(c, command=c), **{}) for c in (0, 1)]
        for packet in transport.done_packets:
            packet[0x330] = 1
            packet[0x33C] = 91
        weights = DownWeights(np.zeros((448, 16, 32), np.int8),
                              np.zeros((448, 16), np.uint8), np.zeros((448, 16), np.uint8), layer_id=0)
        pipeline = GuOnlyPipeline(backend, lambda layer: weights,
                                  lambda c, l, output: (c, l, int(output[0, 0])),
                                  prepare_gu=lambda normalized: INPUT,
                                  cpu_down=lambda payload, handle: np.zeros((16, 4096), np.int64), layers=1)
        report = pipeline.run(request_id=91)
        self.assertEqual(report["outputs"], ((0, 0, 0), (1, 0, 0)))
        self.assertEqual((report["hardware_commands"], report["hardware_down_commands"]), (4, 0))
        self.assertEqual(calls, [(0, 0, None), (1, 0, None)])
        self.assertIsNone(backend.lease)
        self.assertFalse(pipeline.host_leases)
        # CPU Down/Attention here are explicit scheduling fixtures. The separate
        # fullshape test proves integer Down; this test only binds the transport.

    def test_existing_XdmaSession_applies_aperture_once_and_writes_four_bytes(self):
        session = XdmaSession(event=None)  # Constructor opens no descriptors.
        session._fds = {"h2c": 501, "c2h": 502, "user": 503}
        with patch("host.scalellm_runtime.os.pwrite", side_effect=lambda fd, data, offset: len(data)) as write, \
             patch("host.scalellm_runtime.os.pread", return_value=b"abcd") as read:
            session.write32(0x30C, 1)
            self.assertEqual(write.call_args.args, (503, struct.pack("<I", 1), 0x30C))
            self.assertEqual(session.h2c_write_local(1, b"1234", 0x10000000, 4), 4)
            self.assertEqual(write.call_args.args, (501, b"1234", 0x90000000))
            self.assertEqual(session.c2h_read_local(1, 4, 0x10100000, 4), b"abcd")
            self.assertEqual(read.call_args.args, (502, 4, 0x90100000))
        session._fds.clear()  # Fake integers were never opened and must not close.


if __name__ == "__main__":
    unittest.main()
