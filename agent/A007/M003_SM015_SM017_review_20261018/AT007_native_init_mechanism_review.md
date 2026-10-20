# A007：AT007 TCL 与完整 INIT-only 原生机制通过

execution=completed（本审核）；verdict=supported；applicability=AT007 toy 与 extractor9442b534；review=可用于正式入口修复，G4 未放行。

原生于 06:25:31.196862Z 自然 native0，无 stop/survivor；13 归档原/副本与 16 PID/start 结束独立核实。正式 TCL 读取实际 apply 一次，149 行完整 INIT 前缀与生成驱动原字节一致，INIT end 存在、无 error 或 OPT begin/end；实际日志无 opt 命令。明确写出的 INIT checkpoint 恢复后 pblock/成员保留，apply attempt 增量 0。三 RTL/G2 保持。

A007 对冻结 extractor 独立重放实际驱动，正例及 11 个缺标记/后续命令负例通过，Tcl info complete=1；原始驱动与前缀也已在自身审核目录保存。正式源包须继续绑定绝对 helper 根、canonical TCL 注册、真实 apply/存量约束、restore 前 guard/counter，并保存完整生产生成脚本及 hook 闭包。

[机器证据](AT007_native_init_mechanism_review.json)。本结论不替代正式新图 13120/81/34/40+40、预算/80保护/严格 preplace。A007 未运行 EDA 或访问 DCP 内容/哈希。
