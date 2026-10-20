# AT003 原生 alias 资格阶段审核

execution：canonical 阶段完成，全端点导出仍在运行。verdict：实际 scalar/alias 元素身份检查通过；计数差异未解释，G1 未完成。applicability：f0ac0b91 固定包及当前关闭回执。review：有未决口径项的阶段接受，不是优化或候选通过。

已关闭 `alias_identity_summary.tsv` 记录 **2,914,086 次原生 handle/NAME 元素精确匹配**，list 表示差异为 0。8 条保存的真实配对逐元素一致。固定源码继续在任何真实元素差异处失败，只有全部既定 alias 查询完成后才写此 summary/marker。因此此次支持单对象 scalar 原样包装在实际固定查询中的资格；没有把 CPU 模拟当作原生结果。

完整 marker 给出 **569,597 个冲突 canonical**；已独立核的本次 report 为 **547,548**，差 **+22,049**。核归档源码 164–172 行确认该字典在 seed 阶段之后重新置空，仅由 `ROUTE_STATUS == CONFLICTS` 集合填充，不能用“包括补充 seed”解释差额。

当前完整 raw→alias→inventory 的离线复算和端点分类尚未闭合。保留两个原生口径，待固定导出完成后按现有字段分析；不删网凑数，不单凭某个桶数量相同便认定解释，不插入新原生查询。G1 的计数适用性、未知类别、固定深查范围和候选关键事实仍需审核。

[机器证据与真实来源](native_alias_stage_review.json)。本次仅有界读取关闭小账本、源码相关行及日志尾段，没有 EDA/DCP/生产改动、信号或锁控制。
