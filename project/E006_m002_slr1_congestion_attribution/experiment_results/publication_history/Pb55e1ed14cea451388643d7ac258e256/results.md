# E006：当前结果

热点 UNION 原语 103313 条，其中 MLP 79277 条（约76.7%）；旧输入前端候选覆盖弱，保留为未实施的探索对照。当前 C01/C02 尚未选定，不预判迁移收益或布通。[原闭合热点事实](runs/R003/attempts/AT001_lean_physopt_attribution/hotspot_ownership_closed_stage_facts.json)。

以下是已闭合 R004 原生资源，供 R005 引用；不是 R005 新测：

| 候选 | LUT | FF | BRAM36 | DSP | 实际 P | 热点原语交集 | CLB触及/共享/当前独占 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| C01 SwiGLU producer1 | 1890 | 6317 | 6 | 2 | 9491 | 8697 | 1788 / 1776 / 12 |
| C02 Down weight repack | 3348 | 3557 | 0 | 0 | 7257 | 2303 | 1347 / 1339 / 8 |

[两候选资源与成员独立核查](runs/R004/independent_membership_resources_and_probe_review.json)。两候选 P 均在 SLR1；站点共享、祖先/macro 资格和新增跨区连接仍需结合实际图判断。SLR2 的资源余量不证明可打包或布通。原 9 对象 property probe 未复现 R003 错误，不能把 LOC/BEL 当已证原因。

R004 已按本次明确用户例外受控结束，native -15 / supervisor125；只闭合两个成员/资源阶段，完整 cut/时序/UNION 未完成，收尾检查通过。[真实终态事实](runs/R004/attempts/AT001_exact_candidate_comparison/terminal_facts.json)。R005 AT001于09:29:55自然失败（native/supervisor1，stop=null）：入口缺少owner辅助函数，两成员阶段失败，新的class/role/cut未执行。完整入口集成旧负/新正对照后，AT002已于09:34:23实际启动。当前恢复检查点，尚无新原生cut/时序结果。


---
Published: 2026-10-17T01:36:31.443971+00:00
Publication: P8cc85d1e2ad1496baedc7bd7c17e6f54
