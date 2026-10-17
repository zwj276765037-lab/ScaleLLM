#!/usr/bin/env python3
"""Transaction model for one cohort16 A8W8 projection tile."""

from __future__ import annotations

from dataclasses import dataclass


GROUPS = 128
WAVES = 2
ROWS_PER_WAVE = 8
COLS_PER_TILE = 16
GROUP_SIZE = 32
WEIGHT_BYTES_PER_GROUP = COLS_PER_TILE * GROUP_SIZE


@dataclass(frozen=True)
class WeightAcceptance:
    group: int


@dataclass(frozen=True)
class WaveConsumption:
    group: int
    wave: int
    activation_bank: int


@dataclass(frozen=True)
class ProjectionSchedule:
    weights: tuple[WeightAcceptance, ...]
    consumptions: tuple[WaveConsumption, ...]
    output_waves: tuple[int, ...]

    @property
    def physical_weight_bytes(self) -> int:
        return len(self.weights) * WEIGHT_BYTES_PER_GROUP

    @property
    def reread_weight_bytes(self) -> int:
        return len(self.consumptions) * WEIGHT_BYTES_PER_GROUP


def build_projection_schedule(groups: int = GROUPS) -> ProjectionSchedule:
    if groups <= 0 or groups > GROUPS:
        raise ValueError("groups must be in 1..128")
    weights = tuple(WeightAcceptance(group) for group in range(groups))
    consumptions = tuple(
        WaveConsumption(group=group, wave=wave, activation_bank=wave)
        for group in range(groups)
        for wave in range(WAVES)
    )
    return ProjectionSchedule(weights, consumptions, (0, 1))


def audit_projection_schedule(schedule: ProjectionSchedule,
                              groups: int = GROUPS) -> None:
    expected = build_projection_schedule(groups)
    if schedule != expected:
        raise ValueError("projection schedule violates group/wave order")
    if schedule.physical_weight_bytes * WAVES != \
            schedule.reread_weight_bytes:
        raise ValueError("one accepted weight group must feed both waves")


if __name__ == "__main__":
    item = build_projection_schedule()
    audit_projection_schedule(item)
    print({
        "weight_acceptances": len(item.weights),
        "wave_consumptions": len(item.consumptions),
        "output_waves": item.output_waves,
        "physical_weight_bytes": item.physical_weight_bytes,
        "avoided_reread_bytes": (
            item.reread_weight_bytes - item.physical_weight_bytes),
    })

