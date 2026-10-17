# AT003 C01：完整有向 cut 独立阶段审核

C01 的 cut 阶段确已闭合，原生 query/stage 均为 code 0。已重核 27 项原始账本/固定源码身份，并将闭合账本只读链接到 A007 目录，实际重跑本次归档 validator；完整重算结果与工程 native_result 全字段相等。当前只接受 C01 连接覆盖事实；C01 有界时序、C02 对照及最终进程收尾尚未闭合，不选择候选。

execution：本次 cut 独立审核完成。verdict：C01具备较强热点成员覆盖，同时存在明确的宽输入边界代价；综合候选支持仍待比较。applicability：E005 同一 physopt 图、R005 AT003 b330；资源与站点事实明确复用 R004。review：cut 证据接受，不代表时序或物理收益通过。

## 已闭合覆盖

14,307 个 canonical nets、55,605 个候选 native leaf pins（其中1,276断开）、58,361条保留端点。3,087网使用唯一外部driver缩减模式，11,220网完整枚举候选driver负载；全部14,307网原生角色资格通过，没有方向未解析回退网。全部 top-port 查询实际成功且返回0端点，不能由此推广到别的图或候选。

边界为3,087个INGRESS网及55个EGRESS网，共21,479个候选边界driver→load对。实际 timing scope 精确对应20,534个INGRESS leaf LOAD、945个EGRESS外部leaf LOAD；当前是查询集合完整性，不是时序结果。缩减模式中的外部peer LOAD仍明确未枚举，完整外部fanout与全cut TNS未测。

## 卸载收益与连接代价

此前已审资源/保护说明见[既有选型要点](../R005_python_environment_review_20261017/candidate_policy_capacity_notes.md)。C01现有S的热点交集8,697（91.48%），实际P为9,491，全部SLR1；原生LUT/FF为1,890/6,317，另有2 DSP、6 RAMB36及MUX打包需求。这支持其“移走热点内部一组逻辑”的针对性，但源CLB绝大多数与组外共享，不能把触及站点数当保证释放数；SLR2原CLB利用率93.07%，目的地打包仍待新物理实现。

本次独立从闭合端点逐网汇总得到：

| 边界类别 | 方向 | 网数 | driver→load对 |
| --- | --- | ---: | ---: |
| 已知data/select | INGRESS | 3,072 | 6,144 |
| mixed-known/unknown | INGRESS | 3 | 9 |
| unknown/unclassified | INGRESS | 3 | 26 |
| mixed-known/unknown | EGRESS | 53 | 941 |
| unknown/unclassified | EGRESS | 2 | 4 |
| clock分类 | INGRESS | 3 | 7,770 |
| reset/set分类 | INGRESS | 1 | 6,156 |
| constant分类 | INGRESS | 5 | 429 |

6,144个已知data/select对全部来自组外 `u_projection_repack/g_output_payload_row[].out_payload_r_reg[]`，对应3,072条输入网。当前其已知位置均不跨SLR；仅假设全部候选P迁到SLR2、所有组外端点位置固定，就变成6,144个跨SLR逻辑对。它不是6,144条独立信号、SLL数量或已布线路径，也不反映真实重布局后复制、共享路由或邻近逻辑移动。

55条外向边界共945个负载对，其中896个落到组外 `g_row_ring_column[].u_row_ring_bram/...mem_reg_bram_0`；这些类别含未分类BRAM/组合语义，不能把6,144当全部数据/控制代价。加上已知位置的mixed/unknown边界980对，非clock边界在该固定外部位置假设下共有7,124个跨SLR逻辑对，当前已知位置跨SLR为0。

clock类别共7,770对，其中6,335来自核心clock buffer，6来自 `core_gate/...aresetn_BUFG_inst`，另1,429来自接到clock类pin的GND。分类由端点REF/pin和clock证据驱动，不能将全部归成同一种普通时钟路由或SLL负担。reset/set的6,156对实际driver为候选RAW-only GND；它们与另429个constant对及1,429个clock类GND对的源位置均UNPLACED，共8,014对位置不确定，不能把表中“已知跨SLR计数0”解释为零代价。原constant排除/专用clock/复位安全验证保持。

40条原失败样本的实际已解析alias与本候选完整alias交集为0。只说明这40条样本没有直接命中，不能证明C01与拥塞无关，也不能把热点成员重叠当作已证实失败因果。完整热点UNION恢复仍不在本次范围。

## 当前判断

C01较强的热点覆盖与较宽的跨区输入边界同时成立。物理卸载有依据，但其选择必须结合C02同口径cut、两者实际有界setup/hold路径、目的地资格和打包压力；现阶段不支持“一定一次布通”或仅凭资源余量选定C01。已完整查询的连接事实可继续使用，不要求为替代获取协议重跑R006。

原始闭合事实：[工程facts](../../../project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R005/attempts/AT003_system_python_directed_cut/candidate_C01_directed_cut_closed_facts.json)。独立证据：[27项身份及完整adapter重放](C01_cut_replay_identity_evidence.json)、[按方向/外部单元族的边界汇总](C01_cut_cost_breakdown.json)。本轮无EDA、DCP读取、进程/锁操作或工程源码改动。
