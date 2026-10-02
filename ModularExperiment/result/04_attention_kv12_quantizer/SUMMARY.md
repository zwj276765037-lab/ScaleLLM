# 04 Attention KV12 quantizer and K/V cache boundary

- 状态：`RUNNING`（S24 producer→K/V cache 的 boundary-inclusive 功能、周期背压和 100 MHz post-route 已闭环；真实 trace 软件 workload PASS；多 seed、trace RTL replay 和下游 QK/PV chain 待补）
- 工作单位：一个 batch 含 4 个 `32×S24 Q8.16` row；16 batches 共 64 records，K/V 各 32 records
- 比较边界：从共同的 `4×32×S24` 输入开始，到独立 K/V cache 的写入、读回与响应接口结束
- 固定条件：`xcvu9p-flga2104-2L-e`、Vivado 2025.2、100 MHz、`HD.CLK_SRC=BUFGCE_X0Y0`、setup uncertainty 0.150 ns、hold uncertainty 0 ns

## 当前结论

本模块得到一个必须保留的混合/负结果。ScaleCode 路径把每个 cache record 压缩为 `32×S12 + meta16 = 400 bits`，相对 direct FP16 的 512 bits 和 direct FP32 的 1024 bits 分别缩小 21.88% 和 60.94%。在相同 4096-depth、独立 K/V bank 的真实 post-route 顶层中，SC 使用 89 个等效 BRAM36 tile，较 FP16 的 114 个节省 21.93%，较 FP32 的 228 个节省 60.96%。

但是，当前 production `hap_kv12_quantizer4` 的除法量化实现不是速度或 LUT/FF 优势：SC 总周期为 3909，分别是 FP16 的 1.730×和 FP32 的 1.768×；SC 使用 12,329 LUT/9,985 FF，也显著多于 FP16 的 1,803/4,145 和 FP32 的 2,161/4,596。本模块不能写成 ScaleCode 全面占优；它支持的是“KV cache 容量/位宽显著下降”，同时暴露“现有 KV12 producer 需要优化”的工程瓶颈。

FP baseline 不是先运行 SC quantizer 再改格式。FP16/FP32 从相同 S24 输入原生反量化，并把每 lane 的 IEEE 值直接存入等深 K/V cache。baseline 使用一个真实共享 converter，以最小资源实现；它并未为了追平更慢的 SC producer 而复制转换器，因此资源数据是保守的 direct-FP 对照。

## 真实 Llama K/V trace 软件证据

`data_trace/` 已从正式冻结的 Llama-3.1-8B-Instruct trace 派生。固定选择 8 个
`(sample, layer, token, kv_head)` 坐标，覆盖 samples `{0,1}`、layers
`{0,15,31}`、全部 8 个 KV-head 编号和 12 个源 tensor。每个坐标依次生成一批
post-RoPE K 和一批 V，每批包含 head-dim 的四个连续 group32；总计 16 batches、
64 records、2,048 lanes，K/V 各 32 records。

BF16 先以 nearest-even 转成共同 S24 Q8.16。SC 从该边界逐完整 group32 调用
production `kv12_quantize_s24`；FP16/FP32 直接从共同 S24 转成 native IEEE lane，
没有先消费 SC 的 S12 输出。正式 manifest 绑定源 tensor file/payload hash、
production model、generator、坐标与全部数据文件。独立临时重生成和逐字节比较为：

```text
M04_TRACE_VECTOR_VERIFY_PASS files=7 batches=16 records=64 lanes=32 source_tensors=12 manifest_sha256=ac31392da0a79bfbc512be83ebcb4b0476ef2d16eb958ef7f33699ab6bcc0065
```

| 软件路径 | max error vs common S24 | RMSE vs common S24 | RMSE vs raw BF16 | cosine vs raw BF16 |
|---|---:|---:|---:|---:|
| SC KV12 | `6.7138672e-3` | `8.9869041e-4` | `8.9869062e-4` | `0.999999888780` |
| FP16 direct | `3.0517578e-5` | `6.7434958e-7` | `1.1960909e-6` | `0.9999999999996` |
| FP32 direct | `0` | `0` | `1.0301219e-6` | `0.9999999999997` |

S24 saturation、KV12 clip、保留 `-2048` 和 zero-scale record 均为 0。FP32
相对 raw BF16 的非零 RMSE 全部来自共同 BF16→S24 边界，而非 float conversion。
runner 已支持 `./experiment/04_attention_kv12_quantizer/run_boundary_xsim.sh
sc|fp16|fp32 0|1 trace` 并从 `HAP_DATA_DIR` 向 TB 传入正式目录；全局 preflight
已验证 shell/Tcl/source/data 合同。由于当前 M09 大型 OOC 尚在运行，M04 三路
trace XSIM 没有启动，因此本节仍只属于软件/输入证据，不能升级为硬件 PASS。

## 功能、吞吐和周期

确定性 workload 使用 seed `20260908`，包含零值、S24 边界、极小非零值、交替大值、常值、正态和重尾样本。三路均完成 16 batches、64 record 写入与 64 record 读回；每个 record 对各自 golden bit-exact，mismatch 和格式错误均为 0。SC 未产生保留码 `-2048`，本 workload 中也没有量化 clip。

| 版本 | record 格式 | record bits | batch II min/max | 首输入到末写入 | 末输入到末写入 | 无阻塞总周期 | 结果 |
|---|---|---:|---:|---:|---:|---:|---|
| SC production | `32×S12 + meta16` | 400 | 239 / 245 | 3,875 | 244 | 3,909 | PASS |
| FP16 direct cache | `32×IEEE FP16` | 512 | 139 / 139 | 2,225 | 139 | 2,259 | PASS |
| FP32 direct cache | `32×IEEE FP32` | 1,024 | 136 / 136 | 2,177 | 136 | 2,211 | PASS |

周期性 backpressure 覆盖 K/V 两个 response channel。SC、FP16、FP32 的总周期分别为 3919、2267、2219；三路在 stall 时均保持 `valid` 与 payload 稳定，仍为 0 mismatch、0 格式错误，FIFO/cache 协议没有溢出。

| 指标 | SC vs FP16 | SC vs FP32 |
|---|---:|---:|
| record 位宽节省 | 21.88%（少 112 bits） | 60.94%（少 624 bits） |
| 等效 BRAM36 tile 节省 | 21.93%（少 25） | 60.96%（少 139） |
| 无阻塞总周期比 `SC/FP` | 1.730×（多 1,650 cycles） | 1.768×（多 1,698 cycles） |
| 首输入到末写入周期比 `SC/FP` | 1.742×（多 1,650 cycles） | 1.780×（多 1,698 cycles） |
| LUT 变化 | 增加 583.80%（多 10,526） | 增加 470.52%（多 10,168） |
| FF 变化 | 增加 140.89%（多 5,840） | 增加 117.25%（多 5,389） |

这里没有把 producer 的 batch II 强行定义为“同吞吐”。SC 与单 converter FP baseline 的自然吞吐不同，而 FP 已经更快；复制 SC quantizer 或重构除法器后再做严格 matched-throughput producer 对比，属于后续优化实验。

## 100 MHz post-route 资源与时序

| 版本 | LUT primitives | FF primitives | DSP48E2 | RAMB36E2 | RAMB18E2 | 等效 BRAM36 tiles | URAM | WNS (ns) | WHS (ns) | 推导 Fmax (MHz) | DRC errors | unrouted | 有效性 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SC production producer+cache | 12,329 | 9,985 | 0 | 88 | 2 | 89 | 0 | 3.420 | 0.010 | 151.976 | 0 | 0 | VALID |
| FP16 converter+direct cache | 1,803 | 4,145 | 0 | 114 | 0 | 114 | 0 | 3.783 | 0.011 | 160.849 | 0 | 0 | VALID |
| FP32 converter+direct cache | 2,161 | 4,596 | 0 | 228 | 0 | 228 | 0 | 2.846 | 0.011 | 139.774 | 0 | 0 | VALID |

等效 BRAM36 tile 按 `RAMB36E2 + RAMB18E2/2` 计算。三份结果均来自完整 producer+双 bank cache 顶层的真实布局布线，不使用“单核面积×复制数”。推导 Fmax 只由本次 OOC critical period 得到，主比较仍固定为共同 100 MHz；未施加板级 I/O delay，不能替代系统时序。

SC LUT/FF 主要来自四路 production KV12 worker 的最大值检测、ratio/scale 搜索和整数除法控制；FP baseline 只有一个逐 lane 共享 fixed-to-float converter。FP cache 的 BRAM 随 record width 增长，且 FP32 恰为 FP16 的两倍；这与逻辑位宽和实现后的 228/114 tile 一致。

## 数值精度

共同 reference 是输入 S24 Q8.16 的实值。SC 以 `qvalue × scale_code / 2^scale_shift` 重构；FP16 使用 Xilinx half 的 FTZ 语义；FP32 对 Q8.16 输入可精确表示。

| 版本 | max abs error | mean abs error | RMSE | cosine similarity |
|---|---:|---:|---:|---:|
| SC | 0.2347412 | 0.00717357 | 0.0204735 | 0.9999989411 |
| FP16 | 0.0192871 | 0.000761375 | 0.00200907 | 0.9999999898 |
| FP32 | 0 | 0 | 0 | 1.0000000000 |

当前 seed 中 FP16/FP32 的误差低于 KV12 是符合格式精度预期的结果；本模块的目标是量化位宽、资源和周期权衡，不把 ScaleCode 描述为精度更高。

FP16 实现必须采用 `S24→FP32→FP16` 两级转换。早期失败证据显示，Xilinx Floating-Point IP 将当前 Q8.16 fixed 配置直接转换为 half 时，对 `+1 LSB` 等极小输入产生 `+Inf` 等异常格式。两级实现与软件 golden 一致；失败 run 被保留，但不进入正式数据表。

## 100 MHz post-route 功耗估算（behavioral SAIF）

以下是“基于仿真波形的 post-route 估算”，不是板级实测。三路均使用本页 16-batch、producer+双 bank cache、周期性 backpressure 回归；behavioral XSIM 预热 100 ns 后记录 DUT SAIF，再导入对应 routed DCP 执行 Vivado 2025.2 `report_power`。

| 版本 | SAIF 时长 (µs) | 匹配网表节点 | 置信度 | 动态功耗 (W) | 器件静态 (W) | 总片上 (W) | 动态能量 (nJ/4×32 batch) | 高-X警告 | 资格 |
|---|---:|---:|---|---:|---:|---:|---:|---:|---|
| SC | 39.065 | 8,918 / 32,924（27.09%） | Medium | 0.067 | 2.471 | 2.538 | 163.585 | 1,600 | VALID with X warning |
| FP16 | 22.565 | 4,515 / 14,883（30.34%） | Medium | 0.050 | 2.471 | 2.522 | 70.516 | 3,072 | VALID with X warning |
| FP32 | 22.085 | 5,505 / 20,462（26.90%） | Medium | 0.105 | 2.473 | 2.578 | 144.933 | 6,144 | VALID with X warning |

动态能量按 `dynamic_power × SAIF_duration / 16` 计算，包含 producer 延迟、cache 写回/读回及背压。SC 动态功耗比 FP32 低约 36.2%，但因完成同一 workload 用时更长，每 batch 动态能量反而比 FP16/FP32 高约 132.0%/12.9%；这是与前述 producer 周期负结果一致的混合结论。高-X警告来自回归未读出的 cache 存储输出，功能测试实际读回的 64 records 仍全部 bit-exact；因此数值可用于带限制的模块估算，但精度弱于无 X 的 SAIF。约 2.47 W 静态功耗属于整颗 VU9P 模型，不是该模块独占值。

## 正式证据

- SC 无阻塞 XSIM：`raw/sc/xsim/20260909_014504_kv_boundary_continuous/`
- FP16 无阻塞 XSIM：`raw/fp16/xsim/20260909_014534_kv_boundary_continuous/`
- FP32 无阻塞 XSIM：`raw/fp32/xsim/20260909_014615_kv_boundary_continuous/`
- SC 周期背压 XSIM：`raw/sc/xsim/20260909_014655_kv_boundary_periodic_backpressure/`
- FP16 周期背压 XSIM：`raw/fp16/xsim/20260909_014725_kv_boundary_periodic_backpressure/`
- FP32 周期背压 XSIM：`raw/fp32/xsim/20260909_014809_kv_boundary_periodic_backpressure/`
- SC 100 MHz OOC：`raw/sc/ooc/20260909_014911_sc_kv_producer_cache_boundary_100mhz/`
- FP16 100 MHz OOC：`raw/fp16/ooc/20260909_015524_fp16_kv_producer_cache_boundary_100mhz/`
- FP32 100 MHz OOC：`raw/fp32/ooc/20260909_020009_fp32_kv_producer_cache_boundary_100mhz/`
- 三路功耗证据：`raw/sc/power/20260912_104841_saif_post_route_100mhz/`、`raw/fp16/power/20260912_105142_saif_post_route_100mhz/`、`raw/fp32/power/20260912_105433_saif_post_route_100mhz/`

三份 OOC 均包含 `summary.json`、post-synth/post-route checkpoint、资源/时序/DRC/route-status 和输入哈希；FP 结果还保存 pre-synth IP Tcl、实际生成 XCI 及其哈希。六份正式 XSIM 与三份 OOC 的目录级 `SHA256SUMS` 已逐项核验通过。FP16 直接 fixed→half 的失败证据保留在 `raw/fp16/xsim/20260909_013944_kv_boundary_continuous/` 和 `20260909_014132_kv_boundary_continuous/`，用于解释实现选择。

## 尚未完成

- 不少于 10 个固定 seed、伪随机长 backpressure、非法地址/协议定向测试，以及已冻结 Llama-3.1-8B 真实 K/V workload 的三路 RTL replay；
- 分离 producer-only 与 cache-only 资源，以定位 KV12 除法器和 record width 的独立成本；
- 优化/复制 SC KV12 producer 后的严格同 batch/s 资源曲线，而不是以当前速度负结果代替；
- 将本边界接入 QK/PV，构建非重叠 attention chain，避免重复计算 converter/cache 边界；
- 板级 I/O 与实测功耗；当前仅有上述基于仿真波形的 post-route 估算。

因此，本页已经支持“ScaleCode KV12 显著降低 cache record width 与 BRAM，但当前 production quantizer 在 LUT/FF 和 producer 周期上劣于共享 direct-FP converter”的模块级结论。完整 attention chain 完成前，状态保持 `RUNNING`。
