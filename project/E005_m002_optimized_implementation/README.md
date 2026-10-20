

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-20T08:57:35.240611+00:00。来源修订：`cfb9c0cd3fc1`。

# E005 · m002_optimized_implementation

关联：M002 / SM009

## 原始管理记录

- [实验协议](experiment_source/protocol.md)
- [来源摘要](experiment_source/summary.md)
- [结果摘要](experiment_results/summary.md)
- [状态摘要](experiment_status/summary.md)

## 当前结果摘录

# E005：完整implementation失败，证据交付完成

**当前组合未合法布通。** R004/AT004于2026-10-16 13:56:35.660913 UTC自然结束，native/监督均1、stop_reason=null，无墙钟、无输出或资源强停。失败DCP及诊断已保存，成功route DCP、完整成功POST和成功父链未取得。R006/AT002与AT003只读补采均自然0/0完成；最后AT003于15:11:38.117704 UTC结束，实际结果和终态已通过独立审核。 实验执行记failed，方法判断inconclusive；内部复核完成不替代用户验收，M002全局目标仍未完成。

## 同阶段关键结果

| 指标与阶段 | E003 | E005 |
| --- | ---: | ---: |
| Phase9重叠路由节点 | 245279 | 1148579 |
| Route35-162拥塞失败信号 | 248289 | 758463 |
| 末期North/South最大拥塞 (%) | 85.471 / 86.437 | 116.672 / 100.013 |
| 末期East/West最大拥塞 (%) | 86.551 / 87.3848 | 102.451 / 112.353 |
| 末期四方向effective congestion level | 6 | 7 |
| physopt CLB LUTs | 814935 | 801751 |
| physopt CLB站点占用 | 146472 / 99.11% | 143802 / 97.31% |
| physopt SLLs Used | 18282 | 18983 |
| physopt setup WNS/TNS (ns) | −1.290 / −762.165 | +0.103 / 0 |
| physopt hold WHS/THS (ns) | −0.620 / −2150.556 | −0.695 / −2145.408 |

节点、信号、SLL使用和跨SLR叶pin是不同口径。两次末期拥塞threshold均0.85、窗口标签64×64，不能与placed Level6或初始%Tiles混比。新route_status为routable2031772、fully_routed1273309、errors/conflicts各758463；Phase8零未布/部分布线不能推翻Phase9合法性FAIL。[布线同阶段审核](experiment_results/runs/R005/AT004_phase9_failure_same_stage_review_evidence.json)、[physopt审核](experiment_results/runs/R005/AT003_completed_physopt_POST_parent_review_evidence.json)。

失败图WNS−13.528/TNS−1920757.000ns、WHS−0.258/THS−468.768ns、WPWS−0.537/TPWS−3.018ns仅作诊断，不是合法routed签核，也无旧E003同类完整失败图可比。失败DRC的RTSTAT-13明确指出路由不足、部分检查未运行；报告命令code0不是DRC通过。

##

（摘录截断；完整记录见链接。）

## 每个运行批次

| 批次 | 详情 | 具体尝试数量 |
| --- | --- | --- |
| R001 | [本批结果与证据](experiment_results/runs/R001/README.md) | 4 |
| R002 | [本批结果与证据](experiment_results/runs/R002/README.md) | 10 |
| R003 | [本批结果与证据](experiment_results/runs/R003/README.md) | 1 |
| R004 | [本批结果与证据](experiment_results/runs/R004/README.md) | 4 |
| R005 | [本批结果与证据](experiment_results/runs/R005/README.md) | 0 |
| R006 | [本批结果与证据](experiment_results/runs/R006/README.md) | 3 |

## 原工程历史结果


本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
