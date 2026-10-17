# E006：SLR1 拥塞归因与候选比较

当前采用[有向候选边界范围修订](../../../mission/M002_ddr_separation_and_timing_recovery/directed_candidate_cut_scope_revision_2026-10-17.md)，在同一 E005 physopt DCP 上独立比较 C01 SwiGLU producer1 与 C02 Down weight repack。覆盖版本为 candidate_directed_cut_v1；保留所有候选边界连接，已证明唯一外 driver 的网允许不导出外部 peer leaf LOAD。未采外部 peer 明记 NOT_ENUMERATED，不声称整网端点/全外部扇出完整。方向时序 max/min 各 cap16，不能当签核。

R005 AT003 采用系统Python环境修复包 b3308185，保留原owner修复；此前owner已通过[独立完整入口集成检查](../../../agent/A007/R005_owner_integration_review_20261017/review_addendum.md)，当前实际11份运行源已归档。原 558c 包和失败原证据保留。AT002真实成员/site导出已写closed，后续Python资格adapter因工具自带解释器缺少_tkinter而失败；显式解释器及环境绑定已修复，AT003原生载图前导入预检实际通过。正式原生schema、本地leaf/alias/角色覆盖、回退和方向时序仍未完成。资源、热点及失败样本引用原闭合身份，不伪称本次新测。原 R004 全网采集与 UNION 补采未完成；旧失败和部分证据保留。

Hadamard、ScaleCode、format05、RTL/IP/ABI/时钟保持；本诊断不执行物理修改。选定至多一个实际支持的候选后，按 E008 原合同与范围修订进入完整 implementation。


---
Published: 2026-10-17T02:50:35.751755+00:00
Publication: P2c8c4114b57e4cb296615706ae12956d
