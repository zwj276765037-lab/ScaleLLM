# SM016/G3b：v3固定入口与联合回归独立接受

**A007结论：G3b无实质阻断，A006可按Root既有授权直接登记新R/AT并开始正式create/synth。** G3a已另行接受；本结论尚不代表新网表、G4或任何物理/时序结果。

适用入口为41源manifest `62d55ff983e6d8062d448e2ac0e5c690d092b4eead0d8512e56a255c3dbfa96c`，G2仍`4424c426…`，三RTL仍MLP `5829f33f…`、resident `55f3e8ef…`、core `672d37c9…`。完整绑定：[正式JSON](G3b_consolidated_review_v3.json)；[最后身份复核](G3b_entry_v3_62d55f_review/final_binding_check.json)，工具chunk `5574b4` exit0。

已完成独立审核：

- 41项当前源及归档全SHA一致。launcher、安全辅助代码的实际本地Python传递import和Tcl依赖纳入冻结；四公共入口旧字节经工程逆补丁重建，均等于SM014冻结SHA，最终diff正文独立复算全等。144旧输入由工程实际重核137不变，仅3RTL+4入口变化；A007独立核其7项变化与4份diff，没有重复全144扫描。
- 同版288项联合回归原log逐项成功，69份实际源/预归档匹配；42项资格/来源/Tcl/probe检查包含其中。A007另独立重放这42项exit0，前后41源不变。七项native的原生范围沿用[G3a](G3a_consolidated_review.md)及[生产smoke审核](AT003_selected_production_smoke_review.json)，不扩写成完整板级/DDR命令测试。
- 实际Tcl变量独立序列化与冻结JSON逐项相等：81组/13120bit/23CR、两片各40URAM与3480CLB site、25个C01保护名。组映射/资源池继续绑定已审G2，不凭名字local推断物理通过。
- overlay正式enabled/global/implementation-only/LATE；运行临时工程凭原XPR注册回执核源，恢复先核现有约束而不reapply。角色、pin、CE/master/own-state/原core17、S/L/R/reset/clock、25/80保护、精确池、原生URAM端口/cascade、来源、预算与恢复负例已落实；fixture不得作为native结果。
- 同stage预算固定已核E005基线，拒绝改名route、错device/tool/header，报告利用量与raw primitive区分。81新LUT1、34helper FF及局部增量锥另核，不能以旧route净数证明预算。
- 原严格reset/CDC/debug/clock/IO/resource谓词保留。新适配仅更换新综合lineage、显式OPT成功回执和已说明的debug阶段入口；新逐phase probe从真实新synth/当前phase CDC与core OOC warning生成，禁止覆盖，绑定原件/归档/阶段manifest，由hook检查native身份。preplace包绑定最终stage_inputs/source_archive。

旧v1 `89b956`因依赖冻结不全、v2 `cb7256`因缺phase probe生成，均保留原件/源并未获G3b总体无阻断；v3在同设计内修复，旧失败/回归证据保持。未通过改RTL/期望或删除断言消除失败。

后续SM017仍须实际新综合23 produced/22 consumed DCP身份、新图对象/API/80保护/URAM和控制集/预算/宏与硬约束资格，以及原INIT→显式OPT/debug严格preplace门。A007只在真实G4包出现后给包SHA绑定的独立结论；A006据原review派生回执，再按SSI_SpreadSLLs/Default/Default完整实施，不增加逐项批准。

正常进程无墙钟/静默强停；单EDA及原资源保护不变。TOP01−2.896ns未直接处理、差22049 OPEN和拥塞风险保持，不承诺一次布通。execution=审核完成，verdict=当前入口/联合回归支持，applicability=上述精确版本，review=A007独立；全局/用户验收尚未发生。
