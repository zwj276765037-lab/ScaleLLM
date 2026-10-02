# 03 Attention RoPE

> **Min/Max 修正状态（2026-09-10）**：孤立 RoPE RTL/OOC 不依赖在线 A8
> 算法，原结构证据仍有效；boundary trace 已用原始 Group32 Min/Max 上游重生并
> 逐字节验证，manifest 为
> `0c39d93a305b96deccd0a144d0d41a0c63fe5a265d634ad0487fc8578618b3a5`。
> 新 boundary-inclusive RTL replay 仍待 Vivado 串行执行。

- 状态：`RUNNING`
- 工作单位：一对 Q/K 偶奇元素的旋转输出
- 主比较：S24 整数乘加/移位与 FP16/FP32 RoPE；boundary-inclusive 包含反量化
- 当前阶段：SC/FP16/FP32 operator-only 功能、同稳态吞吐和最终口径 OOC 已通过；synthetic 与真实 trace boundary 软件向量已完成，等待 boundary-inclusive XSIM/OOC
- 正式结果：operator-only 子结论有效；主结论仍待反量化边界成本

## Boundary-inclusive 准备进度

正式主口径已经冻结为一对输出元素的完整
`128 group32 correlation -> projection accumulation -> RoPE -> S24`，而不是把
单个 group contribution 或已经反量化的 S24/FP 输入冒充完整边界。共同输入、
SC/FP 数据流、FP32 六 bank matched-II accumulation/reduction 顺序及边界去重规则
见 `experiment/03_attention_rope/README.md`。

新的确定性软件 workload 已完成：12 个固定 seed、12 pairs、每 pair 128 groups，
共 1,536 transactions；覆盖 ScaleCode total shift 26/47、320 个 FP16 零 group
contribution 和一个定向饱和 pair。8 个 `.mem` 文件已由独立 verifier 检查行数、
位宽和 manifest 内 SHA-256：

```text
M03_BOUNDARY_VECTOR_VERIFY_PASS files=8 transactions=1536 pairs=12
```

manifest SHA-256：

```text
58cb665ff24ed88a6fe75ee89966e12c8ce3f8820d1ff77d3338a3073039b968
```

排除定向饱和 pair 后，相对未量化 FP64 projection+RoPE reference 的软件指标为：

| 版本 | max abs error | mean abs error | RMSE | cosine |
|---|---:|---:|---:|---:|
| SC | `1.5116695e-5` | `6.0408193e-6` | `7.6824853e-6` | `0.9999999999867435` |
| FP16 | `2.8153599e-2` | `6.5489013e-3` | `9.8931783e-3` | `0.9999769237546203` |
| FP32 | `7.5050291e-6` | `3.2493263e-6` | `4.0528729e-6` | `0.9999999999964452` |

SC/FP16/FP32 boundary RTL、统一 testbench、FP IP 生成 Tcl、XSIM/OOC 驱动和
输入哈希门禁已经创建；生成器/verifier Python 语法、两个 shell 驱动语法和
source-list 文件存在性通过静态检查。受大型 Vivado 严格串行约束，它们尚未
执行 Vivado elaboration。因而当前仍只有新主口径的向量/软件证据，没有可引用
的 boundary-inclusive XSIM、周期或 post-route 资源，不能替换下方
operator-only 硬件结论。

正式 Llama trace 原本只保存 projection 后的 `q/k_pre_rope` 与
`q/k_post_rope`，不能从中反解 128 组 correlation 和 scale metadata。现已用
冻结 input IDs 与同一 checkpoint 重放模型，捕获 6 个 projection-input BF16
tensor；layer 0/15 的新 Q/K 与冻结 trace bit-exact，layer 31 则保留 824,370 个
BF16 bit mismatch，最坏 normalized RMSE `3.9763205e-3`、最低 cosine
`0.999992094591`。补充捕获的独立门禁为：

```text
M03_PROJECTION_INPUT_VERIFY_PASS files=6 samples=2 layers=3 qk_checks=12 bit_mismatches=824370 manifest_sha256=53e54b7d88138a83ff1e56fec7653ccdd4206cc12382c7606c616764ccff2ff1
```

基于这些真实激活和 checkpoint Q/K 权重，production Hadamard+A8 与 V5 folded
W8 exporter 已生成 12 pairs × 128 groups = 1,536 transactions。18 个源 tensor、
坐标、checkpoint shard、generator/model 和 9 个数据文件均绑定 hash；完整临时
重生成与逐字节比较为：

```text
M03_TRACE_VECTOR_VERIFY_PASS files=10 pairs=12 transactions=1536 source_tensors=18 regenerated=1 manifest_sha256=0c39d93a305b96deccd0a144d0d41a0c63fe5a265d634ad0487fc8578618b3a5
```

真实数据中 correlation 为 `[-181274,143878]`、total shift 为 `[31,41]`，
S24/Hadamard/W8 均无饱和且 `pre_quant_clip_lanes=0`。FP16 的 S21 转换有
88 个 correlation 溢出为非有限值，12 pairs 中 11 个被污染，软件 golden 最终
有 19 个 projection 与 22 个 RoPE S24 饱和值。相对共同量化 FP64 的 RMSE 为：

| SC | FP16 | FP32 |
|---:|---:|---:|
| `6.9432013e-6` | `122.0997312` | `4.0256286e-6` |

该真实范围负面证据必须保留；当前 runner/Tcl 已支持 `synthetic|trace` 数据目录，
三路真实 trace XSIM 尚未启动。FP16 非有限值的
最终 Xilinx IP bit pattern 也必须等待 RTL replay，不能把软件结果冒充硬件 PASS。

| 版本 | 功能 | II/吞吐 | 资源/时序 | 结论资格 |
|---|---|---|---|---|
| SC | PASS：512 pairs，0 mismatch | 无阻塞片段 II=1；首输出 4 cycles；整批 635 cycles | 435 LUT，266 FF，4 DSP；WNS 8.113 ns，WHS 0.015 ns | VALID（operator-only 对照） |
| FP16 operator-only | PASS：512 pairs，0 mismatch | 无阻塞片段 II=1；首输出 32 cycles；整批 663 cycles | 894 LUT，1344 FF，8 DSP；WNS 8.226 ns，WHS 0.011 ns | VALID（operator-only） |
| FP32 operator-only | PASS：512 pairs，0 mismatch | 无阻塞片段 II=1；首输出 32 cycles；整批 663 cycles | 1336 LUT，1822 FF，12 DSP；WNS 7.323 ns，WHS 0.011 ns | VALID（operator-only） |

三种实现均能在无阻塞片段接受 1 pair/cycle，不需要复制 FP 核。FP 的整批周期比 SC 多 28 cycles，来自首结果流水延迟。

## Operator-only 有效结论

在相同 100 MHz、相同 steady-state pair/cycle 且全部 post-route 门禁通过时：

| 对比 | LUT 节省 | FF 节省 | DSP 节省 | 512-pair 周期加速 |
|---|---:|---:|---:|---:|
| SC 相对 FP16 | 51.34% | 80.21% | 50.00% | 1.044× |
| SC 相对 FP32 | 67.44% | 85.40% | 66.67% | 1.044× |

这里的 FP 已经采用对 ScaleCode 更有利的保守口径：直接从浮点输入开始，不计 int-to-float 和 scale multiply。即便如此，SC 的资源和短批延迟仍更低。该结论尚不能替代包含反量化边界的主结论。

## 100 MHz post-route 功耗估算（behavioral SAIF）

以下是“基于仿真波形的 post-route 估算”，不是板级实测。三路均重放同一 512-pair、周期性 backpressure workload；behavioral XSIM 在复位后预热 100 ns，再记录 DUT SAIF，并把活动导入上节对应 routed DCP 执行 Vivado 2025.2 `report_power`。

| 版本 | SAIF 时长 (µs) | 匹配网表节点 | 置信度 | 动态功耗 (W) | 器件静态 (W) | 总片上 (W) | 动态能量 (nJ/pair) | 资格 |
|---|---:|---:|---|---:|---:|---:|---:|---|
| SC | 6.325 | 348 / 1,299（26.79%） | Medium | 0.009 | 2.470 | 2.478 | 0.111 | VALID |
| FP16 | 6.605 | 386 / 2,941（13.12%） | High | 0.021 | 2.470 | 2.491 | 0.271 | VALID |
| FP32 | 6.605 | 506 / 4,471（11.32%） | Medium | 0.032 | 2.470 | 2.502 | 0.413 | VALID |

动态能量按 `dynamic_power × SAIF_duration / 512` 计算，包含当前背压与流水填充/排空。SC 相对 FP16/FP32 的动态功耗分别低约 57.1%/71.9%，每 pair 动态能量低约 59.0%/73.1%。三路均无高-X活动警告。约 2.47 W 的器件静态值是整颗 VU9P 的工艺/热模型估算，不是 RoPE 模块独占功耗；模块比较应使用动态功耗和动态能量。

## 已核验证据

- SC：`raw/sc/xsim/20260908_144011_matched_workload/`
- FP16：`raw/fp16/xsim/20260908_142803_operator_only/`
- FP32：`raw/fp32/xsim/20260908_142836_operator_only/`
- 最终口径 SC OOC：`raw/sc/ooc/20260908_152409_sc_rope_pair_100mhz/`
- 最终口径 FP16 OOC：`raw/fp16/ooc/20260908_151442_fp16_rope_operator_only_100mhz/`
- 最终口径 FP32 OOC：`raw/fp32/ooc/20260908_151958_fp32_rope_operator_only_100mhz/`
- 三路功耗证据：`raw/sc/power/20260912_102034_saif_post_route_100mhz/`、`raw/fp16/power/20260912_102234_saif_post_route_100mhz/`、`raw/fp32/power/20260912_102439_saif_post_route_100mhz/`
- `raw/fp16/xsim/20260908_142544_operator_only/` 是数据路径放置错误形成的失败诊断，不得引用。
- `raw/sc/ooc/20260908_145054_sc_rope_pair_100mhz/` 未设置 OOC `HD.CLK_SRC`，仅作为方法学诊断；FP16 的两次 -11 ps hold 失败同样保留为诊断。
