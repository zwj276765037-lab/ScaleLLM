# 02 Attention A8W8 projection

- 状态：`RUNNING`（8×16×128 单 tile boundary-inclusive 同吞吐子实验已完成；25-case FP16 非有限值语义探针、正式 Min/Max 18-tile Q/K/V trace 生成/验证及 SC 周期背压 RTL replay 已 PASS；SC continuous、FP16/FP32 trace、当前源码 synthetic、Wo 多 tile 与 frontend-inclusive 待补）
- 工作单位：128 个 group32 后的一份 physical `8 rows × 16 columns` S24 output tile
- 主比较口径：从相同 U8 activation、S8 weight、zero-point 和 SC/FP scale metadata 开始，经过 128 条真实 group32 lane、S42 accumulation 与共同 S24 round/saturate 输出
- 固定条件：`xcvu9p-flga2104-2L-e`、Vivado 2025.2、100 MHz、`HD.CLK_SRC=BUFGCE_X0Y0`、setup uncertainty 0.150 ns、hold uncertainty 0 ns

## 正式结论（8×16×128 单 tile boundary-inclusive）

SC、FP16 和 FP32 均真实实现 128 条并行 lane 与一个共同 128-lane accumulator；没有用单 lane 资源乘 128 代替综合。三种顶层都在同一 128-group workload 上达到严格 `II=2`，并在最终 8×16 S24 tile 上逐 lane 0 mismatch，因此无需复制即可达到相同 group 接受率和同一 tile 计算几何。

在共同 100 MHz post-route 条件下，SC 相对 FP16 节省 20.15% LUT、49.95% FF 和 5.56% DSP；相对 FP32 节省 26.09% LUT、58.60% FF 和 15.00% DSP。SC 单 tile 总周期为 267，分别比 FP16 的 294 和 FP32 的 287 快 1.101×/1.075×；差异来自浮点边界流水填充，三者稳态 input II 相同。

FP 路径包含真实 boundary cost：每条 lane 都执行 S21 correlation 的 fixed-to-float、activation/weight scale multiply、结果转 S42，再进入与 SC 相同的 tile accumulator。FP16 每 lane 的 32-credit/32-entry FIFO 也计入资源，以覆盖长流水并保持 `II=2`。

## 功能、吞吐与延迟

共同 workload 为 `8 rows × 16 cols × 128 groups × 32 MACs = 524,288 MACs`。输入每个 group 包含 8 行 activation 和 16 列 weight；输出使用同一 S24 round/saturate 合同。testbench 的 output backpressure 模式没有在唯一输出 tile 到达时形成 stall，因此本表是该单 tile 的无输出阻塞结果。

| 版本 | groups | output lanes | mismatch | input II min/max | 首 tile latency (cycle) | 末输入接受 (relative cycle) | 总周期 | 单批 tile/s @100 MHz | 同吞吐资格 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SC production | 128 | 128 | 0 | 2 / 2 | 266 | 254 | 267 | 374,532 | PASS，目标锚点 |
| FP16 boundary-inclusive | 128 | 128 | 0 | 2 / 2 | 293 | 254 | 294 | 340,136 | PASS |
| FP32 boundary-inclusive | 128 | 128 | 0 | 2 / 2 | 286 | 254 | 287 | 348,432 | PASS |

`tile/s` 是一份 tile 从首输入到输出完成的单批倒数，包含 pipeline fill/drain，不等同于无限连续多 tile 的稳态 tile/s。当前匹配顶层在 128 groups 后停止接受并需 clear 才开始下一 tile；连续 Q/K/V/Wo tile 调度仍列在待办中。XSIM JSON 中遗留 `effective_gops_150mhz` 字段不用于本页结论。

## 100 MHz post-route 资源与时序

| 版本 | LUT primitives | FF primitives | DSP48E2 | RAMB36E2 | RAMB18E2 | URAM | WNS (ns) | WHS (ns) | 推导 Fmax (MHz) | DRC errors | unrouted | 有效性 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SC production | 135,975 | 106,081 | 2,176 | 0 | 0 | 0 | 2.280 | 0.010 | 129.534 | 0 | 0 | VALID |
| FP16 boundary-inclusive | 170,279 | 211,937 | 2,304 | 0 | 0 | 0 | 2.867 | 0.006 | 140.185 | 0 | 0 | VALID |
| FP32 boundary-inclusive | 183,975 | 256,225 | 2,560 | 0 | 0 | 0 | 1.942 | 0.008 | 124.094 | 0 | 0 | VALID |

DSP 几何与模块 00 的真实单 lane 结果严格一致：SC `128×17=2,176`、FP16 `128×18=2,304`、FP32 `128×20=2,560`。LUT/FF 则保留完整顶层综合结果，包含共同 accumulator、控制、FIFO 和工具跨层优化，不能由单 lane 简单倍乘替代。

`Fmax` 是本次 post-route critical period 的推导值，不替代共同 100 MHz 主比较。FP16 本次推导 Fmax 高于 SC 是具体流水与布局结果；主资源结论不混用各自 Fmax。

## 派生比较

| 指标 | SC vs FP16 | SC vs FP32 |
|---|---:|---:|
| LUT 节省 | 20.15%（少 34,304） | 26.09%（少 48,000） |
| FF 节省 | 49.95%（少 105,856） | 58.60%（少 150,144） |
| DSP 节省 | 5.56%（少 128） | 15.00%（少 384） |
| 首 tile 加速 `latency_FP/latency_SC` | 1.102× | 1.075× |
| 单 tile 整批加速 `cycles_FP/cycles_SC` | 1.101× | 1.075× |
| 单 tile 周期降低 | 9.18%（少 27 cycles） | 6.97%（少 20 cycles） |

## 数值语义

- 三路都从相同 pre-MAC `(activation-zero_point)×weight` correlation 开始，但分别使用自己的数值合同与 golden，不声明 SC/FP16/FP32 最终 tile 彼此 bit-exact。
- SC 对每个 group contribution 执行 `corr × act_code × weight_code` 和 shift alignment；FP32 执行单精度 scale/product；FP16 执行半精度逐级 product、denormal flush-to-zero，再转回 S42。
- 当前固定 seed 中共有 11,305 个 FP16 group-lane contribution 在 IP 语义下为零。三路最终 S24 tile 分别与各自 golden 0 mismatch、无最终饱和。
- 相对共同 FP64 golden 的 max/mean error、RMSE、cosine 以及更多 seed 尚未完成。

### 真实范围 FP16 非有限值门禁

使用真实 projection input 与 layer-0 W8 权重的范围分析已确认，Q/K/V 单 tile
correlation 分别达到 `[-277754,269277]`、`[-269769,298909]` 和
`[-121705,106787]`；对应共有 1,247、1,517、20 个值超过 FP16 最大有限值。
这些事件不能通过挑选较小样本规避，也不能在软件 golden 中自行改写为有限
饱和值。

为冻结真实 AMD IP 语义，实验新增
`tb/m02_fp16_nonfinite_probe_tb.sv`、
`vivado/run_fp16_nonfinite_probe.tcl` 和
`run_fp16_nonfinite_probe.sh`，以及独立的
`model/verify_fp16_nonfinite_probe.py`。探针真实经过 production group32 MAC，并对
25 个阈值/真实极值/正负 `Infinity x 0` case 逐级记录
`S21 -> FP32 -> FP16 -> mul -> mul -> FP32 -> S42` bit pattern，包含
`Infinity x 0`；verifier 检查 case/correlation/分类标志/S42 payload 并冻结
`semantic_map.json`。三次定向 XSIM 均 PASS；最终权威 run 为
`raw/fp16/semantic_probe/20260910_121638_s21_to_fp16_to_s42/`，输入、FP XCI 和
目录哈希均通过，`semantic_map.json` SHA256 为
`99c04c9756908f11ed41950e9a4e4e60f78a3e9424dc87931f02ad82e570d7e5`。

最终映射记录 25 个 case：S21→FP16 为 7 finite/18 infinity；第一次乘法为
7 finite/16 infinity/2 NaN；第二次乘法和 widen FP32 均为
7 finite/14 infinity/4 NaN。硬件实测的有限到正无穷阈值位于正负 65,519 与
65,520 之间；`Infinity x 0` 产生 `0x7e00` NaN。这里冻结的是 AMD IP 的实际
bit pattern 和 float-to-fixed payload，不把非有限结果解释为数值正确。

探针之后的正式 Q/K/V trace 链已完成生成与独立验证。生成器覆盖 2 samples × layers
`{0,15,31}` × `{Q,K,V}`，共 18 个 `8x16x128` tile、2,304 transactions 和
2,304 个 S24 输出。Q/K tile 纳入 M03 provenance-checked 溢出坐标；V tile 在
真实八 token 上对全部 1,024 个输出行执行 max-abs correlation 排序并选择最坏
16 行。生成器在缺少 PASS+hashed semantic map 时曾实测状态 1 拒绝且不写数据；
门禁解除后形成的正式 manifest SHA256 为
`c1702bc0b43ca56291f886b3ee5a23a7eb1d385907c081ee7b21ec4c14db1e54`。

SC 周期背压 RTL replay 已在
`raw/sc/xsim/20260910_121902_matched_tile_boundary_inclusive_trace_bp1/` PASS：
18 tiles、2,304 groups、2,304 outputs、0 mismatch，input II min/max 均为 2，
首输入至末输出 4,971 cycles，输入等待 2,502 cycles、输出等待 12 cycles。
这证明当前 Min/Max trace 上的 SC 真实 RTL 路径及周期背压协议正确；它不能替代
尚未运行的 SC continuous 或 FP16/FP32 trace replay。

该链现已纳入统一只读门禁，最新结果为
`M02_STATIC_CONTRACT_VERIFY_PASS files=9 semantic_maps=3 formal_trace=1
tiles=18 transactions=2304 valid_outputs=2304`；全局门禁同时为
`BOUNDARY_PREFLIGHT_PASS modules=12 shells=53 tcl=44 source_lists=43
sources=187 sv=69 inline_ip_drivers=4`。

为支持 trace 的永久 ready/周期背压，matched runner 和旧 synthetic TB 增加了
显式 backpressure 参数。该变更不修改被测 RTL，也不影响三份既有 OOC，但会使
旧 XSIM 的 current-input hash 失配；因此三路 synthetic XSIM 必须在后续串行
队列中按当前源码补跑，旧 PASS 只保留为历史功能证据。

## 100 MHz post-route 功耗诊断（behavioral SAIF）

当前仅得到 SC 单 tile 的“基于仿真波形的 post-route 估算”，不是板级实测：2.645 µs SAIF、72,606 / 359,579 个网表节点匹配（20.19%）、Vivado Medium confidence，动态功耗 5.503 W、器件静态 2.552 W、总片上功耗 8.054 W；完整 `8×16` output tile 的动态能量为 14.555 µJ。

该运行虽然功能为 128 groups、0 mismatch、II=2，但 `u_accum/out_s24` 等未初始化/未有效观察节点产生 9,225 条高-X活动警告，足以显著削弱活动可信度，因此资格明确为 `diagnostic_high_x`，不得进入正式功耗对比。FP16/FP32 尚未运行。约 2.55 W 静态值仍是整颗 VU9P 模型，不是本模块独占功耗。原始目录为 `raw/sc/power/20260912_104128_saif_post_route_100mhz/`。

## 已核验证据

- SC XSIM：`raw/sc/xsim/20260908_222128_matched_tile_boundary_inclusive/`
- FP16 XSIM：`raw/fp16/xsim/20260908_222223_matched_tile_boundary_inclusive/`
- FP32 XSIM：`raw/fp32/xsim/20260908_222438_matched_tile_boundary_inclusive/`
- SC 100 MHz OOC：`raw/sc/ooc/20260908_222657_sc_matched_8x16x128_tile_boundary_inclusive_100mhz/`
- FP16 100 MHz OOC：`raw/fp16/ooc/20260908_225903_fp16_matched_8x16x128_tile_boundary_inclusive_100mhz/`
- FP32 100 MHz OOC：`raw/fp32/ooc/20260908_235041_fp32_matched_8x16x128_tile_boundary_inclusive_100mhz/`
- FP16 非有限语义映射：`raw/fp16/semantic_probe/20260910_121638_s21_to_fp16_to_s42/`
- SC Min/Max 18-tile 周期背压 trace XSIM：`raw/sc/xsim/20260910_121902_matched_tile_boundary_inclusive_trace_bp1/`

正式 XSIM/OOC 的共享 RTL 哈希一致。三个 OOC 目录均包含 `summary.json`、post-synth/post-route checkpoint、资源/时序/DRC/route-status 报告和输入哈希；FP 目录还保存 pre-synth IP Tcl、生成的 XCI 及其哈希。所有目录级 `SHA256SUMS` 已逐项通过。

## 尚未完成

- Q/K/V/Wo phase 的连续多 tile workload、16-row cohort 两 wave 与 tail/clear 调度；
- 把模块 01 frontend/cache 接入同一顶层，验证 scale metadata 边界只计一次；
- operator-only 分栏、周期性/伪随机 output backpressure 和不少于 10 个固定 seed；
- 全量相对 FP64 精度统计以及更多 Llama-3.1-8B activation/weight trace；
- 当前源码三路 synthetic XSIM、SC continuous trace，以及 FP16/FP32 的
  continuous/周期背压 18-tile Q/K/V trace XSIM；
- production `col3` array 的非重叠完整层次对比，避免用孤立 matched tile 替代系统实现。

因此本页当前支持“在相同 8×16×128 tile 几何、严格 `II=2` 和共同 100 MHz 下，SC 比真实 boundary-inclusive FP16/FP32 tile 使用更少 LUT/FF/DSP，并降低单 tile 完成周期”的子结论，尚不升级为完整 Attention projection/chain 最终结论。
> **P0 状态（2026-09-10）**：正式 projection trace 已由当前 Min/Max 上游生成，
> 并已有 SC 周期背压 RTL 0 mismatch；旧 synthetic XSIM 仍仅作历史功能证据，
> FP16/FP32 trace 和 SC continuous 尚未完成，不能据此签核三路整链结论。
