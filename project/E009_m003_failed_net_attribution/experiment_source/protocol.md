# E009 / SM013：失败网全量归因协议

M003 contract.md §4 与 SM013 为授权和范围。工程 A006 唯一 EDA，A007 独立审核；Root负责选型/mission/results。只写本新实验和 A006 状态，旧 E008、生产 RTL/XDC 和144生产输入只读。模型期望 gpt-6.1-sol / xhigh；实际模型/强度无独立回执，不声称已核实或切换。

基线为 E008/R001/AT004 route_failed.dcp，765705446B / SHA256 51679d9a4f8dc35c5e5b167ebbecd72260b0862f85ad8168782646f0fc16da21；547548冲突网与702396重叠节点分开。完整查询范围、归一规则、literal seeds、80保护匹配、字段/深查/时序上限和退出条件冻结在 query_plan.json / targets.tcl；prepared_manifest.json绑定实际脚本和基线，载图前与终态重新核身份。

先CPU离线复用报告与协议对照；check_cpu.py用独立小例验证别名计数差异、唯一主组、unknown/multidriver/INOUT、非可加consumer与union。真实原生入口 attribution.tcl：open_checkpoint；route status/schema；器件site→SLR/clock-region与全图轻量cell身份/位置；原生CONFLICTS网的segments闭包和全部leaf/top-port端点；固定补充种子；独立aggregate.py唯一归组/前20；固定深查属性、物理site/tile、有限代表时序；最终重算、正常结束。不综合/opt/place/physopt/route、不加载新XDC/修改对象、不写DCP。

每canonical网络只入(driver归一模块,sourceSLR,sorted loadSLR set)一组；主组计数必须等于canonical全集。raw native objects、alias、canonical与原报告差异逐项保留，不凑数。多driver/INOUT/无driver/无位置独立显示；consumer/region incidence不相加。前20和固定补充按canonical ID union计算覆盖，分母为实得canonical失败全集。节点完整映射、全cut TNS、每网SLL未测写NOT_MEASURED。

批量属性/缓冲TSV；失败网每4096个仅一次进度，pin每16384批次；不逐pin同步刷日志。深查以查询清单耗尽结束，不追新类、不递归fanin/fanout、不全设计source×sink笛卡尔积。新类列缺口，由Root另定后继R。

CPU0–7/max8/nice5；单EDA含仿真/编译；树RSS192GiB、MemAvailable48GiB持续30s、disk30GiB。supervise.py复用已审进程树资源助手，核PID/start，触发只清本任务所有进程；正常无墙钟/静默强停。原生进程与supervisor/代理状态分开；同范围常规工具失败新AT，范围变更新R，旧证据不覆盖。

产物位于AT/evidence/native/：attribution_manifest.json、failed_nets.tsv、module_region_summary.tsv、candidate_endpoints.tsv、unknowns_and_coverage.json、raw_conflicts/aliases/endpoints/cells/sites与深查/timing原证据。工程结果需A007独立审核才能提交G1，取数成功不证明根因唯一或改造有效。
