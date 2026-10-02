# MLP 层非线性计算模块

## 1. 模块功能

MLP 非线性模块实现 Llama SwiGLU：

```text
Z = SiLU(Gate) × Up
```

输入是 Gate 和 Up projection产生的 S24 Q8.16结果，输出是 S32 Q16.16 product。product随后按 group32执行 Hadamard和在线 A8量化，形成 Down projection的输入。

主模块：

```text
hap_mlp_swiglu_product_frontend16_q4
├── 2 × hap_mlp_swiglu_row_stream8_q4
│   └── 1 × hap_mlp_silu_mul per row branch
├── two-bank central 16×32 product ring
├── 1 × hap_mlp_hadamard32_s32_norm_stream
└── 4 × hap_mlp_robust_a8_quantizer_s35
```

## 2. 输入形状

Gate 和 Up的逻辑 shape相同：

```text
16 rows × 14336 columns × S24
```

物理 kernel先产生12-column结果，再由 inverse gearbox恢复为16-column projection records。非线性模块只接收恢复后的16-column顺序：

```text
one Gate record = 16 rows × 16 columns × S24
one Up record   = 16 rows × 16 columns × S24
```

每个矩阵共有：

```text
14336 / 16 = 896 records
```

## 3. Gate/Up 配对

SwiGLU 必须将同一 row、同一 column位置的 Gate和 Up配对。任何 record、block、matrix或 row tag不一致都会造成错误结果。

对一个32-column product group，输入由两个连续16-column records组成。行内处理顺序固定为：

```text
Gate half 0
→ Up half 0
→ compute 16 products
→ Gate half 1
→ Up half 1
→ compute 16 products
→ assemble one 32-column product group
```

`hap_mlp_swiglu_product_frontend16_q4` 使用局部 history/buffer保存尚未配对的 operand，并检查 Gate/Up record顺序。

## 4. SiLU 函数

数学定义：

```text
SiLU(x) = x / (1 + exp(-x))
```

硬件不实时计算指数和除法，而是使用定点查找表：

```text
x ≤ -16 : output 0
-16 < x < +16 : LUT lookup
x ≥ +16 : bypass x
```

LUT采样参数：

```text
range = [-16, +16]
step = 1/256
mathematical samples = 8193
output format = S24 Q8.16
```

物理 BRAM ROM只保存8192个 words。精确的 `+16` endpoint由常量提供，避免为了一个额外 entry把 ROM深度扩展到下一个二次幂。

ROM image：

```text
data/mlp_silu_q16.mem
```

## 5. LUT 地址计算

Gate输入为 S24 Q8.16。对 `-16 < x < +16`：

```text
offset = x + 16
address = round(offset × 256)
```

RTL 等价地对 Q16 code加128后右移8位，实现最接近的 `1/256` 网格采样。

- address 0对应接近 -16。
- address 8192对应 +16 endpoint。
- address 8192不访问 BRAM，而使用常量 `16 << 16`。

## 6. SiLU Pipeline

`hap_mlp_silu_mul` 使用可整体停顿的四级流水：

```text
Stage 1: register selected Gate and Up, form LUT address
Stage 2: synchronous ROM result and zero/LUT/bypass selection
Stage 3: SiLU(Gate) × Up
Stage 4: round to S32 Q16.16 output
```

RTL 中 valid信号覆盖输入寄存器、ROM返回、乘法结果和 output stage。下游反压时使用统一 pipeline enable冻结所有数据和 valid，确保 Gate、Up和 LUT result不发生错位。

流水填满后，在下游持续 ready时可以每周期接受一个 Gate/Up元素并产生一个 product。

## 7. SwiGLU 乘法格式

两个输入：

```text
SiLU(Gate): S24 Q8.16
Up:         S24 Q8.16
```

乘法结果：

```text
S24 × S24
→ S48 Q16.32
→ round-half-away-from-zero
→ arithmetic shift right 16
→ S32 Q16.16
```

该位置不会提前饱和到 S24。S32保留更宽整数范围，供后续 Hadamard使用。

## 8. 16-row 组织

非线性 frontend将16 rows分为两个8-row局部 row stream进行组织，但它们共享相同的 record顺序和完成条件：

```text
row stream 0: rows 0–7
row stream 1: rows 8–15
```

每个 row stream内部有一条物理 `hap_mlp_silu_mul`，所以 production中共有两条相同的 SiLU乘法流水，分别串行处理各自8×16 tile的128个元素。两条流水并行覆盖上下两个 row half，但它们仍属于同一个 MLP层和同一条 record序列。

## 9. Product Group32

两个连续16-column output records形成一个 group32：

```text
16 rows × 32 columns × S32
```

14336个 intermediate columns最终形成：

```text
14336 / 32 = 448 product groups
```

两个 row branch输出带 `group_seq/row/column` tag的 S32 element stream。顶层使用两组 central ring bank收集完整16 rows、32 columns；只有 row scoreboard全部完成后，该 bank才能进入 Hadamard/量化阶段。另一 bank可同时收集下一 group。

## 10. Product Hadamard

central product ring缓存完整 `16×32×S32` group，再用唯一一套 `hap_mlp_hadamard32_s32_norm_stream`依次处理16 rows：

```text
S32 Q16.16
→ 32-point normalized Hadamard
→ S35 Q19.16
```

该 Hadamard包含64个 normalization DSP，并在 row维度时间复用；不是16套完全展开的变换器。

## 11. Product 在线 A8 量化

Hadamard输出按 row分发给4个 `hap_mlp_robust_a8_quantizer_s35`：

```text
quantizer 0: rows 0, 4, 8, 12
quantizer 1: rows 1, 5, 9, 13
quantizer 2: rows 2, 6, 10, 14
quantizer 3: rows 3, 7, 11, 15
```

每个 quantizer处理4 rows，输出：

```text
32 × U8 values/row
1 × U24 metadata/row
```

四个 worker完成后，frontend组装：

```text
16 rows × 32 U8
+ 16 rows × U24 metadata
```

并写入 Down activation cache。在线量化的具体格式见 `02_hadamard_online_quantization.md`。

## 12. Down Cache 接口

每个 product group对应一个 Down cache write：

- group index：0–447。
- activation payload：`16×32×U8`。
- metadata payload：`16×U24`。
- valid/ready：只有双方同时为1才提交。

Gate/Up阶段只有在448个 group全部写入、SwiGLU/Hadamard/quantizer pipeline全部 drain后才可以启动 Down projection。

## 13. 握手与反压

- Gate 和 Up必须同时属于同一位置才可送入 SiLU乘法。
- `hap_mlp_silu_mul` 的下游 stall会冻结整条局部流水。
- product group buffer未释放前不能被下一 group覆盖。
- Hadamard输出只有在目标 quantizer ready时才能前进。
- 量化结果未被 Down cache接受时，U8和 metadata必须保持稳定。
- 计数器只在 `valid && ready` 时更新。

## 14. 错误条件

- Gate/Up matrix tag、record index、row或 half index不匹配。
- 在 half 0未完成时收到 half 1，或重复收到相同 half。
- product group未满32列就提交。
- SiLU pipeline中 operand和 ROM response错位。
- Hadamard row分发与4个 quantizer返回顺序不匹配。
- metadata reserved bits非零。
- product group计数不等于448。

## 15. 绘图要求

非线性模块应画成：

```text
Gate 16-column records ─┐
                        ├── exact-position pairing
Up 16-column records ───┘
          │
          ▼
SiLU LUT: [-16,+16], step 1/256
          │
          ▼
SiLU(Gate) S24 × Up S24
→ S48
→ round to S32 Q16.16
→ assemble 16 rows × 32 columns
→ one shared Hadamard32 across rows
→ four robust A8 quantizers
→ 448-group Down activation cache
```

必须区分：

- SiLU 的数学8193 samples与物理8192-word ROM。
- 16-column projection record与32-column product quantization group。
- 一个共享 Hadamard与4个量化 worker。

不得把 SiLU LUT画成 Attention 的257-entry exp LUT，也不得在 SiLU乘法后直接截断为S24。

## RTL 依据

- `rtl/mlp/hap_mlp_swiglu_product_frontend16_q4.sv`
- `rtl/mlp/hap_mlp_silu_mul.sv`
- `rtl/mlp/hap_mlp_hadamard32_s32_norm_stream.sv`
- `rtl/mlp/hap_mlp_robust_a8_quantizer_s35.sv`
- `rtl/mlp/hap_mlp_down_activation_cache16.sv`

## 真实算数案例：两条16-column记录形成一个 Down group32

本例选择 row 0 的一组32列。前16列来自第一个 projection record，后16列来自第二个 record。数值是人为选择的合法 S24 Q8.16输入，但 LUT 地址、ROM内容、四级流水、乘法舍入、Hadamard和 A8 metadata均按 production RTL 精确计算。

### 1. 四种 Gate/Up 数值

为了同时覆盖 LUT、负端钳零和正端 bypass，32列分成四段：

| lane | Gate | Up | SiLU行为 |
|---|---:|---:|---|
| 0–7 | 1.0 | -0.75 | 读取 LUT |
| 8–15 | 0.5 | 2.0 | 读取 LUT |
| 16–23 | -16.0 | 1.0 | `gate<=-16`，直接输出0 |
| 24–31 | 16.0 | 0.25 | `gate>=+16`，直接 bypass Gate |

它们由两条外部16-column记录进入：

```text
record 0 = lanes  0–15 = 8个(1.0,-0.75) + 8个(0.5,2.0)
record 1 = lanes 16–31 = 8个(-16,1.0) + 8个(16,0.25)
```

### 2. LUT 地址和 SiLU 输出

对 `Gate=1.0`：

```text
gate_raw = 65536
gate_offset = 65536 + 1048576 = 1114112
rounded_address = (1114112 + 128) >> 8 = 4352

silu_rom[4352] = 24'h00BB27
               = 47911
               = 0.7310638427734375
```

对应数学值 `1×sigmoid(1)=0.731058...`。

对 `Gate=0.5`：

```text
gate_raw = 32768
rounded_address = (32768 + 1048576 + 128) >> 8
                = 4224

silu_rom[4224] = 24'h004FAD
               = 20397
               = 0.3112335205078125
```

对边界值：

```text
Gate=-16:
    gate_raw=-1048576
    gate_zero=1
    silu_raw=0

Gate=+16:
    gate_raw=1048576
    gate_bypass=1
    silu_raw=1048576
```

### 3. S48 Q16.32 乘法与 S32 Q16.16 输出

第一段的一个 lane：

```text
silu_raw = 47911
up_raw   = -0.75 × 65536 = -49152

S48 product = 47911 × (-49152)
            = -2354921472

S32 result
= -((abs(-2354921472) + 32768) >> 16)
= -35933
= -0.5482940673828125
```

第二段：

```text
20397 × (2.0×65536) = 2673475584
round / 65536 = 40794
real = 0.622467041015625
```

第三段：

```text
0 × 65536 = 0
```

第四段：

```text
1048576 × (0.25×65536)
→ round / 65536
= 262144
= 4.0
```

所以写入 central product ring 的 row 0为：

```text
product_s32 =
[-35933 × 8 lanes,
  40794 × 8 lanes,
      0 × 8 lanes,
 262144 × 8 lanes]
```

### 4. 四级可停顿 SiLU 流水

对第一个 lane，无反压时数据依次经过：

```text
Stage 1: capture Gate=65536, Up=-49152
Stage 2: 计算 address=4352，同步读取 ROM，保存 bypass/zero tag
Stage 3: silu_raw=47911 与 Up相乘，得到 -2354921472
Stage 4: half-away-from-zero，输出 product_s32=-35933
```

若输出被反压，`pipe_advance=0`，四级中的 valid、Gate/Up tag、ROM结果和乘积同时停住；不会只停最后一级。

### 5. Product Hadamard 的五级结果

下面全部使用原始 Q16整数。第0级就是上一节的32个 product。由于每8个值相同，中间大量节点变成0。

| 级 | 蝶形距离 | 非零结果 |
|---:|---:|---|
| S1 | 1 | lane 0/2/4/6 = -71866；8/10/12/14 = 81588；24/26/28/30 = 524288 |
| S2 | 2 | lane 0/4 = -143732；8/12 = 163176；24/28 = 1048576 |
| S3 | 4 | lane 0 = -287464；8 = 326352；24 = 2097152 |
| S4 | 8 | lane 0 = 38888；8 = -613816；16 = 2097152；24 = -2097152 |
| S5 | 16 | lane 0 = 2136040；8 = -2710968；16 = -2058264；24 = 1483336 |

第五级的四个非零值可直接由四个8-lane常量 `A,B,C,D` 验证：

```text
A=-35933, B=40794, C=0, D=262144

S5[0]  = 8×( A+B+C+D) =  2136040
S5[8]  = 8×( A-B+C-D) = -2710968
S5[16] = 8×( A+B-C-D) = -2058264
S5[24] = 8×( A-B-C+D) =  1483336
```

乘 `11585/65536` 并 half-away-from-zero后，S35 Q16输出为：

```text
lane 0  =  377594 =  5.761627197265625
lane 8  = -479226 = -7.312408447265625
lane 16 = -363846 = -5.551849365234375
lane 24 =  262214 =  4.001068115234375
其余 lane = 0
```

### 6. Product online A8 的真实结果

`hap_mlp_robust_a8_quantizer_s35` 对上述32项得到：

```text
abs_max1 = 479226
abs_max2 = 377594
abs_threshold = 478911

min1 = -478911
min2 = -363846
max2 = 262214
max1 = 377594

clip_low  = -475344
clip_high =  374016
diff      =  849360
```

scale编码过程：

```text
849360 << 12 = 3478978560
再左移一次超过 SCALE_SHIFT_LIMIT
scale_shift = 12

scale numerator
= (3478978560 + 8355840) >> 16
= 53212

scale_code = floor(53212/255) = 208 = 8'hD0
```

zero-point：

```text
adjusted = 475344×2^12 + 208×2^15
         = 1953824768
ratio numerator = 1953824768 >> 16 = 29813
zero_point = floor(29813/208) = 143 = 8'h8F
```

因此：

```text
out_meta = {2'b00, 6'd12, 8'hD0, 8'h8F}
         = 24'h0CD08F

out_u8 =
[255,143,143,143,143,143,143,143,
   0,143,143,143,143,143,143,143,
  34,143,143,143,143,143,143,143,
 222,143,143,143,143,143,143,143]
```

关键 lane复核：

```text
lane 0:
    输入被 clip到374016
    magnitude quotient=112
    q=143+112=255

lane 8:
    输入被绝对阈值/low bound裁到-475344
    magnitude quotient=143
    q=143-143=0

lane16:
    输入=-363846
    magnitude quotient=109
    q=143-109=34

lane24:
    输入=262214
    magnitude quotient=79
    q=143+79=222

零 lane:
    q=zero_point=143
```

### 7. 四个 quantizer 与 Down cache 的实际路由

一个共享 Hadamard按 row 0、1、2、...、15顺序输出。`dispatch_row[1:0]` 选择 quantizer：

```text
row 0  → quantizer 0，本例结果写 output row 0
row 1  → quantizer 1
row 2  → quantizer 2
row 3  → quantizer 3
row 4  → quantizer 0 的下一 wave
...
row 15 → quantizer 3 的第四 wave
```

四个 quantizer完成16行后，模块一次性输出：

```text
16 rows × 32 U8 payload
+ 16 rows × U24 metadata
```

本例的 row 0 payload和 `24'h0CD08F` 写入 Down activation cache的当前 group地址。只有448个 group全部形成后，Down projection才会启动。
