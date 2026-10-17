# AT003 C01：cut、资源及有界时序合并判断

C01有界时序已实际闭合，query/stage均code 0。已重核9项原始报告/账本身份，并实际重跑归档timing validator，结果与工程native_result全字段相等。INGRESS的20,534个候选LOAD和EGRESS的945个外部LOAD均完整进入各自max/min查询，四次查询均实际返回16条路径，cap16/nworst1保持。

| 查询方向 | 最差setup slack | 最差hold slack |
| --- | ---: | ---: |
| INGRESS | +1.416 ns | −0.128 ns |
| EGRESS | +1.848 ns | +0.035 ns |

这些是原physopt图上的有界查询结果，报告使用estimated网络延时；不是完整cut TNS、合法route后的时序签核，也不是迁移到SLR2后的剩余预算。原LOGIC_DELAY/NET_DELAY属性列全部明确UNKNOWN_UNSUPPORTED_PROPERTY，保留不改写；以下数值另从原生rpt首条最差路径取得。

最差INGRESS setup实际由另一SwiGLU分支的`output_element_r_reg[0]/C`到C01 DSP子对象`CEA1`，数据延时8.092ns，原报告分解为logic0.475ns、estimated route7.617ns。最差EGRESS setup由C01 `output_element_r_reg[2]/C`到另一分支`input_gate_r_reg[11]/CE`，数据延时7.877ns，其中logic0.416ns、estimated route7.461ns。两侧最差路径均涉及分支间控制，报告的网络延时占比超过94%；“单独的8-row计算分支”不能理解为无组外控制耦合。

最差INGRESS hold由组外projection_repack寄存器到C01 `up_tile_r_reg[1141]/D`：data delay0.140ns、clock skew0.206ns、slack−0.128ns，已有hold失败。最差EGRESS hold由C01 `out_product_s32_reg[24]/C`到组外row-ring BRAM DIN，slack仅+0.035ns。迁移会同时改变数据延时和时钟偏斜，不能根据“跨区更长”预填hold修复，也不能忽略其对setup的代价。

结合[已接受的完整cut](C01_cut_review.md)与[R004资源/保护要点](../R005_python_environment_review_20261017/candidate_policy_capacity_notes.md)：C01热点S交集91.48%，卸载对象有针对性；同时3,072条组外payload输入网形成6,144个边界对，55条外向网形成945对，目的地SLR2原CLB利用率93.07%且C01有DSP/BRAM/MUX打包需求。现有正setup与负ingress hold支持“需要实际布局验证的候选”，不足以判定优于C02或保证布通。候选比较仍待C02同口径cut与有界时序；无需为取得相同覆盖重跑R006。

C02新class schema原件已核，与此前C01已接受schema逐字节一致，实际NAME/DIRECTION/IS_LEAF及IN/OUT/INOUT/MIXED/UNKNOWN证据保持；这只接受class子步骤，不预填C02连接或时序通过。

execution：本阶段独立审核完成；verdict：C01连接/有界时序证据接受，当前已有边界hold失败，选型仍inconclusive；applicability：同E005 physopt图及b330，资源复用R004；review：等待C02完整对照与真实终态，未选候选。详见[原始身份、完整重放和四条最差路径摘录](C01_timing_review.json)。本轮无EDA、DCP读取、工程源码改写或进程/锁操作。
