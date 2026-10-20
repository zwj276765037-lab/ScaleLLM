

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-20T08:57:35.240611+00:00。来源修订：`cfb9c0cd3fc1`。

# E006 · m002_slr1_congestion_attribution

关联：M002 / SM010

## 原始管理记录

- [实验协议](experiment_source/protocol.md)
- [来源摘要](experiment_source/summary.md)
- [结果摘要](experiment_results/summary.md)
- [状态摘要](experiment_status/summary.md)

## 当前结果摘录

# E006：完整比较已结束，选择C01

R006 AT003于北京时间2026-10-17 12:45:04自然结束，六阶段与十一查询全部0；native0/supervisor0，无停止或清理。144生产输入、原DCP、12运行源及绑定依赖保持；12个原PID/start结束，项目EDA资源已释放。[工程终态](experiment_results/runs/R006/attempts/AT003_buffered_alias_directed_cut/terminal_summary.json)、[独立收尾](../../agent/A007/R006_AT003_native_stage_review_20261017/natural_terminal_review.json)。

主控接受独立推荐：**仅选择C01 SwiGLU的`g_row_branch[1].u_branch_leaf`迁往SLR2，开展E008完整implementation**。[集中候选判断](../../agent/A007/R006_AT003_native_stage_review_20261017/single_candidate_recommendation.md)、[实际执行绑定](../../.research-agent/decision_inputs/E006_R006_AT003_C01_selected_E008_execution_20261017.json)。支持的是有意义的定向物理实验，尚未证明减压、布通或时序收敛。

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

普通逻辑对仅排除clock/reset/constant，保留mixed/unknown；不是网数、SLL用量或拥塞实测。C01热点覆盖为C02的3.78倍、普通边界对少41.8%。其3072条输入data/select网形成6144对，出口945对中896连外部row-ring BRAM；控制仍与兄弟分支耦合。C02普通入口9572/出口2663对，与w4_frontend、down_scheduler及gate_scheduler连接广；不能将unknown

（摘录截断；完整记录见链接。）

## 每个运行批次

| 批次 | 详情 | 具体尝试数量 |
| --- | --- | --- |
| R001 | [本批结果与证据](experiment_results/runs/R001/README.md) | 1 |
| R002 | [本批结果与证据](experiment_results/runs/R002/README.md) | 0 |
| R003 | [本批结果与证据](experiment_results/runs/R003/README.md) | 1 |
| R004 | [本批结果与证据](experiment_results/runs/R004/README.md) | 1 |
| R005 | [本批结果与证据](experiment_results/runs/R005/README.md) | 3 |
| R006 | [本批结果与证据](experiment_results/runs/R006/README.md) | 3 |

## 原工程历史结果


本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
