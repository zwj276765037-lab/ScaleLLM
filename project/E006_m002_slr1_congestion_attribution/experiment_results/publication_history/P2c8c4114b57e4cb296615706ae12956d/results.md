# E006：当前结果

热点 UNION 原语 103313 条，其中 MLP 79277 条（约76.7%）；旧输入前端候选覆盖弱，保留为未实施的探索对照。当前 C01/C02 尚未选定，不预判迁移收益或布通。[原闭合热点事实](runs/R003/attempts/AT001_lean_physopt_attribution/hotspot_ownership_closed_stage_facts.json)。

以下是已闭合 R004 原生资源，供 R005 引用；不是 R005 新测：

| 候选 | LUT | FF | BRAM36 | DSP | 实际 P | 热点原语交集 | CLB触及/共享/当前独占 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| C01 SwiGLU producer1 | 1890 | 6317 | 6 | 2 | 9491 | 8697 | 1788 / 1776 / 12 |
| C02 Down weight repack | 3348 | 3557 | 0 | 0 | 7257 | 2303 | 1347 / 1339 / 8 |

[两候选资源与成员独立核查](runs/R004/independent_membership_resources_and_probe_review.json)。两候选 P 均在 SLR1；站点共享、祖先/macro 资格和新增跨区连接仍需结合实际图判断。SLR2 的资源余量不证明可打包或布通。原 9 对象 property probe 未复现 R003 错误，不能把 LOC/BEL 当已证原因。

R004 已按本次明确用户例外受控结束，native -15 / supervisor125；只闭合两个成员/资源阶段，完整 cut/时序/UNION 未完成，收尾检查通过。[真实终态事实](runs/R004/attempts/AT001_exact_candidate_comparison/terminal_facts.json)。R005 AT001于09:29:55自然失败（native/supervisor1，stop=null）：入口缺少owner辅助函数，两成员阶段失败，新的class/role/cut未执行。完整入口集成旧负/新正对照后，AT002于09:34:23启动、09:45:04自然失败（native/supervisor1、stop=null）。真实readonly_resolve导出完成，Vivado内Python缺少_tkinter使资格adapter导入失败；尚未进入class/role/cut/时序。144输入及原DCP/源保持、PID/锁已收尾。[AT002终态](runs/R005/attempts/AT002_owner_helper_repaired_directed_cut/terminal_facts.json)。

AT003于北京时间09:51:16实际启动，原生system_python_runtime_preflight code0，系统Python3.12/Tcl8.6.14及_tkinter导入已核；其后才开始加载DCP。当前尚无新cut/方向时序结果。[启动核验](runs/R005/attempts/AT003_system_python_directed_cut/native_start_verified.json)。

本AT两候选membership qualification均已原生code0并完成CPU一致性核查：C01 RAW/S/P=9514/9507/9491，C02=7260/7257/7257，与R004真实成员字段一致。[C01闭合事实](runs/R005/attempts/AT003_system_python_directed_cut/candidate_C01_membership_qualification_closed_facts.json)、[C02闭合事实](runs/R005/attempts/AT003_system_python_directed_cut/candidate_C02_membership_qualification_closed_facts.json)。当前正在C01有向边界采集，cut/时序未闭合，不作支持判断。

C01完整有向cut已于02:33:41Z闭合并核查：14,307个canonical nets，55,605候选leaf pins，58,361保留端点；3,087 reduced外部driver网、11,220候选driver全枚举网；边界3,087 ingress/55 egress，共21,479个driver-load对。[C01闭合事实](runs/R005/attempts/AT003_system_python_directed_cut/candidate_C01_directed_cut_closed_facts.json)。已知data/select边界6,144对，当前已知跨SLR为0，固定组外位置并将全P移SLR2的假设下为6,144对；这是连接位置推算，不是SLL用量或实现结果。部分clock/constant/reset驱动位置未确定，不能当已知同区；原40失败样本与本候选完整alias交集为0，不代表全局失败不相关。C01有界时序正在执行，C02cut/时序未完成，候选未选。

C01有界方向时序已闭合并独立复核，四组实际max/min查询均返回cap16路径。INGRESS20,534候选LOAD：setup最差+1.416ns、hold−0.128ns；EGRESS945外部LOAD：setup+1.848ns、hold+0.035ns。[C01时序事实](runs/R005/attempts/AT003_system_python_directed_cut/candidate_C01_bounded_timing_closed_facts.json)、[独立合并判断](../../../agent/A007/R005_AT003_native_stage_review_20261017/C01_timing_review.md)。原physopt图使用estimated网络延时，不是完整cut TNS或合法route签核。双向最差setup均涉及兄弟SwiGLU分支控制，原rpt网络延时占比分别94.13%/94.72%；原属性LOGIC/NET_DELAY仍保留UNKNOWN，不与rpt抽取混淆。输入hold为projection_repack→up_tile寄存器，原图已失败，不能预填迁移会改善。当前C02cut在实际采集，候选尚未选定。


---
Published: 2026-10-17T02:41:38.115451+00:00
Publication: Pe9e2d972d46847eca314285f73e73429
