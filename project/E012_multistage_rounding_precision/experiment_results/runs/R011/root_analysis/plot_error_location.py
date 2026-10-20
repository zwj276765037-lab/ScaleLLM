"""Render only independently checked R006 data; no model execution."""
import hashlib
import json
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager, pyplot as plt

HERE = Path(__file__).resolve().parent
REVIEW = HERE.parent / "independent_review"
stage_path = REVIEW / "existing_stage_review.json"
cross_path = REVIEW / "residual_cross_review.json"
stages = json.loads(stage_path.read_text())["layer32_existing_stages"]
pooled = json.loads(cross_path.read_text())["pooled"]
font = subprocess.check_output(["fc-match", "-f", "%{file}", "Noto Sans CJK SC"], text=True).strip()
font_manager.fontManager.addfont(font)
plt.rcParams.update({"font.family": font_manager.FontProperties(fname=font).get_name(),
                     "font.size": 11, "axes.unicode_minus": False,
                     "axes.spines.top": False, "axes.spines.right": False})
ink, blue, orange = "#20354b", "#246ba0", "#d46b24"
keys = ["layer31_input_previous_block", "mlp_residual_input_propagation",
        "mlp_residual_sum_propagation", "final_norm"]
labels = ["第32层入口", "注意力残差后", "MLP残差后", "最终归一化后"]
med = [stages[k]["relative_l2_percent"]["0.5"] for k in keys]
p95 = [stages[k]["relative_l2_percent"]["0.95"] for k in keys]
retained = [100 * (1 - pooled["signal_cancellation_fraction_of_component_sum"]),
            100 * (1 - pooled["error_cancellation_fraction_of_component_sum"])]
fig, (ax, bx) = plt.subplots(1, 2, figsize=(11.8, 4.8), gridspec_kw={"width_ratios": [1.35, 1]})
fig.suptitle("第32层：误差跳升发生在 MLP 残差合并处", x=.5, y=.97,
             color=ink, fontsize=17, fontweight="bold")
fig.text(.5, .895, "1024篇固定文本 · 103,700个位置 · 原始双轨迹数据", ha="center", color="#586878")
ax.axvspan(1.52, 2.48, color="#fff2e4", zorder=0)
ax.plot(range(4), med, "o-", color=blue, label="文本误差中位数", linewidth=2)
ax.plot(range(4), p95, "D-", color=orange, label="文本误差P95", linewidth=2)
for x, (m, p) in enumerate(zip(med, p95)):
    ax.annotate(f"{m:.3f}%", (x, m), xytext=(0, -19), textcoords="offset points", ha="center", color=blue)
    ax.annotate(f"{p:.3f}%", (x, p), xytext=(0, 9), textcoords="offset points", ha="center", color=orange)
ax.set(xticks=range(4), xticklabels=labels, ylim=(.55, 3.2), ylabel="相对L2误差（%）")
ax.grid(axis="y", alpha=.2)
ax.legend(loc="upper left", frameon=False, fontsize=10)
bx.bar([0, 1], retained, color=[blue, orange], width=.58, zorder=3)
bx.axhline(100, color="#8493a0", linestyle="--", linewidth=1)
for x, y in enumerate(retained):
    bx.text(x, y + 3, f"{y:.2f}", ha="center", fontweight="bold", color=ink, fontsize=15)
bx.set(xticks=[0, 1], xticklabels=["真实信号能量", "误差能量"], ylim=(0, 119),
       ylabel="MLP残差合并后保留量（各自合并前之和=100）")
bx.grid(axis="y", alpha=.2, zorder=0)
bx.text(.5, .03, "信号抵消54.64%，误差仅抵消1.54%", transform=bx.transAxes,
        ha="center", color=ink, fontsize=10, bbox={"facecolor": "white", "edgecolor": "none", "alpha": .9})
fig.text(.5, .045, "合并后的误差大多来自两路已有差异；此图不把它解释为加法器自身舍入损失。",
         ha="center", color="#586878", fontsize=10)
fig.subplots_adjust(left=.07, right=.98, top=.80, bottom=.18, wspace=.34)
fig.savefig(HERE / "layer32_error_location.png", dpi=180, facecolor="white")
plt.close(fig)
manifest = {"source_files": [{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                              for p in (stage_path, cross_path)],
            "stage_keys": keys, "median_percent": med, "p95_percent": p95,
            "energy_retained_normalized_to_own_component_sum": retained,
            "scope": "Descriptive original1024 same-document paired trajectories, not new3document intervention."}
(HERE / "plot_sources.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
print(HERE / "layer32_error_location.png")
