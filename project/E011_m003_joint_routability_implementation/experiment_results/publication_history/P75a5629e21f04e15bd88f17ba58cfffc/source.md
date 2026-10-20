# E011：M003联合可布线版本

G2 4424c426冻结C-M2（81区域CE、head/tail各6560 FF）、C-A3（2×81920×128、40+40 URAM、34独立同沿地址FF）、C-P1（正式overlay、原C01 hard-SLR2及25保护）。三RTL保持当前已验证版本；算法/ABI/core100MHz/UI200MHz/双DDR/80边界不变。唯一工程与EDA执行A006，A007独立审核，Root集中决策；不处理M004/E010/GPU/旧根。

当前入口v3 manifest151e4f11，45源；相对v2仅5入口文件修改。普通fresh run guard保持；显式恢复分支保留实际stale状态，以原AT003原生23完成生产网表、22实际消费、379输入和188归档闭合资格，再验证真实当前图/约束/预算。原AT003外层失败1永不改写，不使用旧基线DCP。后继qualify使用同一恢复守卫；source审核不等于G4。

单EDA、CPU0–7/nice5/max8/synth1、RSS192GiB、MemAvailable48GiB持续30s、disk30GiB保护；正常无墙钟/静默强停。无bitstream/板卡/GPU/PPL/ACC。架构/池/计数/预算/物理策略改变报Root；当前固定SSI_SpreadSLLs/Default/Default、增量关闭。

---
Published: 2026-10-18T07:02:26.761331+00:00
Publication: Pc387af2b05e546dd928a3f468824f179
