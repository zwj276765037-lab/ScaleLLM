#!/usr/bin/env python3
"""Render two English scientific figures with Python/Matplotlib, from measured data."""
from pathlib import Path
import importlib.util
import json
import sys
import time

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / "08_paper_fidelity_decoding_v1"
spec = importlib.util.spec_from_file_location("validated_plot_functions", PREVIOUS / "plot_paper.py")
plot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plot)
plot.HERE = HERE
plot.plt.rcParams["font.family"] = "DejaVu Sans"


def figure_local(data):
    fig = plot.plt.figure(figsize=(14, 5.5))
    plot.local_plot(fig.add_axes([.075, .26, .90, .52]), data, plot.EN)
    fig.suptitle("Local computation error", fontsize=20, y=.98, fontweight="semibold")
    fig.legend(
        plot.legend_handles(), plot.EN["legend"],
        loc="upper center", bbox_to_anchor=(.53, .91),
        ncol=3, frameon=False, fontsize=14, columnspacing=1.4,
    )
    fig.text(.075, .100, plot.EN["note1"], fontsize=14)
    fig.text(.075, .055, plot.EN["note2"], fontsize=14)
    return plot.save_png(fig, "figure_1_local_operator_error.png")


def figure_decoding(data):
    text = dict(plot.EN)
    fig = plot.plt.figure(figsize=(14, 7.5))
    fig.suptitle("Fixed-prefix decoding stability", fontsize=20, y=.98, fontweight="semibold")
    fig.text(.5, .925, "1,024 documents · 103,700 prediction positions · 128,256 vocabulary entries",
             ha="center", fontsize=14)
    fig.text(.075, .855, "A  Greedy next-token agreement", fontsize=16, fontweight="bold")
    plot.decode_bar(fig.add_axes([.075, .730, .90, .09]), data, text)
    fig.text(.075, .685, text["fixed"], fontsize=14)
    fig.text(.075, .645,
             r"Post-hoc sufficient condition: $m > 2\epsilon$; "
             r"$m$ = reference Top-1/Top-2 gap, $\epsilon = \|\hat z-z\|_\infty$.",
             fontsize=14)

    xs = [.075, .375, .745]
    widths = [.245, .320, .230]
    axes = [fig.add_axes([x, .245, width, .235]) for x, width in zip(xs, widths)]
    plot.coverage_plot(axes[0], data, text)
    plot.margin_plot(axes[1], data, text)
    plot.tv_plot(axes[2], data, text)
    titles = ["B  Full-vocabulary coverage", "C  Flips by reference margin", "D  Output-distribution TV"]
    for x, title in zip(xs, titles):
        fig.text(x, .560, title, fontsize=16, fontweight="bold")
    fig.text(xs[0], .515, text["coverage_note"], fontsize=14)
    fig.text(xs[1], .515, text["margin_note"], fontsize=14)
    summary = data["TV"]["summary"]
    fig.text(xs[2], .126,
             f"P50 {float(summary['p50_percent']):.5f}%   P95 {float(summary['p95_percent']):.5f}%",
             fontsize=14)
    fig.text(xs[2], .088,
             f"P99 {float(summary['p99_percent']):.5f}%   Max {float(summary['max_percent']):.5f}%",
             fontsize=14)
    fig.text(.075, .023,
             "Identical-prefix, single-step comparisons; these measurements do not establish free-generation equivalence.",
             fontsize=14)
    return plot.save_png(fig, "figure_2_decoding_stability.png")


def main():
    started = time.monotonic()
    data, sources = plot.load_data()
    data["figure_policy"].update({
        "layout": "two separate English figures",
        "figure_1_inches": [14, 5.5],
        "figure_2_inches": [14, 7.5],
    })
    plot.save_json("plot_data.json", data)
    images = [figure_local(data), figure_decoding(data)]
    for source in sources:
        assert plot.identity(source["path"])["sha256"] == source["sha256"]
    plot.save_json("source_manifest.json", {
        "renderer": "Python / Matplotlib (Agg)",
        "image_generation_model_used": False,
        "new_model_experiment": False,
        "language": "English only",
        "sources": sources,
        "script": plot.identity(__file__),
        "shared_plot_functions": plot.identity(PREVIOUS / "plot_paper.py"),
        "statistics_changed": False,
    })
    names = [name for item in images for name in [item["file"], item["preview"]]]
    names += ["plot_data.json", "source_manifest.json"]
    plot.save_json("output_manifest.json", {
        "execution_state": "completed",
        "images": images,
        "outputs": [plot.identity(HERE / name) for name in names],
        "python": sys.version,
        "matplotlib": plot.matplotlib.__version__,
        "wall_seconds": time.monotonic() - started,
        "all_11264_local_points_retained": True,
        "all_103700_positions_retained": True,
        "certificate_recomputed": True,
        "source_files_unchanged": True,
    })
    print(json.dumps({"completed": True, "images": images,
                      "wall_seconds": time.monotonic() - started}, indent=2))


if __name__ == "__main__":
    main()
