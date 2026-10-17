# E002：阶段结果

正式综合与OPT网表已取得，尚无place/route结果。以下数值为未布局估计，不能作为物理收敛或板级验收。

| 板级资源 | 正式综合 | OPT后 |
| --- | --- | --- |
| LUT | 841576（71.18%） | 828255（70.06%） |
| FF | 1029313（43.53%） | 1021363（43.20%） |
| DSP | 5451（79.69%） | 5451（79.69%） |
| BRAM tiles | 945（43.75%） | 941（43.56%） |
| URAM | 752（78.33%） | 752（78.33%） |

综合R001/AT002于2026-10-15 02:44:24 UTC完成，22个OOC及top全部结束，exit0、114.28分钟、峰值树RSS27.06GiB、无遗留。339输入/45 DCP身份冻结。[综合事实](runs/R001/synthesis_stage_facts.json) / [终态](runs/R001/attempts/AT002_fresh_synth/status.json)。

R003/AT004的真实opt_design成功（37分32秒），218404246-byte DCP已保存。黑盒1→0、no_clock530→0、内部未约束554→0；3个reset IO缺delay仍按对象分类。OPT时序WNS+0.904ns/TNS0，WHS−0.814ns/THS−48989.652ns、992151个hold失败端点；PW栏目WPWS−0.012ns/TPWS−0.037ns、5项失败，最差为PCIe Max Skew。timing FAIL。默认DRC15914项均warning，无error/critical。[OPT事实](runs/R003/attempts/AT004_complete_recovery_preflight_opt_place_physopt/opt_command_facts.json) / [时序](../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/timing_opt.rpt)。

AT004在place前受控终止（125/native−15），完整POST未完成。原瞬时survivor记录与事后31个PID身份全部退出的核验分别保留。AT005从该OPT恢复并重存397273730-byte DCP，不重跑OPT；完成14份报告，资源/时序相同。实际hub输入、两输出和530个C端点均同50MHz/mmcm_clkout5_1，源MMCM/BUFG及网络一致，无3.333ns输出残留。hub参数仍300MHz，调试功能未验证。OPT本身已自动实现debug；保留原生显式调用作为独立pre_place阶段，不能声称OPT缺少实现能力。[架构审核§5.17–5.23](runs/R005/architecture_review.md)。

AT005退出1，仅未知CDC门失败：实际8条Critical；相对INIT为4条保留、2条旧source移除、4条新增身份（2个ready CDC10代表source变化、2个同UI多同步分支CDC11）。已明确限定诊断准入，最终reset/CDC安全仍OPEN。

AT006于06:18:56–06:34:16 UTC从同OPT恢复，原门失败退出1、无资源中止/遗留，未显式debug或place。取得119909158-byte完整复位图、14份实际原语导出与定向CDC/扇出证据。[原终态](runs/R003/attempts/AT006_cdc_reset_proof_debug_place_physopt/status.json)。审核确认7条异步链INIT1符合XPM源，4条原AUX及3条HostSplit链INIT0；ready输入/末Q/最终AND和两DDR base的有效极性均未见矛盾。工具导出省略的原语参数可依据同安装权威默认值解释，不能把任意空属性当0。当前修复为检查器参数解析、launch C至同FF Q归一化及有效极性/别名判读，未修改RTL。[复位专项§8](runs/R005/reset_warning_review.md)。

AT007于06:53:52–07:05:03 UTC恢复同OPT，取得88个BRAM的688个WEBWE→同cell CLKBWRCLK实际时钟；独立核验全部分别属于对应UI，无缺项/错pin/错clock。原gate仅余4个已知辅助对象枚举上限，因此原native/managed1及无survivors终态保留，未debug/place。[AT007终态](runs/R003/attempts/AT007_bram_port_clock_debug_place_physopt/status.json)。这4项均由clock-pair对象数量超过64产生，不是工具API错误；其4份完整小报告为3/3/1/1 Critical，共8个唯一元组，与完整报告精确相等。辅助对象属性coverage_limited保留，其他未知/新增路径仍拒绝。

[R002/AT011完整真实组合资格](runs/R002/attempts/AT011_auxiliary_cdc_full_gate_cpu/actual_combined_status.json)已PASS：gate_issues=[]、14链结构/完整fanout/688实际端口均通过，8项标classified_reset_cdc_diagnostic_only；正式reset/CDC安全仍OPEN。最终[102项CPU](runs/R002/attempts/AT011_auxiliary_cdc_full_gate_cpu/status.json)通过，包含受影响负例、完整实际组合门及AT007递归父链验证。R003/AT008于07:08:25 UTC实际启动，从同OPT恢复并复用全部同身份完成报告/图/端口证据，当前尚未place；显式debug及后续阶段各自取证，不将离线准入冒充物理完成。[启动记录](runs/R003/attempts/AT008_complete_opt_gate_debug_place_physopt/started.json)。

证据限制：5份工具已清理的debug worker OOC XDC原bytes/hash缺失；已归档OPT嵌入有效XDC及生成身份，不能称完整源重现。历史29条reset warning、同域多release/重汇合、完整SmartConnect事务及32层数值仍未全局验收。A004的局部证明不泛化为系统安全。所有失败原记录保留，历史过程见publication_history及各AT。


---
Published: 2026-10-15T07:10:04.706421+00:00
Publication: P4304343e5f4f45078632a8bdc496af6e
