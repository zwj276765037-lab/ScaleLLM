# ScaleLLM：审核总览

SM011/E007已获用户“进行针对性优化后开启下一轮implementation”授权，正在准备输入bank与MLP capture/Hadamard/四量化器成组迁往SLR2的工程入口，实际EDA尚未启动。[执行合同](../mission/M002_ddr_separation_and_timing_recovery/slr2_input_locality_candidate_contract_2026-10-17.md)、[E007状态](../project/E007_m002_slr2_input_locality_implementation/experiment_status/summary.md)。前置SM010/E006只读诊断继续，已核当前MLP为SLR1主要贡献者、候选规模与职责；热点/连接及真实收尾待完成，单EDA资源未释放。[E006状态](../project/E006_m002_slr1_congestion_attribution/experiment_status/summary.md)。

以下为已结束的E005基线及其验收限制。

E005优化后的完整implementation及补采已全部结束，合法布通失败：1148579重叠路由节点、758463拥塞失败信号，失败DCP和诊断已保存。局部功能通过，新综合及完整place/physopt流程完成；布线前setup改善，hold仍失败。R006两批只读补采均自然成功、独立复核完成，144冻结输入与原检查点保持。整体执行failed、方法判断inconclusive，用户结果审核未记录；M002全局目标未完成。

当前基线为VCU118 / xcvu9p-flga2104-2L-e、Vivado2025.2、core100MHz与双DDR UI200MHz；Attention→DDR0、MLP→DDR1。Hadamard、ScaleCode、format05、数值与Host ABI保持。唯一实现入口是project/hardware与project/software。

| 已核事实 | 判断 |
| --- | --- |
| Attention与Gate/Down定向差分及独立oracle通过；80局部控制在实际网表落实 | 只覆盖已执行局部测试，不代表全系统或板级功能验收 |
| 同physopt阶段LUT814935→801751、CLB站点99.11%→97.31%、setup WNS−1.290→+0.103ns | 资源和布线前setup改善；hold WHS−0.695ns仍失败 |
| 同route Phase9重叠节点245279→1148579，拥塞失败信号248289→758463 | 本次组合未合法布通，关键失败指标恶化；两种计数单位不同 |
| 新SLR0/1/2 CLB99.00%/99.85%/93.07%；Gate1917跨SLR叶pin，Attention同SLR仍大跨度 | 局部拥挤和连接跨度仍是实际风险；尚不能分离RTL与SSI布局的因果贡献 |

详细数值与原报告见[E005结果](../project/E005_m002_optimized_implementation/experiment_results/summary.md)，阶段内部审核见[SM009](reviews/SM009.md)。R006旧48窗映射已测，固定窗口原生拥塞为UNAVAILABLE；实际资源占用不能替代拥塞等级。新最坏12峰行→10区域已在各自place/physopt实际测量，全部SLR1且SLICE站点均有primitive占用；不等于LUT/FF/BEL槽全部满。原48行保留，其他36非峰行未逐区测量，10区重叠不累加。

当前合法routed时序、正式CDC/reset/release/transaction与外部IO安全、端到端数值和板级验收均未完成。失败图时序不作签核；用户结果审核尚未记录。无bitstream、板卡、GPU、PPL/ACC。

前置历史见[M002阶段报告](missions/M002_summary.md)和[M001整理报告](missions/M001_summary.md)。E003失败与E004方案原证据保持；旧工程严格只读、旧长期会话不重绑。本轮已完成证据交付，当前无本任务活动EDA；后续优先隔离布局策略与热点资源/连接局部性，不因一次实验失败自动扩大优化范围。

此前概览及阶段文字已按字节归档至 `.research-agent/manual_status_history/E005_20261016T150423Z_before_final_reconciliation`；该目录用于历史保存，当前事实以上述摘要及原运行证据为准。
