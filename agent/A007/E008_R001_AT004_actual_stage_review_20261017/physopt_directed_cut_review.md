# AT004 physopt 完整有向cut审核

execution：17项实际投影输入及归档验证器完整重放完成，逐字段等于当前摘要。verdict：接受合同范围内完整候选leaf与有向边界覆盖。applicability：当前physopt图及同阶段native-origin reconciled P。review：独立子步骤通过，无新增停点。

14,307条网、55,605个候选leaf pins、1,276个断开pins、58,361个保留endpoint、44,054个候选相关driver/load pairs、21,479个boundary pairs。3,087条外部驱动网采用有向范围，11,220条候选驱动网完整枚举；INGRESS3,087/EGRESS55。拓扑统计同本轮已审place。

当前已知跨SLR逻辑pair127：clock6、known-data/select38、mixed53、unknown-semantic30。未知位置pair8,014：clock1,429、constant429、reset_set6,156；逐原始endpoint检查均为非S/P驱动端SLR=UNPLACED、候选负载端SLR2。所有9491个P实际落区结论不受这一外部/常量驱动位置未知混淆。reset_set是net类别，不表示P复位接收器未布局。

这些是逻辑连接pair，不是全SLL数、带宽、拥塞或改善量。完整外部fanout、热点UNION和full-cut TNS未测。through-LOAD查询集INGRESS20,534/EGRESS945，并不保证每条后续时序路径跨候选边界。完整阶段另行组合审核。
