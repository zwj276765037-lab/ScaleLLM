#!/usr/bin/env python3
"""Executable V5 gate/up tile-major gather and inverse-repack contract.

The production V4 stream is ordered by 16-column projection tile and then by
the 128 hidden K groups.  Gate and up tiles are interleaved.  A V5 8x12
kernel, however, must see all K groups of one 12-column pass before moving to
the next pass.  This model makes that transpose explicit and keeps it
separate from production RTL.

The contract intentionally models weight, code and shift as three independent
symbolic fields.  A test therefore catches metadata/data skew as well as a
column-order error.  It also provides an elastic 12-to-16 projection gearbox
and a cycle-level single-bank/ping-pong overlap model.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Iterable, Iterator, Optional, Sequence


SOURCE_COLUMNS = 16
COMPUTE_COLUMNS = 12
SUPERTILE_COLUMNS = math.lcm(SOURCE_COLUMNS, COMPUTE_COLUMNS)
GROUP_SIZE = 32
HIDDEN = 4096
INTERMEDIATE = 14336
HIDDEN_GROUPS = HIDDEN // GROUP_SIZE
MATRICES = ("gate", "up")

WEIGHT_BITS_PER_COLUMN_GROUP = GROUP_SIZE * 4
META_BITS_PER_COLUMN = 8 + 6
LANE_BITS = WEIGHT_BITS_PER_COLUMN_GROUP + META_BITS_PER_COLUMN
SOURCE_RECORD_BITS = SOURCE_COLUMNS * LANE_BITS
COMPUTE_RECORD_BITS = COMPUTE_COLUMNS * LANE_BITS

# RAMB36E2 true-dual-port mode is 1024x36.  True dual port matters: four
# destination lanes receive two writes when one 16-column record straddles a
# 12-column boundary.
RAMB36_TDP_WIDTH = 36
RAMB36_TDP_DEPTH = 1024


def ceil_div(value: int, divisor: int) -> int:
    if value < 0 or divisor <= 0:
        raise ValueError("ceil_div requires value>=0 and divisor>0")
    return (value + divisor - 1) // divisor


def low_mask(valid: int, width: int) -> int:
    if valid < 0 or valid > width:
        raise ValueError("invalid low-mask width")
    return (1 << valid) - 1 if valid else 0


@dataclass(frozen=True)
class LanePayload:
    """Independent symbolic weight and ScaleCode fields for one column."""

    weight: int
    code: int
    shift: int


ZERO_LANE = LanePayload(0, 0, 0)


def symbolic_lane(matrix: int, global_column: int,
                  k_group: int) -> LanePayload:
    """Return a deterministic nonzero identity for one matrix/column/group."""
    serial = ((matrix + 1) << 40) | ((global_column + 1) << 12) | (k_group + 1)
    # Fields deliberately use unrelated transforms so swapping only metadata
    # cannot accidentally pass the comparison.
    return LanePayload(
        weight=(serial * 0x1F123BB5 + 0x13579BDF) & ((1 << 128) - 1),
        code=((serial * 29 + 17) & 0xFF) or 1,
        shift=(serial * 11 + 7) & 0x3F,
    )


@dataclass(frozen=True)
class BlockShape:
    index: int
    first_column: int
    valid_columns: int
    source_records_per_matrix: int
    compute_passes_per_matrix: int
    source_transactions: int
    compute_transactions: int


def block_shapes(width: int, groups: int = HIDDEN_GROUPS) -> tuple[BlockShape, ...]:
    if width <= 0 or groups <= 0:
        raise ValueError("width and groups must be positive")
    result = []
    for index, first in enumerate(range(0, width, SUPERTILE_COLUMNS)):
        valid = min(SUPERTILE_COLUMNS, width - first)
        records = ceil_div(valid, SOURCE_COLUMNS)
        passes = ceil_div(valid, COMPUTE_COLUMNS)
        result.append(BlockShape(
            index=index,
            first_column=first,
            valid_columns=valid,
            source_records_per_matrix=records,
            compute_passes_per_matrix=passes,
            source_transactions=records * len(MATRICES) * groups,
            compute_transactions=passes * len(MATRICES) * groups,
        ))
    return tuple(result)


@dataclass(frozen=True)
class SourceTransaction:
    block: int
    matrix: int
    record_in_block: int
    global_record: int
    k_group: int
    valid_mask: int
    lanes: tuple[LanePayload, ...]


def source_transactions(shape: BlockShape, width: int,
                        groups: int = HIDDEN_GROUPS) -> Iterator[SourceTransaction]:
    """Yield the exact existing V4 order for one gather block.

    A full block is:

      gate-record0[g0..g127], up-record0[g0..g127],
      gate-record1[g0..g127], up-record1[g0..g127],
      gate-record2[g0..g127], up-record2[g0..g127].
    """
    del width  # Shape already contains the clipped block width.
    first_record = shape.first_column // SOURCE_COLUMNS
    for record in range(shape.source_records_per_matrix):
        valid = min(SOURCE_COLUMNS,
                    shape.valid_columns - record * SOURCE_COLUMNS)
        mask = low_mask(valid, SOURCE_COLUMNS)
        for matrix in range(len(MATRICES)):
            for k_group in range(groups):
                lanes = []
                for lane in range(SOURCE_COLUMNS):
                    offset = record * SOURCE_COLUMNS + lane
                    if offset < shape.valid_columns:
                        lanes.append(symbolic_lane(
                            matrix, shape.first_column + offset, k_group))
                    else:
                        lanes.append(ZERO_LANE)
                yield SourceTransaction(
                    block=shape.index,
                    matrix=matrix,
                    record_in_block=record,
                    global_record=first_record + record,
                    k_group=k_group,
                    valid_mask=mask,
                    lanes=tuple(lanes),
                )


@dataclass(frozen=True)
class ComputeTransaction:
    block: int
    pass_in_block: int
    matrix: int
    k_group: int
    valid_mask: int
    lanes: tuple[LanePayload, ...]


class GateUpGatherBank:
    """One pass-oriented 48-column bank with fail-closed input tags.

    Storage is arranged as ``[matrix][pass][K-group][12 lanes]``.  An input
    record is scattered into at most two pass addresses.  This is the
    tile-major-to-pass-major transpose that a generic three-record streaming
    gearbox alone cannot provide.
    """

    def __init__(self, shape: BlockShape, groups: int = HIDDEN_GROUPS):
        if groups <= 0:
            raise ValueError("groups must be positive")
        self.shape = shape
        self.groups = groups
        self.accepted = 0
        self.sealed = False
        dimensions = (len(MATRICES), shape.compute_passes_per_matrix, groups)
        self._lanes = [
            [
                [[ZERO_LANE for _ in range(COMPUTE_COLUMNS)]
                 for _ in range(dimensions[2])]
                for _ in range(dimensions[1])
            ]
            for _ in range(dimensions[0])
        ]
        self._written = [
            [
                [[False for _ in range(COMPUTE_COLUMNS)]
                 for _ in range(dimensions[2])]
                for _ in range(dimensions[1])
            ]
            for _ in range(dimensions[0])
        ]

    def _expected_tag(self) -> tuple[int, int, int]:
        per_record = len(MATRICES) * self.groups
        record = self.accepted // per_record
        remainder = self.accepted % per_record
        matrix = remainder // self.groups
        k_group = remainder % self.groups
        return record, matrix, k_group

    def accept(self, transaction: SourceTransaction) -> None:
        if self.sealed:
            raise ValueError("cannot write a sealed gather bank")
        if self.accepted >= self.shape.source_transactions:
            raise ValueError("too many source transactions")
        record, matrix, k_group = self._expected_tag()
        expected_record = self.shape.first_column // SOURCE_COLUMNS + record
        valid = min(SOURCE_COLUMNS,
                    self.shape.valid_columns - record * SOURCE_COLUMNS)
        expected_mask = low_mask(valid, SOURCE_COLUMNS)
        actual_tag = (transaction.record_in_block, transaction.matrix,
                      transaction.k_group)
        if (transaction.block != self.shape.index or
                actual_tag != (record, matrix, k_group) or
                transaction.global_record != expected_record or
                transaction.valid_mask != expected_mask or
                len(transaction.lanes) != SOURCE_COLUMNS):
            raise ValueError("illegal tile-major source tag/order/mask")

        for source_lane, payload in enumerate(transaction.lanes):
            offset = record * SOURCE_COLUMNS + source_lane
            lane_valid = bool(expected_mask & (1 << source_lane))
            if not lane_valid:
                if payload != ZERO_LANE:
                    raise ValueError("invalid source lane must be zero")
                continue
            destination_pass = offset // COMPUTE_COLUMNS
            destination_lane = offset % COMPUTE_COLUMNS
            if self._written[matrix][destination_pass][k_group][destination_lane]:
                raise ValueError("gather destination written twice")
            expected_payload = symbolic_lane(
                matrix, self.shape.first_column + offset, k_group)
            if payload != expected_payload:
                raise ValueError("weight/metadata payload does not match tag")
            self._lanes[matrix][destination_pass][k_group][destination_lane] = \
                payload
            self._written[matrix][destination_pass][k_group][destination_lane] = \
                True
        self.accepted += 1

    def seal(self) -> None:
        if self.accepted != self.shape.source_transactions:
            raise ValueError("cannot seal an incomplete gather bank")
        for matrix in range(len(MATRICES)):
            for output_pass in range(self.shape.compute_passes_per_matrix):
                valid = min(
                    COMPUTE_COLUMNS,
                    self.shape.valid_columns - output_pass * COMPUTE_COLUMNS)
                for k_group in range(self.groups):
                    for lane in range(COMPUTE_COLUMNS):
                        written = self._written[matrix][output_pass][k_group][lane]
                        payload = self._lanes[matrix][output_pass][k_group][lane]
                        if lane < valid:
                            if not written:
                                raise ValueError("valid compute lane was not filled")
                        elif written or payload != ZERO_LANE:
                            raise ValueError("masked compute lane is observable")
        self.sealed = True

    def drain(self) -> Iterator[ComputeTransaction]:
        """Yield accumulator-safe pass-major order.

        Each matrix/pass owns 128 consecutive K-group transactions, so the
        existing one-context projection accumulator can retain first/last
        semantics.  Gate/up are interleaved at completed-pass granularity to
        make inverse projection repack and the legacy SwiGLU order natural.
        """
        if not self.sealed:
            raise ValueError("cannot drain an unsealed gather bank")
        for output_pass in range(self.shape.compute_passes_per_matrix):
            valid = min(
                COMPUTE_COLUMNS,
                self.shape.valid_columns - output_pass * COMPUTE_COLUMNS)
            mask = low_mask(valid, COMPUTE_COLUMNS)
            for matrix in range(len(MATRICES)):
                for k_group in range(self.groups):
                    yield ComputeTransaction(
                        block=self.shape.index,
                        pass_in_block=output_pass,
                        matrix=matrix,
                        k_group=k_group,
                        valid_mask=mask,
                        lanes=tuple(self._lanes[matrix][output_pass][k_group]),
                    )


@dataclass(frozen=True)
class ProjectionPass:
    block: int
    pass_in_block: int
    matrix: int
    valid_mask: int
    columns: tuple[Optional[int], ...]


@dataclass(frozen=True)
class LegacyProjectionTile:
    matrix: int
    global_record: int
    columns: tuple[int, ...]


def projection_passes(width: int) -> tuple[ProjectionPass, ...]:
    """Symbolic 12-column kernel results in the frozen drain order."""
    output = []
    for shape in block_shapes(width):
        for output_pass in range(shape.compute_passes_per_matrix):
            valid = min(
                COMPUTE_COLUMNS,
                shape.valid_columns - output_pass * COMPUTE_COLUMNS)
            for matrix in range(len(MATRICES)):
                columns: list[Optional[int]] = []
                for lane in range(COMPUTE_COLUMNS):
                    offset = output_pass * COMPUTE_COLUMNS + lane
                    columns.append(
                        shape.first_column + offset if lane < valid else None)
                output.append(ProjectionPass(
                    block=shape.index,
                    pass_in_block=output_pass,
                    matrix=matrix,
                    valid_mask=low_mask(valid, COMPUTE_COLUMNS),
                    columns=tuple(columns),
                ))
    return tuple(output)


def expected_legacy_tiles(width: int) -> tuple[LegacyProjectionTile, ...]:
    if width <= 0 or width % SOURCE_COLUMNS:
        raise ValueError("legacy SwiGLU boundary requires a multiple of 16")
    output = []
    for record in range(width // SOURCE_COLUMNS):
        columns = tuple(range(record * SOURCE_COLUMNS,
                              (record + 1) * SOURCE_COLUMNS))
        for matrix in range(len(MATRICES)):
            output.append(LegacyProjectionTile(
                matrix=matrix, global_record=record, columns=columns))
    return tuple(output)


class ElasticInverseRepacker:
    """One-output-skid reference for pass-major 12 -> legacy 16 columns.

    Wide payload state is resetless in the intended RTL.  This software model
    represents only valid state: while ``out_valid`` is stalled, both payload
    and all input-side state remain unchanged.
    """

    def __init__(self, width: int):
        self.width = width
        self.expected_inputs = projection_passes(width)
        self.input_index = 0
        self.tails: list[list[int]] = [[], []]
        self.next_record = [0, 0]
        self.out_valid = False
        self.out_payload: Optional[LegacyProjectionTile] = None

    def input_ready(self, out_ready: bool) -> bool:
        return not self.out_valid or out_ready

    def tick(self, in_valid: bool, in_payload: Optional[ProjectionPass],
             out_ready: bool) -> tuple[bool, bool]:
        """Advance one cycle and return ``(input_fire, output_fire)``."""
        ready = self.input_ready(out_ready)
        input_fire = bool(in_valid and ready)
        output_fire = bool(self.out_valid and out_ready)

        if output_fire:
            self.out_valid = False
            self.out_payload = None

        if input_fire:
            if in_payload is None or self.input_index >= len(self.expected_inputs):
                raise ValueError("inverse repacker received an illegal input")
            expected = self.expected_inputs[self.input_index]
            if in_payload != expected:
                raise ValueError("12-column projection order/tag/mask mismatch")
            self.input_index += 1
            valid_columns = in_payload.valid_mask.bit_count()
            if in_payload.valid_mask != low_mask(valid_columns, COMPUTE_COLUMNS):
                raise ValueError("projection mask is not low-contiguous")
            for lane, column in enumerate(in_payload.columns):
                if lane < valid_columns:
                    if column is None:
                        raise ValueError("valid projection lane is empty")
                    self.tails[in_payload.matrix].append(column)
                elif column is not None:
                    raise ValueError("masked projection lane is nonzero")

            tail = self.tails[in_payload.matrix]
            if len(tail) >= SOURCE_COLUMNS:
                if len(tail) >= 2 * SOURCE_COLUMNS:
                    raise ValueError("inverse tail exceeded one legacy record")
                columns = tuple(tail[:SOURCE_COLUMNS])
                del tail[:SOURCE_COLUMNS]
                record = self.next_record[in_payload.matrix]
                expected_columns = tuple(range(
                    record * SOURCE_COLUMNS,
                    (record + 1) * SOURCE_COLUMNS))
                if columns != expected_columns:
                    raise ValueError("inverse repack reconstructed wrong columns")
                if self.out_valid:
                    raise ValueError("one-entry inverse output skid overflow")
                self.out_valid = True
                self.out_payload = LegacyProjectionTile(
                    matrix=in_payload.matrix,
                    global_record=record,
                    columns=columns,
                )
                self.next_record[in_payload.matrix] += 1
        return input_fire, output_fire

    def finished(self) -> bool:
        return (self.input_index == len(self.expected_inputs) and
                not self.out_valid and all(not tail for tail in self.tails))


@dataclass(frozen=True)
class InverseSimulation:
    cycles: int
    input_count: int
    output_count: int
    input_stall_cycles: int
    output_stall_cycles: int
    stable_input_checks: int
    stable_output_checks: int
    outputs: tuple[LegacyProjectionTile, ...]


def simulate_inverse_backpressure(width: int, seed: int = 0x481216,
                                  input_probability: float = 0.73,
                                  ready_probability: float = 0.61) -> InverseSimulation:
    inputs = projection_passes(width)
    model = ElasticInverseRepacker(width)
    rng = random.Random(seed)
    input_index = 0
    presenting = False
    outputs = []
    cycles = input_stalls = output_stalls = 0
    stable_inputs = stable_outputs = 0
    held_input: Optional[ProjectionPass] = None
    held_output: Optional[LegacyProjectionTile] = None

    limit = max(1000, len(inputs) * 100)
    while not model.finished() or input_index < len(inputs):
        if not presenting and input_index < len(inputs):
            presenting = rng.random() < input_probability
        in_payload = inputs[input_index] if presenting else None
        out_ready = rng.random() < ready_probability
        in_ready = model.input_ready(out_ready)

        if presenting and not in_ready:
            input_stalls += 1
            if held_input is not None:
                if in_payload != held_input:
                    raise AssertionError("input payload changed under backpressure")
                stable_inputs += 1
            held_input = in_payload
        else:
            held_input = None

        visible_output = model.out_payload
        if model.out_valid and not out_ready:
            output_stalls += 1
            if held_output is not None:
                if visible_output != held_output:
                    raise AssertionError("output payload changed under backpressure")
                stable_outputs += 1
            held_output = visible_output
        else:
            held_output = None

        input_fire, output_fire = model.tick(
            presenting, in_payload, out_ready)
        if output_fire:
            if visible_output is None:
                raise AssertionError("output handshake without a payload")
            outputs.append(visible_output)
        if input_fire:
            input_index += 1
            presenting = False
        cycles += 1
        if cycles > limit:
            raise RuntimeError("inverse backpressure simulation did not converge")

    return InverseSimulation(
        cycles=cycles,
        input_count=input_index,
        output_count=len(outputs),
        input_stall_cycles=input_stalls,
        output_stall_cycles=output_stalls,
        stable_input_checks=stable_inputs,
        stable_output_checks=stable_outputs,
        outputs=tuple(outputs),
    )


@dataclass(frozen=True)
class BufferScheduleSimulation:
    banks: int
    cycles: int
    source_transactions: int
    compute_transactions: int
    source_stall_cycles: int
    compute_stall_cycles: int
    stable_source_checks: int
    stable_compute_checks: int


def simulate_buffer_schedule(
        width: int, groups: int = HIDDEN_GROUPS, banks: int = 2,
        seed: Optional[int] = None, source_probability: float = 1.0,
        compute_ready_probability: float = 1.0) -> BufferScheduleSimulation:
    """Cycle-model fill/drain overlap with ready/valid payload stability.

    The payload identity is ``(block, transaction-in-block)``.  A bank becomes
    drainable only after its complete tile-major source block has arrived.
    Drain order is block order and one pass-major compute transaction per
    accepted cycle.  No same-cycle look-ahead across a state transition is
    assumed.
    """
    if banks <= 0:
        raise ValueError("at least one bank is required")
    if not (0 < source_probability <= 1 and
            0 < compute_ready_probability <= 1):
        raise ValueError("probabilities must be in (0,1]")
    shapes = block_shapes(width, groups)
    rng = random.Random(seed)

    # State entries are EMPTY, FILL, FULL or DRAIN.  A bank owns at most one
    # block, identified by bank_block.
    state = ["EMPTY"] * banks
    bank_block: list[Optional[int]] = [None] * banks
    fill_offset = [0] * banks
    drain_offset = [0] * banks
    next_fill_block = 0
    next_drain_block = 0

    source_presenting = False
    source_accepted = compute_accepted = 0
    source_stalls = compute_stalls = 0
    stable_source = stable_compute = 0
    held_source: Optional[tuple[int, int]] = None
    held_compute: Optional[tuple[int, int]] = None
    cycles = 0

    total_source = sum(shape.source_transactions for shape in shapes)
    total_compute = sum(shape.compute_transactions for shape in shapes)
    limit = max(1000, (total_source + total_compute) * 100)

    while compute_accepted < total_compute:
        # Allocate an empty bank to the next block before evaluating ready.
        if next_fill_block < len(shapes) and not any(
                item == "FILL" for item in state):
            try:
                bank = state.index("EMPTY")
            except ValueError:
                bank = -1
            if bank >= 0:
                state[bank] = "FILL"
                bank_block[bank] = next_fill_block
                fill_offset[bank] = 0
                next_fill_block += 1

        # Start the oldest full block.  There is one ordered compute stream.
        if not any(item == "DRAIN" for item in state):
            drain_bank = next((index for index in range(banks)
                               if state[index] == "FULL" and
                               bank_block[index] == next_drain_block), -1)
            if drain_bank >= 0:
                state[drain_bank] = "DRAIN"
                drain_offset[drain_bank] = 0
                next_drain_block += 1

        fill_bank = next((index for index in range(banks)
                          if state[index] == "FILL"), -1)
        drain_bank = next((index for index in range(banks)
                           if state[index] == "DRAIN"), -1)

        if not source_presenting and source_accepted < total_source:
            source_presenting = rng.random() < source_probability
        source_ready = fill_bank >= 0
        if source_presenting:
            source_block = (bank_block[fill_bank] if fill_bank >= 0 else
                            next_fill_block)
            source_offset = fill_offset[fill_bank] if fill_bank >= 0 else 0
            visible_source = (int(source_block), source_offset)
        else:
            visible_source = None

        if source_presenting and not source_ready:
            source_stalls += 1
            if held_source is not None:
                if visible_source != held_source:
                    raise AssertionError("source changed while gather not ready")
                stable_source += 1
            held_source = visible_source
        else:
            held_source = None

        compute_valid = drain_bank >= 0
        compute_ready = rng.random() < compute_ready_probability
        visible_compute = ((int(bank_block[drain_bank]),
                            drain_offset[drain_bank])
                           if compute_valid else None)
        if compute_valid and not compute_ready:
            compute_stalls += 1
            if held_compute is not None:
                if visible_compute != held_compute:
                    raise AssertionError("compute payload changed while stalled")
                stable_compute += 1
            held_compute = visible_compute
        else:
            held_compute = None

        if source_presenting and source_ready:
            block = int(bank_block[fill_bank])
            fill_offset[fill_bank] += 1
            source_accepted += 1
            source_presenting = False
            if fill_offset[fill_bank] == shapes[block].source_transactions:
                state[fill_bank] = "FULL"

        if compute_valid and compute_ready:
            block = int(bank_block[drain_bank])
            drain_offset[drain_bank] += 1
            compute_accepted += 1
            if drain_offset[drain_bank] == shapes[block].compute_transactions:
                state[drain_bank] = "EMPTY"
                bank_block[drain_bank] = None

        cycles += 1
        if cycles > limit:
            raise RuntimeError("buffer overlap simulation did not converge")

    return BufferScheduleSimulation(
        banks=banks,
        cycles=cycles,
        source_transactions=source_accepted,
        compute_transactions=compute_accepted,
        source_stall_cycles=source_stalls,
        compute_stall_cycles=compute_stalls,
        stable_source_checks=stable_source,
        stable_compute_checks=stable_compute,
    )


@dataclass(frozen=True)
class GatherResources:
    weight_bits_per_bank: int
    metadata_bits_per_bank: int
    useful_bits_per_bank: int
    ping_pong_useful_bits: int
    naive_source_record_ramb36_per_bank: int
    ramb36_per_bank: int
    central_ping_pong_ramb36: int
    duplicated_outer_slr_ramb36: int
    inverse_tail_bits: int
    optional_inverse_output_skid_bits: int


def gather_resources(groups: int = HIDDEN_GROUPS) -> GatherResources:
    # A full pass-oriented bank has 2 matrices x 4 passes x 128 groups x 12
    # lanes.  The same quantity is 768 source records x 2272 bits.
    lanes_per_bank = len(MATRICES) * 4 * groups * COMPUTE_COLUMNS
    weight_bits = lanes_per_bank * WEIGHT_BITS_PER_COLUMN_GROUP
    metadata_bits = lanes_per_bank * META_BITS_PER_COLUMN
    useful = weight_bits + metadata_bits
    depth = len(MATRICES) * 4 * groups
    if depth != RAMB36_TDP_DEPTH:
        raise ValueError("formal RAMB36 estimate is specialized to 128 groups")
    per_lane = ceil_div(LANE_BITS, RAMB36_TDP_WIDTH)
    ramb_per_bank = COMPUTE_COLUMNS * per_lane
    source_records = len(MATRICES) * 3 * groups
    naive_source_record_ramb36 = ceil_div(
        SOURCE_RECORD_BITS, RAMB36_TDP_WIDTH)
    if source_records > RAMB36_TDP_DEPTH:
        raise ValueError("source-record buffer exceeds one RAMB36 depth")
    inverse_tail = len(MATRICES) * COMPUTE_COLUMNS * 16 * 24
    inverse_skid = SOURCE_COLUMNS * 16 * 24
    return GatherResources(
        weight_bits_per_bank=weight_bits,
        metadata_bits_per_bank=metadata_bits,
        useful_bits_per_bank=useful,
        ping_pong_useful_bits=2 * useful,
        naive_source_record_ramb36_per_bank=naive_source_record_ramb36,
        ramb36_per_bank=ramb_per_bank,
        central_ping_pong_ramb36=2 * ramb_per_bank,
        duplicated_outer_slr_ramb36=4 * ramb_per_bank,
        inverse_tail_bits=inverse_tail,
        optional_inverse_output_skid_bits=inverse_skid,
    )


def validate_compute_transaction(transaction: ComputeTransaction,
                                 shape: BlockShape) -> None:
    valid = transaction.valid_mask.bit_count()
    expected_valid = min(
        COMPUTE_COLUMNS,
        shape.valid_columns - transaction.pass_in_block * COMPUTE_COLUMNS)
    if (valid != expected_valid or
            transaction.valid_mask != low_mask(valid, COMPUTE_COLUMNS)):
        raise AssertionError("compute mask mismatch")
    for lane, payload in enumerate(transaction.lanes):
        if lane < valid:
            column = (shape.first_column +
                      transaction.pass_in_block * COMPUTE_COLUMNS + lane)
            expected = symbolic_lane(
                transaction.matrix, column, transaction.k_group)
        else:
            expected = ZERO_LANE
        if payload != expected:
            raise AssertionError("compute weight/metadata payload mismatch")


def audit_full_gather(width: int = INTERMEDIATE,
                      groups: int = HIDDEN_GROUPS) -> tuple[int, int]:
    """Exhaustively fill/drain every full-shape block and validate each lane."""
    source_count = compute_count = 0
    for shape in block_shapes(width, groups):
        bank = GateUpGatherBank(shape, groups)
        for transaction in source_transactions(shape, width, groups):
            bank.accept(transaction)
            source_count += 1
        bank.seal()
        expected_index = 0
        for transaction in bank.drain():
            per_pass = len(MATRICES) * groups
            expected_pass = expected_index // per_pass
            remainder = expected_index % per_pass
            expected_matrix = remainder // groups
            expected_group = remainder % groups
            if (transaction.pass_in_block != expected_pass or
                    transaction.matrix != expected_matrix or
                    transaction.k_group != expected_group):
                raise AssertionError("compute stream is not pass-major")
            validate_compute_transaction(transaction, shape)
            expected_index += 1
            compute_count += 1
        if expected_index != shape.compute_transactions:
            raise AssertionError("compute transaction count mismatch")
    return source_count, compute_count


def report() -> str:
    shapes = block_shapes(INTERMEDIATE)
    source = sum(item.source_transactions for item in shapes)
    compute = sum(item.compute_transactions for item in shapes)
    single = simulate_buffer_schedule(INTERMEDIATE, banks=1)
    ping_pong = simulate_buffer_schedule(INTERMEDIATE, banks=2)
    resources = gather_resources()
    tail = shapes[-1]
    lines = [
        "V5 gate/up gather contract (MODEL)",
        f"supertile blocks                         {len(shapes)}",
        f"full blocks / tail columns              {len(shapes)-1} / {tail.valid_columns}",
        f"source transactions                     {source}",
        f"12-column kernel transactions           {compute}",
        f"tail source records/matrix              {tail.source_records_per_matrix}",
        f"tail compute passes/matrix              {tail.compute_passes_per_matrix}",
        f"single-bank ideal cycles                {single.cycles}",
        f"ping-pong ideal cycles                  {ping_pong.cycles}",
        f"ping-pong startup overhead cycles       {ping_pong.cycles-compute}",
        f"weight / metadata bits per bank          {resources.weight_bits_per_bank} / {resources.metadata_bits_per_bank}",
        f"useful bits / gather bank               {resources.useful_bits_per_bank}",
        f"useful bits / ping-pong                 {resources.ping_pong_useful_bits}",
        f"naive source-row RAMB36 / bank           {resources.naive_source_record_ramb36_per_bank}",
        f"central ping-pong RAMB36 estimate        {resources.central_ping_pong_ramb36}",
        f"two-outer-SLR duplicated RAMB36 estimate {resources.duplicated_outer_slr_ramb36}",
        f"inverse tails / optional skid bits       {resources.inverse_tail_bits} / {resources.optional_inverse_output_skid_bits}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(report())
