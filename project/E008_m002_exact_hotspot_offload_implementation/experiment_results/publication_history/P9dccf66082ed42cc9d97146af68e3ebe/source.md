# E008：C01定向卸载与完整实现

按[SM012合同](../../../mission/M002_ddr_separation_and_timing_recovery/exact_hotspot_offload_implementation_contract_2026-10-17.md)、[有向边界范围](../../../mission/M002_ddr_separation_and_timing_recovery/directed_candidate_cut_scope_revision_2026-10-17.md)及[端口索引获取补充](../../../mission/M002_ddr_separation_and_timing_recovery/top_port_reverse_index_acquisition_revision_2026-10-17.md)执行。唯一主动变量为C01 `g_row_branch[1].u_branch_leaf` → SLR2；hard Pblock非排他、不限制走线，保持原约束。

父图为E005 `debug_materialized.dcp`，396068466B / 8451b2a86885d5ebb7bcb58dc24c352ac442492425c174269f9a803bb39c202f，沿用144冻结生产输入和175约束来源。复用原综合/OPT/debug与未受影响功能结果，不冒充本次新测。place=SSI_SpreadSLLs、physopt=Default、route=Default，无incremental。每实际阶段重新验证成员/物理父/origin-copy/祖先macro、80保护边界、完整端口索引及有向cut，全部实际P需落SLR2。

45bbc原生属性兼容修复已独立接受，保留原缓冲日志修复；仅RLOC_ORIGIN明确不受支持且原生读取成功为空时兼容，其他属性/祖先/macro/伙伴/前后一致性和完整物理门保持。26有限用例（3成功/23预期拒绝）通过；AT002实际before读取已通过，after一致性仍待原生结果。RTL/IP、Hadamard、ScaleCode、format05、Host ABI与时钟不变。单EDA，CPU0–7/nice5/max8；保留资源保护，正常进程无墙钟/无输出强停。无bitstream/GPU/板卡/PPL/ACC。

当前消费b9dc源码包，仅将物理约束导出选项 `-constraints physical` 改为本机2025.2支持的 `-type physical`，输出路径不变；不加quiet/force/no_fixed_only、不重载约束。9有限实际region用例及115身份/真实入口[独立delta审核](../../../agent/A007/E008_R001_AT002_actual_stage_review_20261017/physical_xdc_fix_review/review.json)接受，其余策略/时序/覆盖/物理流程全复用不变。AT003使用39实际归档源，完整原生export/after/pre-place资格仍待当前新图验证。

---
Published: 2026-10-17T07:44:21.579031+00:00
Publication: P472c7cbf38d1412cb4764cd8fa0938be
