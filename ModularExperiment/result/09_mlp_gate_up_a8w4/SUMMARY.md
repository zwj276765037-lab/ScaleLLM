# 09 MLP Gate/Up A8W4 projection

> **Min/Max 修正状态（2026-09-10）**：Gate/Up 计算核结构不包含在线 A8
> producer，既有核级资源证据可保留；真实 trace 已用 M08 Min/Max payload 重生并
> 逐字节验证，manifest 为
> `d2837d2118ac00bf70519277c26dbb8e2ffa1c12d28f0588caa3e5fd13af5c63`。
> 该新 trace 的 RTL replay 尚待执行。

- 状态：`RUNNING`（三路 12-seed 功能/精度/吞吐、周期背压与 serial
  physical wrapper 已闭环；SC/FP16 100 MHz post-route 已通过；旧 FP32 OOC
  被外部终止并以 exit 143 归档；真实 pre-Gate/Up + checkpoint 软件 workload 已通过完整重生成
  验证，三路 trace XSIM 与当前源版本 SC continuous XSIM 待补跑）
- 工作单位：128 group32 后的一份 physical `16×12` Gate/Up S24 tile
- 比较版本：SC production packed dot + ScaleCode recovery；FP16/FP32 使用
  同一 packed integer dot，随后执行 int-to-FP、两次 native-scale multiply、
  rate-one FP accumulation 和公共 S24 输出转换
- 固定条件：Vivado 2025.2，`xcvu9p-flga2104-2L-e`，100 MHz，
  `HD.CLK_SRC=BUFGCE_X0Y0`，setup uncertainty 0.150 ns，hold uncertainty 0 ns

## 当前证据资格

| 版本 | 12-seed continuous | 周期背压 | serial physical wrapper | 100 MHz post-route | 当前资格 |
|---|---|---|---|---|---|
| SC | PASS，但最新 continuous 目录的当前输入哈希失配，待复跑 | PASS，当前输入/目录哈希通过 | PASS，当前输入/目录哈希通过 | PASS，全部门禁/哈希通过 | 功能结论需 continuous 复跑；资源结果 VALID |
| FP16 | PASS，全部哈希通过 | PASS，全部哈希通过 | PASS，全部哈希通过 | PASS，全部门禁/哈希通过 | VALID |
| FP32 | PASS，全部哈希通过 | PASS，全部哈希通过 | PASS，全部哈希通过 | FAIL（外部终止，exit 143） | 功能/周期 VALID；无正式资源结论 |

FP32 重新完成最终 route 前不得给出 SC-vs-FP32 的正式资源或 100 MHz 时序结论。

## 正式 workload 与数值精度

固定 workload 使用 seeds `36929`–`36940`，共 12 tiles、1,536 group32
transactions。每 tile 包含 128 groups、16 rows 和最多 12 columns，并覆盖
`0xfff`、`0x0ff`、`0x00f` masks。三路分别对各自 AMD-IP/ScaleCode 数值合同
做到 bit-exact、0 mismatch。

| 版本 | max abs error | mean abs error | RMSE | cosine similarity |
|---|---:|---:|---:|---:|
| SC | 9.7248703e-6 | 4.0819052e-6 | 4.8511496e-6 | 0.9999999999979416 |
| FP16 | 6.4530130e-3 | 8.9345574e-4 | 1.1971529e-3 | 0.9999999352367307 |
| FP32 | 7.8547746e-6 | 3.8299749e-6 | 4.4372854e-6 | 0.9999999999982782 |

这里比较的是 Gate/Up tile 对共同 exact-scale reference 的误差，不替代完整
SwiGLU、Down projection 或模型级精度。

## 真实 Gate/Up trace workload

正式 `data_trace/` 使用 M08 已验证的 pre-Gate/Up 捕获，不从 Gate/Up 输出反推
输入；Gate/Up 权重直接读取同一 checkpoint，并由 production V5 exporter 执行
normalized folded group32 W4 量化。workload 覆盖层 0/15/31 的 Gate 和 Up，
每 tile 使用来自两个样本的 16 个真实 token row，共 6 tiles、768 group32
transactions。前五个 tile 为 `0xfff`，最后一个 Up tile 对应 14336-channel 尾部
并使用真实 `0x00f` mask，共 1,024 个有效输出。

- 131,072 个有效 correlation，范围 `[-7384,6959]`；total shift `[26,37]`；
- `input_s24_saturation=0`、`hadamard_saturation=0`；
- `weight_preclamp_lanes=0`、三路最终 output saturation 均为 0；
- FP16 非有限 contribution 为 0，832 个 contribution 在半精度语义下为零。

| 版本 | max abs error | mean abs error | RMSE | cosine similarity |
|---|---:|---:|---:|---:|
| SC | 1.1227225e-5 | 4.6585791e-6 | 5.6047257e-6 | 0.999999999949 |
| FP16 | 2.1619191e-3 | 1.4443500e-4 | 2.7056551e-4 | 0.999999959415 |
| FP32 | 7.6657161e-6 | 3.9279462e-6 | 4.5015972e-6 | 0.999999999967 |

该表相对三路共同的量化 payload/decoded-scale FP64 reference。若连同实际输入
与 checkpoint 的 A8/W4 量化误差，SC/FP16/FP32 RMSE 分别为
`2.6677993e-2/2.6682038e-2/2.6677545e-2`，cosine 均约 `0.998826`。

完整 capture/checkpoint 哈希、临时重生成、文件 inventory、逐行格式与逐字节
比较结果为：

```text
M09_TRACE_VECTOR_VERIFY_PASS files=14 tiles=6 transactions=768 valid_outputs=1024 source_tensors=6 manifest_sha256=d2837d2118ac00bf70519277c26dbb8e2ffa1c12d28f0588caa3e5fd13af5c63
```

runner/Tcl 已支持 `synthetic|trace` 和 trace 的 `RUN_TILES=6`。当前没有三路
trace XSIM，因此以上仍是软件精度/输入范围证据，不进入硬件吞吐或资源表。

## 功能、吞吐与周期

### 无阻塞 12-tile workload

| 版本 | inputs / outputs | mismatch | input II min/max | output II min/max | 首输出 latency | 总周期 | 有效性 |
|---|---:|---:|---:|---:|---:|---:|---|
| SC | 1536 / 12 | 0 | 1 / 1 | 128 / 128 | 140 | 1549 | 待当前源 continuous 复跑后恢复正式资格 |
| FP16 | 1536 / 12 | 0 | 1 / 1 | 128 / 128 | 187 | 1596 | VALID |
| FP32 | 1536 / 12 | 0 | 1 / 1 | 128 / 128 | 186 | 1595 | VALID |

三路都达到相同的 group input II=1 和 tile output II=128。按已观察周期，SC
相对 FP16 的首输出和整批加速分别为 `187/140 = 1.3357×`、
`1596/1549 = 1.0303×`；SC 相对 FP32 的对应周期比为 `1.3286×`、
`1.0297×`。SC continuous 当前输入哈希复跑通过前，这些 SC 派生值保持阶段性
结论；周期背压证据已经使用当前输入并通过。

### 周期背压

| 版本 | mismatch | 首输出 latency | 总周期 | output stall cycles | stability checks | 有效性 |
|---|---:|---:|---:|---:|---:|---|
| SC | 0 | 143 | 1550 | 10 | 10 | VALID |
| FP16 | 0 | 187 | 1596 | 7 | 7 | VALID |
| FP32 | 0 | 186 | 1595 | 9 | 9 | VALID |

### 256-bit serial physical wrapper

| 版本 | load words/group | groups | result words | mismatch | 总周期 | stall/stability checks | 有效性 |
|---|---:|---:|---:|---:|---:|---:|---|
| SC | 26 | 128 | 18 | 0 | 3491 | 4 / 4 | VALID |
| FP16 | 26 | 128 | 18 | 0 | 3538 | 4 / 4 | VALID |
| FP32 | 28 | 128 | 18 | 0 | 3793 | 4 / 4 | VALID |

serial 周期包含窄口装载/排空开销，主要用于证明正式 OOC physical top 的接口、
payload/last 稳定性和完整 96-lane 算术，不替代上表的逻辑 tile 吞吐。

## 100 MHz post-route

| 版本 | LUT primitives | FF primitives | DSP48E2 | BRAM36/18 | URAM | WNS (ns) | WHS (ns) | DRC | unrouted | elapsed (s) | 有效性 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SC | 468,640 | 347,287 | 3,072 | 0 / 0 | 0 | +0.072 | +0.009 | 0 | 0 | 8,798 | VALID |
| FP16 | 442,767 | 560,119 | 3,840 | 0 / 0 | 0 | +0.143774 | +0.008816 | 0 | 0 | 13,266 | VALID |
| FP32 | — | — | — | — | — | — | — | — | — | FAIL（exit 143） | 不得引用 |

SC 相对 FP16 多 25,873 LUT primitives，即 LUT 节省为 `-5.843%`；少
212,832 FF（节省 `37.998%`）和 768 DSP48E2（节省 `20.000%`）。因此当前
结果是混合结果，不能写成所有资源均减少。

旧 FP32 run 在 aggressive physical optimization 中被外部终止，最终
`STATUS=FAIL`、`exit_status=143`。终止前 post-synth 为 491,036 CLB LUT、
640,744 CLB registers 和 4,224 DSP；post-place/replication 估计 WNS 为
`-1.471/-1.462 ns`，phys_opt 诊断曾改善到约 `-0.784 ns`。这些不完整数据只保留
为失败诊断，不进入正式资源表，也不能预测重跑后是否通过 100 MHz。

## 100 MHz post-route 功耗估算（sampled behavioral SAIF）

以下是“基于仿真波形的 post-route 估算”，不是板级实测。功耗 TB 与 routed serial physical wrapper 完全一致，重放 128 groups，输出一个完整 `16×12` tile，并施加周期性 backpressure。由于全 DUT 有 55,418 个仿真 scope、递归枚举无法在可接受时间内完成，本模块记录 wrapper/core 的全部边界对象，并在 96 条结构相同的 lane 中按 `row=0..11, pair=row mod 6` 均匀抽样 12 条 lane 的全部内部活动；其余综合网表节点由 Vivado 概率传播。因此两项均必须标为 `sampled_internal_12_of_96_lanes`，不能冒充 full-internal SAIF。

| 版本 | SAIF 时长 (µs) | 匹配网表节点 | 置信度 | 动态功耗 (W) | 器件静态 (W) | 总片上 (W) | 动态能量 (µJ/16×12 tile) | 高-X警告 | 资格 |
|---|---:|---:|---|---:|---:|---:|---:|---:|---|
| SC | 34.915 | 58,526 / 1,110,167（5.272%） | Medium | 2.614 | 2.507 | 5.121 | 91.268 | 10,304 | VALID sampled with X warning |
| FP16 | 35.385 | 60,502 / 1,333,785（4.536%） | Medium | 3.214 | 2.516 | 5.730 | 113.727 | 10,304 | diagnostic low coverage |
| FP32 | — | — | — | — | — | — | — | — | 无 routed DCP |

动态能量按 `dynamic_power × SAIF_duration` 计算，覆盖完整 serial tile。SC 精确匹配率超过 5% 门槛，可作为带采样和高-X限制的模块估算；FP16 虽然 Vivado 文本表把 4.536% 四舍五入显示为 5%，门禁使用精确 `matched/total`，因此仍正确降级为低覆盖 diagnostic，不能用来形成正式 SC-vs-FP16 功耗倍数结论。两路高-X警告主要来自采样 lane 内尚未写入的 result-memory 位，功能回归本身均为 0 mismatch。约 2.51 W 的器件静态值属于整颗 VU9P 模型，不是 Gate/Up 模块独占功耗。

## Production boundary 诊断

早期 distinct-tile regression 暴露 production shared dual-slice 的 drain
boundary 问题：最后一个 recovered contribution 可能依赖下一事务作隐式
flush，导致跨 tile tag/累加错位。正式实验使用
`m09_sc_a8w4_lane2_accum` 修正 tag、recovery pipeline 与 accumulator
boundary；数值叶子仍是 production packed dot 和 ScaleCode recovery。该修正
只证明实验顶层的独立事务语义，不宣称原 production wrapper 已经修复。

## 正式证据

- workload/精度：`experiment/09_mlp_gate_up_a8w4/data/manifest.json`
- SC 周期背压：
  `raw/sc/xsim/20260909_071008_gate_up_a8w4_native_fp_accum_periodic_backpressure/`
- FP16 continuous / 周期背压：
  `raw/fp16/xsim/20260909_073040_gate_up_a8w4_native_fp_accum_continuous/`、
  `raw/fp16/xsim/20260909_071127_gate_up_a8w4_native_fp_accum_periodic_backpressure/`
- FP32 continuous / 周期背压：
  `raw/fp32/xsim/20260909_065937_gate_up_a8w4_native_fp_accum_continuous/`、
  `raw/fp32/xsim/20260909_072020_gate_up_a8w4_native_fp_accum_periodic_backpressure/`
- serial wrappers：`raw/sc/xsim/20260909_074354_gate_up_a8w4_serial_ooc_wrapper_periodic_backpressure/`、
  `raw/fp16/xsim/20260909_074457_gate_up_a8w4_serial_ooc_wrapper_periodic_backpressure/`、
  `raw/fp32/xsim/20260909_075146_gate_up_a8w4_serial_ooc_wrapper_periodic_backpressure/`
- SC OOC：`raw/sc/ooc/20260909_080025_sc_gate_up_a8w4_native_scale_serial_ooc_100mhz/`
- FP16 OOC：`raw/fp16/ooc/20260909_102819_fp16_gate_up_a8w4_native_scale_serial_ooc_100mhz/`
- SC 功耗证据：`raw/sc/power/20260912_130003_saif_post_route_100mhz/`
- FP16 低覆盖功耗诊断：`raw/fp16/power/20260912_131638_saif_post_route_100mhz/`
- FP32 OOC（外部终止，`STATUS=FAIL`、exit 143）：
  `raw/fp32/ooc/20260909_141050_fp32_gate_up_a8w4_native_scale_serial_ooc_100mhz/`

以上标为 VALID 的目录均已核验 `STATUS`、exit status、目录级
`SHA256SUMS` 和当前 `INPUT_SHA256SUMS`。旧 SC continuous 目录
`20260909_062602...` 自身目录哈希通过，但 5 个当前输入哈希失配，已降级为
diagnostic。失配项为 `generate_vectors.py`、`manifest.json`、
`m09_fp_a8w4_lane2_accum.sv`、`expected_fp16_s24x16x12.mem` 和
`expected_fp32_s24x16x12.mem`；早期 mismatch/timeout/IP-golden 调试目录同样
保留，不进入主表。

## 尚未完成

1. Vivado 空闲后严格串行重跑 FP32 OOC，并检查 `WNS/WHS`、DRC、unrouted、exit status 及双重哈希；
2. 严格串行补跑 `./experiment/09_mlp_gate_up_a8w4/run_matched_xsim.sh sc 0`；
3. 写入三路最终资源、时序及 SC-vs-FP32 派生比较；
4. 补跑真实 Gate/Up 三路 trace XSIM、伪随机长背压与完整 MLP chain。

在 1–3 完成前，本页只支持 SC-vs-FP16 的正式资源混合结论，以及已通过当前
输入哈希的协议/精度子结论；模块状态保持 `RUNNING`。
