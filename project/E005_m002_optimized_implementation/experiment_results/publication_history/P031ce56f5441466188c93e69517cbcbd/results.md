# E005：新综合与OPT完成，物理入口修复接续中

Attention AT001与生产Down/Gate AT003局部功能通过：原版逐拍与独立oracle均PASS，3个生产RTL保持冻结；[功能事实](runs/R001/rtl_functional_final_facts.json)。179项入口检查通过，新create成功。新综合原生自然0，真实80个局部控制逐项符合设计，LUT841576→828763（−12813，同Synthesized阶段）。恢复closure/342源/45DCP已绑定，164项补充CPU通过，A007集中独立复核完成；原综合监督/leader wait UNKNOWN及2097.384826秒观测缺口保留。[综合阶段审核](runs/R005/synthesis_stage_review_facts.json)。

R004/AT001于02:46:43→04:15:48 UTC真实执行新物理入口，INIT完整POST完成，原生opt_design成功且0 Errors，生成新opt.dcp。之后POST因 `native project mode has no qualified explicit pre-place debug admission` 自然失败，native/监督均1、stop_reason=null、无残留。没有执行place/physopt/route；该次失败与OPT成功分开记录。[原终态](runs/R004/attempts/AT001_fresh_place_physopt/status.json)。

新OPT检查点218327530字节，SHA256 `af634c358eecf869c83cb45c0755d0164b39d5a9f5aed316bcaa52cd3c02919e`，器件/top/板卡/工具身份吻合。[检查点观察](runs/R004/attempts/AT001_fresh_place_physopt/new_OPT_checkpoint_observation.json)。OPT资源：LUT815443（68.97%）、CLB Registers1021366（43.20%）、BRAM941、URAM752、DSP5451；时序WNS+0.904ns/TNS0，WHS−0.814ns/THS−48990.676ns，WPWS−0.012ns，FAIL且仅布线前估计。[资源与时序事实](runs/R004/attempts/AT001_fresh_place_physopt/completed_OPT_timing_resources_observation.json)。新OPT内部缺时钟及未约束端点均0，critical CDC8；当前图完整分类及正式安全仍待后续核验。

两PHY、调试核本次实际生成与来源已保全。XPM两条18-401告警与旧同阶段端点/出处一致，合法端点实际覆盖仍按新图检查。PHY worker实际禁用缓存、produced/result成对一致；主日志同时有cache消息，但未观测到第三磁盘cache副本。首次模板cache_writes误述已追加更正并保留原证据，不作为实测。当前工具正常自然结束，没有墙钟/无输出强停，峰值树RSS约32.68GiB；142项活动输入在原运行中保持冻结。

A006按已授权普通修复安装窄来源入口并回归，从本次新OPT恢复显式debug和布局前检查，显式采用SSI_SpreadSLLs，后续Default独立physopt及完整route；不重复成功综合/INIT/OPT。恢复草稿验证不冒充已安装入口或实际物理通过，原failed POST不改写为成功父点。A007继续集中审核新来源与当前图。合法布通、物理时序与CDC/reset安全尚未通过。


---
Published: 2026-10-16T04:18:02.143054+00:00
Publication: Pb14a7d4c1aff4c1bb085761c63171e52
