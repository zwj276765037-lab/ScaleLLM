# AT001 失败归因与最小兼容规则

这次失败发生在 `slr2::placement_policy before $scope`，早于候选 Pblock 创建和 `place_design`；不能据此判断 C01 无法布局或卸载无效。原错误是首个祖先 REF `scalellm_vcu118_f05_bd` 的原生属性表没有 `RLOC_ORIGIN`，而入口将其无条件列为必需属性。

独立解析实际原生回执发现，问题同样覆盖 primitive：resource_admissibility 已逐个查询 9514 个对象，归并为 15 个完整 schema，**全部 9514 个对象都不支持 RLOC_ORIGIN**；NAME、REF_NAME、IS_PRIMITIVE、LOC/BEL、fixed、USER_SLR_ASSIGNMENT、RLOC、MACRO_NAME、DONT_TOUCH 均仍在属性表中。成员导出的 24 个 REF schema 也全部缺此属性。只对 hierarchy 例外会在随后 primitive 上再次失败。[机器证据与规则](RLOC_ORIGIN_schema_failure_and_minimal_rule.json)。

建议唯一允许缺失的 schema 项限定为 `RLOC_ORIGIN`。每个真实范围对象都必须有 exact NAME、REF、IS_PRIMITIVE 和实际 `list_property` 回执，可复用本次已逐对象取得的 schema；不能用某个同 REF 对象的属性表代替全范围。支持该属性时读取原值，非空仍按现有相对布局冲突拒绝；缺失时明确记录 unsupported 状态及 scalar 查询的原生返回码和值，只有返回成功且空值、其他相对布局与 macro 检查全部满足时才允许该已知兼容状态。原生查询报错、非空、其他必需属性缺失，均保持失败。

保留完整祖先与 P 的 RLOC/MACRO_NAME 检查、真实 `get_macros` 及伙伴枚举和组外伙伴拒绝规则。不要把未知属性替换成无标记的空值，也不要猜测 RPM_GRID 默认值。before/after 比较必须覆盖支持状态、实际值、对象范围和所有原 Pblock 的策略／成员；不清除或软化任何现有硬约束。

实际修复放入新独立包，保留原 3cae 与 AT001 原证据。同一 C01 在真实收尾后新开 AT，按既有完整实现合同继续。有限 CPU 检验应覆盖 hierarchy/primitive 缺失、支持且空／非空、原生查询异常、其他必需项缺失、相对宏冲突、同 REF 不同 schema，以及 before/after 状态改变；不增加用户批准门。
