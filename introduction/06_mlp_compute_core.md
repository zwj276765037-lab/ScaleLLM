# MLP 层计算核心

## 1. 模块功能

MLP 计算核心实现 Llama SwiGLU MLP：

```text
Gate = X × W_gate
Up   = X × W_up
Z    = SiLU(Gate) × Up
Y    = Z × W_down
```

模型形状：

```text
X: 16 × 4096
Gate / Up / Z: 16 × 14336
Y: 16 × 4096
```

投影使用 A8W4 group32定点计算。Gate、Up 和 Down 共用同一个物理计算核心。

## 2. 模块层次

```text
hap_mlp_full_command16_s45
├── hap_mlp_input_frontend16_compact_cache
└── hap_mlp_serial_ddr_command16_v5_s45
    ├── hap_mlp_w4_dual_ddr_frontend
    ├── hap_mlp_gate_up_v5_scheduler16_q4
    │   ├── hap_mlp_gate_up_gather_pingpong12
    │   ├── hap_mlp_projection_repack12_to16_s24_history2
    │   └── hap_mlp_swiglu_product_frontend16_q4
    ├── hap_mlp_down_activation_cache16
    ├── hap_mlp_down_v5_scheduler16_s45
    └── hap_mlp_shared_dual_slice16x12_s43_s45
```

production综合时，`hap_mlp_full_command16_v5_s45.sv` 通过宏生成兼容模块名 `hap_mlp_full_command16_s45`。

## 3. 总体数据流

```text
16×4096 S24 input
→ Hadamard32 + online A8
→ 128-group input activation cache
→ Gate/Up A8W4 projection
→ 12-column result to 16-column order
→ SiLU(Gate) × Up
→ Hadamard32 + online A8
→ 448-group Down activation cache
→ Down A8W4 projection
→ 12-column result to 16-column order
→ 16×4096 S24 output
```

## 4. 顶层控制

Full-command wrapper状态：

```text
IDLE
→ CLEAR
→ LAUNCH
→ RUN
→ RELEASE_ISSUE
→ RELEASE_WAIT
→ IDLE
```

- `CLEAR` 初始化当前命令的状态和计数器。
- `LAUNCH` 锁存 activation bank、metadata bank和 DDR base address。
- `RUN` 执行 Gate/Up和 Down。
- `RELEASE_ISSUE/WAIT` 确认 input cache和资源所有权完成释放。

串行计算引擎状态：

```text
P_IDLE
→ P_GATE_LAUNCH
→ P_GATE_RUN
→ P_DOWN_LAUNCH
→ P_DOWN_RUN
→ P_IDLE
```

Gate/Up 阶段的 DDR done和 compute done必须同时成立，才能进入 Down。

## 5. 输入 activation cache

Hidden 4096被分成：

```text
4096 / 32 = 128 group32
```

每个输入 group包含：

```text
16 rows × 32 × S24
= 12288 bits
= 48 × 256-bit AXI beats
```

`hap_mlp_input_frontend16_compact_cache` 对输入执行 Hadamard32和 online A8量化，并保存：

```text
16 rows × 32 U8 values
16 rows × U24 activation metadata
```

输入 cache使用两个 bank。只有被命令选中的 bank完整 ready时，full-command wrapper才接受启动。

## 6. 外部 W4 权重格式

所有 MLP 权重在 DDR中保持 16-column ABI：

```text
16 columns × 32 weights × 4 bits = 2048-bit payload
```

双 DDR分担：

```text
DDR0 = 8 columns × 32 × W4 = 1024 bits
DDR1 = 8 columns × 32 × W4 = 1024 bits
```

两个 half-group合并为一个16-column record，并配对一条224-bit metadata：

```text
[127:0]   16 × scale_code U8
[223:128] 16 × scale_shift U6
```

物理 kernel的12列宽度不会改变外部 DDR或 metadata格式。

## 7. Gate/Up 权重数量和顺序

Intermediate 14336对应：

```text
14336 / 16 = 896 external records/matrix
Gate + Up = 1792 records/hidden group
1792 × 128 groups = 229376 source transactions
```

外部 source为 tile-major顺序。对每个最多48-column block：

```text
record 0: Gate groups 0..127, then Up groups 0..127
record 1: Gate groups 0..127, then Up groups 0..127
record 2: Gate groups 0..127, then Up groups 0..127
```

最后一个 block只有32个有效列，因此只接收 record 0和 record 1。

## 8. 16-column 到 12-column Gearbox

物理 kernel一次只计算12列。`hap_mlp_gate_up_gather_pingpong12` 将三个外部 record收集成48列：

```text
3 × 16 external columns
→ 48-column ping-pong gather bank
→ 4 × 12-column physical passes
```

列映射：

```text
pass 0 = columns 0–11
pass 1 = columns 12–23
pass 2 = columns 24–35
pass 3 = columns 36–47
```

`14336 = 298×48 + 32`，所以总计299个 block。最后32列生成三个 pass：12列、12列、8列；最后4个物理 lane由 valid mask屏蔽。

ping-pong bank允许一侧被 kernel读取时，另一侧继续收集下一个48-column block。

每个矩阵的内部 physical tile数量为：

```text
ceil(14336 / 12) = 1195 tiles
Gate + Up = 2390 tiles
2390 × 128 hidden groups = 305920 kernel transactions
```

## 9. 物理 A8W4 Kernel

核心模块：

```text
hap_mlp_shared_dual_slice16x12_s43_s45
```

物理结构：

```text
low slice:  rows 0–7  × 12 columns
high slice: rows 8–15 × 12 columns
```

两个 slice并行处理同一组12列权重，因此一个 compute request逻辑上覆盖16 rows ×12 columns。

每个8×12 slice：

```text
8 rows
× 6 two-column lanes/row
× 32 pack2 DSP/lane
= 1536 DSP48E2
```

两块合计：

```text
2 × 1536 = 3072 DSP48E2
```

## 10. Pack2 DSP

`hap_a8w4_pack2_dsp` 使用一个 DSP48E2同时计算一个 activation对两个相邻 W4列的乘积。

输入：

```text
one centered activation S9
two signed weights S4: weight0, weight1
```

两个 W4被打包为一个 S16 operand：

```text
packed_weight = {weight1, sign-extended weight0 field}
DSP product = activation × packed_weight
```

通过字段提取、符号修正和 carry修正，精确恢复：

```text
product0 S12 = activation × weight0
product1 S12 = activation × weight1
```

一个 pack2 leaf对应一个 DSP，不是两个 DSP。

## 11. Group32 Lane

一个 two-column lane包含32个 pack2 DSP：

```text
32 × two S12 products
→ two independent LUT reduction trees
→ dot0 S17 and dot1 S17
```

ScaleCode恢复：

```text
raw S33 = dot S17 × activation_code × weight_code
total_shift = activation_shift + weight_shift
guard S36 = raw × 2^(24-total_shift)
```

非零数据的合法 `total_shift` 范围为21到44。输出为两列 S36 Q12.24 group partial。

## 12. Gate/Up 累加与输出重排

Gate/Up 每个 projection tile累加128个 hidden group：

```text
S36 group partial
→ S43 tile accumulator
→ round and saturate
→ 12-column S24 tile
```

`hap_mlp_projection_repack12_to16_s24_history2` 将连续12-column tile恢复为外部16-column顺序：

```text
physical stream: 12 + 12 + 12 + 12
logical stream:  16 + 16 + 16
```

Gate和 Up各输出896个16-column records。重排只改变列分组，不改变数值。

## 13. Down activation

Gate/Up结果进入 MLP 非线性模块，产生 S32 Q16.16 SwiGLU product。随后执行 Hadamard32和 online A8量化，写入：

```text
hap_mlp_down_activation_cache16
```

Down input数量：

```text
14336 / 32 = 448 group32
```

每个 group保存16 rows的 A8 values和 U24 metadata。

## 14. Down Projection

Down输出4096列，外部 W4 source数量为：

```text
4096 / 16 = 256 records/group
256 × 448 groups = 114688 source transactions
```

内部12-column compute tile数量：

```text
ceil(4096 / 12) = 342 tiles
```

- tiles 0–340：12个有效列。
- tile 341：4个有效列，8个 lane被 mask。

Down按 group-major顺序工作：对 activation group 0–447依次读取该组的256个外部 weight records，并形成342个内部 compute requests。

## 15. Down 累加与输出

Down对每个输出 tile累加448个 activation group：

```text
S36 group partial
→ S45 group-major accumulator
→ round and saturate
→ 12-column S24 tile
→ 12-to-16 inverse gearbox
→ 256 × 16-column output records
```

最终输出：

```text
16 rows × 4096 × S24
= 256 tile16 records
= 6144 × 256-bit AXI beats
```

342×12产生4104个物理 slot，但只有前4096列有效；最后8个 slot不能写入模型输出。

## 16. Gate/Up/Down 的资源共享

同一对8×12 slices按阶段复用：

```text
Gate/Up phase: shared lanes → S43 accumulator
Down phase:    shared lanes → S45 accumulator
```

S43和 S45 accumulator是不同的累加路径，但前面的3072个 pack2 DSP完全共享。不能为 Gate、Up、Down各计算一次3072 DSP。

## 17. 完成条件和错误

Gate/Up 完成需要：

- 229376条 W4和 metadata transaction完成。
- 所有12-column pass完成。
- Gate/Up各896条16-column结果完成重排。
- 448个 SwiGLU activation group写入 Down cache。
- DDR、gather、kernel、repack和 nonlinear pipeline全部 drain。

Down 完成需要：

- 114688条 source transaction完成。
- `448×342` 个 group/tile compute request完成。
- 342个最终 S24 tile完成。
- 256条16-column output record被接收。

错误包括 group/tile次序错误、metadata reserved bits非零、shift越界、tail mask错误、row-half tag不一致和 output record遗漏/重复。

## 18. 绘图要求

MLP 核心图必须表达：

- `16×4096 → 16×14336 → 16×4096`。
- 外部权重记录宽16列，物理 kernel宽12列。
- `3×16 → 4×12` gather和 `12→16` inverse gearbox。
- 两个并行8×12 row-half slices。
- 每个 slice的 `8×6×32 = 1536 DSP`。
- 一个 DSP通过 pack2产生两列乘积。
- Gate/Up使用 S43 accum，Down使用 S45 accum。
- Gate、Up、Down共用同一套3072 DSP lanes。
- Down最后一个 tile只有4个有效列。

不得把物理 kernel画成16列，也不得为三个投影复制三套 kernel。

## RTL 依据

- `rtl/mlp/hap_mlp_full_command16_v5_s45.sv`
- `rtl/mlp/hap_mlp_serial_ddr_command16_v5_s45.sv`
- `rtl/mlp/hap_mlp_gate_up_v5_scheduler16_q4.sv`
- `rtl/mlp/hap_mlp_gate_up_gather_pingpong12.sv`
- `rtl/mlp/hap_mlp_shared_dual_slice16x12_s43_s45.sv`
- `rtl/mlp/hap_a8w4_slice8x12_group_s36.sv`
- `rtl/mlp/hap_a8w4_group32_lane2_s36.sv`
- `rtl/mlp/hap_a8w4_pack2_dsp.sv`
- `rtl/mlp/hap_mlp_down_v5_scheduler16_s45.sv`
- `rtl/mlp/hap_mlp_down_group_major_accum_s45.sv`

## 真实算数案例：Gearbox、一个 pack2 DSP 和 128-group 累加

本例使用合法的小整数，完整追踪一个 row上的两个 output columns。它对应一个 `hap_a8w4_group32_lane2_s36`：内部包含32个 pack2 DSP，同时得到两列 dot。其他 row和其他 output columns在物理硬件中并行执行相同结构。

### 1. `3×16 → 4×12` 的具体列映射

先给三个外部 record放入容易识别的列编号：

```text
R0 = [ 0, 1, 2, ...,15]
R1 = [16,17,18, ...,31]
R2 = [32,33,34, ...,47]
```

ping-pong gather bank把它们拼成一个48列向量，然后按物理 kernel宽度读出：

```text
pass0 = [ 0, 1, 2, ...,11]
pass1 = [12,13,14, ...,23]
pass2 = [24,25,26, ...,35]
pass3 = [36,37,38, ...,47]
```

计算完成后，inverse gearbox按原位置恢复：

```text
pass0[0:11] + pass1[0:3]  → output record [0:15]
pass1[4:11] + pass2[0:7]  → output record [16:31]
pass2[8:11] + pass3[0:11] → output record [32:47]
```

因此 gearbox只改变物理分组，不进行数值加法。在全矩阵最后一个32-column block中，只产生两个完整12列 pass和一个8列 pass；第三个 pass的 `column_valid_u12=12'h0FF`，最后4个 lane不能进入输出。

### 2. 一个 group32 的两列输入

取 kernel已经完成 zero-point中心化后的 S9 activation：

```text
a = [1,2,3,4,5,6,7,8,
     9,10,11,12,13,14,15,16,
     17,18,19,20,21,22,23,24,
     25,26,27,28,29,30,31,32]
```

两个 W4 output column分别取：

```text
w0 = [-3,1,1,1,1,1,1,1,
       1,1,1,1,1,1,1,1,
       1,1,1,1,1,1,1,1,
       1,1,1,1,1,1,1,1]

w1 = [2,-1,2,-1,2,-1,2,-1,
      2,-1,2,-1,2,-1,2,-1,
      2,-1,2,-1,2,-1,2,-1,
      2,-1,2,-1,2,-1,2,-1]
```

### 3. lane 0 的一个 DSP 如何同时算两列

lane 0输入为：

```text
activation = 1
weight0 = -3 = 4'hD
weight1 =  2 = 4'h2
```

`hap_a8w4_pack2_dsp` 把低权重符号扩展到12 bit，再与高权重拼接：

```text
sign_extend_12(weight0) = 12'hFFD
packed_weight_s16 = {4'h2, 12'hFFD}
                   = 16'h2FFD
                   = 12285

DSP P = activation × packed_weight
      = 1 × 12285
      = 12285
      = 25'h02FFD
```

低列直接取低12 bit：

```text
product0 = signed(P[11:0])
         = signed(12'hFFD)
         = -3
```

高列不能只取 `P[24:12]`，必须消除低字段符号扩展和负低乘积引起的 arithmetic-floor carry：

```text
P[24:12] = 2
weight0_negative ? activation : 0 = 1
P[11] = 1

product1 = 2 - 1 + 1 = 2
```

最终正好恢复两个独立乘法 `1×(-3)=-3` 和 `1×2=2`。这就是一颗 DSP48E2 同时服务两个 W4 output columns的真实位级行为。

### 4. 32个 DSP 输出与五级加法树

32个 leaf对 column 0产生：

```text
p0 =
[-3,2,3,4,5,6,7,8,
  9,10,11,12,13,14,15,16,
 17,18,19,20,21,22,23,24,
 25,26,27,28,29,30,31,32]
```

加法树各级为：

```text
2项和  = [-1,7,11,15,19,23,27,31,
          35,39,43,47,51,55,59,63]
4项和  = [6,26,42,58,74,90,106,122]
8项和  = [32,100,164,228]
16项和 = [132,392]
32项和 = [524]
```

column 1的32个 leaf输出为：

```text
p1 =
[2,-2,6,-4,10,-6,14,-8,
 18,-10,22,-12,26,-14,30,-16,
 34,-18,38,-20,42,-22,46,-24,
 50,-26,54,-28,58,-30,62,-32]
```

对应加法树：

```text
2项和  = [0,2,4,6,8,10,12,14,
          16,18,20,22,24,26,28,30]
4项和  = [2,10,18,26,34,42,50,58]
8项和  = [12,44,76,108]
16项和 = [56,184]
32项和 = [240]
```

因此 `dot0_s17=524`，`dot1_s17=240`。

### 5. ScaleCode 恢复到 S36 Q12.24

为该 row选择 activation metadata：

```text
activation_code  = 128
activation_shift = 16
```

两列 weight metadata分别为：

```text
column0: weight_code=64, weight_shift=8
column1: weight_code=32, weight_shift=8
```

两个 total shift都为 24，所以 `align_raw_s36` 不需要左右移：

```text
raw0 = dot0 × activation_code × weight0_code
     = 524 × 128 × 64
     = 4292608

guard0 = raw0 <<< (24-24) = 4292608

raw1 = dot1 × activation_code × weight1_code
     = 240 × 128 × 32
     = 983040

guard1 = raw1 <<< (24-24) = 983040
```

这些 guard都使用 S36 Q12.24。这里没有每 group舍入。

### 6. Gate/Up 的 128-group accumulator

假定这是 hidden group 0，且 group 1–127对这两个输出列的 guard均为 0：

```text
group 0:
    in_first=1
    accum0=4292608
    accum1=983040

group 1...126:
    in_first=0, in_last=0
    accum保持不变

group 127:
    in_last=1
    加入最后一个0并触发 finalize
```

S43 Q19.24 accumulator只在完整128组结束后统一除以 `2^8`，转成 S24 Q8.16：

```text
column0 S24 raw = (4292608 + 128) >> 8
                 = 16768
column0 real    = 16768 / 65536
                 = 0.255859375

column1 S24 raw = (983040 + 128) >> 8
                 = 3840
column1 real    = 3840 / 65536
                 = 0.05859375
```

两个结果都不饱和。它们作为同一个12-column physical pass中的两个列结果，随后由 inverse gearbox恢复到外部16-column顺序。

### 7. 这个局部算例在完整阵列中的复制位置

```text
1个 lane2:
    32个 pack2 DSP → 同一 row的2个 output columns

1个 row:
    6个 lane2 × 32 DSP = 192 DSP → 12 columns

1个 8×12 slice:
    8 rows × 192 DSP = 1536 DSP

两个 row-half slices:
    2 × 1536 = 3072 DSP
```

Gate、Up和 Down改变的是调度阶段、group数和 accumulator宽度，不会再复制上述3072颗 DSP。Down阶段采用448组和 S45 accumulator，但 pack2与五级加法树的单组算术完全相同。
