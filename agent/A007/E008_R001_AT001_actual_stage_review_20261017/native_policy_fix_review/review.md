# E008 原生属性兼容修复：集中审核通过

接受冻结入口 `45bbc8479f26a7c4754861f55f400ec3560e324095e7c52367b307eeb1aeb590`，支持原授权下同一 C01 新 AT 继续完整 implementation，无新增用户批准门。[完整审核](review.json)。

独立核查 268 个非 DCP 身份并调用实际只读 `verify_manifest`，均通过。原 `3cae` 包保持。对 Tcl 实际加载后的所有过程逐个比较，仅 `resource_admissibility` 和 `placement_policy` 改变；原 constrain wrapper、祖先／macro／伙伴／Pblock 检查和所有其他过程完全相同，16 个复用源保持。

新增缓存只保存原 resource_admissibility 已逐对象查询的 REF、IS_PRIMITIVE 和 schema，不增加或替代该阶段原生查询。before 仅复用同一次、尚未修改设计的逐对象回执，祖先及 after 全部重新读取实际 schema。唯一缺失例外是 RLOC_ORIGIN，必须实际 scalar 查询 native0 且空值，并在策略快照中保留明确 unsupported 状态；其他 11 项必需属性缺失仍失败。支持但非空的 RLOC_ORIGIN 仍进入原相对宏拒绝规则；before/after 支持状态和实际值参加严格比较。

独立在 A007 目录重放同一有限 26 用例，实际执行修复后的 resource／policy／constrain Tcl 过程：3 个成功、23 个预期拒绝。每例返回码、结果、实际 region 调用次数及全部产物字节都与工程原结果一致。覆盖 hierarchy／primitive 缺失、同 REF 不同 schema、支持且空／非空、unsupported 非空／原生错误、其他 11 项逐一缺失、祖先 SLR 冲突、相对宏、伙伴枚举／组外伙伴及 after 状态／值改变。未重跑历史大组合。

执行：本次集中源码与有限 CPU 审核完成。判断：支持此限定兼容修复。适用范围：原生命令由有限 mock 提供，不能代替新 AT 的真实 Vivado 资格和布局布线结果。审核：接受新包；真实终态、单 EDA lane 和 Root 新 manifest 绑定仍沿用既有执行依赖。未读取或哈希 DCP，未运行 EDA、控制锁或发送进程信号。
