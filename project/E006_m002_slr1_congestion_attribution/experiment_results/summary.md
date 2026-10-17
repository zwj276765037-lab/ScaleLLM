# E006：完整比较已结束，选择C01

R006 AT003于北京时间2026-10-17 12:45:04自然结束，六阶段与十一查询全部0；native0/supervisor0，无停止或清理。144生产输入、原DCP、12运行源及绑定依赖保持；12个原PID/start结束，项目EDA资源已释放。[工程终态](runs/R006/attempts/AT003_buffered_alias_directed_cut/terminal_summary.json)、[独立收尾](../../../agent/A007/R006_AT003_native_stage_review_20261017/natural_terminal_review.json)。

主控接受独立推荐：**仅选择C01 SwiGLU的`g_row_branch[1].u_branch_leaf`迁往SLR2，开展E008完整implementation**。[集中候选判断](../../../agent/A007/R006_AT003_native_stage_review_20261017/single_candidate_recommendation.md)、[实际执行绑定](../../../.research-agent/decision_inputs/E006_R006_AT003_C01_selected_E008_execution_20261017.json)。支持的是有意义的定向物理实验，尚未证明减压、布通或时序收敛。

| 比较项 | C01（选择） | C02（保留） |
| --- | ---: | ---: |
| 热点S成员交集（复用R004） | 8697 | 2303 |
| LUT / FF（复用R004） | 1890 / 6317 | 3348 / 3557 |
| BRAM36 / DSP（复用R004） | 6 / 2 | 0 / 0 |
| 实际P（复用R004，原全在SLR1） | 9491 | 7257 |
| 完整canonical nets | 14307 | 10317 |
| ingress / egress nets | 3087 / 55 | 2998 / 1795 |
| 全部边界driver-load对 | 21479 | 19325 |
| 普通已定位边界逻辑对 | 7124 | 12235 |
| ingress setup / hold（ns） | +1.416 / −0.128 | +2.537 / −0.055 |
| egress setup / hold（ns） | +1.848 / +0.035 | +2.537 / −0.027 |

普通逻辑对仅排除clock/reset/constant，保留mixed/unknown；不是网数、SLL用量或拥塞实测。C01热点覆盖为C02的3.78倍、普通边界对少41.8%。其3072条输入data/select网形成6144对，出口945对中896连外部row-ring BRAM；控制仍与兄弟分支耦合。C02普通入口9572/出口2663对，与w4_frontend、down_scheduler及gate_scheduler连接广；不能将unknown分类当作零数据成本。[C01实际cut](runs/R006/attempts/AT003_buffered_alias_directed_cut/candidate_C01_directed_cut_closed_facts.json)、[C02实际cut与时序独立核查](../../../agent/A007/R006_AT003_native_stage_review_20261017/C02_cut_timing_review.json)。

C01负hold、双向最差setup路径超过94%的网络延迟、SLR2 CLB占用93.07%及MUX/DSP/BRAM打包仍是风险。源CLB大多与组外共享，触及站点不等于可释放站点；未放置驱动不按零成本。时序来自原physopt估计图，非迁移后或route签核。原40条失败样本交集C01为0/C02为3，仅是有限样本关联。固定窗原生拥塞仍UNAVAILABLE。

缓冲日志修复后C01完整本地映射27.893s（R005为27.597s，AT002为2448.378s）；七语义账本逐字节一致、167160事件sidecar完整flush。这只证明局部阶段恢复。原R001/R004/R005及R006 AT002受控部分证据、AT001/AT002技术失败均保留，停止许可均已使用，不扩大到后继正常实现。


---
Published: 2026-10-17T04:51:34.492335+00:00
Publication: P124524e4d3404c68bd13aa4db86ab57d
