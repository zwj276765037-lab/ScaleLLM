"""Plot measured BF16 local replay only, keeping invalid and other sources out."""
from __future__ import annotations

import argparse
import csv
from fractions import Fraction
import json
import math
from pathlib import Path
import sys

from run_local_experiment import identity, write_new

OPS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def measured_points(path: Path) -> tuple[list[dict], dict]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    points, excluded, lengths = [], [], set()
    for row in rows:
        source = row.get("provenance", {})
        if source.get("kind") != "real_trace" or source.get("trajectory") != "bf16":
            raise ValueError("plot accepts only real BF16 local input replay; no synthetic/production mixing")
        length = source.get("captured_activation", {}).get("source_shape", [None, None])[1]
        if length not in (32, 128):
            raise ValueError("missing actual 32/128-token source geometry")
        lengths.add(length)
        if row.get("status") != "ok" or not row.get("metrics", {}).get("bounds", {}).get("applicable"):
            excluded.append({"sample_id": row.get("sample_id"), "status": row.get("status"),
                             "reasons": row.get("metrics", {}).get("bounds", {}).get("excluded_reasons", [])})
            continue
        if not row.get("source_file_validation", {}).get("verified"):
            raise ValueError("real source files were not checksum-verified")
        current = row["current"]["output_code"]
        output_only = row["output_only"]["output_code"]
        exact = Fraction(int(row["exact"]["numerator"]), int(row["exact"]["denominator"]))
        points.append({"sample_id": row["sample_id"], "layer": source["layer"], "op": source["op"],
                       "token": source["token"], "column": source["column"], "profile": row["profile"],
                       "current_code": current, "output_only_code": output_only,
                       "signed_delta_lsb": current - output_only,
                       "current_error_lsb": float(Fraction(current) - exact * 65536),
                       "output_only_error_lsb": float(Fraction(output_only) - exact * 65536)})
    if len(lengths) != 1:
        raise ValueError("32/128-token attempts must be plotted separately")
    if not points:
        raise ValueError("no eligible measured points")
    return points, {"total_rows": len(rows), "eligible_rows": len(points), "excluded_rows": excluded,
                    "tokens": next(iter(lengths)), "trajectory": "bf16", "local_only": True}


def plot(path: Path, directory: Path) -> dict:
    points, scope = measured_points(path)
    directory.mkdir(parents=True, exist_ok=False)
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    from matplotlib.font_manager import FontProperties
    from matplotlib.ticker import MaxNLocator
    font_file = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    font = FontProperties(fname=str(font_file)) if font_file.is_file() else FontProperties(family="sans-serif")
    plt.rcParams.update({"axes.unicode_minus": False, "font.size": 10, "savefig.dpi": 180,
                         "svg.fonttype": "path", "pdf.fonttype": 42})
    csv_path = directory / "paired_measured_points.csv"
    with csv_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(points[0]))
        writer.writeheader()
        writer.writerows(points)
    layers = sorted({point["layer"] for point in points})
    fig, axes = plt.subplots(len(layers), 1, figsize=(10, 2.15 * len(layers) + 1), sharex=True, squeeze=False)
    for panel, layer in enumerate(layers):
        ax = axes[panel, 0]
        ax.axhline(0, color="#777777", linewidth=.8)
        for index, op in enumerate(OPS):
            selected = sorted((point for point in points if point["layer"] == layer and point["op"] == op),
                              key=lambda point: (point["token"], point["column"]))
            count = len(selected)
            x = [index + (position - (count - 1) / 2) * .043 for position in range(count)]
            ax.scatter(x, [point["signed_delta_lsb"] for point in selected], color="#176B9B", s=23, alpha=.85)
            ax.text(index, 1.02, f"n={count}", transform=ax.get_xaxis_transform(), ha="center", fontsize=8)
        ax.set_ylabel(f"层 {layer}\n差值 (LSB)", fontproperties=font)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.grid(axis="y", color="#dddddd", linewidth=.5)
        ax.spines[["top", "right"]].set_visible(False)
    axes[-1, 0].set_xticks(range(len(OPS)), OPS)
    fig.suptitle(f"当前实现 − 仅输出舍入：真实 BF16 局部输入，{scope['tokens']} tokens", fontproperties=font, y=.99)
    fig.text(.5, .01, f"单文本；层 {','.join(map(str,layers))}；首末 token × 4 输出通道；有效 {len(points)}/{scope['total_rows']}；每点一个输出，横向偏移仅防重叠。全 V5 / PPL / ACC 未测。",
             ha="center", fontproperties=font, fontsize=8)
    fig.tight_layout(rect=(0, .045, 1, .95))
    outputs = []
    for ext in ["png", "pdf", "svg"]:
        destination = directory / f"paired_output_delta.{ext}"
        fig.savefig(destination)
        outputs.append(identity(destination))
    plt.close(fig)
    profiles = [profile for profile in ["attention", "mlp_gate_up", "mlp_down"]
                if any(point["profile"] == profile for point in points)]
    fig, ax = plt.subplots(figsize=(7.8, 4.2))
    bars = {}
    for error, label, offset, color in [("output_only_error_lsb", "仅输出舍入", -.17, "#6CA787"),
                                        ("current_error_lsb", "当前实现", .17, "#176B9B")]:
        values = []
        for profile in profiles:
            chosen = [point[error] for point in points if point["profile"] == profile]
            values.append(math.sqrt(sum(value * value for value in chosen) / len(chosen)))
        bars[label] = dict(zip(profiles, values))
        ax.bar([index + offset for index in range(len(profiles))], values, width=.32, label=label, color=color)
    ax.axhline(0, color="#333333", linewidth=1, linestyle="--", label="精确 oracle（参考）")
    ax.set_xticks(range(len(profiles)), [f"{profile}\nn={sum(point['profile']==profile for point in points)}" for profile in profiles])
    ax.set_ylabel("相对精确 oracle 的 RMSE (F16 输出 LSB)", fontproperties=font)
    ax.set_title(f"固定相同整数码与 ScaleCode · {scope['tokens']}-token BF16 局部输入", fontproperties=font)
    ax.legend(prop=font, frameon=False)
    ax.grid(axis="y", color="#dddddd", linewidth=.5)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    for ext in ["png", "pdf", "svg"]:
        destination = directory / f"error_vs_exact_reference.{ext}"
        fig.savefig(destination)
        outputs.append(identity(destination))
    plt.close(fig)
    manifest = {"schema": "m005_real_plot_manifest_v1", "input": identity(path),
                "plot_code": identity(Path(__file__)), "command": [sys.executable, *sys.argv],
                "scope": scope, "matplotlib_version": matplotlib.__version__,
                "font": identity(font_file) if font_file.is_file() else None,
                "paired_points": identity(csv_path), "rmse_lsb_by_profile": bars,
                "figures": outputs, "population_inference_or_noninferiority_claim": False}
    write_new(directory / "plot_manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = plot(args.results.resolve(), args.output_dir.resolve())
    print(json.dumps({"figures": len(result["figures"]), "scope": result["scope"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
