"""Serialized final-board driver and atomic 32-layer incremental runtime.

The transport is the existing XDMA session's read32/write32/local transfer
interface.  Construction verifies the new hardware identity before writes.
HostModelAdapter performs the existing host numerical boundaries.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from .scalellm_decode16 import DecodeRow
from .scalellm_final_abi import ATTENTION, MLP, CSR, IDS, FinalDescriptor
from .scalellm_final_layout import (
    HIDDEN, INPUT_BYTES, INTERMEDIATE, pack_normalized_fp32, prepare_host_down,
    unpack_attention_s24, unpack_mlp_s32, zero_inactive,
)


class FinalCommandError(RuntimeError):
    pass


class FinalBoardBackend:
    def __init__(self, session, timeout_s=120.0, poll_s=0.001):
        self.session = session
        self.timeout_s, self.poll_s = float(timeout_s), float(poll_s)
        if self.timeout_s <= 0 or self.poll_s < 0:
            raise ValueError("invalid command timeout/poll interval")
        self.pending = None
        self.recovery_generation = 1
        self.receipts = []
        self.verify_identity()

    def verify_identity(self):
        for register, key in (("MAGIC", "magic"), ("ABI", "abi"),
                              ("CORE_HZ", "core_hz"),
                              ("ATTENTION_LAYOUT", "attention_layout"),
                              ("MLP_LAYOUT", "mlp_layout"),
                              ("ATTENTION_FORMAT", "attention_format"),
                              ("MLP_FORMAT", "mlp_format")):
            if self.session.read32(CSR[register]) != IDS[key]:
                raise FinalCommandError("final hardware identity mismatch: " + register)
        if self.session.read32(CSR["CAPABILITIES"]) & IDS["capabilities"] != IDS["capabilities"]:
            raise FinalCommandError("final hardware capabilities missing")

    def run(self, descriptor: FinalDescriptor, payload: bytes, validate_output=None) -> bytes:
        if validate_output is not None and not callable(validate_output):
            raise ValueError("output validator must be callable")
        self.require_quiescent()
        if len(payload) != descriptor.input_bytes:
            raise ValueError("input byte length mismatch")
        input_rows = unpack_attention_s24(payload)
        if np.any(input_rows != zero_inactive(input_rows, descriptor.active_mask)):
            raise ValueError("inactive input rows must be zero")
        self.pending = descriptor
        if self.session.h2c_write_local(descriptor.channel, payload,
                                        descriptor.input_base, 1 << 20) != len(payload):
            raise FinalCommandError("short final input write; pending identity retained")
        for word, value in enumerate(descriptor.words()):
            self.session.write32(CSR["DESCRIPTOR"] + word * 4, value)
        self.session.write32(CSR["ACTION"], 1)
        if self.session.read32(CSR["ADMISSION_ERROR"]):
            raise FinalCommandError("final START admission rejected; pending identity retained")
        deadline = time.monotonic() + self.timeout_s
        while not self.session.read32(CSR["STATUS"]) & 2:
            if time.monotonic() >= deadline:
                raise TimeoutError("final command timeout; no position committed")
            time.sleep(self.poll_s)
        snapshot = tuple(self.session.read32(CSR["COMPLETION_DESCRIPTOR"] + word * 4)
                         for word in range(64))
        if snapshot != descriptor.words():
            raise FinalCommandError("stale final completion descriptor; pending retained")
        error = self.session.read32(CSR["DONE_ERROR"])
        if error or self.session.read32(CSR["STATUS"]) & 4:
            raise FinalCommandError(f"final command failed error=0x{error:08x}; no position committed")
        counts = (self.session.read32(CSR["DONE_INPUT_BYTES"]),
                  self.session.read32(CSR["DONE_OUTPUT_BYTES"]))
        if counts != (descriptor.input_bytes, descriptor.output_bytes):
            raise FinalCommandError("final completion transfer length mismatch")
        output = self.session.c2h_read_local(descriptor.channel, descriptor.output_bytes,
                                            descriptor.output_base, 1 << 20)
        if len(output) != descriptor.output_bytes:
            raise FinalCommandError("short final output read; completion retained")
        values = (unpack_attention_s24(output) if descriptor.opcode == ATTENTION
                  else unpack_mlp_s32(output))
        if np.any(values != zero_inactive(values, descriptor.active_mask)):
            raise FinalCommandError("inactive output row leaked data; completion retained")
        # Diagnostics compare independent gold while DONE and storage ownership
        # are retained. A failed comparison leaves pending intact and issues no ACK.
        if validate_output is not None:
            validate_output(descriptor, output)
        # Recheck complete identity after output copy and before releasing storage.
        if tuple(self.session.read32(CSR["COMPLETION_DESCRIPTOR"] + word * 4)
                 for word in range(64)) != snapshot:
            raise FinalCommandError("completion changed during output copy")
        cycles = self.session.read32(CSR["DONE_CYCLES"])
        self.session.write32(CSR["ACK_ID"], descriptor.command_id)
        self.session.write32(CSR["ACTION"], 2)
        if self.session.read32(CSR["ADMISSION_ERROR"]) or self.session.read32(CSR["STATUS"]) & 3:
            raise FinalCommandError("final completion ACK failed; pending retained")
        self.receipts.append(dict(command_id=descriptor.command_id, layer=descriptor.layer,
                                  opcode=descriptor.opcode, active_mask=descriptor.active_mask,
                                  cycles=cycles, seconds=cycles / IDS["core_hz"]))
        self.pending = None
        return output

    def require_quiescent(self):
        """Read-only guard before any tensor, weight or RoPE mutation."""
        if self.pending is not None:
            raise FinalCommandError("previous command retained; external full reset recovery required")
        self.verify_identity()
        if self.session.read32(CSR["STATUS"]) & 7:
            raise FinalCommandError("hardware has busy/completion/reset state")

    def accept_quiescent_recovery(self):
        """Record an external full reset; invalidates all old runtime/asset owners.

        No persistent DDR history is presumed to survive. A fresh asset store
        and runtime must rebuild requests from explicit known token histories.
        """
        self.verify_identity()
        if self.session.read32(CSR["STATUS"]) & 7:
            raise FinalCommandError("recovery requires a fresh quiescent hardware state")
        if self.recovery_generation == 0xffffffff:
            raise OverflowError("recovery session generation exhausted")
        self.recovery_generation += 1
        self.pending = None


@dataclass
class RequestSlot:
    epoch: int = 0
    prompt: tuple[int, ...] = ()
    max_new_tokens: int = 0
    position: int = 0
    generated: list[int] = field(default_factory=list)
    finished: bool = True

    @property
    def input_token(self):
        return self.prompt[self.position] if self.position < len(self.prompt) else self.generated[-1]


class FinalDecodeRuntime:
    """One all-layer transaction per token position of each active request.

    ``assets.prepare_layer(layer, rows)`` stages GU weights/metadata and fills
    each row's RoPE from its own absolute position before corresponding command.
    ``model`` supplies embedding, normalization, residual, Host Down and LM head.
    No logical position/generated-token list changes before all work succeeds.
    """
    def __init__(self, backend, model, assets, eos_token_ids=()):
        self.backend, self.model, self.assets = backend, model, assets
        self.recovery_generation = backend.recovery_generation
        self.eos_token_ids = frozenset(int(value) for value in eos_token_ids)
        self.slots = [RequestSlot() for _ in range(16)]
        self.command_id = 0
        self.batch_tag = 0
        self.buffer_generation = 0
        self.step_pending = False

    def allocate(self, slot, prompt_tokens, max_new_tokens):
        self._require_session()
        if self.step_pending:
            raise FinalCommandError("cannot replace a slot during a failed/pending step")
        if type(slot) is not int or not 0 <= slot < 16:
            raise ValueError("request slot must be 0..15")
        state = self.slots[slot]
        prompt = tuple(prompt_tokens)
        if not state.finished or not prompt or len(prompt) > 128:
            raise ValueError("slot busy or invalid prompt length")
        if any(type(token) is not int or token < 0 for token in prompt):
            raise ValueError("prompt tokens must be nonnegative integers")
        if type(max_new_tokens) is not int or not 0 <= max_new_tokens <= 128 - len(prompt):
            raise ValueError("generation exceeds 128-position context")
        if state.epoch == 0xffffffff:
            raise OverflowError("request epoch exhausted")
        self.slots[slot] = RequestSlot(state.epoch + 1, prompt, max_new_tokens,
                                       finished=False)
        return state.epoch + 1

    def _identity(self):
        if self.command_id == 0xffffffff or self.buffer_generation == 0xffffffff:
            raise OverflowError("hardware command identity exhausted")
        self.command_id += 1
        self.buffer_generation += 1
        return self.command_id, self.buffer_generation

    def _require_session(self):
        if self.backend.recovery_generation != self.recovery_generation:
            raise FinalCommandError("hardware reset invalidated prior KV history; create fresh runtime/assets and rebuild known token history")

    def step(self):
        self._require_session()
        active = [not state.finished for state in self.slots]
        if not any(active):
            return {}
        if any(state.position >= 128 for state in self.slots if not state.finished):
            raise ValueError("context length exhausted")
        self.backend.require_quiescent()
        rows = tuple(DecodeRow(True, state.epoch, state.position)
                     if active[slot] else DecodeRow()
                     for slot, state in enumerate(self.slots))
        mask = sum(int(value) << slot for slot, value in enumerate(active))
        tokens = [state.input_token if active[slot] else 0
                  for slot, state in enumerate(self.slots)]
        # On a pure Host failure this remains set, and a quiescent same-session
        # retry uses the same uncommitted position. A full reset invalidates
        # this runtime's entire KV history through recovery_generation.
        self.step_pending = True
        hidden = zero_inactive(self.model.embed(tokens), mask)
        tag = self.batch_tag
        for layer in range(32):
            self.backend.require_quiescent()
            weight_generation = self.assets.prepare_layer(layer, rows)
            command, generation = self._identity()
            attention = FinalDescriptor.create(command, tag, ATTENTION, layer, rows,
                                                 generation, weight_generation)
            payload = pack_normalized_fp32(self.model.attention_input(hidden, layer), mask)
            output = self.backend.run(attention, payload)
            residual, normalized = self.model.after_attention(
                hidden, unpack_attention_s24(output), layer, mask)
            command, generation = self._identity()
            mlp = FinalDescriptor.create(command, tag, MLP, layer, rows,
                                        generation, weight_generation)
            product = self.backend.run(mlp, pack_normalized_fp32(normalized, mask))
            hidden = zero_inactive(self.model.after_mlp(residual, product, layer, mask), mask)
        predictions = self.model.predict(hidden, mask)
        if len(predictions) != 16 or any(type(predictions[s]) is not int or predictions[s] < 0
                                         for s in range(16) if active[s]):
            raise ValueError("invalid host LM-head predictions")
        # One atomic logical commit after all 32 layers and final host outputs.
        emitted = {}
        for slot, state in enumerate(self.slots):
            if not active[slot]:
                continue
            state.position += 1
            if state.position >= len(state.prompt):
                if len(state.generated) < state.max_new_tokens:
                    token = predictions[slot]
                    state.generated.append(token)
                    emitted[slot] = token
                if (len(state.generated) >= state.max_new_tokens
                        or (state.generated and state.generated[-1] in self.eos_token_ids)):
                    state.finished = True
        self.batch_tag = (self.batch_tag + 1) & 0xffff
        self.step_pending = False
        return emitted

    def run(self):
        while any(not state.finished for state in self.slots):
            self.step()
        return {slot: tuple(state.generated) for slot, state in enumerate(self.slots)
                if state.prompt}


class HostModelAdapter:
    """Actual existing float32 norm/residual/Down/LM-head numerical path."""
    def __init__(self, model, down):
        self.model, self.down = model, down

    def embed(self, tokens):
        return self.model.embed(tokens)

    def attention_input(self, hidden, layer):
        from .scalellm_hostops import rms_norm
        w = self.model.norm_weights
        return rms_norm(hidden, w.input_layernorm[layer], w.epsilon)

    def after_attention(self, hidden, attention_s24, layer, mask):
        from .scalellm_hostops import rms_norm
        w = self.model.norm_weights
        residual = zero_inactive(hidden + attention_s24.astype(np.float32) / 65536, mask)
        return residual, rms_norm(residual, w.post_attention_layernorm[layer], w.epsilon)

    def after_mlp(self, residual, product_payload, layer, mask):
        # The new product is already S32/F16. Its host H32/A8 and Down remain
        # exact frozen format05 integer operations, as in the baseline host.
        down_s32 = self.down.run(layer, prepare_host_down(product_payload))
        if isinstance(down_s32, bytes):
            down_s32 = np.frombuffer(down_s32, dtype="<i4").reshape(16, HIDDEN)
        return zero_inactive(residual + np.asarray(down_s32, dtype=np.float32) / 65536, mask)

    def predict(self, hidden, mask):
        from .scalellm_hostops import rms_norm
        w = self.model.norm_weights
        normalized = rms_norm(hidden, w.final_norm, w.epsilon)
        result = self.model.evaluate(normalized, [0] * 16, top_k=1)
        return [int(row[0]) for row in result["top_token_ids"]]
