# ScaleCode 模块化硬件对比实验总报告

> **Min/Max 更正进度（2026-09-10）**：M01/M02/M03/M08/M09/M11/M12 的正式软件
> trace 已按原始 Group32 Min/Max 生成并通过依赖哈希与逐字节校验；M02 的最终
> FP16 非有限值语义探针与 SC 18-tile 周期背压 RTL replay 均已 PASS。M12 SC
> 三层全尺寸 trace 已 PASS；M12 FP16 layer-0 首跑以 200 个 tile 数值 mismatch
> 结束，已精确定位为实验 golden 缺少 AMD minimum-normal underflow 边界语义，
> 修正后的 synthetic/三层 trace golden 已完成双重重生与完整性复核，当前 trace
> manifest 为 `4074940a6004d6487ef19705caf70bcf542e7c65fccce25d8117831e8883945c`；
> FP16 RTL 重跑尚未执行。M01/M08/
> M11 的旧量化器 XSIM/OOC 仍为 `robust-clipping legacy`，不能据此签核新算法的
> 资源、周期或 bit-exact；M04–M07/M10 的孤立算子结构结果不受本次量化器替换影响。

## 当前状态

`RUNNING` — 本页是当前证据快照，不是完整 Attention/MLP 链最终结论。

> **Recovery 阵列新增实验（2026-09-12）**：已新增 M13 recovery-only
> 96-lane 对比，正式边界为 S17 dot+scale metadata 到 S36 Q12.24
> contribution，排除 dot 与 accumulator。SC/FP16/FP32 各 786,432 个结果均
> 0 mismatch，三路实测 II=1，即共同 192 contribution/cycle；首输出延迟分别
> 为 3/29/28 cycle。OOC 与 post-route timing-netlist SAIF 功耗因机器存在其他
> Vivado/XSIM 任务而等待，当前没有资源或功耗数字。详见
> `result/13_scalecode_fp_recovery_array/SUMMARY.md`。

截至 2026-09-10，00–12 共 13 个模块中：

- 11 个模块已有 SC、FP16、FP32 三路功能与 100 MHz post-route 有效子实验；
- 其中 6 个模块已有三路 boundary-inclusive 数据，5 个模块当前只有
  operator-only 数据；
- 09 Gate/Up 已完成三路功能和 SC/FP16 post-route；旧 FP32 OOC 被外部终止，
  `STATUS=FAIL`、exit 143，等待 Vivado 空闲后串行重跑；真实
  Gate/Up 软件 workload 已结合 pre-Gate/Up 捕获与 checkpoint 权重完成；
- 01 Attention frontend 已从真实 projection input 派生 128-bundle 软件 workload
  并通过完整重生成验证，三路 trace XSIM 尚未执行；
- 02 Attention projection 已冻结 25-case AMD FP16 非有限语义，正式生成并验证
  18-tile Q/K/V Min/Max trace，SC 周期背压 XSIM 0 mismatch；其余 trace 模式待补；
- 08 MLP frontend 已补充捕获真实 pre-Gate/Up 输入并派生 128-bundle 软件
  workload，三路 trace XSIM 尚未执行；
- 12 Down 已完成 synthetic 及三层真实 trace+checkpoint 的 full-shape 向量与
  软件精度；SC 三层 full-shape XSIM 均 0 mismatch，FP16 修正前 layer-0 FAIL
  已精确解释，修正后 golden 已冻结，RTL 重跑待执行。

所有模块继续保持 `RUNNING`，因为 Goal 还要求 boundary-inclusive 主口径、
不少于 10 seeds、shape/flow-control sweep、真实 trace、Attention/MLP 链顶层
和最终跨模块审计；已有有效子实验不等于整个实验完成。

## 正式证据门禁

主表只允许纳入同时满足以下条件的结果：

1. 使用相同 workload/common observation point，三路功能、协议和数值检查通过；
2. FP baseline 的持续输出吞吐不低于对应 SC production 锚点；
3. 使用 Vivado 2025.2、`xcvu9p-flga2104-2L-e`、100 MHz、
   `HD.CLK_SRC=BUFGCE_X0Y0`、0.150 ns setup uncertainty、0 ns hold
   uncertainty 完成真实顶层 post-route；
4. `WNS >= 0`、`WHS >= 0`、DRC errors=0、unrouted nets=0；
5. `STATUS`、exit status、输入哈希、生成 IP 哈希（适用时）及目录级
   `SHA256SUMS` 均通过。

仅 XSIM、仅 synthesis estimate、负时序、低吞吐 FP、输入哈希漂移或失败调试
目录均保留为 diagnostic，不进入资源/速度结论。

可用以下只读审计重新分类全部 raw run：

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
./tools/scripts/audit_raw_results.sh
```

当前扫描 203 份 run，得到 57 份 `VALID_CANDIDATE`、0 份 `RUNNING` 和
146 份 `INVALID_OR_DIAGNOSTIC`。后续 source/TB/provenance 更新已使部分旧 XSIM 和早期
M01 8-divider 诊断 OOC 的当前输入哈希失配；摘要选定的 M01 3-lane FP16/FP32
正式 OOC 当前输入哈希仍全部 PASS。历史/诊断测量继续保留但不进入主表。
2026-09-11 已在最终 M12 mini verifier 与报告计数更正后重新执行完整
preflight、mini 独立重生和 raw audit；上述计数保持不变，且没有
ModularExperiment `RUNNING` 目录。
`VALID_CANDIDATE` 只表示通用门禁通过；是否为
同吞吐最小 baseline、正式 workload 或最终选定 run，仍以模块 `SUMMARY.md`
中的明确证据路径为准。

通用 OOC runner 已对后续新 run 加强 current-input provenance：
`INPUT_SHA256SUMS` 现在同时绑定 OOC shell/Tcl、模块 launcher、source list、
generated-IP pre-synth Tcl 和全部 RTL。该改动不追溯改写历史目录；旧 run 仍按其
冻结证据分类，新 run 若 driver/IP 配置漂移会被统一 raw audit 自动拒绝。

01–12 的 boundary/trace 启动前只读门禁现可统一复跑：

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
./tools/scripts/audit_boundary_preflight.sh
```

当前结果为 `BOUNDARY_PREFLIGHT_PASS modules=12 shells=55 tcl=45
source_lists=43 sources=187 sv=69 inline_ip_drivers=4`。M02 静态合同现为
`semantic_maps=3 formal_trace=1`；缺少合格映射时的 fail-closed 已实测，最终映射、
正式向量与 SC 周期背压 RTL replay 均已 PASS。其余十一个模块执行冻结向量 verifier，
其中 M01/M03/M04/M05/M06/M07/M08/M09/M10/M11 还执行真实 trace 完整性或临时重生成/逐字节 verifier；
四份自包含 FP driver 还会与原始 operator/boundary IP
配置做逐字 prefix/concat 比较，防止复制后静默漂移。
M12 另外执行三层真实 trace/checkpoint workload 完整性核验以及
source/top/payload/IP-latency 静态合同核验；全量 257 MiB 临时重生成/逐字节
比较已单独 PASS。当前静态合同为
`M12_STATIC_CONTRACT_VERIFY_PASS source_entries=28 modules=21 tops=6
ip_latencies=7 payload_variants=3 trace_layers=3 nonzero_mini=1 wave_ab=1
vivado_guard=1`。
03/05/06/07/10 的统一 top-contract 核验当前为
`BOUNDARY_TOP_CONTRACT_VERIFY_PASS modules=5 source_lists=12
source_entries=42 ooc_tops=15 tb_tops=5 farm_bindings=4`，确保 runner 中的三路
top 实际存在于对应 hashed source list，并保持 Softmax x22/x26、PV x19/x21
复制结构的真实 RTL 绑定。
门禁现还会拒绝 shell 中可通过 `bash -n`、但会污染 Vivado argv 的字面补丁
`+`。该检查曾在执行前发现并修复 06/07 boundary XSIM runner 的此类残留；
修复后完整 preflight 再次 PASS，未产生伪硬件 run。
该门禁只证明脚本/Tcl/source/RTL 结构与软件数据完整，不能代替 Vivado
elaboration、XSIM 或 post-route。

## 模块证据矩阵

| 模块 | 当前三路硬件证据 | 成本口径 | 当前可支持的结论 | 主要缺口 |
|---|---|---|---|---|
| 00 Scale Apply | XSIM + OOC + 三路 SAIF power PASS | A8W8 boundary-inclusive | 有效子结论 | A8W4 FP、多 seed/无阻塞精度 |
| 01 Attention Input Hadamard+A8 | Min/Max synthetic/trace 软件向量 PASS；旧 robust XSIM/OOC 仅作 legacy | producer/cache boundary-inclusive | 仅当前软件精度；暂无 Min/Max 硬件资源/周期结论 | Min/Max synthetic/trace RTL replay 与 OOC、多 seed、长背压 |
| 02 Attention A8W8 Projection | 历史 XSIM + 当前 OOC PASS；SC power 仅高-X diagnostic；25-case FP16 语义探针和 SC 18-tile Q/K/V 周期背压 XSIM PASS | 单 tile boundary-inclusive | OOC资源/时序子结论；Min/Max SC trace 0 mismatch | 当前源码 synthetic、SC continuous、FP16/FP32 trace、Wo/frontend/chain |
| 03 RoPE | operator-only XSIM/OOC/三路 SAIF power PASS；synthetic 与真实 trace boundary 软件向量 PASS、RTL待 elaboration | operator-only | 有效子结论；新增真实范围负证据 | projection→RoPE boundary/trace XSIM/OOC |
| 04 KV12 Quantizer/Cache | XSIM + OOC + 三路 SAIF power PASS（带 cache X 限制）；真实 K/V trace软件向量 PASS | producer+cache boundary-inclusive | 有效混合结论；新增 trace 精度 | 多 seed、trace RTL replay、QK/PV chain |
| 05 QK Score | operator-only XSIM/OOC/三路 SAIF power PASS；boundary 12-seed 与真实 trace 两套向量 PASS、三路逻辑/physical RTL与TB待 elaboration | operator-only | 有效子结论；新增软件/trace 精度 | 两套 boundary full XSIM、serial XSIM 与 OOC |
| 06 Softmax | N=128 XSIM + replicated OOC PASS；SC power PASS，FP power 低覆盖 diagnostic；boundary 两套 N-sweep 软件向量 PASS | N=128 operator-only | 有效子结论；新增软件/trace 精度 | 两套 score boundary XSIM/OOC |
| 07 PV | N=128 XSIM + replicated OOC + 三路 SAIF power PASS；boundary 两套 N-sweep 软件向量 PASS | N=128 operator-only | 有效子结论；新增软件/trace 精度 | 两套 probability/V boundary XSIM/OOC |
| 08 MLP Input Hadamard+A8 | Min/Max synthetic/trace 软件向量 PASS；旧 robust XSIM/OOC 仅作 legacy | producer/cache boundary-inclusive | 仅当前软件精度；暂无 Min/Max 硬件资源/周期结论 | Min/Max synthetic/trace RTL replay 与 OOC、多 seed、长背压 |
| 09 Gate/Up A8W4 | 三路 XSIM；SC/FP16 OOC PASS；SC sampled power PASS、FP16 power 低覆盖 diagnostic；旧 FP32 OOC 外部终止 | boundary-inclusive | SC-vs-FP16 资源混合结论；新增 trace 精度 | FP32 OOC 重跑、SC continuous hash 复跑、trace RTL replay |
| 10 SiLU×Up | XSIM + OOC PASS；SC power PASS、FP power 低覆盖 diagnostic；boundary 两套软件向量 PASS | operator-only | 有效子结论；新增软件/trace 精度 | 两套 Gate/Up→SiLU boundary XSIM/OOC |
| 11 Product Hadamard+A8 | Min/Max synthetic/trace 软件向量 PASS；旧 robust XSIM/OOC 仅作 legacy | producer boundary-inclusive | 仅当前软件精度；暂无 Min/Max 硬件资源/周期结论 | Min/Max divider/三路 RTL replay 与 OOC、多 seed、MLP chain |
| 12 Down A8W4 | SC 三层 full trace 数值/协议 PASS、FP16 修正引起通用 provenance 哈希漂移而待刷新；FP16 修正前 layer-0 为已解释的 diagnostic FAIL，修正后 golden PASS | full-shape boundary-inclusive 设计 | 已解释的 SC RTL 子证据；无 FP/三路资源结论 | 非零小型 A/B 后刷新 SC、重跑 FP16/FP32 full/trace XSIM 与三路 OOC |
| 13 Recovery-only array96 | 三路 4,096-cycle XSIM PASS，均 II=1、0 mismatch；OOC/power 待执行 | S17+native metadata→S36 Q12.24，排除 dot/accumulator | 已确认等吞吐与真实 pipeline latency | 三路串行 OOC、post-route timing-netlist SAIF |

详细原始路径、排除项与复现命令见各模块 `SUMMARY.md` 和
`experiment/<module>/README.md`。

## 当前资源与周期观察

下表只列每个模块最重要的阶段性结果。百分比均为 SC 相对 FP 的节省；负数
表示 SC 使用更多资源。速度为共同 100 MHz、共同 workload 的
`cycles_FP/cycles_SC`。

| 模块/口径 | SC vs FP16 | SC vs FP32 | 解释 |
|---|---|---|---|
| 00 A8W8 scale apply boundary | LUT 22.66%、FF 50.24%、DSP 5.56%；批次 1.064× | LUT 29.02%、FF 58.87%、DSP 15.00%；批次 1.045× | scale application 微边界为正 |
| 01 Attention input producer/cache（旧 robust legacy） | LUT -7.39%、周期 0.9285× | LUT -7.33%、周期 0.9285× | 不得外推为 Min/Max producer 结论 |
| 02 A8W8 projection 单 tile boundary | LUT 20.15%、FF 49.95%、DSP 5.56%；1.101× | LUT 26.09%、FF 58.60%、DSP 15.00%；1.075× | 有效正子结论 |
| 03 RoPE operator-only | LUT 51.34%、FF 80.21%、DSP 50.00%；1.044× | LUT 67.44%、FF 85.40%、DSP 66.67%；1.044× | 尚未计 projection scale boundary |
| 04 KV12 producer+cache | LUT -583.80%；周期 0.578× | LUT -470.52%；周期 0.566× | SC record 400b，少于 512/1024b；BRAM 显著省，但现有 quantizer 逻辑/周期差 |
| 05 QK operator-only | LUT 65.29%、FF 56.87%、DSP 66.67%；1.188× | LUT 63.18%、FF 62.23%、DSP 75.00%；1.176× | 已免费给 FP 反量化输入 |
| 06 Softmax N=128 operator-only | LUT 98.99%、FF 99.75%、DSP 98.86%；1.107× | LUT 99.52%、FF 99.88%、DSP 98.90%；1.141× | FP16×22、FP32×26 为满足持续 row/s 的最小实测复制数 |
| 07 PV N=128 operator-only | LUT 95.04%、FF 98.97%、DSP 96.49%；1.153× | LUT 96.86%、FF 99.27%、DSP 97.62%；1.172× | FP16×19、FP32×21；FP 另用 76/168 BRAM36 |
| 08 MLP input producer/cache（旧 robust legacy） | LUT -7.06%、周期 0.940× | LUT -6.79%、周期 0.940× | 不得外推为 Min/Max producer 结论 |
| 09 Gate/Up boundary（阶段性） | LUT -5.843%、FF 37.998%、DSP 20.000%；1.0303× | 资源待 FP32 route；功能周期 1.0297× | SC-vs-FP16 是混合结果 |
| 10 SiLU×Up operator-only x2 | LUT 94.10%、FF 98.90%、DSP 60.00%；1.096× | LUT 96.76%、FF 99.32%、DSP 60.00%；1.133× | SC 代价为多 12 BRAM36 LUT-ROM |
| 11 Product Hadamard+A8 physical top（旧 robust legacy） | LUT 10.99%、FF 6.12%；周期 0.9567× | LUT 13.17%、FF 6.49%；周期 0.9567× | 不得外推为 Min/Max producer 结论 |

这些数据不支持“ScaleCode 在所有模块都更省、更快”的笼统说法。当前更精确的
观察是：

- scale apply、projection 以及 RoPE/QK/Softmax/PV/SiLU 后续算术显示明显的
  整数/移位优势，尤其在 FP 单核吞吐不足、必须真实复制时；
- scale producer/quantizer 本身可能抵消收益；目前仅 04 的现有 producer 结果不因
  本次 A8 Min/Max 更正失效，01/08 必须等待新 RTL/OOC 后再判断；
- 09 的资源与周期方向不同；11 的同类旧观察属于 robust legacy，必须等待
  Min/Max RTL/OOC 后重签；
- 只有把真实边界计一次并综合完整 Attention/MLP 链，才能判断净系统收益。

## 100 MHz post-route 功耗快照（behavioral SAIF）

以下全部是“基于仿真波形的 post-route 估算”，不是板级实测。统一流程为：100 MHz behavioral XSIM 重放模块功能 workload，复位后预热 100 ns，记录 DUT SAIF，导入与该 DUT 对应的 routed DCP，再用 Vivado 2025.2 `report_power`。动态能量包含该次 workload 的背压和流水填充/排空。约 2.47–2.52 W 的静态值是整颗 VU9P 在默认工艺/热环境下的器件模型值，不是各模块独占功耗，因此总表只用动态功耗和动态能量比较。

| 模块/工作单位 | SC 动态 W / 能量 | FP16 动态 W / 能量 | FP32 动态 W / 能量 | 资格与限制 |
|---|---:|---:|---:|---|
| 00 Scale Apply / group32 | 0.028 / 0.962 nJ | 0.028 / 1.023 nJ | 0.035 / 1.257 nJ | 三路 VALID |
| 02 A8W8 Projection / 8×16 tile | 5.503 / 14.555 µJ | — | — | SC 有 9,225 条高-X，仅 diagnostic |
| 03 RoPE / pair | 0.009 / 0.111 nJ | 0.021 / 0.271 nJ | 0.032 / 0.413 nJ | 三路 VALID |
| 04 KV12+Cache / 4×32 batch | 0.067 / 163.585 nJ | 0.050 / 70.516 nJ | 0.105 / 144.933 nJ | 三路 VALID with cache X warning |
| 05 QK / score | 0.077 / 6.421 nJ | 0.149 / 14.759 nJ | 0.177 / 17.311 nJ | 三路 VALID |
| 06 Softmax / N=128 row | 0.003 / 13.368 nJ | 0.408 / 2,006.361 nJ | 1.250 / 6,337.435 nJ | 仅 SC VALID；FP 匹配率 2.16%/1.73%，diagnostic |
| 07 PV / row-tile16 | 0.142 / 188.039 nJ | 0.828 / 1,264.296 nJ | 1.408 / 2,184.380 nJ | 三路 VALID |
| 09 Gate/Up / 16×12 tile | 2.614 / 91.268 µJ | 3.214 / 113.727 µJ | — | SC 为 12/96 lane sampled + X warning；FP16 匹配率 4.536%，diagnostic；FP32 无 DCP |
| 10 SiLU×Up x2 / product | 0.018 / 0.112 nJ | 0.138 / 0.872 nJ | 0.268 / 1.701 nJ | 仅 SC VALID；FP 匹配率 1.50%/1.31%，diagnostic |

M01/M08/M11 的 routed DCP 仍对应旧 clipping/robust producer，与当前 Min/Max 算法不一致，禁止用来填当前功耗；M12 尚无 routed DCP。M06/M10 的 FP 和 M09 FP16 保留数值是为了暴露估算范围，但不满足 5% 精确 SAIF 覆盖门禁，不得写成正式功耗优势。完整机器可读字段、原始路径、精确匹配率、置信度、组件功耗、SAIF 时长与警告数见 `result/power_summary.csv` 和 `result/power_summary.json`。

## 09 Gate/Up 当前运行

三路 12-seed、1,536-group/12-tile XSIM 均为 0 mismatch、input II=1、
无阻塞 output II=128。RMSE 为：

| SC | FP16 | FP32 |
|---:|---:|---:|
| 4.8511496e-6 | 1.1971529e-3 | 4.4372854e-6 |

SC post-route 为 468,640 LUT、347,287 FF、3,072 DSP，
WNS/WHS=`+0.072/+0.009 ns`；FP16 为 442,767 LUT、560,119 FF、3,840
DSP，WNS/WHS=`+0.143774/+0.008816 ns`。二者 DRC/unrouted 均为 0，目录和
当前输入哈希通过。

旧 FP32 OOC 在 `phys_opt_design -directive AggressiveExplore` 中被外部终止，
`STATUS=FAIL`、exit 143。终止前仅有 post-synth 491,036 CLB LUT、640,744
registers、4,224 DSP 和未收敛的负 WNS 诊断；这些不完整数据不能进入正式表。

## 12 Down 当前证据

正式 workload 为 12 seeds、448 groups × 342 tiles = 153,216 transactions，
有效输出 65,536 个 S24，tail mask `0x00f`。约 86 MiB 的 12 个 `.mem` 和
manifest 已通过独立 verifier。软件精度为：

| 版本 | max abs error | mean abs error | RMSE | cosine |
|---|---:|---:|---:|---:|
| SC | 1.5037134e-5 | 6.4344503e-6 | 7.7055634e-6 | 0.9999999999986661 |
| FP16 | 9.4402246e-3 | 1.1507838e-3 | 1.4688116e-3 | 0.9999999519225544 |
| FP32 | 2.4633482e-5 | 4.0462260e-6 | 4.7917034e-6 | 0.9999999999994785 |

当前没有可引用的 Down 三路硬件资源、时序或周期结论。

M12 已补建全 96 pair-lane/192 output-lane 的 `5 groups × 16 tiles` 非零小型
workload 与 wave/no-wave 成对 runner。64 个 group/tile 具有非零算术贡献，三路
各 2,944 个有效输出元素全部非零；独立重生/逐文件 byte-compare PASS，manifest
SHA256 为 `a7d4b14bf67e6a8ab495b20f055fbd6fcc97ca7093b8e2d76c27311aaf95af23`，
且 80 个三路 payload 的各字段均已反向绑定到正式 synthetic 的 group/tile 源行。
runner 会逐字比较 288 个输出 word 和全部功能周期/握手指标，并要求 no-wave WDB
严格更小；无关 Vivado/XSIM 活跃时，serial A/B、full XSIM 与 OOC 三类入口的
fail-closed 门禁已实测均返回 exit 75，未启动实验硬件进程；共享非阻塞 `flock`
还防止 ModularExperiment 自身误并发。实际三路 A/B 仍等待共享硬件环境空闲。

M12 真实 workload 现已从层 0/15/31 的实际 BF16 Down 输入和相应 checkpoint
`down_proj.weight` 生成。每层为 16 rows × 448 groups × 342 tiles，三层合计
459,648 transactions 和 196,608 个有效输出，约 257 MiB。weight 由 production
V5 exporter 执行 normalized folded group32 W4 量化；三路共享相同 centered
S9/W4 payload 与 decoded scale，只改变 scale 表示/应用，避免重复计入 M11
producer。全量临时重生成/逐字节校验结果为：

```text
M12_TRACE_VECTOR_VERIFY_PASS files=38 layers=3 rows=48 transactions=459648 valid_outputs=196608 regenerated=1 fp16_boundary_cases=3 source_tensors=6 manifest_sha256=4074940a6004d6487ef19705caf70bcf542e7c65fccce25d8117831e8883945c
```

层 0 的 SC/FP16/FP32 raw-checkpoint RMSE 为
`3.9469860e-3/5.2208961e-3/3.9469214e-3`，层 15 为
`6.9021009e-3/6.9043436e-3/6.9020167e-3`。层 31 在 row 0/8、输出列
788/1384/4062 出现三路共同的 6 个 S24 ±128 饱和，导致三路 RMSE 均约
`1.6303`；该真实范围负证据保留在 workload 与报告中，不能删去。以上仍是
软件/输入证据，必须完成三路 RTL replay 后才可升级资格。

## 完成前必须补齐

1. 先完成 M12 全宽非零小型有波形/无波形 A/B，再在当前 manifest 下刷新 SC、
   重跑 FP16/FP32 synthetic/三层 full trace，并严格串行完成三路 100 MHz OOC；
2. 补齐 02 SC continuous、FP16/FP32 continuous+backpressure trace 和当前源码 synthetic；
3. 为 03、05、06、07、10 补 boundary-inclusive 主口径，并保证完整链只计一次
   dequant 边界；
4. 补齐 `N={1,16,32,64,112,128}`、不少于 10 seeds、永久 ready、周期/伪随机
   backpressure、数值异常和目标模块专属指标（Softmax KL/top-1 等）；
5. 从已冻结的 Llama-3.1-8B trace 派生模块量化输入/golden，并在 boundary 与
   Attention/MLP 非重叠链 XSIM 中重放；
6. 实现 Attention 与 MLP 非重叠链顶层，重新综合而不是把孤立模块面积相加；
7. 为 01/08/11 完成当前 Min/Max routed DCP、为 12 和 09 FP32 补齐 routed DCP，并提高 06/09/10 FP SAIF 覆盖后刷新功耗；统一 CSV/JSON 已生成，figures 尚待最终数据；
8. 从全部最新 `SUMMARY.md` 与原始 JSON 重建最终报告并逐项完成审计。

M02 真实 projection trace 的前置语义门禁已经完成：定向 XSIM 使用
production group32 MAC 和正式 AMD FP16 IP 链，覆盖 FP16 溢出阈值、真实 Q/K/V
correlation 极值及正负 `Infinity x 0`，记录到 S42 的每一级 bit pattern。最终
25-case run 为
`raw/fp16/semantic_probe/20260910_121638_s21_to_fp16_to_s42/`，
`semantic_map.json` SHA256 为
`99c04c9756908f11ed41950e9a4e4e60f78a3e9424dc87931f02ad82e570d7e5`；
输入、FP XCI 和目录哈希均通过。

语义门禁之后的 M02 真实 Q/K/V 生成器与独立 verifier 已完成，目标几何为
2 samples × 3 layers × 3 projections =
18 tiles、2,304 group transactions、2,304 outputs。Q/K 保留 M03 已证实的真实
溢出坐标，V 从全部 1,024 行选择真实 max-abs correlation 最坏 16 行；正式
manifest SHA256 为
`c1702bc0b43ca56291f886b3ee5a23a7eb1d385907c081ee7b21ec4c14db1e54`。
SC 周期背压 XSIM 已完成 18 tiles、2,304 groups、0 mismatch，input II=2，总计
4,971 cycles。matched runner/TB 的 backpressure 增强使旧 M02 XSIM
current-input hash 失配，三路 synthetic 仍须补跑；被测 RTL 与既有 OOC 未修改。

旧 `module_experiment` 的 150 MHz 数据及 `legacy_seed/` 只用于实现交叉检查，
不进入本报告正式数值。

真实 trace 已从本地 Llama-3.1-8B-Instruct BF16 checkpoint 正式冻结：2 个固定
文本样本、256 tokens、层 0/15/31，共 66 个 pre/post-RoPE Q/K、V、raw/masked
score、probability、Gate/Up 与实际 Down 输入 tensor，并生成 27,504 个
token/head/group slice hash。正式 run 的 capture/verifier、目录与输入 hash 全部
PASS；详见 `result/trace/SUMMARY.md`。当前剩余缺口是从这些 tensor 和 checkpoint
权重派生其余模块量化 workload，并完成 RTL/整链重放；trace 本身不能替代硬件
结果。M03 已用冻结 input IDs 和相同 checkpoint 补充捕获 6 个真实 projection
输入，并以重算 Q/K 对原 trace 做 provenance 检查：layer 0/15 bit-exact，layer 31
保留 824,370 个 BF16 bit mismatch，最坏 normalized RMSE `3.9763205e-3`、最低
cosine `0.999992094591`。随后从原始 Min/Max A8/W8 量化生成 12 pairs × 128 groups
= 1,536 transactions，manifest SHA256 为
`0c39d93a305b96deccd0a144d0d41a0c63fe5a265d634ad0487fc8578618b3a5`。
真实 S21 correlation 范围导致 FP16 88 次非有限转换，污染 11/12 pairs 和 22/24
个 RoPE 软件输出；SC/FP16/FP32 相对共同量化 FP64 的 RMSE 为
`6.9432013e-6/122.0997312/4.0256286e-6`。该负面范围证据等待 Xilinx IP trace
XSIM 复核，不能提前写成硬件 PASS。

M01 Attention frontend 已从上述 6 个 projection-input tensor 选择 8 个真实
token row，完整生成 128 个 8-row/group32 bundle；SC/FP16/FP32 相对共同
Hadamard 实值的 RMSE 为
`1.7589088e-3/1.6618187e-3/1.6601894e-3`，manifest SHA256 为
`7e6dea87382e21471a2f0c32d5cae7ca32d31f7a9ac8cc9999f306aef93aa8d6`。
M04 KV12 已从 12 个真实 post-RoPE K/V tensor 派生 16 batches、
64 group32 records；K/V 交替，每个 head 完整覆盖四个连续 group32。相对共同
S24，SC KV12/FP16/FP32 RMSE 为 `8.9869041e-4/6.7434958e-7/0`，且 S24
saturation、KV12 clip、保留 `-2048` 与 zero-scale record 均为 0；manifest
SHA256 为 `ac31392da0a79bfbc512be83ebcb4b0476ef2d16eb958ef7f33699ab6bcc0065`。
M05 QK、M06 Softmax 和 M07 PV 已分别完成真实 trace 软件 workload：三者均覆盖
2 samples × 3 layers × 6 shapes × 2 heads，即 72 rows/4,236 keys。M07 按 GQA
映射使用 KV-head 0/4，对完整 32-lane group 执行 production KV12 量化后读取
head-dim 0–15 tile；其 verifier manifest SHA256 为
`ce9eac6783699b0c84ea55314541aa4a784c824ab817056f0acaf232e52f465b`；
M05 对 16,944 个 K group 执行同一 production KV12 量化，manifest SHA256 为
`05e530d373bb4173927fddd1a174bfc0a0b9573a1ae692911a33290e13ae4f74`。
M08 MLP frontend 已使用冻结 input IDs/checkpoint 补充捕获层 0/15/31 的
6 个 `128×4096` pre-Gate/Up BF16 tensor；层 0/15 的 Gate/Up 重算 bit-exact，
层 31 保留 5,316,910 个 BF16 bit mismatch，最坏 normalized RMSE 为
`4.8446746e-3`、最低 cosine 为 `0.999988273647`。随后派生 16-row × 128-group
frontend workload，SC/FP16/FP32 相对共同 Hadamard 实值的 RMSE 为
`1.5539701e-3/1.4622940e-3/1.4613934e-3`；capture/workload manifest SHA256
分别为 `281da5fef1979b0f8c0199497cb0117948d3ce530e0aeeb094f4eae96c50b9e7` 和
`aa2ba847b92230b3cb7bfe687e58377d965d3213a2d9df15ea46c37242c23cf2`。
M09 Gate/Up 随后用相同捕获与 checkpoint 权重生成层 0/15/31 的 Gate/Up
6-tile workload，共 768 transactions 和 1,024 个有效输出，包含五个 full mask
与一个真实 `0x00f` tail。correlation/total-shift 范围为
`[-7384,6959]/[26,37]`，FP16 非有限 contribution 与三路输出饱和均为 0；
SC/FP16/FP32 相对共同量化 FP64 的 RMSE 为
`5.6047257e-6/2.7056551e-4/4.5015972e-6`，manifest SHA256 为
`d2837d2118ac00bf70519277c26dbb8e2ffa1c12d28f0588caa3e5fd13af5c63`。
M10 SiLU×Up 也已派生 2 samples × 3 layers × 8 tokens × 128 均匀通道的
6,144-vector 真实 workload，manifest SHA256 为
`bc7b6a64fe7efd65692b9baf91b190c0a7e7ad1b9023aa4211c2eed0ee16492b`。
M11 使用实际 Down 输入选择 16 个跨样本/层/token 的 row，完整覆盖
448 groups × 16 rows × 32 lanes；SC/FP16/FP32 相对 raw-trace Hadamard 的
RMSE 为 `1.4611e-3/1.7346e-3/1.2325e-3`，manifest SHA256 为
`f305d9db27e4b354e3492f080953bbd41459a09cd2a6a294c67481463d8f3de7`。
M12 使用三层真实 Down 输入与对应 checkpoint 权重完成 3 份 full-shape
workload，manifest SHA256 为
`4074940a6004d6487ef19705caf70bcf542e7c65fccce25d8117831e8883945c`；其中
layer 31 的 6 个真实 S24 饱和点作为输出范围限制保留。上述十一个模块尚未运行
完整的三路 boundary RTL trace XSIM；M12 SC layer-0/15/31 已完成三条 full-shape
trace，每层 153,216 transactions、65,536 outputs、0 mismatch、input II max=1、
总周期 153,234；layer-31 正确保留 6 个真实 S24 饱和点。三条运行目录哈希仍通过，
且修正前后 SC 实际使用的 payload/golden 逐字节相同；但旧 runner 将三路全部
golden 和共享 generator/manifest 写入通用输入哈希，当前 raw audit 因 FP16 修正
带来的 provenance 变化将三条 SC 运行判为 input-hash drift。runner 现已按所选
variant 读取/哈希；正式候选资格仍需要在当前 manifest 下刷新。
FP16 layer-0 首跑完整接受 153,216 个事务并输出 342 个 tile、II=1，但 200 个
tile payload mismatch，因此只保留为 diagnostic。对同一输入离线替换为 M02 已实测
的 AMD minimum-normal underflow 阈值后，变化恰好为 314 个 element/200 个 tile，
且 tile 索引与 RTL mismatch 逐项一致。修正后的 generator SHA256 为
`751afbead80f4e393c99fedbed609f997301eaab88b43ed39ddbb9f276e2a09b`；三层
golden 已完成第二次独立全量重生/逐文件 byte-compare，并通过 3 个定向 FP16
边界自测。相对旧 FP16 golden，layer-0/15/31 分别变化
314/117/17 个 element、分布在 200/80/15 个 tile；修正后 RTL 重跑尚未执行。
独立 correction auditor 已同时验证失败目录自身哈希、代表边界位型及 Layer-0
全部 RTL mismatch 集合，结果为
`M12_FP16_CORRECTION_VERIFY_PASS files=38 changed_payloads=3
changed_elements=448 changed_tiles=295 layer0_rtl_mismatch_tiles=200
fp16_boundary_cases=3`。
> **P0 更正（2026-09-10）**：上述 M01/M02/M03/M08/M09/M11/M12 软件 trace 已是
> 当前 Min/Max 数据；M02 另有 SC 周期背压 RTL replay PASS。旧量化器 XSIM/OOC 仍为
> `robust-clipping legacy`，必须在实验本地 Min/Max RTL 回归与重新综合后更新。
