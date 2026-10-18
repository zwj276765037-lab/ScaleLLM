# E008：用户PDU停机暂停，AT003已真实停止

**按用户服务器关机更换PDU要求，AT003已于2026-10-17T08:44:09.782954Z（北京时间16:44:09）真实停止。** 08:44:00.987566Z核对本任务PID/start后向supervisor发SIGTERM，现有监督器清理全部归属子树。native−15/supervisor125，停止原因signal15；无owner存活、EDA锁释放，14项收尾全通过。144生产输入、39归档源、消费包及原合同保持。两个只读观察器真实exit0，无自动重试、新AT或新checkpoint请求。[停止总证据](runs/R001/attempts/AT003_C01_physical_xdc_fix_full_implementation/user_PDU_stop_closeout_20261017.json)。

停止前完整restored pre-place已实际通过并独立接受：成员RAW9514/S9507/P9491、原策略前后字节同、唯一SLR2 hard Pblock/9491成员与78266站点、真实物理XDC、269完整端口索引及有向cut/timing均闭合。175约束与144输入、39源和162metadata已核；80保护边界的preplace证据明确继承旧synth/父place/physopt，本轮POST尚未到达。正式reset/CDC/IO仍OPEN。[完整preplace](runs/R001/attempts/AT003_C01_physical_xdc_fix_full_implementation/pre_place_closed_stage_facts.json)、[独立全门审核](../../../agent/A007/E008_R001_AT003_actual_stage_review_20261017/restored_pre_place_global_review.json)。

place已实际进入Phase1.3模型构建，按用户要求中断；place未完成，physopt/route未执行。本AT没有新DCP，无法从中途place恢复。同C01合法重启父仍为原debug_materialized.dcp（396068466B/8451b2a86885d5ebb7bcb58dc24c352ac442492425c174269f9a803bb39c202f），用户恢复后须新AT重新加载和资格，再重做place→physopt→route。E005基线physopt.dcp保留，但不能替代本次迁移过程。[工程续接说明](runs/R001/attempts/AT003_C01_physical_xdc_fix_full_implementation/PDU_resume_readme.md)。

C01方法未评估，未声称卸载生效、布通、时序或签核完成。原AT001/AT002入口自然失败与最小修复证据保留；AT003的非零退出是用户停机，不作方法失败。未布局有界入setup/hold+6.158/−0.074、出+6.859/+0.081ns，仅through LOAD集合各max/min16；返回路径不保证每条跨cut边，不作跨阶段改善、全cutTNS或routed timing结论。


---
Published: 2026-10-17T08:47:06.796853+00:00
Publication: P855dd1d321d6401cbfcb4f6fbac367b5
