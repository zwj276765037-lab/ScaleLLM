# E005：SSI布局命令成功，完整布局报告生成中

Attention AT001及生产Gate/Down AT003局部功能通过，覆盖原版逐拍比较与独立oracle；三处生产RTL保持冻结。[功能事实](runs/R001/rtl_functional_final_facts.json)。新create与正式综合自然成功，80个局部控制逐项符合预期；同Synthesized阶段LUT841576→828763（减少12813），BRAM/URAM/DSP保持。342输入与45DCP恢复父链已绑定。[综合审核](runs/R005/synthesis_stage_review_facts.json)。原综合监督/leader wait UNKNOWN与2097.384826秒资源观测缺口保留，原wrapper真实native/exit0单独有证据。

新原生OPT与AT003完整debug POST/pre_place已完成。新debug DCP396068466字节；新图reset/fanout与688BRAM时钟端点有资格，gate_issues为空，黑盒/内部no_clock/未约束端点均0，8条Critical完成诊断分类、新未分类0。[布局前事实](runs/R004/attempts/AT003_current_CDC_bound_OPT_place_physopt/completed_debug_pre_place_facts.json)、[独立审核](runs/R005/AT003_completed_debug_pre_place_review_evidence.json)。显式implement_debug_core返回0且工具报告already implemented；raw verified0、声明300MHz/实际50MHz、vendor异常约束及外部IO缺delay仍保留。正式安全OPEN；该阶段WNS+0.904、WHS−0.814、WPWS−0.012ns，hold/PW FAIL。

**实际SSI_SpreadSLLs布局命令已成功返回0**，起止epoch1792128495→1792136882，耗时8387秒（2小时19分47秒），原生日志0 Errors。07:48:44 UTC观察时正在写新place DCP；完整place POST、80边界及实际拥塞/时序/CDC检查尚未闭合，独立physopt和route尚未执行。[原生命令事实](runs/R004/attempts/AT003_current_CDC_bound_OPT_place_physopt/place_native_command_success_observation.json)。这只证明布局命令成功，不能等同完整物理验收或已布通。

本次出现Place46-14高拥塞告警，风险保持，实际窗口与资源比较待新报告。[风险原文](runs/R004/attempts/AT003_current_CDC_bound_OPT_place_physopt/place_congestion_risk_observation.json)。布局内部还报告MLP branch1 ingress pointer的2067/1632个负载中只有133/103可作为该扇出优化候选，受约束或macro限制；这属于剩余网络观察，不能与80局部边界效果混为一项。[实际观察](runs/R004/attempts/AT003_current_CDC_bound_OPT_place_physopt/place_internal_remaining_fanout_observation.json)。布局内部临时时序不作为最终placed/routed时序。

AT001缺显式debug入口及AT002旧CDC报告固定hash造成的自然失败均保留。修复后219项CPU回归通过；同OPT实际图严格重核支持接续，原failed integrity及OPT对象枚举coverage_limited未改写。当前debug新图没有执行同一aux对象枚举，not_limited不能解释为枚举完整。[回归事实](runs/R002/attempts/AT010_current_CDC_recovery_cpu/completion_facts.json)。

当前唯一EDA继续完整place POST、Default独立physopt。按[报告覆盖审核](runs/R005/AT003_frozen_physical_reporting_coverage.json)，自然阶段闭合后从准确closed DCP最小只读补充固定旧窗口、目标跨SLR和层次利用率；不热改、不重做布局。结构/资源/约束合法后继续一次完整Default route，负时序或高拥塞风险本身不新增审批门。合法布通、时序收敛与正式CDC/reset安全分别验收；本轮无bitstream/板卡/GPU/PPL/ACC。


---
Published: 2026-10-16T07:50:30.805003+00:00
Publication: P3046cd8ea04844fd9ab67b9d204cf7ae
