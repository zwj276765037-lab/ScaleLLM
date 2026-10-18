# AT004 place 有界时序审核

execution：24项投影中新增7项时序输入独立核对，归档验证器完整重放；4组共64条原生报告行的起终点、时钟、slack、data path delay逐项匹配。verdict：接受完整方向查询集合及有界结果，INGRESS hold存在负slack。applicability：当前Fully Placed图。review：独立子步骤通过，无新增停点。

INGRESS20,534/EGRESS945个through-LOAD引脚，max/min各16条、nworst1。最差INGRESS setup/hold为+0.603/−0.221ns；EGRESS为+0.603/+0.057ns。本轮投影、index/cut lineage、报告日期和8条闭合BEGIN/END事件完成阶段绑定。

64是返回报告行数，不是穷举唯一path数；方向之间可返回重合路径。through-pin查询不保证每条路径跨候选边界，非full-cut TNS或正式时序签核。LOGIC_DELAY/NET_DELAY仍为UNKNOWN_UNSUPPORTED_PROPERTY，不补造数值；全局hold FAIL及正式reset/CDC/IO OPEN保持。不作跨阶段因果改善判断。
