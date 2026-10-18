# M002：阶段报告

> 最新进度：**用户暂停：服务器关机更换PDU。E008/AT003已于北京时间2026-10-17 16:44:09停止，14项收尾通过、无残留工程进程且EDA资源已释放。未经用户明确通知继续，不启动任何工程/观察器/自动重试。** [续接记录](../../mission/M002_ddr_separation_and_timing_recovery/pdu_shutdown_handoff_2026-10-17.md)。

下文保留E005已结束基线及更早阶段记录。

> 当前进度：E005优化后的完整implementation及补采已全部结束，合法布通失败：1148579重叠路由节点、758463拥塞失败信号，失败DCP和诊断已保存。局部功能通过，新综合及完整place/physopt流程完成；布线前setup改善，hold仍失败。R006两批只读补采均自然成功、独立复核完成，144冻结输入与原检查点保持。整体执行failed、方法判断inconclusive，用户结果审核未记录；M002全局目标未完成。[E005结果](../../project/E005_m002_optimized_implementation/experiment_results/summary.md)、[主控审核](../reviews/SM009.md)。

## E004、E003及更早阶段历史

下文为各阶段当时的判断，不覆盖E005当前结果。

> 最新进度：SM008/E004详细优化分析已完成，主控整合及独立审核完成。首选Attention固定slot写入48个局部边界、MLP32个同拍输出CE及SSI_SpreadSLLs布局；验证、后备与严格route判据见[优化方案](../../project/E004_m002_routability_optimization_analysis/experiment_results/optimization_plan.md)及[主控审核](../reviews/SM008.md)。只读诊断自然完成、原DCP未改，无活动EDA。候选尚未实施，布通收益inconclusive；本轮未改生产设计或运行新综合/place/route。

> E003已结束基线：本轮完整implementation尝试已自然结束，执行FAILED；place/独立physopt命令、DCP和完整POST通过，R003/AT001 route实际19065秒后于22:45:40 UTC返回Tcl1。Phase9合法布通FAIL：245279重叠路由节点、248289拥塞失败信号（不同指标）。22:45:51 UTC监督/driver自然结束，stop_reason=null，无时间或资源终止，六个原进程退出且单EDA锁释放。没有生成route DCP/完整route_status/正式routed时序/POST；最后有效恢复点是AT002 physopt.dcp。原失败保留，无新EDA尝试，未改变算法/RTL/XDC/接口/时钟/默认策略。 下文E002/E001为前置历史，不能当作本轮最终结果。

150项CPU/实际图与来源验证后，新原生place POST已真正完成；此前两条DDR1 AUX代表源适配问题已在真实新图分类中关闭。独立physopt命令/DCP已完成，正式WNS−1.290/TNS−762.165ns，setup980；WHS−0.620/THS−2150.556ns及hold33141不变，仍FAIL且互连仍为布线前估计。完整physopt POST已通过，55份阶段文件封闭；本轮route已自然失败，245279重叠节点导致非法布线，没有完整routed产物。正式安全OPEN，全布通未达到。[阶段facts](../../project/E003_m002_full_implementation/experiment_results/runs/R002/attempts/AT002_closed_place_POST_physopt/completed_place_POST_facts.json)、[独立审核](../../project/E003_m002_full_implementation/experiment_results/runs/R004/architecture_review.md)。

## E002：综合与入口适配完成，布局实验因时间上限结束

2026-10-15 02:44:24 UTC，新工程正式综合完整结束，exit0，耗时114.28分钟，峰值进程树RSS27.06GiB，无残留本次进程。板级LUT841576（71.18%）、FF1029313（43.53%）、DSP5451（79.69%）、BRAM945 tiles（43.75%）、URAM752（78.33%）；聚合资源未超器件总容量。

综合估计WNS+0.904ns/TNS0、WHS-0.814ns/THS-49355.641ns，时序FAIL；PW检查栏目5个失败，已见最差为PCIe Max Skew -0.012ns。唯一dbg_hub_CV工具占位、530缺时钟/554未约束MIG调试端点、6条reset CDC critical需继续核查。默认DRC无error/critical，但保留15927条warning。原始数字与身份见[E002结果及证据](../../project/E002_m002_synthesis_and_physical_baseline/experiment_results/summary.md)。

物理流程已取得实际OPT DCP，优化命令exit0；黑盒1→0、缺时钟530→0、内部未约束554→0。优化后LUT70.06%、FF43.20%、BRAM43.56%，DSP/URAM保持；时序仍FAIL。AT004在place前受控结束，整体125/native-15，不冒充完整POST或物理成功。后继从OPT继续实际clock/约束/复位检查和布局布线。各次实际结果集中见[E002状态](../../project/E002_m002_synthesis_and_physical_baseline/experiment_status/summary.md)和[A007审核](../../project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R005/architecture_review.md)。

过程记录（终态见下一段）：最新OPT报告为8条reset CDC critical，相对INIT精确4保留、2旧source移除、4新增身份；实际结构/688端口取证与102项CPU通过，正式reset/CDC安全仍OPEN。AT008实际OPT准入、debug和完整pre_place通过后进入布局，于09:08:31 UTC达到原2小时上限，124/native−15、无survivors；布局到细化Phase3.3，无完整place/physopt DCP，route未开始。AT012恢复入口已安装，19项本次测试及实际完整POST/父链核验通过，96项legacy复用；AT009于09:41:02 UTC从完整pre_place检查点实际启动恢复，截止11:41:02 UTC，本次live恢复检查已通过并实际进入place，准备至回执实测减少31分21秒；尚无完成布局产物。保留有限live sanity/DRC和原资源/时限，若再无新完整物理恢复点则不重复place。跨SLR属性告警影响待测，原失败保留；全局时序与板级验收未完成。

**最终布局终态：**AT009从完整pre_place恢复，准备至回执实测748.398秒，比AT008同口径少1881.143秒（31分21秒）；恢复成本改进真实成立，但未在原两小时内完成布局。11:41:11 UTC终止，124/native−15，峰值树RSS32.28GiB，所有7个进程身份退出；停在Phase4.1.1.3布局后时序优化，无place/physopt成功回执或完整DCP。内存中的部分布局不能续接，按合同停止重复place，缺失阶段恢复候选未测试/未安装/未执行，route未运行。[原终态与身份](../../project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R003/attempts/AT009_completed_pre_place_recovery_place_physopt/terminal_facts.json)。

布局内部中间估计WNS−1.884ns/TNS−1349.388ns，不能替代完整placed/hold/PW报告。10个BUFG插入候选全因placement/routing conflicts跳过；两条DDR1 BUFCE_ROW延迟控制值上限4告警是满足PLL/RIU Max Skew的工具限制，不代表4ns或两个违例，也不能套用此前PCIe的−0.012ns。USER_SLL_REG放置意图未满足和相关完整影响仍待实际物理报告。[中间事实](../../project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R003/attempts/AT009_completed_pre_place_recovery_place_physopt/post_place_bufg_opt_intermediate_facts.json)、[架构审核](../../project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R005/architecture_review.md)。本轮执行未取得完整物理基线，方法结论inconclusive；成本上限不反驳架构，未达到100MHz时序/复位安全/板级签核。

## E001：已完成的修复与快速功能验证

2026-10-15，项目主控整合审核。**本轮修复与快速验证已完成；可进入 fresh synthesis 获取当前架构的资源、时钟和告警报告。implementation 尚不具备直接启动条件。** 这是工程启动建议，不是综合/物理/板级验收；本轮未运行正式综合或 implementation。M002 的时序恢复和最终部署目标仍未完成。

## 已修复

- 恢复 Attention/MLP 各自的两条完整逻辑权重流；新调度器将 Attention 两流送 DDR0、MLP 两流送 DDR1，保留成对描述符、返回归属、背压、维护排空和错误冻结。
- 为 MLP tensor/metadata/输出提供独立 256-bit 数据口，经 BD 到 DDR1；Attention 数据口到 DDR0。两个引擎的 native reader 时钟/复位分别对应专属 DDR。
- 恢复 Host API 与六个权重 CSR 本地偏移；DDR0 常驻完整 Attention 1280 MiB，DDR1 采用受 lease 保护的 84 MiB 单层 MLP slot。修复地址交叠、输入/输出别名和在飞权重覆写；异常后保守阻止复用。
- 新只读布局 ID `0x2B8=0x4D303032`，Host 在 preload/写入前校验，旧布局硬件被拒绝。Hadamard、ScaleCode、format05、数值位宽/舍入和 golden 保持。
- 修复完整构建源清单、BD 连接和约束入口；移除新 XDC 中无依据的例外/位置，旧 mission0004/0005 物理约束保留原件但退出 M002 默认输入。

接口与地址权威见 [执行合同](../../mission/M002_ddr_separation_and_timing_recovery/repair_contract_2026-10-15.md) 和 [RTL 说明](../../project/hardware/source/m002_dedicated_ddr.md)。修复前 [readiness 审核](../reviews/M002_readiness_2026-10-15.md) 是历史基线，不能继续当作当前源码状态。

## 实际验证

| 范围 | 最终证据 | 结论 |
| --- | --- | --- |
| Host/API/加载生命周期 | [R001 AT104](../../project/E001_m002_repair_quick_validation/experiment_results/runs/R001/attempts/AT104/output.log) | 106 项 CPU 测试 PASS，exit 0；含真实 Host 调用路径和未退役/旧布局负例 |
| 构建与静态合同 | [R003 AT006](../../project/E001_m002_repair_quick_validation/experiment_results/runs/R003/attempts/AT006_final_cpu_and_static_contract/status.json) | 49 项 CPU 测试和源静态审计 PASS |
| 整数参考/源身份 | [R004](../../project/E001_m002_repair_quick_validation/experiment_results/runs/R004/run.md) | 9 项整数参考 PASS；170 个数值/软件文件与冻结 M001 hash 一致 |
| 完整 board RTL 展开 | [R003 AT004](../../project/hardware/vivado/reports/m002_R003_AT004_final_complete_board_rtl_elaboration/elaboration_scope.txt) | 88 个 RTL 文件，0 blackbox，exit 0；`synth_design -rtl`，不是正式综合 |
| 权重调度与完整组 | [R002 AT008](../../project/hardware/vivado/reports/m002_R002_AT008_final_weight_groups/xsim.log) | 38 主检查 PASS；115 Attention/184 MLP 完整组；pending 第二描述符遇满队列实测 17 cycles |
| 原生 reader/CDC/FIFO 集成 | [R002 AT009](../../project/hardware/vivado/reports/m002_R002_AT009_final_real_frontends/xsim.log) | 7 主检查 PASS；各 64 完整组；物理 R 背压 505/598 cycles 后完整维护排空 |
| 数据路由/布局 CSR | [R002 AT002](../../project/hardware/vivado/reports/m002_R002_AT002_dedicated_data/xsim.log)、[AT003](../../project/hardware/vivado/reports/m002_R002_AT003_memory_layout_csr/xsim.log) | 分别 11/10 主检查 PASS，DDR0 阻塞时 MLP 独立进度、完整读写与只读兼容标记 |
| 实际 Vivado BD | [R003 AT007](../../project/hardware/vivado/reports/m002_R003_AT007_actual_bd_validation/bd_validation_summary.txt) | 构造和 `validate_bd_design` 返回 0；256-bit MLP→DDR1、core100/UI200 连接通过；保留严重告警说明见下 |

上述范围不可相加为互不重叠的用例总数。主控核对原始日志/退出码；Host 20 个输入与完整展开 96 个输入 hash 当前一致。data/CSR 的实际编译依赖未因其他 TB 修复而改变，详见 [适用性复核](../../project/E001_m002_repair_quick_validation/experiment_results/runs/R003/applicability_recheck.json)。

失败尝试全部保留：含初次声明顺序编译错误、源变化后主动终止的展开、CPU fixture/旧通道期望、权重 TB delta-cycle 采样竞态及首组 oracle 未初始化。后者通过实际 got/expected 诊断和独立 Python 字节模型定位；仅修正组合计算触发并增加非 X 断言，没有修改地址/数据期望函数或数值 golden。各次详见 [R001](../../project/E001_m002_repair_quick_validation/experiment_results/runs/R001/worker_report.md)、[R002](../../project/E001_m002_repair_quick_validation/experiment_results/runs/R002/worker_report.md)、[R003](../../project/E001_m002_repair_quick_validation/experiment_results/runs/R003/worker_report.md)。

## 告警和综合启动判断

完整 RTL 展开日志有 296 条普通 warning，0 error/critical；其中 29 条 reset 优先级告警来自三个未改变的历史数值模块，源身份已核实。这不等于告警已解决，需要后续综合和复位行为核查。见 [告警分类](../../project/E001_m002_repair_quick_validation/experiment_results/runs/R003/attempts/AT004_final_complete_board_rtl_elaboration/warnings.json) 及相邻 provenance。

实际 BD 日志有 4 条 `BD 41-1354` 地址段重叠 critical，另有 1 条逐个 add_files 的性能提示 critical。**命令返回成功不等于无严重告警签核。** 独立审核实际生成的内部 BD 确认：Host splitter 按 0/0x80000000 的两个 2 GiB 窗口选 DDR；DDR1 core 的 S00/S02 各自只有 local 0 窗口，Host S01 继承上游路由，唯一出口地址宽度 31 位。因此当前证据支持有意跨主地址别名，未发现错误 DDR 可达路径。该模式在旧构建已有，不以新增 MLP 口为全部告警根因。

[实际译码参数与源身份](../../project/E001_m002_repair_quick_validation/experiment_results/runs/R003/attempts/AT007_actual_bd_validation/bd_address_decode_evidence.json) 和相邻边界复算保存了此结论的依据。保留这些 critical，不作正式豁免；本轮没有真实 SmartConnect AXI 边界/双 DDR 区分写读仿真。以上静态生成配置足以支持启动 fresh synthesis 进一步取证，但不足以支持 implementation 或 bitstream 签核。

## 下一阶段与未覆盖

启动与验收的补充澄清：当前place/route的直接阻塞是本轮加入的临时脚本保护和其后的旧物理检查，不能据此断言架构无法布局布线。“处理告警”指分类、验证和必要修复，不要求全部清零；真实互连功能补证可与诊断性物理实验并行，未决项仍不能当作最终验收通过。详见 [Q001追问解释](../../question/Q001_M002_synthesis_readiness/answer.md)。

1. 使用新的项目/报告目录执行正常 `create` 后仅 `synth`，获取资源、时钟和综合告警；validate-only 临时项目缺 IP outputs/wrapper，不可直接沿用。实际入口在 [R003 报告](../../project/E001_m002_repair_quick_validation/experiment_results/runs/R003/worker_report.md)，本轮没有执行。
2. 在 implementation 前建立与当前专属 DDR 设计一致的物理检查，处理上述告警并补真实互连边界/区分写读验证。旧 native025 分区/terminal 数目不适用，当前 place/route 入口对此作技术拒绝。
3. 完整 32 层/双 cohort 数值回归、setup/hold/CDC/DRC、route、bitstream、板级闭环、PPL/ACC 和性能仍须独立验证。RTL 展开对象数不是综合资源。
4. KV 仅保留地址，未新增/验证外部 KV 生命周期。单层 MLP Host 流送开销必须进入新的性能模型；旧“+40%”或 tokens/s 预测不能复用为测量结论。

SM 审核：[SM002](../reviews/SM002.md)、[SM003](../reviews/SM003.md)、[SM004](../reviews/SM004.md)。执行 completed 仅指本轮限定任务；用户全局验收尚未发生。旧工程未修改，未恢复旧对话绑定或旧工程任务。
