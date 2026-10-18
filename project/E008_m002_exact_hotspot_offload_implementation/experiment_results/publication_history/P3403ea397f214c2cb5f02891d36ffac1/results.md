# E008：AT004完整preplace通过，真实place运行中

用户明确“可以继续了”后，AT004_C01_PDU_resume_full_implementation已于2026-10-17T09:23:05.136988Z（北京时间17:23:05）真实启动。[原生启动事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/native_start_verified.json)：39归档源匹配b9dc、144生产输入保持、父DCP8451匹配，supervisor14547/start69484、native14680/start70786，CPU0–7/nice5与唯一项目EDA/锁一致。09:32Z父图恢复及成员子步骤已闭合并[独立增量接受](../../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/pre_place_membership_incremental_review.json)：10份账本与AT003字节同，RAW9514/S9507/P9491、16内部DSP→2父、全P未布局；仅3个actual artifact身份重绑。09:44Z新原生资源/before策略/硬Pblock与真实XDC导出已闭合并[独立增量接受](../../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/actual_before_pblock_export_incremental_review.json)：30个SLR2区精确覆盖X0Y10:X5Y14、三策略0、P9491/sites78266、无冲突。真实XDC1598540B仅命令注释输出路径异于AT003，可执行成员/几何全同。09:56Z原策略保留已闭合并[独立接受](../../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/actual_policy_preservation_incremental_review.json)：9525全fresh after/17schema与before及AT003原字节一致，只新建指定9491成员hard区。09:56:49Z[完整端口索引与alias闭合](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/candidate_pre_place_native_port_index_closed_facts.json)并[独立接受](../../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/pre_place_native_index_alias_review.json)：269ports/269groups/2772aliases/2170calls，方向与闭合均完整，167160事件配对/flush正确。本轮有向cut已完整闭合并独立接受；四组timing及完整restored preplace实际门已通过。10:07Z实际调用place_design SSI_SpreadSLLs并开始Placer，native本次Implementation/xcvu9p许可checkout通过。当前10:40Z实际place已自然推进到Phase2.1.1.1 PBP（Partition Driven Placement），RSS28.78GiB/MemAvailable465.44GiB/disk391.0GiB，PID/start保持且CPU持续增长；尚无place命令完成/POST/locality/physopt/route结果。

重启环境核验通过：workspace原路径rw ext4、boot_id1342c043…，初始MemAvailable493.74GiB、磁盘391.64GiB；真实入口验证、全部旧owners结束及lane空闲已核。Vivado2025.2 build6299465版本确认；本机node-locked许可lmdiag0，lmstat的无SERVER仅不适用于该许可类型，本次native place已实际checkout通过。未改消费源、原合同、选型或验收。

AT003于08:44:09Z按用户PDU关机指令停止，14项收尾和[独立恢复输入核查](../../../agent/A007/E008_PDU_resume_review_20261017/AT003_stop_and_resume_input_review.json)通过，原始停止记录保留。它已完成并独立接受完整restored preplace，但place Phase1.3中断，没有当前E008 DCP；AT004从冻结debug_materialized父图重新加载和资格，不能恢复中途place。无需重做综合/OPT/debug或无关功能测试。

当前C01方法仍未取得迁移后物理结论。原AT001/AT002入口自然失败与修复、AT003用户停机不作C01方法反驳；无place完成、physopt、route合法性或正式时序通过结论。Hadamard、ScaleCode、format05、ABI、core/双DDR时钟及全部禁区保持。


[本轮完整preplace与真实place调用事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/pre_place_closed_stage_facts.json)绑定当前39源/144保持，restore guard native0/blackbox0/DRC blockers0/clockgroups1，live内部no_clock/constant/PW/unconstrained endpoints均0。原完整POST/80边界继承范围不冒新测，当前timing/fullglobal独立delta审核已接受本轮诊断资格，无额外执行门；正式reset/CDC/IO仍OPEN。

实际未布局through LOAD有界查询四组各16：入setup/hold+6.158/−0.074ns，出+6.859/+0.081ns，LOAD集合20534/945；不保证每条返回路径都穿cut边，不当迁移收益、fullcutTNS或routed timing。相关44054逻辑对全未布局，crossing0不作改善。

[本轮独立全局preplace审核](../../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/restored_pre_place_global_incremental_review.json)接受144/39、175约束/162metadata与actual reads/overlay、当前live clock/guard/DRC/reset/debug关系及真实place调用。DRC15914 Warning保留、debug实际50MHz与声明300MHz差异保留；80旧保护表为继承，本轮post-place仍须fresh验证。该诊断资格不代替正式reset/CDC/IO验收或place完成。

本轮PBP告警经[A007只读独立审核](../../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/place_warning_contract_impact_review.md)核查：全设计SLR1→SLR2当前需10865/17280 SLL（62.88%），仅阶段估计，不是候选专属代价、最终用量、合法route或timing；旧10594对应SLR0→1不可同边界相减。USER_SLL_REG忽略提示可见100个DDR/MIG对象，随后抑制、真实总量未知；旧轮亦存在且曾非致命，不证明本轮无害。9525原策略快照不含这些DDR对象/该属性，原字节保持不等于placer实际兑现，也不能由warning反推工程删除或软化。无新增停点，原流程/完整验收保持。 [本轮观察事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/place_PBP_warning_observed_facts_20261017.json)。

---
Published: 2026-10-17T10:40:50.959695+00:00
Publication: P1c7f61b693d245aab109ea0d9c6e32b3
