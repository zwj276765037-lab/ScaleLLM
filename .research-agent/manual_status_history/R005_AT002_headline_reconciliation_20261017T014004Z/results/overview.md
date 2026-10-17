# ScaleLLM：审核总览

用户针对性优化与完整implementation授权保持。热点MLP贡献约76.7%，旧SM011/E007输入候选降为未实施探索对照；C01/C02成员与资源已在R004闭合。用户另行批准切换后，R004于09:17:59受控结束，原全网cut/时序/UNION未完成保持；R005于09:19:19实际启动同图有向边界比较，当前恢复检查点。[最新实测](../project/E006_m002_slr1_congestion_attribution/experiment_results/summary.md)、[E006状态](../project/E006_m002_slr1_congestion_attribution/experiment_status/summary.md)。

后继SM012/E008原b59共通入口准备已审，新有向cut口径9f267包已准备、独立核查中。候选未选择，尚未启动implementation。R004收尾与R005原生启动的[独立证据](../agent/A007/R004_controlled_closure_R005_start_review_20261017.json)已闭合；本次停止例外不扩展到后续正常进程。

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

前置历史见[M002阶段报告](missions/M002_summary.md)和[M001整理报告](missions/M001_summary.md)。E003失败与E004方案原证据保持；旧工程严格只读、旧长期会话不重绑。E005证据交付已完成；E006 R004已启动两个热点候选的只读比较，当前原DCP恢复中。原E007输入前端候选降为探索对照，下一实现范围待比较结果确定。

此前概览及阶段文字已按字节归档至 `.research-agent/manual_status_history/E005_20261016T150423Z_before_final_reconciliation`；该目录用于历史保存，当前事实以上述摘要及原运行证据为准。
