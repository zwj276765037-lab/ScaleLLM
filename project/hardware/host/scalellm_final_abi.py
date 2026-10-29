"""Final ABI, descriptor admission and completion identity; no legacy fallback."""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path

from .scalellm_decode16 import DecodeRow
from .scalellm_final_layout import (
    INPUT_BYTES, MLP_OUTPUT_BYTES, ROPE_BASE, layer_spans, tensor_spans,
    index,
)

SPEC = json.loads((Path(__file__).resolve().parents[1]
                   / "source/final/abi.json").read_text())
IDS = SPEC["ids"]
CSR = SPEC["registers"]
ERRORS = SPEC["errors"]
ATTENTION = SPEC["opcodes"]["ATTENTION"]
MLP = SPEC["opcodes"]["MLP"]


@dataclass(frozen=True)
class FinalDescriptor:
    command_id: int
    batch_tag: int
    opcode: int
    layer: int
    active_mask: int
    buffer_generation: int
    input_base: int
    output_base: int
    input_bytes: int
    output_bytes: int
    weight_half0: int
    weight_half1: int
    metadata_base: int
    rope_base: int
    weight_generation: int
    rows: tuple[DecodeRow, ...]

    def __post_init__(self):
        for value, bits, label in ((self.command_id, 32, "command"),
                                   (self.batch_tag, 16, "batch tag"),
                                   (self.buffer_generation, 32, "buffer generation"),
                                   (self.weight_generation, 32, "weight generation")):
            index(value, 1 << bits, label)
        if min(self.command_id, self.buffer_generation, self.weight_generation) == 0:
            raise ValueError("command/buffer/weight generation must be nonzero")
        index(self.layer, 32, "layer")
        index(self.active_mask, 1 << 16, "active mask")
        if not self.active_mask or len(self.rows) != 16:
            raise ValueError("descriptor requires sixteen rows and nonzero active mask")
        for slot, row in enumerate(self.rows):
            if not isinstance(row, DecodeRow) or row.active != bool(self.active_mask >> slot & 1):
                raise ValueError("row activity differs from active mask")
            if not row.active and (row.position or row.epoch):
                raise ValueError("inactive descriptor rows must be canonical zero")
        if self.opcode not in (ATTENTION, MLP):
            raise ValueError("unknown final opcode")
        prefix = "attention" if self.opcode == ATTENTION else "mlp"
        legal = [s for b in range(6) for s in [tensor_spans(b)]
                 if s[prefix + "_input"].address == self.input_base
                 and s[prefix + "_output"].address == self.output_base]
        if not legal:
            raise ValueError("tensor addresses must be one canonical nonoverlapping buffer")
        if self.input_bytes != INPUT_BYTES or self.output_bytes != (
                INPUT_BYTES if self.opcode == ATTENTION else MLP_OUTPUT_BYTES):
            raise ValueError("tensor length differs from final layout")
        spans = layer_spans(self.layer)
        expected = ((spans["attention_c0"].address, spans["attention_c1"].address,
                     spans["attention_meta"].address, ROPE_BASE)
                    if self.opcode == ATTENTION else
                    (0, 0x01c00000, spans["mlp_gate_meta"].address, 0))
        if (self.weight_half0, self.weight_half1, self.metadata_base, self.rope_base) != expected:
            raise ValueError("weight/metadata/RoPE address differs from canonical layer")

    @property
    def channel(self):
        return 0 if self.opcode == ATTENTION else 1

    @property
    def numeric_format(self):
        return IDS["attention_format" if self.opcode == ATTENTION else "mlp_format"]

    @property
    def buffer_layout(self):
        return IDS["attention_layout" if self.opcode == ATTENTION else "mlp_layout"]

    def words(self) -> tuple[int, ...]:
        words = [0] * 64
        values = dict(self.__dict__, magic=IDS["magic"], abi=IDS["abi"], flags=0,
                      numeric_format=self.numeric_format, buffer_layout=self.buffer_layout)
        for field, offset in SPEC["descriptor_words"].items():
            words[offset] = values[field]
        for slot, row in enumerate(self.rows):
            words[32 + 2 * slot:34 + 2 * slot] = [row.position, row.epoch]
        return tuple(words)

    def pack(self) -> bytes:
        return struct.pack("<64I", *self.words())

    @classmethod
    def unpack(cls, payload: bytes):
        if len(payload) != 256:
            raise ValueError("descriptor must be exactly 256 bytes")
        words = struct.unpack("<64I", payload)
        if words[:2] != (IDS["magic"], IDS["abi"]):
            raise ValueError("final magic/ABI mismatch; old bitstream unsupported")
        if words[17] or any(words[20:32]):
            raise ValueError("descriptor reserved words must be zero")
        values = {field: words[offset] for field, offset
                  in SPEC["descriptor_words"].items()
                  if field not in ("magic", "abi", "flags", "numeric_format", "buffer_layout")}
        values["rows"] = tuple(DecodeRow(bool(words[6] >> slot & 1),
                                        words[33 + 2 * slot], words[32 + 2 * slot])
                               for slot in range(16))
        result = cls(**values)
        if words[18:20] != (result.numeric_format, result.buffer_layout):
            raise ValueError("numeric format/tensor layout mismatch")
        return result

    @classmethod
    def create(cls, command_id, batch_tag, opcode, layer, rows,
               buffer_generation, weight_generation, buffer_id=0):
        spans, tensors = layer_spans(layer), tensor_spans(buffer_id)
        attention = opcode == ATTENTION
        prefix = "attention" if attention else "mlp"
        return cls(command_id, batch_tag, opcode, layer,
                   sum(int(r.active) << slot for slot, r in enumerate(rows)),
                   buffer_generation, tensors[prefix + "_input"].address,
                   tensors[prefix + "_output"].address, INPUT_BYTES,
                   INPUT_BYTES if attention else MLP_OUTPUT_BYTES,
                   spans["attention_c0"].address if attention else 0,
                   spans["attention_c1"].address if attention else 0x01c00000,
                   spans["attention_meta" if attention else "mlp_gate_meta"].address,
                   ROPE_BASE if attention else 0, weight_generation, tuple(rows))
