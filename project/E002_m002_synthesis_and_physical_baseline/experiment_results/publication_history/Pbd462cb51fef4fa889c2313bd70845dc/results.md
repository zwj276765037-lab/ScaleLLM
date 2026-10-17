# E002：阶段结果

正式综合、OPT与完整pre_place已完成；AT008在细化布局期间达到原2小时上限，未生成完整place DCP。尚无完成布局、phys_opt或route结果；下表均为未布局资源。

| 板级资源 | 正式综合 | OPT / debug_materialized |
| --- | --- | --- |
| LUT | 841576（71.18%） | 828255（70.06%） |
| FF | 1029313（43.53%） | 1021363（43.20%） |
| DSP | 5451（79.69%） | 5451（79.69%） |
| BRAM tiles | 945（43.75%） | 941（43.56%） |
| URAM | 752（78.33%） | 752（78.33%） |

正式综合R001/AT002于2026-10-15 02:44:24 UTC结束，22个OOC及top完成、exit0、114.28分钟、峰值树RSS27.06GiB，无遗留。339输入/45 DCP身份已冻结。[综合事实](runs/R001/synthesis_stage_facts.json)。

真实opt_design完成并取得DCP，后继复用同网表，不重复综合/OPT。黑盒1→0、no_clock530→0、内部未约束554→0；3个reset IO缺delay保留对象分类。OPT和debug_materialized未布局时序均为WNS +0.904ns/TNS0、WHS −0.814ns/THS −48989.652ns、992151个hold失败端点。PW栏目5项失败、WPWS −0.012ns、TPWS −0.037ns，最差代表为PCIe Max Skew；不能把全部5项归为同一类别。**timing FAIL**。OPT默认DRC15914项均warning，无error/critical。[时序原报告](../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/timing_debug_materialized.rpt)。

物理检查修复已通过[102项CPU与真实组合门](runs/R002/attempts/AT011_auxiliary_cdc_full_gate_cpu/status.json)。AT008实际OPT准入、显式implement_debug_core及新阶段完整pre_place通过：gate_issues=[]，7条async链/4条原AUX/3条HostSplit链、完整相关fanout及688个BRAM写端口clock均有实际取证。7条async INIT1符合XPM源，原检查预期一直正确；本轮修复涉及省略原语默认参数、同FF C→Q归一化、有效极性和BRAM端口clock判读，未改RTL。实际hub输入/两输出/530个C端点均50MHz，有效scoped约束无3.333ns残留。OPT本身已实现debug，显式调用确认already implemented；独立debug DCP为397261751 bytes、SHA e58d8970…8fc44e。[实际准入与DCP证据](../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/pre_place_evidence.json)。

8条Critical CDC仅归入classified_reset_cdc_diagnostic_only：相对INIT为4保留、2旧source移除、4新增身份（2 ready CDC10代表源变化、2同UI多同步分支CDC11）。四份定向报告3/3/1/1 Critical与全报告8元组一致；辅助对象枚举超过64的限制保留。新debug阶段没有重跑该辅助枚举，原字段not_limited的范围由[独立说明](runs/R003/attempts/AT008_complete_opt_gate_debug_place_physopt/auxiliary_cdc_scope_clarification.json)纠正，不能当作限制消失。正式reset/CDC安全仍OPEN。[架构审核§5.24–5.29](runs/R005/architecture_review.md)、[复位源核查§8](runs/R005/reset_warning_review.md)。

AT008已实际执行place_design，前置DRC两次0 Errors。08:22:43 UTC观察到Phase2.1.1.2 Clock Region Placement。出现Place30-1229：SLR分区无法满足部分USER_SLL_REG并忽略属性继续。不可变日志前缀保留100条可见warning及抑制提示，**不是完整受影响数量，也不能据样本断定仅DDR0受影响**。当前AXI Register Slice配置与vendor HDL提供属性来源；实际SLR位置、Laguna使用和时序影响待完成物理产物判断。[告警事实与日志身份](runs/R003/attempts/AT008_complete_opt_gate_debug_place_physopt/place_30_1229_warning_facts.json)。

AT008于09:08:31 UTC受控结束，managed124/native−15、stage_wall_timeout、owned_survivors=[]，峰值树RSS28.10GiB。最后完成Phase3.3 Area Swap，日志布局累计74分59秒；place/physopt命令完成回执和对应DCP均未生成，不能恢复部分细化布局进度。[原终态](runs/R003/attempts/AT008_complete_opt_gate_debug_place_physopt/status.json)。AT012恢复入口已安装：新增13项恢复测试与6项隔离测试本次通过，96项未变legacy明确复用AT011；真实AT008完整debug POST组合回放和最终父链通过。AT009于09:41:02 UTC实际启动，从已完成的debug/pre_place恢复，继承同DCP POST；恢复仍付open/live sanity/DRC成本。[恢复验证](runs/R002/attempts/AT012_post_debug_pre_place_recovery_cpu/status.json)、[实际启动](runs/R003/attempts/AT009_completed_pre_place_recovery_place_physopt/started.json)。原2小时尝试不延长，后继单次仍2小时，实际净节省和能否完成待测。若后继仍无新完整物理恢复点，不再重复place。失败尝试原终态、日志与后继资格分别保留，完整过程见各AT与publication_history。5份已清理debug-worker OOC XDC原bytes/hash缺失；hub300MHz元数据与调试功能未验证；XPM局部valid导出选项不兼容、18-401及约束安全仍OPEN。历史29条reset warning、完整SmartConnect事务、32层数值和板级验收未全局闭合，局部结构证据不等于全系统安全。


---
Published: 2026-10-15T09:43:53.638057+00:00
Publication: P24a363f1444849fab79163b59d71875f
