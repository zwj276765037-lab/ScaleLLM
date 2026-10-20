#!/usr/bin/env python3
"""One English output-distribution figure, rendered directly from measured TV."""
from pathlib import Path
import csv
import hashlib
import json
import os

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
os.environ["MPLCONFIGDIR"] = str(HERE / ".mpl_cache")
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image


def identity(path):
    return {"path": str(path.resolve()),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    source = BASE / "01_full1024/per_position_tv.csv"
    with source.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    values = np.sort(np.array([float(row["tv_percent"]) for row in rows]))
    assert len(values) == 103700 and len({row["doc_id"] for row in rows}) == 1024
    assert np.isfinite(values).all() and np.all((values >= 0) & (values <= 100))
    # Inverse empirical CDF: exactly 95% / 99% of observed positions satisfy
    # the displayed order-statistic thresholds, before display rounding.
    quantiles = {
        str(percent): float(values[int(np.ceil(percent * len(values) / 100)) - 1])
        for percent in [50, 95, 99]
    }
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10, "axes.labelsize": 11,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.axisbelow": True, "axes.linewidth": .8,
        "figure.facecolor": "white", "savefig.facecolor": "white",
    })
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    fig.subplots_adjust(left=.105, right=.965, bottom=.18, top=.815)
    fig.text(.105, .945, "Next-token distribution fidelity", fontsize=15, weight="semibold")
    fig.text(.105, .885,
             "Rounded vs. retained precision · 103,700 positions · 1,024 documents",
             fontsize=9.5, color="#52616D")
    x = np.r_[0., values]
    y = np.r_[0., 100 * np.arange(1, len(values) + 1) / len(values)]
    ax.step(x, y, where="post", color="#2166AC", linewidth=1.9)
    ax.set_xscale("symlog", linthresh=.1, linscale=.65)
    ax.set_xlim(0, 34)
    ax.set_ylim(0, 104)
    ax.set_xticks([0, .1, .5, 1, 2, 5, 10, 30],
                  ["0", "0.1", "0.5", "1", "2", "5", "10", "30"])
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_xlabel("Softmax distribution difference (TV, %)", labelpad=8)
    ax.set_ylabel("Cumulative token positions (%)", labelpad=8)
    ax.grid(axis="y", color="#DAE0E6", linewidth=.6)
    for percent in [95, 99]:
        q = quantiles[str(percent)]
        ax.scatter([q], [percent], s=32, facecolor="#D36B19",
                   edgecolor="white", linewidth=.6, zorder=4)
    ax.annotate("95th percentile\nTV = 1.83%",
                xy=(quantiles["95"], 95), xytext=(.14, 75),
                ha="left", va="center", fontsize=10, linespacing=1.4,
                arrowprops={"arrowstyle": "-", "color": "#778692", "lw": .8},
                bbox={"facecolor": "white", "edgecolor": "none", "pad": 3})
    ax.annotate("99th percentile\nTV = 3.68%",
                xy=(quantiles["99"], 99), xytext=(5.2, 75),
                ha="left", va="center", fontsize=10, linespacing=1.4,
                arrowprops={"arrowstyle": "-", "color": "#778692", "lw": .8},
                bbox={"facecolor": "white", "edgecolor": "none", "pad": 3})
    mass_coverage = float(100 * np.mean(values <= 2))
    ax.text(.53, .12,
            f"{mass_coverage:.2f}% of positions:\n≥ 98% shared probability mass",
            transform=ax.transAxes, fontsize=10, linespacing=1.5, color="#194F82",
            bbox={"boxstyle": "round,pad=.55", "facecolor": "#EDF4FA", "edgecolor": "none"})
    fig.text(.105, .025,
             "Full empirical CDF; x-axis linear near zero, logarithmic above 0.1%.",
             fontsize=8.5, color="#52616D")
    target = HERE / "figure_2_output_distribution_fidelity.png"
    fig.savefig(target, dpi=600)
    plt.close(fig)
    with Image.open(target) as im:
        dimensions = list(im.size)
        im.resize((2160, 1320), Image.Resampling.LANCZOS).save(
            HERE / "figure_2_output_distribution_fidelity_preview.png")
    summary = {
        "renderer": "Python / Matplotlib", "image_generation_model_used": False,
        "positions": len(values), "documents": 1024, "all_positions_and_full_tail_retained": True,
        "quantile_convention": "Inverse empirical CDF, ceil(q*N)-th observation; percentages displayed rounded.",
        "ecdf_quantile_tv_percent": quantiles,
        "shared_mass_percent_at_quantiles": {q: 100 - v for q, v in quantiles.items()},
        "existing_report_linear_interpolation_tv_percent":
            {str(q): float(np.quantile(values, q / 100)) for q in [50, 95, 99]},
        "maximum_tv_percent": float(values[-1]),
        "positions_with_TV_at_most_2_percent": int(np.sum(values <= 2)),
        "coverage_TV_at_most_2_percent": mass_coverage,
        "minimum_tv_percent": float(values[0]),
        "sources": [identity(source)],
        "script": identity(Path(__file__)),
        "output": {**identity(target), "pixels": dimensions, "dpi": 600},
        "scope": "Same fixed prefixes, full-vocabulary softmax, temperature 1; retained-intermediate-precision reference.",
        "interpretation": "Shared probability mass = sum(min(p_v,q_v)) = 1 - TV. Not an accuracy score or an observed token match rate.",
        "matplotlib": matplotlib.__version__,
    }
    (HERE / "figure_statistics.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
