# AT004 place 完整时序与 fresh80 子步骤审核

本轮全局 place 时序 **未通过，原因是 hold**。Fully Placed 原生报告及完整摘要重放一致：WNS +0.147 ns / TNS 0 / setup 违例端点 0；WHS −0.562 ns / THS −1879.853 ns / hold 违例端点 34,042。该报告 WPWS/TPWS 与 PW-skew 违例数为 0。

相同阶段旧 E005 为 WNS +0.103、WHS −0.695、THS −2145.408、hold 违例端点 30,885。本轮 worst slack 和累计 hold slack较好，但 hold 违例端点增加 3,157；setup/hold 总端点增加 11，PW-skew 总端点增加 59。变化混合，不判整体改善或 C01 因果。timer settings、时钟表及 core100MHz/双DDR UI200MHz保持一致。

内部 no_clock/constant/PW-clock/unconstrained 为 0，外部 input1/output2 无delay及 6 项 unconstrained clock groups 保留；report_methodology 未运行的声明仍在。完整时序摘要不是所有接口约束、安全或 routed timing 签核，工程原“DRC now running”已用独立澄清记录标明为旧观察措辞，时序身份和数值未改。

本轮 **fresh80 结构子步骤通过**：80 个唯一保护边界为 input48/gate16/down16，DONT_TOUCH全1，LUT类型/INIT/CE负载宽度256/384/512与已审合同一致；所有driver LOC/BEL与负载SLR/范围均有实际值。14条control-source原始行及闭合结果/原生日志marker已核。此处是本轮新测，不再只是pre-place继承证据。

完整POST、候选P对应关系/SLR2落区和后续physopt/route仍须各自真实验收；本记录不替代这些门，也不新增审批或EDA。

[完整时序审核](place_full_timing_report_review.json) · [fresh80结构审核](place_fresh80_structure_review.json)
