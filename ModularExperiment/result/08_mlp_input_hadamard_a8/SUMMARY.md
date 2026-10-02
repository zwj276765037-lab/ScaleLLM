# 08 MLP input Hadamard and A8 scale/cache boundary

> **Min/Max 修正状态（2026-09-10）**：实验本地 S27 SC/FP 量化器、synthetic
> 向量和真实 trace 已切换到原始 Group32 Min/Max，且生成器已解除对共享脚本私有
> `hadamard()` helper 的依赖。正式 trace manifest 为
> `aa2ba847b92230b3cb7bfe687e58377d965d3213a2d9df15ea46c37242c23cf2`，完整
> 重生成与逐字节比较 PASS。下文旧 XSIM/OOC 仍是 `robust-clipping legacy`，
> 新 Min/Max XSIM/OOC 完成前不得用于最终量化器资源或速度签核。

- 状态：`RUNNING`（Min/Max synthetic/trace 软件 workload 已验证；旧 robust-clipping 的 XSIM/OOC 仅作 legacy，Min/Max 三路 RTL replay/OOC、多 seed和伪随机长背压待补）
- 工作单位：一个 `16 rows × 32 lanes` 的 S24 输入 bundle；共测试 128 bundles
- 主比较边界：共同 `16×32 S24 Q8.16` 输入，经 production fold4 normalized Hadamard、4 个 row-time-multiplexed A8 producer、两 bank cache，到 U8+metadata 读响应
- 固定条件：`xcvu9p-flga2104-2L-e`、Vivado 2025.2、100 MHz、`HD.CLK_SRC=BUFGCE_X0Y0`、setup uncertainty 0.150 ns、hold uncertainty 0 ns

## 旧 robust-clipping 硬件子实验结论（legacy）

以下周期与资源均来自修改前的 robust-clipping RTL，只能作为历史结构参考，不能外推为 Min/Max 实现结论。在共同 100 MHz 下，旧 production SC 完成 128 bundles 的首输入到末写入为 194,357 cycles，而 FP16/FP32 baseline 均为 182,704 cycles；旧 SC 慢 6.38%。旧 SC 使用 37,644 LUT/35,943 FF，分别比 FP16 多 2,482 LUT/213 FF、比 FP32 多 2,392 LUT/150 FF。三路 DSP 数均为 8。

差异来自 scale **生成边界**，不是后续整数 ScaleCode apply 核。SC 使用四个 production robust quantizer 搜索 code/shift 并逐 lane 做编码比值；FP baseline 使用四个独立 native affine quantizer，由相同 clipping bounds 形成 `(clip_high-clip_low)/255`，每 quantizer 复用三个 8-cycle 商单元生成 U8，再把 Q24 scale 转为 IEEE FP16/FP32。FP 路径没有先运行 SC quantizer，也没有读取或转换 ScaleCode。

存储方面，SC 与 FP16 metadata 都是每 row 24 bits，因此 post-route cache tile 数相同；FP32 每 row 40 bits，多使用 2 个 RAMB36E2 和 2 个 RAMB18E2。按等效 RAMB36 tile 计算，SC 相对 FP32 节省 4.35%，但不足以抵消本边界的 LUT/FF 与周期劣势。

## 旧硬件比较边界与实现选择（legacy）

```text
共同 16×32 S24 Q8.16
  -> production hap_mlp_hadamard32_s24_fold4
  SC   -> 4× production robust A8 -> U8 + zp/code/shift -> 双 8-row cache
  FP16 -> 4× native affine A8     -> U8 + zp/FP16       -> 双 8-row cache
  FP32 -> 4× native affine A8     -> U8 + zp/FP32       -> 双 8-row cache
```

三路包含相同输入捕获、fold4 Hadamard、16-row bundle 组装、cache 写读、tag、bank release 和 backpressure 边界。FP scale 定义为 robust clipping 后的 `(clip_high-clip_low)/255`；U8 使用独立 affine 映射。FP16 scale 采用 `Q24→FP32→FP16` 两级 Xilinx converter，FP32 采用 `Q24→FP32`。正式 OOC 均为完整顶层，不使用叶子核面积乘复制数。

## 旧 robust-clipping 功能、协议与周期（legacy）

确定性 workload 使用 seed `0x16cace`，覆盖 128 个 group、2,048 个 row 记录；其中 362 个 row 的 clipping range 为零，Hadamard saturation 为 0。三路均完成 128 次输入、128 次 cache 写入、128 次读响应和一次 bank release；每个 U8 bundle 与 metadata 均 bit-exact，mismatch 和格式错误均为 0。

| 版本 | metadata/row | write II min/max | 首次写入延迟 | 首输入到末写入 | 无阻塞总周期 | 128-bundle 实测吞吐 @100 MHz | 结果 |
|---|---|---:|---:|---:|---:|---:|---|
| SC production | `zp8/code8/shift8` | 1502 / 1527 | 1523 | 194,357 | 194,490 | 65,858 bundle/s | PASS |
| FP16 native | `zp8/IEEE FP16` | 1414 / 1430 | 1430 | 182,704 | 182,837 | 70,059 bundle/s | PASS |
| FP32 native | `zp8/IEEE FP32` | 1414 / 1430 | 1430 | 182,704 | 182,837 | 70,059 bundle/s | PASS |

周期性 backpressure 下，三路总周期分别为 194,538、182,885、182,885；每路经历 48 个 output stall cycles。所有版本在 `valid && !ready` 时保持 payload、tag 和 metadata 稳定，恢复后仍为 128/128 bit-exact。

| 派生指标 | SC vs FP16 | SC vs FP32 |
|---|---:|---:|
| LUT 节省（负数表示 SC 更多） | -7.06%（多 2,482） | -6.79%（多 2,392） |
| FF 节省（负数表示 SC 更多） | -0.60%（多 213） | -0.42%（多 150） |
| 等效 BRAM36 tile 节省 | 0% | 4.35%（少 3.0 tiles） |
| 周期加速 `cycles_FP/cycles_SC` | 0.940× | 0.940× |
| SC 相对 FP 的首输入到末写入增幅 | 6.38% | 6.38% |

## 旧 robust-clipping 100 MHz post-route 资源与时序（legacy）

| 版本 | LUT primitives | FF primitives | DSP48E2 | RAMB36E2 | RAMB18E2 | 等效 BRAM36 | URAM | WNS (ns) | WHS (ns) | 推导 Fmax (MHz) | DRC | unrouted | 有效性 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SC production | 37,644 | 35,943 | 8 | 62 | 8 | 66.0 | 0 | 2.826 | 0.010 | 139.392 | 0 | 0 | VALID |
| FP16 native | 35,162 | 35,730 | 8 | 62 | 8 | 66.0 | 0 | 2.240 | 0.010 | 128.866 | 0 | 0 | VALID |
| FP32 native | 35,252 | 35,793 | 8 | 64 | 10 | 69.0 | 0 | 2.024 | 0.010 | 125.374 | 0 | 0 | VALID |

等效 BRAM36 按 `RAMB36E2 + RAMB18E2/2` 计算。主结论只使用共同 100 MHz。若把本次 OOC 推导 Fmax 与首输入到末写入周期相乘，128-bundle 吞吐分别约为 SC 91,801、FP16 90,282、FP32 87,836 bundle/s；这仅说明当前 SC 顶层有更大时序余量，不是板级 Fmax，也不能替代共同频率比较。

## 旧 robust-clipping synthetic 数值精度（legacy）

共同 reference 是 fold4 Hadamard S27 Q8.16 的实值输出。SC 按 `(q-zp)×code/2^shift` 重构；FP 按 `(q-zp)×IEEE scale` 重构。

| 版本 | max abs error | mean abs error | RMSE | cosine similarity |
|---|---:|---:|---:|---:|
| SC | 25.56245 | 0.22313 | 1.95233 | 0.999890415 |
| FP16 | 24.80464 | 0.22684 | 1.90164 | 0.999891868 |
| FP32 | 24.62341 | 0.22587 | 1.88931 | 0.999892484 |

当前 seed 中 SC 的 mean absolute error 略低，但 FP16/FP32 的 max absolute error、RMSE 和 cosine 略好。差异来自两种 scale/U8 映射，不足以概括模型级精度；三路仍需在真实 MLP trace 与完整 gate/up、SiLU×gate、down-projection 链上继续评估。

## 真实 MLP 输入与 frontend workload

正式补充捕获使用冻结的两个 input-ID 样本、同一 Llama-3.1-8B BF16
checkpoint 和 CUDA eager 前向，直接在 `gate_proj` pre-hook 保存层 0/15/31
的共同 MLP 输入，共 6 个 `128×4096` raw-BF16 tensor。新算出的 Gate/Up 与原
冻结 trace 比较时，层 0/15 bit-exact；层 31 的四个比较共保留 5,316,910 个
BF16 bit mismatch，最坏 normalized RMSE `4.8446746e-3`，最低 cosine
`0.999988273647`。这是真实非重现性记录，不删除、不写成 bit-exact：

```text
M08_MLP_INPUT_VERIFY_PASS files=6 samples=2 layers=3 checks=12 bit_mismatches=5316910 manifest_sha256=281da5fef1979b0f8c0199497cb0117948d3ce530e0aeeb094f4eae96c50b9e7
```

随后从 6 个输入 tensor 选择 16 个跨样本/层/token 的 row，完整生成 128 个
`16 rows × 32 lanes` bundle。三路共享相同 BF16→S24 输入和 production fold4
Hadamard，并由独立 Min/Max reference 生成相同 ideal-scale affine U8/zp。

- 65,536 lanes；S24 输入与 Hadamard saturation 均为 0；
- SC/FP zero-scale row 均为 0，`pre_quant_clip_lanes=0`；
- Hadamard reference、Min/Max reference、刺激生成脚本分别绑定独立哈希。

| 版本 | max abs error | mean abs error | RMSE | cosine similarity |
|---|---:|---:|---:|---:|
| SC | 1.3778687e-2 | 1.1526297e-3 | 1.5539701e-3 | 0.9999875746 |
| FP16 | 1.0299683e-2 | 1.1053316e-3 | 1.4622940e-3 | 0.9999889911 |
| FP32 | 1.0022521e-2 | 1.1049756e-3 | 1.4613934e-3 | 0.9999890048 |

完整临时重生成、依赖/格式/文件哈希与逐字节比较结果为：

```text
M08_TRACE_VECTOR_VERIFY_PASS files=8 rows=16 groups=128 lanes=32 source_tensors=6 manifest_sha256=aa2ba847b92230b3cb7bfe687e58377d965d3213a2d9df15ea46c37242c23cf2
```

runner/Tcl 已支持 `synthetic|trace` 数据目录，trace run 会把 capture、生成器、
verifier、production model、6 个 NPY 和全部正式 `.mem` 纳入输入哈希。当前尚未
启动 trace XSIM，因此不能把该软件 PASS 提升为硬件 PASS。

## 当前 Min/Max 版本功耗状态

当前不发布功耗数值。现存 routed DCP 对应旧 robust-clipping producer，而当前算法已改为 Hadamard 后直接归约 `max/min` 求 scale；当前 behavioral SAIF 与旧网表既不算法等价，也无法形成可信结构映射。必须先完成当前 Min/Max RTL 的 XSIM 与 post-route DCP，再按统一的 `100 MHz behavioral XSIM → DUT SAIF → routed DCP → report_power` 流程估算。旧硬件结果只能作为 legacy，不能填入当前功耗表。

## 旧 robust-clipping 证据路径（legacy）

- SC 无阻塞 XSIM：`raw/sc/xsim/20260909_034352_mlp_input_frontend_native_scale_continuous/`
- FP16 无阻塞 XSIM：`raw/fp16/xsim/20260909_034441_mlp_input_frontend_native_scale_continuous/`
- FP32 无阻塞 XSIM：`raw/fp32/xsim/20260909_034537_mlp_input_frontend_native_scale_continuous/`
- SC 周期背压 XSIM：`raw/sc/xsim/20260909_034631_mlp_input_frontend_native_scale_periodic_backpressure/`
- FP16 周期背压 XSIM：`raw/fp16/xsim/20260909_034709_mlp_input_frontend_native_scale_periodic_backpressure/`
- FP32 周期背压 XSIM：`raw/fp32/xsim/20260909_034758_mlp_input_frontend_native_scale_periodic_backpressure/`
- SC 正式 OOC：`raw/sc/ooc/20260909_034853_sc_mlp_input_frontend_native_scale_cache_100mhz/`
- FP16 正式 OOC：`raw/fp16/ooc/20260909_035849_fp16_mlp_input_frontend_native_scale_cache_100mhz/`
- FP32 正式 OOC：`raw/fp32/ooc/20260909_040919_fp32_mlp_input_frontend_native_scale_cache_100mhz/`

六份正式 XSIM 与三份正式 OOC 的目录级 `SHA256SUMS` 已逐项核验；FP16/FP32 OOC 的 `IP_XCI_SHA256SUMS` 也通过。三份 OOC 都包含完整顶层 post-route checkpoint、资源/时序/DRC/route-status 报告和输入哈希。

## 尚未完成

- 不少于 10 个固定 seed、伪随机长 backpressure、reset/clear 中断与非法协议定向测试；
- Llama-3.1-8B 真实 MLP 输入的三路 RTL replay，以及后续 gate/up、SiLU×gate、product requant 和 down-projection 的最终误差；
- producer-only/cache-only 资源拆分和功耗/energy per bundle；
- 非重叠 MLP chain 顶层与板级时序。

因此，旧数据只记录 robust-clipping 结构曾出现的负/混合结果；它不再支持当前 Min/Max producer 的资源或速度结论。Min/Max 三路 RTL replay 与 OOC 完成前，本模块状态保持 `RUNNING`。
