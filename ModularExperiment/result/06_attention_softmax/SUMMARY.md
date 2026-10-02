# 06 Attention Softmax

- 状态：`RUNNING`（N=128 operator-only 同吞吐硬件子实验完成；12-seed 与真实 Llama trace 两套 N sweep/KL/top-1 软件向量 PASS；boundary-inclusive RTL/TB/trace runner 已静态预检，Vivado elaboration/XSIM/OOC 待执行）
- 工作单位：一个 row/head 的 128 个 U16 probability
- 比较版本：SC 整数/LUT Softmax、FP16 与 FP32 `sub/exp/add/div/convert`
- 统一实现条件：Vivado 2025.2，`xcvu9p-flga2104-2L-e`，100 MHz，`HD.CLK_SRC=BUFGCE_X0Y0`，setup uncertainty 0.150 ns，hold uncertainty 0 ns

## Boundary-inclusive 软件证据

正式 workload 使用 12 个固定 seed，覆盖 `N={128,112,64,32,16,1}`，共 72
rows、4,236 scores。8 个 `.mem` 保存共同 S20 Q6.14 score/mask、显式
FP16/FP32 转换输入和三路 U16 probability reference。独立 verifier 已使用
production `fixbit_v2.softmax_row_u16` 重算全部 SC golden，并核对记录宽度、数量、
生成器/production model 哈希和文件哈希：

`M06_BOUNDARY_VECTOR_VERIFY_PASS files=8 rows=72 scores=4236`

manifest SHA256：
`373f0e918dd55d660c8f130950b6bd29c98b3dd2a4562843633bdd367ac1ce17`。
二次生成的整个 `data_boundary/` 聚合哈希保持不变。

| 软件路径 | max abs probability error | mean abs | RMSE | mean/max sum error (U16 LSB) | mean KL | top-1 |
|---|---:|---:|---:|---:|---:|---:|
| SC | `1.2259532e-4` | `2.3619395e-6` | `8.6897949e-6` | `1.5833 / 16` | `1.3503885e-4` | 72/72 |
| FP16 | `1.3737456e-3` | `1.7524274e-5` | `9.1724396e-5` | `22.8194 / 160` | `1.1700430e-4` | 72/72 |
| FP32 | `1.5258789e-5` | `1.1451707e-6` | `2.4398614e-6` | `1.4444 / 16` | `1.1596017e-4` | 72/72 |

该表是相对稳定 FP64 Softmax 的软件参考。尤其 FP16 的 Xilinx exp/add/div 和
FTZ 行为必须由后续 XSIM 实测，表中数值不能替代硬件功能或精度结果。

### 真实 Llama trace 软件 workload

已从 `result/trace` 中冻结的真实 score tensor 派生第二套与相同 TB 几何完全
一致的 workload：2 samples × 3 layers（0/15/31）× 6 个 causal prefix
`N={128,112,64,32,16,1}` × 2 heads（0/17），仍为 72 rows、4,236 scores。
每一 row 取 `query_token=N-1` 和 keys `[0,N)`；真实 FP32 score 以 nearest-even
量化至共同 S20 Q6.14，未发生饱和。

`M06_TRACE_VECTOR_VERIFY_PASS files=10 rows=72 scores=4236 source_tensors=6
manifest_numeric_rel_tol=1e-13 manifest_sha256=6de3aedc9f6b686aaabf98b705559b0b423cf4ac7ecbe7ded0dcbb3352103731`

| 软件路径 | max abs probability error | mean abs | RMSE | mean KL | top-1 |
|---|---:|---:|---:|---:|---:|
| SC | `1.6002278e-4` | `6.1701865e-6` | `1.2244691e-5` | `1.1042537e-4` | 72/72 |
| FP16 | `1.0714611e-2` | `3.5540346e-5` | `3.5488395e-4` | `1.2625825e-4` | 72/72 |
| FP32 | `1.5258789e-5` | `3.8845549e-6` | `4.5178869e-6` | `1.2765266e-4` | 72/72 |

误差参考为量化前的真实 FP32 trace score 所定义的稳定 FP64 Softmax；单独记录
的 score Q6.14 量化 max/mean/RMSE 为 `3.0517578e-5 / 1.5164746e-5 /
1.7582842e-5`。`data_trace/trace_rows.csv` 保存每行的 sample/layer/query-token/
head/source-tensor hash。独立 verifier 在临时目录完整重生成，硬件 payload
逐字节比较；manifest 结构与非浮点字段严格相等，浮点归约指标允许 `1e-13`
相对容差，以屏蔽不同 BLAS 归约顺序造成的末位噪声。

相同 RTL/TB 已支持第三个 `trace` dataset 参数，待共享机器空闲后串行运行：

```bash
./experiment/06_attention_softmax/run_boundary_xsim.sh sc 0 trace
./experiment/06_attention_softmax/run_boundary_xsim.sh fp16 0 trace
./experiment/06_attention_softmax/run_boundary_xsim.sh fp32 0 trace
```

当前这些仍是软件/输入证据，尚无真实 trace boundary XSIM PASS。

## Boundary RTL/TB 准备状态

三路 boundary RTL/TB 与运行脚本已落盘并通过静态完整性检查。SC 从共同 S20
score/mask 直接进入 production Softmax；FP 在同一点计入 fixed-to-float、
FP16 narrow、保序 FIFO，并继续使用 x22/x26 同吞吐 farm。TB 覆盖全部 72 个
variable-N row、两种 backpressure 和五组 transaction/row counters。

FP16 的 128 U16 LSB 容差在首次 boundary XSIM 前冻结，依据是已通过的 N=128
operator-only 回归最大误差为 96 LSB；SC/FP32 仍要求 exact。自包含 FP IP Tcl
关闭了 OOC driver 的传递性哈希缺口。启动前审计还发现并修复了 XSIM runner
中会污染 Vivado argv 的字面补丁 `+`；增强后的统一 preflight 已再次 PASS，
且问题在首次 boundary Vivado 运行前关闭。以上只证明 RTL/TB/Tcl/路径已准备，
当前没有新增 boundary 硬件 PASS、周期、资源或时序结论。

## 同吞吐基线结构

FP 单核在 N=128 下远慢于 SC：FP16 最慢 row 为 9583 cycles，FP32 为 11447 cycles，而 SC 为 456 cycles。因此使用以下复制下界：

- FP16：`ceil(9583 / 456) = 22` 核；
- FP32：`ceil(11447 / 456) = 26` 核。

正式 FP 顶层不是单核资源乘复制数，而是真实包含 22/26 个 FP leaf、每核完整 128×U16 结果缓冲、core-busy 生命周期、输入 row 分配、顺序 FIFO、公共 1 probability/cycle 退休 mux 和 backpressure。每个 leaf 先独立完成并写满 row buffer，避免非当前 row 的核停在第一个 probability 而使复制失效。

## 96-row 功能、精度和性能

三种版本使用同源的 32-row N=128 workload 重放三次；FP 输入由同一 Q6.14 score 解码，输出均在 U16 probability 观察点比较。输出端使用相同周期性 backpressure。

| 版本 | 功能/精度 | 首输出延迟 (cycles) | row 间隔 min/mean/max (cycles) | 96-row 周期 |
|---|---|---:|---:|---:|
| SC | PASS，12288 probabilities，bit-exact，0 mismatch；all-masked 拒绝通过 | 301 | 444 / 444.232 / 449 | 42651 |
| FP16 x22 operator-only | PASS，协议 0 mismatch；MAE 0.785156 U16 LSB，max 96 LSB | 9088 | 148 / 399.737 / 6128 | 47211 |
| FP32 x26 operator-only | PASS，协议 0 mismatch；当前 U16 golden 下 MAE/max error=0 | 11392 | 148 / 390.884 / 7840 | 48674 |

FP16/FP32 的平均 row 间隔均小于 SC，故持续平均 row/s 达到并略高于 SC；但 FP farm 先计算、缓存、再突发退休，最大 row 间隔明显大于 SC。该 burstiness 和更高首结果延迟必须作为系统缓存/尾延迟代价保留，不能仅用平均吞吐掩盖。

相同 96-row batch 下，SC 相对 FP16 的周期加速为 `47211/42651 = 1.107×`，相对 FP32 为 `48674/42651 = 1.141×`。即使 FP farm 的稳态平均 row/s 略高，SC 仍因 301-cycle 首输出延迟而更快完成短/中批次。

## 100 MHz post-route 结果

| 版本 | LUT | FF | DSP48E2 | BRAM36 | WNS (ns) | WHS (ns) | 推导 Fmax (MHz) | DRC | Unrouted | 有效性 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SC | 762 | 426 | 2 | 0 | 5.793 | 0.010 | 237.699 | 0 | 0 | VALID |
| FP16 x22 operator-only | 75687 | 169230 | 176 | 0 | 1.721 | 0.010 | 120.783 | 0 | 0 | VALID |
| FP32 x26 operator-only | 159634 | 355198 | 182 | 0 | 1.424 | 0.010 | 116.602 | 0 | 0 | VALID |

结果缓冲由综合器映射为 LUT/寄存器/SRL 资源，最终顶层未使用 RAMB36E2/RAMB18E2；表中 LUT/FF 已包含这些缓冲，不是漏计 cache。

## Operator-only 有效子结论

| 对比 | LUT 节省 | FF 节省 | DSP 节省 | 96-row 周期加速 |
|---|---:|---:|---:|---:|
| SC 相对 FP16 x22 | 98.99%（少 74925） | 99.75%（少 168804） | 98.86%（少 174） | 1.107× |
| SC 相对 FP32 x26 | 99.52%（少 158872） | 99.88%（少 354772） | 98.90%（少 180） | 1.141× |

在 N=128、相同持续平均 row/s、真实复制/缓存/调度顶层和全部 post-route 门禁通过的条件下，SC Softmax 显著减少 LUT、FF、DSP，并降低首结果与 96-row 整批延迟。该结果是 operator-only 的保守对比：FP 直接接收已反量化 score，尚未承担 score 边界的 int-to-float/scale 成本；因此它是有效子结论，但不能替代完整 Attention 链的 boundary-inclusive 主结论。

## 100 MHz post-route 功耗估算（behavioral SAIF）

以下是“基于仿真波形的 post-route 估算”，不是板级实测。三路使用本页同一 96-row、N=128、周期性 backpressure workload；behavioral XSIM 预热 100 ns 后记录 DUT SAIF，再导入相应 routed DCP 执行 Vivado 2025.2 `report_power`。

| 版本 | SAIF 时长 (µs) | 匹配网表节点 | 置信度 | 动态功耗 (W) | 器件静态 (W) | 总片上 (W) | 动态能量 (nJ/row) | 资格 |
|---|---:|---:|---|---:|---:|---:|---:|---|
| SC | 427.775 | 530 / 1,644（32.24%） | High | 0.003 | 2.470 | 2.473 | 13.368 | VALID |
| FP16 x22 | 472.085 | 6,165 / 285,561（2.16%） | Medium | 0.408 | 2.475 | 2.883 | 2,006.361 | diagnostic low coverage |
| FP32 x26 | 486.715 | 10,593 / 610,946（1.73%） | Medium | 1.250 | 2.487 | 3.737 | 6,337.435 | diagnostic low coverage |

动态能量按 `dynamic_power × SAIF_duration / 96` 计算。SC 的 SAIF 覆盖充分且无高-X警告，可作为正式模块估算；FP16/FP32 的 behavioral floating-point IP 内部名称不能充分映射到综合后的 primitive，匹配率仅 2.16%/1.73%，低于 5% 门槛，所以两项数值只保留为低覆盖近似，不能据此形成正式 SC-vs-FP 功耗倍数结论。约 2.47 W 静态值属于整颗 VU9P 模型，不是 Softmax 独占功耗。

## 已核验证据

- SC 96-row XSIM：`raw/sc/xsim/20260908_181720_long_96_rows/`
- FP16 x22 XSIM：`raw/fp16/xsim/20260908_181755_operator_only_x22/`
- FP32 x26 XSIM：`raw/fp32/xsim/20260908_182041_operator_only_x26/`
- SC OOC：`raw/sc/ooc/20260908_163651_sc_softmax_row128_100mhz/`
- FP16 x22 OOC：`raw/fp16/ooc/20260908_164048_fp16_softmax_operator_only_x22_100mhz/`
- FP32 x26 OOC：`raw/fp32/ooc/20260908_170913_fp32_softmax_operator_only_x26_100mhz/`
- 功耗证据：SC `raw/sc/power/20260912_112607_saif_post_route_100mhz/`；FP16/FP32 低覆盖诊断分别为 `raw/fp16/power/20260912_112800_saif_post_route_100mhz/`、`raw/fp32/power/20260912_113613_saif_post_route_100mhz/`

以上三个 XSIM 和三个 OOC 目录均为 `STATUS=PASS`；OOC 均为 `valid=1`，且全部目录的 `SHA256SUMS` 已核验。

## 单核诊断与排除结果

- FP16 单核：`raw/fp16/xsim/20260908_144130_operator_only_single_core/`，306651 cycles/32 rows，不能用于同吞吐面积结论。
- FP32 单核：`raw/fp32/xsim/20260908_144231_operator_only_single_core/`，366147 cycles/32 rows，不能用于同吞吐面积结论。
- `raw/fp16/xsim/20260908_161305_operator_only_x22/`、`161523`、`161647`、`161814`：replicated TB 的 time-0 派生索引未初始化，使首个 mask 为 `X`，均保留为失败诊断。
- `raw/fp16/xsim/20260908_161935_operator_only_x22/`：暴露初版顶层缺少 per-core 输出 row buffer，公共输出仍被单核逐 probability 延迟串行化；已中止并标为 `FAIL`。
- `raw/fp16/xsim/20260908_162757_operator_only_x22/` 与 `raw/fp32/xsim/20260908_163046_operator_only_x26/`：缓冲架构的首次通过结果；正式引用后续增加 mean interval 字段的 96-row 复测目录。
