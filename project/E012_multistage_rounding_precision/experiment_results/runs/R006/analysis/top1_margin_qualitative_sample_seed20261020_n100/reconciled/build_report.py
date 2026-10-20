"""Assemble manually reviewed annotations; no automatic semantic classifier."""
import collections
import csv
import datetime
import hashlib
import html
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
BASE = OUT.parent


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def identity(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def save_json(name, value):
    with (OUT / name).open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


LABELS = {
    "F": "局部格式变化",
    "W": "局部措辞或语法变化",
    "C": "内容、事实或指代差异",
    "L": "逻辑连接变化",
    "U": "上下文或续文不足，无法判断",
}
LABEL_NOTES = {
    "F": "仅当前上下文未见内容差异，不证明后续生成不变。",
    "W": "未见明确命题反转，不代表严格同义或语义无损。",
    "C": "涉及不同内容维度或事实候选，不等于已判定当前版本错误。",
    "L": "可见逻辑连接作用发生变化，尚未确认同一完整命题真值相反。",
    "U": "不能归入无害项；保留片段、否定、数值等风险旗标。",
}
samples = read_jsonl(BASE / "samples.jsonl")
root = {r["sample_id"]: r for r in read_jsonl(BASE / "root_annotation/annotations_v1.jsonl")}
other = {r["sample_id"]: r for r in read_jsonl(BASE / "independent_annotation/annotations_v1.jsonl")}
adj = json.loads((OUT / "adjudication.json").read_text())
decisions = {r["sample_id"]: r for r in adj["decisions"]}
expected_ids = [f"S{i:03d}" for i in range(1, 101)]
assert [s["sample_id"] for s in samples] == expected_ids
assert set(root) == set(other) == set(expected_ids)
disagreements = {
    sid for sid in expected_ids if root[sid]["label"] != other[sid]["primary_label"]
}
assert disagreements == set(decisions) and len(disagreements) == 16

rows = []
for s in samples:
    sid = s["sample_id"]
    a, b = root[sid], other[sid]
    label = decisions.get(sid, {}).get("final_label", a["label"])
    reason = decisions.get(sid, {}).get("reason", a["rationale_zh"])
    flags = sorted(set(a["risk_flags"] + b["riskflags"]))
    row = {
        "sample_id": sid,
        "doc_id": s["doc_id"],
        "domain": s["domain"],
        "position": s["position"],
        "reference_margin": s["reference_top1_margin"],
        "softmax_tv": s["softmax_tv"],
        "reference_top1_id": s["reference"]["id"],
        "current_top1_id": s["current"]["id"],
        "reference_token": s["reference"]["single_token_text"],
        "current_token": s["current"]["single_token_text"],
        "reference_token_repr": s["reference"]["single_token_repr"],
        "current_token_repr": s["current"]["single_token_repr"],
        "prefix": s["prefix_full_without_special_tokens"],
        "reference_joint_tail": s["reference"]["joint_tail12_prefix_and_token"],
        "current_joint_tail": s["current"]["joint_tail12_prefix_and_token"],
        "final_label": label,
        "category_zh": LABELS[label],
        "rationale_zh": reason,
        "risk_flags": flags,
        "root_initial_label": a["label"],
        "independent_initial_label": b["primary_label"],
        "initial_agreement": sid not in disagreements,
        "adjudicated": sid in decisions,
        "definite_semantic_reversal_established": False,
    }
    rows.append(row)

counts = collections.Counter(r["final_label"] for r in rows)
assert dict(counts) == {"U": 46, "C": 24, "W": 28, "F": 1, "L": 1}
with (OUT / "annotations.jsonl").open("x", encoding="utf-8") as f:
    for row in rows:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
with (OUT / "annotated_samples.csv").open("x", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    for row in rows:
        writer.writerow({**row, "risk_flags": ";".join(row["risk_flags"])})

sources = [
    BASE / "sample_manifest.json",
    BASE / "protocol.json",
    BASE / "samples.jsonl",
    BASE / "validation.json",
    BASE / "root_annotation/rubric.json",
    BASE / "root_annotation/sampling_reproduction.json",
    BASE / "root_annotation/annotations_v1.jsonl",
    BASE / "root_annotation/summary_v1.json",
    BASE / "independent_annotation/rubric.md",
    BASE / "independent_annotation/annotations_v1.jsonl",
    BASE / "independent_annotation/summary_v1.json",
    OUT / "adjudication.json",
]
summary = {
    "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "population": "876 Top-1 disagreements with reference margin < 0.05",
    "sampling": "Sorted (doc_id, position), Python random.Random(20261020).sample, 100 without replacement",
    "seed": 20261020,
    "sample_count": 100,
    "unique_documents": len({s["doc_id"] for s in samples}),
    "domains": dict(collections.Counter(s["domain"] for s in samples)),
    "review_method": "Two independent AI item-by-item reviews, frozen before comparison; Root adjudication. No independent human annotation.",
    "initial_agreement": 84,
    "initial_disagreements": 16,
    "final_counts": {label: counts[label] for label in LABELS},
    "category_definitions": LABEL_NOTES,
    "completed_proposition_reversals_established": 0,
    "logic_connector_case": "S094",
    "explicit_negation_unresolved_case": "S096",
    "limitations": [
        "One-step fixed-prefix token differences, not generated answers or full reasoning traces.",
        "No candidate is assumed to be correct; original next token is not a correctness label.",
        "F/W are not proofs of semantic equivalence; C/L are not measured task failures.",
        "46 uncertain examples remain in the denominator and are not counted as harmless.",
        "Both AI reviewers incidentally saw S001 auxiliary source-next token in schema inspection; neither used it as gold. Remaining sample views excluded it.",
        "Observed category percentages describe this sample, not task accuracy or exact population prevalence.",
        "No additional model inference or GPU execution.",
    ],
    "sources": [identity(q) for q in sources],
}
save_json("summary.json", summary)

example_ids = ["S009", "S050", "S020", "S024", "S028", "S092", "S094", "S096"]
by_id = {r["sample_id"]: r for r in rows}
md = [
    "# 低 Margin Top-1 翻转：100例局部定性审阅",
    "",
    "从参考 Margin < 0.05 的876个翻转位置中，按固定种子20261020无放回等概率抽取100例。"
    "样本来自93篇文档：网页54例、影评33例、新闻13例。样本名单先冻结，再解码和分类，没有替换难判样本。",
    "",
    "**结论：不能把低 Margin 翻转统一解释为等价或纯格式替换。**"
    "样本中既有局部措辞变化，也有人名、年龄、数量、时间和逻辑连接差异；46例因后续未知无法可靠分类。"
    "这些差异本身不判定哪一候选正确，也不等于任务准确率下降。",
    "",
    "## 分类统计",
    "",
    "| 类别 | 数量 / 100 | 解读 |",
    "|---|---:|---|",
]
for label in LABELS:
    md.append(f"| {LABELS[label]} | {counts[label]} | {LABEL_NOTES[label]} |")
md += [
    "",
    "## 代表性样本",
    "",
    "箭头方向始终为参考版本 → 舍入版本。下表仅截取实际输入前缀的末尾；完整可用前缀在逐例明细中。",
    "",
    "| 样本 | 前缀末尾 | 参考 token → 舍入 token | Margin | 分类与依据 |",
    "|---|---|---|---:|---|",
]
for sid in example_ids:
    r = by_id[sid]
    tail = r["prefix"][-95:].replace("\n", " ↵ ").replace("|", "\\|")
    pair = (r["reference_token_repr"] + " → " + r["current_token_repr"]).replace("|", "\\|")
    md.append(f"| {sid} | …{tail} | `{pair}` | {r['reference_margin']:.7f} | {r['category_zh']}：{r['rationale_zh']} |")
md += [
    "",
    "S094 的 except → and 显示例外与并列补充的逻辑连接变化，但没有观察完整后续，不能声称同一命题已被反转。"
    "S096 的 looking → not 位于否定相关位置，因 not 后的谓语未知归为不确定，仍重点标记。"
    "本样本没有确认 Yes ↔ No 式同一完整命题的反转；这不等于全部876例不存在此类情况。",
    "",
    "子词也可能只改变分词进度。例如S031的 Analyst 是 Analysts 的前缀，后续仍可补 s，"
    "不能据这一个token就确认单复数事实改变。不能把原文后续机械接到两个候选后，冒充模型实际生成结果。",
    "",
    "## 评阅方法与边界",
    "",
    "两次独立AI逐例评阅分别读取100条完整可用前缀及两候选，在互不读取对方标签的情况下冻结结果。"
    "初始主标签84/100一致，16例由主控逐条裁决，初始文件和全部裁决理由均保留。"
    "**这不是独立人工标注，也不是完整推理过程或任务质量评测。**",
    "",
    "两次评阅在最初字段探查中均意外看到S001原文下一token辅助字段；该例仍归不确定，未用作正确答案。"
    "其余99例评阅视图均排除了该辅助字段。参考Top-1也未被当作正确答案。",
    "",
    "比例仅描述这100个低Margin翻转样本，不能直接外推成模型整体错误率。"
    "此集合是固定自然文本前缀，包含问题描述等文本，但没有两条候选各自继续生成的完整轨迹；"
    "因此既不能认定措辞变化绝对无损，也不能认定内容候选不同就是回答出错。",
    "",
    "## 完整证据",
    "",
    f"- [可搜索的100例上下文与标注]({OUT / 'review.html'})",
    f"- [100例标注CSV]({OUT / 'annotated_samples.csv'})",
    f"- [100例机器可读JSONL]({OUT / 'annotations.jsonl'})",
    f"- [统计与来源身份]({OUT / 'summary.json'})",
    f"- [16例分歧裁决]({OUT / 'adjudication.json'})",
    f"- [冻结抽样名单]({BASE / 'sample_manifest.json'})",
    f"- [原始评阅包]({BASE / 'review_packet.md'})",
]
(OUT / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

esc = html.escape
parts = ["""<!doctype html><html lang="zh"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>低 Margin 翻转：100例上下文审阅</title>
<style>
body{max-width:1120px;margin:32px auto;padding:0 22px;font:16px/1.65 system-ui,sans-serif;color:#203047;background:#f7f9fc}
h1{font-size:28px} .lead,details,.stats{background:white;padding:18px;border-radius:10px;margin:14px 0}
table{width:100%;border-collapse:collapse}td,th{text-align:left;border-bottom:1px solid #dde4ec;padding:8px}
select,input{font:inherit;padding:9px;margin:6px 6px 6px 0}input{min-width:240px}
summary{cursor:pointer;font-weight:600}.badge{font-size:13px;border-radius:6px;background:#e6edf5;padding:3px 7px;margin-right:8px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f5f8;padding:12px;border-radius:6px;font:14px/1.7 ui-monospace,monospace}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}.muted{color:#5d6d81;font-size:14px}.note{border-left:4px solid #d18b35;padding-left:12px}
@media(max-width:700px){.pair{grid-template-columns:1fr}body{padding:0 12px}}
</style><h1>低 Margin 翻转：100例上下文审阅</h1>
<div class="lead">从876个参考 Margin &lt; 0.05 的翻转位置随机抽取100例；固定种子20261020，93篇文档。
<p class="note"><b>两次独立AI逐例评阅并复核分歧，尚未经独立人工标注。</b>
格式/措辞类不保证语义无损；内容/逻辑类不等于任务错误；46例不确定不计入无害项。</p></div>
<div class="stats"><table><tr><th>类别</th><th>数量</th><th>解释</th></tr>"""]
for label in LABELS:
    parts.append(f"<tr><td>{LABELS[label]}</td><td>{counts[label]}</td><td>{LABEL_NOTES[label]}</td></tr>")
parts.append("""</table></div><div><label>筛选 <select id="filter"><option value="">全部100例</option>""")
for label in LABELS:
    parts.append(f'<option value="{label}">{LABELS[label]} ({counts[label]})</option>')
parts.append("""</select></label><input id="search" placeholder="搜索样本、词语、依据或文档"><span id="visible"></span></div>
<p class="muted">箭头为参考 → 舍入。单token用引号显示空格；“接在前缀后”仅展示实际已知前缀加一个候选，不是续写。
点击每行展开完整可用前缀、依据和两次初始标签。</p>""")
for r in rows:
    sid = r["sample_id"]
    pair = f"{r['reference_token_repr']} → {r['current_token_repr']}"
    search_text = " ".join([sid, r["doc_id"], r["prefix"], pair, r["rationale_zh"], " ".join(r["risk_flags"])])
    parts.append(f'<details class="sample" data-label="{r["final_label"]}" data-search="{esc(search_text.lower(), quote=True)}">')
    parts.append(f'<summary><span class="badge">{esc(r["category_zh"])}</span>{sid}　{esc(pair)}　<span class="muted">Margin {r["reference_margin"]:.7f}</span></summary>')
    parts.append(f'<p>{esc(r["rationale_zh"])}</p><p class="muted">{esc(r["doc_id"])} · 位置 {r["position"]}（从0计） · {esc(r["domain"])} · TV {100*r["softmax_tv"]:.4f}%</p>')
    parts.append(f'<b>完整可用输入前缀</b><pre>{esc(r["prefix"])}</pre>')
    parts.append(f'<div class="pair"><section><b>参考 token {esc(r["reference_token_repr"])}</b><pre>{esc(r["reference_joint_tail"])}</pre></section><section><b>舍入 token {esc(r["current_token_repr"])}</b><pre>{esc(r["current_joint_tail"])}</pre></section></div>')
    parts.append(f'<p class="muted">初始标签：主控 {LABELS[r["root_initial_label"]]}；独立AI {LABELS[r["independent_initial_label"]]}。{"已逐条裁决" if r["adjudicated"] else "初始一致"}。风险旗标：{esc(", ".join(r["risk_flags"]))}</p></details>')
parts.append("""<p class="muted">没有将参考token或原文下一token当作正确答案。没有自由生成的后续轨迹，因此不据此判定最终回答准确率。
初始标签一致84/100。两次评阅在字段探查中均意外看到S001原文辅助下一token，未作为正确性依据；其余99例评阅视图均排除该字段。</p>
<script>
const cards=[...document.querySelectorAll('.sample')],f=document.getElementById('filter'),q=document.getElementById('search');
function update(){let n=0;for(const c of cards){const show=(!f.value||c.dataset.label===f.value)&&c.dataset.search.includes(q.value.toLowerCase());c.hidden=!show;if(show)n++}document.getElementById('visible').textContent='显示 '+n+' / 100'}
f.addEventListener('change',update);q.addEventListener('input',update);update();
</script></html>""")
(OUT / "review.html").write_text("\n".join(parts), encoding="utf-8")
save_json("artifact_manifest.json", {
    "artifacts": [identity(OUT / name) for name in ["annotations.jsonl", "annotated_samples.csv", "summary.json", "report.md", "review.html", "adjudication.json", "build_report.py"]],
    "preserved_inputs": [identity(q) for q in sources],
})
print(json.dumps({"counts": dict(counts), "initial_agreement": 84, "written": ["report.md", "review.html", "annotated_samples.csv", "annotations.jsonl", "summary.json"]}, ensure_ascii=False))
