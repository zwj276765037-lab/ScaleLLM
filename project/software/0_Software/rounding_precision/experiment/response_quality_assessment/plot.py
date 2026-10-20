"""Plot only real resolved AI assessments; no fabricated or empty result chart."""
import argparse
import csv
import json
from pathlib import Path

try:
    from .common import identity, write_json
    from .aggregate import LABELS
except ImportError:
    from common import identity, write_json
    from aggregate import LABELS


def render(summary, output_dir):
    if summary.get("schema") != "scalellm_response_quality_aggregate_v1" or summary.get("execution_state") != "completed":
        raise ValueError("requires completed real assessment aggregate")
    if not any(d["overall"]["resolved_question_clusters"] for d in summary["datasets"]):
        raise ValueError("no resolved assessments; refusing to draw a quality chart")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    colors = {"Better": "#287c8e", "Comparable": "#abb5bd", "Worse": "#d65a48"}
    datasets = summary["datasets"]
    heights = [len(d["groups"]) + 1 for d in datasets]
    fig, axes = plt.subplots(len(datasets), 1, figsize=(14.0, 2.3 + .50 * sum(heights)), squeeze=False,
                             gridspec_kw={"height_ratios": heights})
    for ax, dataset in zip(axes[:, 0], datasets):
        rows = dataset["groups"] + [{"group": "Overall", **dataset["overall"]}]
        for i, row in enumerate(rows):
            left = 0
            if row["resolved_question_clusters"]:
                for label in LABELS:
                    value = row["percent_of_resolved"][label]
                    ax.barh(i, value, left=left, height=.68, color=colors[label], edgecolor="white", linewidth=.6)
                    if value >= 5:
                        ax.text(left + value/2, i, f"{value:.1f}%", ha="center", va="center", fontsize=9,
                                color="white" if label != "Comparable" else "#182126")
                    left += value
            else:
                ax.text(1, i, "No resolved assessment", va="center", color="#6b6b6b", fontsize=9)
            intervals = row["conditional_question_wilson_95_ci_percent"]
            interval_text = "Wilson 95%: " + "; ".join(f'{label[0]} {intervals[label]["low"]:.1f}–{intervals[label]["high"]:.1f}' if intervals[label] else f'{label[0]} unavailable' for label in LABELS)
            ax.text(101.5, i, f'{row["resolved_question_clusters"]}/{row["planned_question_clusters"]} resolved; {row["unresolved_question_clusters"]} unresolved\n' + interval_text,
                    va="center", fontsize=7.8, linespacing=1.4)
        ax.set_yticks(range(len(rows)), [r["group"].replace("_", " ").title() for r in rows])
        ax.invert_yaxis()
        ax.set_xlim(0, 100)
        ax.set_xticks([0, 25, 50, 75, 100])
        ax.set_xlabel("Share of resolved question clusters (%)")
        title = "AlpacaEval — Source groups" if dataset["dataset"] == "alpaca_eval" else "MT-Bench — Task categories (whole two-turn conversations)"
        official_target = dataset.get("official_benchmark_target_questions")
        if official_target:
            title += f' — roster {dataset["overall"]["planned_question_clusters"]}/{official_target}'
        ax.set_title(title, loc="left", fontsize=11, pad=9)
        ax.spines[["right", "top"]].set_visible(False)
        ax.grid(axis="x", alpha=.13)
        ax.set_axisbelow(True)
    fig.suptitle("Response quality relative to the retained-precision reference", x=.12, ha="left", fontsize=14)
    fig.legend(handles=[Patch(facecolor=colors[label], label=f"{label} than Reference" if label != "Comparable" else "Comparable to Reference") for label in LABELS],
               loc="upper center", bbox_to_anchor=(.50,.955), ncol=3, frameon=False, fontsize=10)
    foot = ("Preliminary AI-agent assessment; not human review or official benchmark leaderboard scores.\n"
            "Two swapped orders must agree. Missing, truncated, failed or conflicting cases remain unresolved.\n"
            "Pointwise Wilson 95% intervals use resolved questions; independent-question sampling is an unverified assumption.\n"
            "Benchmarks have separate overall rows. Comparable does not establish correctness or semantic equivalence.")
    fig.text(.12, .015, foot, ha="left", va="bottom", fontsize=8, color="#3d4449", linespacing=1.5)
    fig.subplots_adjust(left=.17, right=.65, top=.88, bottom=.12, hspace=.46)
    output_dir.mkdir(parents=True, exist_ok=False)
    path = output_dir / "response_quality.png"
    fig.savefig(path, dpi=300, facecolor="white", bbox_inches="tight", pad_inches=.16)
    plt.close(fig)
    return path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--summary", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()
    summary = json.loads(a.summary.read_text())
    image = render(summary, a.output_dir)
    write_json(a.output_dir / "source_data.json", {"schema": "scalellm_response_quality_figure_data_v1",
        "summary": summary, "source_identity": identity(a.summary), "renderer_identity": identity(__file__),
        "png": identity(image), "statistical_scope": "conditional resolved proportions; all planned/resolved/unresolved denominators shown"})
    with (a.output_dir / "confidence_intervals.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["dataset", "group", "label", "count", "resolved", "planned", "unresolved", "percent", "wilson95_low", "wilson95_high", "bootstrap95_low_aux", "bootstrap95_high_aux"])
        for dataset in summary["datasets"]:
            for row in dataset["groups"] + [{"group": "Overall", **dataset["overall"]}]:
                for label in LABELS:
                    ci = row["conditional_question_wilson_95_ci_percent"][label]
                    auxiliary = row["conditional_cluster_bootstrap_95_ci_percent"][label]
                    writer.writerow([dataset["dataset"], row["group"], label, row["counts"][label], row["resolved_question_clusters"], row["planned_question_clusters"],
                                     row["unresolved_question_clusters"], row["percent_of_resolved"][label], ci["low"] if ci else None, ci["high"] if ci else None,
                                     auxiliary["low"] if auxiliary else None, auxiliary["high"] if auxiliary else None])
    write_json(a.output_dir / "output_manifest.json", {"execution_state": "completed", "sources": [identity(a.summary), identity(__file__)],
        "outputs": [identity(p) for p in sorted(a.output_dir.iterdir()) if p.is_file()]})
    print(str(image.resolve()))


if __name__ == "__main__":
    main()
