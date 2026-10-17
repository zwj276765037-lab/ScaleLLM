# ScaleLLM：审核总览

当前任务为SM012/E008：**已选择C01 SwiGLU branch[1]迁往SLR2，并于北京时间2026-10-17 12:50:44实际启动R001/AT001完整implementation**。当前恢复E005正式父网表、进入布局前流程；尚无新place/physopt/route成功结果。

E006 R006 AT003于北京时间12:45:04自然成功，六阶段全部通过、native0/supervisor0；25项工程收尾与独立终态核验完成。C01热点成员8697、C02为2303；普通已定位边界逻辑对7124 vs12235。独立审核支持本轮仅选择C01进行单变量物理实验，不承诺一次布通。[完整比较](../project/E006_m002_slr1_congestion_attribution/experiment_results/summary.md)、[候选判断](../agent/A007/R006_AT003_native_stage_review_20261017/single_candidate_recommendation.md)。

E008使用3cae已审入口，35份实际运行源、144生产输入和本项目唯一EDA占用已核；启动亦经独立审核。只改变选定模块的SLR2位置要求，完整pre-place资格→SSI_SpreadSLLs place→Default physopt→Default route连续执行。[实际状态](../project/E008_m002_exact_hotspot_offload_implementation/experiment_status/summary.md)、[启动事实](../project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT001_C01_slr2_offload_full_implementation/native_start_verified.json)、[启动独立审核](../agent/A007/E008_R001_AT001_actual_stage_review_20261017/start_review.md)。

C01父图输入hold−0.128ns、SLR2 CLB93.07%和MUX/DSP/BRAM打包是未验证风险；源站点多与组外共享，不能承诺全部释放。原physopt有界时序不是迁移后时序，逻辑连接对不是实测SLL。实际落区、局部压力、合法布通、setup/hold/PW及CDC/reset/IO分别验收。

单EDA与资源保护、正常无墙钟/无输出强停保持；此前单次停止许可均已使用。RTL/IP、Hadamard、ScaleCode、format05、ABI和时钟不变；无bitstream/GPU/板卡/PPL/ACC，旧工程只读、旧会话不重绑。进程由本次实际监督器管理，文档状态不是实时心跳，未另设跨会话通知服务。

基线为VCU118 / xcvu9p-flga2104-2L-e、Vivado2025.2，core100MHz、双DDR UI200MHz；Attention→DDR0、MLP→DDR1。唯一实现入口为project/hardware与project/software。

E005已结束：同physopt阶段LUT814935→801751、CLB站点99.11%→97.31%、setup WNS−1.290→+0.103ns，但hold WHS−0.695ns失败；route出现1148579重叠节点、758463拥塞失败信号，未合法布通。SLR0/1/2 CLB99.00%/99.85%/93.07%。这些指标为不同层面的观测，不证明候选卸载必然解决根因。[E005结果](../project/E005_m002_optimized_implementation/experiment_results/summary.md)、[SM009审核](reviews/SM009.md)。

固定窗口原生拥塞UNAVAILABLE；占用不是拥塞实测。正式routed时序、CDC/reset/release/transaction/外部IO安全、端到端数值和板级验收仍未完成。历史阶段原文与本次更新前正文保存于.research-agent/manual_status_history，原运行证据保持。
