# AT004 outer physopt命令与新完整时序子步骤审核

execution：实际原生命令及新完整时序证据独立核验完成。verdict：接受命令native0与当前报告；全局时序仍因hold FAIL。applicability：AT004 Physopt postPlace图，完整physopt POST/fresh80/locality另审。review：独立子步骤接受，无新增停点。

phys_opt_design -directive Default实际149秒、13:26:15Z返回0。原生明确WNS≥0跳过全部setup物理综合优化，netlist未修改；命令、许可、结束文本与工程excerpt精确一致。physopt.dcp保存文本与580,691,314字节元数据已核；SHA仅引用A006身份记录，未读取或哈希DCP。

新timing_physopt.rpt为Physopt postPlace、min_max/report_unconstrained，12列指标及页眉后全部正文与实际place报告相同。独立复核42 intra/20 inter/17 other组表、50时钟与timer settings；setup WNS+0.147ns、TNS0、违例0，但hold WHS−0.562ns、THS−1879.853ns、违例34,042，时序仍FAIL。PW/skew摘要违例0。

报告仅日期、命令输出路径、阶段及页眉横线变化；没有hold修复或物理收益证据。外部input1/output2未设delay、6组unconstrained、report_methodology未运行及正式reset/CDC/IO OPEN保持。命令成功/新时序报告不等于完整physopt POST/locality通过，也不声称route成功。
