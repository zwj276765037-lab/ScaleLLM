"""GU-only CPU task graph and separate FPGA/Host layer leases.

Transport is supplied by a backend; this module never submits hardware Down.
It does not claim board execution, implement a fake completion for CPU Down,
or replace the application's Attention/residual/RMSNorm boundary callbacks.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import threading
from typing import Mapping, Protocol

import numpy as np

from . import scalellm_mlp_gu_only_abi as abi
from .scalellm_mlp_gu_only import DownWeights, prepare_and_run_down
from .scalellm_mlp_linear import prepare_gate_up_input_from_normalized_fp32
from .scalellm_runtime import RuntimeContractError


def validate_gu_only_abi(identity: Mapping[str, int]):
    for key, expected in abi.IDS.items():
        if type(identity.get(key)) is not int or identity[key] != expected:
            raise RuntimeContractError(f"GU-only runtime identity {key} mismatch")
    if type(identity.get("capabilities")) is not int or identity["capabilities"] != abi.CAPABILITIES:
        raise RuntimeContractError("GU-only requires caps0x1d, including no hardware DOWN")


@dataclass(frozen=True)
class GuDescriptor:
    command_id: int
    request_id: int
    cohort_id: int
    layer_id: int
    buffer_id: int
    buffer_generation: int
    metadata_generation: int
    epoch_id: int
    opcode: int = 1
    down_half0_base: int = 0
    down_half1_base: int = 0

    def __post_init__(self):
        for value in self.__dict__.values():
            if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
                raise RuntimeContractError("descriptor fields must be U32 integers")
        if self.opcode != 1:
            raise RuntimeContractError("GU-only accepts complete32-bit opcode1; hardware DOWN is forbidden")
        if self.down_half0_base or self.down_half1_base:
            raise RuntimeContractError("reserved Down addresses must be zero")
        if self.cohort_id not in (0, 1) or not 0 <= self.layer_id < 32 or not 0 <= self.buffer_id < 6 or self.buffer_id // 3 != self.cohort_id:
            raise RuntimeContractError("GU descriptor cohort/layer/buffer identity mismatch")
        if not self.buffer_generation or not self.metadata_generation or not self.epoch_id:
            raise RuntimeContractError("generation/metadata/epoch must be nonzero")

    def words(self):
        base = 0x10000000 + self.buffer_id * 0x800000
        return (self.command_id, self.request_id, (self.buffer_id << 16) | self.cohort_id,
                self.layer_id, 1, abi.IDS["numeric_format"], base, base + 0x100000,
                73728, 1376256, self.buffer_generation, self.metadata_generation,
                self.epoch_id, 0, 0x01C00000, 0, 0)

    def pack(self):
        return b"".join(word.to_bytes(4, "little") for word in self.words())


@dataclass(frozen=True)
class GuCompletion:
    descriptor: GuDescriptor
    payload: bytes | bytearray | memoryview
    error: int = 0
    input_bytes: int = 73728
    output_bytes: int = 1376256
    records: int = 1792


class GuOnlyBackend(Protocol):
    def discover(self) -> Mapping[str, int]: ...
    def stage_gu_layer(self, layer_id: int, epoch_id: int) -> int:
        """Stage only GU artifacts/metadata, commit epoch; return generation."""
    def run_attention(self, cohort: int, layer: int, previous):
        """Execute existing Attention and Host residual/RMSNorm boundary."""
    def run_gu(self, descriptor: GuDescriptor, payload: bytes) -> GuCompletion: ...
    def ack_gu(self, command_id: int) -> None: ...
    def quiescent(self) -> bool: ...
    def release_gu_layer(self, layer_id: int, epoch_id: int) -> None: ...
    def prefetch_gu_layer(self, layer_id: int) -> None: ...


@dataclass(frozen=True)
class HostDownLease:
    layer_id: int
    cohort_id: int
    weights: DownWeights
    gu_payload: bytes


class GuOnlyPipeline:
    """Two cohorts; FPGA epoch can release while CPU Down retains old weights.

    Next-layer cohort work waits for its CPU Down AND residual consumer.
    Layer starts are conservative: both prior cohort consumers retire before
    the next epoch executes. Prefetch may overlap outstanding CPU work.
    Callbacks provide actual application boundaries; mock backends in CPU tests
    demonstrate scheduling contracts, never RTL or model correctness.
    """
    def __init__(self, backend: GuOnlyBackend, weights_for_layer, after_down, *,
                 cpu_down=prepare_and_run_down,
                 prepare_gu=prepare_gate_up_input_from_normalized_fp32, layers=32):
        if type(layers) is not int or not 1 <= layers <= 32:
            raise ValueError("layers must be in1..32")
        self.backend, self.weights_for_layer, self.after_down = backend, weights_for_layer, after_down
        self.cpu_down, self.prepare_gu, self.layers = cpu_down, prepare_gu, layers
        self.host_leases = {}
        self.fpga_lease = None
        self.events = []
        self.lock = threading.Lock()
        self.command_sequence = 0
        self.epoch_sequence = 0
        self.buffer_generations = {buffer: 0 for buffer in range(6)}

    def _event(self, name, **identity):
        with self.lock:
            self.events.append({"event": name, **identity})

    def _consume_down(self, lease):
        self._event("host_down_start", layer=lease.layer_id, cohort=lease.cohort_id)
        output = np.asarray(self.cpu_down(lease.gu_payload, lease.weights))
        if output.dtype.kind not in "iu" or output.shape != (16, 4096) or np.any(output < -2147483648) or np.any(output > 2147483647):
            raise RuntimeContractError("CPU Down returned invalid S32/F16 cohort16 output")
        self._event("host_down_done", layer=lease.layer_id, cohort=lease.cohort_id)
        consumed = self.after_down(lease.cohort_id, lease.layer_id, output)
        with self.lock:
            del self.host_leases[(lease.layer_id, lease.cohort_id)]
        self._event("host_consumer_retired", layer=lease.layer_id, cohort=lease.cohort_id)
        return consumed

    def run(self, initial=(None, None), *, request_id=0):
        validate_gu_only_abi(self.backend.discover())
        if self.host_leases or self.fpga_lease is not None:
            raise RuntimeContractError("prior failed/unretired leases prohibit a new run")
        if type(request_id) is not int or not 0 <= request_id <= 0xFFFFFFFF:
            raise ValueError("request_id must fit U32")
        previous = list(initial)
        if len(previous) != 2:
            raise ValueError("exactly two cohort initial states required")
        pending = {}
        gu_commands = attention_commands = 0
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="gu_only_down") as pool:
            for layer in range(self.layers):
                for cohort, future in pending.items():
                    previous[cohort] = future.result()
                pending = {}
                weights = self.weights_for_layer(layer)
                if not isinstance(weights, DownWeights) or weights.layer_id != layer:
                    raise RuntimeContractError("immutable layer-specific Down handle required")
                self.epoch_sequence += 1
                epoch = self.epoch_sequence
                self.fpga_lease = (layer, epoch)
                generation = self.backend.stage_gu_layer(layer, epoch)
                self._event("fpga_epoch_acquire", layer=layer, epoch=epoch)
                copied_and_acked = set()
                for cohort in (0, 1):
                    # A known CPU failure stops new submissions; in-flight work
                    # remains owned and is never renamed as a successful layer.
                    for future in pending.values():
                        if future.done():
                            future.result()
                    normalized = self.backend.run_attention(cohort, layer, previous[cohort])
                    attention_commands += 1
                    payload = self.prepare_gu(normalized)
                    if len(memoryview(payload).cast("B")) != 73728:
                        raise RuntimeContractError("GU input must contain exactly73728 bytes")
                    buffer = cohort * 3 + layer % 3
                    self.buffer_generations[buffer] += 1
                    descriptor = GuDescriptor(self.command_sequence, request_id, cohort, layer,
                                              buffer, self.buffer_generations[buffer], generation, epoch)
                    self.command_sequence += 1
                    result = self.backend.run_gu(descriptor, payload)
                    gu_commands += 1
                    if not isinstance(result, GuCompletion) or result.descriptor != descriptor or result.error or (result.input_bytes, result.output_bytes, result.records) != (73728, 1376256, 1792):
                        raise RuntimeContractError("GU completion identity/error/count mismatch")
                    owned_output = memoryview(result.payload).cast("B").tobytes()
                    if len(owned_output) != 1376256:
                        raise RuntimeContractError("GU output copy has wrong size")
                    lease = HostDownLease(layer, cohort, weights, owned_output)
                    with self.lock:
                        self.host_leases[(layer, cohort)] = lease
                    self._event("gu_output_copied", layer=layer, cohort=cohort, command=descriptor.command_id)
                    self.backend.ack_gu(descriptor.command_id)
                    if not self.backend.quiescent():
                        raise RuntimeContractError("GU ACK did not establish drained hardware")
                    copied_and_acked.add(cohort)
                    self._event("gu_acked", layer=layer, cohort=cohort, command=descriptor.command_id)
                    pending[cohort] = pool.submit(self._consume_down, lease)
                if copied_and_acked != {0, 1} or not self.backend.quiescent():
                    raise RuntimeContractError("cannot release incomplete FPGA layer lease")
                self.backend.release_gu_layer(layer, epoch)
                self.fpga_lease = None
                self._event("fpga_epoch_release", layer=layer, epoch=epoch)
                if layer + 1 < self.layers:
                    self.backend.prefetch_gu_layer(layer + 1)
            for cohort, future in pending.items():
                previous[cohort] = future.result()
        return {"outputs": tuple(previous), "attention_commands": attention_commands,
                "gu_commands": gu_commands, "hardware_commands": attention_commands + gu_commands,
                "cpu_down_tasks": self.layers * 2, "hardware_down_commands": 0,
                "events": tuple(self.events)}
