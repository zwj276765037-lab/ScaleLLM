# 【P0 紧急修改通知】Hadamard 后在线 A8 激活量化须移除 Robust Clipping，并按 Group32 原始 Min/Max 重新核实

> 发布日期：2026-09-10  
> 状态：待硬件、算法、软件三方确认并完成修改  
> 接收方：Attention、MLP、量化器 RTL、验证、模型评测负责人  
> 适用工程：`ScaleLLM` 当前生产 RTL、Python golden、测试向量及由其产生的综合/仿真结果

## 1. 通知结论

经对最终模型量化代码、现有硬件 RTL、Python golden 和模块实验记录进行交叉核对，当前硬件在线激活量化与最终模型量化基线不一致：

- **最终模型基线**：Hadamard 之后，以每个 row 内连续 **32 个激活为一组**，执行 **8-bit unsigned asymmetric Min/Max 量化**；原始组内最小值和最大值必须参与区间计算，**不进行 percentile、MSE-search、最大/次大插值或任何量化前裁剪**。
- **当前硬件/旧 golden**：先用最大与次大绝对值计算 `abs_threshold` 并裁剪一次，再用最小/次小、最大/次大插值得到 `clip_low/clip_high` 并裁剪第二次，最后才生成 scale、zero-point 和 U8。

这会改变激活值、量化区间、scale、zero-point、U8 code，以及后续 Q/K/V/O、Gate/Up/Down projection 的数值。该问题不是允许的定点近似，而是**量化算法定义发生了变化**。

因此，本问题按 **P0 / 阻断最终数值正确性签核** 处理。请立即执行以下动作：

1. 暂停把当前 robust-clipping 版本的仿真 `PASS`、综合结果或模块报告作为最终算法正确性证据。
2. 确认当前综合、实现或计划上板的版本是否包含本文列出的量化器；若包含，必须进入修改范围。
3. 将 Hadamard 后在线 A8 激活量化改为本文第 3 节定义的 group32 原始 Min/Max 规则。
4. 同步更新独立软件 golden、测试向量、`.mem`、模块回归和端到端模型评测。
5. 完成第 8～10 节的核实与联合签字后，方可恢复数值正确性签核。

## 2. 问题性质与边界

本通知针对的是 **Hadamard 输出到 A8 之前额外加入的统计裁剪**，不是要求删除系统中所有形式的 clamp 或 saturation。

### 必须删除或旁路

- 根据最大、次大绝对值生成 robust absolute threshold；
- 将原始 Hadamard 输出预先限制到 `±abs_threshold`；
- 根据最小/次小及最大/次大插值生成 percentile-style `clip_low/clip_high`；
- 在量化前将每个 lane 再限制到 `[clip_low, clip_high]`；
- 任何以“抑制离群值”“改善 robust range”或“适配 ScaleCode 范围”为目的、但没有写入最终模型量化合同的隐式裁剪。

### 必须保留

- Hadamard 蝶形、`1/sqrt(32)` 归一化及其既定定点位宽；
- Hadamard 运算自身从更宽中间结果饱和到 S27/S35 的既定数值规则；
- U8 最终合法码域的 `clamp(0, 255)`；
- ScaleCode/metadata 的接口格式、cache/ready-valid 协议及必要的定点防溢出逻辑；
- projection 累加器和输出位宽边界处原本定义的饱和；
- 离线权重量化。权重的 **8-bit signed symmetric、group32、absmax** 规则不属于本次错误。

换言之：**删除的是量化范围确定之前对有效激活数据做的算法性裁剪，不是删除数值格式边界所必需的最终饱和。**

## 3. 修改后的唯一算法合同

### 3.1 输入与分组

- 输入必须是已经完成 Hadamard32 和归一化后的值；
- 每个 row 中连续 32 个数构成一个独立 group；
- 不得跨 row、跨 group 共享或复用 min、max、scale、zero-point；
- S27 路径和 S35 路径使用相同量化语义，仅输入位宽不同。

设一个 group 的 32 个**原始 Hadamard 输出**为：

```text
x[0], x[1], ..., x[31]
```

### 3.2 原始 Min/Max 范围

```text
group_min = min(x[0:31])
group_max = max(x[0:31])

low  = min(group_min, 0)
high = max(group_max, 0)
diff = high - low
```

把 0 强制包含在范围中是最终软件参考的一部分：

- 全正 group：`low = 0`，`high = group_max`；
- 全负 group：`low = group_min`，`high = 0`；
- 正负混合 group：`low = group_min`，`high = group_max`；
- 全零 group：`low = high = diff = 0`。

这里的 `group_min/group_max` 必须直接来自原始 group32，不能来自任何被阈值修改后的副本。

### 3.3 A8 unsigned asymmetric 量化

数学基准为：

```text
qmin  = 0
qmax  = 255
scale = (high - low) / 255
zp    = round(-low / scale), clamped to [0, 255]
q[i]  = round(x[i] / scale + zp), clamped to [0, 255]
```

全零 group 使用约定的零输出：

```text
q[0:31] = 0
metadata = 0
```

非零 group 继续将 scale 编码为现有 `scale_code + scale_shift` metadata。metadata 位域如接口不变，仍为：

```text
{reserved[1:0], scale_shift[5:0], scale_code[7:0], zero_point[7:0]}
```

### 3.4 明确禁止的量化前处理

在 `group_min/group_max` 扫描前后，均不得执行以下操作：

```text
x[i] = clamp(x[i], -abs_threshold, +abs_threshold)
x[i] = clamp(x[i], clip_low, clip_high)
range = percentile(x)
range = mse_search(x)
range = function(max1, max2, min1, min2)
```

如果一个 group 中只有一个很大的正或负离群值，该离群值仍然必须成为该 group 的真实 `high` 或 `low`。精度是否受离群值影响属于模型算法选择，硬件不能自行用裁剪替换 Min/Max 合同。

## 4. 已确认的当前偏差

### 4.1 生产 RTL 中存在两阶段裁剪

当前以下两个量化器均包含 robust clipping：

- `rtl/attention/hap_robust_a8_quantizer.sv`
- `rtl/mlp/hap_mlp_robust_a8_quantizer_s35.sv`

两者定义了相同常量：

```text
ABS_Q9999_Q16 = 65333
CLIP_Q001_Q16 = 2032
CLIP_Q999_Q16 = 63504
```

并通过以下状态执行 absolute threshold、二次范围统计和边界插值：

```text
ST_ABS_SCAN
ST_ABS_THR_DIFF
ST_ABS_THR_MUL
ST_ABS_THR_CAPTURE
ST_CLIP_SCAN
ST_CLIP_DRAIN
ST_BOUNDS_MUL
ST_BOUNDS_CAPTURE
```

最终在 `ST_QUANT_PREP` 中又将 lane 限制到 `clip_low_r/clip_high_r`。这不是单纯保护输出 U8 范围，而是在量化前实际改变输入及动态范围。

### 4.2 Python golden 也固化了相同错误语义

以下 golden 函数复制了相同的两阶段裁剪：

- `model/fixbit_v2.py` 中的 `robust_a8_quantize()`；
- `model/mlp_fixed.py` 中的 `robust_a8_quantize_s35()`。

多个 projection、MLP 以及 ModularExperiment 向量生成器直接调用上述函数。因此，现有“RTL 对 golden bit-exact PASS”可能只是证明两端实现了同一个错误算法，不能证明与最终模型基线一致。

至少以下类型的向量需要重新生成：

- Attention input / QKV projection；
- Attention context / O projection；
- MLP input / Gate-Up projection；
- SwiGLU product / Down projection；
- 所有间接调用 `robust_a8_quantize()` 或 `robust_a8_quantize_s35()` 的 `.mem`、trace 和回归向量。

### 4.3 最终模型参考代码没有裁剪

最终参考位于：

```text
fpga_llm_project/scripts/scale_code_linear/scalepath4_method_inference.py
```

其中激活路径在 Hadamard 后直接执行：

```python
xmin = torch.minimum(xg.amin(dim=-1), torch.zeros((), device=x.device))
xmax = torch.maximum(xg.amax(dim=-1), torch.zeros((), device=x.device))
scale = ((xmax - xmin) / 255.0).clamp_min(1e-12)
zp = torch.round(-xmin / scale).clamp(0, 255)
q = torch.round(xg / scale.unsqueeze(-1) + zp.unsqueeze(-1)).clamp(0, 255)
```

该路径没有 percentile、MSE-search、最大/次大插值或量化前 clip。

## 5. 一个可以直接复核的反例

现有说明文档中的同一组 S27 Hadamard 输出已经能证明偏差。该组包含：

```text
group_min = -2965760
group_max =  5746160
```

### 当前 robust-clipping 实现

```text
5746160 先被 absolute threshold 裁为 5737547
clip_low  = -2919783
clip_high =  5559649
diff      =  8479432
```

之后原始最大值和最小值在 `ST_QUANT_PREP` 中分别被限制到 `5559649` 和 `-2919783`。

### 正确 Min/Max 实现

```text
low  = min(-2965760, 0) = -2965760
high = max( 5746160, 0) =  5746160
diff = 8711920
```

正确实现中，`5746160` 和 `-2965760` 不得在量化前被改写。该向量必须加入强制回归，并要求旧实现失败、新实现通过。

## 6. 已识别的硬件影响范围

| 数据路径 | Hadamard 输出 | 当前量化器 | 已发现的生产实例 |
|---|---:|---|---|
| Attention input → Q/K/V | S27 | `hap_robust_a8_quantizer` | `rtl/attention/hap_attention_frontend_8row.sv` |
| Attention context → O | S27 | `hap_robust_a8_quantizer` | 请硬件负责人核对 O 前端实际集成层级 |
| MLP input → Gate/Up | S27 | `hap_robust_a8_quantizer` | `rtl/mlp/hap_mlp_input_frontend16_compact_cache.sv` |
| SwiGLU product → Down | S35 | `hap_mlp_robust_a8_quantizer_s35` | `rtl/mlp/hap_mlp_product_frontend16_q4.sv`、`rtl/mlp/hap_mlp_swiglu_product_frontend16_q4.sv` |

请不要只修改 Attention 中的一份实例。必须从模块定义、所有实例化点、综合 source list、仿真 source list、复制的 legacy RTL 以及已生成 IP/OOC 工程逐项搜索并确认。

已有实验还记录了实际发生裁剪的 lane 数：

- Attention input 实验：`2,031` 个 clip lanes；
- MLP input 实验：`4,087` 个 clip lanes。

这说明裁剪路径不是不可达的死代码，而是已经改变了真实测试数据。

对应记录：

- `ModularExperiment/result/01_attention_input_hadamard_a8/SUMMARY.md`
- `ModularExperiment/result/08_mlp_input_hadamard_a8/SUMMARY.md`

## 7. RTL 修改要求

### 7.1 范围扫描

对捕获的 32 个原始值只扫描一次真实最小值和最大值：

```text
raw_min = min(all 32 original lanes)
raw_max = max(all 32 original lanes)
low     = min(raw_min, 0)
high    = max(raw_max, 0)
diff    = high - low
```

S27 路径的差值需要能够表示完整 S27 有符号动态范围；S35 路径同理。必须检查减法前的符号扩展和差值寄存器位宽，不能因溢出而产生隐式范围缩小。

### 7.2 状态机

可以重构或旁路第 4.1 节列出的 robust 状态，但修改后必须满足：

- `ABS_Q9999_Q16`、`CLIP_Q001_Q16`、`CLIP_Q999_Q16` 不再影响任何功能输出；
- scale 生成直接接收 `high-low`；
- zero-point 直接由 `low` 和目标 scale 产生；
- U8 量化读取原始 group memory，而不是 `clipped_mem` 或其等价数据；
- `ST_QUANT_PREP` 不得再按统计边界改写 lane；
- 吞吐、backpressure、输入输出计数、reset、error/format counter 行为要重新验证。

模块名可暂时保持不变以降低集成风险，但如果继续使用 `robust` 命名，必须在代码与文档中明确其功能已经是 Min/Max，避免后续人员误恢复裁剪。推荐后续统一重命名为 `*_minmax_a8_quantizer*`，重命名本身不应阻塞本次功能修复。

### 7.3 ScaleCode 可表示范围

移除裁剪后，`diff` 可能大于旧 robust 路径产生的差值。S35 路径尤其需要核对 `scale_code[7:0] + scale_shift[5:0]` 是否覆盖完整有效输入范围。

如果出现无法表示的合法 Min/Max 范围：

1. 必须显式报出向量、输入范围和 metadata 上限；
2. 由算法、软件、硬件三方决定扩大编码或规定异常处理；
3. **不得为了通过现有 ScaleCode 范围而静默恢复裁剪。**

## 8. 两项必须同步澄清的 bit-exact 合同

以下问题与“移除 clipping”相互独立，但会影响逐 bit 一致性，必须在本次联合核实中签字确认。

### 8.1 舍入规则

最终 PyTorch 参考使用 `torch.round`；当前定点 RTL/Golden 的若干路径采用加半后截断或 round-half-away-from-zero。对恰好位于 `n+0.5` 的正数、负数、zero-point 和 U8 quotient，结果可能不同。

必须建立专门的 half-tie 向量，明确以下每一处的舍入方式：

- Hadamard 归一化；
- ideal scale 到 ScaleCode；
- zero-point；
- 每 lane U8；
- 反量化或 projection 尺度恢复。

### 8.2 原始 scale 与解码 ScaleCode 的使用位置

最终模型参考目前使用原始 Min/Max scale 生成 `zp/q`，再使用 decoded ScaleCode 做反量化；当前硬件倾向于直接使用 encoded/decoded ScaleCode 比值生成 `zp/q`。这可能造成额外的 1-LSB 差异。

请三方明确并冻结以下唯一合同：

```text
zp 和 q 是基于 ideal MinMax scale，还是基于 decoded ScaleCode scale？
```

在该问题未决前，至少应保证两种候选都使用**同一组未经裁剪的 low/high**，并分别报告差异，不能把 ScaleCode 近似误差和 clipping 误差混为一类。

## 9. 强制验证矩阵

### 9.1 量化器单元测试

S27 和 S35 两套量化器都必须覆盖：

| 用例 | 必查结果 |
|---|---|
| 32 个全零 | U8 全零、metadata 零、无异常状态 |
| 32 个相同正数 | `low=0`、`high=该正数`，不得认为 range 为零 |
| 32 个相同负数 | `low=该负数`、`high=0`，不得认为 range 为零 |
| 单个正离群点，其余小值/零 | 离群点必须等于 `high`，不得被改写 |
| 单个负离群点，其余小值/零 | 离群点必须等于 `low`，不得被改写 |
| 正负高度不对称 | low/high、zp、U8 逐 lane 核对 |
| 最大值或最小值重复 | 结果只能由真实 Min/Max 决定，不得受次大/次小排序影响 |
| S27 边界及边界附近 | 符号扩展、diff 位宽、scale 编码、最终 U8 |
| S35 边界及边界附近 | diff/ScaleCode 可表示范围、错误处理、最终 U8 |
| 随机均匀/正态/重尾分布 | 对独立 Min/Max golden 逐 lane bit-exact |
| 真实模型 trace | low/high、metadata、32 个 U8 及下游 projection 输出 |
| 连续流与随机反压 | 数据、tag、metadata 不串组，计数一致 |

每个 group 至少记录并比较：

```text
raw_min
raw_max
low
high
diff
scale_code
scale_shift
zero_point
u8[0:31]
metadata
```

建议增加一个单独的 `pre_quant_clip_count` 或 assertion：正常设计中该计数必须恒为 0。它不能与最终 U8 `0/255` 合法饱和计数混用。

### 9.2 模块级回归

以下链路必须使用重新生成的、独立 Min/Max golden 完成逐 bit 回归：

1. Hadamard → A8 quantizer；
2. Attention input → Q/K/V projection；
3. Attention context → O projection；
4. MLP input → Gate/Up projection；
5. SwiGLU product → S35 A8 quantizer → Down projection；
6. cache 写入/读出、metadata 对齐、tag 和 backpressure。

golden 不得简单复制 RTL 里的状态机和常量。至少保留一份直接按第 3 节数学公式实现的独立参考，以避免 RTL 和 golden 同源错误再次产生“假 PASS”。

### 9.3 系统级回归

- 重新生成所有受影响 `.mem`、trace、manifest 和 checksum；
- 重跑所有曾引用 robust golden 的 XSIM/仿真；
- 对改后 RTL 重新综合并报告资源、时序、吞吐和 latency 变化；
- 在最终模型配置上重跑已签核测试集的 PPL/ACC；
- 将软件最终 Min/Max reference、修改后硬件仿真和修改前 robust 版本三者并列比较；
- 对 PPL/ACC 的任何变化给出模型、层、数据集和版本号，不能只给总平均值。

旧向量和旧结果必须标记为 `robust-clipping legacy`，避免与新 Min/Max 结果混用。

## 10. 验收标准

只有同时满足以下条件，才可关闭本问题：

- [ ] 已确认所有生产综合和仿真 source list，不存在遗漏的 robust 量化器副本；
- [ ] S27、S35 在线激活量化均从原始 group32 直接获得 `low/high`；
- [ ] 三个 robust 常量对功能输出不再有影响；
- [ ] 任意合法输入 lane 在量化前均未被 percentile/threshold 改写；
- [ ] 第 5 节反例显示 `low=-2965760`、`high=5746160`、`diff=8711920`；
- [ ] 单离群点测试证明真实离群点进入 Min/Max 范围；
- [ ] 独立 golden、RTL 的 low/high、scale metadata、zero-point 和 32 个 U8 完成 bit-exact 比较；
- [ ] 第 8 节的舍入与 ScaleCode 使用合同已书面确认；
- [ ] Attention QKV/O、MLP Gate/Up/Down 的模块回归全部通过；
- [ ] 所有受影响向量、`.mem`、manifest 和 checksum 已重新生成；
- [ ] PPL/ACC 或等效系统级结果已重跑并归档；
- [ ] 修改后综合的时序、资源、吞吐和 latency 已复核；
- [ ] 算法、软件、硬件、验证四方负责人完成签字。

## 11. 要求硬件部门回复的核实项

请硬件负责人按以下格式回复，避免只回复“已修改”或“仿真通过”：

```text
1. 当前已综合/计划上板的 commit：
2. 实际使用的 S27/S35 quantizer 文件及实例化点：
3. 是否确认存在 ABS_Q9999、Q001、Q999 两阶段裁剪：是/否
4. 修改 commit：
5. robust 状态/常量的处理方式：删除/旁路/其他（说明）
6. 原始 Min/Max 扫描实现及 diff 位宽：
7. S35 最大合法 diff 是否可由现有 ScaleCode 表示：
8. 舍入规则确认：
9. zp/q 使用 ideal scale 或 decoded ScaleCode：
10. 单元回归报告路径：
11. Attention/MLP 集成回归报告路径：
12. 新向量、mem、manifest/checksum 路径：
13. 修改后综合时序/资源/吞吐报告路径：
14. 剩余风险、未覆盖项和预计关闭时间：
```

## 12. 证据索引

### 最终 Min/Max 参考

- `fpga_llm_project/scripts/scale_code_linear/scalepath4_method_inference.py`：激活 Min/Max 约在 104～127 行；权重 symmetric absmax 约在 80～101 行。

### 当前 RTL

- `ScaleLLM/rtl/attention/hap_robust_a8_quantizer.sv`：robust 常量、状态机、边界生成及 `ST_QUANT_PREP` 裁剪。
- `ScaleLLM/rtl/mlp/hap_mlp_robust_a8_quantizer_s35.sv`：S35 对应实现。
- `ScaleLLM/rtl/attention/hap_attention_frontend_8row.sv`：S27 quantizer 实例。
- `ScaleLLM/rtl/mlp/hap_mlp_input_frontend16_compact_cache.sv`：MLP input 的 S27 quantizer 实例。
- `ScaleLLM/rtl/mlp/hap_mlp_product_frontend16_q4.sv`：S35 quantizer 实例。
- `ScaleLLM/rtl/mlp/hap_mlp_swiglu_product_frontend16_q4.sv`：S35 quantizer 实例。

### 当前软件 golden 与说明

- `ScaleLLM/model/fixbit_v2.py`：`robust_a8_quantize()`。
- `ScaleLLM/model/mlp_fixed.py`：`robust_a8_quantize_s35()`。
- `ScaleLLM/introduction/02_hadamard_online_quantization.md`：当前 robust 算法及数值示例；该文档需要在修改完成后同步改为 Min/Max 语义。
- `ScaleLLM/ModularExperiment/result/01_attention_input_hadamard_a8/SUMMARY.md`：Attention clip-lane 记录。
- `ScaleLLM/ModularExperiment/result/08_mlp_input_hadamard_a8/SUMMARY.md`：MLP input clip-lane 记录。

## 13. 最终提醒

本问题最容易出现的误判是：修改 Python golden 使其继续匹配 RTL，随后用 `PASS` 宣布问题关闭。正确的验收方向必须相反：

```text
最终模型 Min/Max 量化合同
        ↓
独立软件 reference
        ↓
RTL bit-exact 验证
        ↓
Attention/MLP 集成验证
        ↓
PPL/ACC 系统级确认
```

在这个链路中，不允许再以未签核的 robust clipping 作为共同基线。

## 14. 2026-09-10 硬件执行状态

用户已确认软件侧在线激活量化不存在量化前裁剪，硬件必须以最终软件 Min/Max 路径为
唯一合同。当前已完成第一阶段修复：

- ScaleLLM 与 HAP 的 S27/S35 生产量化器已删除 absolute-threshold、percentile bounds、
  `clipped_mem` 及相关状态，直接扫描原始 Group32；
- `zp/U8` 已改为 ideal Min/Max affine 表达式一次 ties-to-even 舍入，ScaleCode 仅用于
  下游恢复；24-bit metadata 与 ready/valid 接口不变；
- 独立 MinMax golden、通知反例、单离群点、正负/全零、half-tie 与 S27/S35 边界测试已建立；
- S27 128-group Attention projection 集成回归与 S35 64-vector/448-group 回归已通过，
  ScaleLLM 和 HAP 副本均完成短仿真核对；
- 旧 robust OOC 与 HAP 级联等待脚本已停止，旧综合/placement 结果只保留作 legacy 物理参考。

本问题尚未关闭：M02 Q/K/V、M09 Gate/Up 和 M12 L00/L15/L31 Down 的真实 ScaleCode
trace 已通过，仍需补齐其余受影响硬件链路并执行 fresh synth。软件 PPL/ACC 不重复执行，
直接采用 `0_Software` 的冻结结果与量化合同；placement、route、bitstream 和板测仍未启动。
