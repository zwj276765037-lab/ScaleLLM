# R002 — E005

Recorded: 2026-10-16T00:23:02.482262+00:00

Execution state: completed
Verdict: supported（入口CPU/native preflight及fresh create）；综合/实现另批判定

- A006唯一EDA调度者，SM009当前授权；A009的三RTL/TB及功能解释独立负责。期望gpt-6.1-sol/xhigh，actual unverified。
- AT001初始CPU150+6通过；AT002轻量preflight因空内存工程无impl_1自然exit1，原help保留；AT003在真实目标空工程实际接受SSI_SpreadSLLs；AT004在指定part后原生classic help及FLOW实际核验通过，native/监督0。早期无part的Advanced Flow帮助不作为当前器件适用结论。
- [AT005最终CPU入口](attempts/AT005_final_cpu_entry_checks/status.json)：151+6+11+11=179项通过、输入身份未变；覆盖失败取证原错误传播/逐项catch/不覆盖/无design/成功不变/失败父链拒收、新E005动态源anchor及源变更拒收、监督隔离和板级构建/ROM输入资格。没有EDA。
- [入口小facts](entry_preparation_facts.json)保存安装版help/属性、CPU和当前脚本身份；原AT001后preflight Tcl/runner记录项变化已明确，AT004/AT005覆盖更新后范围。
- R001功能：Attention AT001 v1已PASS；MLP AT002 v1 TB声明顺序编译失败保留，AT003 v2已PASS。原native/监督退出0、输入运行后hash核对及协议/oracle覆盖由A009报告，不把功能PASS当作物理结构落实。
- [AT006 fresh create](attempts/AT006_fresh_create/started.json)于2026-10-16T00:46:50Z附近真实启动，supervisor151633、leader151639、native151741/start922416983，实际CPU0–7/nice5。全新project `project/hardware/vivado/project/m002_E005_R002_AT006_fresh`，report `project/hardware/vivado/reports/m002_E005_R002_AT006_fresh_create`。
- [新源冻结](../../../experiment_source/frozen_inputs_before_create.json)141项，SHA `f94724cb255978e7f77acd8f5f0cc0f7dfb025b6ae8c272aaccac1eb17f21dc1`。constructor实际输入另由原native日志与constructor_inputs.sha256绑定；不是E003旧源身份。
- 当前create无wall/no-output上限；单lane8CPU/max8/nice5、RSS192GiB、MemAvailable48GiB持续30秒、disk30GiB保护。冻结输入运行期间不改，正常进程自然结束。
- create真实终态后自动进入R003新的正式综合；新网表48/32边界/负载图仍未执行，不预填功能或可布通结论。place/physopt/route在R004继续，时序/CDC/reset/板级各自判定。

AT006于2026-10-16T00:52:14.857095Z自然结束，native/监督0、stop null、无survivors，峰RSS2.745GiB；原进程身份退出、141源hash全部未变，真实constructor PASS及core100/UI200+200元数据存在。[终态小facts](attempts/AT006_fresh_create/completion_facts.json)。创建scope只为validated BD/generated IP，不等于综合/布通；R003/AT001已自动真实启动，当前重工具lane由新综合持有。

A run record alone does not establish PASS or a method verdict.

## 原综合闭合后的监督恢复入口（AT007/AT008）

原controller与wrapper已自然0，原监督UNKNOWN/观测缺口保留。4个未被实际342源绑定的工程入口在闭合后适配独立closure；原版本在R003/AT001/engineering_inputs_before_supervision_recovery。AT007从仓库根discover导致包导入失败，原native1/完整日志保留；AT008用project/hardware包根重跑，实际164项CPU PASS、12输入before/after全同，无残存。覆盖缺wrapper、native/POST非零、resource stop、残存/同PID活进程及source/closure/DCP/资源快照篡改。真实freeze --handover native0，342源/45DCP独立资格通过；新142物理输入冻结见experiment_source/frozen_inputs_before_physical.json。

## AT009 — 安装后的fresh-project OPT恢复回归

04:17:53Z启动、04:18:29.886Z完成，198项CPU（原164+新增34）全部通过，native/supervisor0、stop=null、无owned残留；[完成facts](attempts/AT009_project_OPT_recovery_cpu/completion_facts.json)、[最终安装差异](attempts/AT009_project_OPT_recovery_cpu/installed_entry_changes.diff)。144输入前后不变；安装后的真实OPT原来源只读再资格通过，原342源/45DCP不变。不将草稿遗失末输出的回归观测冒充通过。后继R004/AT002已直接启动，无额外审核停点。
