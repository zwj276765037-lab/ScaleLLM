# 物理 XDC 导出选项修复：集中审核通过

接受冻结入口 `b9dcabf46f82b505e0a49de9a2c14eb013b7d71937e2d2805a9538f7545227bb`，支持现有委派下同一 C01 的 AT003 直接继续；无新增批准门。[完整独立审核](review.json)。

唯一执行差异是 `candidate_hooks.tcl` 中 `write_xdc -constraints physical` 改为 `write_xdc -type physical`，输出路径不变。本机 Vivado 2025.2 安装手册和工程实际 native0 的 `help write_xdc` 回执均说明：`-constraints` 接受 VALID/INVALID/ALL；`-type` 接受 physical。没有添加会隐藏内部错误的 `-quiet`、覆盖文件的 `-force`，也没有扩大固定位置导出范围或重新读取 XDC。

独立核验 115 个身份，实际只读 `verify_manifest` 通过。原 21 个 own 源中仅上述一行改变，16 个复用源保持；加载 Tcl 后，只有 `slr2::constrain_region` 函数体含这一处替换，所有其他过程一致。

在 A007 目录独立重放冻结 CT002 的 9 个有限用例，实际执行原／新 constrain_region：正确导出成功；原无效选项、原生导出异常、成员不符、越区、缺资源站点、软 Pblock、已有同名 Pblock、冲突 LOC 均被拒绝。每例结果与产物字节和工程证据一致，原生导出 errorcode 保留。旧 CT001 harness 证据保留，未重跑无变化的 26／32 大套用例。

执行：限定变更与有限 CPU 审核完成。判断：支持命令选项兼容修复。适用范围：原生帮助确认语法，CPU mock 验证调用和错误处理；本次审核没有实际打开设计或导出完整设计。审核：接受新包；真实 export、after 策略保持、完整 pre-place 以及 place/physopt/route/signoff 仍由新 AT 按原合同验证。
