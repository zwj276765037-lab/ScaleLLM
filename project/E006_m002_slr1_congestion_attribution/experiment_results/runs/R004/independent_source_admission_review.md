# E006/R004 只读入口独立准入审核

执行入口源码准备通过，适用于 final manifest `29b84a338ec696ab2ed68e4b246d12fc3e0313459c75e1fc8102b3527bb677b7`（6641 bytes），执行绑定 `e7edc4b1...`、原合同与措辞补充、独立 targets `8a07bcbe...`。结论已通过实际协作消息交 root/A006，工程可按合同完成真实 PID/锁/输入/资源准入后直接启动；无新增用户许可门。

[机器复核事实](independent_source_admission_review.json)保留精确身份和独立 CPU 输出；[初审](independent_initial_source_review.json)保留 3b7a/cc5f 包中的问题。集中修复闭合：

- F01：外向时序只以单 driver 边界网的全部组外 LOAD leaf/top endpoints 查询；内向取组内 LOAD。原先组内 driver 与内部 loads 可挤占 cap16 的错误已修。INOUT/unknown 保留 UNRESOLVED，不虚构方向。CT003 混合内外 fanout 反例已独立纯 Tcl 重放。
- F02：真实 P 父对象输出九项 fixed/SLR/RLOC/macro/origin 属性及 actual Pblocks；DSP 子 primitive 不再是唯一 policy 载体。
- F03：失败相关 9 对象探针保留五列原始 native vector 本体/长度以及每对象 scalar；实际触发列仍等原生结果。
- N01：全部 P-touched sites 的 primitive 内外成员已导出，可用于实际 shared/exclusive 分析，不直接将 touched sites 当作释放量。

两精确 root 与 literal `[1]`、原 NW/owner/40 样本目标保持；RAW/S/P 泛化保留 memory/常量与未知，不套旧输入候选资源断言。完整 canonical aliases、所有 leaf IN/OUT/INOUT 与 top ports、REF/native IS_CLOCK、计数回读均有真实入口；旧 UNION 范围保持并单列 legacy IN/OUT。只读主脚本与 inspector 未发现物理/Pblock mutation。所有 runner 非 main helper AST 和真实监督/收尾尾段与已审 lean 相同，继续单 EDA、正常进程无墙钟或静默强停。

本次重新核了 102 条小文件身份引用；大导出和 DCP 仅核既有 producer identity 与实际 stat，未重读大 DCP/676 MB 全图文件。独立 optional-empty mock 保留 scalar 空位，required-empty 被拒绝；这不证明原生错误列。独立 harness 的 Python 列表语法及 tkinter tuple 表示修正保存在 [自身审核脚本修正记录](independent_CPU_audit_harness_repairs.json)，工程源未因此改动。

execution：源码准入完成，实际 native 在审核时 NOT_RUN。verdict：只读入口修订可执行，候选适用性和迁移收益仍 unassessed。applicability：固定原 physopt、fresh R004/AT001；cap16 为样本，full-cut TNS 和正式签核未测。review：A007 独立内部阶段审核，非物理验收。E007 探索对照同源修补不构成本次启动依赖。
