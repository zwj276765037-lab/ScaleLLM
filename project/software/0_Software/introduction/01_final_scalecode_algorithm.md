# 最终 ScaleCode 量化算法说明

## 1. 归档结论

本归档将历史最终方法统一命名为 `mlp_w4_scalecode`。其核心配置为：

| 项目 | 最终值 |
|---|---|
| Hadamard | 归一化 Hadamard32，`H / sqrt(32)` |
| group size | 32，沿线性层输入维/激活最后一维分组 |
| 激活 | A8，无符号非对称 MinMax |
| Attention 权重 | W8，有符号、零点为 0 的对称量化 |
| MLP 权重 | W4，有符号、零点为 0 的对称量化 |
| scale 编码 | 8-bit `code` + 8-bit `shift` |
| 量化范围搜索/裁剪 | 无 percentile、MSE、alpha 或校准式 clipping |

作用模块：

- Attention：`q_proj`、`k_proj`、`v_proj`、`o_proj`，使用 W8A8。
- MLP：`gate_proj`、`up_proj`、`down_proj`，使用 W4A8。
- GLM 融合层 `gate_up_proj` 按 MLP 使用 W4A8。
- `lm_head` 明确排除，不量化。

## 2. Hadamard 与线性层等价变换

代码先对激活最后一维按 32 点分块做右乘：

```text
x_h = x · H32
```

同时把线性层权重沿输入维折叠为对应的 `H32^T · W` 形式。若不量化，二者相乘仍与原线性层等价。Hadamard 只处理完整的 32 元素块；不足 32 的尾部保持原值。最终 12 个模型的主要线性维度均按 32 对齐。

## 3. 激活 A8：无符号非对称 MinMax

对 `x_h` 的最后一维每 32 个数为一组。每组先把 0 纳入表示区间：

```text
x_min = min(min(group), 0)
x_max = max(max(group), 0)
qmax  = 255
s_a   = max((x_max - x_min) / 255, 1e-12)
zp_a  = clamp(round(-x_min / s_a), 0, 255)
q_a   = clamp(round(x / s_a + zp_a), 0, 255)
```

随后将 `s_a` 编码为 ScaleCode，并用解码后的 `s_a_dec` 做反量化：

```text
x_dq = (q_a - zp_a) * s_a_dec
```

这里的动态范围就是当前组真实 MinMax；没有先按百分位、固定阈值或 alpha 截断激活。

## 4. 权重 W8/W4：有符号对称 MinMax

权重先完成 Hadamard folding，然后对每个输出通道沿输入维每 32 个数一组：

```text
s_w = max(max(abs(group)) / qmax, 1e-12)
q_w = clamp(round(w / s_w), -qmax - 1, qmax)
w_dq = q_w * s_w_dec
```

其中：

| 模块 | bits | `qmax` | 整数范围 |
|---|---:|---:|---:|
| Q/K/V/O | 8 | 127 | `[-128, 127]` |
| Gate/Up/Down | 4 | 7 | `[-8, 7]` |

权重零点固定为 0。若输入维不是 32 的整数倍，分组前在尾部补 0，反量化后再裁掉 padding。

## 5. ScaleCode 精确定义

最终实现对激活 scale 和 folded-weight scale 使用同一编码：

```text
code_max = 255
s_safe   = max(s, 1e-30)
shift    = clamp(floor(log2(255 / s_safe)), 0, 255)
code     = clamp(round(s_safe * 2^shift), 0, 255)
s_dec    = code * 2^(-shift)
```

必须注意：这里不是“总共 8 bit 的 scale”。`code` 是一个 `uint8`，`shift` 也以一个 `uint8` 保存，因此每个 scale 的逻辑 payload 是两个 8-bit 字段。量化整数 `q` 使用编码前的 MinMax scale 计算，反量化使用 `s_dec`。

## 6. 关于 clipping 的硬件核对要求

本最终软件基线没有额外的分布裁剪。代码中的两类 `clamp` 不能误解成算法新增 clipping：

1. `q` 限制到 INT8/INT4/UINT8 可表示范围，这是任何定点量化必需的整数饱和。
2. scale 的 `clamp_min` 只防止常数组或全零组除零。

硬件若在求 MinMax 前对激活或权重再做阈值裁剪，将不再等价于本软件基线，会改变 scale、零点、量化整数以及最终 ACC/PPL。硬件联调应逐组核对 `min/max -> raw scale -> zero point -> code/shift -> decoded scale -> q`。详细修正通知见 `../../introduction/00_URGENT_online_a8_minmax_correction_notice.md`。

## 7. 权威代码位置

- 基础实现：`experiment/scripts/scale_code_linear/scalepath4_method_inference.py`
  - `encode_scale`
  - `qdq_weight_iah_scale_code`
  - `qdq_activation_iah_scale_code`
- 最终 W8/W4 模块选择：`experiment/scripts/accuracy_MLP_4bit/mlp4_method_inference.py`
  - `ATTENTION_OPS` / `MLP_OPS`
  - `weight_bits_for_op`
  - `attach_scalepath_iah_scale_code_mlp_w4`

这些程序是 QDQ 数值参考实现：它们在软件中保存反量化后的 folded weight 以评估数值质量，并不等同于硬件侧最终的 bit-packing/存储布局。
