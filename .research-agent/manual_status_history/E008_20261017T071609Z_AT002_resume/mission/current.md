# 当前大 mission

当前任务为SM012/E008：**已选择C01 SwiGLU branch[1]迁往SLR2，并于北京时间2026-10-17 12:50:44实际启动R001/AT001完整implementation**。当前恢复E005正式父网表、进入布局前流程；尚无新place/physopt/route成功结果。

E006 R006 AT003于北京时间12:45:04自然成功，六阶段全部通过、native0/supervisor0；25项工程收尾与独立终态核验完成。C01热点成员8697、C02为2303；普通已定位边界逻辑对7124 vs12235。独立审核支持本轮仅选择C01进行单变量物理实验，不承诺一次布通。[完整比较](../project/E006_m002_slr1_congestion_attribution/experiment_results/summary.md)、[候选判断](../agent/A007/R006_AT003_native_stage_review_20261017/single_candidate_recommendation.md)。

E008使用3cae已审入口，35份实际运行源、144生产输入和本项目唯一EDA占用已核；启动亦经独立审核。只改变选定模块的SLR2位置要求，完整pre-place资格→SSI_SpreadSLLs place→Default physopt→Default route连续执行。[实际状态](../project/E008_m002_exact_hotspot_offload_implementation/experiment_status/summary.md)、[启动事实](../project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT001_C01_slr2_offload_full_implementation/native_start_verified.json)、[启动独立审核](../agent/A007/E008_R001_AT001_actual_stage_review_20261017/start_review.md)。

C01父图输入hold−0.128ns、SLR2 CLB93.07%和MUX/DSP/BRAM打包是未验证风险；源站点多与组外共享，不能承诺全部释放。原physopt有界时序不是迁移后时序，逻辑连接对不是实测SLL。实际落区、局部压力、合法布通、setup/hold/PW及CDC/reset/IO分别验收。

单EDA与资源保护、正常无墙钟/无输出强停保持；此前单次停止许可均已使用。RTL/IP、Hadamard、ScaleCode、format05、ABI和时钟不变；无bitstream/GPU/板卡/PPL/ACC，旧工程只读、旧会话不重绑。进程由本次实际监督器管理，文档状态不是实时心跳，未另设跨会话通知服务。

M002全局目标仍未完成。当前合同为[SM012单候选卸载](M002_ddr_separation_and_timing_recovery/exact_hotspot_offload_implementation_contract_2026-10-17.md)，并适用同目录有向范围与端口索引获取补充。原SM011/E007输入前端仅为未实施探索对照。

| 已结束阶段 | 真实结果 |
| --- | --- |
| E005优化后完整实现 | route自然失败，1148579重叠节点、758463拥塞失败信号；原证据保留 |
| E004详细分析 | 已完成，组合收益由后续实际结果判断 |
| E003完整实现 | route自然失败，245279重叠节点、248289拥塞失败信号 |

E001快速验证、E002综合与物理入口适配为前置历史；不将局部功能通过或先前综合成功解释为全系统/板级验收。

<!-- research-agent:identity-index:begin -->
## Registered identities

This index records identity and links only. Execution, conclusions and user decisions remain in the linked records.

| Mission | Title | Contract | Summary |
|---|---|---|---|
| M001 | clean_project_migration | [contract](../mission/M001_clean_project_migration/contract.md) | [summary](../results/missions/M001_summary.md) |
| M002 | ddr_separation_and_timing_recovery | [contract](../mission/M002_ddr_separation_and_timing_recovery/contract.md) | [summary](../results/missions/M002_summary.md) |
<!-- research-agent:identity-index:end -->
