#!/usr/bin/env python3
"""Render the independently merged six-task accuracy CSV as MD/PNG/vector PDF."""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
from typing import Any

from gsm8k_protocol import atomic_json, sha256_file
from six_model_matrix import FIVE_CONFIG_CASES, MODEL_SPECS

TASKS = ("piqa", "arc_easy", "gsm8k", "boolq", "hellaswag", "winogrande")
LABELS = ("PIQA", "ARC-e", "GSM8K", "BoolQ", "HellaS.", "WinoG.", "Avg.")
SETTINGS = {"bf16": "Full precision (BF16)", "a8w8_fp32": "A8W8 / FP32 scale",
            "a8w4_fp32": "A8W4 / FP32 scale", "a8w4_fp16": "A8W4 / FP16 scale",
            "reference_qdq": "A8W4 / ScaleCode"}


def load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        raw = list(csv.DictReader(handle))
    expected = {(spec.name, case) for spec in MODEL_SPECS for case in FIVE_CONFIG_CASES}
    by_key = {}
    protocols = set()
    for item in raw:
        key = item["model"], item["case"]
        if key not in expected or key in by_key:
            raise ValueError("CSV contains duplicate or unexpected model/case")
        row: dict[str, Any] = dict(item)
        for task in (*TASKS, "macro_accuracy"):
            text = item.get(task, "")
            if text in {"", "--"}:
                row[task] = None
                if task not in {"gsm8k", "macro_accuracy"}:
                    raise ValueError(f"missing historical task: {task}")
            else:
                number = float(text)
                if not math.isfinite(number) or not 0 <= number <= 1:
                    raise ValueError(f"accuracy outside [0,1]: {task}")
                row[task] = number
        if row["gsm8k"] is None:
            if row["macro_accuracy"] is not None:
                raise ValueError("partial row must not report a six-task average")
            if item.get("status") == "validated":
                raise ValueError("validated row has no GSM8K score")
        else:
            if item.get("status") != "validated" or item.get("gsm8k_full_split") != "True" or item.get("gsm8k_independent_harness_validated") != "True":
                raise ValueError("GSM8K score lacks independent full-test validation")
            expected_average = sum(row[task] for task in TASKS) / 6
            if row["macro_accuracy"] is None or not math.isclose(row["macro_accuracy"], expected_average, rel_tol=0, abs_tol=1e-14):
                raise ValueError("average differs from six unrounded task scores")
            if not item.get("gsm8k_protocol_id"):
                raise ValueError("validated GSM8K row lacks protocol ID")
            protocols.add(item["gsm8k_protocol_id"])
        by_key[key] = row
    if set(by_key) != expected or len(raw) != 30:
        raise ValueError("accuracy table requires exactly six models x five settings")
    if len(protocols) > 1:
        raise ValueError("accuracy table cannot mix GSM8K protocol versions")
    return [by_key[(spec.name, case)] for spec in MODEL_SPECS for case in FIVE_CONFIG_CASES]


def display(value: float | None) -> str:
    return "--" if value is None else f"{100 * value:.2f}"


def render(input_csv: Path, output_dir: Path) -> dict[str, Any]:
    input_csv, output_dir = input_csv.resolve(), output_dir.resolve()
    rows = load_rows(input_csv)
    output_dir.mkdir(parents=True, exist_ok=True)
    names = ["accuracy_table.md", "accuracy_table.png", "accuracy_table.pdf", "render_manifest.json"]
    if any((output_dir / name).exists() for name in names):
        raise FileExistsError("render output artifacts already exist; choose a new output directory")
    count = sum(row["gsm8k"] is not None for row in rows)
    validation_path = input_csv.parent / "validation.json"
    validation = None
    if count:
        if not validation_path.is_file():
            raise ValueError("GSM8K table requires the independent validation.json beside its CSV")
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        if (validation.get("schema") != "scalellm_gsm8k_independent_validation_v1" or
                validation.get("artifacts", {}).get("six_task_with_gsm8k.csv") != sha256_file(input_csv) or
                validation.get("groups_validated") != count or
                validation.get("full_validated") is not (count == 30)):
            raise ValueError("CSV differs from its independent validation report")
    protocols = sorted({row["gsm8k_protocol_id"] for row in rows if row["gsm8k"] is not None})
    relative_csv = os.path.relpath(input_csv, output_dir)
    markdown = ["# Six-model five-setting accuracy", "",
                f"GSM8K independent full-test validation: **{count}/30**. Accuracy is in percent.", "",
                f"Source: [six-task CSV]({relative_csv}). [PNG](accuracy_table.png) · [PDF](accuracy_table.pdf)", "",
                "| Model | Setting | PIQA | ARC-e | GSM8K | BoolQ | HellaS. | WinoG. | Avg. |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for index, row in enumerate(rows):
        label = row["model"] if index % 5 == 0 else ""
        values = [display(row[task]) for task in (*TASKS, "macro_accuracy")]
        markdown.append("| " + " | ".join([label, SETTINGS[row["case"]], *values]) + " |")
    markdown += ["", "GSM8K: main/test, all 1,319 questions, 5-shot raw prompts, greedy generation, strict exact match.",
                 "Other five tasks: complete evaluation splits, 0-shot likelihood, literature_2048 (context=2,048).",
                 "Avg. is the equal-weight mean of six unrounded scores; -- means pending or unvalidated. FP32/FP16 refer to scale precision.",
                 "HellaS. = HellaSwag; WinoG. = WinoGrande; ARC-e = ARC-Easy.", "",
                 "Cache v2 checks the native cached call path; cache-on/off equivalence is not claimed. The original 0.125/0.01 comparison remains diagnostic.", "",
                 "GSM8K protocol: " + (", ".join(f"`{value}`" for value in protocols) if protocols else "pending"),
                 "", f"Source CSV SHA-256: `{sha256_file(input_csv)}`.", ""]
    (output_dir / "accuracy_table.md").write_text("\n".join(markdown), encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties, findfont
    from matplotlib.patches import Rectangle
    font = findfont(FontProperties(family="STIXGeneral"), fallback_to_default=False)
    with plt.rc_context({"font.family": "STIXGeneral", "mathtext.fontset": "stix", "pdf.fonttype": 42}):
        fig = plt.figure(figsize=(15, 14.4), facecolor="white")
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        ax.text(.5, .974, "TABLE III", ha="center", va="center", fontsize=17)
        ax.text(.5, .948, "MODEL ACCURACY UNDER DIFFERENT SCALE REPRESENTATIONS", ha="center", va="center", fontsize=17)
        subtitle = "(SOFTWARE QUANTIZATION SIMULATION)." if count == 30 else f"(SOFTWARE QUANTIZATION SIMULATION; GSM8K VALIDATED {count}/30)."
        ax.text(.5, .924, subtitle, ha="center", va="center", fontsize=15)
        left, right, setting_x = .018, .988, .235
        header_y, first_y, row_height = .878, .842, .0246
        number_centers = [.527, .602, .677, .752, .827, .902, .974]
        ax.hlines(.899, left, right, linewidth=1.25, color="black")
        ax.text(.022, header_y, "Model", fontsize=15, va="center")
        ax.text(setting_x, header_y, "Setting", fontsize=15, va="center")
        for center, label in zip(number_centers, LABELS, strict=True):
            ax.text(center, header_y, label, fontsize=15, va="center", ha="center")
        ax.hlines(.858, left, right, linewidth=.8, color="black")
        for index, row in enumerate(rows):
            y = first_y - index * row_height
            if row["case"] == "reference_qdq":
                ax.add_patch(Rectangle((setting_x-.007, y-row_height*.49), right-setting_x+.007,
                                       row_height*.98, facecolor="#e1f1f5", edgecolor="none", zorder=0))
            if index % 5 == 0:
                label = row["model"]
                if label == "DeepSeek-R1-Distill-Llama-8B":
                    label = "DeepSeek-R1-\nDistill-Llama-8B"
                ax.text(.022, y+.007 if "\n" in label else y, label, fontsize=14,
                        va="top" if "\n" in label else "center", linespacing=.95)
            ax.text(setting_x, y, SETTINGS[row["case"]], fontsize=14.5, va="center")
            for center, task in zip(number_centers, (*TASKS, "macro_accuracy"), strict=True):
                ax.text(center, y, display(row[task]), fontsize=14.5, va="center", ha="center")
            if index % 5 == 4:
                ax.hlines(y-row_height*.55, left, right, linewidth=1.1 if index == 29 else .8, color="black")
        footnotes = [
            f"Accuracy (%). GSM8K full-test independent validation: {count}/30 settings. -- means pending or unvalidated.",
            "GSM8K: 5-shot raw prompts, greedy generation, strict exact match, all 1,319 main/test questions.",
            "Other five tasks: 0-shot likelihood, complete evaluation splits, literature_2048. Avg.: six-task equal-weight mean.",
            "Cache v2 validates native cached calls; cache-on/off equivalence is not claimed. Original tolerance checks remain diagnostic.",
            "HellaS. = HellaSwag; WinoG. = WinoGrande; ARC-e = ARC-Easy. FP32 / FP16 denote scale precision.",
        ]
        for index, text in enumerate(footnotes):
            ax.text(left, .102-index*.018, text, fontsize=11.6, va="center")
        fig.savefig(output_dir / "accuracy_table.png", dpi=180, bbox_inches="tight", pad_inches=.04)
        fig.savefig(output_dir / "accuracy_table.pdf", bbox_inches="tight", pad_inches=.04,
                    metadata={"Title": "Six-model six-task accuracy", "Creator": "ScaleLLM render_accuracy_table.py"})
        plt.close(fig)
    manifest = {"schema": "scalellm_six_task_accuracy_render_v1", "source_csv": str(input_csv),
                "source_csv_sha256": sha256_file(input_csv), "groups_expected": 30, "gsm8k_groups_validated": count,
                "validation_report": str(validation_path) if validation else None,
                "validation_report_sha256": sha256_file(validation_path) if validation else None,
                "font_family": "STIXGeneral", "font_file": font,
                "task_order": list(TASKS), "average": "mean of six unrounded 0-1 scores, then percent formatting",
                "gsm8k_protocol_ids": protocols,
                "artifacts": {name: sha256_file(output_dir / name) for name in names if name != "render_manifest.json"},
                "renderer_sha256": sha256_file(Path(__file__).resolve())}
    atomic_json(output_dir / "render_manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", "--csv", type=Path, required=True, dest="input_csv")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = render(args.input_csv, args.output_dir)
    print(f"Rendered {result['gsm8k_groups_validated']}/30 validated GSM8K settings into {args.output_dir}")


if __name__ == "__main__":
    main()
