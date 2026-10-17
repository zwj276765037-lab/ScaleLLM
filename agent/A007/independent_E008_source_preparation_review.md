# E008 通用入口源码准备独立审核

execution：CPU 有界审核 completed。verdict：最终固定源码包在 F01 修复后可接受为后继实验准备。applicability：`prepared_manifest.json` 8935 bytes，SHA256 `b59d11262626f9acad735569dfee182978d7fcbd4a213fb6da3b336a94762072`。review：A007 独立文件身份、关键源码、实际 Tcl 文件生命周期与纯函数检查；不是候选选择、原生启动或物理结果验收。

详细证据为 [独立审核 JSON](independent_E008_source_preparation_review_b59d1126.json)，36782 bytes，SHA256 `ae78c921ab65760b43be7aad7cbef8a0420833ed2f0edd34e558cbde8d39a4bd`。独立脚本为 [audit_E008_source_preparation.py](audit_E008_source_preparation.py)。E008 尚无 R/AT；本记录保存在 A007 责任目录，不替主控登记实验。

F01 已关闭：初稿 `19924f7d…` 的 resolve 与后续 phase 都以 EXCL 新建同一个 `candidate_site_members_${point}.tsv`，会在首次 place locality 阶段失败。独立执行源码中的实际 Tcl open 命令，对 place/physopt/route 三阶段均复现旧版第二次打开失败，且确认原文件内容未被覆盖。修订将 resolve 原始 root 快照命名为 `candidate_literal_site_members_${point}.tsv`，reconcile 后实际 P 快照保持原名；三个阶段的两份独立文件均创建成功。candidate_hooks 的修复与原稿相比只有这一处文件名替换。旧稿和中间稿各 11 份自有源码均按完整 SHA256 独立核对归档。

N01 已处理：新资源资格导出原先逐对象重复写完整 `list_property` 字符串，可能产生大量重复文本。最终源码仍逐对象查询 native property 支持和受支持的 PRIMITIVE_* 实际值，仅将排序后完全相同的属性集合存入独立字典，每个对象保留 support_id；字典也纳入 physical overlay 的身份绑定。没有以按 REF 采样代替逐对象检查。工程的明确 mock-native Tcl IO 回归只证明导出逻辑，不能当作真实 Vivado 资格证据。

独立复核的主要边界：

- manifest 的 32 项引用逐项一致。E007 的 8 个 adapter 函数 AST 保持不变，包含真实成功父点适配、origin query 检查及 compliance；controller 与 E007 相比只增加 pre-place 方向时序调用。E007 本身仍只是已审核源码准备，真正的成功物理父链来自 E005。
- exact root 使用字面 root + `/`，C01 的 `[1]` 不变为 glob；S 只排除常量，P 使用真实 DSP48E2 父归一。RAMB18/36、URAM 保留；专用 clock/IO 和未知资源保留于账本并拒绝未解释迁移资格。旧输入双 bank、四 quantizer、8 DSP、Hadamard-only 限制已移除。
- 纯函数实际运行覆盖原对象存续、native origin 替换、仅名称后缀伪复制、origin 对象逃逸实际 Pblock、原对象无解释消失五例；后三例拒绝。全局 ORIG_CELL_NAME 查询不漏掉非 primitive DSP 父，最终仍与 originalP 精确对应。
- 当前 R004 已核 property helper 和 cap16 scoped timing 与新入口一致；外向使用 outside LOAD，内向使用 inside LOAD，不把内部负载混入外向诊断。仍保留完整 cut 与独立方向查询，不声称全 cut TNS。
- 启动依赖要求真实 E006 terminal、PID/start 全闭合、一个实际支持的 C01/C02、当前合同/manifest/review 身份和非阻塞单 EDA 锁。完整 place `SSI_SpreadSLLs` → physopt `Default` → route `Default`、80 项原保护、时钟/CDC/reset/IO、原资源保护和无正常墙钟/静默强停保持。

尚未发生的事实包括：R004 全 cut、方向时序、UNION 恢复与终态闭合；至多一个候选的独立支持结论及主控真实 closeout；E008 实际 pre-place 对象/祖先/宏/几何资格和其后物理结果。上述是既定工程依赖与原生检查，不是新增用户批准停点。当前没有选候选、启动/排队 EDA、修改 R004 运行源、控制进程/锁或读取大 DCP。

版本检查曾在工程进行已声明的 N01 窄修时正确拒绝原 `2147c23f…` 版本断言，记录在 [version guard observation](independent_E008_version_guard_observation.json)。随后绑定主控链路收到的最终固定包并核对中间归档；这不是工程实验失败。
