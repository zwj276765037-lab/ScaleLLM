# FP→Q→Hadamard 精度报告

日期：2026-09-11

## 1. 最终判断

目前没有证据要求修改硬件数据路径。对本次 Qwen2.5-0.5B-Instruct 验证，完整 RTL 激活前端相对归档软件 ScaleCode 基线带来 `+1.060%` 的相对 PPL 增量和 `-0.0916` 个百分点的 token accuracy 变化；真实激活的 A8 后 RMSE 没有增加。

因此准确表述是：**硬件路径不是与软件 bit-identical；在入口不饱和的组上，Hadamard 不会放大 S24 Q8.16（或 down 路径 S32 Q16.16）的量化噪声；包含极少量真实 S24 饱和点的完整 PPL 实验仍显示精度维持在约 1% 增量范围。**

如果项目要求是“PPL 完全不变”或增量小于 1%，当前数据不能证明达标；如果允许约 1.1% 的相对 PPL 增量，则该路径通过本次验证。

## 2. 严格证明

令 `H` 为未归一化的 32 点 Hadamard 矩阵，`T = H/sqrt(32)`。因为：

```text
H H^T = 32 I
T T^T = I
```

所以 `T` 是正交变换。S24 Q8.16 和 S32 Q16.16 都有 16 个小数位，令其量化步长 `Delta = 2^-16`，且入口没有饱和：

```text
Q(x) = Delta * round_half_away(x / Delta)
e    = Q(x) - x
```

每个元素满足 `|e_i| <= Delta/2`，于是：

```text
||T Q(x) - T x||_2 = ||T e||_2 = ||e||_2
                    <= sqrt(32) * Delta/2
                    = 4.3158373e-5  （每个 Group32 的 L2 上界）
```

对应的组内 RMS 上界就是 `Delta/2 = 7.6293945e-6`。这证明了“先 FP→Q 再 Hadamard”不会因为 Hadamard 本身放大量化能量。

production 并非使用无限精度的 `1/sqrt(32)`，而是：

```text
c     = 11585 / 65536
alpha = c * sqrt(32) = 0.9999794995173528
|alpha - 1|          = 2.0500483e-5
```

再计入 Hadamard 输出到 16 个小数位的舍入 `r`，对每个未饱和组有：

```text
||y_rtl - T x||_2
  <= ||Q(x)-x||_2
   + |alpha-1| * ||Q(x)||_2
   + sqrt(32) * Delta/2
```

实验对每个适用组直接计算右侧上界。合成数据和真实激活的违例数均为 0。

位宽也足以容纳合法输入的最坏 Hadamard 输出：S24 Q8.16 的归一化最坏幅值小于 `sqrt(32)*128 ≈ 724.1`，低于 S27 Q11.16 的 1024 边界；S32→S35 同理。因此只要 FP→S24 入口不饱和，Hadamard 内部不会额外溢出。

## 3. bit-exact 核对

`test_fptoq_core.py` 共 7 项测试：

- Host S24 half-away 舍入和饱和边界；
- NumPy 整数 Hadamard 与 `ScaleLLM/model/fixbit_v2.py` 逐元素一致；
- NumPy MinMax A8/code/shift/zp 与 `fixbit_v2.py` 逐元素一致；
- 正交能量恒等式；
- 逐组理论界；
- Torch 模型适配器与 NumPy bit-exact 路径一致。
- Torch S32→S35 down 前端与 `ScaleLLM/model/mlp_fixed.py` 逐元素一致。

结果：`Ran 7 tests ... OK`。

## 4. 真实激活实验

模型：Qwen2.5-0.5B-Instruct，BF16，24 层。数据为 calibration `first64.jsonl` 的前 8 个非空文本，每条最多 256 token。

Q/K/V 共用同一输入，Gate/Up 也共用同一输入，因此每层只采一份代表，避免把相同张量重复三次或两次。最终得到 4 类边界各 8,192 组，共 32,768 个不重复 Group32：`q_proj`、`o_proj`、`gate_proj`、`down_proj`。

| 指标 | 结果 |
|---|---:|
| 输入范围 | `[-48.0, 41.25]` |
| S24 输入饱和 | `0 / 1,048,576` elements |
| Hadamard 输出饱和 | `0 / 1,048,576` elements |
| 输入值恰好可用 `2^-16` 网格表示 | `98.8167%` |
| FP→Q 输入 RMSE | `6.52570e-7` |
| ideal H 后仅 FP→Q 的 RMSE | `6.52570e-7` |
| 完整 RTL H 相对 FP64 H RMSE | `1.92203e-5` |
| 完整 RTL H cosine | `0.9999999999881` |
| 完整 RTL H SQNR | `93.53 dB` |
| 软件 A8 相对 FP-H RMSE | `0.0041831104` |
| 硬件 A8 相对 FP-H RMSE | `0.0041827805` |
| 硬件 A8 RMSE 相对变化 | `-0.00789%` |
| 硬件/软件 A8 输出 cosine | `0.9999998851` |
| A8 byte match rate | `99.7474%` |
| metadata group match rate | `99.4415%` |
| 硬件/软件组 RMSE 中位数 | `0` |
| 硬件/软件组 RMSE p99 | `7.13893e-4` |
| 理论界违例 | `0 / 32,768` groups |

A8 byte 或 metadata 不要求完全一致，因为一个很小的 Hadamard 扰动可能跨过 round/ScaleCode 阈值。关键结果是相对同一 FP-H gold 的总体 RMSE没有升高。

原始数据：`qwen2.5-0.5b/activation_groups.npz`、`qwen2.5-0.5b/analysis/summary.csv` 和 `summary.json`。

## 5. 完整模型 PPL A/B

WikiText2 test，block/stride 1024，最多 65,536 输入 token，64 blocks，65,472 scoring tokens。三路均为 BF16、seed 20260911、deterministic、TF32 off，且使用相同的 folded ScaleCode Attention W8 / MLP W4 weight。

| 路径 | PPL | 相对 software | token accuracy | accuracy 绝对变化 |
|---|---:|---:|---:|---:|
| software | `17.939881` | `0` | `44.4938%` | `0` |
| pre_q_only | `18.113120` | `+0.9657%` | `44.4144%` | `-0.0794 pp` |
| rtl_exact | `18.130087` | `+1.0602%` | `44.4022%` | `-0.0916 pp` |

software 的 `17.93988145780752` 与既有归档 `0_Software/results/Qwen2.5-0.5B-Instruct/ppl_wikitext2.csv` 完全一致。由此排除了“基线脚本或评测切分换了”造成的伪差异。

`pre_q_only` 隔离了 S24 Q8.16 / S32 Q16.16 输入边界；`rtl_exact` 进一步加入整数蝶形、11585 系数、末级舍入和整数 A8。RTL exact 相对 pre-Q-only 的额外 PPL 只有约 `0.0937%`，主要增量来自 FP→定点输入边界，而不是 Hadamard 蝶形本身。

完整 `rtl_exact` 运行还累计了前端审计计数：

| 硬件路径 | 元素数 | 输入范围 | 输入饱和 | Hadamard 饱和 | ScaleCode format error |
|---|---:|---:|---:|---:|---:|
| S24→S27 | `8,447,459,328` | `[-58.5, 334.0]` | `260` (`3.08e-6%`) | `0` | `0` |
| S32→S35 | `7,642,939,392` | `[-2160.0, 172.0]` | `0` | `0` | `0` |

校准 trace 没有遇到 S24 离群值，但全 WikiText2 前向发现了 260 个正向 S24 饱和点。它们只占约 3,249 万分之一的 S24 元素，因此不会改变“主体误差不被 Hadamard 放大”的判断；但严格 L2 证明不能用于这些饱和点。上表和最终 PPL 是包含这些点后的经验结果。

审计计数按软件中的逻辑 Linear 调用累计；Q/K/V 共用的输入会计三次，Gate/Up 共用的输入会计两次。production 可以共享一次前端结果。该重复不改变每条路径的数值或饱和率，但 `260` 不是去重后的物理传输个数。

原始数据：`qwen2.5-0.5b/ppl_full/*.json` 与 `comparison.csv`。

## 6. 失效边界

两个负向探针必须保留：

- `tiny_rms_2^-14`：信号幅值接近 `2^-16` 的定点步长，硬件 A8 RMSE 会明显高于软件。真实模型样本中绝大多数值不处于这个整体低幅状态，但理论上不能排除其它模型。
- `overflow_probe`：每组放入 `±160`，必然触发 S24 饱和，硬件误差显著增大。正交误差证明不适用于饱和量化。完整 WikiText2 确实出现了极少量 S24 饱和，因此不能把校准样本的零饱和外推成全 workload 零饱和。

因此部署时建议保留/暴露已有 `hadamard_saturation_count`，并在 Host 侧新增或记录 FP→S24 saturation count。若其它 workload 的 S24 饱和率显著高于本次 `3.08e-8`，应重新评估输入缩放，不能直接引用本报告的 PPL 结论。

## 7. 能证明什么、不能证明什么

可以严格证明：未饱和 S24 Q8.16 / S32 Q16.16 误差的 L2 能量不被 ideal Hadamard 放大，且 production 系数/舍入满足给定逐组上界。

本次经验上支持：Qwen2.5-0.5B 的常规真实激活误差远低于 A8 误差底噪；即使完整 workload 含 260 个稀有 S24 饱和元素，模型 PPL 增量仍约 1.06%。

不能宣称：所有 12 个模型、所有 prompt、所有生成长度都必然小于 1.06%；A8 是非线性的，端到端误差也会随模型传播。若需要论文级跨模型声明，应按同一脚本继续跑 12 模型 A/B，并预先规定允许的 PPL/ACC 增量阈值。

## 8. Llama-3.1-8B-Instruct 交叉验证

随后按完全相同的三路口径完成了 Llama-3.1-8B-Instruct、64 blocks、65,472 scoring tokens 的 WikiText2 验证：

| 路径 | PPL | 相对 software | token accuracy | accuracy 变化 |
|---|---:|---:|---:|---:|
| software | `8.761912525` | `0` | `53.27163%` | `0` |
| pre_q_only | `8.767853563` | `+0.06781%` | `53.21053%` | `-0.06109 pp` |
| rtl_exact | `8.760934559` | `-0.01116%` | `53.27621%` | `+0.00458 pp` |

全量 RTL 审计中，S24 Q8.16 路径处理 `51,489,275,904` 个元素，范围 `[-21.5, 17.75]`；S32 Q16.16 down 路径处理 `30,035,410,944` 个元素，范围 `[-560, 239]`。两路入口饱和、Hadamard 输出饱和和 ScaleCode 格式错误全部为 0。

这组结果把结论从单一小模型扩展到一个 8B 模型：Llama workload 上完整硬件前端没有可测的质量下降，而且 S24 动态范围有明显余量。但 Qwen 与 Llama 的端到端变化并不相同，因此仍应把“正交变换不放大量化误差”视为通用数学结论，把具体 PPL 变化视为逐模型实验结论。

完整 Llama 激活误差、审计和复现信息见 `results/llama3.1-8b-instruct/REPORT.md`。
