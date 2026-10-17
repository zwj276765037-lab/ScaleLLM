# E002：阶段结果

**正式综合、OPT、物理入口适配及完整pre_place已完成；本轮布局因时间上限结束，未取得完整物理基线。** 最后一次AT009于2026-10-15 11:41:11 UTC结束，无完整place/physopt DCP、无遗留任务进程；按合同停止重复place，独立physopt/route均NOT_RUN。当前无活动EDA，方法可行性结论inconclusive。

| 板级资源 | 正式综合 | OPT / debug（未布局） |
| --- | --- | --- |
| LUT | 841576（71.18%） | 828255（70.06%） |
| FF | 1029313（43.53%） | 1021363（43.20%） |
| DSP | 5451（79.69%） | 5451（79.69%） |
| BRAM tiles | 945（43.75%） | 941（43.56%） |
| URAM | 752（78.33%） | 752（78.33%） |

正式综合R001/AT002于02:44:24 UTC完整结束：22 OOC及top、exit0、114.28分钟、峰值树RSS27.06GiB。339个输入/45个DCP路径身份已冻结。[综合事实](runs/R001/synthesis_stage_facts.json)。聚合资源未超不代表物理可实现。

真实OPT命令完成并取得DCP，后继未重跑综合/OPT。黑盒1→0、no_clock530→0、内部未约束554→0；3个reset IO缺delay保留分类。未布局OPT/debug时序WNS+0.904ns/TNS0、WHS−0.814ns/THS−48989.652ns、992151个hold失败端点；WPWS−0.012ns/TPWS−0.037ns、PW栏目5项失败，最差代表是PCIe Max Skew，不把全部5项归为同类。timing FAIL；默认DRC15914项均warning，无error/critical。[真实时序](../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/timing_debug_materialized.rpt)。

入口适配AT011的102项CPU及完整真实组合门通过；实际7条async/4条原AUX/3条HostSplit、14份primitive导出、完整相关fanout及688个BRAM写端口clock证据支持限定诊断继续。7条async INIT1符合XPM源，原检查预期一直正确；本轮修复的是导出默认参数、同FF C→Q归一化、有效极性和双时钟BRAM端口判读，未改生产RTL。8项Critical CDC仅限精确分类，正式reset/CDC安全OPEN；相对INIT为4保留、2旧source移除、4新增身份。辅助枚举上限保留，debug阶段未运行辅助枚举不等于限制消失。OPT本身自动实现debug；显式调用确认already implemented。实际hub输入/两输出/530 C均50MHz，有效scope无3.333ns残留。[门验证](runs/R002/attempts/AT011_auxiliary_cdc_full_gate_cpu/status.json)、[架构评判](runs/R005/architecture_review.md)、[复位源核查](runs/R005/reset_warning_review.md)。

AT008在原两小时上限结束，124/native−15，无遗留；最后完成细化Phase3.3，无完整place/physopt产物。其完成的debug DCP（397261751 bytes，SHA e58d8970…8fc44e）及完整pre_place为一次恢复提供有效父点。AT012新增13项恢复测试与重跑6项隔离测试通过，96项未变legacy仅复用；真实完整POST回放及父链通过，入口已安装。[恢复验证](runs/R002/attempts/AT012_post_debug_pre_place_recovery_cpu/status.json)。原失败及完整历史保留。

AT009从同debug DCP恢复，open_checkpoint耗时8分16秒，新的live guard native0/166秒，零黑盒/DRC blockers、内部clock及未约束端点均0，hub全链匹配。启动至pre_place回执实测748.398秒，AT008同口径2629.541秒，减少1881.143秒（31分21秒）；回执写入时剩107分31.6秒，不是精确place命令起点。[成本与恢复事实](runs/R003/attempts/AT009_completed_pre_place_recovery_place_physopt/pre_place_restored_facts.json)。成本改进真实成立，但不能据此预言整体物理完成。

**AT009终态：**09:41:02.527929–11:41:11.046467 UTC，原7200秒wall timeout，managed124/native−15，峰值树RSS32.278GiB，7个PID/start_ticks均退出；终止回收约8.5秒不等于批准延时。全局与细化布局已给checksum，最后完整子阶段4.1.1.2 BUFG Replication；末行4.1.1.3 Post Placement Timing Optimization仍未完成。无place/physopt成功回执或DCP，内存部分进度不能恢复。主控与A007各自核13项小文件身份并确认无存活进程。[终态事实](runs/R003/attempts/AT009_completed_pre_place_recovery_place_physopt/terminal_facts.json)。该状态只证明本次成本边界未达成，不反驳算法或证明总体不可布。

布局内部优化中间估计WNS−1.884ns/TNS−1349.388ns，没有对应完整clock pair/hold/PW报告，不是完成placed结果，也不能与OPT正值直接宣称同一路径退化。10个BUFG插入候选全部因placement/routing conflicts跳过，后续复制候选0；这不是route_design失败或全部负slack根因证明。[中间事实](runs/R003/attempts/AT009_completed_pre_place_recovery_place_physopt/post_place_bufg_opt_intermediate_facts.json)。

USER_SLL_REG忽略告警100条可见对象与AT008相同，仍有抑制，完整影响数未知；不能据样本排除DDR1。两条Place30-1995为DDR1 c0_riu_clk/u_bufg_divClk_0的水平BUFCE_ROW delay控制值上限4，用于PLL/RIU Max Skew约束，不是4ns或两个违例；旧OPT样本正slack不能替代新物理结果，PCIe−0.012ns属于不同规则。[SLR事实](runs/R003/attempts/AT009_completed_pre_place_recovery_place_physopt/place_30_1229_warning_facts.json)、[DDR1告警](runs/R003/attempts/AT009_completed_pre_place_recovery_place_physopt/place_30_1995_warning_facts.json)。

按合同，无新完整物理点则不再place。仅补缺失POST/physopt的候选只做静态审核，未测试、未安装、未执行；没有合法新父点，route NOT_RUN。[R004](runs/R004/worker_report.md)、[最终架构评判§5.33](runs/R005/architecture_review.md)。后续若另立实验，优先取得closed DCP及完整时序/拥塞/SLR报告，再核控制广播局部性等可证伪假设，不在本轮扩大预算或改架构。

5份已清理worker OOC XDC原字节缺失、debug 300MHz元数据与功能未验证、XPM局部valid导出不兼容、18-401约束告警仍保留。正式reset/CDC/重汇合及事务安全、历史29条reset warning、完整SmartConnect事务、32层数值和板级验收未完成；本轮无bitstream/板卡/GPU/PPL/ACC。


---
Published: 2026-10-15T11:48:00.996477+00:00
Publication: Pf5009f41992446088a038a4b3c757e99
