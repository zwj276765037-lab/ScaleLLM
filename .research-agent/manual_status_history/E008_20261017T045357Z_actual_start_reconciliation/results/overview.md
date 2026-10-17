# ScaleLLM：审核总览

当前目标为针对SLR1热点选择一个有实际证据支持的模块卸载到SLR2，并真实启动SM012/E008完整implementation。已有授权保持；候选尚未选定，E008未启动。热点MLP贡献约76.7%，旧输入前端候选保留为未实施探索对照。

当前E006/R006/AT003缓冲日志版已于2026-10-17 03:49:59Z真实原生启动，正在载入同一E005 physopt图。12归档源/23be、144输入、CPU0–7/nice5与项目唯一EDA资源已核。[最新实际状态](../project/E006_m002_slr1_congestion_attribution/experiment_status/summary.md)。

R005的C01完整cut/有界时序保持，原图输入hold−0.128ns、双向最差setup涉及兄弟SwiGLU控制耦合。R006 AT002两候选membership通过，C01完整端口索引269端口/269组/2170次native0已独立接受；完整cut/时序未完成。AT002新增高频同步alias日志造成明显额外工作，用户单独批准切换后于03:48:51Z受控结束，16项输入/进程/锁收尾通过。全部部分结果和原始证据保持。[归因与候选结果](../project/E006_m002_slr1_congestion_attribution/experiment_results/summary.md)。

同一缓冲日志修复的R00623be/E0083cae包已[集中独立接受](../agent/A007/R006_AT002_native_stage_review_20261017/buffered_alias_logging_review/review.md)：仅改变六处高频alias事件写出方式，完整事件/时间/错误收尾与原查询/缓存/索引资格/时序保持。此前1425/dcc64均未改。当前图仍实际核验，性能不预填；完整C02对照和终态闭合后直接选型并启动E008，无新的普通工程批准门。

此前R001/R004/R005/R006-AT002单次停止许可均已使用，不扩展到当前正常AT003。单EDA及资源保护、正常无墙钟/无输出强停、Hadamard/ScaleCode/format05和RTL/IP/ABI/时钟保持，无bitstream/GPU/板卡/PPL/ACC，旧工程只读。

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

前置历史见[M002阶段报告](missions/M002_summary.md)和[M001整理报告](missions/M001_summary.md)。E003失败与E004方案原证据保持；旧工程严格只读、旧长期会话不重绑。E005证据交付已完成；E006 R004成员/资源已闭合并受控结束，当前R005 AT003继续两个热点候选有向边界比较。原E007输入前端候选降为探索对照，下一实现范围待比较结果确定。

此前概览及阶段文字已按字节归档至 `.research-agent/manual_status_history/E005_20261016T150423Z_before_final_reconciliation`；该目录用于历史保存，当前事实以上述摘要及原运行证据为准。
