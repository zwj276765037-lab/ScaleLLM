# ScaleLLM 软件精度实验结果总览

整理/更新日期：2026-10-18（Asia/Shanghai）。本文及配套图表整理已有历史结果，没有运行模型推理或修改原始结果。

主要取数入口是 **`six_model_algorithm_literature_2048` 的校正协议全量结果**，已覆盖六个模型、五种配置、六项 ACC 与一项 WikiText-2 PPL。其他目录包含不同协议、早期版本、冒烟或诊断结果，分别列示用途与状态。

## 当前展示表：用 GSM8K 替换 ARC-c

论文样式完整表：[PNG 预览](accuracy_table.png) · [矢量 PDF](accuracy_table.pdf) · [Markdown 表格](accuracy_table.md)。按模型分组，每组五行配置，浅蓝色突出 ScaleCode，不含 PPL。

当前选用任务为 **PIQA、ARC-Easy、GSM8K、BoolQ、HellaSwag、WinoGrande**。用户已要求从展示表移除 ARC-Challenge。五项已有校正数据保持；GSM8K 暂无该统一校正范围的结果，因此 GSM8K 和新六任务 Avg. 均标为 `--`（待测）。旧协议 GSM8K first-300 与含 ARC-c 的旧均值不填入当前表；后续补测需固定 GSM8K 的生成协议，再重算六任务平均。

## 待补充：GSM8K 精度验证

**需要补充六个模型、五种配置的 GSM8K 实测结果，共 30 组。当前可纳入新表的 GSM8K 结果为 0/30；状态为计划已制定、待实施，未启动推理。** 旧协议 first-300 已有历史结果，新增统一评估所需的全量结果仍待补充。

详细入口：[GSM8K 补测实施计划](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/source/gsm8k_completion_plan_20261018/plan.md)。已核实 test 1,319 条、train 7,473 条，并保存数据身份、30组矩阵和逐题 few-shot 清单。推荐 lm_eval 0.4.11 标准 GSM8K 5-shot 提示、greedy 生成和 strict exact-match；正式协议在入口核验与 train pilot 后封存。当前 GPU 查询存在 NVML 驱动/库版本不匹配，须在运行前排除。新程序和原始补测证据使用当前工作区 `project/software`；本目录继续作为用户总表展示入口。

| 模型 | BF16 | A8W8 / FP32 scale | A8W4 / FP32 scale | A8W4 / FP16 scale | A8W4 / ScaleCode |
| --- | --- | --- | --- | --- | --- |
| DeepSeek-R1-Distill-Llama-8B | 待补测 | 待补测 | 待补测 | 待补测 | 待补测 |
| GLM-4-9B-0414 | 待补测 | 待补测 | 待补测 | 待补测 | 待补测 |
| Llama-3.1-8B-Instruct | 待补测 | 待补测 | 待补测 | 待补测 | 待补测 |
| Llama-3.2-3B-Instruct | 待补测 | 待补测 | 待补测 | 待补测 | 待补测 |
| Qwen2.5-7B-Instruct | 待补测 | 待补测 | 待补测 | 待补测 | 待补测 |
| Qwen3-8B | 待补测 | 待补测 | 待补测 | 待补测 | 待补测 |

补充范围与处理步骤：

1. 采用 GSM8K main 的完整 test split，目标 1,319 条；核对本地数据身份、行数及 SHA-256。按详细计划固定 prompt、5-shot 示例、原始文本模式、greedy 解码、生成长度、strict/flexible 答案提取和 exact-match，并对五种配置采用相同规则。新表须注明 GSM8K 为 5-shot 生成，其余五项沿用 0-shot likelihood；不将新组合标作统一 0-shot。
2. 使用与主表一致的六个 checkpoint 和五种量化配置，补充 GSM8K 生成与评分入口；先做明确标记的小样本检查，再完成 30 组全量实测。
3. 新结果按批次、模型、配置和独立 AT 保存逐题输出、标准答案、提取答案、正确性、汇总指标、运行日志及 manifest，记录模型、代码、数据、环境与协议身份。使用当前工作区 `project/software/0_Software/fix_experiment/results/gsm8k_full_completion/` 下独立目录，布局见详细计划，不覆盖历史运行。
4. 每组校验样本完整性、评分规则及主表输入身份后，填入 GSM8K 列；按 `Avg. = (PIQA + ARC-Easy + GSM8K + BoolQ + HellaSwag + WinoGrande) / 6` 重算该组平均值。结果缺失的组继续标待补测；旧 first-300 分数和含 ARC-c 的旧均值不用于填补。

补充完成后更新：当前 [Markdown 表格](accuracy_table.md)、[PNG 表格](accuracy_table.png)、[PDF 表格](accuracy_table.pdf) 及本节覆盖状态。新六任务展示表单独引用 GSM8K 新批次，历史 `six_model_summary.csv` 与原始 manifest 保持原样。

以下保留原六任务历史汇总，便于核对来源，其 Avg. 包含 ARC-c，与当前展示组合分别记录。

## 历史六任务平均 ACC（%，包含 ARC-c）

平均 ACC =（PIQA + ARC-Easy + ARC-Challenge + BoolQ + HellaSwag + WinoGrande）/ 6，即下文的 Macro ACC。每组使用六项未舍入分数等权平均，再转为百分数并保留两位小数。本表先只展示 ACC。

| 模型 | BF16 | A8W8 / FP32 scale | A8W4 / FP32 scale | A8W4 / FP16 scale | A8W4 / ScaleCode |
| --- | ---: | ---: | ---: | ---: | ---: |
| DeepSeek-R1-Distill-Llama-8B | 49.50 | 49.46 | 48.03 | 47.83 | 47.96 |
| GLM-4-9B-0414 | 77.03 | 77.13 | 76.50 | 76.65 | 76.74 |
| Llama-3.1-8B-Instruct | 75.89 | 75.85 | 74.95 | 74.77 | 74.95 |
| Llama-3.2-3B-Instruct | 68.84 | 68.79 | 66.99 | 67.57 | 67.03 |
| Qwen2.5-7B-Instruct | 73.73 | 69.95 | 72.52 | 69.34 | 72.75 |
| Qwen3-8B | 74.05 | 74.02 | 73.15 | 72.98 | 73.26 |

来源：[six_model_summary.csv](six_model_algorithm_literature_2048/six_model_summary.csv) 的 `macro_accuracy`，已复核与六项任务的均值一致。

## 1. 主结果与证据入口

| 项目 | 记录 |
| --- | --- |
| 协议 | `literature_2048`；全量 official evaluation split；0-shot；context = 2048 |
| 结果覆盖 | 6 模型 × 5 配置 = 30 组；180 项 ACC + 30 项 PPL |
| 历史总 manifest 时间 | 2026-09-15 12:54:22 CST |
| 历史执行状态 | `status=complete`；`missing=[]`；`validation_errors=[]` |
| 数值总表 | [six_model_summary.csv](six_model_algorithm_literature_2048/six_model_summary.csv) |
| 五配置相对 BF16 差值 | [five_config_delta.csv](six_model_algorithm_literature_2048/five_config_delta.csv) |
| 总 manifest 与原始来源 | [experiment_manifest.json](six_model_algorithm_literature_2048/experiment_manifest.json) |
| 运行记录 | [runner_state.json](six_model_algorithm_literature_2048/runner_state.json) |
| 数据来源与身份 | [data_manifest.json](six_model_algorithm_literature_2048/data_manifest.json) |
| 协议规范 | [ACC/PPL 评测对齐规范](../source/ScaleLLM_ACC_PPL_evaluation_alignment_standard.md) |

本次整理读取了全部 30 份 merged manifest，核对六项 ACC 的任务覆盖、样本数、主指标、有限数值及其与 CSV 的一致性；核对宏平均与 PPL 的全流、2048 非重叠块和尾块丢弃标记，并复核 24 行相对 BF16 的差值公式。未重新计算逐题 likelihood、PPL NLL，也未重新哈希模型权重或重跑 GPU。历史完成记录与当前数值复现是两项不同的验证。

## 2. 校正后的评测口径

| 任务 | Evaluation split | 每组样本数 | 主指标 |
| --- | --- | --- | --- |
| PIQA | validation | 1,838 | `acc_norm` |
| ARC-Easy | test | 2,376 | `acc_norm` |
| ARC-Challenge | test | 1,172 | `acc_norm` |
| BoolQ | validation | 3,270 | `acc` |
| HellaSwag | validation | 10,042 | `acc_norm` |
| WinoGrande | validation/dev | 1,267 | `acc` |

- ACC 使用冻结的 lm-evaluation-harness 0.4.11 请求与指标口径，0-shot continuation likelihood，不使用 chat template 或 system prompt；已披露的 tokenizer 边界兼容规则为 `fixed_context_independent_continuation_fallback_v1`，各配置采用同一规则。
- ARC-Challenge 使用 test 1,172 条。旧表的 validation 299 条结果属于另一口径。
- Macro ACC 是上述六项未舍入分数的等权平均；先平均再转换为百分数。主表 ACC 单位为 **%**，保留两位小数；PPL 保留四位小数。精确值和各任务 stderr 见 CSV 与 merged manifest。
- PPL 使用 WikiText-2 raw-v1 完整 test 文本、各模型原生 tokenizer、2,048-token 非重叠完整块，丢弃不足一块的尾部；累计 NLL 与评分 token 后计算 PPL。
- 表中 FP32/FP16 指 scale 的表示精度；本批模型计算 dtype 为 BF16。`reference_qdq` 使用原生软件 Attention/RoPE/KV，验证算法级 QDQ。

| 配置标识 | 表内名称 | Attention 权重 | MLP 权重 | Scale 表示 |
| --- | --- | --- | --- | --- |
| `bf16` | BF16 | 原始 BF16 | 原始 BF16 | 无量化 |
| `a8w8_fp32` | A8W8 / FP32 scale | W8 | W8 | FP32 |
| `a8w4_fp32` | A8W4 / FP32 scale | W8 | W4 | FP32 |
| `a8w4_fp16` | A8W4 / FP16 scale | W8 | W4 | FP16 |
| `reference_qdq` | A8W4 / ScaleCode | W8 | W4 | uint8 code + uint8 shift |

所有量化配置采用 Hadamard32、Group32、activation A8；GLM 的融合 `gate_up_proj` 按 MLP 处理，`lm_head` 不量化。

## 3. 历史六模型 × 五配置准确率与 PPL 总表（包含 ARC-c）

所有行在历史 merged manifest 中均为 `complete` 且 `full_split=true`。每行“配置”链接到该组的原始 merged manifest。

| 模型 | 配置 | PIQA | ARC-e | ARC-c | BoolQ | HellaSwag | WinoGrande | Macro ACC | WT2 PPL |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DeepSeek-R1-Distill-Llama-8B | [BF16](six_model_algorithm_literature_2048/DeepSeek-R1-Distill-Llama-8B/bf16_literature_2048/merged/manifest.json) | 60.01 | 40.57 | 28.41 | 62.17 | 52.95 | 52.88 | 49.50 | 26.3376 |
| DeepSeek-R1-Distill-Llama-8B | [A8W8 / FP32 scale](six_model_algorithm_literature_2048/DeepSeek-R1-Distill-Llama-8B/a8w8_fp32_literature_2048/merged/manifest.json) | 60.12 | 40.61 | 28.41 | 62.14 | 52.88 | 52.57 | 49.46 | 26.1272 |
| DeepSeek-R1-Distill-Llama-8B | [A8W4 / FP32 scale](six_model_algorithm_literature_2048/DeepSeek-R1-Distill-Llama-8B/a8w4_fp32_literature_2048/merged/manifest.json) | 58.54 | 38.43 | 27.56 | 62.17 | 49.80 | 51.70 | 48.03 | 29.8958 |
| DeepSeek-R1-Distill-Llama-8B | [A8W4 / FP16 scale](six_model_algorithm_literature_2048/DeepSeek-R1-Distill-Llama-8B/a8w4_fp16_literature_2048/merged/manifest.json) | 57.94 | 38.13 | 27.22 | 62.17 | 49.72 | 51.78 | 47.83 | 31.1503 |
| DeepSeek-R1-Distill-Llama-8B | [A8W4 / ScaleCode](six_model_algorithm_literature_2048/DeepSeek-R1-Distill-Llama-8B/reference_qdq_literature_2048/merged/manifest.json) | 58.05 | 38.22 | 27.39 | 62.17 | 49.83 | 52.09 | 47.96 | 29.8801 |
| GLM-4-9B-0414 | [BF16](six_model_algorithm_literature_2048/GLM-4-9B-0414/bf16_literature_2048/merged/manifest.json) | 80.47 | 81.10 | 60.32 | 86.82 | 80.23 | 73.24 | 77.03 | 11.3954 |
| GLM-4-9B-0414 | [A8W8 / FP32 scale](six_model_algorithm_literature_2048/GLM-4-9B-0414/a8w8_fp32_literature_2048/merged/manifest.json) | 80.41 | 81.23 | 60.67 | 86.70 | 80.16 | 73.64 | 77.13 | 11.3976 |
| GLM-4-9B-0414 | [A8W4 / FP32 scale](six_model_algorithm_literature_2048/GLM-4-9B-0414/a8w4_fp32_literature_2048/merged/manifest.json) | 80.09 | 80.64 | 59.98 | 86.51 | 79.51 | 72.30 | 76.50 | 11.5938 |
| GLM-4-9B-0414 | [A8W4 / FP16 scale](six_model_algorithm_literature_2048/GLM-4-9B-0414/a8w4_fp16_literature_2048/merged/manifest.json) | 80.47 | 81.10 | 59.30 | 86.67 | 79.62 | 72.77 | 76.65 | 11.5810 |
| GLM-4-9B-0414 | [A8W4 / ScaleCode](six_model_algorithm_literature_2048/GLM-4-9B-0414/reference_qdq_literature_2048/merged/manifest.json) | 80.41 | 80.60 | 59.90 | 86.94 | 79.73 | 72.85 | 76.74 | 11.5989 |
| Llama-3.1-8B-Instruct | [BF16](six_model_algorithm_literature_2048/Llama-3.1-8B-Instruct/bf16_literature_2048/merged/manifest.json) | 81.45 | 79.80 | 55.46 | 85.14 | 79.55 | 73.95 | 75.89 | 7.1616 |
| Llama-3.1-8B-Instruct | [A8W8 / FP32 scale](six_model_algorithm_literature_2048/Llama-3.1-8B-Instruct/a8w8_fp32_literature_2048/merged/manifest.json) | 81.12 | 79.92 | 55.38 | 85.08 | 79.58 | 74.03 | 75.85 | 7.1631 |
| Llama-3.1-8B-Instruct | [A8W4 / FP32 scale](six_model_algorithm_literature_2048/Llama-3.1-8B-Instruct/a8w4_fp32_literature_2048/merged/manifest.json) | 80.41 | 78.45 | 54.35 | 83.55 | 78.66 | 74.27 | 74.95 | 7.5750 |
| Llama-3.1-8B-Instruct | [A8W4 / FP16 scale](six_model_algorithm_literature_2048/Llama-3.1-8B-Instruct/a8w4_fp16_literature_2048/merged/manifest.json) | 79.87 | 78.83 | 53.67 | 83.82 | 78.62 | 73.80 | 74.77 | 8.2379 |
| Llama-3.1-8B-Instruct | [A8W4 / ScaleCode](six_model_algorithm_literature_2048/Llama-3.1-8B-Instruct/reference_qdq_literature_2048/merged/manifest.json) | 80.20 | 78.66 | 54.69 | 83.70 | 78.60 | 73.88 | 74.95 | 7.5733 |
| Llama-3.2-3B-Instruct | [BF16](six_model_algorithm_literature_2048/Llama-3.2-3B-Instruct/bf16_literature_2048/merged/manifest.json) | 77.04 | 71.17 | 46.33 | 78.53 | 71.61 | 68.35 | 68.84 | 10.9430 |
| Llama-3.2-3B-Instruct | [A8W8 / FP32 scale](six_model_algorithm_literature_2048/Llama-3.2-3B-Instruct/a8w8_fp32_literature_2048/merged/manifest.json) | 76.55 | 70.92 | 46.16 | 78.29 | 71.61 | 69.22 | 68.79 | 10.9039 |
| Llama-3.2-3B-Instruct | [A8W4 / FP32 scale](six_model_algorithm_literature_2048/Llama-3.2-3B-Instruct/a8w4_fp32_literature_2048/merged/manifest.json) | 74.86 | 67.26 | 43.94 | 79.02 | 67.74 | 69.14 | 66.99 | 12.4244 |
| Llama-3.2-3B-Instruct | [A8W4 / FP16 scale](six_model_algorithm_literature_2048/Llama-3.2-3B-Instruct/a8w4_fp16_literature_2048/merged/manifest.json) | 75.84 | 67.21 | 44.03 | 78.99 | 70.46 | 68.90 | 67.57 | 11.4108 |
| Llama-3.2-3B-Instruct | [A8W4 / ScaleCode](six_model_algorithm_literature_2048/Llama-3.2-3B-Instruct/reference_qdq_literature_2048/merged/manifest.json) | 74.92 | 66.88 | 44.45 | 79.14 | 67.58 | 69.22 | 67.03 | 12.5095 |
| Qwen2.5-7B-Instruct | [BF16](six_model_algorithm_literature_2048/Qwen2.5-7B-Instruct/bf16_literature_2048/merged/manifest.json) | 79.65 | 76.14 | 51.62 | 85.44 | 79.55 | 70.01 | 73.73 | 8.2488 |
| Qwen2.5-7B-Instruct | [A8W8 / FP32 scale](six_model_algorithm_literature_2048/Qwen2.5-7B-Instruct/a8w8_fp32_literature_2048/merged/manifest.json) | 75.95 | 71.42 | 49.06 | 83.67 | 74.64 | 64.96 | 69.95 | 8.3824 |
| Qwen2.5-7B-Instruct | [A8W4 / FP32 scale](six_model_algorithm_literature_2048/Qwen2.5-7B-Instruct/a8w4_fp32_literature_2048/merged/manifest.json) | 78.94 | 73.53 | 51.62 | 83.61 | 78.62 | 68.82 | 72.52 | 8.7998 |
| Qwen2.5-7B-Instruct | [A8W4 / FP16 scale](six_model_algorithm_literature_2048/Qwen2.5-7B-Instruct/a8w4_fp16_literature_2048/merged/manifest.json) | 75.68 | 69.87 | 49.74 | 82.54 | 74.12 | 64.09 | 69.34 | 8.7689 |
| Qwen2.5-7B-Instruct | [A8W4 / ScaleCode](six_model_algorithm_literature_2048/Qwen2.5-7B-Instruct/reference_qdq_literature_2048/merged/manifest.json) | 78.56 | 74.66 | 51.37 | 84.10 | 78.73 | 69.06 | 72.75 | 8.6672 |
| Qwen3-8B | [BF16](six_model_algorithm_literature_2048/Qwen3-8B/bf16_literature_2048/merged/manifest.json) | 77.48 | 80.85 | 56.48 | 86.67 | 74.95 | 67.88 | 74.05 | 9.7355 |
| Qwen3-8B | [A8W8 / FP32 scale](six_model_algorithm_literature_2048/Qwen3-8B/a8w8_fp32_literature_2048/merged/manifest.json) | 77.53 | 81.06 | 56.40 | 86.64 | 74.84 | 67.64 | 74.02 | 9.7479 |
| Qwen3-8B | [A8W4 / FP32 scale](six_model_algorithm_literature_2048/Qwen3-8B/a8w4_fp32_literature_2048/merged/manifest.json) | 76.55 | 79.97 | 55.46 | 86.33 | 73.36 | 67.25 | 73.15 | 10.0739 |
| Qwen3-8B | [A8W4 / FP16 scale](six_model_algorithm_literature_2048/Qwen3-8B/a8w4_fp16_literature_2048/merged/manifest.json) | 76.82 | 79.50 | 55.03 | 86.36 | 73.45 | 66.69 | 72.98 | 10.0550 |
| Qwen3-8B | [A8W4 / ScaleCode](six_model_algorithm_literature_2048/Qwen3-8B/reference_qdq_literature_2048/merged/manifest.json) | 76.82 | 79.84 | 55.80 | 86.30 | 73.45 | 67.32 | 73.26 | 10.0678 |

## 4. ScaleCode 相对同模型 BF16 的变化

ACC 差值单位为百分点（pp）；PPL 变化为相对百分比。差值均从未舍入值计算。四种量化配置的完整差值见 [five_config_delta.csv](six_model_algorithm_literature_2048/five_config_delta.csv)。

| 模型 | BF16 ACC (%) | ScaleCode ACC (%) | ACC Δ (pp) | BF16 PPL | ScaleCode PPL | PPL 相对变化 |
| --- | --- | --- | --- | --- | --- | --- |
| DeepSeek-R1-Distill-Llama-8B | 49.50 | 47.96 | -1.5409 | 26.3376 | 29.8801 | +13.45% |
| GLM-4-9B-0414 | 77.03 | 76.74 | -0.2944 | 11.3954 | 11.5989 | +1.79% |
| Llama-3.1-8B-Instruct | 75.89 | 74.95 | -0.9363 | 7.1616 | 7.5733 | +5.75% |
| Llama-3.2-3B-Instruct | 68.84 | 67.03 | -1.8075 | 10.9430 | 12.5095 | +14.31% |
| Qwen2.5-7B-Instruct | 73.73 | 72.75 | -0.9877 | 8.2488 | 8.6672 | +5.07% |
| Qwen3-8B | 74.05 | 73.26 | -0.7931 | 9.7355 | 10.0678 | +3.41% |

以上结果支持本批协议下的软件算法精度比较。各模型的 ACC 与 PPL 均有退化，不能概括为无损；本表不用于认定硬件 bit-exact、RTL 功能、时序或板级验收通过。

## 5. PPL 各模型评分规模

同一模型的五种配置使用同一 tokenizer stream 与分块规模；以下数字取该模型 BF16 行，已核对五配置一致。

| 模型 | 原始 token 数 | 完整块数 | 评分 token 数 | 丢弃尾部 token 数 |
| --- | --- | --- | --- | --- |
| DeepSeek-R1-Distill-Llama-8B | 316,944 | 154 | 315,238 | 1,552 |
| GLM-4-9B-0414 | 289,583 | 141 | 288,627 | 815 |
| Llama-3.1-8B-Instruct | 288,936 | 141 | 288,627 | 168 |
| Llama-3.2-3B-Instruct | 288,936 | 141 | 288,627 | 168 |
| Qwen2.5-7B-Instruct | 298,938 | 145 | 296,815 | 1,978 |
| Qwen3-8B | 298,938 | 145 | 296,815 | 1,978 |

## 6. 本目录其他实验入口

下表用于定位历史证据。状态来自相应文件；未对这些批次重新做全部实验验收。

| 目录 / 入口 | 内容与已见状态 | 使用范围 |
| --- | --- | --- |
| [six_model_algorithm_literature_2048/](six_model_algorithm_literature_2048/) | 六模型五配置校正协议全量结果；30 组 complete | 本文主表来源 |
| [algorithm_reference_full/paper_summary.csv](algorithm_reference_full/paper_summary.csv) | 早期单模型 BF16 与 reference_qdq，literature_2048；两行 complete | 早期独立批次，保留原协议与身份 |
| [algorithm_reference_smoke/paper_summary.csv](algorithm_reference_smoke/paper_summary.csv) | reference_qdq 为部分样本；同时引用完整 BF16 基线 | 冒烟与基线引用，不替代六模型主表 |
| [algorithm_precision_full/paper_summary.csv](algorithm_precision_full/paper_summary.csv) | hardware_128；BF16 complete，v5_algorithm incomplete / strict_failure_before_metrics | 128 上下文及严格失败证据 |
| [algorithm_precision_smoke/paper_summary.csv](algorithm_precision_smoke/paper_summary.csv) | hardware_128；BF16 与 v5_algorithm 为部分样本 | 冒烟结果 |
| [algorithm_precision_smoke_batch32/paper_summary.csv](algorithm_precision_smoke_batch32/paper_summary.csv) | hardware_128；v5_algorithm 部分样本 | batch32 冒烟结果 |
| [paper_full_strict/paper_summary.csv](paper_full_strict/paper_summary.csv) | 两种上下文 BF16 complete；v5 hardware_128 failed / strict_failure_before_metrics | 分协议基线与失败证据 |
| [smoke_literature_limit1/paper_summary.csv](smoke_literature_limit1/paper_summary.csv) | literature_2048；full_split=false | 小样本冒烟 |
| [smoke_v5_strict_limit1/manifest.json](smoke_v5_strict_limit1/manifest.json) | v5 hardware_128；complete 但 full_split=false | 小样本冒烟 |
| [extended_ppl_smoke/](extended_ppl_smoke/) | Llama-3.2-3B-Instruct 扩展 PPL 冒烟目录 | 未作为全量跨模型结果核验 |
| [extended_ppl_batch4_smoke/](extended_ppl_batch4_smoke/) | GLM 扩展 PPL batch4 冒烟目录 | 未作为全量跨模型结果核验 |
| [extended_ppl_batch8_smoke/](extended_ppl_batch8_smoke/) | GLM 扩展 PPL batch8 冒烟目录 | 未作为全量跨模型结果核验 |
| [five_config_legacy_64block_completion/](five_config_legacy_64block_completion/) | 旧 64-block PPL 补齐目录 | 与完整 test stream 的 2048 PPL 分开 |
| [llama31_rope_softmax_fixedpoint_hardware128_v3/validation_completion_audit.json](llama31_rope_softmax_fixedpoint_hardware128_v3/validation_completion_audit.json) | 历史 format-v3 定点验证；该完成审核为 incomplete_evidence，50/53 | 版本专属诊断，不能代表当前 format05 总验收 |
| [s32_candidate_validation/final_validation_summary.json](s32_candidate_validation/final_validation_summary.json) | historical hardware_128 S32/format05 候选汇总；software_status=approved | 分项原始 manifest 必须区分 format04/05；摘要不代替当前硬件验收 |

`s32_candidate_validation` 摘要中的硬件 hold、迁移审计和数值批准均为当时记录。目录中 Down-S32 PPL 的部分原始 manifest 对应中间 format04，不能仅按目录名或最终摘要将其全部重标为完整 format05 PPL。

## 7. 与旧截图表的关系及待补范围

| 范围 | 当前校正主矩阵覆盖 | 后续处理 |
| --- | --- | --- |
| 截图中的五种配置 | 全部覆盖：BF16、A8W8 FP32、A8W4 FP32、A8W4 FP16、ScaleCode | 可据本表形成校正六任务表 |
| PIQA / ARC-c / HellaSwag / WinoGrande | 已覆盖；协议按本文第 2 节 | 使用校正结果，保留对应数据划分与指标 |
| ARC-Easy / BoolQ | 已覆盖；属于当前六任务 Macro ACC | 保留在此协议的宏平均定义中 |
| OBQA / GSM8K | 不在本批六任务矩阵中 | 需分别定义数据、prompt、metric 和生成规则后补测 |
| Llama-3.1-8B 基础版 | 不在本批六模型矩阵中；本表使用 Instruct | 如仍要求基础版，作为独立 checkpoint 补测 |
| 旧 ../../results/_summary/ 截图表 | 属于旧协议历史归档 | 保持历史身份；另行发布新协议展示表 |

旧表数据缺少展示行与新协议尚未覆盖某任务是两类不同问题。旧 validation / first-N / 自定义请求或指标下的数值，不能直接填入新协议结果表；若新增 OBQA、GSM8K 或替换基础版 checkpoint，应单独记录协议版本、任务范围、模型身份及运行批次，再定义相应展示表的平均项数。

## 8. 本文取数文件身份

以下 SHA-256 为整理时对源文件实际读取所得，便于核对本文对应的结果版本。

| 源文件 | SHA-256 |
| --- | --- |
| [six_model_summary.csv](six_model_algorithm_literature_2048/six_model_summary.csv) | `b2f93da7a0b0cde8e2456dabef9cd460f6128318566cd2fe39437801beb134b9` |
| [five_config_delta.csv](six_model_algorithm_literature_2048/five_config_delta.csv) | `ecc2f2b8866d3b6d69d589523f76cc9b2523c8b711b0280e15bbbe0f477c3143` |
| [experiment_manifest.json](six_model_algorithm_literature_2048/experiment_manifest.json) | `d8c3739d7df6027b5c8a563284e7848f43f4b72cd6e6c09b8bce869e1722a96e` |

本文保持原始实测数值，不应用展示上限或按预期精度顺序改写分数；所有原始 CSV、JSON、日志及历史运行目录均保持。
