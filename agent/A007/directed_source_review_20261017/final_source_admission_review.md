# E006 R005 固定源码准备：独立集中审核

**结论：固定 manifest `558c46fe4aaf5e14c3a8f548b02a1fd00891588d2054f5fc9c3e5fcf1d921161`（9705 B）源码准备通过，无待修问题。** 可按已授权范围进入实际运行资格验证；R004 必须真实自然结束，或先取得本次新的用户明确停止例外并完成收尾。此结论不是停止授权、候选选择、原生 API 通过或 implementation 成功。

execution：本次独立源码审核 completed。verdict：accepted for runtime qualification。applicability：仅此 R005 固定包、`candidate_directed_cut_v1` 和绑定的 E005 physopt DCP。review：A007 内部审核，已真实消息交主控与 A006；无新增普通修复批准门。

## 身份与边界

独立重核 14 份源码、5 份 CPU 证据、10 个外部引用、30 个窄范围复用身份；CT003 对应最终版本，实际调用只读 `verify_preparation()` 通过。DCP 只核当前大小与原 R004 identity 绑定，未读取/重新计算大 DCP。原 R004 8 份归档源码及 E008 b59 的 11 份自有源码身份保持。

最终共享 collector `6514c3fe…`（25315 B）、adapter `e3d47cc1…`（32488 B）、inspector `b98703f3…`（18376 B）与实际独立测试快照逐字对应。候选集合先由实际 RAW/S/P、DSP 子对象和 root 外实际 P 建立，本地 pin→net→完整 aliases 闭合；qualified ingress 原生非 IN 过滤分支不先后执行无 filter 整网 leaf 查询。top ports、常量、disconnected、unknown 和完整 fallback 保留，方向时序集合与 cap16/nworst1 分开核验。

## 已修问题与检验

- F01：实际查询命令只用单 alias、旁边声明仍列全部 aliases 时，初版 adapter 会误接受。现在核实际 `-of_objects` 参数与完整 aliases 一致；原反例已拒绝。
- F02：把候选 FDRE 的 REF 改成 GND 并同步分类时，初版 adapter 会误接受。现在以实际 native owner 账本、RAW/S/P、local pin 和 endpoint REF/物理父交叉核验，DSP 子 REF 与父 REF 分开；原反例已拒绝。
- 17 个 collector 小图情形全部符合预期：14 个有效闭合、3 个明确不合格。14 个实际 `scoped_timing` mock 含空路径、两条路径、数组括号、多词和空字段；cut/timing adapter 共 28 次 CLI 全通过。
- 9 个错误 ledger/命令反例全部拒绝，另有有效对照和解析检验。9 个真实 prior-closure 函数的 CPU 小图检查覆盖正常失败后的合法收尾、运行中/残留/身份仍活、完整性缺口、缺失或错误本次停止许可。

完整事实、逐文件身份、初版反例与最终结果见 [审核 JSON](final_source_admission_review_558c46fe.json)（26923 B，SHA256 `412cba2b461f6f231f932eb8fc95af18376f2f617b48bea9fe4a6fc2e7eb82dc`）。原反例与修前快照均保留。

## 实际执行依赖

runner/launcher 绑定实际 attempt、report、scope、manifest 与 R004 terminal/facts；单 EDA 非阻塞锁，不排队也不自动结束旧任务。监督资源与收尾尾段逐字等原 R004：CPU0–7/nice5/max8、192 GiB/48 GiB 持续30秒/30 GiB保护，正常无墙钟或静默强停。

受控停止入口默认只读；必须新的用户决定身份、精确当前 R004、固定 scope/manifest 和显式 `--execute`，才可经 pidfd 向 supervisor1253852/start930758582 发一次 SIGTERM。旧 R001 决定不得复用。此审核未调用停止入口、信号或锁控制。

新 E008 尚不属于本 manifest；actual reconciled P 投影和整包仍待其独立交付，不是 R005 准备通过的依赖。CPU mock 不证明 Vivado 原生 schema/集合完整性、提速或可布通，实际原生阶段与完整物理验收仍须依据新运行证据。
