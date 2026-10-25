#!/usr/bin/env python3
"""Dual-cohort runtime primitives for the ScaleLLM VCU118 control ABI."""

from __future__ import annotations

import os
import selectors
import struct
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass
from enum import Enum, IntEnum
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Protocol, Tuple

from .scalellm_memory import local_to_host


class RuntimeContractError(RuntimeError):
    """Raised when software or hardware violates the frozen runtime contract."""


class CompletionFailure(RuntimeContractError):
    """Raised after a correctly identified command completes with an error."""


class Engine(Enum):
    ATTENTION = "attention"
    MLP = "mlp"


class CompletionStatus(IntEnum):
    SUCCESS = 0x00
    PROTOCOL_ERROR = 0x01
    DDR_ERROR = 0x02
    FORMAT_ERROR = 0x03
    TIMEOUT = 0x04
    MAINTENANCE_ABORT = 0x05
    INTERNAL_ERROR = 0xFF


ENGINE_OP_ID = {Engine.ATTENTION: 0, Engine.MLP: 1}


@dataclass(frozen=True)
class CommandIdentity:
    request_id: int
    command_id: int
    cohort_id: int
    buffer_id: int
    layer_id: int
    op_id: int

    def __post_init__(self) -> None:
        fields = {
            "request_id": (self.request_id, 32),
            "command_id": (self.command_id, 32),
            "cohort_id": (self.cohort_id, 16),
            "buffer_id": (self.buffer_id, 16),
            "layer_id": (self.layer_id, 6),
            "op_id": (self.op_id, 3),
        }
        for name, (value, bits) in fields.items():
            if not 0 <= value < (1 << bits):
                raise ValueError(f"{name}={value} does not fit in {bits} bits")


@dataclass(frozen=True)
class Completion:
    identity: CommandIdentity
    status: CompletionStatus


@dataclass(frozen=True)
class CompletionRegisterMap:
    request: int
    command: int
    owner: int
    layer: int
    status: int
    flags: Optional[int] = None


ATTENTION_COMPLETION = CompletionRegisterMap(
    request=0x078, command=0x07C, owner=0x080, layer=0x084,
    status=0x088)
MLP_COMPLETION = CompletionRegisterMap(
    request=0x288, command=0x28C, owner=0x290, layer=0x294,
    status=0x298, flags=0x29C)


def decode_completion(
    read32: Callable[[int], int], registers: CompletionRegisterMap
) -> Completion:
    if registers.flags is not None:
        flags = read32(registers.flags)
        if not flags & 0x1:
            raise RuntimeContractError("completion registers are not valid")
    request_id = read32(registers.request)
    command_id = read32(registers.command)
    owner = read32(registers.owner)
    layer_id = read32(registers.layer) & 0x3F
    status_word = read32(registers.status)
    buffer_id = (owner >> 16) & 0xFFFF
    status_buffer = status_word & 0xFFFF
    if status_buffer != buffer_id:
        raise RuntimeContractError(
            "completion buffer copies disagree: "
            f"owner=0x{buffer_id:04x} status=0x{status_buffer:04x}")
    try:
        status = CompletionStatus((status_word >> 19) & 0xFF)
    except ValueError as exc:
        raise RuntimeContractError(
            f"unknown completion status 0x{(status_word >> 19) & 0xFF:02x}") \
            from exc
    identity = CommandIdentity(
        request_id=request_id,
        command_id=command_id,
        cohort_id=owner & 0xFFFF,
        buffer_id=buffer_id,
        layer_id=layer_id,
        op_id=(status_word >> 16) & 0x7,
    )
    return Completion(identity=identity, status=status)


class CompletionScoreboard:
    """Tracks the one-outstanding-per-engine hardware command contract."""

    def __init__(self) -> None:
        self._outstanding: Dict[Tuple[Engine, int], CommandIdentity] = {}
        self._last_command_id = -1
        self.completed = 0

    def submit(self, engine: Engine, identity: CommandIdentity) -> None:
        expected_op = ENGINE_OP_ID[engine]
        if identity.op_id != expected_op:
            raise RuntimeContractError(
                f"{engine.value} requires op_id={expected_op}, got {identity.op_id}")
        if identity.command_id <= self._last_command_id:
            raise RuntimeContractError(
                "command_id must increase monotonically within one run")
        if any(item_engine is engine for item_engine, _ in self._outstanding):
            raise RuntimeContractError(
                f"{engine.value} already has an outstanding command")
        key = (engine, identity.command_id)
        self._outstanding[key] = identity
        self._last_command_id = identity.command_id

    def complete(self, engine: Engine, completion: Completion) -> None:
        key = (engine, completion.identity.command_id)
        expected = self._outstanding.get(key)
        if expected is None:
            raise RuntimeContractError(
                f"unexpected {engine.value} completion command_id="
                f"{completion.identity.command_id}")
        if completion.identity != expected:
            raise RuntimeContractError(
                f"{engine.value} completion identity mismatch: "
                f"expected={expected} actual={completion.identity}")
        del self._outstanding[key]
        self.completed += 1
        if completion.status is not CompletionStatus.SUCCESS:
            raise CompletionFailure(
                f"{engine.value} command {identity_text(expected)} completed "
                f"with {completion.status.name}")

    @property
    def outstanding(self) -> Tuple[Tuple[Engine, CommandIdentity], ...]:
        return tuple((engine, identity)
                     for (engine, _), identity in self._outstanding.items())


def identity_text(identity: CommandIdentity) -> str:
    return "/".join(str(value) for value in (
        identity.request_id, identity.command_id, identity.cohort_id,
        identity.buffer_id, identity.layer_id, identity.op_id))


class XdmaSession:
    """Owns persistent Linux XDMA descriptors for one complete test run."""

    def __init__(
        self,
        h2c: str = "/dev/xdma0_h2c_0",
        c2h: str = "/dev/xdma0_c2h_0",
        user: str = "/dev/xdma0_user",
        event: Optional[str] = "/dev/xdma0_events_0",
    ) -> None:
        self.paths = {"h2c": h2c, "c2h": c2h, "user": user,
                      "event": event}
        self._fds: Dict[str, int] = {}
        self._axil_lock = threading.Lock()
        self._h2c_lock = threading.Lock()
        self._c2h_lock = threading.Lock()

    def __enter__(self) -> "XdmaSession":
        if self._fds:
            raise RuntimeContractError("XDMA session is already open")
        flags = {
            "h2c": os.O_WRONLY | os.O_SYNC,
            "c2h": os.O_RDONLY | os.O_SYNC,
            "user": os.O_RDWR | os.O_SYNC,
        }
        try:
            for name, mode in flags.items():
                self._fds[name] = os.open(str(self.paths[name]), mode)
            if self.paths["event"] is not None:
                self._fds["event"] = os.open(
                    str(self.paths["event"]), os.O_RDONLY | os.O_NONBLOCK)
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def close(self) -> None:
        for fd in self._fds.values():
            os.close(fd)
        self._fds.clear()

    def _fd(self, name: str) -> int:
        try:
            return self._fds[name]
        except KeyError as exc:
            raise RuntimeContractError(
                f"XDMA {name} descriptor is not open") from exc

    def write32(self, offset: int, value: int) -> None:
        with self._axil_lock:
            written = os.pwrite(
                self._fd("user"), struct.pack("<I", value & 0xFFFF_FFFF),
                offset)
        if written != 4:
            raise RuntimeContractError(
                f"short AXI-Lite write at 0x{offset:03x}: {written}")

    def read32(self, offset: int) -> int:
        with self._axil_lock:
            data = os.pread(self._fd("user"), 4, offset)
        if len(data) != 4:
            raise RuntimeContractError(
                f"short AXI-Lite read at 0x{offset:03x}: {len(data)}")
        return struct.unpack("<I", data)[0]

    def h2c_write(
        self, data: bytes | bytearray | memoryview, offset: int,
        chunk_bytes: int,
    ) -> int:
        with self._h2c_lock:
            return self._pwrite_all(
                self._fd("h2c"), data, offset, chunk_bytes
            )

    def h2c_write_local(
        self, channel: int, data: bytes | bytearray | memoryview,
        local_offset: int, chunk_bytes: int,
    ) -> int:
        return self.h2c_write(
            data, local_to_host(channel, local_offset, len(data)), chunk_bytes
        )

    def c2h_read(self, size: int, offset: int, chunk_bytes: int) -> bytes:
        if size < 0 or chunk_bytes <= 0:
            raise ValueError("invalid C2H size/chunk_bytes")
        chunks = []
        total = 0
        with self._c2h_lock:
            while total < size:
                item = os.pread(
                    self._fd("c2h"), min(chunk_bytes, size-total),
                    offset+total,
                )
                if not item:
                    raise RuntimeContractError("C2H read made no progress")
                chunks.append(item)
                total += len(item)
        return b"".join(chunks)

    def c2h_read_into(
        self, destination: bytearray | memoryview, offset: int,
        chunk_bytes: int,
    ) -> int:
        if chunk_bytes <= 0:
            raise ValueError("chunk_bytes must be positive")
        view = memoryview(destination).cast("B")
        if view.readonly:
            raise ValueError("C2H destination must be writable")
        if not view.c_contiguous:
            raise ValueError("C2H destination must be contiguous")
        total = 0
        with self._c2h_lock:
            while total < len(view):
                length = min(chunk_bytes, len(view)-total)
                read = os.preadv(
                    self._fd("c2h"), [view[total:total+length]],
                    offset+total,
                )
                if read <= 0:
                    raise RuntimeContractError("C2H read made no progress")
                total += read
        return total

    def c2h_read_local(
        self, channel: int, size: int, local_offset: int, chunk_bytes: int
    ) -> bytes:
        return self.c2h_read(
            size, local_to_host(channel, local_offset, size), chunk_bytes
        )

    def c2h_read_into_local(
        self, channel: int, destination: bytearray | memoryview,
        local_offset: int, chunk_bytes: int,
    ) -> int:
        size = len(memoryview(destination).cast("B"))
        return self.c2h_read_into(
            destination, local_to_host(channel, local_offset, size),
            chunk_bytes,
        )

    def wait_irq(self, timeout_s: float) -> bool:
        event_fd = self._fd("event")
        selector = selectors.DefaultSelector()
        try:
            selector.register(event_fd, selectors.EVENT_READ)
            if not selector.select(timeout_s):
                return False
            return len(os.read(event_fd, 4)) == 4
        finally:
            selector.close()

    @staticmethod
    def _pwrite_all(
        fd: int, data: bytes | bytearray | memoryview, offset: int,
        chunk_bytes: int,
    ) -> int:
        if chunk_bytes <= 0:
            raise ValueError("chunk_bytes must be positive")
        view = memoryview(data)
        total = 0
        while total < len(view):
            written = os.pwrite(fd, view[total:total+chunk_bytes],
                                offset+total)
            if written <= 0:
                raise RuntimeContractError("H2C write made no progress")
            total += written
        return total


class HardwareBackend(Protocol):
    def execute(self, engine: Engine,
                identity: CommandIdentity) -> Completion:
        """Run one command and return its hardware completion."""


class HostBoundaryOps(Protocol):
    def after_attention(self, cohort_id: int, layer_id: int,
                        buffer_id: int) -> None:
        """Run residual add and pre-MLP RMSNorm for one cohort."""

    def after_mlp(self, cohort_id: int, layer_id: int,
                  buffer_id: int) -> None:
        """Run residual add and the next legal Host boundary."""


class Stage(Enum):
    ATTENTION_READY = "attention_ready"
    ATTENTION_RUNNING = "attention_running"
    HOST_AFTER_ATTENTION = "host_after_attention"
    HOST_AFTER_ATTENTION_RUNNING = "host_after_attention_running"
    MLP_READY = "mlp_ready"
    MLP_RUNNING = "mlp_running"
    HOST_AFTER_MLP = "host_after_mlp"
    HOST_AFTER_MLP_RUNNING = "host_after_mlp_running"
    COMPLETE = "complete"


@dataclass
class CohortState:
    request_id: int
    cohort_id: int
    buffer_base: int
    layer_id: int = 0
    stage: Stage = Stage.ATTENTION_READY

    @property
    def buffer_id(self) -> int:
        return self.buffer_base + self.layer_id % 3


@dataclass(frozen=True)
class TraceEvent:
    kind: str
    stage: str
    request_id: int
    cohort_id: int
    layer_id: int
    buffer_id: int
    command_id: Optional[int]
    monotonic_ns: int


@dataclass(frozen=True)
class PipelineReport:
    layers: int
    cohorts: int
    completed_rows: int
    commands_submitted: int
    commands_completed: int
    hardware_window_ns: int
    end_to_end_ns: int
    events: Tuple[TraceEvent, ...]

    def as_dict(self) -> dict:
        result = asdict(self)
        result["events"] = [asdict(event) for event in self.events]
        return result


@dataclass(frozen=True)
class _Task:
    stage: Stage
    cohort_id: int
    identity: Optional[CommandIdentity]


class DualCohortRuntime:
    """Dependency-driven two-engine scheduler with no global cohort barrier."""

    def __init__(self, backend: HardwareBackend, host: HostBoundaryOps,
                 layers: int = 32, cohort_ids: Iterable[int] = (0, 1),
                 host_workers: int = 2,
                 request_ids: Optional[Iterable[int]] = None,
                 command_id_start: int = 1) -> None:
        cohort_ids = tuple(cohort_ids)
        if layers <= 0:
            raise ValueError("layers must be positive")
        if len(cohort_ids) < 2:
            raise ValueError("at least two cohorts are required")
        if len(cohort_ids) != 2:
            raise ValueError("VCU118 runtime requires exactly two cohorts")
        if len(set(cohort_ids)) != len(cohort_ids):
            raise ValueError("cohort_ids must be unique")
        if request_ids is None:
            request_ids = tuple(range(1, len(cohort_ids) + 1))
        else:
            request_ids = tuple(request_ids)
        if len(request_ids) != len(cohort_ids):
            raise ValueError("request_ids must match cohort_ids")
        if len(set(request_ids)) != len(request_ids):
            raise ValueError("request_ids must be unique")
        if any(type(value) is not int or not 0 <= value < (1 << 32)
               for value in request_ids):
            raise ValueError("request_ids must be unsigned 32-bit integers")
        if (type(command_id_start) is not int or
                not 1 <= command_id_start < (1 << 32)):
            raise ValueError("command_id_start must be a positive 32-bit integer")
        self.backend = backend
        self.host = host
        self.layers = layers
        self.states = {
            cohort_id: CohortState(
                request_id=request_ids[index], cohort_id=cohort_id,
                buffer_base=index*3)
            for index, cohort_id in enumerate(cohort_ids)
        }
        self.host_workers = host_workers
        self.scoreboard = CompletionScoreboard()
        self.events = []
        self._next_command_id = command_id_start
        self._buffer_owner = {
            state.buffer_base+slot: "host"
            for state in self.states.values() for slot in range(3)
        }

    def _record(self, kind: str, stage: Stage, state: CohortState,
                command_id: Optional[int]) -> int:
        now = time.monotonic_ns()
        self.events.append(TraceEvent(
            kind=kind, stage=stage.value, request_id=state.request_id,
            cohort_id=state.cohort_id, layer_id=state.layer_id,
            buffer_id=state.buffer_id, command_id=command_id,
            monotonic_ns=now))
        return now

    def _identity(self, engine: Engine, state: CohortState) -> CommandIdentity:
        identity = CommandIdentity(
            request_id=state.request_id,
            command_id=self._next_command_id,
            cohort_id=state.cohort_id,
            buffer_id=state.buffer_id,
            layer_id=state.layer_id,
            op_id=ENGINE_OP_ID[engine])
        self._next_command_id += 1
        return identity

    def _claim_buffer(self, state: CohortState, owner: str) -> None:
        current = self._buffer_owner[state.buffer_id]
        if current != "host":
            raise RuntimeContractError(
                f"buffer {state.buffer_id} is owned by {current}, not host")
        self._buffer_owner[state.buffer_id] = owner

    def _release_buffer(self, state: CohortState, owner: str) -> None:
        current = self._buffer_owner[state.buffer_id]
        if current != owner:
            raise RuntimeContractError(
                f"buffer {state.buffer_id} release expected {owner}, got {current}")
        self._buffer_owner[state.buffer_id] = "host"

    def run(self) -> PipelineReport:
        futures: Dict[Future, _Task] = {}
        engine_busy = {Engine.ATTENTION: False, Engine.MLP: False}
        first_command_ns: Optional[int] = None
        last_completion_ns: Optional[int] = None
        commands_submitted = 0

        with ThreadPoolExecutor(max_workers=2,
                                thread_name_prefix="scalellm-fpga") as fpga_pool, \
             ThreadPoolExecutor(max_workers=self.host_workers,
                                thread_name_prefix="scalellm-host") as host_pool:
            while any(state.stage is not Stage.COMPLETE
                      for state in self.states.values()):
                for engine, ready, running in (
                    (Engine.ATTENTION, Stage.ATTENTION_READY,
                     Stage.ATTENTION_RUNNING),
                    (Engine.MLP, Stage.MLP_READY, Stage.MLP_RUNNING),
                ):
                    candidates = sorted(
                        (state for state in self.states.values()
                         if state.stage is ready),
                        key=lambda item: (item.layer_id, item.cohort_id))
                    if not engine_busy[engine] and candidates:
                        state = candidates[0]
                        identity = self._identity(engine, state)
                        self.scoreboard.submit(engine, identity)
                        self._claim_buffer(state, engine.value)
                        state.stage = running
                        started = self._record("start", running, state,
                                               identity.command_id)
                        if first_command_ns is None:
                            first_command_ns = started
                        future = fpga_pool.submit(
                            self.backend.execute, engine, identity)
                        futures[future] = _Task(
                            stage=running, cohort_id=state.cohort_id,
                            identity=identity)
                        engine_busy[engine] = True
                        commands_submitted += 1

                for state in sorted(self.states.values(),
                                    key=lambda item: (item.layer_id,
                                                      item.cohort_id)):
                    if state.stage is Stage.HOST_AFTER_ATTENTION:
                        stage = state.stage
                        self._record("start", stage, state, None)
                        future = host_pool.submit(
                            self.host.after_attention, state.cohort_id,
                            state.layer_id, state.buffer_id)
                        futures[future] = _Task(
                            stage=stage, cohort_id=state.cohort_id,
                            identity=None)
                        state.stage = Stage.HOST_AFTER_ATTENTION_RUNNING
                    elif state.stage is Stage.HOST_AFTER_MLP:
                        stage = state.stage
                        self._record("start", stage, state, None)
                        future = host_pool.submit(
                            self.host.after_mlp, state.cohort_id,
                            state.layer_id, state.buffer_id)
                        futures[future] = _Task(
                            stage=stage, cohort_id=state.cohort_id,
                            identity=None)
                        state.stage = Stage.HOST_AFTER_MLP_RUNNING

                if not futures:
                    raise RuntimeContractError(
                        "pipeline deadlocked with no runnable task")
                finished, _ = wait(tuple(futures),
                                   return_when=FIRST_COMPLETED)
                for future in finished:
                    task = futures.pop(future)
                    state = self.states[task.cohort_id]
                    result = future.result()
                    if task.stage is Stage.ATTENTION_RUNNING:
                        assert task.identity is not None
                        self.scoreboard.complete(Engine.ATTENTION, result)
                        self._release_buffer(state, Engine.ATTENTION.value)
                        engine_busy[Engine.ATTENTION] = False
                        state.stage = Stage.HOST_AFTER_ATTENTION
                        last_completion_ns = self._record(
                            "complete", task.stage, state,
                            task.identity.command_id)
                    elif task.stage is Stage.MLP_RUNNING:
                        assert task.identity is not None
                        self.scoreboard.complete(Engine.MLP, result)
                        self._release_buffer(state, Engine.MLP.value)
                        engine_busy[Engine.MLP] = False
                        state.stage = Stage.HOST_AFTER_MLP
                        last_completion_ns = self._record(
                            "complete", task.stage, state,
                            task.identity.command_id)
                    elif task.stage is Stage.HOST_AFTER_ATTENTION:
                        state.stage = Stage.MLP_READY
                        self._record("complete", task.stage, state, None)
                    elif task.stage is Stage.HOST_AFTER_MLP:
                        self._record("complete", task.stage, state, None)
                        if state.layer_id + 1 == self.layers:
                            state.stage = Stage.COMPLETE
                        else:
                            state.layer_id += 1
                            state.stage = Stage.ATTENTION_READY
                    else:
                        raise RuntimeContractError(
                            f"unexpected completed task {task.stage.value}")

        if self.scoreboard.outstanding:
            raise RuntimeContractError(
                f"unconsumed completions: {self.scoreboard.outstanding}")
        if first_command_ns is None or last_completion_ns is None:
            raise RuntimeContractError("pipeline produced no hardware command")
        end_ns = time.monotonic_ns()
        return PipelineReport(
            layers=self.layers, cohorts=len(self.states),
            completed_rows=16*len(self.states),
            commands_submitted=commands_submitted,
            commands_completed=self.scoreboard.completed,
            hardware_window_ns=last_completion_ns-first_command_ns,
            end_to_end_ns=end_ns-first_command_ns,
            events=tuple(self.events))


def write_report(path: Path, report: PipelineReport) -> None:
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.as_dict(), indent=2) + "\n",
                    encoding="ascii")
