# AT003：真实策略保持审核通过

接受 placement-policy preservation 子步骤。独立核对全部 9525 个对象：after 全部重新执行原生 schema 查询，17 个完整 schema 按对象与 before 一致；其余 11 个必需属性受支持，RLOC_ORIGIN 均明确 unsupported、native0、空值。before/after 策略字典逐字段相等，两个策略文件也逐字节相同。[完整审核](actual_policy_preservation_review.json)。

原 Pblock 集合为空，after 仅新增 `m002_exact_hotspot_SLR2`。其 9491 个成员无重复，与实际 P 全集相等；范围 `CLOCKREGION_X0Y10:CLOCKREGION_X5Y14`，IS_SOFT／EXCLUDE_PLACEMENT／CONTAIN_ROUTING 均为 0。原生 preservation 标记 verified=1、excluded_macro_partners=0、unknown_policy=0 与实际账本一致。

该结果仅闭合候选策略保持检查。cut／端口索引、有界时序、全局 pre-place 保护及实际 place/physopt/route/signoff 仍分别等待真实结果；尚未判完整 pre-place 或布局通过。实现继续，无新增门。
