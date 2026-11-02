#!/usr/bin/env python3
"""Publication figures from validated KV128 seven-rail records, with gaps visible."""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import defaultdict
import json
import math
from pathlib import Path
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from kv128_sevenrail_analyze import RAILS, require
from kv128_sevenrail_windows import KINDS, at, interval_at, plot, plot_rail_points


LABELS = {"idle": "Idle", "attention_repeat": "Attention repeat",
          "mlp_repeat": "MLP repeat", "full_kv128_step": "Full KV128 step"}
SHADES = {"idle": "#bdbdbd", "attention_repeat": "#8ecae6",
          "mlp_repeat": "#ffb084", "full_kv128_step": "#a8ddb5"}


def minutes(tick: float, origin: int, freq: int) -> float:
    return (tick - origin) / freq / 60


def shade_windows(axis, windows: list[dict], origin: int, freq: int) -> None:
    for row in windows:
        axis.axvspan(minutes(row["start_ticks"], origin, freq),
                     minutes(row["end_ticks"], origin, freq),
                     color=SHADES[row["kind"]], alpha=.17, lw=0)


def shade_legend(figure) -> None:
    figure.legend(handles=[Patch(facecolor=SHADES[kind], label=LABELS[kind])
                           for kind in KINDS], loc="lower center", ncol=4,
                  bbox_to_anchor=(.5, .02), fontsize=8, frameon=False)


def save_pair(figure, stem: Path) -> None:
    figure.savefig(stem.with_suffix(".png"), dpi=220)
    figure.savefig(stem.with_suffix(".svg"))
    plt.close(figure)


def vi_pout_figure(metadata: dict, points: list[dict], windows: list[dict], stem: Path) -> None:
    origin, freq = metadata["sampling_started_ticks"], metadata["qpc_frequency"]
    figure, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
    for axis, (address, name, regulator) in zip(
            axes, [row for row in RAILS if row[2] == "MAX20751"]):
        shade_windows(axis, windows, origin, freq)
        rail = [p for p in points if p["address"] == address]
        vi_x = [minutes((p["vi_before_ticks"] + p["vi_after_ticks"]) / 2,
                        origin, freq) for p in rail]
        pout_x = [minutes((p["read_pout"]["before_ticks"]
                           + p["read_pout"]["after_ticks"]) / 2,
                          origin, freq) for p in rail]
        axis.scatter(vi_x, [p["vi_w"] for p in rail], s=4, marker=".",
                     color="#16324f", label="V×I raw point")
        axis.scatter(pout_x, [p["pout_w"] for p in rail], s=5, marker="x",
                     linewidths=.45, color="#c6412a", label="READ_POUT raw point")
        axis.set_ylabel(f"{name} (W)")
        axis.grid(axis="y", alpha=.2)
        axis.legend(loc="upper left", frameon=False, fontsize=8)
    axes[-1].set_xlabel("Minutes since seven-rail sampler start (QPC)")
    figure.suptitle("Three MAX20751 rails: discrete V×I and READ_POUT readings")
    shade_legend(figure)
    figure.text(.5, .01, "READ_POUT resolution is 2 W; V/I/P reads are asynchronous. "
                "Sensor aperture/lag unknown.",
                ha="center", fontsize=8)
    figure.tight_layout(rect=(0, .065, 1, .97))
    save_pair(figure, stem)


def common_runs(points: list[dict], windows: list[dict], freq: int,
                gap_ticks: float):
    series = {address: [] for address, _, _ in RAILS}
    for point in points:
        a, b = point["vi_before_ticks"], point["vi_after_ticks"]
        series[point["address"]].append(((a + b) / 2,
                                          point["vi_w"] if b - a <= gap_ticks else None))
    for rail in series:
        require(all(left[0] < right[0] for left, right in zip(series[rail], series[rail][1:])),
                "Rail midpoint order invalid in figure")
    times = {rail: [x for x, _ in sample] for rail, sample in series.items()}
    runs, gaps = [], []
    for window in windows:
        start, end = window["start_ticks"], window["end_ticks"]
        bounds = {start, end}
        for sample in series.values():
            bounds.update(t for t, _ in sample if start < t < end)
        current = []
        sorted_bounds = sorted(bounds)
        for a, b in zip(sorted_bounds, sorted_bounds[1:]):
            if b <= a:
                continue
            segments = {rail: interval_at(series[rail], (a + b) / 2,
                                          gap_ticks, times[rail]) for rail in series}
            if any(segment is None for segment in segments.values()):
                if current:
                    runs.append(current)
                    current = []
                if gaps and gaps[-1][1] == a:
                    gaps[-1] = (gaps[-1][0], b)
                else:
                    gaps.append((a, b))
                continue
            y_a = sum(at(*segment, a) for segment in segments.values())
            y_b = sum(at(*segment, b) for segment in segments.values())
            if not current or current[-1][0] != a:
                current.append((a, y_a))
            current.append((b, y_b))
        if current:
            runs.append(current)
    return runs, gaps


def common_coverage_figure(metadata: dict, points: list[dict], result: dict,
                           stem: Path) -> None:
    origin, freq = metadata["sampling_started_ticks"], metadata["qpc_frequency"]
    windows = result["windows"]
    runs, gaps = common_runs(points, windows, freq,
                             result["maximum_interpolated_gap_ms"] / 1000 * freq)
    plotted_missing = sum((b-a)/freq for a, b in gaps)
    reported_missing = sum(row["common_missing_seconds"] for row in windows)
    require(math.isclose(plotted_missing, reported_missing, rel_tol=0, abs_tol=1e-5),
            "Plotted common gaps differ from independently integrated gaps")
    figure, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True,
                                gridspec_kw={"height_ratios": [3, 1]})
    shade_windows(axes[0], windows, origin, freq)
    for run in runs:
        axes[0].plot([minutes(t, origin, freq) for t, _ in run],
                     [v for _, v in run], color="#153b50", lw=.75)
    for a, b in gaps:
        axes[0].axvspan(minutes(a, origin, freq), minutes(b, origin, freq),
                        color="#d62828", alpha=.5, lw=0)
    axes[0].set_ylabel("Seven-rail total telemetry (W)")
    axes[0].set_title("Common valid coverage only: linear interpolation within each rail")
    axes[0].grid(axis="y", alpha=.2)
    for window in windows:
        a, b = (minutes(window[key], origin, freq)
                for key in ("start_ticks", "end_ticks"))
        fraction = window["common_coverage_fraction"]
        axes[1].barh(0, b-a, left=a, height=.6,
                     color="#277da1", align="center")
        if fraction < 1:
            axes[1].text((a+b)/2, -.45, f"{100*fraction:.1f}%",
                         ha="center", va="top", fontsize=7)
    if gaps:
        axes[1].broken_barh([(minutes(a, origin, freq),
                              minutes(b, origin, freq)-minutes(a, origin, freq))
                             for a, b in gaps], (-.3, .6), facecolors="#d62828")
    axes[1].set_ylim(-.8, .8)
    axes[1].set_yticks([])
    axes[1].set_xlabel("Minutes since seven-rail sampler start (QPC)")
    axes[1].set_title("Blue: covered duration; red: actual missing common coverage", fontsize=9)
    shade_legend(figure)
    figure.text(.5, .01, "No line crosses a >420 ms intersample gap. Red gaps are not extrapolated. "
                "Physical sensor aperture/lag remains unknown.", ha="center", fontsize=8)
    figure.tight_layout(rect=(0, .07, 1, 1))
    save_pair(figure, stem)


def busy_host_figure(result: dict, stem: Path) -> None:
    rows = result["command_trace"]["windows"]
    windows = result["windows"]
    figure, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    xs = list(range(len(rows)))
    busy = [row["busy_inner_seconds"] for row in rows]
    host = [row["host_gap_total_seconds"] for row in rows]
    other = [max(0, win["window_seconds"]-b-h) for win, b, h in zip(windows, busy, host)]
    axes[0].bar(xs, busy, color="#277da1", label="Conservative observed BUSY")
    axes[0].bar(xs, other, bottom=busy, color="#f9844a",
                label="Command wall outside conservative BUSY")
    axes[0].bar(xs, host, bottom=[b+o for b, o in zip(busy, other)],
                color="#b9b9b9", label="Host/ACK gaps")
    axes[0].set_ylabel("Seconds in workload window")
    axes[0].legend(loc="upper right", ncol=3, fontsize=8)
    axes[0].set_title("Window time composition (measured QPC, not BUSY-extrapolated power)")
    axes[0].grid(axis="y", alpha=.2)
    first_active = True
    for index, row in enumerate(rows):
        if row["kind"] == "idle":
            continue
        med = row["host_gap_ms"]["median"]
        p95 = row["host_gap_ms"]["p95"]
        if med is not None and med > 0 and p95 > 0:
            axes[1].scatter(index-.1, med, color="#277da1", marker="o", s=20,
                            label="host gap median" if first_active else None)
            axes[1].scatter(index+.1, p95, color="#e76f51", marker="^", s=26,
                            label="host gap p95" if first_active else None)
            first_active = False
        if row["busy_inner_unavailable_command_ids"]:
            axes[1].annotate("BUSY n<2: " + ",".join(map(str,
                           row["busy_inner_unavailable_command_ids"])),
                           (index, max(p95 or 0, med or 0)), xytext=(0, 10),
                           textcoords="offset points", ha="center", fontsize=7,
                           rotation=30, color="#c6412a")
    axes[1].set_yscale("log")
    axes[1].set_ylabel("Active-window host gap (ms, log)")
    axes[1].grid(axis="y", alpha=.2)
    axes[1].legend(loc="upper right", fontsize=8)
    axes[1].set_xticks(xs, [f"{LABELS[row['kind']]}\n{row['repeat_id']}"
                            for row in rows], rotation=35, ha="right", fontsize=8)
    figure.text(.5, .005, "Conservative BUSY excludes the first/last status-read uncertainty. "
                "Two completed commands had fewer than two BUSY observations.",
                ha="center", fontsize=8)
    figure.tight_layout(rect=(0, .025, 1, 1))
    save_pair(figure, stem)


def busy_conditional_figure(result: dict, stem: Path) -> None:
    categories = (("attention_repeat", 1, "A repeat"),
                  ("mlp_repeat", 2, "MLP repeat"),
                  ("full_kv128_step", 1, "Full-step A"),
                  ("full_kv128_step", 2, "Full-step MLP"))
    grouped = defaultdict(list)
    for window in result["command_trace"]["windows"]:
        for command in window["commands"]:
            for point in command["busy_inner_points"]:
                grouped[(window["kind"], command["opcode"],
                         point["address"])].append(point["vi_w"])
    figure, axes = plt.subplots(7, 1, figsize=(11, 15), sharex=True)
    colors = ("#277da1", "#f9844a", "#43aa8b", "#8f5aa6")
    for axis, (address, name, _) in zip(axes, RAILS):
        for category, (kind, opcode, label) in enumerate(categories):
            values = grouped[(kind, opcode, address)]
            if not values:
                continue
            # Deterministic sub-pixel spread exposes overlapping discrete codes.
            offsets = [((index * 37) % 101 - 50) / 250 for index in range(len(values))]
            axis.scatter([category + dx for dx in offsets], values,
                         s=4, alpha=.18, color=colors[category], linewidths=0,
                         label=label if address == RAILS[0][0] else None)
            median = statistics.median(values)
            axis.plot([category-.22, category+.22], [median, median],
                      color="#111111", lw=1.2)
            axis.text(category, max(values), f"n={len(values)}",
                      fontsize=6, ha="center", va="bottom")
        axis.set_ylabel(f"{name}\nW", fontsize=8)
        axis.grid(axis="y", alpha=.18)
    axes[0].legend(loc="upper right", ncol=4, fontsize=7, frameon=False)
    axes[-1].set_xticks(range(4), [x[2] for x in categories])
    axes[-1].set_xlim(-.5, 3.5)
    figure.suptitle("Raw V×I observations wholly inside conservative command BUSY")
    figure.text(.5, .007, "Each dot is a read envelope contained within one BUSY interval; "
                "black bars are point medians. These are not time-weighted active means.",
                ha="center", fontsize=8)
    figure.tight_layout(rect=(0, .02, 1, .98))
    save_pair(figure, stem)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--jsonl", type=Path, required=True)
    parser.add_argument("--prefix", type=Path, required=True)
    args = parser.parse_args()
    stems = {name: args.prefix.with_name(args.prefix.name + "_" + name)
             for name in ("summary", "rail_points", "vi_pout", "common_coverage",
                          "busy_host", "busy_conditional")}
    outputs = [stem.with_suffix(ext) for stem in stems.values() for ext in (".png", ".svg")]
    require(args.prefix.parent.is_dir() and all(not path.exists() for path in outputs),
            "Figure paths must be new files in an existing directory")
    result = json.loads(args.analysis.read_text(encoding="utf-8"))
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    require(result["status"] == "PARTIAL_WITH_LIMITS"
            and result["raw_record_validation_status"] == "PASS"
            and result["target_sweep_period_ms"] == 140,
            "Validated final analysis required")
    with args.jsonl.open(encoding="utf-8-sig") as stream:
        points = [item for line in stream if line.strip()
                  if (item := json.loads(line)).get("record") == "rail_point"]
    require(len(points) == metadata["complete_rail_points"], "Figure/raw point count differs")
    windows = result["windows"]
    plot(result, stems["summary"].with_suffix(".png"))
    plot(result, stems["summary"].with_suffix(".svg"))
    plot_rail_points(metadata, points, windows, stems["rail_points"].with_suffix(".png"))
    plot_rail_points(metadata, points, windows, stems["rail_points"].with_suffix(".svg"))
    vi_pout_figure(metadata, points, windows, stems["vi_pout"])
    common_coverage_figure(metadata, points, result, stems["common_coverage"])
    busy_host_figure(result, stems["busy_host"])
    busy_conditional_figure(result, stems["busy_conditional"])
    print(json.dumps({"status": "COMPLETE", "figures": [str(path) for path in outputs]}))


if __name__ == "__main__":
    main()
