# AT004 fresh physopt全局POST审核

execution：当前全局POST独立核验完成。verdict：接受physopt全局诊断资格；hold FAIL与正式安全OPEN保持。applicability：仅global POST，候选完整locality/阶段另审。review：独立子步骤通过，无新增停点。

completed1/diagnostic1/blackboxes0/COMPLETE_INTERNAL与日志169820完成标记一致。39运行源/144生产输入身份核对；175约束来源、162registry/metadata、13保留原来源和overlay保持，new_actual_reads=[]。

当前reset graph、14 primitive exports、fanout/BRAM与CDC纯逻辑重放等于integrity且issues=[]：7 async、4 AUX、3 HostSplit链、6目标，688个BRAM端口时钟，8分类CDC/新未分类0；4个AUX代表源归一化仍是诊断证明，正式安全OPEN。

12类当前报告去除页眉日期/命令/阶段/横线后，全部正文与已审place相同，包括时钟、DRC、CDC、约束exception、pulse-width、bus-skew与拥塞。DRC保留1 RTSTAT-13 Critical Warning/15,917 Warning，94项bus-skew均MET最差3.262ns，exception覆盖缺口保留。高拥塞与未证明固定热点缓解保持。

复用本轮已审physopt命令、新完整timing与fresh80；hold仍34,042违例，WHS−0.562/THS−1879.853ns。DCP仅核工程保存身份记录与大小，未读/hash内容。额外control_sets/paths_setup/paths_hold/worst_per_clock只核身份，不扩展为穷举或时序签核。完整候选phase与route未由本审核成立。
