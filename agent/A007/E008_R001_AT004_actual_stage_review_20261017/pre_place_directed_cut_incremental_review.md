# AT004 pre-place 有向 cut 增量审核

- execution：17 项实际原始文本投影的身份核对与归档解析器完整重放完成；重放逐字段等于本轮摘要。
- verdict：接受完整候选 leaf 覆盖和合同内有向边界覆盖。14,307 条网、55,605 个候选 leaf pins、1,276 个断开 pins、58,361 个保留端点；44,054 个候选相关 driver/load pairs，其中 21,479 个边界 pairs。
- 3,087 条外部驱动网按定向范围采集，11,220 条候选驱动网完整枚举；方向网数 INGRESS 3,087 / EGRESS 55。导出的 through-pin 集合为 INGRESS 20,534 / EGRESS 945。实际语义统计与已审 AT003 一致。
- applicability：仅 AT004 pre-place cut。所有相关位置均 UNPLACED，known crossing 0 不能说明跨 SLR 或拥塞改善。through-pin 查询不保证逐条路径跨候选边界；未枚举合格外部驱动网的外部 peer loads，非完整外部 fanout、UNION 或 full-cut TNS。
- review：本子步骤接受，无新增执行停点。本记录不验收 timing、完整 pre-place 或 place/route；未读取或哈希 DCP。

[机器审核和原始证据身份](pre_place_directed_cut_incremental_review.json)
