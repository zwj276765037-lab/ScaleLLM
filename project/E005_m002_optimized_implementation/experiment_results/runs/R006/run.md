# R006：各自closed place/physopt DCP的只读比较补采

execution_state: completed
verdict: 合同比较只读测量已完成；R004/AT004合法布通FAIL保持
applicability: 仅SM009/E005 R004/AT003各自closed place/physopt。AT002两phase各60query0及AT003两phase各15query0均已自然0/0闭合；新峰仅保留48来源行中的12峰行→10unique区域映射，fixed拥塞UNAVAILABLE，不代表routed签核。

本批工程收尾已完成，当前无活动EDA。AT001 pre-EDA准入失败原样保留；AT002完成80边界/94net/14上游/原placed device映射/旧48窗/层次等补采，AT003按主控确认的原合同比较义务只补新最坏峰区域。两次均在各自精确closed DCP只读执行，无重放物理命令或写checkpoint。144生产输入、两原DCP、实际源码与来源绑定保持，全部原PID-start无活体，实际锁释放与资源复算已核；A007独立审核完成。见[工程最终报告](../../engineering_final_report_2026-10-16.md)、[AT002终态](attempts/AT002_closed_place_physopt_readonly/readonly_terminal_summary.json)、[AT003终态](attempts/AT003_new_peak_windows_readonly/readonly_terminal_summary.json)。

AT002空new_peak_source_reports检查仅N/A，未作为新峰已测证据；AT003独立补齐12峰/10区域。新旧fixed拥塞无已验证API，明确UNAVAILABLE，occupancy不是拥塞等级，缺席不是0。本轮不再自动开启新implementation或额外实验。以下保留原计划和各阶段实际历史。

## 原始补采范围与计划（历史）

目标是补充80边界与14上游控制源的实际driver REF/位置/SLR、leaf pins与unique cells单位、逐SLR负载和位置包络、源相对精确跨SLR负载、三个精确层次利用率、旧48个原生窗口的实际GRID/tile/site/SLR资源与连接分布。56个原placed LOC以同part实际device拓扑映射，不能改用physopt LOC替代。fixed-window原生拥塞API若未获实际支持，明确UNAVAILABLE；资源/连接占用不是拥塞等级，缺席不能记为0。

非生产草稿位于`agent/A006/physical_supplement/`，含双phase调度、定向查询、目标、监督wrapper。双phase守卫8项隔离纯Tcl检查通过（不用Vivado/不加载真实DCP），Python AST和Tcl结构complete通过；均不代表实际查询API或补采已验证。执行前归档实际源码与jobs、绑定父证据/各phase DCP/命令/integrity/约束和route终态；结束后再核原DCP和生产源身份。

沿用CPU0–7/max8/nice5、单EDA锁、树RSS192GiB、MemAvailable48GiB持续30秒、disk30GiB；无wall/no-output期限。真实失败逐项保留，不扩大范围或无依据重复。无bitstream/板卡/GPU/PPL/ACC；正式安全与时序验收独立。

## 首次准入失败与AT002真实启动

AT001于14:00:14.841Z实际分离启动supervisor868884/start927177312，准入guard因两条旧CPU回执缺execution_state而在Vivado前自然return1，原attempt/report未由wrapper创建。现已以[preflight_failure](attempts/AT001_closed_place_physopt_readonly/preflight_failure.json)独立归档argv、原source、时间/PID-start、return1及stderr；明确未执行EDA。两个旧CPU-only回执原结束/退出与leader PID-start及双hash已核；不改历史失败或原综合UNKNOWN恢复边界。窄修guard的[固定快照/差异](attempts/AT001_closed_place_physopt_readonly/guard_repair_snapshot/manifest.json)、23CPU实际PASS及144原输入实核已保留，A007异步窄复核无实质阻碍，不构成新门。

AT002于14:09:18.658Z实际启动supervisor874653/start927231694；native metadata14:09:31.002Z，leader874789。实际持原单EDA FLOCK，CPU0–7/nice5、max8，无wall/no-output停点；原生日志已调用open_checkpoint各自closed place DCP并加载指定part。见[原生启动观察](attempts/AT002_closed_place_physopt_readonly/native_readonly_started_observation.json)，当前尚未把查询API或输出判为已验证。该新尝试不运行place/physopt/route或checkpoint写入；原R004/AT004自然failed receipt/five capture0、144freeze及进程/锁闭合先已封存。

## AT002 placed阶段已自然完成，physopt继续

placed原生phase receipt code0，epoch1792159776→1792160831，共60项query均0；实际close_design返回后独立目录已固定。见[placed小事实](attempts/AT002_closed_place_physopt_readonly/place_readonly_closed_phase_summary.json)及其绑定的完整原始文件/producer，原place DCP重hash仍32b4af05…，实际archived4cfa wrapper及Tcl源身份未变。80边界、94nets、原56placed LOC的实际device映射和48旧窗均齐。

精确源相对跨SLR leaf pins为Attention0、Gate1917、Down0；Gate rows2/4/6/7各384、row5为381，源均SLR1而负载在SLR0。14个上游net共389leaf pins，其中13跨SLR。此前79组负载各在单一SLR不代表driver与负载同区。fixed-window congestion明确UNAVAILABLE，资源占用和attached segments不作拥塞等级/边界crossings。已真实消息通知主控及A007先行只读审核，原会话继续打开physopt，不因审核增设等待。完整双phase/144freeze/进程锁自然终态仍待核。

## 剩余新最坏窗口映射义务与定向准备

A007复核确认当前AT002定向窗口为旧48窗；新place/physopt报告各48行、45unique区域与旧窗端点零重合，现有旧窗aggregate不足以CPU推导新最坏区域。主控明确这是原合同的剩余比较义务：AT002自然终态后使用新AT003，各自精确closed DCP仅测12方向/type峰行对应10unique新区域，保留原新报告全部48行并明确映射选择范围；不重80/94net/层次或物理命令，不热改当前源，无新审批门。

独立目标见[R005固定清单](../R005/R006_current_peak_window_targets.json)，准备源码位于`agent/A006/new_worst_window_supplement/`，V2固定快照`fixed_preparation_v2/manifest.json`。已对齐NW001–NW010/每个native_line与source index，新增目标/source报告绑定及post保持；原7个准入/closure/freeze函数AST与已审4cfa相同。9项CPU检查、Tcl结构和48/10范围实际通过，producer/log/facts固定；均仅为准备，AT003尚未启动。固定拥塞API仍UNAVAILABLE，资源占用不替代等级。原AT002继续正常physopt旧窗提取。

## AT002双phase与自然终态闭合，AT003实际原生启动

AT002于14:45:12.436500Z自然native/监督0结束，stop=null、无cleanup/无survivors。place/physopt各60项query均0，完整144输入/两原DCP/archived源/contract/input绑定保持，原全部身份无活体、实际FLOCK probe取得并立即释放、资源复算一致，共20项工程核验true；见[终态小事实](attempts/AT002_closed_place_physopt_readonly/readonly_terminal_summary.json)。physopt精确源相对cross-SLR仍input0/Gate1917/Down0，上游13；见[独立physopt小事实](attempts/AT002_closed_place_physopt_readonly/physopt_readonly_closed_phase_summary.json)。422资源样本，树RSS采样峰约22.775GiB，MemAvailable约375.224GiB、磁盘约403.499GiB，精确bytes及最大间隔5.146364秒在facts中保留。此时只闭合旧48窗/80边界等补采，新最坏峰区域仍待后继。

AT003于14:46:05.456829Z实际detach，14:46:16.548276Z原生started：supervisor899702/start927452343、leader899811/start927453483、native899901。原日志明确打开各自closed place.dcp及正确part；实际kernel FLOCK、4原PID/start、CPU0–7/nice5、archived wrapper a4178f和Tcl源均核符，见[实际原生启动观察](attempts/AT003_new_peak_windows_readonly/native_readonly_started_observation.json)。实际输入清单28540bytes/SHA6e921e313e7cae05c3ae7a341784d0973822aeac6a1acf71760d9a2ffe5a343f；V2已获[A007静态复核](../R005/R006_AT003_new_peak_preparation_review_evidence.json)，不新增等待门。当前仅12峰行→10NW区域映射，实际查询/原生终态待核；不重复80/94net/层次或物理命令，不写DCP。

## AT003 placed新峰区域阶段已固定，physopt继续

placed原生phase自然0，epoch1792161981→1792162733（752秒）；15项query全0。见[新峰placed小事实](attempts/AT003_new_peak_windows_readonly/place_readonly_closed_phase_summary.json)及其绑定的完整facts/原表/10个tile列表/producer。原新报告48行全部保留，12峰行与NW001–NW010的行/区域关联和独立target严格一致，原place DCP重新hash不变、archived源与源报告身份保持。

10个新峰区域的site全部SLR1；各区SLICEL/M实际site容量2944–3072、occupied同值，表示每个CLB站点已有primitive占用，不等于全部LUT/BEL容量占满或实际固定拥塞等级。primitive各区54671–56489；attached hierarchical net segments235599–323764。实际GRID矩形与tile/site/REF/SLR分布保留，重叠区域不相加；primitive连接计数不作边界crossings。原会话已继续独立加载physopt，placed成果已真实通知Root/A007先行审核，完整双phase/终态仍待核。

## AT003完整双phase与最终工程闭合

physopt phase自然0、epoch1792162733→1792163491（758秒），15项query全0；10区域资源/连接与10tile列表同placed，48来源行/12峰→10NW关联保持。AT003于15:11:38.117704Z自然native/监督0闭合、stop=null、无cleanup/无survivors，21工程核验全true。原899702/899811/899830/899901四个PID/start均不在，实际FLOCK probe取得即释放，144/2DCP/6archived源/两原新报告/独立target/contract/input身份保持。

300样本树RSS峰22.821053GiB、最低MemAvailable375.171288GiB、最低磁盘401.564053GiB、最大间隔5.157572秒，整会话1521.569428秒，无保护触发。见[完整终态](attempts/AT003_new_peak_windows_readonly/readonly_terminal_facts.json)、[新峰physopt独立审核](../R005/R006_AT003_physopt_new_peak_review_evidence.json)、[终态覆盖独立审核](../R005/R006_AT003_terminal_coverage_review_evidence.json)。固定拥塞仍UNAVAILABLE，新峰仅12峰/10unique子集。R004 route失败、正式时序/安全OPEN不被本次只读完成改变；主控据最终工程报告汇总，本工程不再开启EDA/测试。
