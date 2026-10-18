# E008：AT004完整preplace通过，真实place运行中

用户明确“可以继续了”后，AT004_C01_PDU_resume_full_implementation已于2026-10-17T09:23:05.136988Z（北京时间17:23:05）真实启动。[原生启动事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/native_start_verified.json)：39归档源匹配b9dc、144生产输入保持、父DCP8451匹配，supervisor14547/start69484、native14680/start70786，CPU0–7/nice5与唯一项目EDA/锁一致。09:32Z父图恢复及成员子步骤已闭合并[独立增量接受](../../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/pre_place_membership_incremental_review.json)：10份账本与AT003字节同，RAW9514/S9507/P9491、16内部DSP→2父、全P未布局；仅3个actual artifact身份重绑。09:44Z新原生资源/before策略/硬Pblock与真实XDC导出已闭合并[独立增量接受](../../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/actual_before_pblock_export_incremental_review.json)：30个SLR2区精确覆盖X0Y10:X5Y14、三策略0、P9491/sites78266、无冲突。真实XDC1598540B仅命令注释输出路径异于AT003，可执行成员/几何全同。09:56Z原策略保留已闭合并[独立接受](../../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/actual_policy_preservation_incremental_review.json)：9525全fresh after/17schema与before及AT003原字节一致，只新建指定9491成员hard区。09:56:49Z[完整端口索引与alias闭合](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/candidate_pre_place_native_port_index_closed_facts.json)并[独立接受](../../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/pre_place_native_index_alias_review.json)：269ports/269groups/2772aliases/2170calls，方向与闭合均完整，167160事件配对/flush正确。本轮有向cut已完整闭合并独立接受；四组timing及完整restored preplace实际门已通过。10:07Z实际调用place_design SSI_SpreadSLLs并开始Placer，native本次Implementation/xcvu9p许可checkout通过。10:08Z为Phase1.2初始化，RSS21.75GiB/MemAvailable472.39GiB，正常无stop；place尚未完成、physopt/route未执行。

重启环境核验通过：workspace原路径rw ext4、boot_id1342c043…，初始MemAvailable493.74GiB、磁盘391.64GiB；真实入口验证、全部旧owners结束及lane空闲已核。Vivado2025.2 build6299465版本确认；本机node-locked许可lmdiag0，lmstat的无SERVER仅不适用于该许可类型，实际原生place仍需checkout。未改消费源、原合同、选型或验收。

AT003于08:44:09Z按用户PDU关机指令停止，14项收尾和[独立恢复输入核查](../../../agent/A007/E008_PDU_resume_review_20261017/AT003_stop_and_resume_input_review.json)通过，原始停止记录保留。它已完成并独立接受完整restored preplace，但place Phase1.3中断，没有当前E008 DCP；AT004从冻结debug_materialized父图重新加载和资格，不能恢复中途place。无需重做综合/OPT/debug或无关功能测试。

当前C01方法仍未取得迁移后物理结论。原AT001/AT002入口自然失败与修复、AT003用户停机不作C01方法反驳；无place完成、physopt、route合法性或正式时序通过结论。Hadamard、ScaleCode、format05、ABI、core/双DDR时钟及全部禁区保持。


[本轮完整preplace与真实place调用事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/pre_place_closed_stage_facts.json)绑定当前39源/144保持，restore guard native0/blackbox0/DRC blockers0/clockgroups1，live内部no_clock/constant/PW/unconstrained endpoints均0。原完整POST/80边界继承范围不冒新测，当前timing/fullglobal独立delta审核进行中，无额外执行门；正式reset/CDC/IO仍OPEN。

实际未布局through LOAD有界查询四组各16：入setup/hold+6.158/−0.074ns，出+6.859/+0.081ns，LOAD集合20534/945；不保证每条返回路径都穿cut边，不当迁移收益、fullcutTNS或routed timing。相关44054逻辑对全未布局，crossing0不作改善。

---
Published: 2026-10-17T10:09:22.453028+00:00
Publication: P4d6d5deded0844af989fb2449cdba4f7
