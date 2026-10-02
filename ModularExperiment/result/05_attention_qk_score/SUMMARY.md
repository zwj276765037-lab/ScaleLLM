# 05 Attention QK score

- 状态：`RUNNING`（operator-only 硬件闭环；12-seed 与真实 trace 两套 boundary 软件向量 PASS；boundary RTL/XSIM/OOC 待执行）
- 工作单位：每个 key 的一个 S20 Q6.14 score；每个 score 消费 4 个 group32，即 128 个 Q×K product
- 主吞吐锚点：production `hap_qk_score_row_128` 接受一个 group32 的严格 `II=2`，因此稳定输出一个 score 的 `II=8`
- 固定条件：`xcvu9p-flga2104-2L-e`、Vivado 2025.2、100 MHz、`HD.CLK_SRC=BUFGCE_X0Y0`、setup uncertainty 0.150 ns、hold uncertainty 0 ns

## 当前可支持的结论

在 FP16/FP32 已经得到反量化 Q/K 的 operator-only 边界下，一个真实的 16-lane 浮点 bank 即可通过低/高半组时间复用达到与 SC 相同的 group `II=2` 和 score `II=8`，无需复制多个完整 QK 核。FP 设计使用实际共享 bank、平衡归约树、descriptor/clip/score FIFO 和 backpressure reservation；资源来自完整顶层 post-route，不是单个 IP 资源乘实例数。

在共同 100 MHz 和相同 12.5 Mscore/s 稳态算力下，SC 相对 FP16 节省 65.29% LUT、56.87% FF、66.67% DSP；相对 FP32 节省 63.18% LUT、62.23% FF、75.00% DSP。SC 的流水启动/排空也更短：N=128 整行从首 key group 到末 score 分别为 1039/1117/1125 cycles；N=1 为 23/101/109 cycles（SC/FP16/FP32）。

这仍是保守的 operator-only 子结论：FP 的 S24/S12+ScaleCode 到 FP16/FP32 反量化硬件和 FP cache 宽度尚未计入。它可以证明“即使免费给 FP 已反量化输入，SC QK slot 在同吞吐下仍明显节省资源并降低批延迟”，但不能替代完整 attention chain 的 boundary-inclusive 结论。

## 功能、吞吐和周期

共同确定性 workload 使用 seed `20260908`，按 `N={128,112,64,32,16,1}` 连续运行，共 353 scores、1412 group32。顺序采用 N 递减，因为 production QK 没有 `row_key_count` 端口，`in_last_key` 只在最后输入 group 到达时更新末 key；递减顺序保证末 key 在输出追上前完成更新，且不需要会清零模块计数器的行间 `clear`。

三路在各自独立 golden 下均为 0 mismatch、7 次预期 clip；mask、key index、last sideband 均逐事务检查。无阻塞运行严格达到 input II=2、output II=8。周期性 backpressure 使用 37-cycle 周期、连续 6-cycle deassert 窗口，三路也均为 0 mismatch，reservation/FIFO 未溢出。

| 版本 | scores/groups | mismatch | clip | input II min/max | output II min/max | 六档总周期 | 稳态 score/s @100 MHz | 同吞吐资格 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| SC production | 353 / 1412 | 0 | 7 | 2 / 2 | 8 / 8 | 2939 | 12.5 M | PASS，目标锚点 |
| FP16 16-lane shared | 353 / 1412 | 0 | 7 | 2 / 2 | 8 / 8 | 3491 | 12.5 M | PASS |
| FP32 16-lane shared | 353 / 1412 | 0 | 7 | 2 / 2 | 8 / 8 | 3455 | 12.5 M | PASS |

### Shape sweep 无阻塞延迟

`key→first` 从首 key group 接受沿到首 score transfer；`key→last` 为包含首尾的整行周期数。`query→last` 还包含 4 个 query group 的装载和 FP16 query prescale。

| N | SC query→last | FP16 query→last | FP32 query→last | SC key→first | FP16 key→first | FP32 key→first | SC key→last | FP16 key→last | FP32 key→last |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 128 | 1043 | 1135 | 1129 | 22 | 100 | 108 | 1039 | 1117 | 1125 |
| 112 | 915 | 1007 | 1001 | 22 | 100 | 108 | 911 | 989 | 997 |
| 64 | 531 | 623 | 617 | 22 | 100 | 108 | 527 | 605 | 613 |
| 32 | 275 | 367 | 361 | 22 | 100 | 108 | 271 | 349 | 357 |
| 16 | 147 | 239 | 233 | 22 | 100 | 108 | 143 | 221 | 229 |
| 1 | 27 | 119 | 113 | 22 | 100 | 108 | 23 | 101 | 109 |

所有 N 的稳定项都是 `8×N` cycles；版本差异来自 query 准备和长浮点树的固定 fill/drain。按六档合计周期，SC 相对 FP16/FP32 分别为 1.188×/1.176×；按 N=128 的 `key→last` 为 1.075×/1.083×；按 N=1 为 4.391×/4.739×。

## 100 MHz post-route 资源与时序

| 版本 | LUT primitives | FF primitives | DSP48E2 | RAMB36E2 | RAMB18E2 | URAM | WNS (ns) | WHS (ns) | 推导 Fmax (MHz) | DRC errors | unrouted | 有效性 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SC production | 3,691 | 5,521 | 18 | 0 | 0 | 0 | 5.616 | 0.0100 | 228.102 | 0 | 0 | VALID |
| FP16 operator-only | 10,635 | 12,801 | 54 | 0 | 0 | 0 | 2.983 | 0.0096 | 142.518 | 0 | 0 | VALID |
| FP32 operator-only | 10,025 | 14,616 | 72 | 0 | 0 | 0 | 3.030 | 0.0106 | 143.468 | 0 | 0 | VALID |

推导 Fmax 来自本次 OOC critical period，仅作次级参考，主比较固定为共同 100 MHz。按各自推导 Fmax 和 II=8，理论 score rate 分别为 28.51、17.81、17.93 Mscore/s；未施加顶层 I/O delay，不能替代系统时序。

FP16 顶层包含 16 个共享 half multiplier（先完成 8 个 query half 的 head prescale，再用于 Q×K）、16 个 half-to-single converter、FP32 平衡加法树和一个 float-to-S20 converter。FP32 顶层包含 16 个 lane multiplier、一个 head-scale multiplier、同一几何的 FP32 平衡树和 converter。完整 post-route DSP 计数为 54/72；未用核数乘法估算。

## 派生资源和周期比较

| 指标 | SC vs FP16 | SC vs FP32 |
|---|---:|---:|
| LUT 节省 | 65.29%（少 6,944） | 63.18%（少 6,334） |
| FF 节省 | 56.87%（少 7,280） | 62.23%（少 9,095） |
| DSP 节省 | 66.67%（少 36） | 75.00%（少 54） |
| N=128 `key→last` 加速 | 1.075×（少 78 cycles） | 1.083×（少 86 cycles） |
| N=1 `key→last` 加速 | 4.391×（少 78 cycles） | 4.739×（少 86 cycles） |
| 六档整批加速 | 1.188×（少 552 cycles） | 1.176×（少 516 cycles） |

FP32 LUT 少于 FP16 不是数据错误：FP16 还需要 half-to-single conversion 和 half query prescale 控制/FIFO；FP32 的代价更多体现在 FF 与 DSP。主结论分别按真实完整实现给出，不假定 FP32 每种资源都必然高于 FP16。

## 数值精度

共同 FP64 reference 为反量化 Q/K 的 128-D dot 乘当前 `5793/65536` head scale，并在共同输出边界 clip 到 ±16。SC 使用当前 `model/fixbit_v2.py` 的 exact S24×S12 dot、逐 group ScaleCode 乘法/右移截断、四组累加和 clip；FP16 使用 Xilinx half FTZ 语义、half query prescale/乘法及 balanced FP32 reduction；FP32 使用 balanced FP32 reduction 和 FP32 head scale。

| 版本 | max abs error | mean abs error | RMSE | cosine similarity |
|---|---:|---:|---:|---:|
| SC | 2.0743e-4 | 1.0517e-4 | 1.1232e-4 | 0.999999999283 |
| FP16 | 5.4899e-3 | 2.2864e-4 | 5.3830e-4 | 0.999999983548 |
| FP32 | 3.2454e-5 | 1.4485e-5 | 1.6972e-5 | 0.999999999984 |

这个 seed 中 SC 的误差小于 FP16、大于 FP32；这是当前定点/scale 分布下的实测结果，不外推为所有模型 trace 的普遍精度排序。

## 100 MHz post-route 功耗估算（behavioral SAIF）

以下是“基于仿真波形的 post-route 估算”，不是板级实测。三路重放同一六档 N shape sweep，共 353 scores，并施加周期性 backpressure；behavioral XSIM 预热 100 ns 后记录 DUT SAIF，再导入对应 routed DCP 执行 Vivado 2025.2 `report_power`。

| 版本 | SAIF 时长 (µs) | 匹配网表节点 | 置信度 | 动态功耗 (W) | 器件静态 (W) | 总片上 (W) | 动态能量 (nJ/score) | 资格 |
|---|---:|---:|---|---:|---:|---:|---:|---|
| SC | 29.435 | 3,921 / 12,305（31.87%） | Medium | 0.077 | 2.471 | 2.548 | 6.421 | VALID |
| FP16 | 34.965 | 4,529 / 29,765（15.22%） | Medium | 0.149 | 2.472 | 2.621 | 14.759 | VALID |
| FP32 | 34.525 | 4,757 / 32,409（14.68%） | Medium | 0.177 | 2.472 | 2.649 | 17.311 | VALID |

动态能量按 `dynamic_power × SAIF_duration / 353` 计算。SC 相对 FP16/FP32 的动态功耗分别低约 48.3%/56.5%，每 score 动态能量低约 56.5%/62.9%；三路均无高-X活动警告。该结果仍沿用 operator-only 边界，不能替代包含反量化和 cache 的完整 Attention 功耗。约 2.47 W 静态值属于整颗 VU9P 模型，不参与模块优劣比较。

## 正式证据

- SC 无阻塞 XSIM：`raw/sc/xsim/20260909_010450_matched_qk_shape_sweep_continuous/`
- FP16 无阻塞 XSIM：`raw/fp16/xsim/20260909_010541_matched_qk_shape_sweep_continuous/`
- FP32 无阻塞 XSIM：`raw/fp32/xsim/20260909_010651_matched_qk_shape_sweep_continuous/`
- SC 周期背压 XSIM：`raw/sc/xsim/20260909_010806_matched_qk_shape_sweep_periodic_backpressure/`
- FP16 周期背压 XSIM：`raw/fp16/xsim/20260909_010855_matched_qk_shape_sweep_periodic_backpressure/`
- FP32 周期背压 XSIM：`raw/fp32/xsim/20260909_011003_matched_qk_shape_sweep_periodic_backpressure/`
- SC 100 MHz OOC：`raw/sc/ooc/20260909_011120_sc_matched_qk_slot_operator_only_100mhz/`
- FP16 100 MHz OOC：`raw/fp16/ooc/20260909_011553_fp16_matched_qk_slot_operator_only_100mhz/`
- FP32 100 MHz OOC：`raw/fp32/ooc/20260909_012256_fp32_matched_qk_slot_operator_only_100mhz/`
- 三路功耗证据：`raw/sc/power/20260912_105917_saif_post_route_100mhz/`、`raw/fp16/power/20260912_110125_saif_post_route_100mhz/`、`raw/fp32/power/20260912_110404_saif_post_route_100mhz/`

三份 OOC 均包含 `summary.json`、post-synth/post-route checkpoint、资源/时序/DRC/route-status、输入哈希；FP 结果还保存 pre-synth IP Tcl、实际生成 XCI 及其哈希。六份 XSIM 与三份 OOC 的目录级 `SHA256SUMS` 已核验通过。早期失败目录 `raw/sc/xsim/20260909_010325_matched_qk_shape_sweep_continuous/` 保留为发现递增 N 协议约束的诊断证据，不进入正式表。

## 尚未完成

Boundary 输入预检已经证明旧 operator-only FP16 向量不能冒充显式反量化：
当前 1,412 个 key group、45,184 个 lane 中有 351 个 FP16 scale record 为
subnormal；显式 scale multiplier 相对旧 cache 产生 11,214 个 bit 差异，经过
旧 QK 输入 FTZ 后仍有 5,580 个语义差异。FP32 逐 lane bit 差异为 0。复现脚本
为 `experiment/05_attention_qk_score/model/analyze_boundary_fp_inputs.py`。因此新
FP16 cache/golden 必须按 boundary 硬件顺序重建，此项目前只属于设计门禁，
不是新增硬件结果。

### 12-seed boundary 软件向量

正式 boundary workload 已覆盖 12 seeds × 全部六档 N，共 72 rows、4,236
scores、16,944 key groups。17 个 `.mem` 文件保存共同 Q `S24`、K `S12`、
三路 native metadata/scale、显式转换后的 cache 检查值和三路 score golden，
独立 verifier 输出：

```text
M05_BOUNDARY_VECTOR_VERIFY_PASS files=17 rows=72 scores=4236 key_groups=16944
```

manifest SHA-256：

```text
620271c8f6208c62464a4ed4e185fef45bfd05ed58b1c3f2471ce98e60f23f3f
```

| 版本 | max abs error | mean abs error | RMSE | cosine similarity |
|---|---:|---:|---:|---:|
| SC | `2.3465837e-4` | `1.0682225e-4` | `1.1364282e-4` | `0.999999992628` |
| FP16 | `4.5794423e-1` | `2.7856156e-3` | `1.3105242e-2` | `0.999901951726` |
| FP32 | `3.0510730e-5` | `1.4985894e-5` | `1.7482514e-5` | `0.999999999826` |

显式 FP16 路径覆盖 4,235 个 subnormal scale record 和 135,367 个由 FTZ
变零的 nonzero K lane。该表证明 workload/golden 已冻结，但在 boundary RTL
与 XSIM bit-exact 通过前仍不属于硬件结论。

### 真实 trace boundary 软件向量

正式 trace workload 使用 2 samples、layers `{0,15,31}`、六档 N 和 q-heads
`{0,17}`，按 GQA 4:1 映射到 KV-heads `{0,4}`。共 72 rows、4,236 scores、
16,944 K group32。post-RoPE BF16 Q nearest-even 转为 S24；post-RoPE BF16 K
先转 S24，再由 production `kv12_quantize_s24` 生成 KV12/native metadata。
18 个源 Q/K/score tensor 与每行 coordinate 均有 hash/provenance。

`M05_TRACE_VECTOR_VERIFY_PASS files=19 rows=72 scores=4236 key_groups=16944
source_tensors=18 manifest_numeric_rel_tol=1e-13
manifest_sha256=05e530d373bb4173927fddd1a174bfc0a0b9573a1ae692911a33290e13ae4f74`

| 软件路径 | max error vs captured score | RMSE vs captured score | RMSE vs common quantized score | cosine vs captured score |
|---|---:|---:|---:|---:|
| SC | `8.7080002e-3` | `2.1699979e-3` | `1.2668754e-4` | `0.9999999737991077` |
| FP16 | `4.8947930e-2` | `4.0669533e-3` | `2.5513382e-3` | `0.9999998556145557` |
| FP32 | `8.7690353e-3` | `2.2281306e-3` | `1.7617686e-5` | `0.9999999742189525` |

捕获 score 对比包含 K KV12 量化和 production Q16 head scale 相对模型精确
`1/sqrt(128)` 的差异；共同输入对比隔离了算子自身误差。Q/K BF16→S24、KV12
与三路 score 均无饱和/clip；显式 FP16 路径覆盖 96 个 subnormal scale 和
3,060 个非零 K lane FTZ。runner 已支持 `... trace`，但尚未运行真实 RTL replay。

共享 16-lane、group32 两拍的 FP boundary conversion/scale 前端、FP IP Tcl、
逐 bit cache unit TB 和 XSIM runner 已落盘并通过静态 source/path/shell 检查；
SC 的四组 Q register、512-group 紧凑 K cache、II=2 load、同步 replay 与
production QK 组合顶层也已落盘。FP16/FP32 现也已把 conversion/scale 前端、
完整宽缓存、同步 replay 与 matched-throughput QK slot 组合为单一逻辑顶层。
三路均尚未执行 elaboration，不能从该准备
状态推导资源或周期。

三路 full-row TB 和 XSIM runner 已进一步完成，覆盖全部 72 rows、4,236 scores、
load II=2、cache/core counters、三路 golden、mask/index/last 及两种背压模式。
三路共用的 256-bit、每 command 四 word、每 score 一 word physical wrapper、
smoke TB、SC/FP OOC source lists、FP IP 合并 Tcl、serial XSIM/OOC runner 也已
落盘。shell/Tcl 完整性、source existence、module/endmodule 数、256-bit result
拼接和 smoke counter expectation 静态检查通过。这些文件尚未经过 Vivado
elaboration，不能据此宣称功能、cache inference、资源、时序或速度已经通过。
合并 Tcl 现为两个 IP 配置文件的自包含逐字拼接，公共 OOC driver 哈希覆盖所有
operator 与 boundary FP IP 请求，不再依赖未被递归哈希的嵌套 `source`。

- boundary-inclusive Q/K dequantizer 与 FP cache width/top-level resource；完整链中只在真实整数→FP 边界计一次；
- 伪随机 backpressure、非法协议定向测试和 Llama-3.1-8B 真实 Q/K boundary RTL replay（12-seed 与真实软件 workload 已完成）；
- 8 rows × 32 Q heads × 8 KV heads 的 GQA address-sensitive scheduler 顶层在当前 ScaleLLM 路径下重新闭环；
- QK→Softmax→PV 非重叠 attention chain 的统一综合，避免孤立模块资源相加；
- 板级/系统 I/O 约束与实测功耗；当前仅有上述 operator-only post-route 估算。

因此，本页已经支持 QK operator-only 的同吞吐资源/速度结论，但在 boundary-inclusive 和完整 attention chain 完成前，模块状态继续保持 `RUNNING`。
