

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-18T00:06:15.625771+00:00。来源修订：`943abfac7fc3`。

# E002 · m002_synthesis_and_physical_baseline

关联：M002 / SM005

## 原始管理记录

- [实验协议](experiment_source/protocol.md)
- [来源摘要](experiment_source/summary.md)
- [结果摘要](experiment_results/summary.md)
- [状态摘要](experiment_status/summary.md)

## 当前结果摘录

# E002：阶段结果

**正式综合、OPT、物理入口适配及完整pre_place已完成；本轮布局因时间上限结束，未取得完整物理基线。** 最后一次AT009于2026-10-15 11:41:11 UTC结束，无完整place/physopt DCP、无遗留任务进程；按合同停止重复place，独立physopt/route均NOT_RUN。当前无活动EDA，方法可行性结论inconclusive。

| 板级资源 | 正式综合 | OPT / debug（未布局） |
| --- | --- | --- |
| LUT | 841576（71.18%） | 828255（70.06%） |
| FF | 1029313（43.53%） | 1021363（43.20%） |
| DSP | 5451（79.69%） | 5451（79.69%） |
| BRAM tiles | 945（43.75%） | 941（43.56%） |
| URAM | 752（78.33%） | 752（78.33%） |

正式综合R001/AT002于02:44:24 UTC完整结束：22 OOC及top、exit0、114.28分钟、峰值树RSS27.06GiB。339个输入/45个DCP路径身份已冻结。[综合事实](experiment_results/runs/R001/synthesis_stage_facts.json)。聚合资源未超不代表物理可实现。

真实OPT命令完成并取得DCP，后继未重跑综合/OPT。黑盒1→0、no_clock530→0、内部未约束554→0；3个reset IO缺delay保留分类。未布局OPT/debug时序WNS+0.904ns/TNS0、WHS−0.814ns/THS−48989.652ns、992151个hold失败端点；WPWS−0.012ns/TPWS−0.037ns、PW栏目5项失败，最差代表是PCIe Max Skew，不把全部5项归为同类。timing FAIL；默认DRC15914项均warning，无error/critical。[真实时序](../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/timing_debug_materialized.rpt)。

入口适配AT011的102项CPU及完整真实组合门通过；实际7条async/4条原AUX/3条HostSplit、14份primitive导出、完整相关fanout及688个BRAM写端口clock证据支持限定诊断继续。7条async INIT1符合XPM源，原检查预期一直正确；本轮修复的是导出默认参数、同FF C→Q归一化、有效极性和双时钟BRAM端口判读，未改生产RTL。8项Critical CDC仅限精确分类，正式reset/CDC安全OPEN；相对INIT为4保留、2旧source移除、4新增身份。辅助枚举上限保留，debug阶段未运行辅助枚举不等于限制消失。OPT本身自动实现debug；显式调用确认already implemented。实际hub输入/两输出/530 C均50MHz，有效scope无3.333ns残留。[门验证](runs/R00

（摘录截断；完整记录见链接。）

## 每个运行批次

| 批次 | 详情 | 具体尝试数量 |
| --- | --- | --- |
| R001 | [本批结果与证据](experiment_results/runs/R001/README.md) | 2 |
| R002 | [本批结果与证据](experiment_results/runs/R002/README.md) | 12 |
| R003 | [本批结果与证据](experiment_results/runs/R003/README.md) | 9 |
| R004 | [本批结果与证据](experiment_results/runs/R004/README.md) | 0 |
| R005 | [本批结果与证据](experiment_results/runs/R005/README.md) | 0 |

## 原工程历史结果


本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
