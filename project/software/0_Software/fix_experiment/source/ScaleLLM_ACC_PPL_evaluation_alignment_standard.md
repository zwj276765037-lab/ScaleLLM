# ScaleLLM ACC/PPL 论文评测口径与对齐规范

版本：2026-09-13  
适用模型：Llama-3.1-8B / Llama-3.1-8B-Instruct  
适用实现：ScaleLLM 软件参考实现与 V5 硬件全链路数值孪生

## 1. 目标与结论

本文定义 ScaleLLM 后续论文统一使用的准确率（ACC）与困惑度（PPL）
评测口径，并审计已有实验能否与 GPTQ、SmoothQuant、OmniQuant、QuaRot、
SpinQuant、GyRot 等量化论文进行横向比较。

结论如下：

1. 文献对齐 ACC 必须使用固定版本的 lm-evaluation-harness、0-shot、完整
   official evaluation split、官方 task template 和 task-specific metric。
2. 文献对齐 PPL 必须使用完整 WikiText-2 test token stream、模型原生
   tokenizer、2048-token 非重叠 block、丢弃不足一个 block 的尾部，并对
   所有被评分 token 的 NLL 做 token-weighted 聚合。
3. 算法优先评测使用 `reference_qdq + literature_2048`：保留
   Hadamard32、Group32 A8、Attention W8、MLP W4 与 ScaleCode，Attention、
   RoPE 和 KV 使用模型原生软件实现。V5 硬件 Attention 与 RoPE 只支持
   128 个位置，因此 V5 只能与 `hardware_128` 协议下的 matched BF16 比较。
4. 旧 V5 的 first-300 ACC 和前 65,536 token、context=128 PPL 均不是论文
   标准结果；现有 V5 还存在 total-shift 格式错误，故旧结果只能称为 RTL
   zero-guard diagnostic。
5. 新实验程序用两个独立模型副本同时占用两张 RTX A6000，按工作量拆分
   benchmark，并在归并阶段禁止跨协议计算差值。

## 2. 代表性论文采用的口径

本规范核对了以下代表性工作：

- [GPTQ](https://arxiv.org/abs/2210.17323)
- [SmoothQuant](https://arxiv.org/abs/2211.10438)
- [AWQ](https://arxiv.org/abs/2306.00978)
- [OmniQuant](https://arxiv.org/abs/2308.13137)
- [QuaRot](https://arxiv.org/abs/2404.00456)
- [SpinQuant](https://arxiv.org/abs/2405.16406)
- [GyRot](https://arxiv.org/abs/2607.27694)

这些论文的版本和模型并不完全相同，因此不存在一个能与所有历史表格逐位
等价的单一环境。但当前旋转量化论文的共同主干足够明确：

| 指标 | 主流共同口径 | 需要单独披露的例外 |
|---|---|---|
| PPL | WikiText-2 test，原生 tokenizer，2048 context，全量文本 | SmoothQuant 较早的部分 LLaMA 实验曾用 512 |
| ACC | lm-eval-harness，0-shot，完整 official split | task 集合和 harness commit 因论文而异 |
| 主任务 | PIQA、ARC-Easy、ARC-Challenge、HellaSwag、WinoGrande | BoolQ、LAMBADA、SIQA、OpenBookQA 按论文扩展 |
| 汇总 | 每任务报告原生 metric；综合值采用任务宏平均 | 不能将样本级 micro average 冒充论文平均值 |

QuaRot 使用 PIQA、WinoGrande、HellaSwag、ARC-Easy、ARC-Challenge、
LAMBADA；OmniQuant/GyRot 常用 PIQA、ARC-Easy、ARC-Challenge、BoolQ、
HellaSwag、WinoGrande；SpinQuant 在此基础上扩展 SIQA 和 OpenBookQA。
因此 ScaleLLM 主 ACC 表采用与 GyRot/OmniQuant 交集一致的六任务集合。

## 3. ScaleLLM 固定评测环境

本轮代码冻结到以下软件栈：

| 组件 | 固定版本 |
|---|---:|
| lm-evaluation-harness | 0.4.11 |
| PyTorch | 2.10.0+cu128 |
| Transformers | 5.3.0 |
| Datasets | 4.8.4 |
| Accelerate | 1.13.0 |
| Triton | 3.6.0 |
| NumPy | 2.2.6 |

实验程序不在运行时隐式选择最新 task。它从
`fpga_llm_project/data` 读取固定的本地数据，并用与 lm-eval 0.4.11 相同的
request 构造和 metric 实现执行评分。每个 worker manifest 都记录软件
版本、数据绝对路径、SHA-256、split、样本数、模型路径、GPU、seed、
上下文长度和截断统计。

如果以后升级 lm-eval，即使任务名称不变，也必须视为新协议版本，先以 BF16
复现基线，不能把两个 harness 版本的结果直接拼入同一消融表。

## 4. ACC 标准

### 4.1 数据集和 split

| Task | Evaluation split | 固定样本数 | 主指标 |
|---|---|---:|---|
| PIQA | validation | 1,838 | `acc_norm` |
| ARC-Easy | test | 2,376 | `acc_norm` |
| ARC-Challenge | test | 1,172 | `acc_norm` |
| BoolQ | validation | 3,270 | `acc` |
| HellaSwag | validation | 10,042 | `acc_norm` |
| WinoGrande | validation/dev | 1,267 | `acc` |

ARC 原有本地文件分别只有 570 和 299 条 validation，不能替代论文常用的
test split。新程序将 `allenai/ai2_arc` revision
`210d026faf9955653af8916fad021475a3f00453` 的两个 test split 固定物化到：

- `fpga_llm_project/data/lm_eval_standard/arc_easy_test.jsonl`
- `fpga_llm_project/data/lm_eval_standard/arc_challenge_test.jsonl`

任何文件缺失或样本数不等于表中固定值时，标准实验直接失败，不允许回退到
first-N 或 validation 后继续标记为 literature-aligned。

### 4.2 Prompt、choice 与评分

ACC 为 0-shot continuation likelihood 评测，不使用 instruct chat template，
不额外加入 system prompt。

- PIQA 使用 `Question: {goal}\nAnswer:`，choices 为 `sol1/sol2`。
- ARC 使用 `Question: {question}\nAnswer:`，choices 为选项正文。
- BoolQ 使用 `{passage}\nQuestion: {question}?\nAnswer:`，choices 为
  `no/yes`。
- HellaSwag 必须加入 `activity_label`，将 `ctx_b` 首字母大写，并清理
  `[title]` 与方括号伪影。
- WinoGrande 按 lm-eval 的 multiple-input 定义构造：将候选项填入空格前
  的 prefix，只对空格后的共同 suffix 计算条件似然。

`acc` 选择总 log-likelihood 最大的选项。lm-eval 0.4.11 的 `acc_norm`
选择“总 log-likelihood / choice 字符长度”最大的选项；它不是 token 平均，
也不能用另一个自定义 `score_char_norm` 名称替代后声称等价。

六任务综合准确率定义为任务宏平均：

```text
ACC_macro = (PIQA_acc_norm + ARC-e_acc_norm + ARC-c_acc_norm
             + BoolQ_acc + HellaSwag_acc_norm + WinoGrande_acc) / 6
```

必须同时报告各任务分数、样本数和标准误，不能只报告宏平均。

## 5. PPL 标准

### 5.1 数学定义

设一个完整 block 的 token 为 `x_0, ..., x_(L-1)`，其负对数似然为：

```text
NLL_block = - sum[t=1..L-1] log p(x_t | x_0, ..., x_(t-1))
```

对所有完整 block 求和后：

```text
PPL = exp(total_NLL / total_scoring_tokens)
```

不能先计算各 block 的 PPL 再做算术平均，因为不同有效长度或异常 block 会
改变权重。标准程序始终累计 NLL 总和和被评分 token 总数。

### 5.2 数据处理

固定规则如下：

1. 读取 WikiText-2 raw-v1 test。
2. 丢弃空文本行，以两个换行符连接非空文本。
3. 使用被测 checkpoint 自带 tokenizer，`add_special_tokens=False`。
4. 按 `L=2048` 从头切成不重叠完整 block。
5. 不足 2048 token 的 tail 丢弃。
6. 每个 block 的第一个 token 只作为条件，不计入 NLL。

Llama-3.1-8B-Instruct tokenizer 对当前固定文件得到 288,936 个 token：

| 协议 | Block | 完整 blocks | Scoring tokens | Tail tokens |
|---|---:|---:|---:|---:|
| `literature_2048` | 2,048 | 141 | 288,627 | 168 |
| `hardware_128` | 128 | 2,257 | 286,639 | 40 |

两个 PPL 虽然使用同一个原始 test 文件，但条件上下文不同，属于两个不同
指标，绝对值不能横向比较。

## 6. 两种协议及允许的比较

| 协议 | ACC max length | PPL block | 可运行对象 | 允许的结论 |
|---|---:|---:|---|---|
| `literature_2048` | 2,048 | 2,048 | BF16、软件 Reference-QDQ | 与相同 checkpoint/协议的论文表比较 |
| `hardware_128` | 128 | 128 | matched BF16、V5 full-chain | 只比较 BF16-128 与 V5-128 的相对退化 |

严格禁止以下比较：

- V5-128 PPL 与论文 BF16/QuaRot/SpinQuant 2048 PPL 的绝对值比较；
- first-300 ACC 与完整 split ACC 的绝对值比较；
- Llama-3.1-8B-Instruct 与 LLaMA-3 8B base 的绝对 ACC/PPL 比较；
- `complete_invalid_format_error` 与任何合法硬件实现的质量比较；
- 不同 lm-eval 版本、prompt 或 metric 的结果直接求 delta。

### 6.1 128-context 对 ACC 的实际影响

以 Llama-3.1-8B-Instruct tokenizer 对六任务完整 lm-eval request 做静态审计，
需要左截断的文档如下：

| Task | 完整文档数 | 128 下截断文档 | 截断比例 | 2048 下截断文档 |
|---|---:|---:|---:|---:|
| PIQA | 1,838 | 16 | 0.871% | 0 |
| ARC-Easy | 2,376 | 3 | 0.126% | 0 |
| ARC-Challenge | 1,172 | 3 | 0.256% | 0 |
| BoolQ | 3,270 | 1,552 | 47.462% | 0 |
| HellaSwag | 10,042 | 39 | 0.388% | 0 |
| WinoGrande | 1,267 | 0 | 0% | 0 |

BoolQ 接近一半的 passage 在 128 下被左截断。因此即使
`hardware_128` 使用完整 official split，其 BoolQ 绝对准确率仍不能冒充
标准 lm-eval 结果。PIQA 的 16 个受影响文档中，10 个文档包含合计 20 个
超过 128 token 的 choice；标准 HFLM 会对此直接报错。新硬件协议不会丢弃
这些样本，也不会只评分 choice 尾部，而是用长度不超过 128 的滚动窗口评分
全部 choice token。其余 6 个 PIQA 文档和表中其他受影响文档采用 HFLM 的
prompt 左截断语义。新 worker 会分别记录 `left_truncated_prompt_*` 和
`windowed_continuation_*` 计数。该滚动策略仍属于硬件约束协议，不属于标准
2048 ACC。

## 7. 目前实验存在的问题

旧入口：

`ScaleLLM/0_Software/FPtoQ/experiment/run_v5_fullchain_eval.py`

### 7.1 ACC 问题

1. 每任务只取 first-300，ARC-Challenge 实际只有 299 条。
2. 旧五任务为 PIQA、ARC-Challenge、OpenBookQA、HellaSwag、WinoGrande，
   缺 ARC-Easy 和 BoolQ，与 GyRot 六任务只有四项重合。
3. PIQA 旧 prompt 为 `Goal/Solution`，而 lm-eval 为 `Question/Answer`。
4. HellaSwag 未完整加入 `activity_label`、`ctx_b.capitalize()` 和文本清理。
5. WinoGrande 对 candidate+suffix 整段评分，与 lm-eval 的 multiple-input
   blank 填充方式不同。
6. 自定义 `score_char_norm` 的请求构造、leading-space 和归一化对象没有
   由 lm-eval task 固定，不能直接命名为标准 `acc_norm`。
7. ARC/OpenBookQA split 和标准 harness 不一致。

first-300 偏差已经在仓库历史结果中体现：旧 first-300 BF16 五任务宏平均为
64.503%，完整 split 自定义五任务为 66.662%，相差 -2.159 个百分点；
HellaSwag 单项相差约 -14.590 个百分点。因此 first-300 只适合 smoke test。

### 7.2 PPL 问题

旧 V5 PPL 使用：

- block/context = 128；
- stride = 127；
- 只取前 65,536 token；
- 517 个重叠一 token 的窗口；
- 65,535 scoring tokens。

它只覆盖当前固定 WikiText token stream 的约 22.68%，并且窗口边界规则不同
于 2048 非重叠标准。旧 BF16 17.8417、V5 28.1809 只能描述旧的 matched
context-128 诊断，不能放入 QuaRot/SpinQuant/GyRot 的 2048 PPL 主表。

### 7.3 硬件合同仍无效

旧 V5 运行累计 517 个 `linear_total_shift_format_error`。已知严格失败点为：

```text
model.layers.31.mlp.down_proj.weight
activation_shift = 6
weight_shift = 14
total_shift = 20
MLP legal range = [21, 44]
```

生产 RTL 对非法非零 ScaleCode pair 使用 zero guard，但这不等于合法量化格式。
新程序默认严格失败。只有显式传入 `--allow-format-errors` 才继续诊断，且最终
状态固定为 `complete_invalid_format_error`，不能被汇总脚本包装成有效结果。

### 7.4 Checkpoint 身份不一致

当前默认 checkpoint 是 Llama-3.1-8B-Instruct，而 QuaRot/SpinQuant 的部分
主表使用 LLaMA-3 8B base。协议相同不代表 checkpoint 相同。论文中若坚持
报告 Instruct 模型，应以同一 Instruct BF16 为基线报告相对变化；若要与 base
模型绝对值横比，还必须补跑完全相同的 base checkpoint。

## 8. 新双 GPU 实验实现

程序目录：`ScaleLLM/0_Software/fix_experiment/exp`

| 文件 | 功能 |
|---|---|
| `protocol.py` | 固定数据路径、样本数、lm-eval task template、主指标和协议约束 |
| `prepare_standard_data.py` | 固定 revision 物化/校验 ARC test，并生成数据 SHA-256 manifest |
| `run_eval_worker.py` | 单 GPU 加载一个模型副本，执行标准 ACC、PPL 和截断/硬件审计 |
| `merge_eval_shards.py` | 检查 task 不重不漏，合并两 GPU 输出，计算六任务宏平均 |
| `summarize_plan.py` | 汇总阶段，只为相同协议的 BF16/V5 计算 delta |
| `run_dual_gpu_eval.sh` | 两张 GPU 并发调度与阶段管理 |
| `test_protocol.py` | 固定样本数、首请求模板和禁止误标规则的回归测试 |

每个阶段使用两个独立进程和两个完整模型副本：

```text
GPU0: HellaSwag
GPU1: WikiText-2 + PIQA + ARC-Easy + ARC-Challenge + BoolQ + WinoGrande
```

HellaSwag 有 40,168 个 choice likelihood request，单独放在 GPU0；GPU1 执行
其余约 26,938 个 ACC request 和 PPL，从而避免简单按任务数二等分造成 GPU0
长期空闲。两个进程都只看到一个物理 GPU，并在本地将其映射为 `cuda:0`。

Transformers 5.x 将 checkpoint 中的 `rope_theta/rope_scaling` 归一化为
`rope_parameters`，同时将 LlamaAttention 返回接口从三项改为两项。冻结的
V5 twin 按 Transformers 4.x 接口实现。新 worker 仅恢复原 checkpoint 的
RoPE 配置别名、补齐不可变的 head geometry 属性，并将 V5 返回元组从三项
适配为两项；定点、Hadamard、量化、QK/Softmax/PV 和 MLP 数值路径均不变。
该适配会写入 method manifest，防止环境兼容层被误认为算法修改。

### 8.1 推荐命令

完整论文计划：

```bash
cd /home/user/EDA-202/zhuowenjun
ScaleLLM/0_Software/fix_experiment/exp/run_dual_gpu_eval.sh \
  --plan paper \
  --output ScaleLLM/0_Software/fix_experiment/results/paper_full
```

该计划按顺序执行：

1. BF16 + `literature_2048`；
2. Reference-QDQ + `literature_2048`；
3. BF16 + `hardware_128`；
4. V5 + `hardware_128`。

每个阶段内部两张 GPU 并发。阶段之间顺序执行，以免在同一 GPU 上同时驻留
多个 8B 模型。

仅检查文献口径：

```bash
ScaleLLM/0_Software/fix_experiment/exp/run_dual_gpu_eval.sh \
  --plan literature \
  --output ScaleLLM/0_Software/fix_experiment/results/bf16_literature
```

算法优先的 matched 论文口径运行：

```bash
ScaleLLM/0_Software/fix_experiment/exp/run_dual_gpu_eval.sh \
  --plan algorithm \
  --batch-size 32 \
  --ppl-batch-size 1 \
  --output ScaleLLM/0_Software/fix_experiment/results/algorithm_reference
```

`algorithm` 依次运行 BF16 与 Reference-QDQ 的 `literature_2048`；已有完整
BF16-2048 时可用 `algorithm-only` 只运行 Reference-QDQ。Reference-QDQ
保留 Hadamard32、Group32 A8、Attention W8、MLP W4 与 ScaleCode，使用原生
软件 Attention/RoPE/KV，不受 V5 的 128-position 合同限制。

冒烟测试：

```bash
ScaleLLM/0_Software/fix_experiment/exp/run_dual_gpu_eval.sh \
  --plan literature \
  --limit 1 \
  --output ScaleLLM/0_Software/fix_experiment/results/smoke_limit1
```

任何非零 `--limit` 都会强制写入：

```text
full_split = false
literature_comparable = false
```

### 8.2 输出与论文取数

每个阶段生成：

- `shard_gpu0/manifest.json`、`shard_gpu1/manifest.json`：原始 worker 证据；
- `merged/summary.csv`：逐任务主指标；
- `merged/manifest.json`：宏平均、PPL、协议、数据和硬件审计；
- `gpu0.log`、`gpu1.log`：完整运行日志。

整个 plan 生成：

- `paper_summary.csv`：论文取数入口；
- `paper_manifest.json`：比较规则与来源 manifest。

论文表格至少应包含：模型完整名称、case、上下文长度、每任务 ACC、六任务
宏平均、PPL、数据集/split、lm-eval 版本、是否 full split、硬件合同状态。

## 9. 当前验证状态

已完成以下非论文级验证：

1. 六个 task builder 的本地样本数全部通过固定值检查。
2. PIQA、ARC、HellaSwag、WinoGrande 首条 lm-eval request 与冻结模板一致。
3. 两张 RTX A6000 同时加载 Llama-3.1-8B-Instruct 并完成
   `literature_2048 --limit 1` 双 GPU 冒烟测试。
4. 冒烟输出正确标记 `full_split=false`、
   `protocol_literature_comparable=false`。
5. 归并程序成功拒绝跨协议比较，只在协议名称、上下文和 full-split 状态匹配
   且存在 matched BF16 时计算 Reference-QDQ/V5 delta。
6. V5 严格模式完成 32 层 attach 和 PIQA 单样本请求；该样本未触发
   total-shift 错误，证明新 lm-eval/Transformers 适配入口可执行，但单样本
   通过不覆盖历史全链路已触发的格式错误。
7. 定向选择一个 150-token PIQA continuation，`hardware_128` 滚动分支成功
   评分全部 token 并返回有限 log-likelihood。

冒烟数值不具统计意义，不得写入论文。完整 BF16 已按两种协议运行，完整
Reference-QDQ 已按 `literature_2048` 运行；完整 V5 仍受 strict total-shift
合同约束，只有通过硬件格式审计后才能形成有效结果。

### 9.1 已完成的完整 BF16 结果

完整双 GPU 运行已得到以下基线：

本次运行固定 `batch_size=8`、`ppl_batch_size=1`、seed=20260913；batch size
只改变吞吐，不改变样本、prompt、上下文或 metric 定义。

| Protocol | PIQA | ARC-e | ARC-c | BoolQ | HellaSwag | WinoGrande | Macro ACC | WikiText-2 PPL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `literature_2048` | 81.284 | 79.545 | 55.375 | 85.076 | 79.496 | 73.717 | 75.749 | 7.16143 |
| `hardware_128` | 81.338 | 79.419 | 55.119 | 83.333 | 79.496 | 73.717 | 75.404 | 17.21034 |

ACC 数值单位为百分比；PIQA/ARC/HellaSwag 使用 `acc_norm`，BoolQ/WinoGrande
使用 `acc`。仅改变上下文协议就使宏平均下降 0.345 个百分点，其中 BoolQ
下降 1.743 个百分点；PPL 增加 140.320%。这组实测结果直接证明
`hardware_128` 与 `literature_2048` 不能作为同一个评测口径。

### 9.2 Reference-QDQ 算法全量结果

算法优先实验在两个独立 RTX A6000 worker 上完成，ACC 使用 `batch_size=32`，
PPL 使用 `batch_size=1`。Reference-QDQ 替换全部 224 个目标 Linear：每层
Q/K/V/O 为 A8W8，Gate/Up/Down 为 A8W4；Hadamard block 与量化 group 均为
32，激活与权重 scale 均编码为 8-bit code 与整数 shift。原生 Attention、
RoPE、KV、残差、RMSNorm 和 LM head 不做硬件定点模拟。

| Case | PIQA | ARC-e | ARC-c | BoolQ | HellaSwag | WinoGrande | Macro ACC | WikiText-2 PPL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BF16 | 81.284 | 79.545 | 55.375 | 85.076 | 79.496 | 73.717 | 75.749 | 7.16143 |
| Reference-QDQ | 80.196 | 78.577 | 54.863 | 83.700 | 78.600 | 73.875 | 74.969 | 7.57747 |
| Delta | -1.088 pp | -0.968 pp | -0.512 pp | -1.376 pp | -0.896 pp | +0.158 pp | **-0.780 pp** | **+5.809%** |

WikiText-2 覆盖完整 test token stream：141 个非重叠 2048-token block、
288,627 个 scoring token，tail 168 token 丢弃。六项 ACC 均覆盖完整 official
split，2048 context 下没有截断文档。该结果支持“算法量化退化有限”，但
`-0.780 pp / +5.809% PPL` 不是数学无损，也不是硬件 bit-exact 结果。

正式结果位于：

```text
ScaleLLM/0_Software/fix_experiment/results/algorithm_reference_full/
  reference_qdq_literature_2048/merged/manifest.json
  reference_qdq_literature_2048/merged/summary.csv
  paper_summary.csv
  paper_manifest.json
```

### 9.3 V5 严格全量运行结果

V5 `hardware_128` 的两个 worker 均完成 32 层 attach，但在各自首批真实请求
中独立触发同一个 production-invalid total shift：

```text
GPU0: layer31.mlp.down_proj, row=512, group=170, column=704,
      activation_shift=6, weight_shift=14, total=20, legal=[21,44]
GPU1: layer31.mlp.down_proj, row=0,   group=170, column=704,
      activation_shift=6, weight_shift=14, total=20, legal=[21,44]
```

因此严格计划的 V5 状态是 `failed / strict_failure_before_metrics`，没有合法
V5 ACC 或 PPL。`paper_manifest.json` 显式保留失败 phase 和两个 worker 的
异常，不会因为缺少 merged V5 表而把计划误报为全部完成。若使用
`--allow-format-errors`，得到的只能是 RTL zero-guard diagnostic，不能填入
合法硬件结果列。

## 10. 论文中的推荐表述

文献对齐软件结果可写为：

> We report zero-shot accuracy using lm-evaluation-harness v0.4.11 on the
> complete official evaluation splits. WikiText-2 perplexity is computed on
> the concatenated test token stream using non-overlapping 2,048-token blocks;
> incomplete tail tokens are discarded and token-level negative
> log-likelihoods are aggregated before exponentiation.

V5 硬件结果应单独写为：

> Owing to the 128-position Attention/RoPE limit of the evaluated FPGA design,
> hardware-faithful results are reported against a matched BF16 baseline at
> the same 128-token context. These results are not compared numerically with
> the standard 2,048-context perplexity reported in prior work.

在 total-shift 错误修复前，不应声称“V5 已维持精度”；最多只能声称已建立
可复现的评测程序，并观察 RTL error-path 语义下的诊断结果。

## 11. 参考实现

- [lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness)
- [QuaRot official implementation](https://github.com/spcl/QuaRot)
- [SpinQuant official implementation](https://github.com/facebookresearch/SpinQuant)
- [GPTQ paper](https://arxiv.org/abs/2210.17323)
- [OmniQuant paper](https://arxiv.org/abs/2308.13137)
- [QuaRot paper](https://arxiv.org/abs/2404.00456)
- [SpinQuant paper](https://arxiv.org/abs/2405.16406)
