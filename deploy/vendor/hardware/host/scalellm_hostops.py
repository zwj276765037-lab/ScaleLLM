#!/usr/bin/env python3
"""Pinned S24 ingress/S24-or-S32 egress and Host boundary operations."""

from __future__ import annotations

import ctypes
import errno
import mmap
import os
import threading
import time
from dataclasses import dataclass
from typing import Dict, Mapping, Protocol

import numpy as np

from .scalellm_memory import (
    ACTIVATION_COLUMNS,
    ACTIVATION_INPUT_PAYLOAD_BYTES,
    ACTIVATION_OUTPUT_PAYLOAD_BYTES,
    ACTIVATION_ROWS,
    LAYER_COUNT,
    activation_base_for_buffer,
    activation_channel,
)
from .scalellm_runtime import RuntimeContractError


S24_FRACTION_BITS = 16
S24_SCALE = 1 << S24_FRACTION_BITS
S24_MIN = -(1 << 23)
S24_MAX = (1 << 23) - 1
S32_FRACTION_BITS = 16
S32_SCALE = 1 << S32_FRACTION_BITS
S32_MIN = -(1 << 31)
S32_MAX = (1 << 31) - 1
ACTIVATION_SHAPE = (ACTIVATION_ROWS, ACTIVATION_COLUMNS)


class ActivationDataSession(Protocol):
    def h2c_write_local(
        self, channel: int, data: bytes | bytearray | memoryview,
        local_offset: int, chunk_bytes: int,
    ) -> int:
        """Write a channel-local activation image."""

    def c2h_read_into_local(
        self, channel: int, destination: bytearray | memoryview,
        local_offset: int, chunk_bytes: int,
    ) -> int:
        """Read a channel-local activation image into reusable memory."""


class PinnedBuffer:
    """Page-aligned anonymous storage with an explicit Linux mlock contract."""

    def __init__(self, size: int, require_lock: bool = True) -> None:
        if size <= 0:
            raise ValueError("pinned buffer size must be positive")
        self.size = size
        self._mapping = mmap.mmap(
            -1, size, flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS,
            prot=mmap.PROT_READ | mmap.PROT_WRITE,
        )
        self._view = memoryview(self._mapping)
        self._address = ctypes.addressof(
            ctypes.c_ubyte.from_buffer(self._mapping)
        )
        libc = ctypes.CDLL(None, use_errno=True)
        result = libc.mlock(
            ctypes.c_void_p(self._address), ctypes.c_size_t(size)
        )
        self.locked = result == 0
        if not self.locked and require_lock:
            error = ctypes.get_errno()
            self._view.release()
            self._mapping.close()
            raise RuntimeContractError(
                f"mlock({size}) failed: {os.strerror(error)} "
                f"(errno={error})"
            )

    @property
    def view(self) -> memoryview:
        return self._view

    @property
    def address(self) -> int:
        return self._address

    def close(self) -> None:
        if not hasattr(self, "_mapping"):
            return
        if self.locked:
            libc = ctypes.CDLL(None, use_errno=True)
            if libc.munlock(
                ctypes.c_void_p(self._address), ctypes.c_size_t(self.size)
            ) != 0:
                error = ctypes.get_errno()
                if error not in (errno.EINVAL, errno.ENOMEM):
                    raise RuntimeContractError(
                        f"munlock({self.size}) failed: {os.strerror(error)}"
                    )
        self._view.release()
        self._mapping.close()
        del self._mapping

    def __enter__(self) -> "PinnedBuffer":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


def _require_activation(values: np.ndarray, label: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float32)
    if array.shape != ACTIVATION_SHAPE:
        raise ValueError(
            f"{label} shape must be {ACTIVATION_SHAPE}, got {array.shape}"
        )
    if not np.all(np.isfinite(array)):
        raise RuntimeContractError(f"{label} contains NaN or infinity")
    return np.ascontiguousarray(array)


def pack_s24_q16(
    values: np.ndarray, destination: bytearray | memoryview | None = None,
) -> bytes | memoryview:
    """Round float32 away from zero and pack row-major little-endian S24."""
    array = _require_activation(values, "S24 source")
    magnitude = np.floor(
        np.abs(array, dtype=np.float32) * np.float32(S24_SCALE)
        + np.float32(0.5)
    )
    signed = np.copysign(magnitude, array).astype(np.int64)
    clipped = np.clip(signed, S24_MIN, S24_MAX).reshape(-1)
    encoded = np.bitwise_and(clipped, 0xFF_FFFF).astype(np.uint32)

    if destination is None:
        output = np.empty(ACTIVATION_INPUT_PAYLOAD_BYTES, dtype=np.uint8)
        return_bytes = True
    else:
        view = memoryview(destination).cast("B")
        if view.readonly or len(view) != ACTIVATION_INPUT_PAYLOAD_BYTES:
            raise ValueError(
                "S24 destination must be writable and exactly 192 KiB"
            )
        output = np.frombuffer(view, dtype=np.uint8)
        return_bytes = False
    packed = output.reshape(-1, 3)
    packed[:, 0] = encoded & 0xFF
    packed[:, 1] = (encoded >> 8) & 0xFF
    packed[:, 2] = (encoded >> 16) & 0xFF
    return output.tobytes() if return_bytes else view


def unpack_s24_q16(source: bytes | bytearray | memoryview) -> np.ndarray:
    """Decode a row-major little-endian S24 image to float32 Q8.16."""
    view = memoryview(source).cast("B")
    if len(view) != ACTIVATION_INPUT_PAYLOAD_BYTES:
        raise ValueError("S24 source must be exactly 192 KiB")
    packed = np.frombuffer(view, dtype=np.uint8).reshape(-1, 3)
    raw = (
        packed[:, 0].astype(np.uint32)
        | (packed[:, 1].astype(np.uint32) << 8)
        | (packed[:, 2].astype(np.uint32) << 16)
    )
    signed = ((raw ^ 0x80_0000).astype(np.int32) - 0x80_0000)
    return (
        signed.astype(np.float32) / np.float32(S24_SCALE)
    ).reshape(ACTIVATION_SHAPE)


def pack_s32_q16(
    values: np.ndarray, destination: bytearray | memoryview | None = None,
) -> bytes | memoryview:
    """Round away from zero and pack row-major little-endian S32/F16."""
    array = _require_activation(values, "S32 source").astype(np.float64)
    magnitude = np.floor(np.abs(array) * S32_SCALE + 0.5)
    signed = np.copysign(magnitude, array)
    clipped = np.clip(signed, S32_MIN, S32_MAX).astype(np.int64)
    encoded = clipped.astype("<i4")

    if destination is None:
        return encoded.tobytes(order="C")
    view = memoryview(destination).cast("B")
    if view.readonly or len(view) != ACTIVATION_OUTPUT_PAYLOAD_BYTES:
        raise ValueError(
            "S32 destination must be writable and exactly 256 KiB"
        )
    np.frombuffer(view, dtype="<i4")[:] = encoded.reshape(-1)
    return view


def unpack_s32_q16(source: bytes | bytearray | memoryview) -> np.ndarray:
    """Decode exactly one row-major little-endian signed S32/F16 image."""
    view = memoryview(source).cast("B")
    if len(view) != ACTIVATION_OUTPUT_PAYLOAD_BYTES:
        raise ValueError("S32 source must be exactly 256 KiB")
    signed = np.frombuffer(view, dtype="<i4")
    if signed.size != ACTIVATION_ROWS * ACTIVATION_COLUMNS:
        raise ValueError("S32 source element count does not match cohort16")
    return (
        signed.astype(np.float32) / np.float32(S32_SCALE)
    ).reshape(ACTIVATION_SHAPE)


def pack_mlp_input_s24_q16(
    values: np.ndarray, destination: bytearray | memoryview | None = None,
) -> bytes | memoryview:
    """Pack MLP input in Group32-major, row-major-within-group order."""
    array = _require_activation(values, "MLP S24 source")
    wire_order = array.reshape(
        ACTIVATION_ROWS, ACTIVATION_COLUMNS // 32, 32
    ).transpose(1, 0, 2).reshape(ACTIVATION_SHAPE)
    return pack_s24_q16(wire_order, destination)


def unpack_mlp_output_s32_q16(
    source: bytes | bytearray | memoryview,
) -> np.ndarray:
    """Decode tile16-major MLP output to a row-major float32 tensor."""
    wire_order = unpack_s32_q16(source)
    return wire_order.reshape(
        ACTIVATION_COLUMNS // 16, ACTIVATION_ROWS, 16
    ).transpose(1, 0, 2).reshape(ACTIVATION_SHAPE)


def rms_norm(
    values: np.ndarray, weight: np.ndarray, epsilon: float,
) -> np.ndarray:
    """Deterministic float32 Llama RMSNorm for one cohort16 tensor."""
    source = _require_activation(values, "RMSNorm source")
    gamma = np.asarray(weight, dtype=np.float32)
    if gamma.shape != (ACTIVATION_COLUMNS,):
        raise ValueError(
            f"RMSNorm weight shape must be ({ACTIVATION_COLUMNS},)"
        )
    if not np.all(np.isfinite(gamma)):
        raise RuntimeContractError("RMSNorm weight contains NaN or infinity")
    if not np.isfinite(epsilon) or epsilon <= 0:
        raise ValueError("RMSNorm epsilon must be finite and positive")
    mean_square = np.mean(
        np.square(source, dtype=np.float32), axis=1,
        dtype=np.float32, keepdims=True,
    )
    inverse_rms = np.reciprocal(
        np.sqrt(mean_square + np.float32(epsilon), dtype=np.float32),
        dtype=np.float32,
    )
    return np.multiply(
        np.multiply(source, inverse_rms, dtype=np.float32), gamma,
        dtype=np.float32,
    )


@dataclass(frozen=True)
class LlamaNormWeights:
    input_layernorm: np.ndarray
    post_attention_layernorm: np.ndarray
    final_norm: np.ndarray
    epsilon: float = 1e-5

    def __post_init__(self) -> None:
        expected_layers = (LAYER_COUNT, ACTIVATION_COLUMNS)
        if np.asarray(self.input_layernorm).shape != expected_layers:
            raise ValueError(f"input_layernorm shape must be {expected_layers}")
        if np.asarray(self.post_attention_layernorm).shape != expected_layers:
            raise ValueError(
                f"post_attention_layernorm shape must be {expected_layers}"
            )
        if np.asarray(self.final_norm).shape != (ACTIVATION_COLUMNS,):
            raise ValueError("final_norm shape must be (4096,)")
        if not np.isfinite(self.epsilon) or self.epsilon <= 0:
            raise ValueError("RMSNorm epsilon must be finite and positive")
        for name in (
            "input_layernorm", "post_attention_layernorm", "final_norm"
        ):
            array = np.asarray(getattr(self, name), dtype=np.float32)
            if not np.all(np.isfinite(array)):
                raise RuntimeContractError(f"{name} contains NaN or infinity")
            array = np.ascontiguousarray(array)
            array.setflags(write=False)
            object.__setattr__(self, name, array)


@dataclass(frozen=True)
class ActivationTransfer:
    direction: str
    cohort_id: int
    layer_id: int
    stage: str
    buffer_id: int
    local_offset: int
    size: int
    start_ns: int
    end_ns: int
    pinned: bool
    channel: int = 0


class PinnedActivationPool:
    """Six buffers for S24 H2C/Attention C2H and S32 MLP C2H payloads."""

    def __init__(
        self, session: ActivationDataSession, chunk_bytes: int = 1 << 20,
        require_lock: bool = True,
    ) -> None:
        if chunk_bytes <= 0:
            raise ValueError("activation XDMA chunk size must be positive")
        self.session = session
        self.chunk_bytes = chunk_bytes
        self.buffers: Dict[int, PinnedBuffer] = {}
        try:
            for buffer_id in range(6):
                self.buffers[buffer_id] = PinnedBuffer(
                    ACTIVATION_OUTPUT_PAYLOAD_BYTES, require_lock=require_lock
                )
        except BaseException:
            for buffer in self.buffers.values():
                buffer.close()
            raise
        self._locks = {buffer_id: threading.Lock() for buffer_id in range(6)}
        self._trace_lock = threading.Lock()
        self.transfers: list[ActivationTransfer] = []

    def _buffer(self, buffer_id: int) -> PinnedBuffer:
        try:
            return self.buffers[buffer_id]
        except KeyError as exc:
            raise ValueError("hardware buffer_id must be in 0..5") from exc

    def write(
        self, values: np.ndarray, cohort_id: int, layer_id: int,
        stage: str, buffer_id: int,
    ) -> None:
        if stage == "before_attention":
            encoder = pack_s24_q16
        elif stage == "before_mlp":
            encoder = pack_mlp_input_s24_q16
        else:
            raise ValueError(f"unsupported activation H2C stage {stage!r}")
        buffer = self._buffer(buffer_id)
        engine = "attention" if stage == "before_attention" else "mlp"
        channel = activation_channel(engine)
        local_offset = activation_base_for_buffer(buffer_id, engine)
        payload = buffer.view[:ACTIVATION_INPUT_PAYLOAD_BYTES]
        with self._locks[buffer_id]:
            encoder(values, payload)
            start = time.monotonic_ns()
            written = self.session.h2c_write_local(
                channel, payload, local_offset, self.chunk_bytes
            )
            end = time.monotonic_ns()
        if written != ACTIVATION_INPUT_PAYLOAD_BYTES:
            raise RuntimeContractError(
                f"short activation H2C write: {written}"
            )
        self._record(ActivationTransfer(
            "h2c", cohort_id, layer_id, stage, buffer_id, local_offset,
            written, start, end, buffer.locked, channel,
        ))

    def read(
        self, cohort_id: int, layer_id: int, stage: str, buffer_id: int,
    ) -> np.ndarray:
        buffer = self._buffer(buffer_id)
        if stage == "after_attention":
            expected_bytes = ACTIVATION_INPUT_PAYLOAD_BYTES
            decoder = unpack_s24_q16
        elif stage == "after_mlp":
            expected_bytes = ACTIVATION_OUTPUT_PAYLOAD_BYTES
            decoder = unpack_mlp_output_s32_q16
        else:
            raise ValueError(f"unsupported activation C2H stage {stage!r}")
        engine = "attention" if stage == "after_attention" else "mlp"
        channel = activation_channel(engine)
        local_offset = activation_base_for_buffer(buffer_id, engine, output=True)
        payload = buffer.view[:expected_bytes]
        with self._locks[buffer_id]:
            start = time.monotonic_ns()
            received = self.session.c2h_read_into_local(
                channel, payload, local_offset, self.chunk_bytes
            )
            end = time.monotonic_ns()
            if received != expected_bytes:
                raise RuntimeContractError(
                    f"short activation C2H read: {received}"
                )
            values = decoder(payload)
        self._record(ActivationTransfer(
            "c2h", cohort_id, layer_id, stage, buffer_id, local_offset,
            received, start, end, buffer.locked, channel,
        ))
        return values

    def _record(self, item: ActivationTransfer) -> None:
        with self._trace_lock:
            self.transfers.append(item)

    def close(self) -> None:
        first_error = None
        for buffer in self.buffers.values():
            try:
                buffer.close()
            except BaseException as exc:
                if first_error is None:
                    first_error = exc
        self.buffers.clear()
        if first_error is not None:
            raise first_error

    def __enter__(self) -> "PinnedActivationPool":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


class ScaleLLMHostBoundaryOps:
    """Real residual/RMSNorm boundaries around FPGA Attention and MLP."""

    def __init__(
        self, transfers: PinnedActivationPool, weights: LlamaNormWeights,
    ) -> None:
        self.transfers = transfers
        self.weights = weights
        self._residuals: Dict[int, np.ndarray] = {}
        self._next_stage: Dict[int, tuple[int, str]] = {}
        self._locks: Dict[int, threading.Lock] = {}

    def prepare_cohort(
        self, cohort_id: int, buffer_id: int, initial_hidden: np.ndarray,
    ) -> None:
        if cohort_id in self._residuals:
            raise RuntimeContractError(f"cohort {cohort_id} already prepared")
        hidden = _require_activation(initial_hidden, "initial hidden state")
        self._residuals[cohort_id] = hidden.copy()
        self._next_stage[cohort_id] = (0, "attention")
        self._locks[cohort_id] = threading.Lock()
        normalized = rms_norm(
            hidden, self.weights.input_layernorm[0], self.weights.epsilon
        )
        self.transfers.write(
            normalized, cohort_id, 0, "before_attention", buffer_id
        )

    def _require_stage(
        self, cohort_id: int, layer_id: int, stage: str,
    ) -> threading.Lock:
        if cohort_id not in self._residuals:
            raise RuntimeContractError(f"cohort {cohort_id} was not prepared")
        expected = self._next_stage[cohort_id]
        if expected != (layer_id, stage):
            raise RuntimeContractError(
                f"cohort {cohort_id} Host stage mismatch: "
                f"expected={expected} actual={(layer_id, stage)}"
            )
        return self._locks[cohort_id]

    def after_attention(
        self, cohort_id: int, layer_id: int, buffer_id: int,
    ) -> None:
        lock = self._require_stage(cohort_id, layer_id, "attention")
        with lock:
            output = self.transfers.read(
                cohort_id, layer_id, "after_attention", buffer_id
            )
            residual = np.add(
                self._residuals[cohort_id], output, dtype=np.float32
            )
            if not np.all(np.isfinite(residual)):
                raise RuntimeContractError(
                    "post-Attention residual contains NaN or infinity"
                )
            self._residuals[cohort_id] = residual
            normalized = rms_norm(
                residual, self.weights.post_attention_layernorm[layer_id],
                self.weights.epsilon,
            )
            self.transfers.write(
                normalized, cohort_id, layer_id, "before_mlp", buffer_id
            )
            self._next_stage[cohort_id] = (layer_id, "mlp")

    def after_mlp(
        self, cohort_id: int, layer_id: int, buffer_id: int,
    ) -> None:
        lock = self._require_stage(cohort_id, layer_id, "mlp")
        with lock:
            output = self.transfers.read(
                cohort_id, layer_id, "after_mlp", buffer_id
            )
            residual = np.add(
                self._residuals[cohort_id], output, dtype=np.float32
            )
            if not np.all(np.isfinite(residual)):
                raise RuntimeContractError(
                    "post-MLP residual contains NaN or infinity"
                )
            self._residuals[cohort_id] = residual
            next_layer = layer_id + 1
            if next_layer == LAYER_COUNT:
                self._next_stage[cohort_id] = (next_layer, "complete")
                return
            normalized = rms_norm(
                residual, self.weights.input_layernorm[next_layer],
                self.weights.epsilon,
            )
            next_buffer = (buffer_id // 3) * 3 + next_layer % 3
            self.transfers.write(
                normalized, cohort_id, next_layer, "before_attention",
                next_buffer,
            )
            self._next_stage[cohort_id] = (next_layer, "attention")

    def final_hidden(self, cohort_id: int) -> np.ndarray:
        if self._next_stage.get(cohort_id) != (LAYER_COUNT, "complete"):
            raise RuntimeContractError(f"cohort {cohort_id} is not complete")
        return self._residuals[cohort_id].copy()

    def final_normalized(self, cohort_id: int) -> np.ndarray:
        return rms_norm(
            self.final_hidden(cohort_id), self.weights.final_norm,
            self.weights.epsilon,
        )

    @property
    def states(self) -> Mapping[int, tuple[int, str]]:
        return dict(self._next_stage)
