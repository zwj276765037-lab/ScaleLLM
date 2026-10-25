"""Actual v7 CSR/XDMA binding, compatible with existing XdmaSession methods.

No device is opened by construction. Applications pass their owned session,
strict GuOnlyArtifactManifest and existing Attention/boundary callback. This
adapter never calls the old full-MLP backend/stager or stages Down artifacts.
CSR addresses are control-BAR register offsets. DMA offsets and descriptor
data addresses are physicalDDR1-local; XdmaSession alone adds the Host channel
aperture. Every write32 is one full32-bit CSR write.
"""
from __future__ import annotations

import threading
import time

import numpy as np

from . import scalellm_mlp_gu_only_abi as abi
from .scalellm_memory import (local_to_host, mlp_meta_bases,
                              MLP_GATE_UP_BYTES_PER_CHANNEL, MLP_GATE_META_BYTES)
from .scalellm_mlp_gu_only_runtime import (GuCompletion, GuDescriptor,
                                           validate_gu_only_abi)
from .scalellm_mlp_linear import unpack_a8_rec576
from .scalellm_runtime import RuntimeContractError


class GuOnlyXdmaBackend:
    """Synchronous GU transport with immutable stage payloads and retained faults.

    Attention callback(cohort,layer,previous) must execute the existing Attention
    invocation/residual/RMSNorm boundary and return its normalized FP32 tensor.
    It is an explicit application interface; no fake Attention is supplied.
    On any accepted-operation failure this object stops new work and retains
    its lease/diagnostics. Recovery requires an explicit new hardware session.
    """
    def __init__(self, session, artifacts, *, attention_callback=None,
                 timeout_s=10.0, poll_interval_s=0.0005, chunk_bytes=8 << 20):
        if timeout_s <= 0 or poll_interval_s < 0 or type(chunk_bytes) is not int or chunk_bytes <= 0:
            raise ValueError("invalid GU transport timeout/chunk configuration")
        self.session, self.artifacts, self.attention_callback = session, artifacts, attention_callback
        self.timeout_s, self.poll_interval_s, self.chunk_bytes = timeout_s, poll_interval_s, chunk_bytes
        self.lock = threading.RLock()
        self.initialized = False
        self.poisoned = None
        self.lease = None
        self.pending = None
        self.output_copied = False
        self.acked_cohorts = set()
        self.seen_epochs = set()
        self.seen_commands = set()
        self.metadata_sequence = 0
        self.prefetched = {}
        self.diagnostics = []
        self.staged_identity = []

    def _read(self, address):
        value = self.session.read32(address)
        if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
            raise RuntimeContractError(f"non-U32 CSR read at0x{address:03x}")
        return value

    def _write(self, address, value):
        if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
            raise RuntimeContractError("CSR value must be full U32")
        self.session.write32(address, value)

    def _healthy(self):
        if self.poisoned is not None:
            raise RuntimeContractError(f"GU backend retains failed lease: {self.poisoned}")

    def _snapshot_failure(self, reason):
        if self.poisoned is None:
            self.poisoned = str(reason)
        snapshot = {"reason": str(reason), "lease": self.lease, "pending": self.pending}
        for address in (0x324, 0x370, 0x338, 0x33C, 0x340, 0x344, 0x348, 0x34C, 0x350, 0x364, 0x368):
            try:
                snapshot[f"0x{address:03x}"] = self._read(address)
            except Exception as error:
                snapshot[f"0x{address:03x}"] = f"unavailable:{type(error).__name__}"
        self.diagnostics.append(snapshot)

    def _status(self):
        status = self._read(abi.CSR_MLP_JOB_STATUS)
        if status & 16:
            raise RuntimeContractError("GU hardware reset_required; preserve DONE before external recovery")
        return status

    def _wait(self, description, predicate):
        deadline = time.monotonic() + self.timeout_s
        while not predicate():
            self._status()
            if time.monotonic() >= deadline:
                raise RuntimeContractError(f"timeout waiting for GU {description}")
            if self.poll_interval_s:
                time.sleep(self.poll_interval_s)

    def discover(self):
        keys = {"numeric_format": 0x100, "mlp_control_abi": 0x104, "linear_abi": 0x300,
                "buffer_layout": 0x308, "memory_layout": 0x2B8}
        result = {key: self._read(address) for key, address in keys.items()}
        # W4F5 is artifact identity, not a readable runtime ABI register.
        result["weight_layout"] = abi.IDS["weight_layout"]
        result["capabilities"] = self._read(0x304)
        validate_gu_only_abi(result)
        if self._read(0x000) != 0x48384103 or self._read(0x004) != 0x00020000:
            raise RuntimeContractError("Attention format/ABI mismatch before callback use")
        return result

    def initialize_shared_mode(self):
        with self.lock:
            self._healthy()
            self.discover()
            status = self._status()
            if status & 7 or not status & 8:
                raise RuntimeContractError("cannot initialize GU with active/unACKed/faulted hardware")
            if self._read(0x2A8) & 3:
                raise RuntimeContractError("GU maintenance is pending")
            if (self._read(0x10C) & 0x1F) != 0x1B:
                self._wait("owner readiness", lambda: bool(self._read(0x10C) & 0x20))
                self._write(0x108, 3)
                self._wait("SHARED mode", lambda: (self._read(0x10C) & 0x1F) == 0x1B)
            self.initialized = True

    def _require_idle(self):
        status = self._status()
        if status & 7 or not status & 8 or self._read(0x2A8) & 3 or self._read(0x260) & 0x1C:
            raise RuntimeContractError("GU is not idle, drained and acknowledged")

    def _gu_records(self, layer):
        catalog = self.artifacts.original
        names = ("mlp_gate_up_c0", "mlp_gate_up_c1", "mlp_gate_meta")
        sizes = (MLP_GATE_UP_BYTES_PER_CHANNEL, MLP_GATE_UP_BYTES_PER_CHANNEL, MLP_GATE_META_BYTES)
        payloads, identity = [], []
        for name, size in zip(names, sizes, strict=True):
            record = catalog.layer_artifact(layer, name)
            if record.size != size:
                raise RuntimeContractError(f"GU artifact size mismatch:{name}")
            data = record.read_verified()
            if len(data) != size:
                raise RuntimeContractError(f"GU artifact changed size:{name}")
            payloads.append(data)
            identity.append({"name": name, "size": size, "sha256": record.sha256, "path": str(record.path)})
        metadata = np.frombuffer(payloads[2], np.uint8).reshape(229376, 32)
        if np.any(metadata[:, 28:]):
            raise RuntimeContractError("GU weight metadata padding is nonzero")
        return tuple(payloads), tuple(identity)

    def _h2c(self, data, local_address):
        local_to_host(1, local_address, len(data))
        count = self.session.h2c_write_local(1, data, local_address, self.chunk_bytes)
        if count != len(data):
            raise RuntimeContractError("short GU XDMA H2C write")

    def _clear_admission(self):
        old = self._read(0x370)
        if old:
            self.diagnostics.append({"prior_admission_error": old})
        self._write(0x374, 1)
        if self._read(0x370) != 0:
            raise RuntimeContractError("GU admission diagnostic did not clear")

    def stage_gu_layer(self, layer_id, epoch_id):
        if type(layer_id) is not int or not 0 <= layer_id < 32 or type(epoch_id) is not int or not 0 < epoch_id <= 0xFFFFFFFF:
            raise RuntimeContractError("invalid GU layer/epoch")
        with self.lock:
            self._healthy()
            if not self.initialized:
                self.initialize_shared_mode()
            if self.lease is not None or self.pending is not None or epoch_id in self.seen_epochs:
                raise RuntimeContractError("GU layer lease is active or epoch was reused")
            self._require_idle()
            self.seen_epochs.add(epoch_id)
            self.metadata_sequence += 1
            generation = self.metadata_sequence
            self.lease = (layer_id, epoch_id, generation)
            self.acked_cohorts = set()
            try:
                payloads, identities = self.prefetched.pop(layer_id) if layer_id in self.prefetched else self._gu_records(layer_id)
                # Validate every immutable payload/hash/padding before any DMA.
                bank = 1 - (self._read(0x14C) & 1)
                if self._read(0x14C) & 0x18:
                    raise RuntimeContractError("GU metadata bank already loading")
                meta_base = mlp_meta_bases(bank)[0]
                for data, address in zip(payloads, (0, 0x01C00000, meta_base), strict=True):
                    self._h2c(data, address)
                self.staged_identity.append({"layer": layer_id, "epoch": epoch_id, "artifacts": identities})
                self._write(0x150, bank)
                self._write(0x16C, meta_base)
                self._write(0x170, 0)
                self._write(0x154, 1)
                # A reused inactive bank may still expose the previous full
                # count until LOAD actually starts. Observe its loading state
                # before accepting a count; the production load is229376 beats.
                self._wait("GU-only metadata LOAD start",
                           lambda: bool(self._read(0x14C) & (8 << bank)))

                def loaded():
                    self._status()
                    status = self._read(0x178)
                    if status & 0x10:
                        raise RuntimeContractError("GU metadata DMA reported error")
                    return not status & 4 and self._read(0x160 if bank else 0x15C) == 229376

                self._wait("GU-only metadata LOAD", loaded)
                self._write(0x158, generation)
                self._write(0x154, 2)
                self._wait("GU metadata COMMIT", lambda: self._read(0x144) == generation and (self._read(0x14C) & (1 | (2 << bank))) == (bank | (2 << bank)))
                for address, value in ((0x11C, layer_id), (0x12C, 0), (0x130, 0x01C00000), (0x134, 0), (0x138, 0)):
                    self._write(address, value)
                self._clear_admission()
                self._write(0x36C, epoch_id)
                error = self._read(0x370)  # ordered read after commit result/B.
                if error or self._read(0x368) != epoch_id:
                    raise RuntimeContractError(f"GU epoch rejected:0x{error:08x}")
                return generation
            except BaseException as error:
                self._snapshot_failure(error)
                raise

    def run_attention(self, cohort, layer, previous):
        self._healthy()
        if not self.initialized:
            self.initialize_shared_mode()
        if self.attention_callback is None:
            raise RuntimeContractError("application Attention/residual/RMSNorm callback is required")
        return self.attention_callback(cohort, layer, previous)

    def _check_done(self, descriptor):
        expected = ((0x328, 1), (0x32C, descriptor.buffer_generation), (0x330, descriptor.epoch_id),
                    (0x334, descriptor.metadata_generation), (0x338, descriptor.command_id),
                    (0x33C, descriptor.request_id), (0x340, (descriptor.buffer_id << 16) | descriptor.cohort_id),
                    (0x344, descriptor.layer_id), (0x348, 73728), (0x34C, 1376256), (0x350, 0), (0x364, 1792))
        for address, value in expected:
            if self._read(address) != value:
                raise RuntimeContractError(f"GU DONE identity/error/count mismatch at0x{address:03x}")

    def run_gu(self, descriptor: GuDescriptor, payload):
        with self.lock:
            self._healthy()
            if not isinstance(descriptor, GuDescriptor) or descriptor.opcode != 1:
                raise RuntimeContractError("hardware Down/unknown opcode forbidden")
            if self.lease != (descriptor.layer_id, descriptor.epoch_id, descriptor.metadata_generation) or self.pending is not None or descriptor.command_id in self.seen_commands or descriptor.cohort_id in self.acked_cohorts:
                raise RuntimeContractError("GU descriptor does not own current epoch/cohort lease")
            self._require_idle()
            unpack_a8_rec576(payload, groups=128)  # strict payload checks before DMA/START.
            immutable = memoryview(payload).cast("B").tobytes()
            try:
                self._h2c(immutable, descriptor.words()[6])
                self._clear_admission()
                for field, value in zip(abi.DESCRIPTOR_FIELDS, descriptor.words(), strict=True):
                    self._write(field["csr"], value)
                self.pending = descriptor
                self.output_copied = False
                self.seen_commands.add(descriptor.command_id)
                write_error = None
                try:
                    self._write(0x320, 1)
                except OSError as error:
                    write_error = error
                admission = self._read(0x370)  # never infer acceptance from pwrite length.
                if admission:
                    raise RuntimeContractError(f"GU START admission rejected:0x{admission:08x}")
                if write_error is not None:
                    raise RuntimeContractError("GU START MMIO transaction failed without acceptance proof") from write_error
                self._wait("completion", lambda: bool(self._status() & 2))
                status = self._status()
                if status & 5 or not status & 8:
                    raise RuntimeContractError("GU DONE is not successful/drained")
                self._check_done(descriptor)
                output_base = descriptor.words()[7]
                local_to_host(1, output_base, 1376256)
                result = self.session.c2h_read_local(1, 1376256, output_base, self.chunk_bytes)
                output = memoryview(result).cast("B").tobytes()
                if len(output) != 1376256:
                    raise RuntimeContractError("short GU XDMA C2H read")
                self.output_copied = True
                return GuCompletion(descriptor, output)
            except BaseException as error:
                self._snapshot_failure(error)
                raise

    def quiescent(self):
        self._healthy()
        status = self._status()
        return not status & 1 and bool(status & 8) and not (self._read(0x2A8) & 3) and not (self._read(0x260) & 0x1C)

    def ack_gu(self, command_id):
        with self.lock:
            self._healthy()
            if self.pending is None or command_id != self.pending.command_id or not self.output_copied:
                raise RuntimeContractError("GU ACK requires matching identity and owned output copy")
            try:
                if not self._status() & 2 or not self.quiescent():
                    raise RuntimeContractError("GU completion is not ACK-safe")
                self._check_done(self.pending)
                self._write(0x2A0, command_id)
                self._wait("identity ACK and job cleanup", lambda: not self._status() & 3 and self.quiescent())
                self.acked_cohorts.add(self.pending.cohort_id)
                self.pending = None
                self.output_copied = False
            except BaseException as error:
                self._snapshot_failure(error)
                raise

    def release_gu_layer(self, layer_id, epoch_id):
        with self.lock:
            self._healthy()
            if self.lease is None or self.lease[:2] != (layer_id, epoch_id) or self.pending is not None or self.acked_cohorts != {0, 1} or not self.quiescent():
                raise RuntimeContractError("cannot release GU layer before both copies/ACKs/drain")
            self.lease = None

    def prefetch_gu_layer(self, layer_id):
        with self.lock:
            self._healthy()
            if self.lease is not None or type(layer_id) is not int or not 0 <= layer_id < 32:
                raise RuntimeContractError("GU prefetch requires released FPGA layer and valid next layer")
            try:
                self.prefetched = {layer_id: self._gu_records(layer_id)}
            except BaseException as error:
                self._snapshot_failure(error)
                raise
