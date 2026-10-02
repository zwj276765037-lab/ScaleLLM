# ScaleLLM 六模型 ACC/PPL 正式实验任务书

版本：2026-09-14  
状态：已完成；六模型 BF16/ScaleCode 全量结果 12/12，缺失 0，校验错误 0  
上位规范：`ScaleLLM_ACC_PPL_evaluation_alignment_standard.md`

权威结果目录：

```text
/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/fix_experiment/
  results/six_model_algorithm_literature_2048
```

## 1. 实验目标

本任务按 2026-09-13 冻结的论文对齐口径，重新评测旧表中涉及的六个模型。
旧表只用于确认待测模型集合，旧表中的 ACC、PPL 和 delta 一律不抄录、不预填，
也不作为新结果的正确性判据。

每个 checkpoint 都必须得到一组成对结果：

1. 同 checkpoint 的 BF16 matched baseline；
2. ScaleLLM 软件算法 `reference_qdq`；
3. 六个完整任务的逐项 ACC、标准误与六任务宏平均；
4. 完整 WikiText-2 test 上的 token-weighted PPL；
5. `reference_qdq - BF16` 的逐项 ACC 差值、宏平均差值和 PPL 相对变化。

本轮评测的优先级是验证 ScaleCode 软件算法质量，不是验证 FPGA 数值链路。
因此所有正式结果统一使用 `literature_2048`，不得混入 V5 或硬件约束口径。

## 2. 本轮模型清单与 checkpoint 决策

模型根目录固定为：

```text
/home/user/EDA-202/zhuowenjun/fpga_llm_project/configs/models
```

| 序号 | 论文/旧表显示名 | 本轮精确本地 checkpoint | `model_type` | 架构 | 层数 | Reference-QDQ 预期目标模块数 |
|---:|---|---|---|---|---:|---:|
| 1 | DeepSeek-R1-Distill-Llama-8B | `DeepSeek-R1-Distill-Llama-8B` | `llama` | `LlamaForCausalLM` | 32 | 224 |
| 2 | GLM-4-9B-0414 | `GLM-4-9B-0414` | `glm4` | `Glm4ForCausalLM` | 40 | 240 |
| 3 | Llama-3.1-8B | `Llama-3.1-8B-Instruct` | `llama` | `LlamaForCausalLM` | 32 | 224 |
| 4 | Llama-3.2-3B-Instruct | `Llama-3.2-3B-Instruct` | `llama` | `LlamaForCausalLM` | 28 | 196 |
| 5 | Qwen2.5-7B-Instruct | `Qwen2.5-7B-Instruct` | `qwen2` | `Qwen2ForCausalLM` | 28 | 196 |
| 6 | Qwen3-8B | `Qwen3-8B` | `qwen3` | `Qwen3ForCausalLM` | 36 | 252 |

旧表把第 3 个模型简写为 `Llama-3.1-8B`，但该组实验对应的是 Instruct
checkpoint。本轮固定使用 `Llama-3.1-8B-Instruct`，不使用同目录下另一个
`Llama-3.1-8B` base checkpoint。论文表中必须写出完整 checkpoint 名称，
避免与使用 base 模型的论文结果直接混比。

预期目标模块数只用于 smoke 阶段的完整性检查，不允许为了凑数忽略架构差异：

- Llama、DeepSeek-Llama、Qwen2.5、Qwen3 每层应替换
  `q_proj/k_proj/v_proj/o_proj/gate_proj/up_proj/down_proj` 共 7 个 Linear；
- GLM-4 每层应替换 `q_proj/k_proj/v_proj/o_proj/gate_up_proj/down_proj`
  共 6 个 Linear，其中 `gate_up_proj` 是融合 MLP 模块；
- `lm_head`、embedding、normalization 及 Qwen3 的 `q_norm/k_norm` 不量化。

任一模型实际 attach 数、每类 op 数量或权重位宽与本表不符时，正式实验必须停止，
先修复架构适配，不能把部分量化模型标成 `reference_qdq`。

## 3. 本轮方法定义

### 3.1 BF16 matched baseline

- 从同一个本地 checkpoint 加载权重，计算 dtype 为 BF16；
- 使用原模型的 tokenizer、Attention、RoPE、KV cache 语义、RMSNorm、MLP、
  residual 和 LM head；
- 不插入 Hadamard、激活量化、权重量化或 ScaleCode；
- 使用 eager attention，以避免不同 attention backend 成为未记录变量；
- `use_cache=False`，且 BF16 与 `reference_qdq` 使用相同 prompt、截断和评分代码。

### 3.2 ScaleLLM `reference_qdq`

本轮唯一算法主方法固定为：

| 项目 | 冻结配置 |
|---|---|
| Hadamard | normalized Hadamard32，block size = 32 |
| activation group | Group32 |
| activation | A8，软件 QDQ |
| Attention weights | W8：Q/K/V/O |
| MLP weights | W4：Gate/Up/Down；GLM 融合 `gate_up_proj` 也按 W4 |
| scale | 8-bit ScaleCode；activation 与 folded-weight scale 均编码为 `uint8 code + uint8 shift_bits` |
| compute dtype | BF16 |
| 非量化路径 | 原生软件 Attention、RoPE、KV、Softmax、residual、RMSNorm、激活函数和 LM head |

该 case 是验证 Hadamard32 + Group32 A8 + Attention W8 + MLP W4 + ScaleCode
的算法级软件参考实现，不是硬件 bit-exact 仿真。它明确不包含：

- S24/S27/S32/S35/S37/S44/S46 等硬件定点格式；
- KV12、定点 QK、定点 Softmax、定点 PV 或硬件 accumulator；
- V5 `hardware_128` 的 128-position 限制；
- RTL zero guard 或 `--allow-format-errors`。

### 3.3 本轮排除的消融项

旧表中的 A8W8/FP32 scale、A8W4/FP32 scale、A8W4/FP16 scale 等消融项不在
本轮任务内。本轮只跑 BF16 和 8-bit ScaleCode `reference_qdq`。如果后续需要
scale-format ablation，应建立独立任务和结果表，不能插入本轮主表后改变任务总量。

## 4. ACC 正式口径

### 4.1 固定环境与总体规则

- `lm-evaluation-harness==0.4.11`；
- zero-shot continuation likelihood，不做生成式答案解析；
- 完整 official evaluation split，`limit=None`；
- context/max length = 2048；
- 不调用 chat template，不添加 system prompt，不因 checkpoint 名称带
  `Instruct` 而改变模板；
- prompt、choice 构造和主 metric 与 lm-eval 0.4.11 冻结实现一致；
- seed 固定为 `20260913`；batch size 只允许作为吞吐参数调整并写入 manifest。

### 4.2 数据集、split、样本数和主指标

数据根目录固定为：

```text
/home/user/EDA-202/zhuowenjun/fpga_llm_project/data
```

| Task | 固定本地文件 | Split | 样本数 | 论文主指标 |
|---|---|---|---:|---|
| PIQA | `piqa/validation_full.jsonl` | validation | 1,838 | `acc_norm` |
| ARC-Easy | `lm_eval_standard/arc_easy_test.jsonl` | test | 2,376 | `acc_norm` |
| ARC-Challenge | `lm_eval_standard/arc_challenge_test.jsonl` | test | 1,172 | `acc_norm` |
| BoolQ | `bape_eval/raw/boolq/validation.parquet` | validation | 3,270 | `acc` |
| HellaSwag | `hellaswag/hellaswag_val.jsonl` | validation | 10,042 | `acc_norm` |
| WinoGrande | `winogrande/winogrande_1.1/winogrande_1.1/dev.jsonl` | validation/dev | 1,267 | `acc` |

每次正式运行前必须重新验证文件存在、固定行数和 SHA-256。缺失、行数错误或
SHA 不一致必须失败，禁止静默切换到联网下载版本、validation 替代 test、
first-N 子集或另一个本地副本。

`acc` 取总 continuation log-likelihood 最大的 choice。`acc_norm` 严格采用
lm-eval 0.4.11 的“总 log-likelihood / choice 字符长度”，不是 token 平均，
也不能把旧程序的 `score_char_norm` 改名后视为等价。

六任务综合指标是任务等权宏平均，而不是按样本数加权的 micro average：

```text
ACC_macro = (PIQA_acc_norm + ARC-Easy_acc_norm + ARC-Challenge_acc_norm
             + BoolQ_acc + HellaSwag_acc_norm + WinoGrande_acc) / 6
```

每个任务必须报告 `n_samples`、主指标和 lm-eval 返回的标准误 `stderr`。
Macro ACC 只按上述公式计算，不用六个任务的样本量再次加权。

### 4.3 非前缀稳定 tokenizer 的边界规则

DeepSeek-R1-Distill-Llama-8B 的 tokenizer 不是严格 prefix-stable。例如
`Answer:` 单独编码的末 token 与 `Answer: no` 联合编码的末 token 不同。
lm-eval 0.4.11 默认用 `len(tokenize(context))` 切分联合编码，在该模型上会令
部分 choice 得到空 continuation 并使全量评测在37%处触发断言；另一些非空
choice 也会因边界 merge 被错误切掉首 token。

本轮固定采用 `fixed_context_independent_continuation_fallback_v1`：

1. 若联合编码以完整 context 编码为前缀，逐字节执行 lm-eval 0.4.11 原路径；
2. 若 tokenizer 在边界发生 merge，保持 context token 不变，仅将 continuation
   以 `add_special_tokens=False` 独立编码；
3. 同一规则同时用于 matched BF16 与 `reference_qdq`，不得只修其中一个 case；
4. 每任务记录 fallback documents/requests，论文中披露该 tokenizer 兼容层。

对 DeepSeek 六任务全部67,106个 likelihood request 的静态审计得到37,976个
boundary fallback，修复后空 continuation 为0。该兼容层不改变 prompt 字符串、
choice 字符串、gold label、`acc/acc_norm` 或其他模型的 prefix-stable 请求。

## 5. WikiText-2 PPL 正式口径

固定文件为：

```text
/home/user/EDA-202/zhuowenjun/fpga_llm_project/data/
  wikitext-2-raw-v1/test-00000-of-00001.jsonl
```

处理和统计规则冻结如下：

1. 读取 WikiText-2 raw-v1 的完整 test split；
2. 丢弃空文本行，以两个换行符 `\n\n` 连接非空行；
3. 使用每个被测 checkpoint 自带的原生 tokenizer，
   `add_special_tokens=False`；
4. 从 token stream 起点按 2,048 token 切成不重叠完整 block；
5. 不足 2,048 token 的最后 tail 丢弃；
6. 每个 block 的第一个 token 只提供条件，不计入 NLL；
7. 先累加所有 block 的 NLL 与 scoring-token 数，再计算：

```text
PPL = exp(total_NLL / total_scoring_tokens)
```

禁止先算每个 block 的 PPL 再做算术平均。不同模型 tokenizer 得到的 token
总数、完整 block 数、scoring tokens 和 tail tokens可能不同，必须逐模型实测
并写入结果；Llama-3.1-8B-Instruct 的 288,627 个 scoring tokens不得硬套给
DeepSeek、GLM、Qwen 或其他 Llama checkpoint。

## 6. 运行规模与双 GPU 调度

正式结果规模为：

```text
6 models x 2 cases x (6 ACC tasks + 1 PPL task)
= 12 model-case phases
= 72 task-level ACC results + 12 PPL results
= 84 logical metrics workloads
```

正式调度采用两个独立的单 GPU worker 和动态最长任务优先队列。一个 worker
一次加载一个完整 model-case，并顺序执行该 case 的六项 ACC 与 PPL；两张卡
同时从 12 个 model-case 中领取不同任务：

```text
GPU0: one complete model-case job
GPU1: another complete model-case job
```

此前 Llama-3.1-8B-Instruct 的 Reference-QDQ 实测中，HellaSwag shard 为
1,185.5 秒，另一 shard 为 629.2 秒。若每个 case 固定占两卡，较快的卡会空闲
约 556 秒，并且同一 checkpoint 要重复加载和构造 QDQ 两次。六模型任务改为
model-case 动态队列后，每个 case 只加载一次；任一 GPU 完成当前 case 后立即
领取下一个最长待测 case，从而降低总 GPU 空闲时间。每个 manifest 仍独立记录
模型、case、GPU 和完整 task 集合，不跨 checkpoint 合并数值。

启动前必须检查两张 GPU 的显存与现有进程。不得擅自终止不属于本任务的进程；
资源不足时等待或降低 batch size。正式 ACC 的默认 `batch_size=32`、PPL
`batch_size=1`；某模型 OOM 时可按 32 -> 16 -> 8 -> 4 -> 1 降低 ACC batch，
但必须记录最终值。降低 batch size 不改变数据、prompt、metric 和有效性。

## 7. 执行阶段与 gate

### 阶段 A：静态预检

1. 运行 `exp/test_protocol.py`；
2. 生成并核验数据 manifest；
3. 检查六个 checkpoint 的 `config.json`、tokenizer 文件和全部权重分片；
4. 记录绝对路径、模型架构、config/tokenizer/weight-index/权重分片指纹；
5. 冻结 Python、PyTorch、Transformers、Datasets、Accelerate、Triton、
   lm-eval、CUDA、GPU 型号和算法代码版本。

### 阶段 B：逐模型 smoke

每个模型的 BF16 与 `reference_qdq` 都必须执行 `--limit 1` smoke，验证：

- 模型和原生 tokenizer 可离线加载；
- 六个 task 都能构造并完成 likelihood request；
- WikiText-2 至少一个 2,048-token block 返回有限 NLL；
- `reference_qdq` 的 attach 总数、`per_op` 和每类权重位宽与第 2 节一致；
- 输出 tensor、ACC likelihood 和 PPL NLL 无 NaN/Inf；
- GLM-4、Qwen2.5、Qwen3 的 Transformers 架构接口确实兼容现有 QDQ wrapper。

所有 smoke 输出必须标记：

```text
full_split = false
literature_comparable = false
```

smoke 数值不能进入正式 CSV、论文表或与 BF16 计算 delta。

### 阶段 C：全量正式运行

只有对应模型两个 case 的 smoke 都通过后才可启动 `limit=None` 全量运行。
任一 shard 失败时保留日志和 failure manifest，只重跑失败 shard；两个 shard
均为 `complete` 后才允许 merge。一个模型失败不应污染其他模型已完成结果。

### 阶段 D：归并与一致性审计

归并程序必须检查：

- model fingerprint、case、`literature_2048`、seed 和软件环境匹配；
- 六个 ACC task 不重不漏，样本数等于第 4 节固定值；
- PPL 使用该模型原生 tokenizer，并记录完整 blocks/scoring/tail tokens；
- `full_split=true`、`literature_comparable=true`；
- 每个任务 metric 名称正确，结果为有限数；
- 只有同 checkpoint 的 BF16 与 `reference_qdq` 才计算 delta。

## 8. Manifest、复用与失败恢复

每个 worker 至少记录：

- checkpoint 精确名称、resolved path、架构与模型 fingerprint；
- case 及完整算法参数；
- 数据绝对路径、source、split、行数与 SHA-256；
- task、metric、context length、tokenizer 设置、seed、batch size；
- 软件版本、CUDA/GPU、开始/结束时间和 elapsed time；
- attach summary、截断计数、PPL token/block/tail 计数；
- `status`、`full_split`、`literature_comparable` 和错误 traceback。

旧表数值绝不复用。已有新口径结果也不能只因目录名或 checkpoint path 相同而
直接复制；只有 model/data/code/environment/method/protocol manifest 完全一致、
两个 shard 均完整且 merge 审计通过时，才允许作为 cache hit。任何身份字段
缺失或不一致都必须重跑。默认计划仍覆盖六个模型的两个 case。

结果目录不得原地覆盖成功 manifest。建议结构为：

```text
results/six_model_algorithm_literature_2048/
  <model_slug>/
    bf16_literature_2048/
      shard_gpu0/
      shard_gpu1/
      merged/
    reference_qdq_literature_2048/
      shard_gpu0/
      shard_gpu1/
      merged/
  six_model_summary.csv
  six_model_delta.csv
  experiment_manifest.json
```

## 9. 正式输出表（全量实测）

下表所有 ACC 均为百分数，PPL 为 WikiText-2 raw-v1 完整 test stream 的
token-weighted perplexity。`ScaleCode` 即第 3.2 节冻结的 `reference_qdq`，不是
硬件定点仿真。

| Model checkpoint | Case | PIQA `acc_norm` | ARC-e `acc_norm` | ARC-c `acc_norm` | BoolQ `acc` | HellaSwag `acc_norm` | WinoGrande `acc` | Macro ACC | WikiText-2 PPL | PPL scoring tokens | Status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| DeepSeek-R1-Distill-Llama-8B | BF16 | 60.0109 | 40.5724 | 28.4130 | 62.1713 | 52.9476 | 52.8808 | 49.4993 | 26.33755 | 315,238 | complete |
| DeepSeek-R1-Distill-Llama-8B | ScaleCode | 58.0522 | 38.2155 | 27.3891 | 62.1713 | 49.8307 | 52.0916 | 47.9584 | 29.88011 | 315,238 | complete |
| GLM-4-9B-0414 | BF16 | 80.4679 | 81.1027 | 60.3242 | 86.8196 | 80.2330 | 73.2439 | 77.0319 | 11.39536 | 288,627 | complete |
| GLM-4-9B-0414 | ScaleCode | 80.4135 | 80.5976 | 59.8976 | 86.9419 | 79.7252 | 72.8493 | 76.7375 | 11.59886 | 288,627 | complete |
| Llama-3.1-8B-Instruct | BF16 | 81.4472 | 79.7980 | 55.4608 | 85.1376 | 79.5459 | 73.9542 | 75.8906 | 7.16164 | 288,627 | complete |
| Llama-3.1-8B-Instruct | ScaleCode | 80.1959 | 78.6616 | 54.6928 | 83.7003 | 78.5999 | 73.8753 | 74.9543 | 7.57330 | 288,627 | complete |
| Llama-3.2-3B-Instruct | BF16 | 77.0403 | 71.1700 | 46.3311 | 78.5321 | 71.6092 | 68.3504 | 68.8389 | 10.94305 | 288,627 | complete |
| Llama-3.2-3B-Instruct | ScaleCode | 74.9184 | 66.8771 | 44.4539 | 79.1437 | 67.5762 | 69.2186 | 67.0313 | 12.50951 | 288,627 | complete |
| Qwen2.5-7B-Instruct | BF16 | 79.6518 | 76.1364 | 51.6212 | 85.4434 | 79.5459 | 70.0079 | 73.7344 | 8.24882 | 296,815 | complete |
| Qwen2.5-7B-Instruct | ScaleCode | 78.5637 | 74.6633 | 51.3652 | 84.0979 | 78.7293 | 69.0608 | 72.7467 | 8.66721 | 296,815 | complete |
| Qwen3-8B | BF16 | 77.4755 | 80.8502 | 56.4846 | 86.6667 | 74.9452 | 67.8769 | 74.0498 | 9.73551 | 296,815 | complete |
| Qwen3-8B | ScaleCode | 76.8226 | 79.8401 | 55.8020 | 86.2997 | 73.4515 | 67.3244 | 73.2567 | 10.06784 | 296,815 | complete |

每项 ACC 在明细 CSV/JSON 中同时给出 `n_samples` 与 `stderr`。Delta 表使用：

```text
ACC delta (pp) = 100 x (ACC_reference_qdq - ACC_bf16)
PPL relative change (%) = 100 x (PPL_reference_qdq / PPL_bf16 - 1)
```

不得把 ACC 的相对百分比变化写成百分点，也不得把 PPL 绝对差写成相对百分比。

| Model checkpoint | ScaleCode - BF16 Macro ACC (pp) | BF16 PPL | ScaleCode PPL | PPL 相对变化 |
|---|---:|---:|---:|---:|
| DeepSeek-R1-Distill-Llama-8B | -1.5409 | 26.33755 | 29.88011 | +13.4506% |
| GLM-4-9B-0414 | -0.2944 | 11.39536 | 11.59886 | +1.7858% |
| Llama-3.1-8B-Instruct | -0.9363 | 7.16164 | 7.57330 | +5.7481% |
| Llama-3.2-3B-Instruct | -1.8075 | 10.94305 | 12.50951 | +14.3147% |
| Qwen2.5-7B-Instruct | -0.9877 | 8.24882 | 8.66721 | +5.0720% |
| Qwen3-8B | -0.7931 | 9.73551 | 10.06784 | +3.4136% |

## 10. 明确禁止的口径混用

以下结果均不能进入本轮主表：

- first-1、first-300 或任何 first-N ACC；
- ARC validation 代替 ARC test；
- 旧五任务中的 OpenBookQA，或把 GSM8K 混入六任务 Macro ACC；
- 旧 `score_char_norm` 代替 lm-eval 0.4.11 `acc_norm`；
- chat-template、system prompt 或 few-shot 结果；
- 前 65,536 token、128 context、滑窗/重叠窗口或 block-PPL 平均；
- `hardware_128`、V5 full-chain、S24 前端、硬件位宽修正版或 RTL error path；
- base 与 Instruct checkpoint、不同 tokenizer 或不同 harness 版本之间直接求 delta；
- smoke、失败恢复中的部分数据或任何 NaN/Inf 结果。

## 11. 程序实施状态

以下原定实施项均已完成：

1. `run_six_model_eval.py` 实现六模型动态双 GPU 队列、逐 case 目录、cache/resume；
2. `prepare_model_identity.py` 对 checkpoint 全文件生成 SHA-256 身份；
3. 总 manifest 记录算法与评测程序逐文件 SHA-256 及聚合代码指纹；
4. `six_model_matrix.py` 对每种架构的 attach 总数、`per_op` 和权重位宽强校验；
5. 12 个 model-case 的 smoke gate 全部通过，且 smoke 与正式结果目录隔离；
6. 12 个 model-case 全量运行、恢复、归并与全局一致性审计全部完成。

## 12. 完成判据

只有同时满足以下条件，才可宣布六模型 ACC/PPL 实验完成：

1. 六个精确 checkpoint 均有 BF16 与 `reference_qdq` 两行正式结果；
2. 72 个 ACC task-level 结果全部覆盖规定 split 和样本数，并带 stderr；
3. 12 个 PPL 结果全部覆盖各 tokenizer 对应的完整 2,048-token blocks；
4. 12 个 model-case worker 均为 `complete`，每个 case 的七项任务无缺失或重复；
5. 所有 merge、fingerprint、协议和有限数检查通过；
6. 生成主表、delta 表、总 manifest，并可从表中每个值追溯到 worker manifest；
7. smoke、旧表、硬件 128-context 和失败运行均未进入正式结果。

在以上条件全部满足前，只能汇报“进行中”或明确的失败状态，不能用局部模型、
局部 task 或旧数据推断六模型结论。

## 13. 实际执行、失败恢复与审计结论

### 13.1 双 GPU 长任务执行

- 硬件：2 × NVIDIA RTX A6000 48 GB；
- 调度窗口：2026-09-14 14:15:34 至 17:08:20（Asia/Shanghai），约 2 小时
  52 分 47 秒，包含数据/模型预检、tokenizer 审计、12 个 smoke、12 个全量
  model-case 与 DeepSeek 失败恢复；
- 两个独立 worker 各绑定一张 GPU，按预计耗时最长优先动态取任务；
- full 模式总覆盖 6 × 2 × 6 = 72 个完整 ACC task 结果以及 12 个完整 PPL；
- 结束后两张 GPU 均无本实验残留进程。

### 13.2 PPL token 规模

同一模型的 BF16 与 ScaleCode 使用完全相同的 tokenizer stream 与 block 边界。

| Tokenizer/checkpoint | Raw tokens | 2,048-token blocks | Scoring tokens | Discarded tail |
|---|---:|---:|---:|---:|
| DeepSeek-R1-Distill-Llama-8B | 316,944 | 154 | 315,238 | 1,552 |
| GLM-4-9B-0414 | 289,583 | 141 | 288,627 | 815 |
| Llama-3.1-8B-Instruct | 288,936 | 141 | 288,627 | 168 |
| Llama-3.2-3B-Instruct | 288,936 | 141 | 288,627 | 168 |
| Qwen2.5-7B-Instruct | 298,938 | 145 | 296,815 | 1,978 |
| Qwen3-8B | 298,938 | 145 | 296,815 | 1,978 |

### 13.3 DeepSeek 首次失败与恢复

DeepSeek ScaleCode 首次全量运行在第 24,879/67,106 个 likelihood request
触发 lm-eval 的空 continuation 断言。这是 tokenizer 在 prompt/choice 边界
发生 token merge 所致，不是 ScaleCode 张量溢出、NaN/Inf、显存不足或模型
checkpoint 损坏。修复后静态审计 67,106 个请求，其中 37,976 个走
`fixed_context_independent_continuation_fallback_v1`，空 continuation 为 0。

恢复运行把 HellaSwag 与其余任务分给两张 GPU 并行完成，随后只归并通过完整性
检查的 recovery shards。首次失败的 log、failure manifest 和 run state 均保留，
不删除、不伪装为成功记录；权威状态以最终 `experiment_manifest.json` 为准。

### 13.4 最终审计

- `test_protocol.py`：6/6 通过（含旧版 PPL manifest 缺省 Down-S24 字段的合并兼容性）；
- `test_tokenizer_boundary.py`：2/2 通过；
- `python -m py_compile exp/*.py`：通过；
- `experiment_manifest.json`：`status=complete`；
- completed model-case：12/12；
- `missing=[]`；
- `validation_errors=[]`；
- 算法与评测代码聚合 SHA-256：
  `fffcf5c1a4453774cec5db2ec07efebd3fd7a28c5de6eab3aa334911181749bd`。

### 13.5 可用于论文的结论边界

本实验支持的结论是：ScaleCode 软件算法在六个 checkpoint 上可完整运行，并且
相对 matched BF16 的 Macro ACC 下降范围为 0.2944–1.8075 pp，WikiText-2 PPL
相对上升范围为 1.7858%–14.3147%。因此不能笼统写成“无损”或“始终维持 BF16
精度”；更严谨的表述应是多数模型的知识任务 Macro ACC 下降约 1 pp，但
DeepSeek 与 Llama-3.2 的语言建模 PPL 更敏感。该结论只验证算法级 QDQ，不证明
S24 等硬件入口、定点 Hadamard、定点 accumulator 或完整 FPGA 链路的 bit-exact
精度；硬件结论必须由独立 V5/full-chain 实验支持。
