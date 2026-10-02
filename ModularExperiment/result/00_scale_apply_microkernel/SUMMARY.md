# 00 Scale application microkernel

- 状态：`RUNNING`（A8W8 boundary-inclusive 同吞吐子实验已完成；A8W4 FP、无阻塞/多 seed 与精度统计待补）
- 工作单位：A8W8 每个 group32 一份 S42 Q18.24 contribution，production 目标 `II=2`；A8W4 每个 group32 两列 S36 contribution，production 目标 `II=1`
- 主比较口径：A8W8 boundary-inclusive，从相同 `32×U8 activation + 32×S8 weight + zero-point + scale metadata` 开始，到共同 S42 Q18.24 输出结束
- 固定条件：`xcvu9p-flga2104-2L-e`、Vivado 2025.2、100 MHz、`HD.CLK_SRC=BUFGCE_X0Y0`、setup uncertainty 0.150 ns、hold uncertainty 0 ns

## 正式结论（A8W8 boundary-inclusive）

SC、FP16 和 FP32 均使用同一 256-vector workload、相同 32-lane group32 整数 dot producer、ready/valid 边界和最终 S42 输出合同。三者的前 64 次 intrinsic input interval 均为严格 `II=2`，因此单核即达到相同持续逻辑输出算力，不需要复制 FP 核。

在共同 100 MHz post-route 条件下，SC 相对 FP16 节省 22.66% LUT、50.24% FF 和 5.56% DSP；相对 FP32 节省 29.02% LUT、58.87% FF 和 15.00% DSP。SC 的首输出 latency 为 10 cycles，相对 FP16/FP32 分别快 3.70×/3.00×。在当前先无阻塞、后周期性 backpressure 的 256-vector 批次中，整批分别快 1.064×/1.045×。

该结论包含 FP 的真实边界成本：相同 S21 correlation 先转 FP，乘 activation/weight scale，再按 AMD Floating-Point IP 的 round-to-nearest-even 语义转回 S42；FP16 为覆盖约 37-cycle 流水并保持 `II=2` 使用 32 credits 和 32-entry S42 FIFO，其资源已包含在正式实现中。

## 功能、吞吐与批次延迟

testbench 在 cycle 160 前保持 `out_ready=1`，之后采用每 4 cycle 接收 1 cycle 的周期性 backpressure。表中的持续 II 来自前 64 次输入接受事件；总周期包含该压力流控，不能当作永久无阻塞数据。

| 版本 | vectors | mismatch | intrinsic II min/max | 首输出 latency (cycle) | producer wait | 256-vector 总周期 | 有效 group/cycle | @100 MHz Mgroup/s | 同吞吐资格 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SC production | 256 | 0 | 2 / 2 | 10 | 562 | 881 | 0.290579 | 29.0579 | PASS，目标锚点 |
| FP16 boundary-inclusive | 256 | 0 | 2 / 2 | 37 | 554 | 937 | 0.273212 | 27.3212 | PASS |
| FP32 boundary-inclusive | 256 | 0 | 2 / 2 | 30 | 602 | 921 | 0.277959 | 27.7959 | PASS |

`effective group/cycle` 与 Mgroup/s 是当前带 backpressure 的整批吞吐。稳态无阻塞输出能力以共同 `II=2` 为准，即每核理论 0.5 group/cycle、100 MHz 下 50 Mgroup/s；永久无阻塞整批测量仍列在待办中。XSIM JSON 中遗留字段名 `effective_gops_150mhz` 来自旧测试脚本，本页不引用它，所有主结果按 cycle 和 100 MHz 重新计算。

## 100 MHz post-route 资源与时序

| 版本 | LUT primitives | FF primitives | DSP48E2 | RAMB36E2 | RAMB18E2 | URAM | WNS (ns) | WHS (ns) | 推导 Fmax (MHz) | DRC errors | unrouted | 有效性 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SC production | 932 | 821 | 17 | 0 | 0 | 0 | 5.297 | 0.013 | 212.630 | 0 | 0 | VALID |
| FP16 boundary-inclusive | 1,205 | 1,650 | 18 | 0 | 0 | 0 | 6.113 | 0.011 | 257.255 | 0 | 0 | VALID |
| FP32 boundary-inclusive | 1,313 | 1,996 | 20 | 0 | 0 | 0 | 5.627 | 0.010 | 228.661 | 0 | 0 | VALID |

`Fmax` 是由本次 post-route critical period 推导的实现点指标，不替代共同 100 MHz 主比较。FP16 本次推导 Fmax 高于 SC/FP32 是具体流水与布局布线结果；主结论不把不同 Fmax 与共同频率面积表混用。

## 100 MHz post-route 功耗估算（behavioral SAIF）

以下数据不是板级实测功耗。方法为：对与功能回归相同的 256-vector、先无阻塞后周期性 backpressure workload 做 100 MHz behavioral XSIM；复位结束后只记录 DUT 层级的 SAIF 翻转活动；随后导入对应的 routed DCP，并由 Vivado 2025.2 `report_power` 进行 post-route 功耗估算。环境模型采用 report 默认的 typical process、25 °C、250 LFM、medium heat sink。三路时钟与输入活动覆盖均为 High；未直接匹配的内部节点由 Vivado 活动传播模型补全。

| 版本 | SAIF 时长 (µs) | 匹配网表节点 | 置信度 | Clock (W) | CLB logic (W) | Signals (W) | DSP (W) | 动态功耗 (W) | 器件静态 (W) | 总片上 (W) | 当前 workload 动态能量 (nJ/group32) |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SC production | 8.795 | 1,130 / 3,074（37%） | Medium | 0.002 | 0.006 | 0.006 | 0.015 | 0.028 | 2.470 | 2.498 | 0.962 |
| FP16 boundary-inclusive | 9.355 | 1,432 / 4,491（32%） | High | 0.004 | 0.006 | 0.005 | 0.014 | 0.028 | 2.470 | 2.498 | 1.023 |
| FP32 boundary-inclusive | 9.195 | 1,710 / 5,074（34%） | High | 0.004 | 0.007 | 0.007 | 0.016 | 0.035 | 2.470 | 2.505 | 1.257 |

动态能量按该 SAIF 窗口直接计算：`dynamic_power × SAIF_duration / 256`。因此它对应本页已经说明的 backpressure workload，不能冒充永久 `out_ready=1` 的稳态能量。受 `report_power` 仅输出到 1 mW 精度影响，能量同样是近似值。SC 与 FP16 的动态功耗在当前报告精度下相同；SC 相对 FP32 的动态功耗低约 20.0%，当前 workload 的动态能量低约 23.5%。器件静态 2.470 W 是整颗 VU9P 在所选工艺/热环境模型下的估算，不应解释为这个小模块独占的静态功耗，模块间主比较应使用动态功耗和动态能量。

机器可读汇总见 `power_summary.csv` 和 `power_summary.json`。原始证据目录均含 SAIF、未匹配节点清单、text/XML/RPX power report、XSIM/power 日志、manifest 与 SHA256：

- SC：`raw/sc/power/20260912_100508_saif_post_route_100mhz/`
- FP16：`raw/fp16/power/20260912_101007_saif_post_route_100mhz/`
- FP32：`raw/fp32/power/20260912_101229_saif_post_route_100mhz/`

## 派生比较

| 指标 | SC vs FP16 | SC vs FP32 |
|---|---:|---:|
| LUT 节省 | 22.66%（少 273） | 29.02%（少 381） |
| FF 节省 | 50.24%（少 829） | 58.87%（少 1,175） |
| DSP 节省 | 5.56%（少 1） | 15.00%（少 3） |
| 首输出加速 `latency_FP/latency_SC` | 3.700× | 3.000× |
| 当前压力批次加速 `cycles_FP/cycles_SC` | 1.064× | 1.045× |
| 当前压力批次周期降低 | 5.98%（少 56 cycles） | 4.34%（少 40 cycles） |

## 数值语义与实现边界

- SC 使用 production `hap_a8w8_group32_lane_s42`：`correlation × act_code × weight_code` 后按 `act_shift + weight_shift` 对齐到 S42 Q18.24。
- FP32 使用 S21 fixed-to-FP32、一次 FP32 scale×scale、一次 FP32 correlation×scale 和 FP32-to-S42。
- FP16 先将 S21 转 FP32 再转 FP16，执行两个 FP16 multiply，随后转回 FP32/S42。生成向量按 AMD FP IP 的 denormal flush-to-zero 和 round-to-nearest-even 语义建 golden；本组 256 vectors 中有 230 个 FP16 IP 零输出，软件逐级 IEEE 模型与 IP 语义有 119 个差异，因此不能把未经 IP 语义校准的软件 FP16 值当成 RTL golden。
- 三种版本分别对各自数值合同做到 0 mismatch；它们不是三者 bit-exact 相等的声明。相对共同 FP64 golden 的 max/mean error、RMSE 与 cosine 尚待补齐。

## A8W4 已完成锚点

SC A8W4 `hap_a8w4_scalecode_recover2_lut` 已完成 4,096-vector 功能与 100 MHz post-route：0 mismatch，4,303 cycles，928 LUT、201 FF、0 DSP，WNS 5.262 ns、WHS 0.007 ns，DRC=0、unrouted=0。其 FP16/FP32 同 `II=1` 双列输出 baseline 尚未实现，因此该数据只作为 production SC 锚点，不进入浮点资源对比。

## 已核验证据

- SC A8W8 XSIM：`raw/sc/xsim/20260908_215319_a8w8_scalecode/`
- FP16 A8W8 XSIM：`raw/fp16/xsim/20260908_215711_boundary_inclusive_a8w8/`
- FP32 A8W8 最新共享 RTL XSIM：`raw/fp32/xsim/20260908_220013_boundary_inclusive_a8w8/`
- SC A8W8 100 MHz OOC：`raw/sc/ooc/20260908_220106_sc_scale_apply_a8w8_100mhz/`
- FP16 A8W8 100 MHz OOC：`raw/fp16/ooc/20260908_220503_fp16_scale_apply_a8w8_boundary_inclusive_100mhz/`
- FP32 A8W8 100 MHz OOC：`raw/fp32/ooc/20260908_220917_fp32_scale_apply_a8w8_boundary_inclusive_100mhz/`
- SC/FP16/FP32 100 MHz post-route SAIF 功耗：见上节三个 `raw/*/power/` 目录；
- SC A8W4 XSIM：`raw/sc/xsim/20260908_142059_a8w4_scalecode_recover2/`
- SC A8W4 正式 100 MHz OOC：`raw/sc/ooc/20260908_152823_sc_a8w4_scalecode_recover2_100mhz/`

正式 XSIM/OOC 输入源哈希已交叉一致；三个正式 OOC 目录均包含 `summary.json`、post-synth/post-route checkpoint、资源/时序/DRC/route-status 报告和输入哈希。FP OOC 还保存 pre-synth IP Tcl、生成的 XCI 及其哈希。所有正式目录级 `SHA256SUMS` 已逐项通过。

## 尚未完成

- A8W4 FP16/FP32 boundary-inclusive、同 `II=1` 的双列输出 baseline；
- A8W8 operator-only 分栏，以及永久 ready、伪随机 backpressure、不少于 10 个固定 seed；
- 相对共同 FP64 golden 的误差、饱和/underflow/overflow 统计与真实 Llama-3.1-8B trace；
- 与 02 projection 或完整 Attention 链的边界去重顶层综合。

因此本页当前支持“A8W8 scale application 在相同单核 `II=2` 和共同 100 MHz 下，SC 比 boundary-inclusive FP16/FP32 使用更少 LUT/FF/DSP，并降低首输出与本压力批次周期”的子结论，尚不升级为完整 Attention/MLP 链最终结论。
