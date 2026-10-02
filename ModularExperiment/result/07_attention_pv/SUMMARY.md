# 07 Attention PV

- 状态：`RUNNING`（N=128 operator-only 同吞吐硬件子实验完成；12-seed 与真实 trace 两套 N-sweep boundary 软件向量 PASS；boundary RTL/TB 已静态预检，Vivado elaboration/XSIM/OOC 待执行）
- 工作单位：128 keys 后的一份 16-element S24 context tile
- 比较口径：SC 从 `U16 probability + 16×S12 value + scale-code meta` 开始；FP16/FP32 operator-only 从已经反量化的浮点 probability/value 开始，因此当前比较对 FP baseline 有利
- 固定条件：`xcvu9p-flga2104-2L-e`、Vivado 2025.2、100 MHz、`HD.CLK_SRC=BUFGCE_X0Y0`、setup uncertainty 0.150 ns、hold uncertainty 0 ns

## Boundary-inclusive 软件证据

正式 workload 覆盖 12 seeds × `N={128,112,64,32,16,1}`，共 72 rows、
4,236 key transactions、67,776 个 V lane。13 个 `.mem` 保存共同 U16
probability、V S12/native metadata、显式 FP16/FP32 boundary cache 和三路 S24
context reference。独立 verifier 已用 production `pv_row_tile16_s24` 重算全部
SC golden，并核对记录宽度/数量、生成器/model 和数据哈希：

`M07_BOUNDARY_VECTOR_VERIFY_PASS files=13 rows=72 keys=4236 lanes=16`

manifest SHA256：
`8088bb9f1f0fe50150f30c75bf45084721d04ed0a27aea341b79a51a9d89a4b0`；
二次生成的 `data_boundary/` 聚合哈希保持不变。

| 软件路径 | max abs error | mean abs error | RMSE | cosine | S24 saturation |
|---|---:|---:|---:|---:|---:|
| SC | `1.0076242e-5` | `3.6885362e-6` | `4.3617823e-6` | `0.999999999999957` | 16 |
| FP16 | `9.5267749e-2` | `4.9090278e-3` | `1.3963638e-2` | `0.999999576677264` | 16 |
| FP32 | `7.6957712e-6` | `3.6586537e-6` | `4.3091965e-6` | `0.999999999999958` | 16 |

误差相对只在共同 S24 观察点裁剪一次的 FP64 reference，饱和数量单独报告，避免
用未裁剪的超范围 FP64 值人为放大三路误差。FP16 workload 还覆盖 145 个
probability FTZ、1,060 个 subnormal scale 和 16,957 个非零 V lane 反量化后
变零。以上仍是软件证据；实际 Xilinx IP 数值、周期、cache inference、资源和
时序必须等待 boundary RTL/XSIM/OOC。

## 真实 trace 软件证据

正式 trace workload 为 2 samples × layers `{0,15,31}` ×
`N={128,112,64,32,16,1}` × q-heads `{0,17}`，仍为 72 rows、4,236 keys。
q-head 0/17 按 Llama GQA 4:1 映射到 KV-head 0/4。每个 key 的 BF16 V 先按
production ABI nearest-even 转为 S24 Q8.16，再对完整 head-dim 0–31 group32
调用 `kv12_quantize_s24`；PV 固定读取 head-dim 0–15 的 16-lane tile，并保留
该完整 group 的 native code/shift。FP32 probability nearest-even 转为共同
U16 Q0.16，三路不使用彼此不同的源输入。

独立临时重生成结果如下；硬件 payload 逐字节比较，manifest 的结构/非浮点字段
严格相等，浮点归约指标允许 `1e-13` 相对容差：

`M07_TRACE_VECTOR_VERIFY_PASS files=15 rows=72 keys=4236 lanes=16
source_tensors=12 manifest_numeric_rel_tol=1e-13
manifest_sha256=ce9eac6783699b0c84ea55314541aa4a784c824ab817056f0acaf232e52f465b`

| 软件路径 | RMSE vs raw trace PV | cosine vs raw trace | RMSE vs common quantized PV | S24 saturation |
|---|---:|---:|---:|---:|
| SC | `7.0642112e-5` | `0.9999999379567994` | `4.6099882e-6` | 0 |
| FP16 | `6.5395644e-3` | `0.9984470007062256` | `6.5371985e-3` | 0 |
| FP32 | `7.0731914e-5` | `0.9999999382008915` | `4.1184005e-6` | 0 |

输入量化误差被单独保留：probability RMSE `4.4738652e-6`，其中 12 个 N=1
概率 1.0 饱和为 U16 `65535`；BF16→S24 无饱和，production KV12 无 clip，
KV12 reconstruction 相对 BF16 V 的 RMSE 为 `1.8590829e-4`。真实数据还覆盖
582 个非零 FP16 probability FTZ、1,061 个 FP16 subnormal scale，以及
16,964 个非零 KV12 lane 在 FP16 反量化后变零。

runner 已支持：

```bash
./experiment/07_attention_pv/run_boundary_xsim.sh sc 0 trace
./experiment/07_attention_pv/run_boundary_xsim.sh fp16 0 trace
./experiment/07_attention_pv/run_boundary_xsim.sh fp32 0 trace
```

这些命令尚未启动，因此真实 trace 目前仍是软件证据，
不能宣称 RTL replay 已完成。

## Boundary RTL/TB 准备状态

共同 U16 probability、16×S12 V 与 meta16 边界的三路 RTL/TB/Tcl/脚本已
落盘并通过静态预检。FP 路径真实计入 probability/V conversion、由 metadata
精确重建 native FP scale、16-lane V-scale multiply、transaction-order
sideband/data FIFO，再进入 x19/x21 farm；没有使用向量文件中预先反量化的 FP
cache 作为硬件公共输入。全部 4,236 个 metadata 的组合 scale 编码已与冻结的
FP32/FP16 bit pattern 交叉验证一致。

TB 覆盖 72 个 variable-N row、continuous/periodic backpressure、S24×16
exact output、input/conversion/core/output/saturation counters。自包含 FP IP
Tcl 使 OOC driver 哈希覆盖 operator 与 boundary IP。启动前审计还发现并修复
了 XSIM runner 中会污染 Vivado argv 的字面补丁 `+`；增强后的统一 preflight
已再次 PASS，且问题在首次 boundary Vivado 运行前关闭。当前仍缺 Vivado
elaboration/XSIM/OOC，因而没有新增 boundary 周期、资源或时序结论。

## 正式结论（N=128 operator-only）

SC、FP16×19 和 FP32×21 均通过同一 96-row workload、同吞吐、100 MHz post-route、DRC、route-status 和证据哈希门禁。FP baseline 是真实综合的复制顶层，包含每核完整 128-key 行缓存、输入分发、顺序退休、仲裁和 backpressure；资源不是单核面积的算术倍乘。

在满足持续输出率的最小已验证复制数下，SC 相对 FP16×19 节省 95.04% LUT、98.97% FF、96.49% DSP；相对 FP32×21 节省 96.86% LUT、99.27% FF、97.62% DSP。代价是 FP16/FP32 分别额外使用 76/168 个 RAMB36 作为复制核行缓存，而 SC 不使用 BRAM。

SC 的首份 context latency 比 FP16×19/FP32×21 分别快 18.66×/20.58×；96-row 整批周期分别快 1.153×/1.172×。FP farm 因复制数必须取整数而具有约 3% 的持续吞吐裕量，因此资源比较不是通过降低 FP 吞吐获得的。

## 功能与吞吐

共同 workload 为 96 rows × 128 keys × 16 lanes，共 12,288 个 key 事务。三种版本最终 S24 context 均为 0 mismatch。

| 版本 | 核数 | 首输出 latency (cycle) | row interval min/mean/max (cycle) | 96 rows 总周期 | 功能 | 同吞吐资格 |
|---|---:|---:|---:|---:|---|---|
| SC production | 1 | 131 | 132 / 132.453 / 137 | 12,715 | PASS，0 mismatch，input II=1 | PASS，目标锚点 |
| FP16 replicated | 19 | 2,444 | 124 / 128.589 / 141 | 14,661 | PASS，0 mismatch | PASS |
| FP32 replicated | 21 | 2,696 | 125 / 128.411 / 137 | 14,896 | PASS，0 mismatch | PASS |

SC mean interval 由 `(last_output_cycle - first_output_cycle) / 95` 计算。FP testbench 直接记录逐 row interval。FP metric 中 `saturation_count_before_last=1312` 是最后一次 nonblocking counter 更新前的采样值，不与 SC 最终 `saturation_count=1326` 做数值比较；0 mismatch 已逐 lane 覆盖最终饱和输出。

### 最小复制数诊断

| 候选 | 首输出 | mean row interval | 总周期 | 结论 |
|---|---:|---:|---:|---|
| FP16×18 | 2,444 | 135.421 | 15,310 | FAIL 同吞吐；保留为功能通过诊断 |
| FP16×19 | 2,444 | 128.589 | 14,661 | 最小已验证正式候选 |
| FP32×20 | 2,696 | 133.832 | 15,411 | FAIL 同吞吐；保留为功能通过诊断 |
| FP32×21 | 2,696 | 128.411 | 14,896 | 最小已验证正式候选 |

×18/×20 的 mean interval 由首、末输出和 95 个 row 间隔计算。由于它们慢于 SC 的 132.453 cycle/row，不进入正式资源表。

## 100 MHz post-route 资源与时序

| 版本 | LUT primitives | FF primitives | DSP48E2 | RAMB36E2 | RAMB18E2 | URAM | WNS (ns) | WHS (ns) | 推导 Fmax (MHz) | DRC errors | unrouted | 有效性 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SC production | 6,407 | 1,820 | 32 | 0 | 0 | 0 | 3.771 | 0.024 | 160.539 | 0 | 0 | VALID |
| FP16×19 buffered | 129,045 | 175,995 | 912 | 76 | 0 | 0 | 1.122 | 0.010 | 112.640 | 0 | 0 | VALID |
| FP32×21 buffered | 203,872 | 250,340 | 1,344 | 168 | 0 | 0 | 1.878 | 0.010 | 123.126 | 0 | 0 | VALID |

`Fmax` 是由本次 post-route critical period 推导的实现点指标，不替代共同 100 MHz 主比较。FP32 的本次 Fmax 高于 FP16 是布局布线结果，不代表位宽增加通常会提高 Fmax。

## 派生比较

| 指标 | SC vs FP16×19 | SC vs FP32×21 |
|---|---:|---:|
| LUT 节省 | 95.04%（少 122,638） | 96.86%（少 197,465） |
| FF 节省 | 98.97%（少 174,175） | 99.27%（少 248,520） |
| DSP 节省 | 96.49%（少 880） | 97.62%（少 1,312） |
| BRAM 差值 | SC 少 76 RAMB36 | SC 少 168 RAMB36 |
| 首输出加速 `latency_FP/latency_SC` | 18.66× | 20.58× |
| 96-row 整批加速 `cycles_FP/cycles_SC` | 1.153× | 1.172× |

## 100 MHz post-route 功耗估算（behavioral SAIF）

以下是“基于仿真波形的 post-route 估算”，不是板级实测。三路使用本页同一 96-row × 128-key × 16-lane、周期性 backpressure workload；behavioral XSIM 预热 100 ns 后记录 DUT SAIF，再导入对应 routed DCP 执行 Vivado 2025.2 `report_power`。

| 版本 | SAIF 时长 (µs) | 匹配网表节点 | 置信度 | 动态功耗 (W) | 器件静态 (W) | 总片上 (W) | 动态能量 (nJ/row-tile16) | 资格 |
|---|---:|---:|---|---:|---:|---:|---:|---|
| SC | 127.125 | 739 / 12,297（6.01%） | Medium | 0.142 | 2.471 | 2.613 | 188.039 | VALID |
| FP16 x19 | 146.585 | 49,939 / 376,056（13.28%） | High | 0.828 | 2.482 | 3.310 | 1,264.296 | VALID |
| FP32 x21 | 148.935 | 70,526 / 584,836（12.06%） | Medium | 1.408 | 2.491 | 3.899 | 2,184.380 | VALID |

动态能量按 `dynamic_power × SAIF_duration / 96` 计算，包含复制核缓存、调度、背压和流水填充/排空。SC 相对 FP16×19/FP32×21 的动态功耗分别低约 82.9%/89.9%，每 row-tile16 动态能量低约 85.1%/91.4%；三路均无高-X活动警告。该结论仍是 N=128 operator-only 功耗，不能与未计入的反量化边界重复相加。约 2.47 W 静态值属于整颗 VU9P 模型。

## 缓存实现诊断

初版 replicated RTL 把 RAM 读写放在带异步复位的 replay FSM 中。Vivado 明确报告 `RAM is sensitive to asynchronous reset signal`，并把每个 FP16 `128×272-bit` row memory 溶解为 34,816 个寄存器，FP16×19 综合出现约 839,743 个 FDRE。该 OOC 在进入布局布线前主动终止并标记 `FAIL`，不得作为面积结论。

正式版本将 row-memory 读写拆为无复位同步 RAM 进程，并使用 block-RAM 映射；功能/吞吐重跑后指标逐项不变。FP16 每 bank 使用 4 个 RAMB36，共 76 个；FP32 每 bank 使用 8 个，共 168 个。此版本显著降低 FF，也避免人为放大 FP baseline。

## 已核验证据

- SC 96-row XSIM：`raw/sc/xsim/20260908_182747_matched_workload/`
- FP16×19 正式 XSIM：`raw/fp16/xsim/20260908_193928_operator_only_x19_buffered/`
- FP32×21 正式 XSIM：`raw/fp32/xsim/20260908_203309_operator_only_x21_buffered/`
- SC 100 MHz OOC：`raw/sc/ooc/20260908_191945_sc_pv_tile16_100mhz/`
- FP16×19 100 MHz OOC：`raw/fp16/ooc/20260908_194949_fp16_pv_operator_only_x19_buffered_100mhz/`
- FP32×21 100 MHz OOC：`raw/fp32/ooc/20260908_204859_fp32_pv_operator_only_x21_buffered_100mhz/`
- 三路功耗证据：`raw/sc/power/20260912_115154_saif_post_route_100mhz/`、`raw/fp16/power/20260912_115404_saif_post_route_100mhz/`、`raw/fp32/power/20260912_121334_saif_post_route_100mhz/`
- FP16 RAM 推断失败诊断：`raw/fp16/ooc/20260908_192419_fp16_pv_operator_only_x19_buffered_100mhz/`

正式 OOC 目录均包含 `summary.json`、post-synth/post-route checkpoint、资源/时序/DRC/route-status 报告、源文件哈希；FP 目录还保存 pre-synth IP 配置脚本、生成的 XCI 及其哈希。目录级 `SHA256SUMS` 已逐项通过。

## 尚未完成

- boundary-inclusive 主口径：从共同量化 payload 与 scale metadata 开始，把 FP 反量化边界纳入同一顶层；
- 新 12-seed/N-sweep workload 的 boundary RTL、周期性/伪随机 backpressure XSIM 与硬件指标；
- Llama-3.1-8B 真实 trace boundary RTL/XSIM 重放（软件派生与 FP64 精度已完成）；
- 完整 attention 链顶层，避免跨模块资源直接相加。

因此本页支持“N=128 PV operator-only 子模块在真实同吞吐硬件下 SC 显著节省计算资源并降低短批/首结果延迟”的子结论，尚不升级为完整 attention 链的最终结论。
