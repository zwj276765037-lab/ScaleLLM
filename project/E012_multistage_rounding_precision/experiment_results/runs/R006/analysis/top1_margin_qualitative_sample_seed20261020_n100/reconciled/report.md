# 低 Margin Top-1 翻转：100例局部定性审阅

从参考 Margin < 0.05 的876个翻转位置中，按固定种子20261020无放回等概率抽取100例。样本来自93篇文档：网页54例、影评33例、新闻13例。样本名单先冻结，再解码和分类，没有替换难判样本。

**结论：不能把低 Margin 翻转统一解释为等价或纯格式替换。**样本中既有局部措辞变化，也有人名、年龄、数量、时间和逻辑连接差异；46例因后续未知无法可靠分类。这些差异本身不判定哪一候选正确，也不等于任务准确率下降。

## 分类统计

| 类别 | 数量 / 100 | 解读 |
|---|---:|---|
| 局部格式变化 | 1 | 仅当前上下文未见内容差异，不证明后续生成不变。 |
| 局部措辞或语法变化 | 28 | 未见明确命题反转，不代表严格同义或语义无损。 |
| 内容、事实或指代差异 | 24 | 涉及不同内容维度或事实候选，不等于已判定当前版本错误。 |
| 逻辑连接变化 | 1 | 可见逻辑连接作用发生变化，尚未确认同一完整命题真值相反。 |
| 上下文或续文不足，无法判断 | 46 | 不能归入无害项；保留片段、否定、数值等风险旗标。 |

## 代表性样本

箭头方向始终为参考版本 → 舍入版本。下表仅截取实际输入前缀的末尾；完整可用前缀在逐例明细中。

| 样本 | 前缀末尾 | 参考 token → 舍入 token | Margin | 分类与依据 |
|---|---|---|---:|---|
| S009 | …Refugees #39; hopes for return will outlive Arafat BEIRUT, Lebanon | `' -' → ' --'` | 0.0231037 | 局部格式变化：BEIRUT, Lebanon后的单横线与双横线均表现为新闻电头分隔符，局部可见内容不变。 |
| S050 | …ows a high alcohol content drink in his face, and he catches fire. In the hospital, his face is | `' badly' → ' severely'` | 0.0038643 | 局部措辞或语法变化：受伤面部描述中badly与severely是相近程度副词，未见明确事实或极性反转。 |
| S020 | … 18 rebounds in the game. Justin Jackson led the Mavericks with 19 points (9-16 FG) to go with  | `'4' → '5'` | 0.0007191 | 内容、事实或指代差异：球员统计中to go with后的4与5改变待陈述的数量，属于事实数值差异。 |
| S024 | …ack dress. “Very excited to not have to hide this anymore,” she wrote. ↵ Teigen, 31, and Legend,  | `'38' → '39'` | 0.0219498 | 内容、事实或指代差异：人物报道中Legend后的38与39改变年龄数值，不能视为格式替换。 |
| S028 | …ter." ↵ "EDF Energy is happy to work with L3 MAPPS to add two more simulators to our fleet," said | `' David' → ' Mark'` | 0.0050154 | 内容、事实或指代差异：引语said之后David与Mark为不同人名，可能改变发言者身份。 |
| S092 | …19-year-old Chilling Adventures of Sabrina megastar sparked rumours of a courting previous this | `' yr' → ' week'` | 0.0022087 | 内容、事实或指代差异：恋情报道中的this yr与this week改变传闻发生的时间范围，涉及事实时间。 |
| S094 | …940s Hollywood, nothing in this door slamming horror - made on three sets - makes much sense... | `'except' → 'and'` | 0.0173445 | 逻辑连接变化：nothing makes much sense后的except引入例外，and引入并列或补充，显式改变逻辑衔接；未形成可判定真值相反的完整后续。 |
| S096 | …picks Anthony Beauvillier Jersey Womens , Vegas Golden Knights general manager George McPhee is | `' looking' → ' not'` | 0.0101728 | 上下文或续文不足，无法判断：not明确引入否定相关风险，但否定后的谓语尚未出现，不能确认与looking所述同一命题反转；保留explicit_negation重点旗标。 |

S094 的 except → and 显示例外与并列补充的逻辑连接变化，但没有观察完整后续，不能声称同一命题已被反转。S096 的 looking → not 位于否定相关位置，因 not 后的谓语未知归为不确定，仍重点标记。本样本没有确认 Yes ↔ No 式同一完整命题的反转；这不等于全部876例不存在此类情况。

子词也可能只改变分词进度。例如S031的 Analyst 是 Analysts 的前缀，后续仍可补 s，不能据这一个token就确认单复数事实改变。不能把原文后续机械接到两个候选后，冒充模型实际生成结果。

## 评阅方法与边界

两次独立AI逐例评阅分别读取100条完整可用前缀及两候选，在互不读取对方标签的情况下冻结结果。初始主标签84/100一致，16例由主控逐条裁决，初始文件和全部裁决理由均保留。**这不是独立人工标注，也不是完整推理过程或任务质量评测。**

两次评阅在最初字段探查中均意外看到S001原文下一token辅助字段；该例仍归不确定，未用作正确答案。其余99例评阅视图均排除了该辅助字段。参考Top-1也未被当作正确答案。

比例仅描述这100个低Margin翻转样本，不能直接外推成模型整体错误率。此集合是固定自然文本前缀，包含问题描述等文本，但没有两条候选各自继续生成的完整轨迹；因此既不能认定措辞变化绝对无损，也不能认定内容候选不同就是回答出错。

## 完整证据

- [可搜索的100例上下文与标注](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/E012_multistage_rounding_precision/experiment_results/runs/R006/analysis/top1_margin_qualitative_sample_seed20261020_n100/reconciled/review.html)
- [100例标注CSV](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/E012_multistage_rounding_precision/experiment_results/runs/R006/analysis/top1_margin_qualitative_sample_seed20261020_n100/reconciled/annotated_samples.csv)
- [100例机器可读JSONL](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/E012_multistage_rounding_precision/experiment_results/runs/R006/analysis/top1_margin_qualitative_sample_seed20261020_n100/reconciled/annotations.jsonl)
- [统计与来源身份](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/E012_multistage_rounding_precision/experiment_results/runs/R006/analysis/top1_margin_qualitative_sample_seed20261020_n100/reconciled/summary.json)
- [16例分歧裁决](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/E012_multistage_rounding_precision/experiment_results/runs/R006/analysis/top1_margin_qualitative_sample_seed20261020_n100/reconciled/adjudication.json)
- [冻结抽样名单](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/E012_multistage_rounding_precision/experiment_results/runs/R006/analysis/top1_margin_qualitative_sample_seed20261020_n100/sample_manifest.json)
- [原始评阅包](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/E012_multistage_rounding_precision/experiment_results/runs/R006/analysis/top1_margin_qualitative_sample_seed20261020_n100/review_packet.md)
