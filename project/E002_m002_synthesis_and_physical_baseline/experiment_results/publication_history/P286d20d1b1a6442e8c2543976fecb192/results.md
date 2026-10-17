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

剩余实际准入缺口：双时钟BRAM写使能需按具体端口核对所属clock。旧图把整颗RAM两时钟合并，不能据此判跨域直达，也不能仅因集合含UI就放行。工程先在完整现有数据上做离线资格回归，再补最小实际取证；不会重综合/重OPT。

证据限制：5份工具已清理的debug worker OOC XDC原bytes/hash缺失；已归档OPT嵌入有效XDC及生成身份，不能称完整源重现。历史29条reset warning、同域多release/重汇合、完整SmartConnect事务及32层数值仍未全局验收。A004的局部证明不泛化为系统安全。所有失败原记录保留，历史过程见publication_history及各AT。


---
Published: 2026-10-15T06:42:29.096485+00:00
Publication: P31b3132421f140b6baf26e8bc84cb460
