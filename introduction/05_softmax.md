# Softmax 模块

## 1. 模块功能

Softmax 模块把一个 query row、一个 query head对所有有效历史 key的 QK score转换为归一化 probability。

主模块层次：

```text
hap_softmax_row_128
├── hap_softmax_exp_u17
├── hap_softmax_recip_u17
│   └── hap_unsigned_div_seq
└── hap_softmax_prob_u16
```

最大支持128个 key。无效 key不参与最大值、指数和归一化求和。

## 2. 输入和输出

输入 score：

```text
signed S20 Q6.14
range clipped to [-16, +16]
```

输入 sideband：

- `in_first_key`
- `in_last_key`
- `in_mask`

输出：

```text
probability U16
key_index 0...127
out_last_key
```

输入和输出都使用 ready/valid。

## 3. 上游 QK score

Softmax 前的 score来自 `hap_qk_score_row_128`：

```text
Q S24 × K S12
→ 32-element dot
→ S40 group result
→ K ScaleCode recovery
→ S35 Q6.14
→ four group32 accumulation
→ clip to S20 Q6.14 in [-16,+16]
```

每个 key恰好对应一个 score。一个 head dimension为128，所以一个 score必须消费4个 group32。

## 4. 计算阶段

`hap_softmax_row_128` 对一行 score执行三遍逻辑处理：

```text
Pass 1: receive scores and find maximum
Pass 2: calculate exp(score - maximum) and accumulate sum
Pass 3: calculate probability for every key
```

score和中间 exp值保存在 row-local memory中，因此不需要上游重新计算 QK。

## 5. 最大值与数值稳定

对所有有效 key求：

```text
row_max = max(score[k])
delta[k] = score[k] - row_max
```

由于减去最大值：

```text
delta ∈ [-16, 0]
```

如果减法结果低于 -16，则钳位为 -16。这样避免正指数溢出，并将 exp输入限制到固定 LUT范围。

mask key不参与 `row_max`，也不写入有效 exp sum。

## 6. Exp LUT

模块：`hap_softmax_exp_u17`

LUT 参数：

```text
257 entries
index range: 0...256
input range: delta = 0 ... -16
base LUT step: 1/16
output: U17 Q16
```

ROM image：

```text
data/softmax_exp_u17.mem
```

输入 delta 为带14个 fractional bits的 signed S19非正定点值。硬件将 magnitude拆成 LUT index和低10位 fraction，相邻 LUT entry之间使用线性插值：

```text
exp ≈ high_entry - (high_entry - low_entry) × fraction
```

插值乘法使用 DSP，结果舍入后输出 U17 Q16。

## 7. 指数求和

所有有效 key的 exp结果累加到：

```text
row_sum U24
```

单个 exp最大约为 `1.0 = 65536`。最多128项，因此 U24足以保存总和。

期望范围：

```text
65536 ≤ row_sum ≤ 8388608
```

即至少一个有效 key，最多128个 exp(0)相加。

## 8. Reciprocal

模块：`hap_softmax_recip_u17`

使用顺序无符号除法器计算 row sum的倒数尺度：

```text
reciprocal ≈ 2^32 / row_sum
```

分子加入 half denominator实现整数舍入。输出为 U17，并钳位到最大65536。

该步骤是每个 row/head执行一次，而不是为128个 key复制128个除法器。

## 9. Probability

模块：`hap_softmax_prob_u16`

保存的 exp值与同一 row reciprocal相乘：

```text
probability[k] = round(exp[k] × reciprocal / 2^16)
```

输出为 U16；超过 `16'hffff` 时钳位而不是回绕。所有 probability依次输出，并携带原 key index和 last标志。

`hap_attention_row_head128` 将 probability写入：

```text
probability_mem[0:127]
```

该 probability row随后被一个物理 PV tile重复读取8次，用于8个16-column value tiles。

## 10. 状态和存储

Softmax row engine需要维护：

- score memory：最多128项。
- exp memory：最多128项。
- key count和mask。
- row maximum。
- U24 row sum。
- U17 reciprocal。
- input、exp、output三个遍历 index。

高层状态可概括为：

```text
ST_LOAD
→ ST_EXP
→ ST_RECIP_REQ
→ ST_RECIP_WAIT
→ ST_PROB
→ ST_LOAD
```

状态切换必须等待当前流水和 FIFO drain，不能只根据最后一个 input被接受就立即输出 probability。

## 11. 握手与反压

- `in_valid && in_ready` 时接收一个 score。
- `out_valid && !out_ready` 时，probability、key index和 last保持稳定。
- exp pipeline、reciprocal和 probability pipeline之间均保留 valid对齐。
- 最后一项 probability被下游接受后，row才算完成。
- 下一 row/head不能覆盖仍在输出的 memory内容。

## 12. 错误条件

- key count为0或超过128。
- first/last标志与实际 index不一致。
- 上游 score未按契约限制在 `[-16,+16]`，从而触发后续 delta格式检查。
- delta大于0或小于-16而未被正确钳位。
- row sum小于65536或大于8388608。
- divider报告错误。
- output key index不连续或 last标志错误。
- mask在同一个 key的4个 QK group之间不一致。

## 13. 绘图要求

Softmax 应画为三段复用式结构，而不是128套指数和除法器：

```text
S20 scores
→ score RAM + max tracker
→ subtract max and clamp [-16,0]
→ 257-entry exp LUT + interpolation
→ exp RAM + U24 sum
→ one sequential reciprocal unit
→ exp × reciprocal
→ U16 probabilities
```

图中必须标出“最多128 keys”“subtract max”“257-entry exp LUT”“U24 sum”和“一个 reciprocal unit”。不得与 MLP 的8193-sample SiLU LUT混淆。

## RTL 依据

- `rtl/attention/hap_qk_score_row_128.sv`
- `rtl/attention/hap_score_accum4_s20.sv`
- `rtl/attention/hap_softmax_row_128.sv`
- `rtl/attention/hap_softmax_exp_u17.sv`
- `rtl/attention/hap_softmax_recip_u17.sv`
- `rtl/attention/hap_softmax_prob_u16.sv`
- `rtl/attention/hap_unsigned_div_seq.sv`
- `rtl/attention/hap_attention_row_head128.sv`

## 真实算数案例：四个 key 的完整 Softmax

下面给出一个只有 4 个有效 key的合法 row。硬件支持最多128个 key，但 `in_last_key` 可以在 key 3结束当前 row。四个 key均不 mask。

输入 score使用 S20 Q6.14：

| key | 实数 score | S20 raw |
|---:|---:|---:|
| 0 | 2.0 | 32768 |
| 1 | 1.0 | 16384 |
| 2 | 0.0 | 0 |
| 3 | -1.0 | -16384 |

### 1. `ST_LOAD`：写 score RAM并寻找最大值

输入握手依次发生后：

```text
score_mem = [32768, 16384, 0, -16384]
mask_mem  = [0, 0, 0, 0]
row_max   = 32768
row_key_count = 4
```

直到 key 3 的 `in_valid && in_ready && in_last_key` 成立，状态机才从 `ST_LOAD` 进入 `ST_EXP`。

### 2. `ST_EXP`：减最大值

```text
delta_raw = score_raw - row_max
          = [0, -16384, -32768, -49152]

delta_real = [0, -1, -2, -3]
```

这些值都在 `[-16,0]` 内，不触发钳位。

### 3. 257-entry Exp LUT 的真实值

`in_delta_q14_s19` 的 magnitude按下面方式拆分：

```text
index    = magnitude[18:10]
fraction = magnitude[9:0]
```

因为一个 index步长为 1024 个 Q14 raw，即 `1024/16384=1/16`，四个整数 delta的 fraction均为 0：

| delta | magnitude | LUT index | 仓库 `softmax_exp_u17.mem` | U17 raw | Q16 解码 |
|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | `17'h10000` | 65536 | 1.000000 |
| -1 | 16384 | 16 | `17'h05E2D` | 24109 | 0.367874 |
| -2 | 32768 | 32 | `17'h022A5` | 8869 | 0.135330 |
| -3 | 49152 | 48 | `17'h00CBF` | 3263 | 0.049789 |

为了展示低10位插值的真实行为，再单独看 `delta=-1.03125`：

```text
delta raw = -1.03125 × 16384 = -16896
magnitude = 16896
index = 16896 >> 10 = 16
fraction = 16896 & 1023 = 512

LUT[16] = 24109
LUT[17] = 22649
difference = 24109 - 22649 = 1460

interpolation_product = 1460 × 512 = 747520
rounded_drop = (747520 + 512) >> 10 = 730
exp_result = 24109 - 730 = 23379
```

所以插值器不是浮点指数单元，而是“一次 LUT 双读、一次差值、一次 `18×10` 乘法和一次舍入右移”。

### 4. Exp RAM 和 U24 row sum

本例四个 unmasked exp全部写入 `exp_mem`：

```text
exp_mem = [65536, 24109, 8869, 3263]

row_sum
= 65536 + 24109 + 8869 + 3263
= 101777
```

若某个 key被 mask，exp pipeline仍保持地址/valid顺序，但写入和累加使用的 `exp_effective` 为 0。

### 5. `ST_RECIP_REQ/ST_RECIP_WAIT`：一个顺序除法器

reciprocal使用带半分母偏置的整数除法：

```text
numerator = 2^32 + floor(row_sum/2)
          = 4294967296 + 50888
          = 4295018184

reciprocal_u17
= floor(4295018184 / 101777)
= 42200
```

`42200/65536=0.6439208984375`。该量等效于 Q16 编码的 `65536/row_sum`，不是普通 Q16 的 `1/row_sum` 写法。整个 row只请求这一个 reciprocal结果。

### 6. `ST_PROB`：逐 key乘 reciprocal

每个 probability执行：

```text
prob_raw = min(65535, (exp_raw × reciprocal_u17 + 32768) >> 16)
```

逐项结果：

| key | `exp×reciprocal` | 加偏置并右移 | probability U16 | 实数 |
|---:|---:|---:|---:|---:|
| 0 | 2765619200 | `(2765619200+32768)>>16` | 42200 | 0.643921 |
| 1 | 1017399800 | `(1017399800+32768)>>16` | 15524 | 0.236877 |
| 2 | 374271800 | `(374271800+32768)>>16` | 5711 | 0.087143 |
| 3 | 137698600 | `(137698600+32768)>>16` | 2101 | 0.032059 |

最终：

```text
out_prob_u16 = [42200, 15524, 5711, 2101]
sum(out_prob_u16) = 65536
```

本例恰好相加为 65536；一般情况下逐项舍入后不强制概率和严格等于 65536。四项都没有超过 65535，所以 `clamp_count` 不增加。

### 7. 状态、存储和算术单元的对应

```text
ST_LOAD:
    4次握手 → score RAM，同时更新1个 max register

ST_EXP:
    4次 issue → 共用1条 exp LUT/interpolation pipeline
    4次 return → exp RAM + 1个 U24 sum register

ST_RECIP_REQ / ST_RECIP_WAIT:
    row_sum=101777 → 共用1个 sequential divider → recip=42200

ST_PROB:
    exp RAM依次读4项 → 共用1个 U17×U17 multiplier
    输出42200、15524、5711、2101
```

这个算例对应的电路图应只有一套 exp pipeline、一套 row-sum累加器、一个 reciprocal divider和一套 probability multiplier，而不是为四个或128个 key复制这些算术单元。
