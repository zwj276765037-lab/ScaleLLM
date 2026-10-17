# E006 受控切换与 lean 最小修订独立审核

A007 · 2026-10-17。仅只读 CPU 审核；没有 EDA、进程控制、锁获取、大 DCP 读取或工程源码修改。当前真实模型配置未独立核实。

**结论：原 R001/AT001 的本次授权受控收尾成立；精确 R003/AT001 planned 管理骨架的最小源修订可按既有授权启动。** 已通过实际消息通知主控与 A006。这不表示原归因完整完成，也不构成 E007 的实际热点适用性或物理验收。

- execution：本次有界独立审核完成；原运行 `authorized_controlled_stop`，原生 −15、包装器 125。
- verdict：受控收尾和本次源准入 supported；完整原生归因、E007 物理可布性仍待实际证据。
- applicability：下列固定身份和本次实际用户决定；后续正常运行无墙钟/无输出强停政策保持。
- review：独立内部审核通过，非用户最终验收。

## 实际受控终态

[独立机器证据](independent_switch_and_lean_review.json)（59,540 B，SHA256 `c0eb19201935813f975330d6b420af66c4377ba20e92ffd588da4884424bf515`）及[审核生产器](../../../../../agent/A007/audit_E006_controlled_switch_20261017.py)记录了本次检查。原[终态事实](../R001/attempts/AT001_physopt_attribution/controlled_terminal_facts_20261017.json)为 21,596 B / `c066643bfe01cc2b703b6f0357fec84a505dff9684621dcf02ec9ee88348f75f`；[原 status](../R001/attempts/AT001_physopt_attribution/status.json)为 3,768 B / `ab63747e8b6f4c6070940f7ef64c1328f09aa0b7d15d087de35407cd80f2c04d`。

实际 SIGTERM intent 与 signal 绑定用户决定及 supervisor PID 942046 / start 927846090；原监督于 `2026-10-16T23:09:38.159182Z` 结束。本次独立只读检查：五个原 PID/start 身份均不存在，原 pgrp 942061 无非 zombie 进程；精确 EDA lock inode 的 `/proc/locks` 无持有者。未自行获取锁；A006 更早的实际非阻塞获取/立即释放收据另外保留。

144 个生产文件、14 个外部输入、4 个归档源以及其余小型终态/复用证据均独立重算 SHA 一致。579,969,232 B DCP 与 676,367,399 B primitive 导出仅核对 A006 实际全文件哈希收据、审核生产器及当前 stat；本审核没有重新读取二者，不能声称独立重哈希。其余 16 个复用文件实际重哈希。原生 query receipts 最后为 `native_owner_debug`；stage receipts 为空，`result=null`，interconnect remainder 未闭合。

独立重算全部 5,178 个资源样本：最大间隔 6.18559 秒；tree RSS 峰值 43,419,176,960 B，MemAvailable 最小 391,685,402,624 B，disk free 最小 421,308,256,256 B，与事实逐字段一致。没有资源阈值停止、物理命令或 checkpoint 写入。

原包装器 `NameError: name 'new_peak_sources' is not defined` 与 `frozen_inputs_after=null` 保留。该错误导致原包装器完整性收尾未成功；分开的实际 CPU 等值检查支持受控闭合，不将错误解释为输入发生变化，也不把终止写成自然成功。

原合同在首轮闭合核验时曾被临时追加文字，原[CT001 审计](../R001/attempts/AT001_physopt_attribution/controlled_terminal_audit_CT001_contract_transient.json)保留失败观察。主控随后恢复严格原 4,728 B / `cf53ff562b1894620ab0d6cc4398e17718cf815b32b8d2d8fd491adb17754263`，授权补充另存。本次确认的是最终逐字一致；**不能据此声称全过程合同从未改变**。入口仍使用完整严格 SHA，无前缀宽容规则。

## planned 骨架修订范围

本次核验 manifest `a60797ae6c106257904ff3029b575438e1bd0447f615f16230dd7d4e45512aa0`（5,399 B），runner `00d39932cd838533859f35423097f2e6b109dc0444d88050ecb9a4b4f9f81845`（18,844 B），launcher `9d8db013effe9c6069b8c2a1d98314e6c2bffbc40c7b86e72f49a9b613304f47`（2,750 B）。Tcl 仍为已审 `e313e9cd7ac16b036974e149949ec79ddab37f8c9f69f8744f69d20da168c0e1`。

只允许原精确 R003/AT001 目录中的 planned `run.json` 精确字典、原 `report.md` 模板及空 `evidence/`。其他 runtime/raw/source 产物、管理文件符号链接、非 planned 状态、其他已有 AT 和已有报告目录均拒绝。launcher、runner 入口及正式建目录前复查；旧管理文件不覆盖。

本次逐项阅读差异，独立核验实际骨架及 CT002 的 12 项 CPU 正/反例收据（exit 0）。首个 inline CPU 检查的 SyntaxError 原样保留，不冒称测试通过。五个 E007 导入 helper（`identity`、`freeze_check`、`require_registered_closed`、`prior_registered_identities`、`require`）的 AST 独立比较不变；supervision/post-integrity 整段逐字不变。没有重复运行先前 E007 的 59 项选择器用例。

E007 旧 manifest 绑定完整旧 runner，须在 E007 执行前显式保存旧 manifest 并重绑新 runner；本次 helper 不变证明可限定该补审，不需要重审全部 E007。该依赖不阻塞已授权 lean 启动。

## 归因证据使用边界

原 `core_other` query0 实际耗时 13,980 秒，随后 DDR0、DDR1、PCIe、debug 均 query0；这只说明命令返回。此前严格单表 parser 已拒绝 176 MB core_other 多表报告，不能作为一个 owner 的原生聚合资源数。DDR0/1 各含三个 SLR 表，分别属于 MIG、SMC、slice，不能取首表代替整体或静默相加共享物理资源。[单个 query 范围复核](native_owner_closed_scope_review.json)本次重新核验四个小报告：PCIe 的 SLR1 CLB/LUT/FF/BRAM36 等效为 4,769/22,961/25,894/50；debug 为 237/481/753/0，二者其余 SLR 为零。两份 DDR 多表均被严格 parser 拒绝；core_other 的前一阶段实际拒绝观察仅保留来源，不重复扫描大文件。这些事实仍不证明 E007 热点适用性。

lean 继续复用已闭合 primitive/global/首四 owner 证据，并查询 40 个失败样本、10 个节点、真实 tile/site/NW/UNION 与 UNION 附着 canonical nets，以及九个精确 hierarchy 原生报告。热点原生 LUT/FF 保持 `NOT_QUERIED`；没有 huge remainder utilization 或 33 detail queries。真实热点/失败端点阶段闭合后再判候选相交和联系；UNION 端点不是 E007 完整 cut，leaf INOUT/top ports 覆盖仍须后续 E007 完整采集。
