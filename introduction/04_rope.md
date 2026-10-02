# RoPE 模块

## 1. 模块功能

RoPE 对 Q 和 K 的二维偶/奇通道对施加旋转位置编码。V 不经过 RoPE。

核心算术模块：

```text
hap_rope_pair_s24
```

它位于 Q/K projection 与 query store、KV12 quantizer之间。

```text
Q projection S24 ──► RoPE ──► query store
K projection S24 ──► RoPE ──► KV12 quantizer ──► K cache
V projection S24 ────────────► KV12 quantizer ──► V cache
```

## 2. 输入和输出

每次处理一对 S24 Q8.16元素：

- `x0_s24`：head dimension中的偶数元素。
- `x1_s24`：相邻奇数元素。
- `cos_s18`：signed 18-bit余弦系数。
- `sin_s18`：signed 18-bit正弦系数。

系数使用带16个 fractional bits的 signed格式，合法范围为 `[-65536,+65536]`，即实数 `[-1,+1]`。

输出：

- `y0_s24`
- `y1_s24`

输入和输出都使用 ready/valid握手。

## 3. 数学运算

```text
y0 = x0 × cos - x1 × sin
y1 = x0 × sin + x1 × cos
```

每个输出需要两个乘法和一次加减。内部保留扩展乘积位宽，之后按系数的小数位进行舍入，并饱和回 S24 Q8.16。

舍入采用 round-half-away-from-zero；溢出时钳位到 S24 最大值或最小值，不允许 wrap-around。

## 4. Head 内部索引

head dimension为128，因此包含：

```text
128 / 2 = 64 RoPE pairs/head
```

projection和后处理按 group32组织，每个 group32包含16个 pair：

```text
4 group32/head × 16 pairs/group = 64 pairs/head
```

RoPE 系数与 query head/KV head无关：在同一个 token position和 pair-within-head上，所有 heads共享相同 cos/sin。

## 5. 系数存储

外部 RoPE image：

```text
256 × 256-bit AXI beats
= 1024 × 64-bit records
```

每条 64-bit external record的有效字段：

```text
[17:0]  cos_s18
[35:18] sin_s18
[63:36] reserved / padding
```

board wrapper解包 record后，只把36个有效位写入：

```text
rope_mem[0:1023] : 1024 × 36-bit
```

片上地址由以下字段组成：

```text
{row[3:0], head_group32[1:0], pair_in_group[3:0]}
```

对应：

```text
16 rows × 4 groups/head × 16 pairs/group = 1024 entries
```

## 6. 数据调度

对一个 Q 或 K projection tile，RoPE 控制器按 16 rows ×16 pairs扫描当前 group32：

```text
for row = 0..15:
    for pair = 0..15:
        read x0/x1 from postprocess store
        read cos/sin from rope_mem
        execute hap_rope_pair_s24
        write rotated pair
```

Q tile的结果写入 query store。K tile的结果保留在 postprocess路径，随后按4 rows一组送入 KV12 quantizer。

## 7. Pipeline 与握手

`hap_rope_pair_s24` 是带 FIFO 的定点流水模块：

- 输入 fire：`in_valid && in_ready`
- 输出 fire：`out_valid && out_ready`
- 下游 stall时，输出 pair保持稳定。
- cos、sin、x0、x1必须在同一个输入 transaction中锁定。
- pair index和 row index由外层控制器与数据流水保持对齐。

production compute中 RoPE 输出端保持可接收，但 local store写入顺序仍由 `rope_output_index` 检查。

## 8. 加载与生命周期

Attention board wrapper在计算前可执行 RoPE reload：

```text
ROPE_CMD
→ read 256 AXI256 beats
→ split each beat into four 64-bit records
→ write 1024 coefficient entries
→ set rope_loaded
```

只有完整写入1024条记录后，image才被视为有效。compute运行期间不能修改 `rope_mem`；写接口只在 compute IDLE时 ready。

## 9. 错误条件

- RoPE image未加载完整就启动需要 RoPE 的 Attention。
- 写地址超过 `0...1023`。
- 输入、输出 pair计数不等于256 pairs/tile。
- pipeline中的 row/pair tag错位。
- 乘法结果饱和次数可被统计，但数值必须保持确定性。

## 10. 绘图要求

RoPE 图应包含：

```text
Q/K S24 pair
      │
      ├── x0 × cos ─┐
      ├── x1 × sin ─┴─ subtract ─► y0 S24
      ├── x0 × sin ─┐
      └── x1 × cos ─┴─ add ─────► y1 S24

1024×36-bit coefficient memory ─► cos_s18 / sin_s18
```

必须画 Q 和 K进入 RoPE、V 绕过 RoPE。不得把系数存储画成每个 head独立一份，也不得把 external 64-bit padding误认为64位有效系数。

## RTL 依据

- `rtl/attention/hap_rope_pair_s24.sv`
- `rtl/attention/hap_attention_compute_cohort16_top.sv`
- `rtl/attention/hap_attention_board_cohort16_core.sv`
- `rtl/attention/hap_attention_cohort16_local_stores.sv`

## 真实算数案例：一个 Q/K 偶奇 pair 的旋转

下面选择一个合法的 S24 Q8.16 pair：

```text
x0 =  1.5  → in_x0_s24 =  98304 = 24'h018000
x1 = -0.5  → in_x1_s24 = -32768 = 24'hFF8000
```

选择接近 `cos=0.8`、`sin=0.6` 的 S18 Q1.16 系数：

```text
cos_s18 = 52429 = 18'h0CCCD = 0.8000030517578125
sin_s18 = 39322 = 18'h0999A = 0.600006103515625
```

若 external 64-bit record的 padding清零，则记录为：

```text
record[17:0]  = cos = 18'h0CCCD
record[35:18] = sin = 18'h0999A
record[63:36] = 0

record = 64'h000000026668CCCD
```

### 1. 等效矩阵

该 pair等效于与一个 2×2 旋转矩阵相乘：

```text
[y0]   [ cos  -sin ] [x0]
[y1] = [ sin   cos ] [x1]
```

注意 RTL 是先对四个乘积分别舍入到 Q16，再执行加减，不是先用无限精度完成矩阵乘法后统一舍入。

### 2. 四个 DSP 乘积

S24 Q8.16 与 S18 Q1.16 相乘，乘积带 32 个 fractional bits：

| 路径 | 原始整数乘法 | S41 乘积 |
|---|---:|---:|
| `x0×cos` | `98304×52429` | 5153980416 |
| `x1×sin` | `-32768×39322` | -1288503296 |
| `x0×sin` | `98304×39322` | 3865509888 |
| `x1×cos` | `-32768×52429` | -1717993472 |

### 3. 每条乘积独立舍入回 Q16

正数使用 `(value+32768)>>>16`，负数使用 `(value+32767)>>>16`。后者配合 arithmetic floor shift，等价于 half-away-from-zero。

```text
round(x0×cos) =  78644 =  1.20001220703125
round(x1×sin) = -19661 = -0.3000030517578125
round(x0×sin) =  58983 =  0.9000091552734375
round(x1×cos) = -26215 = -0.4000091552734375
```

### 4. 加减并饱和到 S24

```text
y0_raw = 78644 - (-19661)
       = 98305

y1_raw = 58983 + (-26215)
       = 32768
```

因此输出为：

```text
out_y0_s24 = 24'h018001 = 98305 / 65536
             = 1.5000152587890625

out_y1_s24 = 24'h008000 = 32768 / 65536
             = 0.5
```

两个结果都位于 S24范围内，所以 `saturation_count` 不增加。理想浮点结果为 `(1.5,0.5)`；y0多一个 LSB，是系数量化和“先乘法舍入、后加减”的真实硬件误差。

### 5. 与流水寄存器的对应

无反压时，一个 pair在边沿 N 被接受：

```text
N   : 四个 DSP写入 x0_cos/x1_sin/x0_sin/x1_cos
N+1 : 四条 round_s41_q32_to_s25_q16 写入 S25
N+2 : subtract/add 写入 y0_s26/y1_s26
N+3 : saturation后写入 48-bit output FIFO
```

若 `out_ready=0`，已经写入 FIFO 的 `y0/y1` 和 pair顺序保持不变。Q 和 K 都执行以上运算；V 没有这条 2×2 旋转路径。
