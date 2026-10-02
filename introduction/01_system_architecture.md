# ScaleLLM V5 整体系统架构

## 1. 系统目标

ScaleLLM V5 面向 VCU118 FPGA，实现 Llama-3.1-8B 单层中的 Attention 和 MLP 主计算路径。

| 项目 | 参数 |
|---|---:|
| FPGA | VCU118，`xcvu9p-flga2104-2L-e` |
| Hidden size | 4096 |
| Intermediate size | 14336 |
| Transformer layers | 32 |
| 每次计算的逻辑行数 | 16 token rows |
| 可交错在途 cohort | 2，即最多32 active rows |
| Core clock | 100 MHz |
| DDR0 / DDR1 UI clock | 300 MHz / 300 MHz |
| Tensor AXI | 256-bit，读写 |
| Weight AXI | 2 × 512-bit，只读 |

当前 production RTL 由 `attention_mlp_production_v5_cohort16_sources.list` 选择，并固定使用：

- Attention：`hap_attention_board_cohort16_core`
- MLP：`hap_mlp_full_command16_s45`，源码实现位于 `hap_mlp_full_command16_v5_s45.sv`

普通 8-row Attention 顶层、OOC harness 和 testbench 不属于正式系统架构。

## 2. 顶层硬件层次

```text
hap_attention_mlp_board_core
└── hap_attention_mlp_production_core
    ├── AXI-Lite control and status
    ├── 256-bit tensor / metadata DMA
    ├── paired dual-DDR weight subsystem
    ├── resident metadata memory
    └── hap_attention_mlp_resource_top
        ├── hap_attention_board_cohort16_core
        └── hap_mlp_full_command16_s45
```

`hap_attention_mlp_board_core` 是板级边界；`hap_attention_mlp_production_core` 负责控制、DMA、metadata 和 DDR 资源共享；`hap_attention_mlp_resource_top` 包含两个计算核心。

两个 interleaved cohorts表示调度上允许两组16-row工作交错推进，不表示复制两套 Attention和 MLP算术阵列。

## 3. 系统数据流

```text
External tensor DDR
      │ 256-bit AXI
      ▼
Input / output DMA
      │
      ├── Attention core ──► Attention output
      │
      └── MLP core ───────► MLP output

DDR0 512-bit ─┐
               ├── paired weight arbiter ──► W8 / W4 frontends ──► compute cores
DDR1 512-bit ─┘

Metadata DMA ──► on-chip resident URAM ──► projection engines
```

Tensor 和权重使用不同的 AXI 通路：

- 256-bit AXI 搬运输入、输出、Attention metadata、MLP metadata 和 RoPE 系数。
- 两条 512-bit AXI 只读取矩阵权重 payload。
- 权重 payload 保存在外部 DDR；片上 URAM 保存当前层量化 metadata，而不是完整权重矩阵。

AXI-Lite control由 `hap_attention_mlp_axil_router` 分区：`0x000–0x0ff` 属于 Attention，`0x100` 及以上属于 MLP和 production integration。

## 4. Attention 路径

```text
16×4096 S24 input
→ Hadamard32 + online A8 quantization
→ Q / K / V A8W8 projection
→ RoPE
→ K/V quantization and KV cache
→ QK score
→ Softmax
→ probability × V
→ context
→ Hadamard32 + online A8 quantization
→ Wo projection
→ 16×4096 S24 output
```

Attention 的逻辑批次是 16 rows，但 projection array 的物理高度只有 8 rows：

- `wave0` 处理 rows 0–7。
- `wave1` 处理 rows 8–15。
- 两个 wave 共用同一套 W8 权重和同一物理计算阵列。
- 两个 accumulator context 分别保存两个 wave 的累加状态。
- Q、K、V 和 Wo 也复用同一 projection array。

Attention projection array 使用 2240 个 DSP48E2。

## 5. MLP 路径

```text
16×4096 S24 input
→ Hadamard32 + online A8 quantization
→ Gate projection + Up projection
→ SiLU(Gate) × Up
→ Hadamard32 + online A8 quantization
→ Down projection
→ 16×4096 S24 output
```

MLP 的逻辑高度是 16 rows，物理计算核心为：

```text
2 × 8-row slices × 12 output columns
```

- rows 0–7 由第一个 8×12 slice 处理。
- rows 8–15 由第二个 8×12 slice 处理。
- 外部权重格式仍是 16 columns。
- FPGA 内部使用 `3×16 → 4×12` gearbox，把外部记录转换成 12-column 物理 pass。
- Gate、Up 和 Down 在时间上复用同一对 8×12 slices。

两个 slices 合计使用 3072 个 DSP48E2。

## 6. 双 DDR 权重系统

Attention 和 MLP 共享 DDR0、DDR1。`hap_axi512_paired_2client_read_wrr` 保证两个物理通道始终选择同一个 client 和同一个逻辑事务。

持续同时竞争时，三相 weighted round-robin 的 nominal 比例为：

```text
Attention : MLP = 1 : 2
```

Attention W8 group：

```text
DDR0: 8 columns × 32 × W8 = 2048 bits
DDR1: 8 columns × 32 × W8 = 2048 bits
合并: 16 columns × 32 × W8 = 4096 bits
```

MLP W4 group：

```text
DDR0: 8 columns × 32 × W4 = 1024 bits
DDR1: 8 columns × 32 × W4 = 1024 bits
合并: 16 columns × 32 × W4 = 2048 bits
```

两个通道的 descriptor 必须具有匹配的 sequence、ARLEN、ARSIZE 和 ARBURST。物理响应先在各自 DDR 时钟域按 owner tag 返回 Attention 或 MLP，再通过 client 自己的异步 half-group FIFO 跨回 core 域。

## 7. Metadata 和片上存储

Attention 单层 metadata：

```text
640 projection tiles × 128 groups × 256 bits
= 81920 × 256-bit records
```

MLP 每个 metadata bank：

```text
Gate/Up: 229376 × 224-bit records
Down:    114688 × 224-bit records
```

MLP 使用 A/B 两套完整 metadata image：active bank 为当前层计算提供数据，inactive bank 可加载下一层。bank commit 必须等待目标 bank 精确写满、consumer quiescent 且所有 metadata response pipe 为空。

## 8. 时钟域和控制

系统具有三个异步时钟域：

```text
core_clk       100 MHz
ddr0_ui_clk    300 MHz
ddr1_ui_clk    300 MHz
```

- 稳定 compute command 使用 `xpm_cdc_handshake`。
- 窄 AXI descriptor 使用异步 FIFO。
- 宽权重 payload 使用 half-group async FIFO/assembler。
- FIFO 指针使用 Gray-code CDC。
- sticky error level 使用 single-bit CDC。

DDR owner mode：

| 编码 | 模式 |
|---:|---|
| 0 | IDLE |
| 1 | ATTN_ONLY |
| 2 | MLP_ONLY |
| 3 | SHARED |

模式切换必须等待 Attention、MLP 和 paired DDR leaf 全部 quiescent。soft clear 也必须先停止新请求并 drain 在途事务。

## 9. 板级数据量

一个 `16×4096×S24` tensor 占：

```text
16 × 4096 × 24 bits = 6144 × 256-bit AXI beats
```

Attention board wrapper 的顺序为：

```text
metadata load（可选）
→ RoPE load（可选）
→ input load
→ compute
→ output writeback
```

MLP input 按 128 个 group32 读取，每组 48 个 AXI256 beats；MLP output 按 256 个 tile16 写回，每个 tile 24 个 AXI256 beats。

## 10. 绘图要求

系统总图必须表达：

- 三个异步时钟域。
- 一条 256-bit tensor/metadata AXI 和两条 512-bit weight AXI。
- Attention 的“逻辑 16 rows、物理 8 rows、两个时间 wave”。
- MLP 的“外部 16 columns、内部 12 columns、两个 8×12 slices”。
- Attention 与 MLP 对双 DDR 的 paired ownership。
- 外部权重 payload 与片上 metadata URAM 的分离。
- Q/K/V/Wo 共用 Attention projection array。
- Gate/Up/Down 共用 MLP kernel。

不得画成两个完整 Attention arrays，也不得为 Gate、Up、Down 各画一套 MLP array。当前仓库只确认 synth、opt 和 pre-place 审计，不能标注为已完成 route、bitstream 或实板测量。

当前 production core的综合资源审计结果为：

```text
5453 DSP48E2
752 URAM288
812 BRAM tiles
```

## RTL 依据

- `rtl/integration/hap_attention_mlp_board_core.sv`
- `rtl/integration/hap_attention_mlp_production_core.sv`
- `rtl/integration/hap_attention_mlp_resource_top.sv`
- `rtl/integration/hap_axi512_paired_2client_read_wrr.sv`
- `rtl/attention/hap_attention_board_cohort16_core.sv`
- `rtl/mlp/hap_mlp_full_command16_v5_s45.sv`

## 真实算数案例：一次 DMA、双 DDR 和双 wave 工作窗口

下面使用人为选定但完全合法的小数值，以便手工复算。这里的“真实”是指数据宽度、定点编码、DDR 拼接、舍入和资源复用都与 production RTL 一致；数值本身不是从某次模型推理中截取的权重。

### 1. 一个 cohort 的 Tensor DMA

一条命令携带 16 行、每行 4096 个 S24 元素：

```text
元素数 = 16 × 4096 = 65536
总位数 = 65536 × 24 = 1572864 bit
AXI256 beat 数 = 1572864 / 256 = 6144
```

因此系统图中的 tensor DMA 必须表现为一条连续的 6144-beat 搬运，而不能画成 16 条独立外部总线。数据进入 core 域后，row 0–7 形成 wave0，row 8–15 形成 wave1。

### 2. 双 DDR 的一个真实 burst 仲裁窗口

假定两个 client 持续有请求，且起始地址均满足 1024-byte 对齐：

| Client | DDR0 base | DDR1 base | 每通道一个 burst |
|---|---:|---:|---:|
| Attention | `0x1000_0000` | `0x2000_0000` | 16 个 512-bit beat |
| MLP | `0x3000_0000` | `0x4000_0000` | 16 个 512-bit beat |

三相 WRR 从 phase 0 开始时，成对 descriptor 的接受顺序为：

| pair sequence | WRR phase | owner | DDR0 与 DDR1 的动作 |
|---:|---:|---|---|
| 0 | 0 | Attention | 两个通道同时接受 Attention descriptor |
| 1 | 1 | MLP | 两个通道同时接受 MLP descriptor |
| 2 | 2 | MLP | 两个通道同时接受 MLP descriptor |
| 3 | 0 | Attention | 回到下一轮 |

这就是 `Attention : MLP = 1 : 2` 的真实含义：按 paired AXI burst 仲裁，不是每拍在两个 client 之间切换一个乘法数据。

一个 Attention 通道的 16-beat burst包含：

```text
16 beats / 4 beats per W8 half-group = 4 half-groups
DDR0 half-group = columns 0–7  = 2048 bit
DDR1 half-group = columns 8–15 = 2048 bit
两侧按相同 sequence 配对后：
{DDR1 half, DDR0 half} = 4096-bit W8 group
```

一个 MLP 通道的 16-beat burst包含：

```text
16 beats / 2 beats per W4 half-group = 8 half-groups
DDR0 half-group = columns 0–7  = 1024 bit
DDR1 half-group = columns 8–15 = 1024 bit
两侧配对后：
{DDR1 half, DDR0 half} = 2048-bit W4 group
```

所以同样是每通道 16 个 beat，一个 paired Attention burst形成 4 个完整 W8 group，一个 paired MLP burst形成 8 个完整 W4 group。owner tag 随响应返回，不能只凭返回时间判断数据属于哪个核心。

### 3. 同一份 Attention 权重如何依次计算两个 wave

取 Attention 的某个 output column、某个 group32。为了让计算可复核，令该列的 32 个 W8 全部为 `32`，activation zero-point为 `128`：

```text
row 0 的 32 个 activation_u8 全部为 129
row 8 的 32 个 activation_u8 全部为 130

row 0 centered activation = 129 - 128 = 1
row 8 centered activation = 130 - 128 = 2
```

设 activation metadata为 `code=128, shift=16`，weight metadata为 `code=128, shift=10`。总 shift 为 26。

wave0 中 row 0 的 group dot：

```text
dot0 = 32 lanes × 1 × 32 = 1024
code_product = 128 × 128 = 16384
raw0 = 1024 × 16384 = 16777216
guard0 = raw0 >>> (26 - 24)
       = 16777216 >>> 2
       = 4194304
```

wave1 中 row 8 使用同一份 W8 group：

```text
dot8 = 32 lanes × 2 × 32 = 2048
raw8 = 2048 × 16384 = 33554432
guard8 = 33554432 >>> 2 = 8388608
```

若其余 127 个输入 group均为零，则两个 accumulator context分别保持：

```text
wave0_accum[row0] = 4194304
wave1_accum[row8] = 8388608
```

最终 S42 Q18.24 到 S24 Q8.16 需要除以 `2^8` 并执行 half-away-from-zero：

```text
row 0 output raw = (4194304 + 128) >> 8 = 16384 = 0.25
row 8 output raw = (8388608 + 128) >> 8 = 32768 = 0.50
```

硬件时序不是两套阵列并行计算，而是：

```text
W8 group g 到达并被锁存
→ wave0 读取 rows 0–7，得到各自 guard
→ wave1 读取 rows 8–15，得到各自 guard
→ 两个 accumulator context分别更新
→ 直到两个 wave都消费后才释放 group g
```

因此系统框图应画“一份 paired W8 group扇出到同一个 8-row array的两个时间 wave”，而不是画两套 2240-DSP Attention 阵列。

### 4. 同一时刻 MLP 路径中的物理含义

当上表中的 MLP burst返回时，一个 2048-bit W4 group先恢复成外部 16-column record。连续三个 record覆盖 48 个逻辑列：

```text
record 0 = columns  0–15
record 1 = columns 16–31
record 2 = columns 32–47
```

片上 gearbox随后产生：

```text
pass 0 = columns  0–11
pass 1 = columns 12–23
pass 2 = columns 24–35
pass 3 = columns 36–47
```

每个 pass同时送入两个 8×12 slices：slice 0计算 rows 0–7，slice 1计算 rows 8–15。这里是空间上的两个 row-half，而 Gate、Up、Down 是时间上复用同一对 slices。

这个案例对应系统图中的四种不同复用关系：

1. DDR0/DDR1 是并行配对，不是互相替代。
2. Attention wave0/wave1 是时间复用同一阵列。
3. MLP 的两个 8-row slice 是空间并行。
4. Q/K/V/Wo 以及 Gate/Up/Down 分别在各自核心内时间复用计算资源。
