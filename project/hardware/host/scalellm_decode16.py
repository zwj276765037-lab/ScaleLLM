"""Decode16 persistent KV addressing and transaction/lifecycle reference.

This is a host contract model, not a board driver.  The physical records carry
format03 KV12 only; request epochs and committed lengths are separate state.
DDR bytes can survive abort/reset/reuse, but may never become visible through
a new request until that request has written and committed the corresponding
positions.  One transaction appends one position per active slot in one layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

SLOTS = 16
LAYERS = 32
CONTEXT = 128
KV_HEADS = 8
GROUPS = 4
RECORD_BYTES = 64
RECORDS_PER_POSITION = 2 * KV_HEADS * GROUPS
KV_BASE = 0x6000_0000
KV_END = 0x7000_0000
LAYER_STRIDE = 0x0080_0000
SLOT_STRIDE = 0x0008_0000
POSITION_STRIDE = 0x0000_1000
VALUE_STRIDE = 0x0000_0800
HEAD_STRIDE = 0x0000_0100


def _index(value: int, count: int, name: str) -> int:
    if type(value) is not int or not 0 <= value < count:
        raise ValueError(f"{name} must be an integer in 0..{count - 1}")
    return value


@dataclass(frozen=True, order=True)
class KVKey:
    layer: int
    slot: int
    position: int
    is_v: int
    head: int
    group: int

    def __post_init__(self) -> None:
        for value, count, name in ((self.layer, LAYERS, "layer"),
                                   (self.slot, SLOTS, "slot"),
                                   (self.position, CONTEXT, "position"),
                                   (self.is_v, 2, "is_v"),
                                   (self.head, KV_HEADS, "head"),
                                   (self.group, GROUPS, "group")):
            _index(value, count, name)

    @property
    def address(self) -> int:
        return (KV_BASE + self.layer * LAYER_STRIDE + self.slot * SLOT_STRIDE
                + self.position * POSITION_STRIDE + self.is_v * VALUE_STRIDE
                + self.head * HEAD_STRIDE + self.group * RECORD_BYTES)


def key_from_address(address: int) -> KVKey:
    if type(address) is not int or not KV_BASE <= address < KV_END:
        raise ValueError("address outside decode16 KV allocation")
    if address % RECORD_BYTES:
        raise ValueError("KV record address must be 64-byte aligned")
    offset = address - KV_BASE
    layer, offset = divmod(offset, LAYER_STRIDE)
    slot, offset = divmod(offset, SLOT_STRIDE)
    position, offset = divmod(offset, POSITION_STRIDE)
    is_v, offset = divmod(offset, VALUE_STRIDE)
    head, offset = divmod(offset, HEAD_STRIDE)
    return KVKey(layer, slot, position, is_v, head, offset // RECORD_BYTES)


def prefix_keys(layer: int, slot: int, visible_length: int) -> Iterator[KVKey]:
    _index(layer, LAYERS, "layer")
    _index(slot, SLOTS, "slot")
    if type(visible_length) is not int or not 0 <= visible_length <= CONTEXT:
        raise ValueError("visible length must be an integer in 0..128")
    for position in range(visible_length):
        for is_v in range(2):
            for head in range(KV_HEADS):
                for group in range(GROUPS):
                    yield KVKey(layer, slot, position, is_v, head, group)


@dataclass(frozen=True)
class KVRecord:
    values: tuple[int, ...]
    meta: int

    def __post_init__(self) -> None:
        if len(self.values) != 32 or any(type(v) is not int or not -2047 <= v <= 2047
                                         for v in self.values):
            raise ValueError("KV12 record requires 32 lanes in -2047..2047")
        if type(self.meta) is not int or not 0 <= self.meta < 0x4000:
            raise ValueError("KV metadata has reserved bits set")
        code, shift = self.meta & 255, self.meta >> 8
        if (code == 0 and shift != 0) or (code != 0 and not 8 <= shift <= 32):
            raise ValueError("invalid KV scale metadata")
        if code == 0 and any(self.values):
            raise ValueError("zero KV scale requires zero values")

    def pack(self) -> bytes:
        value = self.meta << 384
        for lane, sample in enumerate(self.values):
            value |= (sample & 0xFFF) << (12 * lane)
        return value.to_bytes(RECORD_BYTES, "little")

    @classmethod
    def unpack(cls, data: bytes) -> "KVRecord":
        if len(data) != RECORD_BYTES:
            raise ValueError("KV record must contain exactly 64 bytes")
        packed = int.from_bytes(data, "little")
        if packed >> 400:
            raise ValueError("KV record padding bits must be zero")
        values = tuple((lambda v: v - 4096 if v & 2048 else v)(
                       (packed >> (lane * 12)) & 4095) for lane in range(32))
        return cls(values, (packed >> 384) & 65535)


@dataclass(frozen=True)
class DecodeRow:
    active: bool = False
    epoch: int = 0
    position: int = 0

    def __post_init__(self) -> None:
        if type(self.active) is not bool:
            raise ValueError("active must be boolean")
        _index(self.position, CONTEXT, "position")
        _index(self.epoch, 1 << 32, "epoch")
        if self.active and self.epoch == 0:
            raise ValueError("active slot requires a nonzero epoch")

    @property
    def visible_length(self) -> int:
        return self.position + 1 if self.active else 0


@dataclass(frozen=True)
class DecodeBatch:
    command_id: int
    layer: int
    rows: tuple[DecodeRow, ...]

    def __post_init__(self) -> None:
        _index(self.command_id, 1 << 32, "command_id")
        _index(self.layer, LAYERS, "layer")
        if len(self.rows) != SLOTS or not all(isinstance(r, DecodeRow) for r in self.rows):
            raise ValueError("decode batch requires exactly 16 fixed slot rows")
        if not any(row.active for row in self.rows):
            raise ValueError("empty decode batch")

    @property
    def active_mask(self) -> int:
        return sum(int(row.active) << slot for slot, row in enumerate(self.rows))

    def append_keys(self) -> Iterator[KVKey]:
        for slot, row in enumerate(self.rows):
            if row.active:
                for is_v in range(2):
                    for head in range(KV_HEADS):
                        for group in range(GROUPS):
                            yield KVKey(self.layer, slot, row.position, is_v, head, group)


@dataclass
class _Slot:
    epoch: int = 0
    allocated: bool = False
    eos: bool = False
    lengths: list[int] = field(default_factory=lambda: [0] * LAYERS)


class DecodeKVStore:
    """Reference external memory with atomic visibility and acknowledged writes.

    DDR write acknowledgments can arrive out of order.  On abort, bytes already
    written remain in ``physical``; lengths do not advance.  A retry must write
    the entire uncommitted position and receive fresh acknowledgments.
    """

    def __init__(self) -> None:
        self.physical: dict[int, bytes] = {}
        self._slots = [_Slot() for _ in range(SLOTS)]
        self._transaction: DecodeTransaction | None = None
        self._ticket = 0

    def allocate(self, slot: int) -> int:
        state = self._slots[_index(slot, SLOTS, "slot")]
        if self._transaction is not None:
            raise RuntimeError("cannot change slot ownership during a command")
        if state.allocated and not state.eos:
            raise RuntimeError("slot already owns a live request")
        if state.epoch == 0xFFFF_FFFF:
            raise OverflowError("epoch exhausted; do not wrap request identity")
        state.epoch += 1
        state.allocated, state.eos = True, False
        state.lengths = [0] * LAYERS
        return state.epoch

    def finish(self, slot: int, epoch: int) -> None:
        state = self._owner(slot, epoch)
        if self._transaction is not None:
            raise RuntimeError("cannot finish a request during a command")
        state.eos = True

    def _owner(self, slot: int, epoch: int) -> _Slot:
        state = self._slots[_index(slot, SLOTS, "slot")]
        if not state.allocated or state.epoch != epoch or state.eos:
            raise ValueError("stale, unallocated, or completed request")
        return state

    def length(self, slot: int, epoch: int, layer: int) -> int:
        _index(layer, LAYERS, "layer")
        return self._owner(slot, epoch).lengths[layer]

    def begin(self, batch: DecodeBatch) -> "DecodeTransaction":
        if self._transaction is not None:
            raise RuntimeError("another command is outstanding")
        for slot, row in enumerate(batch.rows):
            if row.active:
                if self._owner(slot, row.epoch).lengths[batch.layer] != row.position:
                    raise ValueError("append position must equal committed layer length")
        transaction = DecodeTransaction(self, batch)
        self._transaction = transaction
        return transaction

    def read(self, key: KVKey, epoch: int) -> KVRecord:
        state = self._owner(key.slot, epoch)
        if key.position >= state.lengths[key.layer]:
            raise ValueError("uncommitted KV position")
        return KVRecord.unpack(self.physical[key.address])

    def reset(self) -> None:
        if self._transaction is not None:
            self._transaction.abort()
        for state in self._slots:
            state.allocated, state.eos = False, False
            state.lengths = [0] * LAYERS


class DecodeTransaction:
    def __init__(self, store: DecodeKVStore, batch: DecodeBatch) -> None:
        self.store, self.batch = store, batch
        self.expected = frozenset(batch.append_keys())
        self.writes: dict[KVKey, int] = {}
        self.acks: dict[int, bool] = {}
        self._tickets: set[int] = set()
        self.failed = False
        self.closed = False

    def _live(self) -> None:
        if self.closed or self.store._transaction is not self:
            raise RuntimeError("command is no longer outstanding")

    def write(self, key: KVKey, record: KVRecord) -> int:
        self._live()
        if self.failed:
            raise RuntimeError("failed command requires abort")
        if key not in self.expected or key in self.writes:
            raise ValueError("write outside current active positions or duplicate record")
        self.store._ticket += 1
        ticket = self.store._ticket
        self.store.physical[key.address] = record.pack()
        self.writes[key] = ticket
        self._tickets.add(ticket)
        return ticket

    def acknowledge(self, ticket: int, success: bool = True) -> None:
        self._live()
        if ticket not in self._tickets or ticket in self.acks:
            raise ValueError("unknown, duplicate, or previous-command write acknowledgment")
        if type(success) is not bool:
            raise ValueError("write acknowledgment must be boolean")
        self.acks[ticket] = success
        self.failed |= not success

    @property
    def writes_complete(self) -> bool:
        return (not self.closed and not self.failed and len(self.writes) == len(self.expected)
                and len(self.acks) == len(self.expected) and all(self.acks.values()))

    def attention_prefix(self, slot: int) -> tuple[KVRecord, ...]:
        """Scratch-loader view; current position requires the full DDR barrier."""
        self._live()
        row = self.batch.rows[_index(slot, SLOTS, "slot")]
        if not row.active or not self.writes_complete:
            raise RuntimeError("attention prefix unavailable before complete write barrier")
        return tuple(KVRecord.unpack(self.store.physical[key.address])
                     for key in prefix_keys(self.batch.layer, slot, row.visible_length))

    def commit(self, *, output_completed: bool) -> None:
        self._live()
        if not self.writes_complete or output_completed is not True:
            raise RuntimeError("completion requires all DDR writes and output completion")
        # All checks precede updates, so the batch's lengths advance atomically.
        for slot, row in enumerate(self.batch.rows):
            if row.active:
                state = self.store._owner(slot, row.epoch)
                if state.lengths[self.batch.layer] != row.position:
                    raise RuntimeError("request changed during command")
        for slot, row in enumerate(self.batch.rows):
            if row.active:
                self.store._slots[slot].lengths[self.batch.layer] += 1
        self.closed = True
        self.store._transaction = None

    def abort(self) -> None:
        self._live()
        self.closed = True
        self.store._transaction = None
