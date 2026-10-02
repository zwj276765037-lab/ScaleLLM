# 11 MLP product Hadamard and Down-A8 scale generation

> **Min/Max 修正状态（2026-09-10）**：实验本地 S35 SC/FP 量化器、synthetic
> 向量和真实 trace 已切换到原始 Group32 Min/Max；真实 trace 的
> `scale_format_overflow_rows=0`，manifest 为
> `f305d9db27e4b354e3492f080953bbd41459a09cd2a6a294c67481463d8f3de7`，完整
> 重生成与逐字节比较 PASS。下文旧 XSIM/OOC 绑定 production robust RTL，只能
> 作为 `robust-clipping legacy`；新 Min/Max XSIM/OOC 尚待串行执行。

- 状态：`RUNNING`（Min/Max synthetic/trace 软件 workload 已验证；旧 robust-clipping 的 XSIM/OOC 仅作 legacy，Min/Max divider/三路 RTL replay/OOC、多 seed与完整 MLP chain 待补）
- 工作单位：一个 `16 rows × 32 lanes` 的 S32 SwiGLU product bundle；共测试 448 bundles
- 主比较边界：共同 `16×32 S32 Q16.16` 输入，经 production shared II=1 Hadamard、4 个 row-time-multiplexed A8 producer，到完整 U8+metadata 输出
- 固定条件：`xcvu9p-flga2104-2L-e`、Vivado 2025.2、100 MHz、`HD.CLK_SRC=BUFGCE_X0Y0`、setup uncertainty 0.150 ns、hold uncertainty 0 ns

## 旧 robust-clipping 硬件子实验结论（legacy）

以下周期与资源均来自修改前的 robust-clipping RTL，只能作为历史结构参考，不能外推为 Min/Max 实现结论。旧结果有利于 ScaleCode 资源与精度、但不支持固定 100 MHz 下“单组更快”：完成 448 bundles 时，旧 SC 为 376,500 cycles，FP16/FP32 均为 360,192 cycles，因此旧 SC 在共同 100 MHz 下慢 4.53%。

资源结论相反：完整 serial physical top 中，SC 使用 78,213 LUT primitives/54,077 FF，FP16 使用 87,865/57,602，FP32 使用 90,072/57,831。SC 相对 FP16 节省 10.99% LUT primitives 和 6.12% FF，相对 FP32 节省 13.17% LUT primitives 和 6.49% FF；三路均为 64 DSP、0 BRAM、0 URAM。完整功能 core 的层级 post-route 结果也保持同方向，SC 相对 FP16/FP32 分别少 5,048/7,229 个 Total LUTs。

单 seed 数值重构中，SC 的 max/mean absolute error、RMSE 和 cosine 四项均优于 FP16/FP32。不过这只是 product-Hadamard+A8 边界的量化误差，尚不能替代完整 MLP 输出或模型精度。

## 旧硬件比较边界与吞吐选择（legacy）

```text
共同 16×32 S32 Q16.16 SwiGLU product
  -> production shared II=1 S32→S35 normalized Hadamard
  SC   -> 4× production robust A8 -> U8 + zp/code/shift
  FP16 -> 4× native affine A8     -> U8 + zp/FP16
  FP32 -> 4× native affine A8     -> U8 + zp/FP32
```

FP 路径从相同 robust clipping bounds 直接形成 `(clip_high-clip_low)/255`，独立生成 affine U8 和 IEEE scale；它不先运行 SC quantizer，不生成、读取或转换 ScaleCode。44/36 radix-16 divider 每周期产生 4 个商位，261 个 directed/random case 全部 exact PASS。

最初的 3-lane FP 候选功能正确，但固定 group II 为 972 cycles，慢于 SC 的最慢 854 cycles，因此不满足 matched-throughput 条件，只保留为 diagnostic。增加到 4 lanes 后 group II 降为 804；由于 lane 数为整数且 3 lanes 已失败，4 lanes 是该共享架构中满足吞吐约束的最小候选。主表只使用 4-lane 版本。

## 旧超宽 OOC physical harness（legacy）

功能 core 的 S32 输入与 U8+metadata 输出合计超过 20,000 个 on-chip tile-bus bits。直接把宽总线作为 OOC 顶层端口时，Vivado placer 报告 `Number of IO terminals is too high for IO rule checking`。该失败与 RTL、资源容量和时序无关，失败目录已保留。

正式 post-route 为三路使用相同的 32-bit serial load/drain physical harness：先装载 512 words，内部仍实例化完整 16-row core，随后串行读出 SC/FP16 的 140 words 或 FP32 的 148 words。三路 harness 的独立 XSIM 均 bit-exact PASS，并验证 output stall 时 payload/last 稳定。主资源表包含整个 physical top；层级表另列完整 `u_core`，不是叶子核面积乘复制数。harness 自身的 Total LUTs/FF 为 SC 17,432/14,428、FP16 17,431/14,428、FP32 17,496/14,430，三路开销基本一致。

## 旧 robust-clipping 功能、协议与周期（legacy）

确定性 workload 使用 seed `0xf1611`，覆盖 448 groups、7,168 row 记录；其中 225 个 row 的 clipping range 为零，Hadamard saturation 和 FP16 nonfinite scale 均为 0。三路均完成 448 次输入和 448 次输出，每个 U8 bundle 与 metadata 均 bit-exact，mismatch、格式错误和内部 error 均为 0。

| 版本 | metadata/row | output II min/max | 首次输出延迟 | 首输入到末输出 | busy cycles | 448-bundle 实测吞吐 @100 MHz | 结果 |
|---|---|---:|---:|---:|---:|---:|---|
| SC production | `zp8/code8/shift8` | 822 / 854 | 846 | 376,500 | 376,051 | 118,991 bundle/s | PASS |
| FP16 native 4-lane | `zp8/IEEE FP16` | 804 / 804 | 804 | 360,192 | 359,743 | 124,378 bundle/s | PASS |
| FP32 native 4-lane | `zp8/IEEE FP32` | 804 / 804 | 804 | 360,192 | 359,743 | 124,378 bundle/s | PASS |

周期性 backpressure 下，SC/FP16/FP32 总周期分别为 376,756、363,748、363,748；output stall cycles 分别为 256、3,556、3,556。stall 数差异来自各自产生 output valid 的相位与固定 ready pattern 的交互；三路都在 `valid && !ready` 时保持 payload 稳定，恢复后仍为 448/448 bit-exact。

| 派生指标 | SC vs FP16 | SC vs FP32 |
|---|---:|---:|
| full physical top LUT primitive 节省 | 10.99%（少 9,652） | 13.17%（少 11,859） |
| full physical top FF 节省 | 6.12%（少 3,525） | 6.49%（少 3,754） |
| full functional core Total LUT 节省 | 11.43%（少 5,048） | 15.60%（少 7,229） |
| full functional core FF 节省 | 8.16%（少 3,525） | 8.64%（少 3,752） |
| 周期加速 `cycles_FP/cycles_SC` | 0.957× | 0.957× |
| SC 相对 FP 的总周期增幅 | 4.53% | 4.53% |

## 旧 robust-clipping 100 MHz post-route：完整 physical top（legacy）

| 版本 | LUT primitives | packed Total LUTs | FF | DSP48E2 | BRAM36/18 | URAM | WNS (ns) | WHS (ns) | 推导 Fmax (MHz) | DRC | unrouted | 有效性 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SC production | 78,213 | 56,530 | 54,077 | 64 | 0 / 0 | 0 | 2.131 | 0.010 | 127.081 | 0 | 0 | VALID |
| FP16 native 4-lane | 87,865 | 61,575 | 57,602 | 64 | 0 / 0 | 0 | 0.880 | 0.010 | 109.649 | 0 | 0 | VALID |
| FP32 native 4-lane | 90,072 | 63,823 | 57,831 | 64 | 0 / 0 | 0 | 1.469 | 0.010 | 117.214 | 0 | 0 | VALID |

`LUT primitives` 是完整 post-route netlist 中 `REF_NAME =~ LUT*` 的逻辑 primitive 数，与 utilization report 中已 pack 的 `Total LUTs` 不可混用。两种口径均完整保留，主派生百分比沿用项目统一的 LUT primitive 口径。

主结论只使用共同 100 MHz。若把本次 OOC 推导 Fmax 与 core 的 448-bundle 周期相乘，吞吐分别约为 SC 151,215、FP16 136,380、FP32 145,789 bundle/s；这说明 SC 的时序余量足以反转固定频率的周期劣势，但该数值不是板级 Fmax，不能替代共同频率比较。

## 旧完整功能 core 层级资源（legacy）

| 版本 | Total LUTs | Logic LUTs | LUTRAMs | SRLs | FF | DSP48E2 |
|---|---:|---:|---:|---:|---:|---:|
| SC production `u_core` | 39,099 | 38,459 | 640 | 0 | 39,649 | 64 |
| FP16 native `u_core` | 44,147 | 43,487 | 640 | 20 | 43,174 | 64 |
| FP32 native `u_core` | 46,328 | 45,668 | 640 | 20 | 43,401 | 64 |

## 旧 robust-clipping synthetic 数值精度（legacy）

共同 reference 是 production S35 Q19.16 Hadamard 的实值输出。SC 按 `(q-zp)×code/2^shift` 重构；FP 按 `(q-zp)×IEEE scale` 重构。

| 版本 | max abs error | mean abs error | RMSE | cosine similarity |
|---|---:|---:|---:|---:|
| SC | 49.15729 | 0.15324 | 1.17259 | 0.999257415 |
| FP16 | 49.34406 | 0.22401 | 1.90782 | 0.997967234 |
| FP32 | 49.37348 | 0.22396 | 1.90787 | 0.997967117 |

本 seed 中 SC 四项均略优于 FP，且 RMSE 明显更低；差异来自 ScaleCode 搜索与 native affine `diff/255` 映射。真实 trace 软件 workload 也保持同方向，具体如下；最终仍须通过 down projection 输出和模型级评测确认系统级影响。

## 真实 trace 软件证据

从正式 `swiglu_down_input_bf16` 选择 16 个跨 2 samples、3 层及序列首/中/尾
位置的唯一 row；每行完整使用 14,336 channels，所以保持 production
448 groups × 16 rows × 32 lanes。6 个源 tensor、16 个 row coordinate 和全部
输入/输出文件均绑定 hash。

`M11_TRACE_VECTOR_VERIFY_PASS files=8 groups=448 rows=16 lanes=32
source_tensors=6
manifest_sha256=f305d9db27e4b354e3492f080953bbd41459a09cd2a6a294c67481463d8f3de7`

| 软件路径 | max error vs raw trace Hadamard | mean error | RMSE | cosine |
|---|---:|---:|---:|---:|
| SC | `0.1033936` | `4.7259391e-4` | `1.4611462e-3` | `0.9999937685509320` |
| FP16 | `0.0604692` | `8.7974598e-4` | `1.7345517e-3` | `0.9999907490464157` |
| FP32 | `0.0614941` | `4.4266074e-4` | `1.2324997e-3` | `0.9999953311580940` |

相对共同 production S35 Hadamard 的 RMSE 为 SC `1.4592621e-3`、FP16
`1.7345393e-3`、FP32 `1.2323259e-3`。BF16→S32 RMSE `2.8367471e-6` 且无
饱和；Hadamard saturation、zero-diff row、FP16 nonfinite scale 与
ScaleCode format overflow row 均为 0。
runner 已支持 `run_matched_xsim.sh sc|fp16|fp32 0|1 trace`，但这组 trace 尚未
经过 RTL replay，因此不改变现有硬件资源/周期结论。

## 当前 Min/Max 版本功耗状态

当前不发布功耗数值。现存 routed DCP 对应旧 robust-clipping producer，不能代表当前 Hadamard 后直接 `max/min` 求 scale 的算法；使用当前 SAIF 标注旧网表会得到方法学上无效的混合结果。必须先完成当前 Min/Max RTL 的功能仿真和 post-route DCP，再按统一的 `100 MHz behavioral XSIM → DUT SAIF → routed DCP → report_power` 流程估算。旧 physical top 继续保留为 legacy 资源/时序证据，不进入当前功耗表。

## 旧 robust-clipping 证据路径（legacy）

- radix-16 divider：`raw/fp_common/xsim/20260909_053546_u44_div_u36_radix16_directed_random/`
- SC 无阻塞 core XSIM：`raw/sc/xsim/20260909_042145_mlp_product_frontend_native_scale_continuous/`
- FP16 无阻塞 4-lane core XSIM：`raw/fp16/xsim/20260909_042818_mlp_product_frontend_native_scale_continuous/`
- FP32 无阻塞 4-lane core XSIM：`raw/fp32/xsim/20260909_042926_mlp_product_frontend_native_scale_continuous/`
- SC 周期背压 core XSIM：`raw/sc/xsim/20260909_042439_mlp_product_frontend_native_scale_periodic_backpressure/`
- FP16 周期背压 4-lane core XSIM：`raw/fp16/xsim/20260909_043036_mlp_product_frontend_native_scale_periodic_backpressure/`
- FP32 周期背压 4-lane core XSIM：`raw/fp32/xsim/20260909_043144_mlp_product_frontend_native_scale_periodic_backpressure/`
- SC serial harness XSIM：`raw/sc/xsim/20260909_043956_mlp_product_frontend_serial_ooc_wrapper/`
- FP16 serial harness XSIM：`raw/fp16/xsim/20260909_044042_mlp_product_frontend_serial_ooc_wrapper/`
- FP32 serial harness XSIM：`raw/fp32/xsim/20260909_044133_mlp_product_frontend_serial_ooc_wrapper/`
- SC 正式 OOC：`raw/sc/ooc/20260909_044220_sc_mlp_product_frontend_native_scale_serial_ooc_100mhz/`
- FP16 正式 OOC：`raw/fp16/ooc/20260909_045914_fp16_mlp_product_frontend_native_scale_serial_ooc_100mhz/`
- FP32 正式 OOC：`raw/fp32/ooc/20260909_051628_fp32_mlp_product_frontend_native_scale_serial_ooc_100mhz/`

以上 13 份正式证据的目录级 `SHA256SUMS` 均已逐项核验；FP16/FP32 OOC 的 `IP_XCI_SHA256SUMS` 也通过。三份 OOC 都包含完整 physical top post-route checkpoint、资源/时序/DRC/route-status、层级资源报告和输入哈希。

不进入主表但保留的诊断/失败证据：

- 3-lane FP16 continuous/BP：`raw/fp16/xsim/20260909_042229_mlp_product_frontend_native_scale_continuous/`、`raw/fp16/xsim/20260909_042523_mlp_product_frontend_native_scale_periodic_backpressure/`
- 3-lane FP32 continuous/BP：`raw/fp32/xsim/20260909_042336_mlp_product_frontend_native_scale_continuous/`、`raw/fp32/xsim/20260909_042633_mlp_product_frontend_native_scale_periodic_backpressure/`
- 直接宽端口 SC OOC placer 失败：`raw/sc/ooc/20260909_043255_sc_mlp_product_frontend_native_scale_100mhz/`

## 尚未完成

- 不少于 10 个固定 seed、伪随机长 backpressure、reset/clear 中断与非法协议定向测试；
- Llama-3.1-8B 真实 SwiGLU product RTL replay（软件 full-shape workload 已完成），以及下游 down-projection 的最终误差；
- 功耗、energy per bundle 和不同 quotient-lane Pareto 点的功耗比较；
- 非重叠 MLP chain 顶层与板级时序。

因此，旧数据只记录 robust-clipping 结构曾出现的资源/周期混合结果；它不再支持当前 Min/Max producer 的资源或速度结论。Min/Max 三路 RTL replay 与 OOC 完成前，本模块状态保持 `RUNNING`。
