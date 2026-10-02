# Hadamard + 激活在线量化模块

## 0. 本章结论：当前硬件是原始 MinMax，不做量化前裁剪

本模块以 32 个连续激活为一个 Group32，先执行归一化 Hadamard32，再直接扫描这 32 个 Hadamard 输出的原始最小值和最大值，最后生成 unsigned A8 数据与 U24 metadata。

当前 production RTL 的唯一有效数据流是：

~~~text
32 个高精度激活
→ 五级 Hadamard 蝶形
→ 乘 11585 并右移 16 bit 归一化
→ 原始 Hadamard 输出缓冲 source_mem[0:31]
→ 逐 lane 扫描 raw_min / raw_max，动态范围强制包含 0
→ 根据 diff = high - low 生成 scale_shift、scale_code、zero_point
→ 8 个除法 lane 分 4 批生成 32 个 U8
→ 同时输出 32×U8 与 1×U24 metadata
~~~

图中不得出现以下旧路径：

- 绝对值阈值；
- 百分位统计；
- 直方图或排序器；
- MSE 搜索；
- clip_low / clip_high；
- clipped_mem；
- 将离群值改写后再量化。

RTL 模块名 hap_robust_a8_quantizer 和 hap_mlp_robust_a8_quantizer_s35 中的 robust 只是兼容旧 source list 的历史名称，不代表当前电路仍执行 robust clipping。

必须区分两种完全不同的操作：

- 不存在对 source_mem 中原始激活的量化前裁剪；所有合法 lane 都直接参与 MinMax，并直接进入 affine numerator 计算。
- affine numerator 会被限制到 [0, diff×255]，这是保证最终 U8 落在 [0,255] 的输出域保护，不会改变用于求 MinMax 的原始激活，也不是 clipping 算法。

## 1. 模块用途与部署位置

在线量化表示：每个 row、每个 Group32 的量化参数都由当前激活即时计算，不从 DDR 读取固定 activation scale。

| 使用位置 | Hadamard 输入 | Hadamard 输出 | 量化器 | 后续计算 |
|---|---|---|---|---|
| Attention 输入 | S24 Q8.16 | S27 Q11.16 | hap_robust_a8_quantizer | Q/K/V projection |
| Attention context | S24 Q8.16 | S27 Q11.16 | hap_robust_a8_quantizer | Wo projection |
| MLP 输入 | S24 Q8.16 | S27 Q11.16 | hap_robust_a8_quantizer | Gate/Up projection |
| SwiGLU product | S32 Q16.16 | S35 Q19.16 | hap_mlp_robust_a8_quantizer_s35 | Down projection |

一行中的每 32 个连续元素独立形成一个量化组：

~~~text
hidden size 4096       → 4096 / 32 = 128 groups / row
intermediate size 14336 → 14336 / 32 = 448 groups / row
~~~

量化参数只属于一个确定的 row + group，不能跨行共享，也不能跨 Group32 复用。

## 2. 顶层硬件结构

用于电路图的结构应画成两段：Hadamard 前端和 MinMax A8 量化器。

~~~text
                         Hadamard 前端
┌──────────────────────────────────────────────────────────────┐
│ Group32 input                                                │
│   → stage1 → stage2 → stage3 → stage4 → stage5              │
│   → ×11585 → round / >>16 → S27 或 S35 → FIFO / output reg  │
└──────────────────────────────────────────────────────────────┘
                              │ ready / valid
                              ▼
                         MinMax A8 量化器
┌──────────────────────────────────────────────────────────────┐
│ source_mem[0:31]                                             │
│   ├→ 1-lane sequential Min/Max scanner → low/high/diff       │
│   ├→ scale shift scanner → divider lane 0 → ScaleCode        │
│   ├→ zero-point numerator → divider lane 0 → zero_point      │
│   └→ 8 numerator builders → 8 dividers × 4 batches → 32 U8  │
│                                                              │
│ output = {quant_data_r[255:0], out_meta[23:0]}               │
└──────────────────────────────────────────────────────────────┘
~~~

最容易画错的物理事实是：

1. 输入的 32 个 Hadamard 结果在一次握手时整体锁存。
2. Min/Max 使用 scan_lane_r 从 lane 0 扫到 lane 31，每拍由 32:1 selector 选出一个 source_mem；它不是 32 输入组合比较树，也不要求 source_mem 被综合成 BRAM。
3. 量化器物理上有 8 个除法 lane，不是 32 个除法器；quant_base_r 依次取 0、8、16、24。
4. ScaleCode 和 zero_point 只启动 divider lane 0；生成 U8 时才同时启动 8 个 divider。
5. 一个量化器同一时刻只处理一个 Group32；ST_OUTPUT 被反压时不能接收下一组。

## 3. Hadamard32 的数学功能

### 3.1 等效矩阵

未归一化结果为：

~~~text
b = H32 × x
~~~

H32 是 Sylvester 顺序的 Walsh-Hadamard 矩阵：

~~~text
H2 = [ 1  1 ]
     [ 1 -1 ]

H4 = H2 ⊗ H2
   = [ 1  1  1  1 ]
     [ 1 -1  1 -1 ]
     [ 1  1 -1 -1 ]
     [ 1 -1 -1  1 ]

H32 = H2 ⊗ H2 ⊗ H2 ⊗ H2 ⊗ H2
H32[i,j] = (-1)^popcount(i & j)
H32 × H32^T = 32I
~~~

因此它不需要一般矩阵乘法器。矩阵中的 +1 和 -1 被实现为五级蝶形加减网络。

### 3.2 每一级蝶形的通用连接

第 s 级的跨度为 d = 2^(s-1)，每个长度 2d 的 block 执行：

~~~text
for base = 0, 2d, 4d, ...
    for offset = 0 ... d-1
        a = previous[base + offset]
        b = previous[base + offset + d]

        next[base + offset]     = a + b
        next[base + offset + d] = a - b
~~~

五级跨度依次是 1、2、4、8、16。

### 3.3 定点位宽

加减法不在中间级舍入，位宽每一级增加 1 bit：

| 路径 | 输入 | stage1 | stage2 | stage3 | stage4 | stage5 |
|---|---:|---:|---:|---:|---:|---:|
| S24 路径 | S24 Q8.16 | S25 | S26 | S27 | S28 | S29 |
| S32 product 路径 | S32 Q16.16 | S33 | S34 | S35 | S36 | S37 |

### 3.4 归一化

硬件常量为：

~~~text
INV_SQRT32_Q16 = 11585
11585 / 65536 = 0.1767730712890625 ≈ 1 / sqrt(32)
~~~

归一化计算为：

~~~text
normalized_raw = round_half_away_from_zero(
                     stage5_raw × 11585 / 65536)
~~~

S24 路径的 S29×U14 乘积存为 S43，舍入后饱和到 S27。S32 product 路径的 S37×U14 乘积存为 S51，舍入到 S35；RTL 已证明所有合法 S32 输入都能落入 S35，因此该路径不需要实际饱和器。

这里的舍入是 half-away-from-zero：

~~~text
正数：(|p| + 32768) >> 16
负数：-((|p| + 32768) >> 16)
~~~

它与后续除法器使用的 ties-to-even 不是同一种舍入规则。

## 4. 三种 Hadamard 物理实现

### 4.1 Attention S24 流式版本

模块：hap_hadamard32_norm_stream

- 五级蝶形各占一级寄存器。
- 32 个 normalization product 并行产生。
- 归一化结果写入深度 8 的 FIFO。
- used_count 同时统计 FIFO 内与蝶形流水中的 group，防止反压时溢出。

### 4.2 MLP 输入 S24 fold4 版本

模块：hap_mlp_hadamard32_s24_fold4

- 五级蝶形的数学连接和位宽与 Attention S24 版本 bit-exact。
- 被折叠的是归一化乘法器：物理上只有 4 个 S29×U14 乘法 lane。
- issue_base_r 依次为 0、4、8、...、28，8 轮完成 32 个归一化结果。
- 完整 Group32 保存在 out_s27_r，直到下游握手。

不要把它画成只有 4 个元素参与 Hadamard；五级蝶形仍覆盖完整 32 元素。

### 4.3 SwiGLU product S32 流式版本

模块：hap_mlp_hadamard32_s32_norm_stream

- 输入为 S32 Q16.16，五级蝶形扩展到 S37。
- 32 个 normalization product 并行产生。
- 输出为 S35 Q19.16，并写入深度 8 的 FIFO。
- 分 bank 的 valid 寄存器用于降低高扇出，不改变五级蝶形算法和周期对齐关系。

## 5. 原始 MinMax 扫描

输入握手后，32 个 S27 或 S35 值保持在 source_mem[0:31]。随后执行：

~~~text
raw_min = 0
raw_max = 0

for lane = 0 ... 31:
    sample = source_mem[lane]
    if sample < raw_min: raw_min = sample
    if sample > raw_max: raw_max = sample

low  = sign_extend(raw_min)
high = sign_extend(raw_max)
diff = high - low
~~~

这等价于：

~~~text
low  = min(0, x[0], x[1], ..., x[31])
high = max(0, x[0], x[1], ..., x[31])
diff = high - low
~~~

将 raw_min 和 raw_max 初始化为 0 会强制动态范围包含零：

| 输入组类型 | low | high | zero_point 的趋势 |
|---|---:|---:|---:|
| 全部非负 | 0 | 原始最大值 | 0 |
| 正负混合 | 原始最小值 | 原始最大值 | 1...254 |
| 全部非正 | 原始最小值 | 0 | 255 |
| 全零 | 0 | 0 | 特殊旁路 |

这里的最小值和最大值都是 Hadamard 归一化后的原始整数。单个极端值也必须成为真实 low 或 high，不能被跳过、替换或限幅。

## 6. ScaleCode 生成

### 6.1 ideal scale

输入带 16 个 fractional bits，因此当前组的理想实数 scale 为：

~~~text
ideal_scale = diff / (255 × 65536)
~~~

metadata 用 8-bit scale_code 和 6-bit scale_shift 近似保存它：

~~~text
decoded_scale = scale_code / 2^scale_shift
~~~

### 6.2 scale_shift 扫描器

定义：

~~~text
SCALE_DENOM_Q16       = 255 << 16 = 16711680
SCALE_EXACT_LIMIT_Q16 = 255 × SCALE_DENOM_Q16
                      = 4261478400
~~~

ST_SCALE_SCAN 从：

~~~text
scale_shifted_diff = diff
scale_shift        = 0
~~~

开始，每拍判断下一次左移是否仍不超过 4261478400：

~~~text
if scale_shift < 63
   and 2 × scale_shifted_diff <= 4261478400:
       scale_shifted_diff <<= 1
       scale_shift        += 1
else:
       停止扫描
~~~

停止后执行：

~~~text
scale_code_raw = RNE(scale_shifted_diff / 16711680)
scale_code     = clamp(scale_code_raw, 1, 255)   // diff != 0
~~~

等价数学式为：

~~~text
scale_code = RNE((diff << scale_shift) / (255 << 16))
~~~

选择尽可能大的 shift 是为了充分使用 8-bit scale_code 的有效精度。注意：ScaleCode 只用于下游定点尺度恢复；当前组 32 个 U8 的生成使用原始 diff 的 ideal ratio，不使用近似后的 scale_code。

## 7. zero_point 与 U8 的精确整数公式

### 7.1 zero_point

当 diff 非零时：

~~~text
zp_numerator = (-low) × 255
zero_point   = RNE(zp_numerator / diff)
zero_point   = min(zero_point, 255)
~~~

由于 low 已保证不大于 0，zp_numerator 是非负整数。

### 7.2 每个 lane 的 U8

RTL 不把 x[i] 改写为另一个激活值，而是直接计算：

~~~text
zero_point_term = diff × zero_point
affine_numerator[i] = x[i] × 255 + zero_point_term
maximum_numerator   = diff × 255

bounded_numerator[i] =
    0,                     if affine_numerator[i] <= 0
    maximum_numerator,     if affine_numerator[i] >= maximum_numerator
    affine_numerator[i],   otherwise

q[i] = RNE(bounded_numerator[i] / diff)
~~~

因此：

~~~text
q[i] ∈ [0,255]
x_hat[i] ≈ (q[i] - zero_point) × scale_code / 2^scale_shift
~~~

bounded_numerator 是 U8 输出域保护。source_mem[i]、low、high 和 diff 均保持原始值。

### 7.3 RNE：round-to-nearest, ties-to-even

对非负 numerator N 和正 denominator D：

~~~text
base      = floor(N / D)
remainder = N - base × D

2 × remainder < D  → base
2 × remainder > D  → base + 1
2 × remainder = D  → base 为偶数则保持 base；
                      base 为奇数则加 1
~~~

ScaleCode、zero_point 和 U8 除法都使用这一规则。Hadamard 归一化不使用这一规则。

## 8. 真实 FSM 与资源复用

非零组完整状态路径为：

~~~text
ST_IDLE
→ ST_MINMAX
→ ST_RANGE
→ ST_SCALE_SCAN
→ ST_SCALE_START
→ ST_SCALE_WAIT
→ ST_ZP_PREP
→ ST_ZP_START
→ ST_ZP_WAIT
→ ST_QUANT_PREP
→ ST_QUANT_START
→ ST_QUANT_WAIT
→ ST_QUANT_PREP → ... 共 4 个 quant batch
→ ST_OUTPUT
~~~

各状态真实行为如下：

| 状态 | 真实寄存器/数据行为 |
|---|---|
| ST_IDLE | in_ready=1；in_valid && in_ready 时整体捕获 32 个 lane，raw_min/raw_max 清为 0 |
| ST_MINMAX | scan_lane_r 每拍加 1；一对 min/max 比较器连续扫描 lane 0...31 |
| ST_RANGE | 锁存 low、high、diff；diff=0 时直接产生全零输出 |
| ST_SCALE_SCAN | 每拍尝试将 scale_shifted_diff 左移 1 bit |
| ST_SCALE_START | 对 divider lane 0 发出一个 start pulse |
| ST_SCALE_WAIT | 等待 ScaleCode 除法完成并锁存 scale_code |
| ST_ZP_PREP | 形成 (-low)×255，分母切换为 diff，只激活 divider lane 0 |
| ST_ZP_START | 对 divider lane 0 发出一个 start pulse |
| ST_ZP_WAIT | 等待并锁存 zero_point |
| ST_QUANT_PREP | 同时形成 8 个 affine numerator；quant_base_r 为 0、8、16 或 24 |
| ST_QUANT_START | 同时启动 8 个 divider |
| ST_QUANT_WAIT | 等待 8 个结果全部完成，写入 quant_data_r 对应的 8 个 byte |
| ST_OUTPUT | out_valid=1；U8 和 metadata 保持稳定，直到 out_ready=1 |

全零组的短路径为：

~~~text
ST_IDLE → ST_MINMAX → ST_RANGE → ST_OUTPUT

out_u8   = 32 × 8'b0
out_meta = 24'b0
~~~

## 9. S27 与 S35 量化器的物理差异

| 项目 | S27 quantizer | S35 quantizer |
|---|---|---|
| 源数据 | 32×S27；in_fire 时整体捕获 | 32×S35；8 个 capture-enable banks，每 bank 4 lanes |
| low/high/diff | S28/S28/U28 | S36/S36/U36 |
| affine numerator | S37，送入 U36 | S45，送入 U44 |
| 除法器阵列 | 8×U36/U28 | 8×U44/U36 |
| 除法算法 | 每拍退休 1 个 quotient bit，只需求 8-bit U8，8 次迭代 | radix-16，每拍退休 4 bit，完整 44-bit quotient，11 次迭代 |
| Scale/ZP 使用方式 | 仅 divider 0 活动 | 仅 divider 0 活动 |
| U8 使用方式 | 8 路并行，4 batches | 8 路并行，4 batches |
| 超范围遥测 | 无 format_error_count | 有 format_error_count |

S35 额外定义：

~~~text
SCALE_ROUND_LIMIT_Q16 = 4269834239
~~~

这是使 shift=0 时 RNE ScaleCode 仍不超过 255 的最大整数 diff。若：

~~~text
diff > 4269834239
~~~

S35 量化器将 format_error_count 加 1，ScaleCode 最终限制为 255。原始 source_mem 和用于生成 U8 的 MinMax 区间仍不裁剪。

S27 的合法数值范围保证 diff 远小于该边界，因此没有这项计数。

## 10. Metadata、下游恢复与接口

### 10.1 U24 metadata

~~~text
bit 23:22  reserved = 0
bit 21:16  scale_shift U6
bit 15:8   scale_code U8
bit 7:0    zero_point U8

out_meta = {2'b00, scale_shift, scale_code, zero_point}
~~~

下游先恢复 centered activation：

~~~text
activation_s9 = signed({1'b0, activation_u8})
              - signed({1'b0, zero_point})
~~~

随后将 activation scale_code/scale_shift 与 weight metadata 合并，完成 group partial 的尺度恢复。

### 10.2 ready/valid

典型接口：

~~~text
input : in_valid, in_ready, in_s27[32×27] 或 in_s35[32×35]
output: out_valid, out_ready, out_u8[32×8], out_meta[24]

lane i 输入 = in_s27[i×27 +: 27] 或 in_s35[i×35 +: 35]
lane i 输出 = out_u8[i×8 +: 8]
~~~

只在 valid && ready 时传输。ST_OUTPUT 遇到反压时：

- out_valid 保持 1；
- out_u8 保持不变；
- out_meta 保持不变；
- in_ready 保持 0。

U8 payload 与 U24 metadata 是不可拆分的一组输出，必须写入相同 row/group 地址。

## 11. Cache 组织

Attention projection frontend：

~~~text
wave 0：rows 0...7  → A8 cache context 0
wave 1：rows 8...15 → A8 cache context 1
~~~

每个 cache context 保存 128 个 hidden groups。MLP input frontend 使用 ping-pong bank：一个 bank 被 Gate/Up projection 读取时，另一个 bank 可装入后续输入。

SwiGLU product 量化后写入 hap_mlp_down_activation_cache16，逻辑容量为：

~~~text
448 groups × (16 rows × 32 U8 + 16 rows × U24 metadata)
~~~

## 12. 错误、清除与边界行为

- Hadamard S24 归一化超出 S27 时饱和，不能二进制回绕。
- Hadamard normalization 使用 half-away-from-zero。
- ScaleCode、zero_point 和 U8 divider 使用 ties-to-even。
- diff=0 的全零组不得启动除法器。
- 除数为 0 或量化 FSM 进入未知状态会置 error；S35 radix-16 divider 还会监测 busy 期间的重复 start。
- S35 的 format_error_count 只是 ScaleCode 表示范围遥测，不触发输入裁剪。
- clear 清除 valid、FSM、输出寄存器和统计计数；宽 Hadamard 数据寄存器可不做物理清零，因为 valid=0 时旧数据不可观察。
- cache 写入必须保持 row/group 次序，不能只写 U8 而丢弃 metadata。

## 13. 硬件作图硬约束

最终电路图至少必须明确画出：

1. 32 元素输入边界和 Group32 标签。
2. 五级蝶形，级间 stride 标注为 1、2、4、8、16。
3. 固定系数乘法器 11585、右移 16 bit、Hadamard 舍入规则。
4. 32×S27 或 32×S35 的 source_mem。
5. scan_lane 计数器、单 lane 读口、一对 min/max 比较器、raw_min/raw_max 初值 0。
6. low、high、diff=high-low 寄存器。
7. scale_shift 左移扫描器和常量 16711680、4261478400。
8. 8 个除法器组成的复用阵列；Scale/ZP 只使用 lane 0，U8 分 4 个 batch。
9. x×255、diff×zero_point、加法器和 numerator 输出域限制逻辑。
10. 256-bit U8 输出寄存器和 24-bit metadata 输出寄存器。
11. FSM 控制、ready/valid 和 ST_OUTPUT 反压保持。
12. U8 cache 与 metadata cache 的并行写入关系。

不得画成：

- Hadamard 输出后先经过异常值删除或裁剪器；
- 32 路 Min/Max 组合比较树；
- 32 个 U8 除法器一次完成整组；
- signed int8 输出；
- activation metadata 从 DDR 离线读取；
- 使用 ScaleCode 近似值反过来生成当前组 U8。

## 14. RTL 依据

- rtl/attention/hap_hadamard32_norm_stream.sv
- rtl/attention/hap_robust_a8_quantizer.sv
- rtl/attention/hap_attention_frontend_8row.sv
- rtl/attention/hap_activation_cache_8row.sv
- rtl/mlp/hap_mlp_hadamard32_s24_fold4.sv
- rtl/mlp/hap_mlp_hadamard32_s32_norm_stream.sv
- rtl/mlp/hap_mlp_robust_a8_quantizer_s35.sv
- rtl/mlp/hap_mlp_swiglu_product_frontend16_q4.sv

---

## 15. 完整真实算数案例：五级 Hadamard + 原始 MinMax A8

下面用一个合法 S24 Q8.16 Group32 贯穿整个硬件。

### 15.1 输入

为便于阅读，先写成解码后的整数：

~~~text
x = [0, 1, 2, 3, ..., 30, 31]
~~~

实际送入 RTL 的 24-bit 原始整数为：

~~~text
x_raw[i] = i × 65536
~~~

下面 S1...S5 先写解码值；对应寄存器内的真实整数仍是表中数值乘 65536。

### 15.2 第一级：stride=1

相邻两个数执行 (a+b, a-b)：

~~~text
(0,1)   → (1,-1)
(2,3)   → (5,-1)
...
(30,31) → (61,-1)

S1 =
[ 1,-1, 5,-1, 9,-1,13,-1,
 17,-1,21,-1,25,-1,29,-1,
 33,-1,37,-1,41,-1,45,-1,
 49,-1,53,-1,57,-1,61,-1 ]
~~~

S1 寄存器位宽为 S25。

### 15.3 第二级：stride=2

第一组四个节点：

~~~text
[1,-1,5,-1]
→ [1+5, -1+(-1), 1-5, -1-(-1)]
→ [6,-2,-4,0]
~~~

完整 S26：

~~~text
S2 =
[  6,-2,-4,0, 22,-2,-4,0,
  38,-2,-4,0, 54,-2,-4,0,
  70,-2,-4,0, 86,-2,-4,0,
 102,-2,-4,0,118,-2,-4,0 ]
~~~

### 15.4 第三级：stride=4

第一组八个节点：

~~~text
[6,-2,-4,0] 与 [22,-2,-4,0]
→ [28,-4,-8,0, -16,0,0,0]
~~~

完整 S27：

~~~text
S3 =
[ 28,-4,-8,0,-16,0,0,0,
  92,-4,-8,0,-16,0,0,0,
 156,-4,-8,0,-16,0,0,0,
 220,-4,-8,0,-16,0,0,0 ]
~~~

### 15.5 第四级：stride=8

完整 S28：

~~~text
S4 =
[120,-8,-16,0,-32,0,0,0,
 -64, 0,  0,0,  0,0,0,0,
 376,-8,-16,0,-32,0,0,0,
 -64, 0,  0,0,  0,0,0,0]
~~~

例如第一段：

~~~text
S4[0] = S3[0] + S3[8] = 28 + 92 = 120
S4[8] = S3[0] - S3[8] = 28 - 92 = -64
~~~

### 15.6 第五级：stride=16

前 16 项和后 16 项逐项做加减：

~~~text
S5 = H32 × x
   = [496,-16,-32,0,-64,0,0,0,
      -128,0,0,0,0,0,0,0,
      -256,0,0,0,0,0,0,0,
      0,0,0,0,0,0,0,0]
~~~

具体节点：

~~~text
S5[0]  = S4[0] + S4[16] = 120 + 376 = 496
S5[16] = S4[0] - S4[16] = 120 - 376 = -256
S5[8]  = S4[8] + S4[24] = -64 + (-64) = -128
~~~

S5 寄存器位宽为 S29。

### 15.7 乘 11585 并归一化

由于本例所有输入都恰好是整数乘 65536，非零 lane 右移后的结果没有半 LSB 歧义：

| lane | S5 解码值 | S43 原始乘积 | S27 normalized raw | Q11.16 解码值 |
|---:|---:|---:|---:|---:|
| 0 | 496 | 496×65536×11585 | 5746160 | 87.679443 |
| 1 | -16 | -16×65536×11585 | -185360 | -2.828369 |
| 2 | -32 | -32×65536×11585 | -370720 | -5.656738 |
| 4 | -64 | -64×65536×11585 | -741440 | -11.313477 |
| 8 | -128 | -128×65536×11585 | -1482880 | -22.626953 |
| 16 | -256 | -256×65536×11585 | -2965760 | -45.253906 |

其余 26 个 lane 的 normalized raw 都是 0。量化器 source_mem 最终保存：

~~~text
[5746160,-185360,-370720,0,-741440,0,0,0,
 -1482880,0,0,0,0,0,0,0,
 -2965760,0,0,0,0,0,0,0,
 0,0,0,0,0,0,0,0]
~~~

### 15.8 真实 32 拍 Min/Max 扫描

初值：

~~~text
raw_min = 0
raw_max = 0
~~~

只有以下 lane 会改变寄存器：

| 扫描 lane | sample | 扫描后的 raw_min | 扫描后的 raw_max |
|---:|---:|---:|---:|
| 初值 | — | 0 | 0 |
| 0 | 5746160 | 0 | 5746160 |
| 1 | -185360 | -185360 | 5746160 |
| 2 | -370720 | -370720 | 5746160 |
| 4 | -741440 | -741440 | 5746160 |
| 8 | -1482880 | -1482880 | 5746160 |
| 16 | -2965760 | -2965760 | 5746160 |
| 其余 lane | 0 | 不变 | 不变 |

因此：

~~~text
low  = -2965760
high =  5746160
diff = high - low
     = 5746160 - (-2965760)
     = 8711920
~~~

最大值和最小值均来自原始 Hadamard 输出，没有任何 lane 被裁剪。

### 15.9 真实 scale_shift 扫描

每进入一次 ST_SCALE_SCAN，硬件最多左移 1 bit：

| scale_shift | scale_shifted_diff |
|---:|---:|
| 0 | 8711920 |
| 1 | 17423840 |
| 2 | 34847680 |
| 3 | 69695360 |
| 4 | 139390720 |
| 5 | 278781440 |
| 6 | 557562880 |
| 7 | 1115125760 |
| 8 | 2230251520 |
| 尝试 9 | 4460503040，超过 4261478400，因此不接受 |

所以：

~~~text
scale_shift = 8
~~~

divider lane 0 执行：

~~~text
N = 2230251520
D = 16711680

N = 133 × D + 7598080
2 × 7598080 = 15196160 < 16711680

scale_code = 133 = 0x85
~~~

对应：

~~~text
ideal_scale   = 8711920 / (255×65536)
              = 0.521307253...
decoded_scale = 133 / 2^8
              = 0.51953125
~~~

### 15.10 真实 zero_point 除法

~~~text
zp_numerator = (-low) × 255
             = 2965760 × 255
             = 756268800

756268800 = 86 × 8711920 + 7043680
2 × 7043680 = 14087360 > 8711920

zero_point = 86 + 1 = 87 = 0x57
~~~

U24 metadata：

~~~text
out_meta = {2'b00, 6'd8, 8'h85, 8'h57}
         = 24'h088557
~~~

### 15.11 四个真实 U8 batch

公共量：

~~~text
zero_point_term  = diff × zero_point
                 = 8711920 × 87
                 = 757937040

maximum_numerator = diff × 255
                  = 8711920 × 255
                  = 2221539600
~~~

重复值只列一次完整除法；相同的零输入 lane 都得到 87。

| lane 类型 | x | affine numerator | 输出域限制后 | 除法与舍入 | q |
|---|---:|---:|---:|---|---:|
| lane 0 | 5746160 | 5746160×255+757937040 = 2223207840 | 2221539600 | 2221539600 / 8711920 = 255 | 255 |
| lane 1 | -185360 | 710670240 | 710670240 | 81 余 5004720；2r>D，向上 | 82 |
| lane 2 | -370720 | 663403440 | 663403440 | 76 余 1297520；2r<D，保持 | 76 |
| 任意零 lane | 0 | 757937040 | 757937040 | 恰好 87 | 87 |
| lane 4 | -741440 | 568869840 | 568869840 | 65 余 2595040；2r<D，保持 | 65 |
| lane 8 | -1482880 | 379802640 | 379802640 | 43 余 5190080；2r>D，向上 | 44 |
| lane 16 | -2965760 | 1668240 | 1668240 | 0 余 1668240；2r<D，保持 | 0 |

注意 lane 0 的 affine numerator 因 zero_point 已舍入到整数而略高于 maximum_numerator。硬件只把 numerator 限制到 diff×255，source_mem[0]=5746160 并未被改写。

4 个物理 batch 为：

~~~text
quant_base=0  → lanes  0...7 → [255,82,76,87,65,87,87,87]
quant_base=8  → lanes  8...15 → [44,87,87,87,87,87,87,87]
quant_base=16 → lanes 16...23 → [0,87,87,87,87,87,87,87]
quant_base=24 → lanes 24...31 → [87,87,87,87,87,87,87,87]
~~~

最终 256-bit U8 payload 按 lane 顺序为：

~~~text
[255,82,76,87,65,87,87,87,
  44,87,87,87,87,87,87,87,
   0,87,87,87,87,87,87,87,
  87,87,87,87,87,87,87,87]
~~~

最终必须把它理解成同一笔事务：

~~~text
32×U8 payload
+ U24 metadata = 24'h088557
+ 对应的 row/group 地址
~~~

这组算例完整覆盖了五级蝶形、固定系数归一化、32 拍原始 MinMax、逐拍 scale shift、divider lane 0 生成 ScaleCode 与 zero_point，以及 8 路除法器分 4 批生成 U8 的真实硬件行为。
