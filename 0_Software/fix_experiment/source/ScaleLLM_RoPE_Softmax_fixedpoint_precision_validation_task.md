# ScaleLLM Attention/MLP 全定点真实推理精度验证任务书

版本：2026-09-17  
状态：按 2026-09-17 用户指令暂停；PPL、Attention 六任务 ACC 和
layer 0/15/31 trace 已完成，MLP-only/Full V5 六任务 ACC 未完成  
目标模型：`Llama-3.1-8B-Instruct`

## 1. 要回答的问题

本实验不预设“定点无损”，而是用可复现证据回答：把 Attention 中的 RoPE、
KV cache、QK、Softmax 和 PV 连同前后投影，以及 MLP 中的 Gate/Up、SiLU、
SwiGLU 和 Down 全部改为 FPGA 的整数数据通路后，相对同 checkpoint、同
128-token 评测协议的浮点模型，节点误差、最终 logit、ACC 和 PPL 是否仍在
可接受范围内。

结论必须同时满足三层证据：

1. 软件整数孪生与 RTL 的标量/向量输出逐 bit 一致；
2. 在真实 Llama 激活上分别验证 Attention-only、MLP-only 和完整 V5，不能只
   用随机输入或只验证 RoPE/Softmax；
3. 在完整真实评测任务上，定点链路相对 matched BF16 基线的
   质量退化满足预先冻结的阈值。

只给出几个随机张量的 cosine，或只给最终 ACC/PPL，均不能单独证明硬件算术
正确且精度可保持。

## 2. 当前硬件数值合同

权威硬件树为：

```text
fpga_llm_project/0_fix_newdataflow_Hadamard/HAP
```

本轮软件孪生冻结以下合同：

| 节点 | 当前格式/规则 |
|---|---|
| post-RMSNorm 输入 | S24 Q8.16，round-half-away，饱和 |
| activation frontend | normalized Hadamard32；Group32；asymmetric MinMax A8；ScaleCode |
| Q/K/V/Wo weight | W8 + ScaleCode，Group32 |
| Q/K/V/Wo 输出 | S24 Q8.16 |
| RoPE 系数 | S18 Q2.16，范围 `[-1,+1]` |
| RoPE 输出 | S24 Q8.16，乘法后 round-half-away，再加减和饱和 |
| KV cache | 对称 KV12 + Group32 ScaleCode；禁止编码 `-2048` |
| QK dot | Q S24 × K S12；每 Group32 得到 S40 |
| score | S20 Q6.14；四个 head groups 累加后裁剪到 `[-16,+16]` |
| exp | 257-entry U17 LUT + 10-bit 线性插值 |
| Softmax sum/reciprocal | row sum U24；reciprocal U17 |
| probability | U0.16，最终 clamp 到 U16 |
| PV | S43 Q19.24 accumulator；round-half-away `/2^8` 到 S24 Q8.16 |
| context | 最多 128 tokens；causal mask |
| Attention format ID | `0x48384103` |
| 完整 MLP format ID | `0x48384603` |
| MLP format-v3 | total shift `[20,44]`；S37 guard；S44 Gate/Up；S46 Down |
| MLP Down 最终边界 | 当前仍为 S24 Q8.16；实测已确认动态范围不足，不是已签核格式 |

注意：`model/fixbit_v2.py` 中的 `0x48384102` 是旧的模型标签。当前生产
Attention top、Host runtime 和 artifact exporter 使用 `0x48384103`。在未完成
新向量的 RTL 逐 bit 回归前，旧 label 的 Python self-test 只能证明算术 helper，
不能直接替代当前 production format 的版本一致性证据。

## 3. 五条 matched 推理路径

所有硬件结论统一使用 `hardware_128`，禁止与 `literature_2048` 的绝对 PPL
直接相减。

| Case | 作用 | Attention | MLP/其余路径 |
|---|---|---|---|
| `bf16` | matched 基线 | 原生 BF16 | 原生 BF16 |
| `reference_qdq` | 分离算法量化误差 | Hadamard/Group32 A8W8 ScaleCode QDQ；RoPE/Softmax 仍浮点 | MLP A8W4 ScaleCode QDQ |
| `v5_attention` | 分离 Attention 中间定点误差 | QKV、RoPE、KV12、QK、Softmax、PV、Wo 全定点 | 原生 BF16；Wo 的 S24 边界转回 BF16 |
| `v5_mlp` | 分离 MLP 定点误差 | 原生 BF16 Attention/RoPE/Softmax | Gate/Up、SiLU、SwiGLU、Down 全定点；S24 边界转回 BF16 |
| `v5` | 完整硬件数值孪生 | 全定点 | MLP 全定点；Host FP32 RMSNorm/residual，FP32 LM head |

`v5_attention` 是因果归因用消融，不等于板上完整 runtime；`v5` 才表示当前
完整硬件数值边界。

当前 format-v3 修改已解决历史 shift-20 与内部 accumulator 合同，但没有解决
Down 的最终 S24/F16 输出边界。该边界从 accumulator finalize 一直延伸到
scheduler/repack、serial/full command、resource/production top、tensor DMA 和
Host unpack；只拓宽 S46 内部状态不能消除末级饱和。正确性优先候选是仅把
Down-only 输出全链改为 S32/F16，同时保持 MLP 输入与 Gate/Up 输出为 S24/F16。

### 3.1 Down 输出硬件修正规格

当前失败与 Group32、ScaleCode 或 S37/S44/S46 内部累计无关。软件全流中
`linear_group_guard_overflow_s37=0`、`linear_accumulator_overflow=0`；失败点是
S46/F24 累加结果按 round-half-away 除以 `2^8` 恢复为 F16 后，又被
`saturate_s24` 钳位到 `[-128,127.9999847]`。layer 31 的参考绝对峰值
`587.87` 已直接违反该边界。

正确性优先的修改必须满足以下不可分割的合同：

1. 保留 post-RMSNorm 输入、Gate/Up 输出的 S24/F16，保留 Group32、S37/F24
   guard、Gate/Up S44/F24 和 Down S46/F24 accumulator；不得把全部 MLP
   激活接口无差别拓宽。
2. 仅将 Down finalizer 改为 S32/F16：仍执行 round-half-away `/2^8`，随后按
   signed-32 范围饱和，并输出独立的 Down-S32 saturation counter。计数非零时
   必须 fail closed。
3. 将 Down-only 的 shared output、12→16 repack、scheduler、serial/full
   command、resource/production top 由 `16×12×24`/`16×16×24` 同步改为
   `16×12×32`/`16×16×32`；Gate/Up 的 S24 repack 不变。
4. tensor DMA 输入仍为 S24/F16 的 48 AXI256 beats/group；Down 输出 tile 从
   `6144 bit = 24 beats` 改为 `8192 bit = 32 beats`，完整 256 tiles 从
   6,144 beats 改为 8,192 beats。输出 beat bank/hold mask 扩到 32 项，
   `output_issue_count` 至少为 6 bit，以能表示完成哨兵值 32。
5. Host 将输入和输出 payload 分开：H2C 输入仍为 192 KiB S24/F16，C2H Down
   输出改为 256 KiB little-endian S32/F16；解包到 FP32 后再做 residual 和
   RMSNorm，下一层入口重新量化为 S24/F16。现有 1 MiB slot 无需改变。
6. 这是 ABI 不兼容修改。当前 `0x48384603` 不得继续代表新格式；建议将新合同
   定义为 `0x48384604`，并同时更新 RTL format register、Host 常量、artifact
   manifest、source-closure 和定向向量。当前 checked-in artifact 仍为
   `0x48384602`，不能用于任何新格式签核。

S32/F16 覆盖约 `[-32768,32767.9999847]`，相对已观测 `587.87` 有约 55 倍
峰值余量且天然对齐 32-bit/AXI256。它仍是 Llama-3.1-8B 的正确性优先候选，
不是未经验证的普适最小位宽；硬件冻结前仍需全流 pre-saturation 范围 sweep、
完整 WikiText-2 PPL 和六任务 ACC。S27/S28/F16 或 S24/F13 只能作为后续
带宽 Pareto 消融，不能替代本轮修复。

离线迁移审计器为
`exp/audit_mlp_down_s32_migration.py`。当前 active production closure 的基线结果
为 `4/15 PASS`：通过项仅证明 Gate/Up S24、MLP 输入 S24 和 production source
closure 等应保持项仍在；Down finalizer、shared Down、scheduler/repack、三层命令/
顶层、production core、DMA 输出、Host C2H、format ID 与 terminal saturation
telemetry 共 11 项仍为 FAIL。硬件修改过程中可使用 `--allow-incomplete` 生成中间
清单；正式签核必须去掉该参数并得到 `15/15 complete_pass`。

## 4. 节点级验证

### 4.1 RTL 一致性

对 RoPE、KV12、QK scale/clip、exp LUT、reciprocal、probability 和 PV 建立冻结
输入向量。Python 与 xsim 的每个整数输出必须 0 mismatch，并记录输入向量、
RTL source、LUT 和 Python model 的 SHA-256。

判定规则：

- mismatch 必须为 0；
- reserved code、非法 shift、overflow 和饱和事件必须与 RTL counter 一致；
- 任何 format ID 或 LUT SHA 不一致均 fail closed。

### 4.2 真实激活 trace

从本地 checkpoint 和固定 prompt 获取真实 post-RMSNorm 激活，至少覆盖 layer
0、15、31。逐节点同时计算浮点 reference 与整数孪生，报告：

- cosine similarity；
- NMSE；
- MAE、max absolute error；
- top-1 agreement（logit 节点）；
- S24 saturation、KV12 clip、QK score clip、Softmax probability clamp 次数；
- score 落在 `[-16,+16]` 边界的比例。

RoPE 和 Softmax 还要各报告两种误差：只替换该节点的局部误差，以及叠加上游
A8W8/KV12 后的累计误差，不能把所有误差都归因给 Softmax LUT。

MLP 必须额外在 layer 0、15、31 记录 Gate/Up projection、SiLU LUT、SwiGLU
乘积、SwiGLU 重新量化、Down projection 和最终 S24 输出。除 cosine、NMSE、
MAE 和最大误差外，还必须报告每个 Linear 模块的 total-shift 分布、S37 guard、
S44/S46 accumulator、S24 saturation 计数。`v5_mlp` 用来隔离 MLP 误差，
`v5` 用来确认 Attention 与 MLP 的误差叠加；两者都必须在真实 checkpoint 和
真实数据上运行，随机张量测试不能替代真实推理。

## 5. 端到端 ACC/PPL 口径

### 5.1 ACC

- `lm-evaluation-harness==0.4.11`；
- zero-shot continuation likelihood；不用 chat template；
- PIQA、ARC-Easy、ARC-Challenge、BoolQ、HellaSwag、WinoGrande 完整官方 split；
- 主指标依次为 `acc_norm/acc_norm/acc_norm/acc/acc_norm/acc`；
- 六任务等权 macro average；
- context=128，超长 continuation 用滚动窗口评分全部 choice token；
- 每个 case 使用完全相同的 prompt、tokenizer、截断和 scoring 代码。

### 5.2 PPL

- WikiText-2 raw-v1 完整 test；去空行后用 `\n\n` 拼接；
- checkpoint 原生 tokenizer，`add_special_tokens=False`；
- 128-token 不重叠完整 block；tail 丢弃；
- 每个 block 首 token 不计 NLL；先累加总 NLL/总 scoring tokens，再指数化；
- 只能与 `bf16 + hardware_128` matched baseline 比较。

### 5.3 预注册判定阈值

以下阈值在查看新结果前冻结，用于“精度保持”的工程判定，不应写成数学无损：

| 指标 | `v5_attention` 相对 BF16 | `v5_mlp` 相对 BF16 | `v5` 相对 BF16 |
|---|---:|---:|---:|
| 六任务 macro ACC | 下降不超过 1.0 pp | 下降不超过 1.0 pp | 下降不超过 1.5 pp |
| WikiText-2 PPL | 相对上升不超过 10% | 相对上升不超过 10% | 相对上升不超过 15% |
| 非预期 overflow/format error | 0 | 0 | 0 |

同时报告各任务 delta 和标准误。即使 macro 通过，若单任务退化超过 3 pp，也必须
单独分析，不能只用平均值掩盖。

## 6. 双 GPU 执行

两张 GPU 按阶段分担不同 case。显存允许时可在低利用率 GPU 上并行一个有界
smoke，但完整正式任务仍保持每卡一个主模型：

```text
阶段 A：GPU0 v5_attention full PPL；GPU1 v5 full PPL
阶段 B：GPU0 v5_mlp full PPL；GPU1 v5 full ACC shard
阶段 C：两卡分别完成 v5_attention/v5_mlp/v5 的六任务 ACC shard
```

先跑 `limit=8` 的五 case smoke，确认 format error、OOM、NaN 和输出 schema 均为
0；随后运行完整 ACC split 和完整 WikiText-2。所有结果写入新的独立目录，不覆盖
既有 `literature_2048` 结果。

建议结果根目录：

```text
ScaleLLM/0_Software/fix_experiment/results/
  llama31_rope_softmax_fixedpoint_hardware128_v3/
```

## 7. 输出与论文结论边界

最终至少输出：五 case manifest、逐任务 ACC/PPL 表、matched delta 表、硬件 counter、
节点 trace JSON/CSV、RTL vector mismatch 报告和一份结论 Markdown。

只有 Attention 与 MLP 的逐 bit 回归、真实激活 trace 和端到端阈值全部通过时，
论文才可写“the fixed-point Attention and MLP pipeline preserves model quality within
the predefined engineering tolerance”。不得写“无精度损失”或“数学等价”。若
ACC 通过而 PPL 不通过，应写成任务精度可接受但语言建模质量未达到预注册阈值，
并继续定位 Attention 的 score clip/Softmax/PV，或 MLP 的 SiLU/SwiGLU/Down/S24
饱和，不能只归因于 RoPE/Softmax。

## 8. 2026-09-17 实测状态

WikiText-2 `hardware_128` 全流覆盖 2,257 blocks、286,639 scoring tokens：BF16、
Attention-only、MLP-only、Full V5 PPL 分别为 `17.208506`、`17.313385`、
`27.801928`、`27.639944`，相对 BF16 为 `—/+0.609%/+61.559%/+60.618%`。Attention-only
六任务 Macro ACC 为 `75.4337%`，相对 matched BF16 `75.3853%` 变化
`+0.048 pp`，PPL 与 ACC 均通过阈值。

MLP-only 全流共记录 20,251 次最终输出饱和，全部位于 Down projection；Full V5
为 18,044 次。layer 31 Down reference 绝对最大值 `587.87` 超过 S24/F16 的
`127.999985` 上限，local cosine/NMSE 为 `0.86647/0.25779`；内部 S37/S44/S46
guard/accumulator overflow 均为 0。相同 8-block 的 BF16、Down-S24、Down-S32
PPL 为 `15.963785/30.723612/17.577764`，因此 S32 是有效修复方向，但仍缺全流
PPL、六任务 ACC 与 pre-saturation 范围 sweep。

权威结果在
`results/llama31_rope_softmax_fixedpoint_hardware128_v3/`。当前 fail-closed audit
为 50/53，剩余项仅为 MLP-only 合并 ACC manifest、Full V5 合并 ACC manifest
和 GPU 回归。2026-09-17 按用户指令终止两个 HellaSwag worker、balanced queue
和 finalizer；终止时 Full V5 为 `8,775/40,168` requests（21.8%），MLP-only
为 `3,907/40,168`（9.7%），均未完成每样本四候选聚合，因此不得由这些进度
计算或报告中间 ACC。日志保留且无 `failure.json`，但当前 evaluator 不提供
request-level 可恢复 checkpoint。三项缺口补齐前，本任务保持“暂停且证据不完整”，
不能签核完整 V5。
