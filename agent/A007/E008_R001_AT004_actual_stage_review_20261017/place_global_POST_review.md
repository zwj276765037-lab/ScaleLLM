# AT004 全局 place POST 独立审核

execution：实际闭合文本证据审核完成。verdict：接受全局 place 诊断资格；hold 时序 FAIL；正式 reset/CDC/IO 安全 OPEN。applicability：AT004/C01 当前 place 图，全候选 locality/compliance/cut/timing/阶段回执另审。review：独立子步骤通过，不新增停点。

原生 place 返回0，耗时7858秒，实际保存580,662,986字节 place.dcp。独立核对保存回执、native生成文本与文件大小；DCP SHA仅引用A006记录，未读取或哈希DCP。

39项运行源及归档、144项生产输入身份核对；175个约束来源、162项registry/metadata、13个保留原来源与恢复pre-place一致，new_actual_reads=[]，候选overlay保持。50个时钟的周期/波形与已审当前完整时序报告一致；内部时钟覆盖完整，外部input1/output2未设delay继续OPEN。

从归档纯函数独立重放当前reset graph、14个primitive导出、fanout及CDC，结果与integrity一致且issues=[]：7 async、4 AUX、3 HostSplit链，6目标，14项launch-C到data-Q归一化，688个实际BRAM端口时钟、10组consumer。CDC原始6、当前分类8、新未分类critical0；4项AUX代表源归一化只证明同一已核逻辑锥，正式安全仍OPEN。

当前DRC为15,917 Warning、1 RTSTAT-13 Critical Warning、0 Error；RTSTAT明确尚未充分布线，路由状态检查未运行，不记为正式DRC通过。94项报告bus-skew约束均MET，最差slack3.262ns；pulse-width all-violators没有条目。584条exception包含覆盖不足/零endpoint条目，clock-interaction有Ignored及Partial False Path；不推导安全或完整时序通过。

复用同身份已审timing、fresh80与congestion：setup WNS+0.147ns，但hold WHS−0.562ns、THS−1879.853ns、34,042个违例endpoint，时序仍FAIL。80个保护边界通过；拥塞为不同自适应窗口，尚无固定热点改善或C01因果结论。完整候选成员、全P落区、cut/timing/compliance与阶段回执另行核验。

详见 place_global_POST_review.json；未调用EDA、控制进程或锁、改生产/消费包或增加审批。
