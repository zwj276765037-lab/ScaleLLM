# Attention 层计算核心

## 1. 模块功能

Attention 计算核心完成一组 16 token rows 的 Q/K/V 投影、位置编码、KV cache更新、QK 打分、Softmax、PV 加权和 Wo 输出投影。

主模块：

```text
hap_attention_board_cohort16_core
└── hap_attention_compute_cohort16_top
    ├── hap_projection_core16x16_w8_reuse
    ├── Q / K / V / context local stores
    ├── hap_rope_pair_s24
    ├── hap_kv12_quantizer4
    ├── hap_kv12_cache
    └── hap_attention_row_head128
        ├── hap_qk_score_row_128
        ├── hap_softmax_row_128
        └── hap_pv_tile16_s43
```

## 2. 模型形状

| 项目 | 数值 |
|---|---:|
| Query rows | 16 |
| Hidden dimension | 4096 |
| Query heads | 32 |
| KV heads | 8 |
| Head dimension | 128 |
| 最大历史 token | 128 |
| Quantization group | 32 |

Q、K、V 的输出形状：

```text
Q = 16 rows × 32 heads × 128 = 16 × 4096
K = 16 rows ×  8 heads × 128 = 16 × 1024
V = 16 rows ×  8 heads × 128 = 16 × 1024
```

Llama GQA 映射固定为：

```text
kv_head = query_head[4:2] = floor(query_head / 4)
```

因此每 4 个连续 query heads共享一个 KV head。

## 3. 完整数据流

```text
16×4096 S24 input
→ Hadamard32 + online A8
→ Q/K/V projection
→ Q and K RoPE
→ K/V KV12 quantization
→ KV cache update
→ QK score for each row/head/key
→ Softmax probabilities
→ probability × V
→ 16×4096 S24 context
→ Hadamard32 + online A8
→ Wo projection
→ 16×4096 S24 output
```

所有主要激活边界均为 signed S24 Q8.16。A8 仅用于 projection array内部输入；K/V 在历史 cache中使用 S12 加 meta16。

## 4. Q/K/V/Wo 投影

### 投影 tile

每个 projection tile产生 16 个输出列，tile编号固定为：

| 投影 | Tile 范围 | Tile 数量 | 输出列数 |
|---|---:|---:|---:|
| Q | 0–255 | 256 | 4096 |
| K | 256–319 | 64 | 1024 |
| V | 320–383 | 64 | 1024 |
| Wo | 384–639 | 256 | 4096 |

每个 tile沿输入维度遍历：

```text
4096 / 32 = 128 weight groups
```

一个 W8 group包含：

```text
16 output columns × 32 signed W8 = 4096 bits
16 columns × 16-bit metadata = 256 bits
```

### 逻辑 16 rows，物理 8 rows

`hap_projection_core16x16_w8_reuse` 的外部结果是 16 rows，但物理 A8W8 lane array只有 8 rows。

```text
wave0 = rows 0–7
wave1 = rows 8–15
```

每个 W8 group的消费顺序必须是：

```text
accept group g
→ read wave0 activation group g
→ compute and accumulate wave0
→ read wave1 activation group g
→ compute and accumulate wave1
→ release group g
```

不能在 wave0 完成后释放权重，也不能画成两套独立阵列。

### 列分片

16 个物理输出列被并行拆成三个 shard：

```text
left shard   = columns 0–1
center shard = columns 2–13
right shard  = columns 14–15
```

对应模块：

- `hap_a8w8_col_shard_left2_s42`
- `hap_a8w8_col_shard_center12_s42`
- `hap_a8w8_col_shard_right2_s42`

`2 + 12 + 2` 是同时工作的物理列分片，不是三个时间 pass。

## 5. A8W8 lane

每个 row、每个 output column、每个 group32执行：

```text
dot = Σ ((activation_u8 - zero_point) × weight_s8)
```

随后使用 activation 和 weight 的 ScaleCode 恢复尺度：

```text
code_product = activation_scale_code × weight_scale_code
total_shift = activation_scale_shift + weight_scale_shift
group partial → S42 Q18.24
```

128 个 group partial在 S42 域中累加。wave0 和 wave1具有两个独立 accumulator context，但共用前面的 lane array。

最后执行 round-half-away-from-zero 和 saturation，得到 S24 Q8.16 tile结果。

完整 Attention projection engine的审计资源为2240个 DSP48E2；该数字已包含当前 physical projection结构，不能因两个 wave再乘2。

## 6. Projection metadata

单层 Attention metadata数量：

```text
640 tiles × 128 groups = 81920 records
```

每条 record为 256 bit，包含 16 个 column metadata。每列格式：

```text
[7:0]   scale_code
[13:8]  scale_shift
[15:14] reserved = 0
```

metadata保存在片上 `hap_weight_meta_resident`；W8 payload保存在外部 DDR。二者根据相同 tile/group index在 projection入口配对。

## 7. Q/K/V 本地存储

projection输出按 `out_wave` 恢复为 16 rows，并写入专用 local stores：

- `hap_attention_cohort16_query_store`：保存 Q，供逐 row/head读取。
- `hap_attention_cohort16_postprocess_store`：保存待 RoPE、待 KV12 量化的数据。
- `hap_attention_cohort16_context_store`：保存 PV 产生的 4096-wide context。

这些存储位于 FPGA 片内，只保存当前命令的中间结果；它们不是外部 DDR，也不是历史 KV cache。

## 8. K/V 量化和缓存

K 经 RoPE后、V 直接进入 `hap_kv12_quantizer4`。该模块包含 4 个并行 worker，每次接收 4 个 group32输入。

每个输出 record：

```text
32 × signed 12-bit values = 384 bits
1 × meta16
```

S12 中的 `-2048` 是保留非法码，量化器不得生成该值。

KV cache逻辑地址：

```text
{kv_head[2:0], token[6:0], group_index[1:0]}
```

总形状为：

```text
8 KV heads × 128 tokens × 4 group32/head
```

K 和 V 使用相同地址结构，但属于两个独立逻辑存储区。当前 cohort写入的 token index为 `query_start + row`；历史 K/V 可在 compute IDLE时 preload。

## 9. QK score

对一个 query row、一个 query head、一个历史 key：

1. 从 query store读取 4 个 Q group32。
2. 从对应 KV head读取 4 个 K group32。
3. 每组计算 32 个 `S24 × S12` 乘积并归约到 S40。
4. 使用 K meta16恢复尺度，得到 S35 Q6.14 group score。
5. 累加 4 组。
6. 将 score clip到 `[-16,+16]`，输出 S20 Q6.14。

有效 key数量按因果关系计算：

```text
row_key_count = min(query_start + row + 1, valid_key_count)
```

窗口最大为 128。production输入约束为：

```text
query_start ≤ 112
1 ≤ valid_key_count ≤ 128
query_start + 16 ≤ valid_key_count
```

## 10. Softmax 和 PV

QK score进入 `hap_softmax_row_128`，产生 U16 probability。具体结构见 `05_softmax.md`。

`hap_attention_row_head128` 内只有一个物理 `hap_pv_tile16_s43`。它对同一个 probability row依次执行 8 个 16-column value tile：

```text
8 tiles × 16 columns = 128-dimension context/head
```

每个 PV tile执行：

```text
probability U16 × value S12 × value ScaleCode
→ S43 Q19.24 accumulation over valid keys
→ round and saturate
→ 16 × S24 context
```

一个 PV leaf时间复用 8 次，不是 8 个并行 PV blocks。

## 11. Row/head 调度

`hap_attention_row_head128` 是一套可复用的 row/head engine。控制器按如下顺序工作：

```text
for row = 0..15:
    for query_head = 0..31:
        load 4 Q groups
        stream all valid K groups
        calculate scores
        calculate Softmax and store probabilities
        for value_tile = 0..7:
            stream V for all valid keys
            calculate one 16-column context tile
```

16 rows、32 heads和128 keys是逻辑迭代空间，不是完全并行展开的硬件阵列。

## 12. Context 与 Wo

32 个 query heads的 context拼成每行 4096 个 S24元素。16 行全部写入 context store后：

```text
context store
→ Hadamard32
→ online A8 quantization
→ two 8-row activation cache contexts
→ same A8W8 projection array
→ Wo tiles 384–639
```

Wo 不使用第二套 projection array。

## 13. 主控制阶段

```text
IDLE
→ input frontend fill
→ Q/K/V projection
→ RoPE and KV12 postprocess
→ input cache release
→ row/head Attention
→ context frontend fill
→ Wo projection
→ context cache release
→ done
```

每个阶段通过 ready/valid与下一级握手。output被反压时，S24 tile、wave和 request tag必须保持稳定。

## 14. 绘图要求

Attention 核心图必须清楚表达：

- 输入和输出均为 `16×4096 S24`。
- 一套 8-row physical projection array，通过 wave0/wave1覆盖16行。
- 两个 activation cache和两个 accumulator context，但只有一套 A8W8 lane array。
- 16列阵列的 `left2 + center12 + right2` 并行分片。
- Q/K/V/Wo tile范围和共用关系。
- 32 query heads到8 KV heads的 `4:1` GQA映射。
- 一个 row/head engine顺序处理16 rows和32 heads。
- 一个 16-column PV leaf顺序执行8个 value tiles。

不得使用旧的 `hap_attention_compute_top`、`hap_projection_core8x16` 或 `hap_attention_board_core` 作为 production主体。

## RTL 依据

- `rtl/attention/hap_attention_compute_cohort16_top.sv`
- `rtl/attention/hap_projection_core16x16_w8_reuse.sv`
- `rtl/attention/hap_a8w8_array_16x16_s42_col3.sv`
- `rtl/attention/hap_a8w8_group32_lane_s42.sv`
- `rtl/attention/hap_linear_tile_accum_dual_s42.sv`
- `rtl/attention/hap_attention_cohort16_local_stores.sv`
- `rtl/attention/hap_kv12_quantizer4.sv`
- `rtl/attention/hap_kv12_cache.sv`
- `rtl/attention/hap_attention_row_head128.sv`

## 真实算数案例：从 A8W8 投影到 QK 和 PV

本例使用人为选择但符合所有 production 格式限制的数值。未写出的 lane、列和 group均设为 0，因此可以只追踪一条物理 lane；真实硬件仍然同时实例化对应的 8-row、16-column 并行结构。

### 1. 一个 A8W8 projection lane

选择 wave0 的 row 0、output column 0、input group 0。令 32 个 activation U8均为 `129`，zero-point为 `128`，32 个 W8均为 `32`：

```text
centered_activation[i] = 129 - 128 = 1
product[i] = 1 × 32 = 32, i=0...31
```

lane内部不会用一个 32 输入的大加法器，而是先后启动低 16 lane和高 16 lane：

```text
low-half sum  = 16 × 32 = 512
high-half sum = 16 × 32 = 512
group dot     = 512 + 512 = 1024
```

设 activation metadata为：

```text
act_scale_code  = 128
act_scale_shift = 16
```

该 output column的 weight metadata为：

```text
wgt_scale_code  = 128
wgt_scale_shift = 10
```

尺度恢复严格按 RTL 进行：

```text
code_product = 128 × 128 = 16384
total_shift  = 16 + 10 = 26
raw_s37      = 1024 × 16384 = 16777216
guard_s42    = raw_s37 >>> (26 - 24)
             = 16777216 >>> 2
             = 4194304
```

假定 group 1–127在该 row/column上都产生 0，则 dual accumulator 的 wave0 context在最后一个 group后仍为 `4194304`。最终从 Q18.24 变为 Q8.16：

```text
projection_raw
= round_half_away_from_zero(4194304 / 256)
= (4194304 + 128) >> 8
= 16384

projection_value = 16384 / 65536 = 0.25
```

对于 wave1 的 row 8，若 activation U8全部改为 `130`，则 centered activation为 2：

```text
group dot       = 32 × 2 × 32 = 2048
wave1 guard     = (2048 × 16384) >>> 2 = 8388608
wave1 S24 raw   = (8388608 + 128) >> 8 = 32768
wave1 real value = 0.5
```

这两个结果分别写入 wave0 和 wave1 accumulator，但前面的 32 乘法和归约路径是同一套物理 lane。一个 W8 group的真实使用顺序是 `wave0 low/high half → wave1 low/high half → release`。

### 2. 一个 128-dimensional QK score

选择 query row 0、query head 5。GQA 地址计算为：

```text
query_head = 5 = 5'b00101
kv_head = query_head[4:2] = 3'b001 = 1
```

因此它读取 KV cache的 `kv_head=1`。128维 head分成四个 group32。对四组都取：

```text
Q group: lane0 = 65536，即 S24 Q8.16 的 1.0；其余 lane = 0
K group: lane0 = 2，其余 S12 lane = 0
K meta : code = 128, shift = 8，即 meta16 = 16'h0880
```

每组的 S24×S12 dot为：

```text
dot_s40 = 65536 × 2 = 131072
```

`hap_score_group_scale_s35` 先乘 K ScaleCode，再用常数 `5793` 实现 `1/sqrt(128)`：

```text
coded = 131072 × 128 = 16777216
scaled_product = 16777216 × 5793 = 97190412288
group_q14 = scaled_product >>> (key_shift + 18)
          = 97190412288 >>> 26
          = 1448
```

四组进入 `hap_score_accum4_s20` 后的寄存器值为：

| group | first/last | accumulator raw | Q6.14 解码值 |
|---:|---|---:|---:|
| 0 | first | 1448 | 0.088379 |
| 1 | — | 2896 | 0.176758 |
| 2 | — | 4344 | 0.265137 |
| 3 | last | 5792 | 0.353516 |

`5792` 位于 `[-262144,+262144]`，所以 score clip不动作。数学参考值为 `4/sqrt(128)=0.353553`；硬件值略有差异来自常数 `5793` 和算术右移。

### 3. 四个 key 的 Softmax 与第一个 PV tile

为了继续展示 row/head engine，令四个 key的最终 QK score为：

```text
score Q6.14 raw = [32768, 16384, 0, -16384]
score real      = [2.0,   1.0,   0.0, -1.0]
```

Softmax模块按其真实 LUT、reciprocal和舍入规则输出：

```text
probability U16 raw = [42200, 15524, 5711, 2101]
sum                 = 65536
```

现在计算第一个 16-column V tile的 column 0。四个 key的 V S12 code和统一 metadata为：

```text
V_s12 = [2, 1, -2, 4]
V meta: code = 128, shift = 8
```

这对应近似实数 V值 `[1.0, 0.5, -1.0, 2.0]`。`hap_pv_tile16_s43` 对每个 key先做：

```text
vcode = V_s12 × 128
raw   = vcode × probability
align_shift = 8 - 8 = 0
term = raw >>> 0
```

逐 key结果为：

| key | V_s12 | probability | S36 term |
|---:|---:|---:|---:|
| 0 | 2 | 42200 | `2×128×42200 = 10803200` |
| 1 | 1 | 15524 | `1×128×15524 = 1987072` |
| 2 | -2 | 5711 | `-2×128×5711 = -1462016` |
| 3 | 4 | 2101 | `4×128×2101 = 1075712` |

S43 accumulator得到：

```text
accum = 10803200 + 1987072 - 1462016 + 1075712
      = 12403968
```

最后除以 `2^8`，执行 half-away-from-zero：

```text
context S24 raw = (12403968 + 128) >> 8
                = 48453
context real    = 48453 / 65536
                = 0.7393341064453125
```

该数值写入 context tile 0 的 column 0。相同 probability row随后再次读取 7 次，依次处理 value columns 16–31、32–47，直到 columns 112–127；硬件只有一个物理 16-column PV leaf。形成完整 128维 context后，数据再经过 context Hadamard/online A8 和同一 projection array的 Wo tile 384–639。

从这个案例画电路时，应能明确区分三种累加：

1. A8W8 lane内部 32 项 dot归约。
2. projection沿 128 个 input group的 S42累加。
3. QK 的 4-group累加与 PV 沿 key维度的 S43累加。
