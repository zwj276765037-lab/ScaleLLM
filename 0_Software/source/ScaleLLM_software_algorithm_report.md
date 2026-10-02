# ScaleLLM 软件算法、定点边界与精度验证报告

> 文档用途：论文软件方法部分、算法复现说明与审稿问题答复底稿  
> 仓库方法标识：`mlp_w4_scalecode` / Group32 Hadamard–ScaleCode quantization  
> 文档日期：2026-09-18  
> 状态：**算法与冻结的数据位宽已通过软件精度签核（APPROVED）**。Llama-3.1-8B-Instruct Reference-QDQ、Full V5 Down-S32 与 MLP-only 最终候选均已完成全量 ACC/PPL；最终硬件候选为 `0x48384605`：Gate/Up S37/S44→S24/F16，Down `[12,44]`、S45/S54→S32/F16。真实 RTL/Host 审计仍为 4/15，硬件实现签核继续 HOLD

---

## 摘要

ScaleLLM 采用免训练的后训练量化（post-training quantization, PTQ）方案。对目标线性层，输入激活先按连续 32 个通道执行归一化 Hadamard32 变换；与之配对的权重在离线阶段完成相同基变换的 folding，从而在理想变换且无量化误差时保持线性层严格等价。Hadamard 后的激活按 token、按 Group32 使用无符号非对称 MinMax A8 量化；Attention 的 `q_proj`、`k_proj`、`v_proj`、`o_proj` 使用 W8，MLP 的 `gate_proj`、`up_proj`、`down_proj` 使用 W4。在线动态的激活 scale 与离线静态的权重 scale 均可编码为 `code × 2^-shift`；整数点积之后通过 zero-point 整数校正、code 乘法、移位对齐和跨组累加恢复各组贡献的尺度。

生产数据流还包含一个必须单独讨论的硬件边界：Host 以 FP32 完成 residual 与 RMSNorm，然后将常规激活转换成 **S24 Q8.16** 传入 FPGA；FPGA 使用整数蝶形计算 Hadamard，输出 S27 Q11.16，再重定标为 Group32 U8。MLP 的 `down_proj` 输入来自 FPGA 内部的 SwiGLU 乘积，使用更宽的 S32 Q16.16 → S35 Q19.16 路径。S24 不是最终 A8，也不能简称为“Q16 激活”：它是总宽 24 bit、含 16 个小数位的高精度定点边界格式；A8 才是后续真正用于低比特矩阵乘的动态分组表示。

必须特别澄清版本术语：**当前 HC-v2 不存在“统一 Q16.16 恢复基线”**。旧 HAP 曾把 32-bit Q16.16 作为 lane/恢复边界，并因每个 Group32 过早收窄而损失精度；当前 Linear/PV 实现已改为在 Q*.24 guard 域跨组或跨 key 累计，QK 则独立使用 Q14 score 域。最终合同中的 S32/F16 分别用于 FPGA 内部 `SiLU(Gate)×Up` 的 SwiGLU 中间乘积和 Down 的末端输出；它不是 Host ingress，也不是逐个 Group32 的 ScaleCode 恢复/累加格式。

当前仓库包含三类共享算法骨架、但证据边界不同的配置：**Reference-QDQ** 用于纯算法质量评估，**Hardware-contract v2（HC-v2）前端 A/B** 用于隔离 S24 与整数 Hadamard，**V5 production full-chain twin** 用于 Llama-3.1-8B-Instruct 的完整软件数字孪生。三者不能被描述为同一次 bit-exact 实验。本报告得到四类互不替代的结论：

1. **解析结论。** 在入口不饱和时，所有含 16 个小数位的定点格式（下文记作 Qm.16）的逐元素舍入误差不超过 `2^-17`；理想归一化 Hadamard 是正交变换，因此不会放大该误差的 L2 能量。HC-v2 系数 `11585/65536` 相对 `1/sqrt(32)` 的归一化误差为 `2.05005e-5`，必须作为 RTL 的附加确定性误差单独计入。
2. **Llama-3.1-8B-Instruct 前端结论。** WikiText2 的 64 个窗口、65,472 个计分 token 上，生产整数激活前端相对归档软件量化基线的 PPL 变化为 `-0.01116%`，应解释为数值持平。累计检查的常规 S24 逻辑元素为 `51,489,275,904`，未出现入口或 Hadamard 饱和。
3. **完整量化算法结论。** 新的 Llama-3.1-8B-Instruct 文献对齐全量实验使用 lm-eval 0.4.11、六项 zero-shot official split 和 WikiText-2 全量 2048-token block。Reference-QDQ 相对 matched BF16 的 Macro ACC 从 `75.749%` 降至 `74.969%`，变化 `-0.780 pp`；PPL 从 `7.16143` 增至 `7.57747`，相对增加 `5.809%`。归档的 12 模型共同五任务平均 ACC 变化为 `-0.927 pp`，平均相对 PPL 增加 `7.70%`。这些结果支持“算法退化有限”，但不能称完整 A8/W8/W4 算法相对 BF16 “无损”。
4. **V5 最终修复。** format-v3（`0x48384603`、Down S37/S46→S24）首先暴露 Down 末级 S24/F16 饱和；`0x48384604` 中间候选把 Down 输出改为 S32/F16，使 Full V5 WikiText-2 PPL 从 `27.639944` 恢复到 `18.555656`，相对 BF16 `17.208506` 增加 `7.828%`，六任务 Macro ACC 为 `74.6364%`，相对 BF16 `75.3853%` 下降 `0.7489 pp`，均通过阈值。MLP-only 压力测试进一步观测到 Down `total_shift_min=12..13`，因此最终 `0x48384605` 候选把 Down 合法范围扩为 `[12,44]`、group guard/448-group accumulator 扩为 S45/S54，并保持 Gate/Up S37/S44 不变。最终 MLP-only PPL 为 `18.452719`（`+7.230%`），保守六任务 Macro ACC 为 `74.6469%`（`-0.7384 pp`）；所有最终候选分片的 format、guard、accumulator、S32-output 异常计数均为 0。软件精度已通过，但真实 RTL/Host 仍未完成 `0x48384605` 迁移。

---

## 0. 2026-09-18 最终候选与版本优先级

本节优先级高于文中所有把 format-v3 `0x48384603` 称为“当前格式”、或把
`0x48384604` 称为“最终修复”的旧段落；这些段落保留为故障定位历史，不得用于
最终硬件规格。最终候选固定为：

```text
Host/RMSNorm input: S24/F16
Gate/Up: total shift [20,44], S37/F24 guard, S44/F24 accumulator,
         S24/F16 output; packed lane进入SwiGLU前按bit[23]符号扩展
SwiGLU product: S32/F16，并以真实32-bit存储
Down: total shift [12,44], S45/F24 group guard,
      S54/F24 accumulator over 448 groups, S32/F16 output
External Down tile: 8192 bit = 32 AXI256 beats; C2H = 256 KiB
Final MLP ABI: 0x48384605
```

| 指标 | BF16 | 最终候选 | 变化 | 门槛 |
|---|---:|---:|---:|---:|
| MLP-only WikiText-2 PPL | 17.208506 | 18.452719 | +7.230% | ≤10% |
| MLP-only 六任务 Macro ACC | 75.3853% | 74.6469% | -0.7384 pp | ≥-1.0 pp |
| Full V5 WikiText-2 PPL | 17.208506 | 18.555656 | +7.828% | ≤15% |
| Full V5 六任务 Macro ACC | 75.3853% | 74.6364% | -0.7489 pp | ≥-1.5 pp |

软件精度结论为 PASS。历史 `4/15 PASS` 来自仅检查 `0x48384604` 中间目标的旧审计，
不能作为当前 format-v5 的完成度。2026-09-24 Mission 0215 已更新迁移审计，
按 `0x48384605`、S45/S54/S32 和 branch-local stream256 检查，结果为
`18/18 static_contract_pass`，审计正向/负向测试 `10/10 PASS`。证据位于
`fpga_llm_project/0_fix_newdataflow_Hadamard/HAP/vivado/reports/mission0215_software_migration_audit_20260924_v2/`。
该结果仅为源码合同检查，不验证模型/reference 身份，不替代动态逐位一致性、
完整板级时序或实板签核；本次没有重跑或修改已批准的 PPL/ACC。硬件部门仍须按
`ScaleLLM/0_Software/fix_experiment/source/ScaleLLM_MLP_Down_S32_fix_handoff.md`
中的 `0x48384605` 清单完成 RTL、DMA、Host 与回归后才能签核。

### 0.1 算法与位宽精度签核结论

对 Llama-3.1-8B-Instruct 和本报告冻结的 `hardware_128` 测评口径，当前结论不再是
“看起来可能满足精度”，而是：**算法与所选数据位宽已经通过软件全量精度测试，
可以进入 RTL/Host 实现与回归阶段。** 该签核同时依赖以下条件，缺一不可：

- Host/RMSNorm 入口为 S24/F16，Gate/Up 保持 S37/F24 group guard、S44/F24
  accumulator 与 S24/F16 输出；
- packed S24 lane 在进入 SiLU/SwiGLU 前按 bit `[23]` 符号扩展，SwiGLU product
  以 signed S32/F16 存储；
- Down total shift 为 `[12,44]`，单组 guard 为 S45/F24，448 组 accumulator
  为 S54/F24，末端输出为 S32/F16；
- 候选运行中 format、guard、accumulator、SwiGLU 与末端输出饱和计数全部为 0；
- MLP-only 与 Full V5 的 PPL/ACC 均满足本节表中的预注册门槛。

这里的“通过”是软件 bit-exact 数值孪生和模型质量意义上的通过，不等价于实板已经
通过。硬件部门若改变上述任一位宽、移位范围、舍入/饱和语义或传输 ABI，必须重新
执行对应的 ACC/PPL 与异常计数验证。

## 1. 先回答四个核心审稿问题

### 1.1 S24 Q8.16 真的能维持精度吗？

对 Llama-3.1-8B-Instruct 的当前证据，答案是：**在已测试 workload 上可以；普遍结论必须带“不饱和”条件。**

- S24 的量化步长为 `2^-16 = 1.52587890625e-5`。
- round-to-nearest 的最大逐元素误差为 `2^-17 = 7.62939453125e-6`。
- 理想归一化 Hadamard 不放大这一误差的 L2 范数。
- Llama 真实激活 trace 的 RTL Hadamard RMSE 为 `7.50253e-6`，而随后 A8 量化的 RMSE 为 `1.39630e-3`；定点 Hadamard 误差约为 A8 误差的 `0.54%`。
- Llama 在固定前 65,536 个输入 token、64 个窗口的 evaluation slice 上进行前端审计，没有发现 S24、S32 或 Hadamard 饱和；硬件前端相对软件基线的 PPL 变化为 `-0.01116%`。

但如果输入超过 `[-128, 127.9999847412]`，S24 会饱和，正交误差证明随即失效。Qwen2.5-0.5B 的同口径 evaluation slice 同时观测到 260 个稀有 S24 饱和元素与约 `+1.0602%` 的相对 PPL 变化；当前 A/B 没有单独隔离这些饱和点的因果贡献。这说明结论应绑定模型、workload 与饱和计数，不能无条件跨模型外推。

### 1.2 激活已经是定点数，为什么还需要 Hadamard？

因为这里有两层用途完全不同的定点表示：

- **S24 Q8.16** 使用固定隐式步长 `2^-16`，目的是在 Host–FPGA 边界上较高精度地表示和运输激活；
- **Group32 U8** 使用每组动态 scale 和 zero-point，目的是把激活真正压缩到 8 bit 并送入低比特 MAC。

把 FP 转成 S24 只改变了数值网格，并没有消除通道离群值，也没有自动缩小每个 Group32 的 MinMax 范围。若直接将带离群值的 S24 压成 A8，一个极端通道仍会放大整组量化步长。Hadamard 位于 S24 与 A8 之间，是为了在低比特重定标前重新分配通道能量。权重侧离线 folding 保证它不改变无量化线性算子。

因此，Hadamard 的作用不是“把浮点变成定点”，而是“改善后续低比特分组量化的数值条件”。它在 S24 定点化之后仍具有独立设计动机；现有分布与局部重构实验支持这一作用，但尚无 matched no-H 端到端 PPL/ACC 消融，本文不声称 Hadamard 不可替代或在所有 workload 上都必需。

### 1.3 既然输入是定点数，后续 scale 不也应该是定点数吗？

如果“定点”是指 scale 不以 FP16/FP32 保存和计算，那么答案是肯定的；如果是指所有组共享同一个固定二进制点，则答案是否定的。HC-v2 将 scale 的 metadata 编码成整数：

~~~text
decoded_scale = scale_code × 2^(-scale_shift)

activation metadata U24 =
    {reserved2, scale_shift[5:0], scale_code[7:0], zero_point[7:0]}
~~~

`scale_code` 和 `scale_shift` 都是整数，解码值是逐组变化的二进制有理数，而不是具有统一二进制点的传统定点标量。这里“动态”指激活 scale 随每个 row、每个 Group32 在线变化；权重 scale 则按输出通道和 Group32 离线静态生成。固定的 S24 二进制小数点与这些分组 scale 可以同时存在，二者没有矛盾。

### 1.4 S24 会不会引入额外开销？

会，必须如实报告。

对一个 `16×4096` tensor：

| 表示 | 数据量 | 相对 S24 |
|---|---:|---:|
| BF16 / FP16 | 128 KiB | S24 多 50% |
| S24 Q8.16 | 192 KiB | 基准 |
| FP32 | 256 KiB | S24 少 25% |
| U8 + U24/Group32（逻辑紧密打包） | 70 KiB | S24 是其 2.7429 倍 |

此外，Host 的 pack/unpack 是 O(N) 的 NumPy 处理。当前 transfer trace 只计 DMA 时间，明确没有覆盖 pack/unpack，因此不能声称这部分开销可忽略。S24 的合理定位是：相对 Host FP32 减少传输量，并使 FPGA 直接进入整数计算；它并不比 BF16 更省带宽。

---

## 2. 方法范围与版本口径

### 2.1 目标算子

最终软件算法作用于以下线性层：

| 模块 | 激活 | 权重 | 是否量化 |
|---|---|---|---|
| `q_proj` / `k_proj` / `v_proj` / `o_proj` | A8 | W8 | 是 |
| `gate_proj` / `up_proj` / `down_proj` | A8 | W4 | 是 |
| GLM `gate_up_proj` | A8 | W4 | 是 |
| `lm_head` | 原精度 | 原精度 | 否 |

Llama-3.1-8B-Instruct 有 32 层、每层 7 个目标 Linear，共 224 个逻辑 Linear。生产硬件可以共享 Q/K/V 或 Gate/Up 的同一份激活前端结果；软件逐模块调用数不能直接解释为物理传输次数。

### 2.2 算法类型

本方法是：

- 免训练 PTQ；
- 权重离线 folding 与分组量化；
- 激活在线动态 MinMax；
- 软件质量评估采用 QDQ；
- 不进行量化感知训练；
- 不使用 percentile、MSE search、alpha search 或校准式 clipping。

RTL 模块名中的 `robust` 是历史兼容名称。当前 production 激活量化器扫描原始 Hadamard 输出的 MinMax，不在求 MinMax 前裁剪离群值。

### 2.3 三类必须分开的实现口径

当前仓库同时存在“历史软件质量基线”“硬件前端隔离实验”和“V5 production 全链路数字孪生”。前两者分别命名为 **Reference-QDQ** 与 **Hardware-contract v2（HC-v2）前端 A/B**。这里 HC-v2 是对固定点数值合同的简称，不等于当前板级 ABI 的版本号。第三类直接命名为 **V5 full-chain twin**；三类服务于不同证据，不能混成一个配置。

真实 RTL 当前仍由 Llama-3.1-8B 构建清单 `vivado/manifests/attention_mlp_production_v5_cohort16_sources.list` 描述：Attention 板级 format ID 为 `0x48384103`，MLP 仍停留在旧的 `0x48384603` 边界；这说明硬件尚未迁移，不代表本文最终软件规格仍是 format-v3。经全量精度验证后，MLP 最终目标已经冻结为 `0x48384605`。`model/fixbit_v2.py` 中的 `0x48384102` 与 MLP 的 `0x48384603/04` 均只能用于历史兼容或故障诊断，不能生成最终 v5 MLP artifact。第 9 节的旧 recovery 说明若与第 0 节冲突，一律以第 0 节和 `0x48384605` 硬件交接清单为准。

| 项目 | Reference-QDQ | Hardware-contract v2（HC-v2） |
|---|---|---|
| 主要用途 | 12 模型 ACC/PPL | FPGA 数据格式与整数执行 |
| 激活输入 | FP/BF16 | 常规 S24 Q8.16；Down 内部 S32 Q16.16 |
| Hadamard | PyTorch 浮点矩阵乘 | 整数 FWHT + `11585/65536` |
| 激活 scale | `code8 + shift8`，shift 0…255 | `code8 + shift6`，shift 0…63 |
| 激活 q 的生成 | raw MinMax scale，`torch.round` | raw integer `diff`，整数 RNE |
| 权重 q 的生成 | raw scale；QDQ 用 decoded scale | decoded ScaleCode scale |
| 权重舍入 | `torch.round`，ties-to-even | half-away-from-zero |
| W8 负范围 | `[-128,127]` | `[-127,127]` |
| W4 范围 | `[-8,7]` | `[-8,7]` |
| 线性计算 | 反量化权重与激活后 `F.linear` | U8×S8/S4 整数点积与移位恢复 |
| 能支持的结论 | 算法级模型质量 | 格式、前端和模块级硬件一致性 |

V5 full-chain twin 在 HC-v2 格式基础上进一步覆盖 production 权重 Hadamard folding、W8/W4 bytes 与 ScaleCode、整数 Linear recovery、定点 RoPE、KV12、QK、定点 Softmax、PV、定点 SiLU×Up，以及 Host FP32 residual/RMSNorm；`lm_head` 保持 Host FP32。最终 MLP 数值合同为 Gate/Up S37/S44→S24/F16、SwiGLU S32/F16、Down `[12,44]` 和 S45/S54→S32/F16。它受真实 V5 的 128-key 上限约束。该实现是软件数字孪生，不是实板 bitstream 测量。

因此论文结果必须分别标注：12 模型 ACC/PPL 支撑的是 Reference-QDQ；Llama/Qwen S24 A/B 支撑的是 HC-v2 激活前端；第 15.4 节旧结果只支撑 format-v2/v3 故障诊断；最终硬件对齐精度结论由 `0x48384605` 的 matched `hardware_128` 全量 ACC/PPL、逐节点审计和零异常计数支撑。不能沿用旧故障结果，也不能把前端“数值持平”单独外推为全链路结论。

---

## 3. 符号、分组与数值格式

### 3.1 符号

| 符号 | 含义 |
|---|---|
| `x` | 一行线性层输入激活 |
| `W` | PyTorch 布局的权重，形状 `[out_features, in_features]` |
| `H_32` | 未归一化 Sylvester Hadamard32 |
| `T = H_32 / sqrt(32)` | 归一化、正交的 32×32 变换 |
| `x_h` | Hadamard 后激活 |
| `W_h` | Hadamard-folded 权重 |
| `g` | 连续 32 个输入通道构成的组 |
| `q_a, z_a` | U8 激活码与激活 zero-point |
| `q_w` | S8 或 S4 权重码 |
| `s_a, s_w` | 激活与权重的理想 scale |
| `c_a, r_a` | 激活 ScaleCode 的 code 与 shift |
| `c_w, r_w` | 权重 ScaleCode 的 code 与 shift |
| `s_hat` | ScaleCode 解码值 `c × 2^-r` |

Hadamard block 与量化 group size 均为 32，且沿线性层输入维/激活最后一维分组。Llama 的 hidden size 4096 对应每行 128 组，intermediate size 14336 对应每行 448 组。

### 3.2 Q 格式命名约定

本仓库采用 `Q整数域总位数.小数位数` 的写法，其中整数域包含符号位。因此：

- S24 Q8.16：1 个符号位、7 个数值整数位、16 个小数位；
- S27 Q11.16：1 个符号位、10 个数值整数位、16 个小数位；
- S32 Q16.16：1 个符号位、15 个数值整数位、16 个小数位；
- S35 Q19.16：1 个符号位、18 个数值整数位、16 个小数位；
- S36 Q12.24：1 个符号位、11 个数值整数位、24 个小数位（PV term）；
- S37 Q13.24：1 个符号位、12 个数值整数位、24 个小数位（format-v3 MLP guard）；
- S42 Q18.24：1 个符号位、17 个数值整数位、24 个小数位；
- S43 Q19.24：1 个符号位、18 个数值整数位、24 个小数位；
- S44 Q20.24：1 个符号位、19 个数值整数位、24 个小数位；
- S46 Q22.24：1 个符号位、21 个数值整数位、24 个小数位；
- S20 Q6.14：1 个符号位、5 个数值整数位、14 个小数位。

有些文献会把同一个 S24 布局写成 sQ7.16；本文为避免与 RTL/软件仓库冲突，始终使用 **S24 Q8.16**。单独写“Q16”只说明不了总位宽和整数范围，应避免。

QK 路径的 RTL 信号名 `group_q14_s35` 表示“35-bit 容器、14 个小数位”。按本文命名约定，它应写成 **S35 Q21.14**，而不是 S35 Q6.14；只有最终 20-bit score 才是 S20 Q6.14。

### 3.3 数值格式表

| 阶段 | 格式 | 实数范围/语义 |
|---|---|---|
| Host RMSNorm / residual | FP32 | Host 高精度计算 |
| 常规 FPGA 入口与输出 | S24 Q8.16 | `[-128, 127.9999847412]`，步长 `2^-16` |
| 常规 Hadamard 输出 | S27 Q11.16 | `[-1024, 1023.9999847412]` |
| SwiGLU/Down 内部入口 | S32 Q16.16 | `[-32768, 32767.9999847412]` |
| Down Hadamard 输出 | S35 Q19.16 | `[-262144, 262143.9999847412]` |
| 在线激活 | U8 | 每 row、每 Group32 动态 scale 与 zero-point |
| Attention 权重 | S8 | production `[-127,127]` |
| MLP 权重 | S4 | `[-8,7]` |
| 激活 metadata | U24 | `reserved2 + shift6 + code8 + zp8` |
| Linear 权重 metadata | U16 | `reserved2 + shift6 + code8`，每 output channel、每 Group32 一份 |
| Attention Linear group/accumulator | S42 Q18.24 | Q/K/V/O，128 个 Group32 内积恢复 |
| MLP Linear group guard | S37 Q13.24 | format-v3 Gate/Up/Down 共用的单组恢复输出 |
| Gate/Up accumulator | S44 Q20.24 | 128 个 Group32 累加 |
| Down accumulator | S46 Q22.24 | 448 个 Group32 累加 |
| K/V cache | S12 + U16 metadata | S12 合法码 `[-2047,2047]`；`-2048` 保留；meta=`reserved2+shift6+code8` |
| QK group score | S35 Q21.14 | 每个 head 的单个 Group32，14 个小数位 |
| QK four-group accumulator | S37 Q23.14 | 4 个 Group32 累加后 clip |
| Attention score | S20 Q6.14 | clip 到 `[-16,+16]` |
| Softmax probability | U16 U0.16 | PV 的概率输入 |
| PV term/accumulator | S36 Q12.24 / S43 Q19.24 | 逐 key 恢复 V scale，最多 128 key 累加 |

### 3.4 S32 Q16.16 位宽自查：它存在，但不是统一入口

当前 RTL 的 `hap_mlp_silu_mul` 确实把 S24 Gate/Up 的乘积输出声明为 S32 Q16.16，因此不能声称生产硬件已经把这一路缩窄。然而，这个 S32 是 Down projection 前的 FPGA 内部保守容器，不经过 Host–FPGA 传输，也不参与 Attention、QKV、O 或 Gate/Up 的常规 S24 ingress。

对所有合法 S24 Gate/Up 输入可以给出一个比 S32 更紧的解析界。当前 SiLU 实现对 `gate>=16` 直接输出 gate，对 `gate<=-16` 输出 0，中间区间查表；结合 `gate,up in [-128,128)`，SwiGLU 乘积严格落在 `[-16384,16384)` 内。因此保留 16 个小数位时，**S31 Q15.16 已足以覆盖合法输入的格式级最坏情况**，S32 Q16.16 至少多 1 个整数位。

真实 workload 的范围更窄，但只构成经验上界：

| 模型与 evaluation slice | 观测 S32 乘积范围 | 保持 16 个小数位所需的最小有符号容器 | 相对当前 S32 |
|---|---:|---:|---:|
| Llama-3.1-8B-Instruct，WikiText2 64 windows | `[-560,239]` | S27 Q11.16 | 少 5 bit |
| Qwen2.5-0.5B，同口径 64 windows | `[-2160,172]` | S29 Q13.16 | 少 3 bit |

所以“Q16.16 有较大浪费”对 workload trace 是成立的；但若要求对任意合法 S24 输入给出无条件证明，目前只能安全主张可从 S32 缩到 S31。本文不建议把 S27/S29 直接写成通用硬件合同，也不把保守整数位误称为精度需求。若未来优化该内部通路，应先做多模型、多数据集和长上下文的范围 sweep，再以饱和遥测或解析界签核；本报告的当前实验仍按实际生产 RTL 的 S32 执行。

---

## 4. 端到端数据流与 Host–FPGA 分工

### 4.1 层级 Host–FPGA 闭环

一个 Transformer 层不是“每个 Linear 都由 Host RMSNorm 后传入”。当前 partition 只在 Attention 与 MLP 两个子层边界往返 Host；层内共有四类线性层入口：

~~~text
Host FP32 residual
→ input_layernorm
→ H2C S24
→ [S24 H/A8] → Q/K/V
→ Attention / RoPE / Softmax / context
→ [S24 H/A8] → O
→ C2H S24
→ Host residual add + post_attention_layernorm
→ H2C S24
→ [S24 H/A8] → Gate/Up
→ fixed SiLU × Up
→ [S32 H/A8] → Down
→ C2H S24
→ Host residual add
~~~

其中方括号表示“定点 Hadamard + Group32 MinMax A8 + U24 metadata”前端；真正进入矩阵乘的是 U8 激活及整数 metadata，而不是 S24/S32 本身。

### 4.2 四类线性层入口

| 数据流 | 前端来源 | H 输入→输出 | 后续投影 | 当前范围证据 |
|---|---|---|---|---|
| RMSNorm→QKV | Host `input_layernorm` 输出 | S24 Q8.16→S27 Q11.16 | W8 Q/K/V | checkpoint gamma 解析界 + workload 审计 |
| Attention context→O | FPGA 内部 attention context | S24 Q8.16→S27 Q11.16 | W8 O | workload trace；不属于 RMSNorm 解析界 |
| RMSNorm→Gate/Up | Host `post_attention_layernorm` 输出 | S24 Q8.16→S27 Q11.16 | W4 Gate/Up | checkpoint gamma 解析界 + workload 审计 |
| SwiGLU→Down | FPGA 内部 `SiLU(Gate)×Up` | S32 Q16.16→S35 Q19.16 | W4 Down | S32→S35 容器界 + workload trace |

三条常规路径共用 S24→S27 前端，但只有 QKV 与 Gate/Up 的 Host RMSNorm ingress 能直接使用第 11.5 节的 gamma 解析范围证明。`o_proj` context 必须依赖独立范围分析或运行时饱和遥测。`down_proj` 也不是 Host 传入的 S24，而是更宽的 FPGA 内部 S32 路径。因此，“所有激活都以 S24 进入 Hadamard”并不准确。

### 4.3 单个前端的整数操作与术语

对前三类 S24 路径，一个前端执行：

~~~text
S24 Q8.16 raw integer
→ five-stage FWHT32
→ ×11585, round-half-away, >>16
→ S27 Q11.16
→ Group32 raw MinMax
→ 32×U8 + U24 metadata
→ A8W8/A8W4 integer dot
→ ScaleCode code multiply + shift alignment
→ cross-group accumulation
→ round/saturate to the contracted output format
~~~

Down 路径的运算结构相同，但入口/变换输出分别替换为 S32 Q16.16 与 S35 Q19.16。

- FP32/BF16 → S24：边界定点化或格式转换；
- S27/S35 → U8：分组重定标量化（requantization）；
- U8×S8/S4 后的 code/shift：尺度应用或定点 rescaling；
- 只有软件 QDQ 为了调用 `F.linear` 才显式构造反量化浮点张量。

所以不应写“进入 FPGA 后做 Hadamard 和反量化”。更准确的表达是“进入 FPGA 后做整数 Hadamard、在线 A8 重定标量化和整数尺度恢复”。

---

## 5. Group32 Hadamard 与权重 Folding

### 5.1 归一化 Hadamard

Sylvester Hadamard 满足：

~~~text
H_32 H_32^T = 32 I
T = H_32 / sqrt(32)
T T^T = I
~~~

对一行激活的每个 32 维块执行右乘：

~~~text
x_h = x T
~~~

实际软件将多个 `T` 放在输入维的块对角线上。HC-v2 RTL 用五级 fast Walsh–Hadamard transform（FWHT）实现，跨度依次为 1、2、4、8、16，不需要通用乘法矩阵。需要注意，RTL 的归一化常量不是无限精度的 `1/sqrt(32)`，所以其实际变换为：

~~~text
T_tilde = (11585 / 65536) H_32
        = alpha T
alpha   = 0.999979499517353
~~~

因此后文凡写 `T` 的正交性与严格 folding 等价性，默认指理想 Reference-QDQ 变换；HC-v2 的 `T_tilde` 偏差另行计入。

### 5.2 线性层等价性

对原始权重 `W`，离线构造：

~~~text
W_h = W T
~~~

则：

~~~text
x_h W_h^T
= (x T) (W T)^T
= x T T^T W^T
= x W^T
~~~

若原 Linear 含 bias `b`，则 bias 不参与 folding，等式两侧同时加上同一个 `b`：

~~~text
x_h W_h^T + b = x W^T + b
~~~

因此，**对激活和权重均使用理想 `T` 时，在无限精度、无量化条件下插入 Hadamard 不改变线性层输出**。运行时不需要再做一次逆 Hadamard：逆变换已经吸收到 folded weight 中；bias 保持原值即可。不过，当前 HC-v2 的 Llama 整数 kernel 以目标投影无 bias 为合同，带 bias 模型仍需定义 bias 的定点编码与累加对齐，不能只凭上述代数等式视为硬件已经支持。

当前 exporter 按理想 `T` folding 权重，而 HC-v2 激活使用 `T_tilde=alpha T`。即使暂时关闭 A8/W8/W4 量化和所有舍入，也有：

~~~text
(x T_tilde)(W T)^T = alpha x W^T
~~~

所以严格线性等价只属于理想参考算法；HC-v2 还包含相对幅度为 `|alpha-1|=2.05005e-5` 的确定性归一化偏差。该偏差很小且已进入第 11.3 节误差界和前端 A/B，但不能称为逐 bit 等价。

该等价性还有三个实现边界：

1. 它是数学等价，不等于 BF16 计算逐 bit 相同；
2. 软件 folding 在 FP32 中生成后通常保存为计算 dtype，仍有舍入；
3. 当前 HC-v2 只支持完整 Group32；Reference-QDQ 对不足 32 的 Hadamard 尾部保持 identity，并在权重量化时补零后裁掉。目标 Llama 维度均为 32 的整数倍。

### 5.3 为什么是 block-32

Group32 同时决定：

- Hadamard 的旋转粒度；
- 激活 MinMax 的共享范围；
- 权重 scale 的共享范围；
- 整数点积的归约长度；
- metadata 的摊销粒度。

选择 32 后，变换复杂度为每组 5 级蝶形，每级产生 32 个加/减输出；scale 与 zero-point 的 metadata 则由 32 个激活共同分摊。

---

## 6. 在线激活 A8：无符号非对称 MinMax

### 6.1 浮点算法定义

对 Hadamard 后的一组 `x_h,g`，先强制动态范围包含 0：

~~~text
l_g = min(min_i x_h,g,i, 0)
u_g = max(max_i x_h,g,i, 0)
s_a,g = max((u_g - l_g) / 255, epsilon)
z_a,g = clamp(round(-l_g / s_a,g), 0, 255)
q_a,g,i = clamp(round(x_h,g,i / s_a,g + z_a,g), 0, 255)
~~~

QDQ 软件重构为：

~~~text
x_hat_h,g,i = (q_a,g,i - z_a,g) × s_hat_a,g
~~~

其中 `s_hat_a,g` 是 ScaleCode 解码值。当前最终方法没有 percentile clipping、MSE clipping 或 alpha clipping。整数码的 `clamp(0,255)` 只是输出域饱和，不是求 MinMax 前删除离群值。

### 6.2 production 的整数等价式

令 Hadamard 后、含 16 个小数位的定点 raw integer 为 `X_i`，并定义：

~~~text
L = min(min_i X_i, 0)
U = max(max_i X_i, 0)
D = U - L
~~~

物理实数的理想 scale 是：

~~~text
s_a = D / (255 × 65536)
~~~

当 `D > 0` 时：

~~~text
z_a = RNE((-L × 255) / D)

N_i = X_i × 255 + z_a × D
N_i_bounded = clamp(N_i, 0, 255 × D)

q_a,i = RNE(N_i_bounded / D)
~~~

其中 RNE 表示 round-to-nearest, ties-to-even。可以看到，U8 的生成直接使用原始整数 `D`，不需要先把 scale 转成浮点，也不依赖 ScaleCode 的近似值。ScaleCode 只用于点积后的尺度恢复。

当 `D = 0` 时，RTL 输出全零 U8 与全零 metadata。这与归档 QDQ 用极小 `epsilon` 防除零的实现形式不同，但全零组的数值输出相同。

### 6.3 激活伪代码

~~~text
Algorithm OnlineActivationFrontend(x_fp_or_fixed):

for each row:
    for each consecutive Group32:
        X = fixed_Qm_16_raw(group)

        B = FWHT32_integer(X)
        Y = round_half_away(B × 11585 / 2^16)
        Y = saturate_to_S27_or_S35(Y)

        L = min(0, min(Y))
        U = max(0, max(Y))
        D = U - L

        if D == 0:
            emit q[0:31] = 0
            emit meta = 0
            continue

        (code, shift) = EncodeActivationScaleFromDiff(D)
        zp = RNE((-L × 255) / D)

        for i in 0..31:
            numerator = clamp(Y[i] × 255 + zp × D, 0, 255 × D)
            q[i] = RNE(numerator / D)

        emit q[0:31]
        emit {reserved2=0, shift6, code8, zp8}
~~~

---

## 7. 离线 W8/W4 权重量化

### 7.1 分组方式

权重先执行 Hadamard folding，再按：

- 每个输出通道独立；
- 沿输入维每连续 32 个元素一组；

进行 zero-point=0、基于 max-abs scale 的 signed 量化。对 bit width `b`：

~~~text
qmax = 2^(b-1) - 1
s_w = max_i |W_h,g,i| / qmax
~~~

Attention 使用 `b=8`、`qmax=127`；MLP 使用 `b=4`、`qmax=7`。权重 zero-point 固定为 0。需要注意，W4 整数码域为 `[-8,7]`，严格说并非关于零完全对称；“max-abs”描述的是 scale 的生成方式。

### 7.2 归档 QDQ 公式

归档质量实验执行：

~~~text
(code_w, shift_w, s_hat_w) = EncodeScale(s_w)

q_w = clamp(round(W_h / s_w), -qmax-1, qmax)
W_hat_h = q_w × s_hat_w
~~~

因此 q 使用编码前的 raw MinMax scale，QDQ 恢复使用编码后的 scale。对应范围为 W8 `[-128,127]`、W4 `[-8,7]`。

### 7.3 production artifact 公式

当前 Llama production exporter 执行：

~~~text
(code_w, shift_w, s_hat_w) = EncodeScaleShift6(s_w)

W8 qmin = -127
W4 qmin = -8

q_w = clamp(round_half_away(W_h / s_hat_w), qmin, qmax)
~~~

production 用 decoded scale 直接生成权重码，并采用 half-away-from-zero。这个差异虽小，却意味着归档 QDQ 的 12 模型结果不能被称为 production weight bytes 的 bit-exact 质量结果。

### 7.4 离线伪代码

~~~text
Algorithm FoldAndQuantizeWeight(W, bits):

T = block_diag(H32/sqrt(32), ...)
W_h = W × T

qmax = 127 if bits == 8 else 7
qmin = -127 if bits == 8 else -8

for each output channel o:
    for each input Group32 g:
        amax = max_abs(W_h[o,g])

        if amax == 0:
            q_w[o,g,:] = 0
            store {code8=0, shift6=0}
            continue

        s_raw = amax / qmax
        (code, shift) = EncodeScaleShift6(s_raw)
        s_dec = code × 2^(-shift)

        for i in 0..31:
            q_w[o,g,i] =
                clamp(round_half_away(W_h[o,g,i] / s_dec),
                      qmin, qmax)

        store q_w[o,g,:]
        store {code8, shift6}
~~~

Reference-QDQ 的全零权重组处理形式不同：它把 raw weight scale 下限钳为 `1e-12`，因此 metadata 概念上未必是零码，但 `q_w=0`，最终重构值仍为零。

---

## 8. ScaleCode：分组 scale 的整数 metadata 编码

### 8.1 定义

对正 scale `s`：

~~~text
s_hat = code × 2^(-shift)
code ∈ [1,255]
~~~

零组约定 `code=0, shift=0`。

`code` 与 `shift` 是纯整数 metadata；其解码值是二进制有理数。不同组可以使用不同 `shift`，所以 ScaleCode 不是“所有 scale 共用固定二进制点”的传统定点格式。

归档软件使用：

~~~text
shift = clamp(floor(log2(255 / s)), 0, 255)
code  = clamp(round(s × 2^shift), 0, 255)
~~~

production 使用 6-bit shift，并针对激活直接从整数 `diff` 生成 code/shift。

### 8.2 shift 位数与可编码幅度必须分开

对非零 Qm.16 raw 动态范围，`D` 是正整数且 `D >= 1`。HC-v2 扫描条件为：

~~~text
while shift < 63
  and (D << (shift + 1)) <= 255 × (255 << 16):
    shift += 1
~~~

右侧常数为 `4,261,478,400 < 2^32`。最小非零 `D=1` 时最大 shift 为 31，因此 6-bit shift 足以覆盖含 16 个小数位输入的最小非零分辨率；RTL 的 0…63 接口范围在“小 scale 端”是充足的。

但指数位数充足不等于任意大动态范围都可编码。`code8×2^-shift6` 在 `shift>=0` 时最大解码值为 255。对 S27 输入量化器：

~~~text
D_max,S27 = 2^27 - 1
s_max,S27 = D_max,S27 / (255 × 2^16)
           = 8.031372489...
~~~

因此 S27 的完整格式范围可编码。对 S35 输入量化器则有：

~~~text
D_max,S35 = 2^35 - 1
s_max,S35 = 2056.031372489...
~~~

这超过 ScaleCode 可表示幅度。考虑 RNE 后，S35 RTL 允许 `D <= 4,269,834,239`；超过该 raw threshold 会递增 `format_error_count`。所以 S35/Down 的可编码性必须由 workload 审计确认，不能仅由 shift6 的位数解析保证。

这也不自动证明所有**离线权重** shift 都小于 64。HC-v2 exporter 会显式检查 weight shift ≤63；Reference-QDQ 的 12 模型 shift8 结果若要完整迁移为 HC-v2 格式，仍需对所有模型的权重 metadata 做单独审计。

### 8.3 正常编码区间的误差

若 shift 未触及上下界，令 `m = s × 2^shift`。最大化 shift 后通常有：

~~~text
127.5 < m <= 255
code = round(m)
~~~

于是：

~~~text
|s_hat - s| <= 0.5 × 2^(-shift)
|s_hat - s| / s < 1 / 255 ≈ 0.39216%
~~~

这个界只适用于未发生 code clamp、shift cap 或 format error 的正常编码组。Llama 前端全量审计的 `scale_format_error` 为 0；Qwen 前端审计也为 0。Hadamard fullscan 中，scale 的数值范围明显下降，但 ScaleCode 的相对编码误差并未同步显著下降，因为 code 的有效尾数区间和 metadata 大小基本固定。

### 8.4 三种 scale 必须区分

| 名称 | 是否动态 | 作用 |
|---|---|---|
| S24/S27/S32/S35 的隐式 scale `2^-16` | 否 | 定义定点 raw integer 的物理单位 |
| 激活 `s_a(row,group)` | 是 | 把当前 Hadamard 激活组映射到 U8 |
| 权重 `s_w(out,group)` | 离线静态 | 把 folded weight 组映射到 S8/S4 |

“输入已经是定点数”只说明第一项固定，不能推出后两项也应为全局常数。

---

## 9. 按 Llama-3.1-8B V5 RTL 匹配的整数尺度恢复

本节只描述当前正式构建清单实际选中的恢复路径，不再把不同模块笼统合并为一个“Q16.16 recovery”。正式硬件中至少有三类数值结构：Linear 同时应用 activation/weight 两个 ScaleCode，QK 只应用 K-cache ScaleCode 并叠加 head scale，PV 则把 V-cache ScaleCode 与 U0.16 probability 合并应用。三者的点积宽度、对齐小数位和最终边界均不同。

### 9.1 五条生产恢复路径总表

对 Linear 路径，一个 Group32 的公共数学式为：

~~~text
corr_o,g = sum_i ((q_a,g,i - z_a,g) × q_w,o,g,i)
s_a,g    ≈ c_a,g × 2^(-r_a,g)
s_w,o,g  ≈ c_w,o,g × 2^(-r_w,o,g)
raw_o,g  = corr_o,g × c_a,g × c_w,o,g
t_o,g    = r_a,g + r_w,o,g
~~~

但只有前三行使用这个双 ScaleCode 公式。当前 Llama-3.1-8B V5 的完整恢复格式如下：

| 生产路径 | 归约长度 | 点积/前级结果 | code 后 raw | 对齐后的单项/单组格式 | 累加格式 | 最终边界 |
|---|---:|---|---|---|---|---|
| Q/K/V/O A8W8 Linear | 32，随后 128 groups | S21 `corr` | S37 | S42 Q18.24 | S42 Q18.24，128 groups | S24 Q8.16 |
| Gate/Up A8W4 Linear | 32，随后 128 groups | S17 `dot` | S33 | S37 Q13.24 | S44 Q20.24，128 groups | S24 Q8.16 |
| Down A8W4 Linear | 32，随后 448 groups | S17 `dot` | S33 | S37 Q13.24 | S46 Q22.24，448 groups | S24 Q8.16 |
| QK score | 32，随后 4 head groups | S40 `dot` | S48 `dot×K_code`，再到 S61 `×5793` | S35 Q21.14 | S37 Q23.14，4 groups | clip 到 S20 Q6.14 `[-16,+16]` |
| PV context | 1 key，随后最多 128 keys | S20 `V_code×V_scale_code` | S36 `×probability` | S36 Q12.24 | S43 Q19.24，最多 128 keys | S24 Q8.16 |

表中的 S42/S37 是 Linear 单组对齐结果，PV 仍使用 S36 单 key term；S42/S44/S46/S43/S37 是跨组或跨 key 状态。除了明确列出的末级 saturation/score clip，生产 RTL 不在每组恢复后饱和。旧 HAP 的 32-bit Q16.16 group recovery boundary 不属于该构建。

### 9.2 Attention Q/K/V/O：S16→S21→S37→S42→S24

Q、K、V 和 O projection 共用 A8W8 recovery lane。每个 Linear 输入维为 4096，所以每个输出元素累加 128 个 Group32。RTL 逐级格式为：

| 阶段 | RTL 数据格式 | 精确语义 |
|---|---|---|
| activation centering | S9 | `a_i = U8(q_a,i) - U8(z_a)`，范围 `[-255,255]` |
| 单 lane 乘积 | S16 | `p_i=a_i×w_i`；虽然通用 S9×S8 可写成 S17，合法范围的实际乘积严格落在 S16 |
| 2/4/8/16 项 reduction | S17/S18/S19/S20 | 两个 16-lane half 分别归约 |
| 32 项相关和 | S21 | 两个 S20 half 相加得到 `corr_s21` |
| code product | U16 | `cprod=c_a×c_w`，两个输入均为 U8 |
| scale raw | S37 | `raw_s37=corr_s21×cprod` |
| total shift | U7 | `t=r_a+r_w`；非零组必须满足 `26<=t<=47` |
| 单组 guard | S42 Q18.24 | `guard=sign_extend_S42(raw_s37) >>> (t-24)` |
| 128-group accumulator | S42 Q18.24 | 每组直接相加；加法使用 S43 临时结果检查溢出，状态仍保存为 S42 |
| finalize 临时量 | S43，16 fractional bits | 对 S42 加减 `128` 后右移 8，实现 exact-half-away-from-zero |
| projection output | S24 Q8.16 | 最后一次 saturation；Q/K/V/O 四类投影一致 |

Attention 的合法 `t` 总是不小于 26，因此这里只有 2…23 bit 的算术右移，没有左移分支。算术右移采用二补码 `>>>`，对负数等价于向负无穷取整，不是 RNE。零 code 组要求对应 shift 为 0；因为 `raw=0`，RTL 直接输出零 guard，不执行无意义移位。

软件必须按 RTL 的 reduction tree 检查每一级宽度，不能只用一个无限精度 `sum()` 后直接转换成 S21。对应的软件整数式为：

~~~text
p_s16[0:31]
→ pairwise S17 → S18 → S19 → S20
→ add two halves as S21
→ multiply U16 code_product as S37
→ arithmetic_shift to S42 Q18.24
→ accumulate 128 groups in S42 Q18.24
→ round_half_away(acc, 8), saturate S24 Q8.16
~~~

### 9.3 MLP Gate/Up/Down：S12→S17→S33→S37→S44/S46→S24

Gate、Up 与 Down 共用同一 A8W4 packed-dot 和 ScaleCode recovery leaf，所以在单组 S37 之前完全相同。RTL 的逐级格式为：

| 阶段 | RTL 数据格式 | 精确语义 |
|---|---|---|
| activation centering | S9 | `a_i=U8(q_a,i)-U8(z_a)`，范围 `[-255,255]` |
| packed DSP 内部乘积 | S25 | S9×packed-S16，仅用于一次 DSP 同算两列，不是一个模型张量格式 |
| 每列单 lane 乘积 | S12 | 精确恢复 `a_i×w4_i`，合法 W4 为 `[-8,7]` |
| 2/4/8/16/32 项 reduction | S13/S14/S15/S16/S17 | 最终每列一个 S17 dot |
| code product | U16 | `cprod=c_a×c_w` |
| scale raw | S33 | `raw_s33=dot_s17×cprod` |
| total shift | U7 | `t=r_a+r_w`；非零组必须满足 `20<=t<=44` |
| 单组 guard | S37 Q13.24 | `t<24` 时左移 `24-t`；否则算术右移 `t-24` |

单组之后才按投影类型分叉：

| 投影 | 输入维/groups | accumulator | 加法检查临时宽度 | finalize 临时宽度 | 输出 |
|---|---:|---|---|---|---|
| Gate | 4096/128 | S44 Q20.24 | S45 | S45 | S24 Q8.16 |
| Up | 4096/128 | S44 Q20.24 | S45 | S45 | S24 Q8.16 |
| Down | 14336/448 | S46 Q22.24 | S47 | S47 扩展、S46 rounded value | S24 Q8.16 |

Gate/Up 的 S44 与 Down 的 S46 不是精度模式选择，而是由 128 与 448 个输入 group 的累加深度分别冻结。两者都只在完整输出元素累加结束后执行一次 `round_half_away(acc,8)` 和 S24 saturation。若合法 `t<24`，S37 guard 的左移是精确的；若 `t>24`，算术右移会产生小于 `2^-24` 的单组截断误差。

MLP RTL 对非法非零 `t` 置 error，并把该组对齐结果置零。软件 golden 应把这种情况作为格式违约直接失败，不能把“置零后继续”当成正常量化语义。

### 9.4 KV12 metadata：不是先恢复到 S24 再计算

K/V projection 的 S24 Q8.16 输出按 Group32 对称量化到 cache：

~~~text
q_kv ∈ [-2047,2047] stored as S12
-2048 is reserved and illegal
meta16 = {reserved2=0, shift6, code8}
s_kv ≈ code8 × 2^(-shift6)
nonzero shift6 ∈ [8,32]
~~~

生产路径不存在一个公共的 “S12×scale→S24” 反量化步骤。K cache 的 scale 直接并入 QK score 的 S61→S35 对齐；V cache 的 scale 直接并入 probability×V 的 S36→S43 对齐。软件若先把 K/V 恢复成 FP32 或 S24 再做 QK/PV，数学上可以近似对应，但舍入位置和位宽不会与 RTL bit-exact。

### 9.5 QK score：S35 Q21.14 与 S20 Q6.14 必须区分

Llama-3.1-8B 每个 attention head 维度为 128，即四个 Group32。Q 保持 S24 Q8.16，K 从 KV cache 读取 S12 与 meta16。每个 group 的硬件链为：

| 阶段 | RTL 数据格式 | 运算 |
|---|---|---|
| Q×K 单 lane | S35 | DSP 内部先形成 S36；因 K 的 `-2048` 被保留禁用，合法乘积可精确保存为 S35 |
| 2/4/8/16/32 项 reduction | S36/S37/S38/S39/S40 | 得到 `dot_s40` |
| 应用 K code | S48 | `coded_s48=dot_s40×U8(key_code)` |
| 应用 head scale | S61 | `scaled_s61=coded_s48×5793`，其中 `5793/2^16≈1/sqrt(128)` |
| group 对齐 | S35 Q21.14 | `group_q14=scaled_s61 >>> (key_shift+18)` |
| 四组累加 | S37 Q23.14 | 4 个 S35 group 相加 |
| score 边界 | S20 Q6.14 | 不再舍入，直接 clip 到 `[-16,+16]`；mask 独立保存 |

`key_shift+18` 来自三个比例：Q 的隐式 `2^-16`、head scale 的 `2^-16` 和目标 score 的 `2^14`。因此：

~~~text
score_group_q14_raw
  = (dot_s40 × key_code × 5793)
      >>> (key_shift + 16 + 16 - 14)
  = scaled_s61 >>> (key_shift + 18)
~~~

该右移同样是算术截断，不是 round-to-nearest。RTL 名称 `group_q14_s35` 只是在说明小数位为 14；按本文 Q 命名法应写成 S35 Q21.14。若把它误写成 S35 Q6.14，会得到总位数不自洽的格式。

### 9.6 PV context：S20→S36 Q12.24→S43 Q19.24→S24

Softmax 输出概率为 U16 U0.16。对每个 key、每个 V lane，RTL 把 V-cache scale 与 probability 合并恢复：

~~~text
vcode_s20 = S12(v_q) × U8(v_code)
raw_s36   = vcode_s20 × U16(probability)
term_s36  = raw_s36 >>> (v_shift - 8)
acc_s43   = sum_over_valid_keys(term_s36)
context   = saturate_S24(round_half_away(acc_s43, 8))
~~~

因为 `v_q×v_code×probability` 的物理比例是 `2^(-(v_shift+16))`，对齐到 24 个小数位需要乘 `2^(24-v_shift-16)=2^(8-v_shift)`，也就是右移 `v_shift-8`。非零 V shift 的合法范围是 8…32，因此 PV 不需要左移。`term_s36` 是 S36 Q12.24，最多 128 个 key 累加在 S43 Q19.24；末级使用 S44 临时量完成 half-away 舍入，再饱和成 context S24 Q8.16。

PV 的 S43 与 Gate/Up 的 S43 位宽和二进制点相同，但数据含义不同：前者按 key 累加 probability×V，后者按输入 Group32 累加 A8W4 Linear 贡献。软件实现不能因为格式名相同就复用错误的 scale 公式。

### 9.7 软件 bit-exact 匹配规则

软件参考应把上面的位宽作为运算合同，而不只是输出注释：

1. 每一级乘积和 reduction 都先用扩展整数计算，再检查能否装入表中指定的 S/U 位宽。验证模式下应记录 overflow；对论文 golden 应直接拒绝非法输入。
2. Python 对有符号整数的 `>>` 与 RTL arithmetic `>>>` 一致，负数向负无穷取整。不要在 group alignment 前加 half LSB。
3. 只有 Hadamard 归一化、SwiGLU 的 S48 Q16.32→S32 Q16.16 和 Q*.24→S24 finalize 使用 round-half-away；A8/ScaleCode divider 使用 ties-to-even；QK group 与 PV term 的 scale shift 都是直接算术右移。
4. 中间 group guard 不饱和。RTL 在 accumulator 加法中用多 1 bit 临时量检测溢出，然后保存固定位宽二补码状态。有效 artifact 必须保证 overflow telemetry 为零。
5. Linear 零 code、KV 零 code、保留位、合法 shift 区间以及 KV `-2048` 保留码都必须逐项检查，不能只比较最终浮点张量。
6. 当前未迁移板级 artifact 仍写 Attention format ID `0x48384103` 和旧 MLP ID `0x48384603`；最终 MLP artifact 必须在 RTL/Host 同步迁移后写 `0x48384605`。数值测试代码中的历史 `0x48384102` 以及 MLP `0x48384603/04` 都不能替代最终 ABI ID。

对应的最小软件执行骨架应分开实现，而不是一个带可选输出 dtype 的通用 `dequant()`：

~~~text
attention_linear_group() : S16→S21→S37→S42(Q24)
mlp_linear_group()       : S12→S17→S33→S37(Q24)
qk_scaled_group()        : S35→S40→S48→S61→S35(Q14)
pv_scaled_term()         : S20→S36→S36(Q24)
finalize_linear/PV()     : Q24 round-away by 8 → saturate S24
finalize_score()         : four Q14 groups in S37 → clip S20
~~~

### 9.8 对齐截断误差

Linear 与 PV 对齐到 Q*.24。一次发生算术右移的对齐误差幅值严格小于 `2^-24`；左移和零移位没有该项误差。在 accumulator 不溢出且最终输出不饱和时，仅按项数相加可得保守界：

~~~text
Attention / Gate-Up Linear: 128 × 2^-24 = 7.6293945e-6
Down Linear:                448 × 2^-24 = 2.6702881e-5
PV:                         128 × 2^-24 = 7.6293945e-6
~~~

该界只计算 Q24 对齐截断，不包含 ScaleCode 编码误差、Hadamard/SwiGLU 误差或末级舍入。完整 Q24 累加后，从 accumulator round-half-away 到 S24 Q8.16；若未饱和，末级舍入再引入至多 `2^-17`。

QK 位于 Q14 域，单个 group 的算术右移截断误差小于 `2^-14`，四组相加时该部分的保守界小于 `4×2^-14=2^-12`。随后 `[-16,+16]` clip 是非线性饱和误差，不能并入这个截断界；因此 QK 不能套用 Q24 的 `2^-24` 结论。

Reference-QDQ 的 `F.linear` 保留原始 Linear bias。当前 Llama-3.1-8B-Instruct 的 Q/K/V/O/Gate/Up/Down projection 均无 bias，因此生产 kernel 的目标公式中 `b_o=0`。迁移到带 bias 的模型时，必须额外定义 bias 的离线编码、累加域对齐和舍入合同。

### 9.9 为什么这里不需要显式“反量化器”

软件 QDQ 通常显式构造：

~~~text
x_dq = (q_a-z_a) × s_a
w_dq = q_w × s_w
y = FP_MATMUL(x_dq, w_dq)
~~~

production 则直接执行整数点积、整数 code 乘法、二进制移位和定点累加。QK/PV 甚至把 cache scale 与 head scale/probability 融合应用，不生成中间 FP K/V。因此论文硬件路径宜使用 “integer scale application” 或“融合定点尺度恢复”，而不是“Hadamard 后反量化”。

### 9.10 输出误差的分组分解

令 Hadamard 后真实激活与 folded weight 分别为 `a`、`w`，量化重构误差为 `delta_a`、`delta_w`，则 Linear 单组输出误差可分解为：

~~~text
(a + delta_a)^T (w + delta_w) - a^T w
= delta_a^T w
+ a^T delta_w
+ delta_a^T delta_w
~~~

Hadamard 前端控制 `delta_a` 的输入定点部分；A8、W8/W4 和 ScaleCode 决定其余部分。这个分解只适用于 Linear 的误差讨论；QK/PV 还分别包含 KV12、head-scale、Softmax probability 和 score clip。因而“证明 S24 误差很小”不等于“证明完整 W4A8 网络无损”。

---

## 10. 舍入、饱和与全零语义

不同阶段使用的舍入规则并不完全相同：

| 阶段 | 规则 |
|---|---|
| production Host FP32 → S24 Q8.16 | nearest，exact half away from zero |
| production FPGA fixed SiLU×Up → S32 Q16.16 | 定点乘积按 MLP 合同 round-half-away 后写入 S32；不是 Host FP 转换或 ScaleCode 恢复 |
| `rtl_exact` 软件适配器浮点 Down 输入 → S32 Q16.16 | nearest，exact half away from zero；仅用于前端 A/B 模拟 |
| Hadamard `×11585 >>16` | nearest，exact half away from zero |
| production 激活 ScaleCode divider | RNE，ties-to-even |
| production zero-point / U8 divider | RNE，ties-to-even |
| 归档 PyTorch QDQ | `torch.round`，ties-to-even |
| production weight exporter | half-away-from-zero |
| Attention Linear S37→S42 Q18.24 | `>>> (total_shift-24)`，向负无穷取整；合法 shift 不走左移 |
| MLP Linear S33→S37 Q13.24 | total shift<24 时精确左移，否则算术右移 |
| QK S61→S35 Q21.14 | `>>> (key_shift+18)`，不加 rounding bias |
| PV S36 raw→S36 Q12.24 | `>>> (v_shift-8)`，不加 rounding bias |
| 最终 Qm.24 → S24 Q8.16 | nearest，exact half away from zero，并饱和 |
| QK S37 Q23.14 → S20 Q6.14 | 不舍入，clip 到 `[-16,+16]` |

全零组也有版本差异：

- 归档 QDQ 用 `clamp_min(1e-12)` 避免除零，数值重构仍为零；
- production 当 `diff=0` 时直接输出全零 q/code/shift/zp，不启动 divider。

论文若要求 bit-exact 复现，应把这些规则作为算法定义的一部分，而不能统一写成笼统的 `round()`。

---

## 11. S24 与整数 Hadamard 的精度证明

### 11.1 入口量化误差

令定点步长：

~~~text
Delta = 2^-16
~~~

对未饱和的 round-to-nearest：

~~~text
Q(x_i) = Delta × round(x_i / Delta)
e_i = Q(x_i) - x_i

|e_i| <= Delta/2
      = 2^-17
      = 7.62939453125e-6
~~~

对 Group32：

~~~text
||e||_2 <= sqrt(32) × 2^-17
        = 4.3158372875e-5
~~~

组内 RMS 上界仍为 `2^-17`。

### 11.2 理想 Hadamard 不放大误差能量

因为 `T T^T = I`：

~~~text
||Q(x) T - x T||_2
= ||(Q(x)-x) T||_2
= ||e||_2
~~~

这是一个严格结论：在入口不饱和时，把 FP→Qm.16 放在 Hadamard 之前不会因理想 Hadamard 而放大 L2 误差能量。

注意，这个结论是 L2 范数结论，不是逐坐标 L-infinity 结论。某些输入（例如常量向量）经过 Hadamard 后，一个坐标可能变大；不能写“Hadamard 对任意向量都降低最大值”。

### 11.3 HC-v2 系数误差与末级舍入

硬件使用：

~~~text
c = 11585 / 65536
alpha = c × sqrt(32)
      = 0.999979499517353

|alpha - 1|
= 2.0500482647e-5
~~~

若 `Q(x)` 为定点入口、`T_tilde=alpha T`、`r` 为 Hadamard 输出重新落回 Qm.16 网格的舍入误差，则：

~~~text
y_rtl = Q(x) T_tilde + r

||y_rtl - T x||_2
<= ||Q(x)-x||_2
 + |alpha-1| × ||Q(x)||_2
 + ||r||_2

||r||_2 <= sqrt(32) × 2^-17
~~~

第一项是入口定点误差，第二项是归一化常量近似，第三项是输出回落 Qm.16 网格的舍入。只有第一项经过理想 `T` 时严格保持 L2 能量；不能笼统写成“整数 Hadamard 不放大误差”。FPtoQ 实验对每个捕获的 Group32 样本直接计算该组右侧界。Llama 与 Qwen calibration capture 各 32,768 组，理论界违例均为 0。

### 11.4 Hadamard 输出位宽安全

对合法 S24 输入，任意归一化 Hadamard 输出坐标满足：

~~~text
|(T x)_j| <= ||x||_2
            <= sqrt(32) × 128
            ≈ 724.08
~~~

S27 Q11.16 可表示约 `[-1024,1024)`，因此只要入口已经合法，归一化 Hadamard 的最坏组合也可被 S27 容纳。

S32→S35 同理：

~~~text
sqrt(32) × 32768 ≈ 185363.8
< 262144
~~~

对应到 RTL raw integer 也可直接验证：

~~~text
S24 path:
|B_unscaled| <= 32 × 2^23 = 2^28
round(|B_unscaled| × 11585 / 2^16)
<= 47,452,160 < 2^26                      # fits S27

S32 path:
|B_unscaled| <= 32 × 2^31 = 2^36
round(|B_unscaled| × 11585 / 2^16)
<= 12,147,752,960 < 2^34                  # fits S35
~~~

因此当前 `11585` 系数下，两条 Hadamard 输出位宽对所有合法入口均解析安全。RTL 仍保留饱和或错误遥测以捕捉实现/接口违约。

### 11.5 Llama RMSNorm 的 prompt-independent 范围界

Llama RMSNorm 为：

~~~text
RMSNorm(x)_i =
    gamma_i × x_i /
    sqrt((1/d) × sum_j x_j^2 + epsilon)
~~~

由 `|x_i| <= ||x||_2` 且分母不小于 `||x||_2/sqrt(d)`：

~~~text
|RMSNorm(x)_i| <= sqrt(d) × |gamma_i|
~~~

Llama-3.1-8B 的 `d=4096`，故 `sqrt(d)=64`。对本地 checkpoint 逐层核验：

| Host ingress | checkpoint 最大 `|gamma|` | prompt-independent 上界 | S24 上界 |
|---|---:|---:|---:|
| `input_layernorm` | 1.4140625 | 90.5 | <128 |
| `post_attention_layernorm` | 1.375 | 88.0 | <128 |

因此，对这两类 Host RMSNorm 输出，S24 范围在任意有限输入下都有解析余量。该证明不自动覆盖 FPGA 内部 `o_proj` context、SwiGLU product 或其他模型；这些位置依赖实际 trace 与更宽的 Down 路径。

---

## 12. Hadamard 是否真的改善后续 A8？

### 12.1 理论上能说什么

Hadamard 保持 L2 能量，并将单通道信息混合到 32 个坐标。它常常能降低局部离群值对 MinMax 的支配，但不是对任意向量都保证降低最大绝对值或组 span。因此正确表述是“统计性改善分组动态范围”，而不是“必然压缩所有向量”。

### 12.2 Llama full-layer 分布证据

Llama-3.1-8B-Instruct 的 ratio CSV 同时包含 activation 与 weight phase。按 `phase=prefill_sample` 过滤后，得到 32 层×7 个目标 Linear、共 224 个 activation layer-op 记录；下表只统计这 224 项：

| 指标 | mean ratio | median ratio | ratio < 1 |
|---|---:|---:|---:|
| activation span | 0.386685 | 0.333837 | 224/224 |
| `scale_max` | 0.361366 | 0.315934 | 222/224 |
| ScaleCode payload relative-error p99 | 0.999272 | 1.000000 | 23/224 |

前两行表明 H 在这份 trace 上显著降低了组范围与最大 scale；这是经验分布证据，不是对任意输入的数学保证。第三行同时提醒，H 没有显著改善 ScaleCode 的相对编码误差，也不会减少固定 metadata 字段的位数。

### 12.3 同一 activation capture 的局部重构对照

对 Llama calibration 的同一 32,768 个 Group32 做只读重算：

| 路径 | A8 reconstruction RMSE | mean group range |
|---|---:|---:|
| raw activation → A8 | 0.001693207 | 0.994169 |
| H32 → A8 | 0.001396300 | 0.850825 |
| 相对变化 | -17.5352% | -14.4184% |

这是 matched 的激活局部重构证据，不是完整网络 no-H/H PPL 消融。当前尚无“去掉 H、重新匹配权重和全部设置”的端到端 PPL/ACC 结果，因此论文不应把这张表改写成端到端精度收益。

---

## 13. 软件参考实现

### 13.1 归档 QDQ 路径

归档 `ScalePathIAHScaleCodeLinear` 在模型加载时：

1. 复制原始 Linear；
2. 在 FP32 中 folding 权重；
3. 按 W8/W4 和 ScaleCode 做 QDQ；
4. 将反量化 folded weight 保存为计算 dtype。

每次 forward：

1. 对输入执行浮点 block Hadamard；
2. 执行 A8/ScaleCode QDQ；
3. 调用 PyTorch `F.linear`。

该实现用于评估算法误差与模型质量，并不声称模拟整数 MAC、物理 accumulator、DDR packing、RoPE 或 Softmax。

### 13.2 硬件前端 A/B 路径

FPtoQ 实验提供三条受控路径：

| Case | 激活前端 | 后续权重与 Linear |
|---|---|---|
| `software` | 浮点 H32 + 归档 A8/ScaleCode QDQ | 相同 folded QDQ weight + `F.linear` |
| `pre_q_only` | 先插入 S24/S32，再用原软件 H/A8 | 同上 |
| `rtl_exact` | S24/S32 + 整数 H + production MinMax A8 | 同上 |

这种设计能分别隔离：

- S24/S32 边界的影响；
- 整数 Hadamard、`11585` 系数和 production A8 的附加影响。

但 `rtl_exact` 的 bit-exact 边界止于激活前端。adapter 在 HuggingFace 图中各 Linear 的输入处注入 S24/S32；其中 Down 的 S32 输入由软件浮点 SwiGLU 输出直接转换，并不是 production fixed-SiLU/multiply 的逐 bit 输出。它也不会将实时 activation metadata 与 HC-v2 weight metadata 配对检查 total-shift 合法区间。因此该实验不是完整 FPGA 推理数字孪生。

### 13.3 证据层级

| 层级 | 覆盖内容 | 当前证据 |
|---|---|---|
| L1 算法级 | H + A8/W8/W4 + ScaleCode QDQ | Llama 文献对齐全量 ACC/PPL + 12 模型归档 ACC/PPL |
| L2 激活前端级 | FP→S24/S32→整数 H→整数 A8 | Llama/Qwen model A/B、真实 trace、单测 |
| L3 production 模块级 | U8×S8/S4、ScaleCode recovery、定点累加 | 10 项 scalar golden conformance tests + RTL/model 源码合同；不替代 fresh XSIM/OOC 签核 |
| L4 软件全链路闭环 | Host residual/RMSNorm、全部整数 Attention/MLP、production weight bytes | format-v3 WikiText-2 全量 PPL 与 layer 0/15/31 trace 已完成：Attention-only 六任务 ACC/PPL 通过，MLP-only/Full V5 因 Down S24/F16 饱和在 PPL 上失败且六任务 ACC 正在完成 |
| L5 实板系统闭环 | 板级 I/O、bitstream、runtime 与实测质量 | 尚无完整实板 ACC/PPL 结论 |

论文的每个 claim 应标出对应层级，不能用 L2 结果代替 L4，也不能用软件 L4 代替实板 L5。历史 L4 运行先定位了 MLP Down S24/F16 末端饱和及更低 Down shift；最终 `0x48384605` L4 数值孪生已经通过全量 ACC/PPL 与零异常审计。L5 仍需等待真实 RTL/DMA/Host 迁移和实板回归，不能用软件 L4 结果替代。

---

## 14. 12 模型算法质量结果

### 14.1 ACC 协议

- PIQA：1,838 个样本，`score_char_norm`；
- ARC-Challenge validation：299，`score_char_norm`；
- OpenBookQA validation：500，`score_char_norm`；
- HellaSwag validation：10,042，`score_char_norm`；
- WinoGrande dev：1,267，`score_sum`；
- GSM8K：first-300，提取数值后的 exact match。

只有 6/12 模型有最终 GSM8K 值。GSM8K 来自历史多轮 repaired/SDPA 运行的并表，不是一次统一的 12 模型重跑。为保证跨模型同口径，本文主统计统一使用所有模型都有的前五项任务；GSM8K 单列。归档 CSV 的历史 `Avg` 在 GSM8K 有值时取 6 项、否则取 5 项，只保留为可追溯的混合口径统计。

### 14.2 完整 ACC 表

数值单位为百分比。

| Model | PIQA | ARC-c | OBQA | HellaSwag | WinoGrande | GSM8K | 5-task ScaleCode Avg | 5-task BF16 Avg | Delta-5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DeepSeek-R1-Distill-Llama-8B | 59.63 | 24.41 | 26.80 | 47.12 | 50.28 | 60.67 | 41.65 | 43.11 | -1.46 pp |
| GLM-4-9B-0414 | 79.92 | 57.86 | 47.80 | 79.98 | 68.82 | 85.00 | 66.88 | 67.50 | -0.63 pp |
| Llama-3.1-8B | 79.98 | 53.85 | 45.40 | 77.56 | 70.24 | NA | 65.41 | 66.24 | -0.83 pp |
| Llama-3.1-8B-Instruct | 79.60 | 55.18 | 49.80 | 77.56 | 71.59 | 79.67 | 66.75 | 66.66 | +0.08 pp |
| Llama-3.2-1B-Instruct | 72.25 | 37.46 | 35.80 | 57.30 | 54.85 | NA | 51.53 | 53.20 | -1.66 pp |
| Llama-3.2-3B-Instruct | 76.17 | 43.81 | 37.80 | 68.15 | 61.25 | 67.33 | 57.44 | 58.51 | -1.07 pp |
| Mistral-7B-Instruct | 82.86 | 58.19 | 49.00 | 81.85 | 70.64 | NA | 68.51 | 68.67 | -0.17 pp |
| Qwen2.5-0.5B-Instruct | 70.57 | 29.77 | 35.60 | 49.61 | 51.62 | NA | 47.43 | 49.64 | -2.21 pp |
| Qwen2.5-1.5B-Instruct | 74.81 | 50.84 | 40.20 | 65.67 | 58.64 | NA | 58.03 | 58.72 | -0.69 pp |
| Qwen2.5-3B-Instruct | 78.56 | 51.17 | 47.00 | 72.02 | 62.43 | NA | 62.24 | 62.29 | -0.06 pp |
| Qwen2.5-7B-Instruct | 79.22 | 49.50 | 45.60 | 78.31 | 65.90 | 88.00 | 63.71 | 65.14 | -1.44 pp |
| Qwen3-8B | 78.35 | 54.52 | 43.40 | 72.21 | 64.33 | 88.67 | 62.56 | 63.55 | -0.99 pp |

以每个模型的共同五任务均值为一个样本，12 模型宏平均相对 BF16 变化为 `-0.927 pp`，模型范围为 `+0.084 pp` 到 `-2.208 pp`。另有 GSM8K 结果的 6 个模型上，GSM8K 平均变化为 `-2.8317 pp`。若复现历史 CSV 的混合五/六任务 `Avg`，会得到 `-1.085 pp`；该数字不作为本文主结论。

按任务分别对 12 个模型做宏平均，ScaleCode 相对 BF16 的变化为：PIQA `-0.7798 pp`、ARC-Challenge `-1.1427 pp`、OpenBookQA `-0.9333 pp`、HellaSwag `-1.2315 pp`、WinoGrande `-0.5459 pp`。这些任务级统计与上述共同五任务总平均使用同一组 12 模型，避免把只有部分模型有值的 GSM8K 混入主口径。

### 14.3 WikiText2 PPL 协议

- WikiText2 test；
- 取固定前 65,536 个输入 token，不应写成整个 WikiText2 test 全量；
- block size = 1024；
- stride = 1024；
- 64 个不重叠窗口；
- 实际 scoring tokens = 65,472。

### 14.4 完整 PPL 表

| Model | BF16 PPL | ScaleCode PPL | Delta PPL | Relative Delta |
|---|---:|---:|---:|---:|
| DeepSeek-R1-Distill-Llama-8B | 33.876374 | 38.663694 | +4.787320 | +14.13% |
| GLM-4-9B-0414 | 12.215040 | 12.443745 | +0.228706 | +1.87% |
| Llama-3.1-8B | 7.103704 | 7.593815 | +0.490111 | +6.90% |
| Llama-3.1-8B-Instruct | 8.252565 | 8.761913 | +0.509347 | +6.17% |
| Llama-3.2-1B-Instruct | 15.556676 | 17.454712 | +1.898035 | +12.20% |
| Llama-3.2-3B-Instruct | 13.087921 | 13.737469 | +0.649548 | +4.96% |
| Mistral-7B-Instruct | 6.775111 | 6.915713 | +0.140602 | +2.08% |
| Qwen2.5-0.5B-Instruct | 16.435293 | 17.939881 | +1.504589 | +9.15% |
| Qwen2.5-1.5B-Instruct | 11.241255 | 11.918522 | +0.677268 | +6.02% |
| Qwen2.5-3B-Instruct | 9.652969 | 11.493648 | +1.840679 | +19.07% |
| Qwen2.5-7B-Instruct | 9.222337 | 9.798556 | +0.576219 | +6.25% |
| Qwen3-8B | 11.132663 | 11.527980 | +0.395316 | +3.55% |

汇总：

- 平均绝对 PPL 增量：`+1.141478`；
- 由未舍入 PPL 重算的平均相对增量：`+7.6968%`（正文简写为 `+7.70%`）；
- 中位相对增量：`+6.21%`；
- 相对增量范围：`+1.87%` 到 `+19.07%`。

这些结果覆盖了 12 个模型，并表明退化具有显著模型依赖性（相对 PPL 变化最高为 `+19.07%`）；它们不支持“相对 BF16 无损”或“各模型均保持同等质量”的声明。

### 14.5 Llama-3.1-8B-Instruct 文献对齐全量复测

为消除第 14.1–14.4 节归档结果中任务集合、ARC split、metric 名称、上下文和 WikiText-2 子集不统一的问题，新增 `reference_qdq / literature_2048` 正式复测。该实验只验证算法：全部 224 个 Q/K/V/O/Gate/Up/Down Linear 使用 Hadamard32、Group32 activation A8、Attention W8、MLP W4 与 8-bit ScaleCode QDQ；Attention、RoPE、KV、Residual、RMSNorm 和 LM head 使用模型原生软件路径，不包含 S24、KV12、定点 Softmax 或 V5 的 128-position 限制。

固定口径为 lm-evaluation-harness 0.4.11、zero-shot、完整 official evaluation split。PIQA、ARC-Easy、ARC-Challenge、HellaSwag 使用 `acc_norm`，BoolQ 与 WinoGrande 使用 `acc`；综合值为六任务宏平均。WikiText-2 使用完整 raw-v1 test token stream、141 个非重叠 2048-token block、288,627 个 scoring token，对总 NLL 做 token-weighted 聚合后取指数。

| Task | Samples | BF16 | Reference-QDQ | Delta |
|---|---:|---:|---:|---:|
| PIQA | 1,838 | 81.284% | 80.196% | -1.088 pp |
| ARC-Easy | 2,376 | 79.545% | 78.577% | -0.968 pp |
| ARC-Challenge | 1,172 | 55.375% | 54.863% | -0.512 pp |
| BoolQ | 3,270 | 85.076% | 83.700% | -1.376 pp |
| HellaSwag | 10,042 | 79.496% | 78.600% | -0.896 pp |
| WinoGrande | 1,267 | 73.717% | 73.875% | +0.158 pp |
| **Macro ACC** | — | **75.749%** | **74.969%** | **-0.780 pp** |

| PPL protocol | BF16 | Reference-QDQ | Absolute delta | Relative delta |
|---|---:|---:|---:|---:|
| WikiText-2 full test, 2048 | 7.16143 | 7.57747 | +0.41604 | **+5.809%** |

六个 ACC split 均完整，2048 context 下截断文档数为 0；PPL 141/141 blocks 完成且 NLL 有限。结果和 matched comparison 位于 `0_Software/fix_experiment/results/algorithm_reference_full`。这组结果是本文优先采用的 Llama 单模型算法质量证据；第 14.1–14.4 节仍用于跨模型趋势，但不再替代本节的论文标准 Llama 数值。

---

## 15. Llama-3.1-8B-Instruct 硬件前端验证

### 15.1 受控 PPL A/B

三路均使用相同的 Hadamard-folded Attention W8 / MLP W4 归档权重、相同数据切分、eager attention、seed `20260911`、deterministic algorithms 和关闭的 TF32。

| 路径 | PPL | 相对 software | Token accuracy | Accuracy delta |
|---|---:|---:|---:|---:|
| `software` | 8.761912525 | 0 | 53.27163% | 0 |
| `pre_q_only` | 8.767853563 | +0.06781% | 53.21053% | -0.06109 pp |
| `rtl_exact` | 8.760934559 | -0.01116% | 53.27621% | +0.00458 pp |

`rtl_exact` 相对 `software` 的变化应表述为“数值持平”，不能解释成可泛化的精度提升。

还必须区分 BF16 基线：原始 BF16 PPL 为 `8.252565`；归档完整量化软件为 `8.761913`，相对 BF16 增加 `6.17%`。`rtl_exact` 的 `8.760935` 相对 BF16 仍约增加 `6.16%`。前端持平只说明 S24/整数 H/A8 没有在既有量化误差上继续恶化。

### 15.2 全量逻辑前端审计

下表来自与 PPL 相同的固定前 65,536 个输入 token、64 个窗口的 evaluation slice；adapter hook 覆盖全部 224 个逻辑 Linear，而不是只统计第 15.3 节的 capture 子样本。

| 路径 | 逻辑元素数 | Group32 数 | 输入范围 | 入口饱和 | H 饱和 | Scale format error |
|---|---:|---:|---:|---:|---:|---:|
| S24 Q8.16 → S27 Q11.16 | 51,489,275,904 | 1,609,039,872 | [-21.5, 17.75] | 0 | 0 | 0 |
| S32 Q16.16 → S35 Q19.16 | 30,035,410,944 | 938,606,592 | [-560, 239] | 0 | 0 | 0 |

计数按 224 个逻辑 Linear 调用累计。Q/K/V 与 Gate/Up 的输入在软件中会重复计数；该表不等于物理 DMA 元素数。

### 15.3 真实 activation trace

capture 运行了 8 条固定 calibration prompt，并对代表性 `q_proj`、`o_proj`、`gate_proj`、`down_proj` 各保存上限 8,192 个 Group32，合计 32,768 组、1,048,576 个元素。这里的“代表性”是省略同源 K/V 与 Up 的重复入口，不是对激活值做去重。由于当前 cap 在运行早期已填满，样本并非跨 8 条 prompt 均匀抽取；manifest 显示每个代表 op、每层各 256 组。

| 指标 | 数值 |
|---|---:|
| 常规 S24→S27 groups | 24,576 |
| Down S32→S35 groups | 8,192 |
| 输入范围 | [-15.0625, 9.25] |
| 入口 / H 饱和 | 0 / 0 |
| FP→Qm.16 RMSE | 1.30317e-6 |
| FP→Qm.16 max abs error | 7.6293945e-6 |
| RTL H 相对 FP64 RMSE | 7.50253e-6 |
| RTL H SQNR | 91.72 dB |
| RTL H cosine | 0.999999999874 |
| software A8 RMSE | 0.00139630013 |
| hardware A8 RMSE | 0.00139615248 |
| hardware A8 RMSE 相对变化 | -0.01057% |
| hardware/software A8 byte match | 98.73438% |
| metadata match | 98.43140% |
| hardware/software A8 cosine | 0.999999856706 |
| 理论界违例 | 0 / 32,768 groups |

A8 byte 不必 100% 相同：很小的前端扰动也可能使临界值跨过整数舍入阈值。更有意义的指标是相对共同 FP-H golden 的 RMSE 没有增加。

### 15.4 历史 V5 format-v2 全链路 ACC/PPL 诊断

> 本节结果对应已经废止的 MLP format-v2（`0x48384602`、S36/S43/S45、
> total shift `[21,44]`），仅用于记录发现 `shift=20` 错误的过程。当前生产
> format-v3 为 `0x48384603`、S37/S44/S46、`[20,44]`，不得引用本节旧 PPL/ACC
> 作为当前实现结果。新实验见
> `0_Software/fix_experiment/source/ScaleLLM_RoPE_Softmax_fixedpoint_precision_validation_task.md`。

本节不再只替换激活前端，而是运行当时的 Llama-3.1-8B-Instruct V5 软件数字孪生。该历史硬件选择使用 Attention format ID `0x48384103`、MLP full format ID `0x48384602`；覆盖 production folded/quantized weight、全部整数 Linear、定点 RoPE/KV12/QK/Softmax/PV/SwiGLU，以及 Host FP32 residual/RMSNorm。V5 只支持最多 128 keys，因此 BF16 与 V5 共同使用 context/max-length 128，不能与第 14–15 节的 1024-context PPL 横向比较。

WikiText2 口径为固定前 65,536 个输入 token、block size 128、stride 127，共 517 个滑窗和 65,535 个计分 token：

| 路径 | PPL | 相对 BF16 | Token accuracy | Accuracy delta | 数值状态 | 硬件合同状态 |
|---|---:|---:|---:|---:|---|---|
| BF16 matched-context | 17.8416705 | 0 | 46.17838% | 0 | pass | valid |
| V5 RTL zero-guard diagnostic | 28.1808505 | +57.9496% | 39.52239% | -6.65599 pp | pass | `invalid_format_error` |

选择题每项取数据集前 300 条原始记录；ARC-Challenge 经样本构造后有 299 条有效记录，其余任务各 300 条。PIQA、ARC-c、OpenBookQA、HellaSwag 使用 `score_char_norm`，WinoGrande 使用 `score_sum`：

| Task | Samples | BF16 ACC | V5 ACC | Delta |
|---|---:|---:|---:|---:|
| PIQA | 300 | 81.6667% | 80.6667% | -1.0000 pp |
| ARC-Challenge | 299 | 54.5151% | 51.1706% | -3.3445 pp |
| OpenBookQA | 300 | 49.3333% | 45.3333% | -4.0000 pp |
| HellaSwag | 300 | 64.0000% | 61.6667% | -2.3333 pp |
| WinoGrande | 300 | 73.0000% | 69.6667% | -3.3333 pp |
| **五任务宏平均** | — | **64.5030%** | **61.7008%** | **-2.8022 pp** |

两条路径均产生完整的 1,499 条选择题记录且所有分数有限。这里 `pass` 只表示数值评测完成，并不表示硬件合同通过。严格模式首先在以下位置停止：

~~~text
model.layers.31.mlp.down_proj.weight
row=1397 group=170 column=704
activation_shift=6 weight_shift=14 total_shift=20
legal total-shift range=[21,44]
~~~

`hap_a8w4_group32_lane2_s36.sv` 对非法且非零的 scale pair 不做自动钳位：该 group 的 guard 贡献置零，同时拉高 sticky error。为了得到故障后的诊断质量，表中 V5 使用 `--allow-format-errors`，严格复现这个 zero-guard 值并继续推理。合并后的审计如下：

| Audit counter | Count |
|---|---:|
| Activation logical elements | 86,872,162,304 |
| FP→fixed saturation | 0 |
| Hadamard saturation | 0 |
| Activation ScaleCode format error | 0 |
| Linear total-shift format error | 517 |
| Linear accumulator overflow | 0 |
| Linear output saturation | 34,239 |
| RoPE output saturation | 0 |
| KV12 clip | 0 |
| QK score clip | 27,297,254 |
| PV output saturation | 0 |
| SwiGLU S32 overflow | 0 |

517 次 total-shift error 全部来自该历史 format-v2 的 WikiText2 PPL 分片；五个 ACC 分片没有新增该错误。尽管如此，该版 V5 在指定 workload 上违反格式合同，而且 matched BF16 对照显示 PPL 和 ACC 均有明显退化。因此论文不能把本节写成“当前 V5 全链路维持精度”或“当前硬件通过”；准确表述是：**历史 format-v2 数字孪生成功运行到质量指标并暴露了一个必须修正的 production 格式错误，zero-guard 后的诊断质量为 PPL +57.95%、五任务 ACC -2.80 pp。**

### 15.5 历史 format-v3 全链路故障诊断（已被 `0x48384605` 取代）

2026-09-17 的验证使用当时的 `0x48384103/0x48384603` 合同，并新增
`v5_attention` 与 `v5_mlp` 两条隔离路径。fresh xsim 已得到：

- Softmax 32 行 × 128 key：0 mismatch；
- cohort16 Attention（RoPE/KV12/QK/Softmax/PV/Wo）：82,695 checks PASS；
- MLP `total_shift=20`：输出 raw S24=`56400`，S37 guard 与 S46 accumulator
  overflow 均为 0。

固定一个 128-token WikiText-2 block，在真实 layer 0/15/31 激活上得到：

| 节点 | 三层最低 cosine | 三层最大 max-abs error |
|---|---:|---:|
| RoPE Q/K local | `0.999999999989` | `1.52523e-5` |
| KV12 key/value | `0.999998447017` | `0.0317383` |
| QK score | `0.999999999402` | `0.00124854` |
| fixed Softmax local | `0.999999983644` | `0.000262371` |
| PV local | `0.999999918583` | `1.18430e-5` |

三层 trace 均无 FP→S24、Hadamard、RoPE、KV12 或 PV 饱和/clip，也无
format/guard/accumulator overflow。QK 的 `[-16,+16]` 算法 clip 仍存在：有效
score 中 layer 0/15/31 分别有 `359/43/5256` 项命中边界，必须与位宽溢出区分。

WikiText-2 raw-v1 test 全流使用 128-token 非重叠 block、丢弃 40-token 尾部，
共 2,257 blocks、286,639 scoring tokens。严格 format-v3 结果为：

| 配置 | PPL | 相对 matched BF16 | 质量阈值 | 合同 |
|---|---:|---:|---|---|
| Matched BF16 | `17.208506` | — | baseline | valid |
| Attention-only | `17.313385` | `+0.609%` | PASS（≤10%） | valid |
| MLP-only | `27.801928` | `+61.559%` | FAIL | valid |
| Full V5 | `27.639944` | `+60.618%` | FAIL | valid |

PPL 全流中，FP→S24、Hadamard、activation ScaleCode、Linear guard/accumulator、
RoPE、KV12、PV 和 SwiGLU 的非预期 overflow/saturation 均为 0。Attention-only
共记录 63,628,049 次 QK `[-16,+16]` 主动 clip，约占 19,081,003,008 个有效
causal score 的 `0.333%`；这属于算法定义的 clamp，不等同于 S20/F14 存储溢出。

MLP-only 的 `linear_output_saturation=20,251`，全部集中在 `down_proj`：layer 1
为 6,847 次，layer 31 为 13,404 次。layer 31 的 Down local trace 中，参考绝对
最大值为 `587.87`，而当时的 S24/F16 仅覆盖 `[-128,127.9999847]`；local cosine
降至 `0.866466`、NMSE 为 `0.25779`。相同 8-block 因果消融中，BF16、历史
Down-S24 和软件 Down-S32 PPL 分别为 `15.963785/30.723612/17.577764`。这证明
该版 Full V5 质量失败的主因是 **Down 最终输出边界过窄**。后续压力测试又发现
Down shift 12～13 会超出旧 S37 guard，因此最终合同不能只改末端输出，而采用
`[12,44]`、S45/S54→S32/F16。该最终合同的全量 PPL、六任务 ACC 和异常计数
已经在第 0 节签核通过。

这也不是只替换一个 `saturate_s24` 函数即可闭环的局部修改。历史 production
图在 Down accumulator finalize、shared slice/elastic queue、Down scheduler、
12→16 repack、serial/full command、resource/production top、tensor DMA 和 Host
unpack/buffer sizing 上都保持 S24/F16 ABI；其中每个 `16×16` 输出 tile 为
`6144 bit = 24×AXI256 beat`，完整 `16×4096` cohort 为 192 KiB。若采用正确性
优先的 S32/F16，Down-only 输出必须全链同步变为 `8192 bit = 32×AXI256 beat`
和 256 KiB，并生成独立的 S32 Host 解包；MLP 输入以及 Gate/Up 输出仍保持
S24/F16，不能无差别把全部激活接口拓宽。若只改 accumulator 或内部端口，
最终 S24 saturation 仍然存在。S27/S28/F16 或保持 24-bit 总宽并改为 F13 都未按
最终全流口径验证，不能替代已经签核的 S32/F16 合同。

为防止再次出现“内部 accumulator 已加宽、外部 ABI 仍旧”的局部修改，新增
`audit_mlp_down_s32_migration.py` 对 active production source closure、Down
finalizer、shared slice、scheduler/repack、serial/full command、resource top、
production core、tensor DMA、Host payload/unpack、format ID 和 saturation telemetry
执行 fail-closed 审计。当前未修改 RTL 的基线为 `4/15 PASS`，其余 11 项明确
失败；硬件签核要求去掉 `--allow-incomplete` 后达到 `15/15 complete_pass`。

Attention-only 六个 full split 为：PIQA `81.447%`、ARC-Easy `79.377%`、
ARC-Challenge `55.887%`、BoolQ `83.180%`、HellaSwag `79.466%`、WinoGrande
`73.244%`。六任务 Macro ACC 为 `75.4337%`，相对 matched BF16 的 `75.3853%`
变化 `+0.048 pp`；HellaSwag 单项相对 BF16 变化 `-0.030 pp`。该合并 manifest
覆盖全部 19,965 个样本，`hardware_contract_status=valid`，全量联合 shift 范围
为 `[28,47]`，历史 shift 25 未复现。MLP-only 与 Full V5 的六任务 ACC 已于
2026-09-17 按用户指令停止；终止时两条 HellaSwag worker 分别只完成
`3,907/40,168` 和 `8,775/40,168` 个 likelihood requests，尚未聚合完整样本，
不得当作中间 ACC。最终总表仍以 `validation_completion_audit.json` 全通过为准。

本轮早期 worker manifest 没有内嵌 `model_identity`，因此不能从该字段直接读取
checkpoint 指纹。可复核产物引用同一本地路径已生成的逐文件身份文件
`six_model_algorithm_literature_2048/model_identities/Llama-3.1-8B-Instruct.json`：
14 个文件、总计 16,069,773,869 bytes，聚合 fingerprint 为
`f32c0adabc4443d374a0ebac6dcb0c5425b2e88aa84c54420ae040117794efe6`。验证器会
核对 resolved path、文件集合与逐文件大小，并重新计算全部 14 个文件的 SHA-256；
当前逐文件 byte hash 为 14/14 PASS。该外部 provenance 不会回写或伪造已经完成
的 worker manifest。

---

## 16. Qwen 交叉验证与负向证据

### 16.1 Qwen2.5-0.5B PPL A/B

| 路径 | PPL | 相对 software | Token accuracy delta |
|---|---:|---:|---:|
| `software` | 17.939881 | 0 | 0 |
| `pre_q_only` | 18.113120 | +0.96566% | -0.07942 pp |
| `rtl_exact` | 18.130087 | +1.06024% | -0.09164 pp |

在同样固定前 65,536 个输入 token、64 个窗口，并覆盖全部 168 个逻辑 Linear 的审计中：

- 常规 S24 路径处理 `8,447,459,328` 个元素，观测输入范围 `[-58.5,334]`；
- 260 个元素发生 S24 饱和，占 `3.07785e-6%`；
- S32 Down 路径处理 `7,642,939,392` 个元素，范围 `[-2160,172]`，无饱和；
- Hadamard 饱和和 ScaleCode format error 均为 0。

Qwen 结果说明 S24 的效果存在模型依赖性。校准 trace 的零饱和不能代替完整 workload 审计。
当前对照没有构造“保留其余 HC-v2 算术、仅消除 S24 饱和”的第四条路径，因此不能把 `+1.06024%` PPL 变化直接归因于这 260 个元素；严谨表述是二者在同一运行中同时被观测到。

### 16.2 合成负向探针

| Probe | 观察 | 含义 |
|---|---|---|
| `tiny_rms_2^-14` | `(RMSE_hw-RMSE_sw)/RMSE_sw=19.19`，即 hardware RMSE 约为 software 的 `20.19×` | 整组幅度接近 `2^-16` 定点步长时，16 个小数位会成为瓶颈 |
| `overflow_probe`，组内 ±160 | 4,096 / 131,072 元素入口饱和，误差显著增加 | 超过 S24 范围时解析正交界不适用 |

这两项负向结果必须保留，避免选择性报告正常尺度数据。

---

## 17. 传输、metadata 与计算开销

### 17.1 每个 cohort16 的数据量

一个 cohort 包含：

~~~text
16 × 4096 = 65,536 elements
~~~

| 格式 | 每元素 | Metadata | 总量 |
|---|---:|---:|---:|
| BF16/FP16 | 2 B | 无 | 128 KiB |
| S24 Q8.16 | 3 B | 隐式 `2^-16`，无逐组 metadata | 192 KiB |
| FP32 | 4 B | 无 | 256 KiB |
| U8 + U24/Group32 | 1 B | 3 B / 32 elements，逻辑紧密打包 | 70 KiB |

U8 内部表示中，metadata 相对纯 A8 payload 的额外开销为 `3/32=9.375%`；但总计仍远小于 S24。这里 70 KiB 假设 U24 真正按 3 B 紧密打包；若内存或总线将每组 metadata 按 4 B 对齐，则总量为 72 KiB。

### 17.2 32 层 Host partition 的流量

当前 Host residual/RMSNorm partition 对单个 cohort16 有 64 次 H2C 和 64 次 C2H。payload 算术如下：

| 边界格式 | 单次 tensor | 64×H2C | 64×C2H | 双向总量 | 口径 |
|---|---:|---:|---:|---:|---|
| BF16 | 128 KiB | 8 MiB | 8 MiB | 16 MiB | 反事实 |
| S24 | 192 KiB | 12 MiB | 12 MiB | 24 MiB | 当前合同 |
| FP32 | 256 KiB | 16 MiB | 16 MiB | 32 MiB | 反事实 |
| U8+U24/group | 70 KiB | 4.375 MiB | 4.375 MiB | 8.75 MiB | 反事实；U24 紧密 3 B |

U8 行不能被解读为“只改传输编码即可节省到 8.75 MiB”。若 H2C 与 C2H 都改为 A8+metadata，Host residual/输出的数值合同、在线量化位置和解码路径都必须改变；它不是与当前 S24 接口功能等价的即插即用替换。若 U24 按 4 B 对齐，该反事实双向 payload 为 9 MiB。

以上都只是 payload 算术，不包含协议、DMA descriptor、burst padding 或地址对齐开销，也不是实测端到端延迟。

### 17.3 Host pack/unpack

`pack_s24_q16` 执行：

- FP32 乘 `2^16`；
- half-away rounding；
- S24 饱和；
- 24-bit two’s-complement；
- 三字节小端交织。

`unpack_s24_q16` 执行三字节拼接、符号扩展和除 `2^16`。二者均为 O(N) memory pass。

当前代码中，pack 在 DMA `start_ns` 之前执行，unpack 在 `end_ns` 之后执行。因此现有 transfer trace 不能用于证明 pack/unpack 延迟为零，也不能直接作为端到端 Host 开销。

### 17.4 Hadamard 与量化计算

每个 Group32 的 FWHT：

- 5 级；
- 每级 16 个蝶形；
- 每个蝶形产生一加一减；
- 总计 160 个加/减结果；
- 再执行归一化常量乘与舍入。

权重 Hadamard 已离线 folding，不进入在线关键路径。在线 H/A8 的代价需要与后续大量输出通道的 GEMM 一起摊销；在没有当前 MinMax production 的统一 XSIM/OOC 周期和资源签核前，本报告只给算法复杂度，不给未经验证的加速比或面积结论。

### 17.5 开销与收益的正确权衡

可以写：

- S24 相对 FP32 将 Host–FPGA tensor payload 减少 25%；
- 定点入口避免 FPGA 内实现 FP Hadamard；
- H 后 U8 与 W8/W4 使主 MAC 保持整数；
- 激活动态 scale 与权重静态 scale 均用整数 code/shift metadata，不需要浮点 scale datapath；
- 同源 Q/K/V、Gate/Up 可共享激活前端。

不能写：

- S24 相对 BF16 节省带宽；
- S24 或 pack/unpack “没有开销”；
- 现有 DMA trace 已包含格式转换时间；
- 固定点一定比 FP 在当前完整设计中更快或更省资源，除非引用 matched 综合/周期结果。

---

## 18. 有效性威胁与尚未完成的验证

以下项目应在论文 limitation 或 future work 中明确披露：

1. **production shift6 跨模型审计。** Llama/Qwen 激活前端未见 format error；但归档 12 模型的所有离线 weight scale 是否均满足 shift≤63，尚需统一扫描。
2. **production weight-path 的跨模型验证。** Llama-3.1-8B-Instruct 最终 `0x48384605` production weight bytes + integer MAC 已完成 MLP-only/Full V5 全量 PPL、六任务 ACC 与严格异常计数验证，精度通过。其余 11 个模型仍只有数值合同不同的 Reference-QDQ，不能直接外推 Llama 的硬件位宽结论。
3. **完整 Host 闭环。** V5 twin 已覆盖 Host residual/RMSNorm→S24→全部整数 Attention/MLP→Down S32→Host 的软件逐层闭环，但尚未用迁移后的真实板级 DMA/runtime/bitstream 闭环复测 ACC/PPL。
4. **no-H 端到端消融。** 已有组范围和局部 RMSE 证据，但尚无 matched no-H vs H 的完整 PPL/ACC。
5. **位宽 Pareto。** 尚未完成 S16/S20/S24 在同一 workload、同一饱和策略下的精度–带宽 sweep。
6. **运行时入口饱和遥测。** Host `pack_s24_q16` 当前静默 `np.clip`，不会返回 saturation count。Hadamard counter 无法发现已被 Host 裁掉的值。
7. **pack/unpack 计时。** 当前 transfer trace 不含格式转换时间。
8. **MinMax production 资源/周期。** 旧 robust-clipping 数据不能当作当前 raw-MinMax 模块的最终资源和性能结果；需 fresh XSIM/OOC 签核。
9. **GSM8K 一致性。** 6 个模型的历史结果由多轮修复/合并得到，参数不完全统一。
10. **完整部署状态。** V5 full-chain twin 是软件算术仿真，不能表述为 full FPGA deployment、完整 bitstream 实板模型质量或板级逐位闭环。
11. **跨输入泛化。** Llama WikiText2 的零饱和不证明任意 prompt、上下文长度或数据集均零饱和。
12. **极小信号。** 合成 tiny-RMS probe 表明 `2^-16` 定点分辨率对极小整组信号可能不足。
13. **activation/weight 联合 shift 合同。** 历史 format-v2 在最后一层 `down_proj` 发现 total shift 20，小于当时的合法下限 21；后续压力测试又观测到 Down 最低为 12～13。最终 `0x48384605` 将 Down 合法范围冻结为 `[12,44]`，采用 S45 group guard 与 S54 accumulator；严格候选的 shift/overflow 异常计数为 0。真实 RTL 仍需补齐 shift 12～19 定向向量和迁移回归。
14. **Down 输入来源。** 旧 `rtl_exact` 前端 A/B 仍在 HuggingFace `down_proj` 输入处转换浮点 SwiGLU；新增 V5 full-chain twin 已覆盖 production fixed-SiLU 与定点乘法。两类结果不可混称。
15. **capture 采样覆盖。** 当前 32,768 组 capture 由四类代表 op 的固定 cap 构成，cap 在运行早期填满，并非对 8 条 calibration prompt 的均匀随机样本；结论只对应已保存样本。
16. **软件环境锁定。** 现有归档记录了模型、数据切分、seed 与部分确定性开关，但 GPU 型号、驱动/CUDA、PyTorch 和 Transformers 等完整版本组合未统一固化；在不同软件栈上不能保证逐 bit 复现，正式发布 artifact 时应补充环境清单或容器镜像。
17. **SwiGLU 乘积位宽。** 当前生产 RTL 仍使用 S32 Q16.16。解析上 S31 足以覆盖所有合法 S24 Gate/Up 输入；Llama/Qwen trace 分别支持 S27/S29，但这些 workload 观测尚不足以签核通用缩窄合同。
18. **MLP Down 输出位宽。** 旧 S46/F24→S24/F16 路径在 layer 1/31 发生末端饱和，layer 31 trace 的 `587.87` 超过 S24/F16 的约 ±128 范围。最终选择已经冻结为 S45/F24 group guard、S54/F24 accumulator 和 S32/F16 输出；MLP-only/Full V5 全量 PPL、六任务 ACC 与严格异常计数均已通过。仍未完成的是 RTL/DMA/Host 对该冻结合同的真实迁移，而不是软件位宽选择。

---

## 19. Claim–Evidence 对照表

| 拟写结论 | 证据 | 强度 | 必要限定 |
|---|---|---|---|
| 理想 H 不放大 Qm.16 入口误差 L2 | 正交性推导 | 严格证明 | 入口未饱和 |
| S24→S27 位宽足够 | Cauchy–Schwarz 最坏界 | 严格证明 | 合法 S24 输入 |
| Llama 两类 RMSNorm 输出落在 S24 | RMSNorm 范围界 + checkpoint gamma | 严格到模型参数 | 只覆盖两类 Host ingress |
| Llama 定点前端数值持平 | 64-block PPL A/B | 强经验支持 | 相对归档 software，不是 BF16 |
| Qwen 前端约 +1.06% PPL | 同口径 PPL A/B | 经验支持 | 同一运行观测 260 个饱和点，未隔离因果 |
| H 降低局部分组范围 | 224 records + capture 重构 | 强分布证据 | 不是端到端 PPL 消融 |
| Llama Reference-QDQ 算法退化有限 | 文献对齐 full-split ACC + WikiText-2 2048 PPL | 强算法级经验支持 | Macro ACC -0.780 pp、PPL +5.809%；非硬件 bit-exact |
| Reference-QDQ 覆盖 12 模型 | ACC/PPL 归档 | 算法级经验支持 | 退化显著模型相关，历史口径不完全统一 |
| 历史 Llama V5 format-v2 质量 | production twin + 1,499 条 ACC 记录 + 65,535-token PPL | 历史诊断证据 | total-shift sticky error；PPL +57.95%、ACC -2.80 pp，不代表当前实现 |
| 最终 Llama V5 软件候选 | WikiText-2 全流 2,257 blocks + 六任务全量 ACC | 强全链路软件证据 | MLP-only PPL +7.230%、Macro ACC -0.7384 pp；Full PPL +7.828%、Macro ACC -0.7489 pp，均通过 |
| 最终 `0x48384605` 格式合同 | 严格模式 + 联合 shift/overflow 审计 | 软件格式支持 | Gate/Up S37/S44；Down `[12,44]`、S45/S54→S32；候选分片异常计数 0；真实 RTL/Host 尚未迁移 |
| 完整实板与软件无损等价 | 当前无充分证据 | 不支持 | 不应声明 |

---

## 20. 审稿答复模板

### Q1：为什么选择 S24，而不是直接传 BF16 或 A8？

建议答复：

> S24 Q8.16 是 Host FP32 residual/RMSNorm 与 FPGA 整数数据通路之间的边界格式。其 16 个小数位将非饱和舍入误差限制在 `2^-17`，而约 ±128 的动态范围对 Llama-3.1-8B 的两类 RMSNorm ingress 可由 checkpoint 参数给出 prompt-independent 上界。与 FP32 相比，S24 将 tensor payload 减少 25%，同时允许 FPGA 直接执行整数 FWHT。我们不声称其优于 BF16 的带宽：S24 比 BF16 多 50%，这是数值范围、整数实现和通信量之间的工程折中。直接传 A8 会要求 Host 提前计算每个 Group32 的动态 scale，并失去当前 FPGA 在线量化与前端共享的数据流。

### Q2：先定点化再 Hadamard 会不会放大误差？

建议答复：

> 对未饱和 Qm.16 入口，误差向量记为 `e=Q(x)-x`。理想归一化 Hadamard `T` 正交，故 `||eT||_2=||e||_2`；每个 Group32 的入口误差 L2 上界为 `sqrt(32)×2^-17=4.31584e-5`。HC-v2 还引入 `11585/65536` 的归一化系数近似和一次 Qm.16 舍入，我们在逐组界中显式加入这两项，并在 Llama 的 32,768 个捕获样本组上观测到零违例。

### Q3：既然 S24 已经是定点，为什么还需要 H 和另一个 scale？

建议答复：

> S24 与 A8 解决不同问题。S24 使用全局固定二进制点 `2^-16`，是高精度边界容器；A8 是实际 MAC 输入，必须用每组动态 MinMax scale 将 32 个值映射到 256 个码。S24 不会自动移除离群通道。Hadamard 在 A8 前混合通道能量，并通过离线 folded weight 保持理想线性等价。在 Llama full-layer trace 上，Hadamard 后组 span/raw span 的平均比为 0.3867，表明它在该 workload 上显著降低了 A8 动态范围；由于尚无 matched no-H 端到端消融，我们只主张独立条件化作用，不主张不可替代性。

### Q4：动态 scale 是否又引入浮点计算？

建议答复：

> 不需要浮点 scale datapath。HC-v2 根据 Qm.16 raw integer 的 `diff` 直接生成 U8、zero-point 与 ScaleCode；scale metadata 是整数 `code8/shift6`，解码值为逐组二进制有理数 `code×2^-shift`。矩阵乘后计算整数 correlation，再乘 activation/weight code 并按两个 shift 之和对齐；算术右移可能产生有界截断，但整个 scale application 不会显式构造逐元素浮点激活或权重。

### Q5：你们能否声称硬件无损？

建议答复：

> 我们只声称 Llama-3.1-8B-Instruct 在固定前 65,536 个输入 token、64 个窗口的 WikiText2 evaluation slice 上，HC-v2 激活前端相对既有软件量化基线数值持平，且观测到零入口/Hadamard 饱和。文献对齐的 Reference-QDQ 完整 Hadamard+A8/W8/W4 相对 matched BF16 的 PPL 增加 5.809%；12 模型平均相对 PPL 增量为 7.70%。因此“前端未观察到额外可分辨退化”与“完整量化相对 BF16 数学无损”是两个不同结论，后者不成立；最终 `0x48384605` 的硬件对齐精度必须由下述 full-chain twin 结果单独支撑。

历史 V5 format-v2/v3 full-chain twin 进一步否定了把前端结果外推到完整 production 链路的做法：它们先后暴露 total-shift 下界和 Down-S24 输出范围问题。最终 `0x48384605` 软件候选已经把 Down 合同扩为 `[12,44]`、S45/S54→S32/F16；MLP-only 的 PPL/Macro ACC 相对 BF16 分别为 `+7.230%/-0.7384 pp`，Full V5 分别为 `+7.828%/-0.7489 pp`，全部候选异常计数为 0。因而可以声称软件 bit-exact 候选在预注册口径内保持精度，但仍不能声称“实板硬件无损”：真实 RTL/DMA/Host 迁移审计仅 `4/15`，完成 `0x48384605` 和实板回归前硬件结论仍为 HOLD。

---

## 21. 可直接用于论文的软件方法描述

下面文字可作为论文 Method 的中文初稿，正式投稿时应按版面压缩，并将仓库路径替换为论文图表编号。第 21.1–21.2 节描述共享算法骨架，第 21.3–21.5 节描述 HC-v2 硬件映射。引用 12 模型结果时必须标注其配置是 Reference-QDQ（shift8、raw-scale 生成权重码等，见第 2.3 节），不能把 HC-v2 的 shift6 描述与 Reference-QDQ 的结果写成同一个已验证配置。

### 21.1 方法总览

> 我们提出一种面向整数 FPGA 数据通路的 Group32 Hadamard–ScaleCode 后训练量化方法。对每个目标线性层，激活沿最后一维划分为连续的 32 元素块，并在在线阶段应用归一化 Hadamard32；权重沿输入维在离线阶段应用相同的块变换。记理想变换 `T=H_32/sqrt(32)`，激活和权重分别变换为 `x_h=xT` 与 `W_h=WT`。由于 `TT^T=I`，有 `x_hW_h^T=xW^T`，因此理想变换在无量化时保持原线性算子不变，并且无需在运行时执行逆变换。硬件常量近似造成的 `T_tilde=alpha T` 偏差在硬件映射与误差分析中单独处理。

### 21.2 激活与权重量化

> Hadamard 后的激活采用 per-token、per-Group32 的无符号非对称 MinMax A8 量化。每组范围强制包含零，令 `l=min(min(x_h),0)`、`u=max(max(x_h),0)`，则 `s_a=(u-l)/255`，zero-point 为 `z_a=round(-l/s_a)`，量化码为 `q_a=clip(round(x_h/s_a+z_a),0,255)`。该过程不使用 percentile、MSE 或 alpha clipping。folded weight 采用 per-output-channel、per-Group32、zero-point=0 的 max-abs signed 量化；Attention 的 Q/K/V/O 使用 W8，MLP 的 Gate/Up/Down 使用 W4，`lm_head` 保持原精度。

### 21.3 ScaleCode 与整数执行

> 在 HC-v2 中，为避免在 FPGA 中保存和应用浮点 scale，我们将每个激活或权重 scale 编码为 `s_hat=c×2^-r`，其中 `c` 为 8-bit unsigned code，`r` 为 6-bit shift。对每个 Group32，整数内积为 `d=sum_i(q_a,i-z_a)q_w,i`，其尺度应用写为 `d×c_a×c_w×2^{-(r_a+r_w)}`。硬件先完成整数 code 乘法，再用二进制移位将组贡献对齐到具有 24 个小数位的 guard 域并累加，从而避免显式构造反量化的浮点激活和权重；发生算术右移时会产生小于 `2^-24` 的逐组截断误差，并非数学无损。若 Linear 含 bias，理想变换下 bias 可保持不变，但 production 还必须给出 bias 的定点编码和累加对齐；当前 Llama 目标投影均无 bias，本报告的 HC-v2 整数合同不外推到带 bias 模型。

### 21.4 硬件对齐的激活边界

> Host 以 FP32 完成 residual 与 RMSNorm，并将常规激活转换为 S24 Q8.16。FPGA 对 S24 raw integer 执行五级 Hadamard 蝶形，并以 Q0.16 常量 11585 近似 `1/sqrt(32)`，生成 S27 Q11.16。随后在线 MinMax 模块直接由整数范围生成 U8 与 `{shift6,code8,zp8}` metadata。Gate/Up 采用 S37/F24 group guard、S44/F24 accumulator 和 S24/F16 输出；packed S24 lane 在进入 SiLU/SwiGLU 前按 bit `[23]` 符号扩展。SwiGLU 乘积到 Down projection 使用 S32 Q16.16→S35 Q19.16 前端；Down 在 `[12,44]` shift 范围内使用 S45/F24 group guard、S54/F24 accumulator，并输出 S32/F16。这里 S24 是高精度入口/中间边界格式，而 U8 是低比特 MAC 格式；Down 的 S32 是为了覆盖投影输出动态范围。

### 21.5 精度论证

> 对入口未饱和的 Qm.16 转换，逐元素舍入误差至多为 `2^-17`。理想归一化 Hadamard 为正交变换，因此入口量化误差的 L2 范数在变换前后保持不变。对 Group32，其 L2 上界为 `4.31584×10^-5`。HC-v2 实际使用 `T_tilde=alpha T`，其中 `alpha=0.9999794995`；它相对理想算子的确定性增益偏差为 `2.05005×10^-5`，输出回落 Qm.16 的舍入也在实验界中单独计入。在 Llama-3.1-8B-Instruct activation capture 上，整数 Hadamard 相对 FP64 的 SQNR 为 91.72 dB；其 RMSE 仅为后续 A8 量化 RMSE 的约 0.54%。

### 21.6 质量结果表述

> 在 12 个 0.5B–9B 模型上，Reference-QDQ 相对 BF16 的共同五任务宏平均 accuracy 变化为 -0.927 个百分点，WikiText2 PPL 的平均相对增量为 7.70%。这是算法级 QDQ 证据。进一步地，在仅替换激活前端的 HC-v2 受控实验中，Llama-3.1-8B-Instruct 相对浮点 Hadamard/A8 软件前端的 PPL 变化为 -0.011%，应解释为数值持平；Qwen2.5-0.5B 的变化为 +1.060%，且同一运行观测到极少量 S24 饱和，但当前实验未证明二者的因果关系。两套结果属于不同数值配置，支持模型相关、带饱和条件的结论，而非普遍无损声明。

> 对 Llama-3.1-8B-Instruct 的 V5 production 全链路软件数字孪生，在共同的 128-context 口径下，WikiText2 PPL 从 BF16 的 17.8417 上升到 28.1809，first-300 五任务宏平均 ACC 从 64.5030% 降至 61.7008%。该运行检测到 517 次 MLP total-shift 格式错误；为完成诊断，非法组按 RTL 置零语义处理。因此这些数值描述的是 `invalid_format_error` 状态下的质量，不能作为部署签核结果。

> 上述一段仅描述已经废止的 format-v2。其后的历史 format-v3 在 matched `hardware_128` 全量 WikiText-2 上，MLP-only 与 Full V5 PPL 分别为 27.801928 和 27.639944；MLP-only 的 20,251 次 `down_proj` 输出饱和和 layer 31 的 587.87 参考峰值共同证明 S24/F16 末端边界不足。该失败结果只用于定位问题，不代表最终候选。

> 最终 `0x48384605` 候选采用 Gate/Up S37/S44→S24/F16、SwiGLU S32/F16、Down `[12,44]` 和 S45/S54→S32/F16。在相同 `hardware_128` 口径下，MLP-only PPL 为 18.452719（相对 BF16 +7.230%），六任务 Macro ACC 为 74.6469%（-0.7384 pp）；Full V5 PPL 为 18.555656（+7.828%），Macro ACC 为 74.6364%（-0.7489 pp）。两组结果均满足预注册门槛，所有候选 format、guard、accumulator、SwiGLU 与末端输出饱和计数为 0。因此当前算法与冻结数据位宽的软件精度结论为 PASS。

---

## 22. 建议的论文图表

### 图 1：两级激活格式

必须把两种“定点激活”画成不同颜色或不同层级：

~~~text
FP32 RMSNorm
    │ boundary quantization, fixed Delta=2^-16
    ▼
S24 Q8.16
    │ integer H32
    ▼
S27 Q11.16
    │ online Group32 requantization
    ▼
U8 + {shift6,code8,zp8}
    │ integer A8W8/A8W4 MAC
    ▼
fixed-point output
~~~

### 图 2：Hadamard 与 weight folding

图中应同时画：

~~~text
x ──T──► x_h ───────────┐
                         ├──► x_h W_h^T
W ──offline W×T──► W_h ─┘

T T^T = I
~~~

不能只画激活 Hadamard 而遗漏权重 folding，否则读者会质疑线性语义改变。

### 图 3：三类整数尺度恢复不能合并画成一条线

图 3a 画 Linear 双 ScaleCode 恢复：

~~~text
Attention: U8/S8 → S16…S21 → S37 → S42 Q18.24
           → S42 Q18.24/128 groups → S24 Q8.16

Gate/Up:  U8/S4 → S12…S17 → S33 → S37 Q13.24
           → S44 Q20.24/128 groups → S24 Q8.16

Down:     U8/S4 → S12…S17 → S33 → S37 Q13.24
           → S46 Q22.24/448 groups → S24 Q8.16
~~~

图 3b 单独画 QK：

~~~text
Q S24 × K S12 → S35…S40 → ×K_code S48
→ ×5793 S61 → S35 Q21.14
→ S37 Q23.14/4 groups → clip S20 Q6.14
~~~

图 3c 单独画 PV：

~~~text
V S12 × V_code → S20 → ×prob U0.16 → S36
→ S36 Q12.24 → S43 Q19.24/128 keys
→ S24 Q8.16 context
~~~

### 表 1：数值格式

直接使用第 3.3 节的格式表，并在表注中写明 Q 命名约定。

### 表 2：证据分层

直接使用第 13.3 节，防止审稿人把 QDQ、activation frontend 和 full FPGA 混为一谈。

---

## 23. 复现入口

### 23.1 FPtoQ 单元测试

~~~bash
cd /home/user/EDA-202/zhuowenjun

PYTHONPATH=ScaleLLM/0_Software/FPtoQ/experiment \
/home/user/anaconda3/bin/python \
ScaleLLM/0_Software/FPtoQ/experiment/test_fptoq_core.py
~~~

当前实际结果：

~~~text
Ran 8 tests
OK
~~~

旧 `FPtoQ/results/REPORT.md` 中“7 tests”的文字已过期，本报告以实际 8 项为准。

V5 full-chain 当前定义 15 项 CUDA integer-twin conformance tests：

~~~bash
cd /home/user/EDA-202/zhuowenjun

PYTHONPATH=ScaleLLM/0_Software/FPtoQ/experiment \
/home/user/anaconda3/bin/python \
ScaleLLM/0_Software/FPtoQ/experiment/test_v5_fullchain.py -q
~~~

本轮全量 ACC 已按用户指令停止，原 finalizer 也已终止，因此 15 项 CUDA 套件
尚未执行；当前 CPU/RTL/Host 七个 suite 共 `42/42` PASS，不能用旧版 `Ran 10 tests`
替代最终 `15/15` CUDA 证据。这些测试即使全部通过，也只证明选定整数算术与
软件 twin 的局部一致性，不等于完整模型质量通过。

### 23.2 Llama-3.1-8B-Instruct PPL 前端 A/B

~~~bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/FPtoQ

PYTHON_BIN=/home/user/anaconda3/bin/python \
MODEL_PATH=/home/user/EDA-202/zhuowenjun/fpga_llm_project/configs/models/Llama-3.1-8B-Instruct \
MODEL_TAG=llama3.1-8b-instruct \
DEVICE=cuda:0 \
bash experiment/run_reproduction.sh ppl
~~~

将最后的 `ppl` 改为 `capture` 可执行真实激活捕获与误差分析。

### 23.3 Llama V5 production 全链路历史 format-v2 重跑

下列 BF16/V5 使用相同的 128-context 与 first-300 ACC 口径。V5 最大只支持 128 keys；`--allow-format-errors` 会按 RTL zero-guard 语义继续并将最终状态标为无效，不能省略该状态说明。

~~~bash
cd /home/user/EDA-202/zhuowenjun

/home/user/anaconda3/bin/python \
ScaleLLM/0_Software/FPtoQ/experiment/run_v5_fullchain_eval.py \
  --case bf16 --device cuda:0 \
  --tasks wikitext2,piqa,arc_challenge,openbookqa,hellaswag,winogrande \
  --wikitext-max-tokens 65536 --wikitext-batch-size 16 \
  --max-mcqa-samples 300 --mcqa-batch-size 32 \
  --output ScaleLLM/0_Software/results/v5_fullchain/Llama-3.1-8B-Instruct

/home/user/anaconda3/bin/python \
ScaleLLM/0_Software/FPtoQ/experiment/run_v5_fullchain_eval.py \
  --case v5 --allow-format-errors --device cuda:0 \
  --tasks wikitext2,piqa,arc_challenge,openbookqa,hellaswag,winogrande \
  --wikitext-max-tokens 65536 --wikitext-batch-size 16 \
  --max-mcqa-samples 300 --mcqa-batch-size 32 \
  --output ScaleLLM/0_Software/results/v5_fullchain/Llama-3.1-8B-Instruct
~~~

上述命令与输出目录仅用于复现已经废止的 format-v2。其严格模式会在最后一层
`down_proj` 的 total shift 20 处停止；后续历史 format-v3 曾把合法范围扩为
`[20,44]`，但又因 Down S24/F16 饱和而失败。最终 `0x48384605` 已进一步把 Down
范围扩为 `[12,44]`，采用 S45/S54→S32/F16，并完成全量 ACC/PPL 和零异常签核。
历史 format-v3 的 Attention-only、MLP-only、Full V5 入口分别由
`fix_experiment/exp/run_eval_worker.py` 和
`fix_experiment/exp/run_llama31_v5_real_inference.sh` 驱动，结果统一写入
`fix_experiment/results/llama31_rope_softmax_fixedpoint_hardware128_v3`；不得把该目录
与历史 `0_Software/results/v5_fullchain/...` 的 1,499 条 first-300 记录混合并表。
最终候选的机器可读汇总位于
`fix_experiment/results/s32_candidate_validation/final_validation_summary.json`。

### 23.4 归档算法单模型重跑

在 `ScaleLLM/0_Software` 下：

~~~bash
bash experiment/run_final_scalecode.sh acc  ../../fpga_llm_project/configs/models/Qwen3-8B
bash experiment/run_final_scalecode.sh ppl  ../../fpga_llm_project/configs/models/Qwen3-8B
bash experiment/run_final_scalecode.sh gsm8k ../../fpga_llm_project/configs/models/Qwen3-8B Qwen3-8B fair eager
~~~

GSM8K 历史并表不能假定由一条统一命令逐 bit 重现。

### 23.5 派生数字的最小复算

第 12.3 节 no-H/H 局部重构使用 `activation_groups.npz` 中的 `groups` 数组，命令如下：

~~~bash
cd /home/user/EDA-202/zhuowenjun

PYTHONPATH=ScaleLLM/0_Software/FPtoQ/experiment \
/home/user/anaconda3/bin/python - <<'PY'
import numpy as np
from fptoq_core import software_a8_qdq, software_hadamard

with np.load(
    "ScaleLLM/0_Software/FPtoQ/results/"
    "llama3.1-8b-instruct/activation_groups.npz"
) as z:
    raw = z["groups"].astype(np.float64)

had = software_hadamard(raw)

def measure(x):
    dq = software_a8_qdq(x).dq
    rmse = np.sqrt(np.mean((dq - x) ** 2))
    span = np.mean(
        np.maximum(x.max(axis=1), 0)
        - np.minimum(x.min(axis=1), 0)
    )
    return float(rmse), float(span)

r = measure(raw)
h = measure(had)
print("raw:", r)
print("had:", h)
print("relative_pct:",
      tuple((h[i] / r[i] - 1) * 100 for i in range(2)))
PY
~~~

预期输出：

~~~text
raw: (0.0016932067688886748, 0.9941688764374703)
had: (0.0013963001288901894, 0.8508252157223075)
relative_pct: (-17.535167320017166, -14.418441787156333)
~~~

第 11.5 节的 RMSNorm gamma 最大值直接从本地 Llama checkpoint 复算：

~~~bash
cd /home/user/EDA-202/zhuowenjun

/home/user/anaconda3/bin/python - <<'PY'
from pathlib import Path
import json
from safetensors import safe_open

root = Path(
    "fpga_llm_project/configs/models/Llama-3.1-8B-Instruct"
)
weight_map = json.loads(
    (root / "model.safetensors.index.json").read_text()
)["weight_map"]

for suffix in (
    "input_layernorm.weight",
    "post_attention_layernorm.weight",
):
    rows = []
    for name, shard in weight_map.items():
        if name.endswith(suffix):
            with safe_open(root / shard, framework="pt", device="cpu") as f:
                rows.append(
                    (name, float(f.get_tensor(name).abs().max()))
                )
    print(
        suffix,
        len(rows),
        max(v for _, v in rows),
        max(rows, key=lambda x: x[1]),
    )
PY
~~~

预期输出的前三列为：

~~~text
input_layernorm.weight 32 1.4140625
post_attention_layernorm.weight 32 1.375
~~~

乘以 `sqrt(4096)=64` 后，对应第 11.5 节的解析范围界 `90.5` 与 `88.0`。末列还会打印取得最大值的具体 tensor 名称，便于审计。

---

## 24. 源码与证据索引

### 24.1 软件算法

- [Hadamard、folding、ScaleCode、A8/W8 QDQ](../experiment/scripts/scale_code_linear/scalepath4_method_inference.py)
- [Attention W8 / MLP W4 路由](../experiment/scripts/accuracy_MLP_4bit/mlp4_method_inference.py)
- [归档算法说明](../introduction/01_final_scalecode_algorithm.md)
- [复现说明](../introduction/03_reproduction_guide.md)

### 24.2 硬件对齐模型

- [V5 cohort16 production source manifest](../../vivado/manifests/attention_mlp_production_v5_cohort16_sources.list)
- [NumPy bit-exact FPtoQ core](../FPtoQ/experiment/fptoq_core.py)
- [Torch software/pre-Q/RTL frontend adapter](../FPtoQ/experiment/torch_frontend.py)
- [8 项前端单元测试](../FPtoQ/experiment/test_fptoq_core.py)
- [Llama V5 production 全链路数字孪生](../FPtoQ/experiment/v5_fullchain.py)
- [V5 ACC/PPL 评测入口](../FPtoQ/experiment/run_v5_fullchain_eval.py)
- [10 项 V5 scalar golden conformance tests](../FPtoQ/experiment/test_v5_fullchain.py)
- [V5 分片结果审计合并工具](../FPtoQ/experiment/merge_v5_fullchain_shards.py)
- [Host S24 pack/unpack 与 RMSNorm](../../host/scalellm_hostops.py)
- [canonical integer arithmetic model](../../model/fixbit_v2.py)
- [MLP fixed SiLU、乘积与 S32 Down 输入模型](../../model/mlp_fixed.py)
- [production weight artifact exporter](../../model/export_scalellm_llama31_artifacts.py)
- [Hadamard/在线 MinMax 硬件说明](../../introduction/02_hadamard_online_quantization.md)
- [S24→S27 Hadamard32 RTL](../../rtl/attention/hap_hadamard32_norm_stream.sv)
- [S32→S35 Down Hadamard32 RTL](../../rtl/mlp/hap_mlp_hadamard32_s32_norm_stream.sv)
- [S27 MinMax A8 RTL](../../rtl/attention/hap_robust_a8_quantizer.sv)
- [S35 MinMax A8 RTL](../../rtl/mlp/hap_mlp_robust_a8_quantizer_s35.sv)
- [A8W8 Group32 ScaleCode RTL](../../rtl/attention/hap_a8w8_group32_lane_s42.sv)
- [A8W4 Group32 ScaleCode RTL](../../rtl/mlp/hap_a8w4_group32_lane2_s37.sv)
- [Attention V5 dual-wave S42 accumulator RTL](../../rtl/attention/hap_linear_tile_accum_dual_s42.sv)
- [MLP V5 S44/S46 tile accumulator RTL](../../rtl/mlp/hap_mlp_tile_accum_s37.sv)
- [Down S46 accumulator RTL](../../rtl/mlp/hap_mlp_down_group_major_accum_s46.sv)
- [KV12 quantizer and meta16 RTL](../../rtl/attention/hap_kv12_quantizer.sv)
- [QK S24×S12→S40 dot RTL](../../rtl/attention/hap_q24k12_group_dot_s40.sv)
- [QK S48→S61→S35 scale RTL](../../rtl/attention/hap_score_group_scale_s35.sv)
- [QK four-group S37→S20 accumulator RTL](../../rtl/attention/hap_score_accum4_s20.sv)
- [PV S20→S36→S43→S24 RTL](../../rtl/attention/hap_pv_tile16_s43.sv)

### 24.3 结果

- [Llama 文献对齐 Reference-QDQ 全量 manifest](../fix_experiment/results/algorithm_reference_full/reference_qdq_literature_2048/merged/manifest.json)
- [Llama 文献对齐 Reference-QDQ 逐任务结果](../fix_experiment/results/algorithm_reference_full/reference_qdq_literature_2048/merged/summary.csv)
- [Llama Reference-QDQ 与 BF16-2048 matched 差值](../fix_experiment/results/algorithm_reference_full/paper_summary.csv)
- [12 模型 ACC 汇总](../results/_summary/final_accuracy_comparison.csv)
- [12 模型 PPL 汇总](../results/_summary/final_scalecode_ppl_wikitext2.csv)
- [12 模型结果来源清单](../results/_summary/source_manifest.csv)
- [ACC 原始观测并表审计](../results/_summary/accuracy_raw_observed_merge_audit.csv)
- [GSM8K 保留结果审计](../results/_summary/accuracy_gsm8k_kept_audit.csv)
- [12 模型结果说明](../introduction/02_final_acc_ppl_results.md)
- [Llama FPtoQ 报告](../FPtoQ/results/llama3.1-8b-instruct/REPORT.md)
- [Llama activation error summary](../FPtoQ/results/llama3.1-8b-instruct/analysis/summary.csv)
- [Llama PPL A/B](../FPtoQ/results/llama3.1-8b-instruct/ppl_full/comparison.csv)
- [Llama `rtl_exact` 全量计数与饱和审计](../FPtoQ/results/llama3.1-8b-instruct/ppl_full/rtl_exact.json)
- [Llama V5 全链路任务汇总](../results/v5_fullchain/Llama-3.1-8B-Instruct/v5/quality_by_task.csv)
- [Llama matched BF16 任务汇总](../results/v5_fullchain/Llama-3.1-8B-Instruct/bf16/quality_by_task.csv)
- [Llama V5 全链路审计 manifest](../results/v5_fullchain/Llama-3.1-8B-Instruct/v5/manifest.json)
- [Llama V5 全链路逐题记录](../results/v5_fullchain/Llama-3.1-8B-Instruct/v5/mcqa_records.jsonl)
- [Llama matched BF16 全链路审计 manifest](../results/v5_fullchain/Llama-3.1-8B-Instruct/bf16/manifest.json)
- [Llama format-v3 可复核精度报告](../fix_experiment/results/llama31_rope_softmax_fixedpoint_hardware128_v3/precision_validation_report.md)
- [Llama format-v3 位宽问题登记](../fix_experiment/results/llama31_rope_softmax_fixedpoint_hardware128_v3/width_findings.csv)
- [Llama format-v3 RTL/Host/software 合同审计](../fix_experiment/results/llama31_rope_softmax_fixedpoint_hardware128_v3/format_v3_contract_audit.json)
- [Llama format-v3 验证工作簿](../fix_experiment/results/llama31_rope_softmax_fixedpoint_hardware128_v3/ScaleLLM_Llama31_format_v3_validation.xlsx)
- [Llama format-v3 完成度审计](../fix_experiment/results/llama31_rope_softmax_fixedpoint_hardware128_v3/validation_completion_audit.json)
- [Qwen activation error summary](../FPtoQ/results/qwen2.5-0.5b/analysis/summary.csv)
- [Qwen PPL A/B](../FPtoQ/results/qwen2.5-0.5b/ppl_full/comparison.csv)
- [Qwen `rtl_exact` 全量计数与饱和审计](../FPtoQ/results/qwen2.5-0.5b/ppl_full/rtl_exact.json)
- [合成正向/负向 probe](../FPtoQ/results/synthetic/summary.csv)
- [Llama full-layer Hadamard/raw ratio](../../../fpga_llm_project/results/All_results/ScalaPATH_4/S11_llama31_instruct_fullscan/fullscan_20260630_111830/numeric_runs/Llama-3.1-8B-Instruct/g32_b8/S3_scale_code_encodability/ratio_iah_vs_raw.csv)

---

## 25. 最终结论

ScaleLLM 的数值设计应被理解为“**高精度定点边界 + Hadamard 条件化 + 低比特动态分组量化 + 整数 ScaleCode 恢复**”，而不是一次简单的 FP→S24 Q8.16 转换。

对当前最关心的 Llama-3.1-8B-Instruct：

- 纯算法 Reference-QDQ 已按论文标准完成六项 full-split ACC 和 WikiText-2 2048 全量 PPL，Macro ACC 相对 BF16 下降 `0.780 pp`，PPL 相对增加 `5.809%`；
- S24 Q8.16 的小数精度有严格舍入界；
- 两类 Host RMSNorm ingress 的动态范围可由 checkpoint 参数严格界定在 ±128 内；
- 理想归一化 Hadamard 保持入口误差的 L2 能量；HC-v2 的 `alpha<1` 线性部分与末级舍入误差已另行计界；
- 真实 trace 中前端误差远低于 A8 量化误差；
- 固定前 65,536 个输入 token、65,472 个计分 token 的 64-window evaluation slice 上，前端 A/B 数值持平且未观测到入口或 Hadamard 饱和。

S24 并未使 Hadamard 的动态范围条件化作用变得冗余：S24 只是固定二进制点的高精度表示，真正进入 MAC 的 U8 仍需动态分组 scale；Hadamard 的目标是降低该 A8 scale 受离群通道支配的程度。现有 trace 和局部重构支持这一独立作用，但尚不足以证明端到端不可替代。激活动态 scale 与权重静态 scale 的 metadata 均为整数 code/shift，其解码值是逐组二进制有理数，所以硬件后续不需要显式浮点反量化。

与此同时，S24 并非免费：它比 BF16 多 50% 的边界流量，并有尚未纳入计时的 Host pack/unpack。新的 Reference-QDQ 全量结果证明算法本身可以在标准口径下保持有限退化，但 Reference-QDQ 与 production shift6/weight bytes/整数 MAC 仍存在实现差异；V5 full-chain twin 只对 Llama-3.1-8B-Instruct 补齐了这条 production 路径。旧 format-v3 的 Down-S24 动态范围失败已由最终 `0x48384605` 软件候选修复；代价是 Down 内部 S45/S54 和外部 S32/C2H 256 KiB，不能继续沿用旧 S37/S46/S24 ABI。

当前最重要的结论是：**ScaleLLM 算法以及 `0x48384605` 冻结的各节点数据位宽，已经在软件数字孪生中通过精度测试；尚待完成的是硬件实现迁移与实板回归，而不是继续猜测位宽是否足够。** 同时必须把算法级、前端级、全链路软件级和实板级证据明确分开：

> 算法优先的文献对齐复测表明，Llama-3.1-8B-Instruct 的 Hadamard32–Group32 A8、Attention W8、MLP W4、ScaleCode Reference-QDQ 相对 matched BF16 的六任务 Macro ACC 下降 0.780 pp，WikiText-2 2048 PPL 增加 5.809%，因此可以主张算法退化有限，但不能主张数学无损。在未饱和条件下，可以严格界定 S24 Q8.16 入口误差；前端隔离 A/B 也支持 S24/整数 Hadamard 数值持平。production 数值孪生进一步证明最终 `0x48384605` 候选（Gate/Up `[20,44]`、S37/S44→S24/F16，SwiGLU S32/F16，Down `[12,44]`、S45/S54→S32/F16）的 MLP-only PPL/Macro ACC 变化为 `+7.230%/-0.7384 pp`，Full V5 为 `+7.828%/-0.7489 pp`，且所有候选异常计数为 0。因此算法和冻结数据位宽的软件精度签核结论均为 PASS。真实硬件实现仍不能签核；RTL/DMA/Host 必须完成 `0x48384605` 迁移并把当前 `4/15` 审计提升到全通过。
