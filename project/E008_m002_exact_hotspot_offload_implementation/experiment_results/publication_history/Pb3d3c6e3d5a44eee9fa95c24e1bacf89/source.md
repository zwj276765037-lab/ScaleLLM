# E008：C01定向卸载与完整实现

按[SM012合同](../../../mission/M002_ddr_separation_and_timing_recovery/exact_hotspot_offload_implementation_contract_2026-10-17.md)、[有向边界范围](../../../mission/M002_ddr_separation_and_timing_recovery/directed_candidate_cut_scope_revision_2026-10-17.md)及[端口索引获取补充](../../../mission/M002_ddr_separation_and_timing_recovery/top_port_reverse_index_acquisition_revision_2026-10-17.md)执行。唯一主动变量为C01 `g_row_branch[1].u_branch_leaf` → SLR2；hard Pblock非排他、不限制走线，保持原约束。

父图为E005 `debug_materialized.dcp`，396068466B / 8451b2a86885d5ebb7bcb58dc24c352ac442492425c174269f9a803bb39c202f，沿用144冻结生产输入和175约束来源。复用原综合/OPT/debug与未受影响功能结果，不冒充本次新测。place=SSI_SpreadSLLs、physopt=Default、route=Default，无incremental。每实际阶段重新验证成员/物理父/origin-copy/祖先macro、80保护边界、完整端口索引及有向cut，全部实际P需落SLR2。

45bbc原生属性兼容修复已独立接受，保留原缓冲日志修复；仅RLOC_ORIGIN明确不受支持且原生读取成功为空时兼容，其他属性/祖先/macro/伙伴/前后一致性和完整物理门保持。26有限用例（3成功/23预期拒绝）通过；AT002实际before读取已通过，after一致性仍待原生结果。RTL/IP、Hadamard、ScaleCode、format05、Host ABI与时钟不变。单EDA，CPU0–7/nice5/max8；保留资源保护，正常进程无墙钟/无输出强停。无bitstream/GPU/板卡/PPL/ACC。

当前消费b9dc源码包，仅将物理约束导出选项 `-constraints physical` 改为本机2025.2支持的 `-type physical`，输出路径不变；不加quiet/force/no_fixed_only、不重载约束。9有限实际region用例及115身份/真实入口[独立delta审核](../../../agent/A007/E008_R001_AT002_actual_stage_review_20261017/physical_xdc_fix_review/review.json)接受，其余策略/时序/覆盖/物理流程全复用不变。AT003使用39实际归档源，当前实际export/after策略已独立接受；完整restored pre-place实际门已通过；独立全门审核已接受；用户已明确继续，AT004使用同一正式父图和已审包重做完整物理流程。

[用户PDU恢复授权](../../../.research-agent/decision_inputs/E008_user_PDU_resume_20261017.json)已归档，AT004执行[新来源绑定](../../../.research-agent/decision_inputs/E008_R001_AT004_C01_PDU_resume_execution_20261017.json)；源包b9dc/39源、144生产及父8451均原字节保持。工具2025.2/build6299465、重启挂载与资源/锁预检通过；node-locked许可lmdiag0，实际Implementation许可checkout仍由本次native place执行。既有26/9有限测试和AT003审核按原范围复用，不重跑综合或无关功能。

AT004本轮完整restored preplace实际门已通过并进入真实place（SSI_SpreadSLLs）；本次native日志确认Implementation/xcvu9p许可checkout通过。完整全门独立审核已接受本轮诊断资格，原POST后的80保护边界/实际P落SLR2/合法route及时序验收保持，不把preplace通过当布局完成。

当前AT004 place后本轮fresh80结构子步骤已独立接受（input48/gate16/down16，DONT_TOUCH全1及REF/INIT/CE宽度、driver/load位置均有实际值）；这部分已是本次新测。完整POST/locality与后续每阶段仍需真实全门验收。

AT004实际place全局POST已completed1/diagnostic_eligible1、完整性gate为空，正式timing仍hold FAIL/safety OPEN；当前候选locality/原生P对应关系和全体落区仍须单独闭合后，才取得完整本阶段资格。

当前place成员/native-origin/P落区及完整端口索引已独立接受，9491实际P全SLR2且全原对象存活。IS_LOC_FIXED/IS_BEL_FIXED的原生空→0 delta保留，另5策略字段同。全局POST诊断资格已独立接受；完整候选cut/timing/combined phase仍须闭合，后续physopt/route保持原全门。

AT004完整place原生POST/locality已均0闭合、candidate compliance true；外层physopt Default实际native0且声明netlist未修改，当前physopt全POST/locality继续。各阶段原资格/时序/安全及route验收仍分别执行。

当前完整place组合独立审核已接受。限定through LOAD四组各16保留覆盖限制；ingress/egress setup16条签名重合，不当独立32或跨cut保证。本阶段physopt命令149s native0、保存DCP已核，完整physopt POST/locality/后续route按原合同继续。

AT004本轮fresh physopt完整timing与fresh80结构已独立接受，timing正文与place一致但hold仍FAIL；独立phase采集身份已核。完整当前global POST/locality及route不豁免，继续原流程。

当前本轮physopt全局POST已completed1/diagnostic1、integrity gate空；实际fresh成员/origin对应关系9491P全SLR2、0替换/缺失。其余候选完整cut/限定timing/combined phase及route继续原全门，不把部分闭合当整体验收。

当前physopt全局POST、fresh成员/native-origin/9491P全SLR2与完整native index已独立接受；剩余完整cut/有界timing/combined phase及route按原合同连续执行。

当前完整physopt原生POST/locality0/compliance已闭合，进入实际Default route；每阶段fresh全门、正式时序及最终进程/输入/源/资源收尾继续，独立physopt组合增量审核并行进行，不新增用户/执行门。


完整physopt本轮全部子步骤和组合独立审核已接受；当前Default route继续原完整验收，holdFAIL/高拥塞/正式安全OPEN不豁免。


当前route初始/全局中间SLL、CLB pin及bus-skew覆盖警告原样保存并独立增量解释，继续原约束/验收；初始化counts和中间timing不代替最终route或签核。


route中途警告已独立核查；现行最终验证须保留并核上述6个目的pin与MLPcommand0共享source的实际bus-skew覆盖，physopt94MET或route命令成功均不代替。原约束/验收和自然运行保持，无新批准门。


---
Published: 2026-10-17T16:30:40.694782+00:00
Publication: Pf338b7588ce343edaad2440545487d38
