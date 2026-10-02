# 01 Attention input Hadamard and A8 scale/cache boundary

> **Min/Max 修正状态（2026-09-10）**：实验本地 S27 SC/FP 量化器、synthetic
> 向量和真实 trace 已切换到原始 Group32 Min/Max，`pre_quant_clip_lanes=0`；正式
> trace manifest 为 `7e6dea87382e21471a2f0c32d5cae7ca32d31f7a9ac8cc9999f306aef93aa8d6`，
> 完整重生成与逐字节比较 PASS。下文 2026-09-09 的 XSIM/OOC 数字仍绑定旧
> production robust RTL，只保留为 `robust-clipping legacy` 结构/历史证据；新
> Min/Max XSIM/OOC 完成前不得引用为最终量化器资源或速度结论。

- 状态：`RUNNING`（Min/Max synthetic/trace 软件 workload 已验证；旧 robust-clipping 的 XSIM/OOC 仅作 legacy，Min/Max 三路 RTL replay/OOC、多 seed 和伪随机长背压待补）
- 工作单位：一个 `8 rows × 32 lanes` 的 S24 输入 bundle；每个 bank 共 128 bundles
- 主比较边界：共同 `8×32 S24 Q8.16` 输入，经 production normalized Hadamard、A8 producer、两 bank cache，到 U8+metadata 读响应
- 固定条件：`xcvu9p-flga2104-2L-e`、Vivado 2025.2、100 MHz、`HD.CLK_SRC=BUFGCE_X0Y0`、setup uncertainty 0.150 ns、hold uncertainty 0 ns

## 旧 robust-clipping 硬件子实验结论（legacy）

以下周期与资源均来自修改前的 robust-clipping RTL，只能作为历史结构参考，不能外推为 Min/Max 实现结论。在共同 100 MHz 下，旧 production SC 完成 128 bundles 需要 28,959 cycles，而三商单元 FP16/FP32 baseline 均为 26,888 cycles；旧 SC 慢 7.70%。旧 SC 使用 65,938 LUT/39,125 FF，比 FP16 多 4,539 LUT/508 FF，比 FP32 多 4,505 LUT/768 FF。三路 DSP 数均为 64。

差异来自 scale **生成边界**，不是后续整数 ScaleCode apply 核。SC 的 production robust quantizer 搜索 code/shift 并逐 lane 做编码比值；FP baseline 直接由相同 clipping bounds 形成 `diff/255`，用三个 8-cycle 饱和商单元生成 affine U8，再把 Q24 scale 转为 IEEE FP16/FP32。三商单元是满足 SC bundle rate 的最小候选；两商单元按每 row 32 lanes 的 16 个 quotient batch，无法达到 production rate。早期八商单元版本只保留为 Pareto/诊断证据，不进入主表。

存储方面，SC 和 FP16 metadata 都是每 row 24 bits，因此实现后的 cache tile 数相同；FP32 每 row 40 bits，多使用 1 个 RAMB36E2 和 1 个 RAMB18E2。相对 FP32，SC 的等效 BRAM36 tile 仅节省 4.35%，不足以抵消本边界的 LUT/FF 与周期劣势。

## 旧硬件比较边界与实现选择（legacy）

```text
共同 8×32 S24 Q8.16
  -> production hap_hadamard32_norm_stream
  SC   -> production robust A8 -> U8 + zp/code/shift -> 2×128 cache
  FP16 -> native affine A8      -> U8 + zp/FP16 scale -> 2×128 cache
  FP32 -> native affine A8      -> U8 + zp/FP32 scale -> 2×128 cache
```

FP 路径没有先运行 SC quantizer、没有生成或读取 ScaleCode，也没有把 SC metadata 事后转换成浮点。FP scale 定义为 robust clipping 后的 `(clip_high-clip_low)/255`；U8 使用独立 affine 映射。FP16 scale 采用 `Q24→FP32→FP16` 两级 Xilinx converter，FP32 采用 `Q24→FP32`。所有版本包含相同输入捕获、Hadamard、bundle 组装、cache 写读、tag 和 backpressure 边界。

第一版 FP frontend 每 row 使用 8 个商单元，功能和 post-route 均通过，但资源分别为 FP16 74,723 LUT/43,045 FF、FP32 74,522 LUT/42,805 FF。它明显不是满足吞吐条件下的最小资源 baseline，因此正式结果改用每 row 3 个商单元。正式顶层是真实完整实现，没有用叶子核面积乘复制数。

## 旧 robust-clipping 功能、协议与周期（legacy）

确定性 workload 使用 seed `20260908`，覆盖全零、S24 正负边界、极小非零、交替正负、常值、正态与重尾输入。三路均完成 128 次输入、128 次 cache 写入、128 次读响应和一次 bank release；每个 U8 bundle 与 metadata 均 bit-exact，mismatch、格式错误和 Hadamard saturation 均为 0。

| 版本 | metadata/row | write II min/max | 首次写入延迟 | 首输入到末写入 | 无阻塞总周期 | 128-bundle 实测吞吐 @100 MHz | 结果 |
|---|---|---:|---:|---:|---:|---:|---|
| SC production | `zp8/code8/shift8` | 221 / 232 | 91 | 28,959 | 29,091 | 442,004 bundle/s | PASS |
| FP16 native 3-lane | `zp8/IEEE FP16` | 211 / 211 | 91 | 26,888 | 27,020 | 476,049 bundle/s | PASS |
| FP32 native 3-lane | `zp8/IEEE FP32` | 211 / 211 | 91 | 26,888 | 27,020 | 476,049 bundle/s | PASS |

周期性 backpressure 下，三路总周期分别为 29,131、27,068、27,068；SC/FP16/FP32 分别经历 40/48/48 个 output stall cycles。所有版本在 `valid && !ready` 时保持 payload、tag 和 metadata 稳定，恢复后仍为 128/128 bit-exact。

| 派生指标 | SC vs FP16 | SC vs FP32 |
|---|---:|---:|
| LUT 节省（负数表示 SC 更多） | -7.39%（多 4,539） | -7.33%（多 4,505） |
| FF 节省（负数表示 SC 更多） | -1.32%（多 508） | -2.00%（多 768） |
| 等效 BRAM36 tile 节省 | 0% | 4.35%（少 1.5 tiles） |
| 周期加速 `cycles_FP/cycles_SC` | 0.928× | 0.928× |
| SC 相对 FP 的总周期增幅 | 7.70% | 7.70% |

## 旧 robust-clipping 100 MHz post-route 资源与时序（legacy）

| 版本 | LUT primitives | FF primitives | DSP48E2 | RAMB36E2 | RAMB18E2 | 等效 BRAM36 | URAM | WNS (ns) | WHS (ns) | 推导 Fmax (MHz) | DRC | unrouted | 有效性 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SC production | 65,938 | 39,125 | 64 | 31 | 4 | 33.0 | 0 | 2.361 | 0.010 | 130.907 | 0 | 0 | VALID |
| FP16 native 3-lane | 61,399 | 38,617 | 64 | 31 | 4 | 33.0 | 0 | 0.982 | 0.010 | 110.889 | 0 | 0 | VALID |
| FP32 native 3-lane | 61,433 | 38,357 | 64 | 32 | 5 | 34.5 | 0 | 1.896 | 0.0098 | 123.396 | 0 | 0 | VALID |

等效 BRAM36 按 `RAMB36E2 + RAMB18E2/2` 计算。主结论只使用共同 100 MHz。若把本次 OOC 推导 Fmax 与各自周期相乘，128-bundle 吞吐分别约为 SC 578,615、FP16 527,887、FP32 587,424 bundle/s；这说明 SC 的时序余量优于 FP16，但该推导不是板级 Fmax，也不能替代共同频率比较。

## 旧 robust-clipping synthetic 数值精度（legacy）

共同 reference 是 Hadamard S27 Q8.16 的实值输出。SC 按 `(q-zp)×code/2^shift` 重构；FP 按 `(q-zp)×IEEE scale` 重构。

| 版本 | max abs error | mean abs error | RMSE | cosine similarity |
|---|---:|---:|---:|---:|
| SC | 6.390625 | 0.0175847 | 0.0793574 | 0.999948892 |
| FP16 | 6.201172 | 0.0219282 | 0.0830078 | 0.999943063 |
| FP32 | 6.155863 | 0.0218910 | 0.0827261 | 0.999943383 |

当前 seed 中 SC 的 mean/RMSE/cosine 略好，FP 的 max absolute error 略低。差异来自两种 scale/U8 映射，不足以概括模型级精度；三路都必须在后续真实 attention trace 与整链输出上继续评估。

## 真实 Attention 输入 workload

正式 `data_trace/` 复用 M03 经独立 verifier 约束的 projection-input 捕获，选择
8 个真实 token row，覆盖两个样本和层 0/15/31；每行完整覆盖 4096 hidden
elements，即 128 个 group32。输入统一按 BF16 nearest-even 实值转为 S24
Q8.16，随后复用 production Hadamard，并对 SC/native-FP 都使用独立 reference
定义的原始 Min/Max ideal-scale affine A8；ScaleCode 仅用于 SC 重构。

- workload：128 bundles，32,768 lanes，6 个 source tensor；
- `input_s24_saturation=0`、`hadamard_saturation_count=0`；
- `sc_zero_scale_rows=0`、`fp_zero_diff_rows=0`；
- `pre_quant_clip_lanes=0`，SC/FP U8 由同一 ideal Min/Max scale 产生。

| 版本 | max abs error | mean abs error | RMSE | cosine similarity |
|---|---:|---:|---:|---:|
| SC | 8.9874268e-3 | 1.2479412e-3 | 1.7589088e-3 | 0.9999884084 |
| FP16 | 8.1481934e-3 | 1.1999371e-3 | 1.6618187e-3 | 0.9999896498 |
| FP32 | 7.9122186e-3 | 1.1991840e-3 | 1.6601894e-3 | 0.9999896701 |

完整临时重生成、文件 inventory、逐行格式、依赖哈希与逐字节比较结果为：

```text
M03_PROJECTION_INPUT_VERIFY_PASS files=6 samples=2 layers=3 qk_checks=12 bit_mismatches=824370 manifest_sha256=53e54b7d88138a83ff1e56fec7653ccdd4206cc12382c7606c616764ccff2ff1
M01_TRACE_VECTOR_VERIFY_PASS files=8 rows=8 groups=128 lanes=32 source_tensors=6 manifest_sha256=7e6dea87382e21471a2f0c32d5cae7ca32d31f7a9ac8cc9999f306aef93aa8d6
```

runner 已支持 `synthetic|trace` 数据选择，且 trace run 会把生成器、独立
verifier、production model、capture manifest、6 个 BF16 NPY 与全部 `.mem`
纳入 `INPUT_SHA256SUMS`。当前尚未启动三路 trace XSIM，所以这里仍只支持软件
精度和输入范围结论。

## 当前 Min/Max 版本功耗状态

当前不发布功耗数值。现存 routed DCP 对应旧 robust-clipping producer，而当前算法已改为 Hadamard 后直接归约 `max/min` 求 scale；把当前 behavioral SAIF 强行导入旧 DCP 会同时破坏算法边界和结构映射，所得数值没有比较资格。必须先完成当前 Min/Max RTL 的 XSIM 与 post-route DCP，再按统一的 `100 MHz behavioral XSIM → DUT SAIF → routed DCP → report_power` 流程估算。旧静态/资源证据继续保留为 legacy，但不能填入当前功耗表。

## 旧 robust-clipping 证据路径（legacy）

- SC 无阻塞 XSIM：`raw/sc/xsim/20260909_021828_attention_frontend_native_scale_continuous/`
- SC 周期背压 XSIM：`raw/sc/xsim/20260909_022629_attention_frontend_native_scale_periodic_backpressure/`
- FP16 无阻塞 XSIM：`raw/fp16/xsim/20260909_031114_attention_frontend_native_scale_continuous/`
- FP16 周期背压 XSIM：`raw/fp16/xsim/20260909_031257_attention_frontend_native_scale_periodic_backpressure/`
- FP32 无阻塞 XSIM：`raw/fp32/xsim/20260909_031216_attention_frontend_native_scale_continuous/`
- FP32 周期背压 XSIM：`raw/fp32/xsim/20260909_031341_attention_frontend_native_scale_periodic_backpressure/`
- SC 正式 OOC：`raw/sc/ooc/20260909_022840_sc_attention_frontend_native_scale_cache_100mhz/`
- FP16 正式 3-lane OOC：`raw/fp16/ooc/20260909_031424_fp16_attention_frontend_native_scale_cache_100mhz/`
- FP32 正式 3-lane OOC：`raw/fp32/ooc/20260909_032837_fp32_attention_frontend_native_scale_cache_100mhz/`

六份正式 XSIM 与三份正式 OOC 的目录级 `SHA256SUMS` 均已逐项核验；FP OOC 的 `IP_XCI_SHA256SUMS` 也通过。三份 OOC 都包含完整顶层 post-route checkpoint、资源/时序/DRC/route-status 报告和输入哈希。

八商单元诊断 OOC 保留在：

- `raw/fp16/ooc/20260909_024112_fp16_attention_frontend_native_scale_cache_100mhz/`
- `raw/fp32/ooc/20260909_025517_fp32_attention_frontend_native_scale_cache_100mhz/`

它们不进入正式主表。

## 尚未完成

- 不少于 10 个固定 seed、伪随机长 backpressure、reset/clear 中断与非法协议定向测试；
- Llama-3.1-8B 真实 attention 输入的三路 RTL replay，以及下游 projection/RoPE/QK/PV 链的最终误差；
- producer-only/cache-only 资源拆分和功耗/energy per bundle；
- 非重叠 attention chain 顶层与板级时序。

因此，旧数据只记录 robust-clipping 结构曾出现的负/混合结果；它不再支持当前 Min/Max producer 的资源或速度结论。Min/Max 三路 RTL replay 与 OOC 完成前，本模块状态保持 `RUNNING`。
