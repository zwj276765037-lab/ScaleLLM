# ScaleCode 与浮点反量化数据通路的模块化硬件对比实验

## 1. 实验目的

本实验要验证以下核心命题：ScaleLLM 用 `scale_code + scale_shift` 表示动态 scale，并在后续数据通路中使用整数乘法、定点对齐和移位；相对于“计算核整数累加结果先反量化成 FP16/FP32，再由浮点 RoPE、QK、Softmax、PV、SiLU/SwiGLU、MLP Down 等算子继续计算”的设计，在达到相同逻辑输出算力时，ScaleCode 路径是否能够：

1. 使用更少的 FPGA 计算与存储资源；
2. 降低单组数据的周期数或绝对计算时间；
3. 保持规定的数值精度和模型语义；
4. 在 Attention 与 MLP 完整后处理链上仍然保持收益，而不只是在孤立微核上受益。

实验必须同时报告正结果和负结果。尚未完成实现、综合、布局布线和测量前，不预设结论成立。

## 2. 假设与待回答问题

- **H1（资源）**：在共同 100 MHz 约束和相同持续输出率下，ScaleCode 版本的 LUT、FF、DSP48E2、BRAM、URAM 中至少主要计算资源显著少于 FP16，且相对 FP32 的收益更大。
- **H2（速度）**：在相同工作负载和无下游阻塞条件下，ScaleCode 版本的 `cycles/work-unit` 或 `ns/work-unit` 小于等吞吐 FP baseline。
- **H3（扩展性）**：当有效 key 数从 1 扩展到 128、或 MLP reduction 从 128 group 扩展到 448 group 时，收益不会被格式转换、缓存或控制开销抵消。
- **H4（数值）**：SC 与 FP baseline 的在线 A8 均遵循最终原始
  Group32 Min/Max 合同；SC RTL 对独立 Min/Max golden bit-exact，FP16/FP32
  baseline 与共同高精度 golden 的误差在预先声明的阈值内。

需要回答的不只是“一个整数乘法器比浮点乘法器小多少”，还包括反量化边界、跨算子格式保持、缓存宽度、吞吐复制数和流水填充/排空开销。

## 3. 冻结的生产基线

实验建立时的仓库锚点为 `ScaleLLM` HEAD `66e6b87`；若后续 RTL 变化，每次结果必须额外记录真实 commit、dirty 状态和输入文件哈希。

| 项目 | 当前生产规格/约束 |
|---|---|
| 模型 | Llama-3.1-8B，32 layers，hidden 4096，intermediate 14336 |
| FPGA | AMD/Xilinx VCU118，`xcvu9p-flga2104-2L-e` |
| 工具 | Vivado 2025.2 |
| 主比较时钟 | core 100 MHz；DDR0/DDR1 300 MHz |
| OOC 时钟源模型 | 所有版本固定 `HD.CLK_SRC=BUFGCE_X0Y0`；setup uncertainty 0.150 ns，hold uncertainty 0 ns |
| 外部 activation ABI | S24 Q8.16 |
| 在线 A8 合同 | Hadamard 后每 row 连续 group32 原始 Min/Max，范围包含 0；U8/zp 使用 ideal scale，nearest-even；禁止量化前 clipping |
| Attention | A8W8，group32，physical 8 rows × 16 columns，2 waves/cohort，projection 2240 DSP48E2 |
| Attention projection 峰值锚点 | lane `II=2`；100 MHz 下理论 useful peak 409.6 GOPS（MAC 计 2 ops，仅作几何校验） |
| MLP | A8W4，group32，physical `2 × 8 × 12`，3072 DSP48E2，片内 `3×16 → 4×12` |
| MLP kernel 峰值锚点 | lane `II=1`；100 MHz 满占用理论 useful peak 1.2288 TOPS（packed 两列，MAC 计 2 ops，仅作几何校验） |
| cohort | 16 logical rows，two interleaved cohorts |
| 系统分析值 | Attention 70.58 processed token/s；MLP 94.82；理想双 cohort pipeline 70.58；均非板测值 |

理论 GOPS 只用于发现少复制/多复制错误，不能替代握手事件计数。模块的真实“输出算力”定义为：`out_valid && out_ready` 在稳定无阻塞窗口内完成的逻辑结果数量/秒，并同时记录结果向量宽度、II、首结果延迟和整批完成周期。

## 4. 比较版本

每个模块至少实现三种版本：

| ID | 数据通路 | 说明 |
|---|---|---|
| `SC` | 当前 ScaleCode/定点整数路径 | 以 production RTL 数值与 ready/valid 行为为基准；scale code 乘法、定点 guard、算术移位、round/saturate |
| `FP16` | FP16 scale 与 FP16 后续计算 | 主浮点 baseline；整数计算核输出转换为 FP16，并应用 FP16 scale 后进入 FP16 算子 |
| `FP32` | FP32 scale 与 FP32 后续计算 | 精度/资源上界对照；整数计算核输出转换为 FP32，并应用 FP32 scale 后进入 FP32 算子 |

如 Xilinx Floating-Point IP 的内部 accumulator 精度高于端口精度，必须记录 IP 配置、舍入模式、latency、DSP usage 和生成文件哈希，不能只写“FP16”或“FP32”。

### 4.1 两种成本口径

每个模块必须同时给出以下结果：

1. **Operator-only**：FP 版本从已反量化的 FP 输入开始，不计输入反量化；这是对 ScaleCode 最保守的对比。
2. **Boundary-inclusive（主结论口径）**：从相同整数 dot/量化 payload 与 scale 元数据开始，FP 版本包含 int-to-float、scale 乘法和必要的格式寄存/缓冲；ScaleCode 版本包含对应 code recovery、shift alignment 和缓冲。

完整链统计时，连续 FP 算子之间保持 FP，不得在每个子模块重复计算反量化成本；反量化只在真实边界计一次。孤立模块资源不能简单相加为系统资源，必须对非重叠层次或独立链顶层重新综合。

## 5. 模块划分与共同输出合同

| 实验目录 | ScaleCode production 锚点 | 匹配的逻辑输出/算力单位 |
|---|---|---|
| `00_scale_apply_microkernel` | `hap_a8w8_group32_lane_s42`、`hap_a8w4_scalecode_recover2_lut` | A8W8 每个 group32 一份 S42 contribution（II=2）；A8W4 每个 group32 两列 S36 contribution（II=1） |
| `01_attention_input_hadamard_a8` | `hap_attention_frontend_8row`、Hadamard、实验内 Min/Max A8 drop-in | 8-row wave 的 group32 U8 payload + U24 metadata；128 groups/row |
| `02_attention_a8w8_projection` | `hap_projection_core16x16_w8_reuse`、col3 array | physical 8×16 output tile，128 group32 累加后输出 S24；16-row cohort 用两个 wave；覆盖 Q/K/V/Wo phase |
| `03_attention_rope` | `hap_rope_pair_s24` | 每事务一对 Q 或 K 的旋转结果；S24 pair；稳定流水按 accepted/output pair 计数 |
| `04_attention_kv12_quantizer` | `hap_kv12_quantizer4` | 每批 4 rows；每 row/group 输出 `32×S12 + meta16`；禁止产生 -2048 sentinel |
| `05_attention_qk_score` | `hap_qk_score_row_128` | 每个 key 消费 4 个 group32，输出一个 S20 Q6.14 score；每 row/head 为 `N∈[1,128]` scores |
| `06_attention_softmax` | `hap_softmax_row_128` | 每 row/head 输入 N scores、输出 N 个 U16 probability；单独报告多 pass row latency 与 probability phase II |
| `07_attention_pv` | `hap_pv_tile16_s43` | 每个 value tile 对 N keys 累加，输出 16 个 S24 context；同一 physical leaf 每 head 时间复用 8 tiles |
| `08_mlp_input_hadamard_a8` | `hap_mlp_input_frontend16_compact_cache` | 每事务 `16×32 S24`，输出 `16×32 U8 + 16×U24 meta`；shared Hadamard + 4 quantizers |
| `09_mlp_gate_up_a8w4` | `hap_mlp_shared_dual_slice16x12_s43_s45` 的 Gate/Up phase | physical 16 rows × 12 cols，128 group32 累加，repack 后 S24 Gate/Up records |
| `10_mlp_silu_multiply` | `hap_mlp_silu_mul` | `SiLU(gate)×up`，每 leaf 稳态 1 element/cycle，4-stage stoppable pipe；链顶层按当前 2 个 row-local lane 计 |
| `11_mlp_product_hadamard_a8` | `hap_mlp_product_frontend16_q4` | 每事务 `16×32 S32` product，输出 `16×32 U8 + 16×U24 meta`；shared II=1 Hadamard + 4 quantizers |
| `12_mlp_down_a8w4` | 同一 shared A8W4 kernel 的 Down phase | physical 16 rows × 12 cols，448 group32 累加，repack 后 `16×4096 S24` |

RMSNorm 当前不在 ScaleLLM production RTL 的上述计算链中，因此不凭空建立目录。若以后加入 production 模块，应先更新本表、冻结接口和输出算力，再开始比较。

## 6. 同等算力的强制匹配规则

1. 使用同一 FPGA part、Vivado 版本、100 MHz 时钟约束、reset/clear 与 ready/valid wrapper。
   OOC implementation 还必须使用相同的 `HD.CLK_SRC=BUFGCE_X0Y0`，避免缺少父级 BUFG 信息造成不可比的时钟偏斜估计。
   hold uncertainty 固定为 0 ns，仍要求工具在器件 min-delay 模型下报告 `WHS >= 0`；原因是 Xilinx FP IP 存在同一 DSP48E2 内不可插延迟的专用路径，额外人为 50 ps margin 会产生无法由布局布线修复的假门禁。setup uncertainty 保持 0.150 ns。
2. 使用相同 tensor shape、有效 key 数、mask、row/head/tile/group 顺序和相同无阻塞/阻塞激励。
3. 先测量 SC production wrapper 的稳定输出率，作为该模块目标；不能只根据 RTL 位宽猜测吞吐。
4. FP 设计若单实例达不到目标，必须复制或加深流水直到 `throughput_FP >= throughput_SC`，并把全部复制资源计入 baseline。
5. 在满足吞吐的 FP 候选中选资源最小者作为主 baseline；若无法精确相等，报告资源-吞吐 Pareto 点，不得拿明显低吞吐 FP 核与 SC 核比较面积。
6. 主资源表使用共同 100 MHz；另报告各实现独立 post-route Fmax 下的最高速度，二者不可混为一个结论。
7. 首结果 latency、steady-state II、整批 latency 都必须报告；短批只报 II 会掩盖 pipeline fill/drain，长批只报总周期会掩盖启动成本。
8. 存储/ROM 的同步读延迟、输出寄存器和 backpressure buffer 对所有版本采用等价边界。

## 7. 输入数据与工作负载

每个模块使用相同随机种子和一一对应的实值输入，至少包含：

- **定向边界向量**：0、最小/最大合法 code、正负极值、scale code 为 0、最小/最大合法 shift、饱和、round-half、Softmax 全相等/单峰/大动态范围、SiLU 的 -16/0/+16 邻域。
- **确定性随机向量**：不少于 10 个固定 seed；覆盖一般分布、长尾和异常值。
- **真实 trace**：从冻结的 Llama-3.1-8B workload 导出的 Q/K/V、score、Gate/Up、SwiGLU product 和 Down 输入；记录层、token、head、group、tensor hash。

可重放 trace 的统一采集入口为：

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
./tools/scripts/run_collect_llama_trace.sh
```

该入口从本地 checkpoint 保存 pre/post-RoPE Q/K、V、raw/masked score、
probability、Gate/Up 和实际 `down_proj` 输入；BF16 以原始 16-bit 位型保存，
manifest 同时记录 checkpoint/workload/tensor 与选定 token/head/group slice 哈希。
只有采集目录通过独立 verifier、并由这些 tensor 派生的模块/整链 workload 完成
XSIM 后，才可把“真实 trace”缺口标为关闭；仅脚本静态通过不算实验数据。
当前 M01 Attention frontend 已从经验证的 projection-input 捕获中选择 8 个
真实 token row，并完整生成 128 个 8-row/group32 bundle；M03 RoPE 已用冻结 input IDs/checkpoint 补充捕获 projection 前激活，并
生成 12-pair/1,536-transaction 的完整 projection-tail workload；M04 KV12 已从
真实 post-RoPE K/V 派生 16-batch/64-record 软件 workload；
M05 QK、M06 Softmax 与 M07 PV 已从正式 trace 各派生
72-row/4,236-key 软件 workload；M08 MLP frontend 已用同一冻结 input IDs/
checkpoint 补充捕获 6 个 pre-Gate/Up 输入 tensor，并派生 16-row/128-group
软件 workload；M09 Gate/Up 已结合该输入与 checkpoint 权重派生层 0/15/31
的 6-tile/768-transaction 软件 workload；M10 SiLU×Up 已派生 6,144-vector 软件
workload，M11 Product Hadamard+A8 已派生完整 448-group × 16-row workload；
M12 Down 还从三层真实 `down_proj.weight` 和实际 Down 输入生成了
3 × 153,216-transaction full-shape workload。十一者均通过独立完整性或临时重生成/
逐字节校验。M03 的补充重放保留 layer-31 BF16 非 bit-reproducibility，并保留
FP16 S21 correlation 溢出造成的 22/24 RoPE 软件饱和值；M04 使用 K/V 交替 batch
与完整四个 head-dim group32；M05/M07 的 GQA KV-head
映射与完整 32-lane KV12 group
量化和固定 16-lane PV tile，以及 M10/M11 的跨层/token/channel 坐标均记录在
manifest。M08 的补充捕获保留 layer-31 Gate/Up 共 5,316,910 个 BF16 bit
mismatch，最坏 normalized RMSE 为 `4.8446746e-3`；M12 的 layer-31 数据保留
六个真实 S24 输出饱和点。它们仍须完成
boundary RTL XSIM，不能因软件 verifier PASS 提前关闭
真实 trace 完成条件。

Boundary-inclusive Vivado 任务启动前，统一执行只读 preflight：

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
./tools/scripts/audit_boundary_preflight.sh
```

该门禁检查 01–12 的 shell 语法与可执行位、Tcl 完整性、
source-list 文件存在性、RTL/TB module 平衡、自包含 FP IP driver，以及各模块
冻结向量或静态合同 verifier；M02 在硬件 semantic map 尚未产生时只验证探针、
18-tile trace 链和 fail-closed 门禁，不把静态准备升级为向量/RTL PASS。门禁同时
拒绝 shell 中残留的字面补丁 `+` 参数污染，因为这种
文本仍能通过 `bash -n`，却会在调用 Vivado 时改变 argv。它不调用 Vivado，
M12 还额外绑定四份 source list、六个 top、三种 serial payload、七个 FP IP
latency/RTL delay 常量、全宽非零 mini workload、FP16 correction audit，以及
serial/full/OOC 共用的 fail-closed Vivado guard。03/05/06/07/10 另由统一
top-contract verifier 检查
12 份 boundary source list、三路共 15 个 OOC top、5 个 TB top 和 Softmax/PV
最小同吞吐复制 farm 绑定。该门禁不调用 Vivado，不能代替 elaboration、XSIM
或 post-route。

当前统一门禁结果为：

```text
BOUNDARY_PREFLIGHT_PASS modules=12 shells=55 tcl=45 source_lists=43 sources=187 sv=69 inline_ip_drivers=4
```

- **shape sweep**：Attention `N={1,16,32,64,112,128}`；完整 16 rows、32 Q heads、8 KV heads；MLP 128 hidden groups和 448 intermediate groups，包含 `3×16→4×12` tail。
- **压力流控**：下游永久 ready、周期性 backpressure、伪随机 backpressure；确保 sideband 与 payload 不错位。

Golden 使用软件 FP64/高精度数学定义。在线 A8 使用
`ModularExperiment/tools/model/minmax_a8.py` 的独立原始 Min/Max reference；
不得再调用 production robust golden 形成同源 PASS。FP baseline 不以 SC 的
ScaleCode 近似误差作为自己的 golden。

## 8. 必须采集的数据

### 8.1 功能与精度

- 输入/输出样本数、hash、PASS/FAIL；
- max/mean absolute error、RMSE、max/mean relative error、cosine similarity；
- saturation、量化前 clip（Min/Max 合同下必须为 0）、underflow/overflow、非法格式计数；
- Softmax：概率和误差、KL divergence、argmax/top-1 match；
- Attention/MLP 链：最终 S24 或实值输出误差、必要时模型层输出 cosine。

### 8.2 性能

- 复位释放到首输入、首输入到首输出、首输入到末输出的 cycle；
- steady-state input II/output II、有效输出/周期、stall cycle、busy cycle；
- `cycles/work-unit`、`work-units/s @100 MHz`、batch latency(ns)；
- post-route Fmax、在各自 Fmax 下的 `work-units/s`；
- 可解释时报告 GOPS，但主指标始终是逻辑结果/秒。

XSIM 的软件墙钟时间不是硬件速度指标。它会受到 AMD FP 仿真模型实例数、
`xelab` debug 等级、WDB 波形记录、主机负载和工具缓存影响；主结论只能使用同一
激励下的 RTL cycle/II，以及通过实现门禁后的共同 100 MHz 或各自 post-route
Fmax。允许为长 trace 关闭非必要 debug/波形，但必须先在同构小 workload 上做
默认配置与加速配置的 A/B 回归，证明输出位型、握手事件计数、首输出 latency、
II 和总周期完全一致，并分别保存命令/配置哈希。小 workload 只证明观测配置
等价，不能替代正式 full-shape trace；XSIM 墙钟时间只作为实验执行成本附注，
不得代入 `speedup_time`。

### 8.3 资源、时序与实现有效性

- post-synth 和 post-route：CLB LUT、LUTRAM、SRL、FF、CARRY、DSP48E2、BRAM18/36、URAM288；
- clock、WNS、TNS、WHS、THS、unrouted nets、DRC errors；
- FP IP 数量、配置与共享/复制方式；
- 可选但推荐：post-route power、动态/静态功耗、energy/work-unit；
- Vivado command、strategy、seed、jobs、host、运行时间、tool log hash。

### 8.4 派生指标

对每项资源 `R` 和速度统一计算：

```text
resource_saving_R = (R_FP - R_SC) / R_FP × 100%
speedup_cycles    = cycles_FP / cycles_SC
speedup_time      = time_FP / time_SC
throughput_ratio  = throughput_SC / throughput_FP
area_per_output   = resource / sustained_outputs_per_cycle
energy_per_output = dynamic_power / sustained_outputs_per_second
```

资源为 0 时不计算百分比；同时报告绝对差值，避免小基数百分比误导。

## 9. 实验流程与结果有效性

1. 冻结 production DUT、wrapper 接口、work-unit 和 SC 输出率。
2. 生成共同输入与 FP64/bit-exact golden。
3. 实现 `SC`、`FP16`、`FP32`，并用同一 testbench 验证无阻塞和 backpressure。
4. 对每个版本进行相同约束的 OOC synthesis；调整 FP 复制/流水直到满足吞吐。
5. 对最终候选执行 implementation，确认 setup/hold、DRC 和 unrouted nets；只有 post-route 合法结果进入主表。
6. 生成模块级 CSV/JSON，再对不重叠的 Attention/MLP 链顶层重新综合，防止资源重复相加。
7. 汇总 FP16-vs-SC、FP32-vs-SC，并明确 operator-only 与 boundary-inclusive 口径。

一个结果只有同时包含配置、功能正确性、吞吐匹配、资源报告和时序有效性时才可用于结论。仅 xsim、仅 synthesis estimate、负 WNS 或低吞吐 baseline 的数据必须标为 diagnostic。

## 10. 预期产物

每个 `experiment/<module>/` 后续采用统一结构：

```text
README.md
rtl/{scalecode,fp16,fp32}/
model/
tb/
data/
vivado/
```

统一结果写入 `result/`，每个模块物理隔离：

```text
result/<module>/SUMMARY.md
result/<module>/raw/<variant>/{xsim,ooc}/
result/<module>/metrics.json
result/tables/module_summary.csv
result/tables/module_summary.json
result/figures/
result/REPORT.md
```

Vivado `.runs/`、`.Xil/`、临时 IP cache、WDB 和大型日志不放入模块源码目录；只保留重建脚本、关键报告和 hash/manifest。

## 11. 完整长周期实验完成条件

实验已经从目录初始化进入完整执行阶段。只有同时满足以下条件才算完成：

1. `00`–`12` 每个模块都有 SC、FP16、FP32 的可重建 RTL/脚本、共同 workload、功能/协议/数值结果与独立 `result/<module>/SUMMARY.md`；
2. FP 单核吞吐不足时，实际实现并综合包含复制核、缓存、分发、顺序退休、仲裁和 backpressure 的顶层，不用单核面积乘复制数代替；
3. 主表中的每个版本均通过相同 100 MHz post-route 门禁：`WNS >= 0`、`WHS >= 0`、DRC error 为 0、unrouted/partially-routed net 为 0，并核验输入与输出证据哈希；
4. 每个模块分别报告功能误差、首结果延迟、稳态 II/吞吐、整批周期、LUT/FF/DSP/BRAM/URAM、时序以及 SC 相对 FP16/FP32 的资源节省和周期加速；
5. operator-only 与 boundary-inclusive 结果明确分栏；未完成边界成本时只能形成子结论，不升级为完整链主结论；
6. `result/REPORT.md` 汇总全部模块的有效结果、负结果、失败诊断、尚存限制和最终可支持的实验命题，并完成跨模块证据/口径审计。

任何仅通过 XSIM、仅有 synthesis estimate、吞吐未匹配、post-route 时序失败或证据不完整的结果均保留为 `DIAGNOSTIC`，不得用于最终资源/速度结论。
