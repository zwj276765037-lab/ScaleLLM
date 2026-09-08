#!/usr/bin/env python3
"""Auditable power sampling for ScaleLLM board acceptance."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from pathlib import Path
import threading
import time
from typing import Sequence

from .scalellm_runtime import RuntimeContractError


MAX_REASONABLE_BOARD_WATTS = 1_000.0


@dataclass(frozen=True)
class PowerSample:
    monotonic_ns: int
    watts: float


def summarize_power_samples(
    samples: Sequence[PowerSample], processed_tokens: int, *,
    source_path: Path, source_label: str, scale_to_watts: float,
    sample_interval_s: float,
) -> dict:
    """Integrate timestamped samples and retain the raw measurement trail."""
    if len(samples) < 2:
        raise RuntimeContractError("power evidence requires at least two samples")
    if type(processed_tokens) is not int or processed_tokens <= 0:
        raise RuntimeContractError("processed token count must be positive")
    if not source_label.strip():
        raise RuntimeContractError("power source label must be nonempty")
    if (not math.isfinite(scale_to_watts) or scale_to_watts <= 0 or
            not math.isfinite(sample_interval_s) or sample_interval_s <= 0):
        raise RuntimeContractError("power sampler scale/interval is invalid")

    energy_joules = 0.0
    watts = []
    previous = None
    for sample in samples:
        if type(sample.monotonic_ns) is not int or sample.monotonic_ns < 0:
            raise RuntimeContractError("power sample timestamp is invalid")
        if (not math.isfinite(sample.watts) or sample.watts <= 0 or
                sample.watts > MAX_REASONABLE_BOARD_WATTS):
            raise RuntimeContractError(
                f"power sample is outside 0..{MAX_REASONABLE_BOARD_WATTS} W"
            )
        if previous is not None:
            delta_ns = sample.monotonic_ns - previous.monotonic_ns
            if delta_ns <= 0:
                raise RuntimeContractError(
                    "power sample timestamps are not strictly increasing"
                )
            energy_joules += (
                (previous.watts + sample.watts) * 0.5 * delta_ns / 1e9
            )
        previous = sample
        watts.append(sample.watts)

    elapsed_ns = samples[-1].monotonic_ns - samples[0].monotonic_ns
    if energy_joules <= 0:
        raise RuntimeContractError("integrated board energy is not positive")
    return {
        "schema": "scalellm_v5_board_power_v1",
        "source_path": str(source_path),
        "source_label": source_label,
        "scale_to_watts": scale_to_watts,
        "requested_sample_interval_s": sample_interval_s,
        "sample_count": len(samples),
        "first_monotonic_ns": samples[0].monotonic_ns,
        "last_monotonic_ns": samples[-1].monotonic_ns,
        "elapsed_ns": elapsed_ns,
        "minimum_watts": min(watts),
        "maximum_watts": max(watts),
        "mean_watts": energy_joules * 1e9 / elapsed_ns,
        "energy_joules": energy_joules,
        "processed_tokens": processed_tokens,
        "processed_tokens_per_joule": processed_tokens / energy_joules,
        "samples": [asdict(sample) for sample in samples],
    }


def power_samples_for_window(
    samples: Sequence[PowerSample], start_ns: int, end_ns: int,
) -> tuple[PowerSample, ...]:
    """Clip samples to a run window, interpolating both exact boundaries."""
    if len(samples) < 2:
        raise RuntimeContractError("power evidence requires at least two samples")
    if (type(start_ns) is not int or type(end_ns) is not int or
            start_ns < 0 or end_ns <= start_ns):
        raise RuntimeContractError("power integration window is invalid")
    for left, right in zip(samples, samples[1:]):
        if right.monotonic_ns <= left.monotonic_ns:
            raise RuntimeContractError(
                "power sample timestamps are not strictly increasing"
            )
    if start_ns < samples[0].monotonic_ns or end_ns > samples[-1].monotonic_ns:
        raise RuntimeContractError("power samples do not cover the run window")

    def interpolate(timestamp_ns: int) -> PowerSample:
        for sample in samples:
            if sample.monotonic_ns == timestamp_ns:
                return sample
        for left, right in zip(samples, samples[1:]):
            if left.monotonic_ns < timestamp_ns < right.monotonic_ns:
                fraction = (
                    (timestamp_ns - left.monotonic_ns) /
                    (right.monotonic_ns - left.monotonic_ns)
                )
                return PowerSample(
                    timestamp_ns,
                    left.watts + fraction * (right.watts - left.watts),
                )
        raise RuntimeContractError("cannot interpolate power window boundary")

    return (
        interpolate(start_ns),
        *(sample for sample in samples
          if start_ns < sample.monotonic_ns < end_ns),
        interpolate(end_ns),
    )


class FilePowerSampler:
    """Sample one kernel/driver telemetry file on a monotonic timeline."""

    def __init__(
        self, path: str | Path, source_label: str, *,
        scale_to_watts: float = 1e-6, sample_interval_s: float = 0.1,
    ) -> None:
        try:
            self.path = Path(path).resolve(strict=True)
        except OSError as exc:
            raise RuntimeContractError(
                f"power telemetry file is missing: {path}"
            ) from exc
        if not self.path.is_file():
            raise RuntimeContractError(
                f"power telemetry source is not a file: {self.path}"
            )
        if not source_label.strip():
            raise RuntimeContractError("power source label must be nonempty")
        if (not math.isfinite(scale_to_watts) or scale_to_watts <= 0 or
                not math.isfinite(sample_interval_s) or sample_interval_s <= 0):
            raise RuntimeContractError("power sampler scale/interval is invalid")
        self.source_label = source_label
        self.scale_to_watts = scale_to_watts
        self.sample_interval_s = sample_interval_s
        self._samples: list[PowerSample] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._error: BaseException | None = None

    def _read_watts(self) -> float:
        try:
            raw = self.path.read_text(encoding="ascii").strip()
            value = float(raw) * self.scale_to_watts
        except (OSError, UnicodeError, ValueError) as exc:
            raise RuntimeContractError(
                f"cannot read power telemetry from {self.path}"
            ) from exc
        if (not math.isfinite(value) or value <= 0 or
                value > MAX_REASONABLE_BOARD_WATTS):
            raise RuntimeContractError(
                f"scaled power telemetry is invalid: {value} W"
            )
        return value

    def _capture(self) -> None:
        watts = self._read_watts()
        sample = PowerSample(time.monotonic_ns(), watts)
        with self._lock:
            if (self._samples and
                    sample.monotonic_ns <= self._samples[-1].monotonic_ns):
                raise RuntimeContractError("monotonic power timestamp regressed")
            self._samples.append(sample)

    def _sample_loop(self) -> None:
        try:
            while not self._stop.wait(self.sample_interval_s):
                self._capture()
        except BaseException as exc:  # Preserve worker failures for stop().
            self._error = exc
            self._stop.set()

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeContractError("power sampler was already started")
        self._capture()
        self._thread = threading.Thread(
            target=self._sample_loop,
            name="scalellm-power-sampler",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            raise RuntimeContractError("power sampler was not started")
        self._stop.set()
        self._thread.join()
        if self._error is not None:
            raise RuntimeContractError("power sampling worker failed") \
                from self._error
        self._capture()

    def report(self, processed_tokens: int) -> dict:
        if self._thread is None or self._thread.is_alive():
            raise RuntimeContractError("power sampler must be stopped first")
        with self._lock:
            samples = tuple(self._samples)
        return summarize_power_samples(
            samples, processed_tokens,
            source_path=self.path,
            source_label=self.source_label,
            scale_to_watts=self.scale_to_watts,
            sample_interval_s=self.sample_interval_s,
        )

    def report_window(
        self, start_ns: int, end_ns: int, processed_tokens: int,
    ) -> dict:
        if self._thread is None or self._thread.is_alive():
            raise RuntimeContractError("power sampler must be stopped first")
        with self._lock:
            samples = tuple(self._samples)
        window = power_samples_for_window(samples, start_ns, end_ns)
        return summarize_power_samples(
            window, processed_tokens,
            source_path=self.path,
            source_label=self.source_label,
            scale_to_watts=self.scale_to_watts,
            sample_interval_s=self.sample_interval_s,
        )

    def __enter__(self) -> "FilePowerSampler":
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        try:
            self.stop()
        except BaseException:
            if exc_type is None:
                raise
        return False
