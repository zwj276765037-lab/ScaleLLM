

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-20T08:57:35.240611+00:00。来源修订：`cfb9c0cd3fc1`。

# E005 / R002 运行结果

[负责人维护的本批运行记录](run.md)

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
- [新源冻结](../../../experi

（摘录截断；完整记录见链接。）

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_cpu_entry_checks](attempts/AT001_cpu_entry_checks) | 未登记；查看原记录 | 未登记 |  |
| [AT002_installed_directive_preflight](attempts/AT002_installed_directive_preflight) | 未登记；查看原记录 | 未登记 |  |
| [AT003_installed_directive_property](attempts/AT003_installed_directive_property) | 未登记；查看原记录 | 未登记 |  |
| [AT004_installed_classic_flow_help](attempts/AT004_installed_classic_flow_help) | 未登记；查看原记录 | 未登记 |  |
| [AT005_final_cpu_entry_checks](attempts/AT005_final_cpu_entry_checks) | 未登记；查看原记录 | 未登记 |  |
| [AT006_fresh_create](attempts/AT006_fresh_create) | 未登记；查看原记录 | 未登记 |  |
| [AT007_supervision_recovery_cpu](attempts/AT007_supervision_recovery_cpu) | 未登记；查看原记录 | 未登记 |  |
| [AT008_supervision_recovery_cpu_cwd](attempts/AT008_supervision_recovery_cpu_cwd) | 未登记；查看原记录 | 未登记 |  |
| [AT009_project_OPT_recovery_cpu](attempts/AT009_project_OPT_recovery_cpu) | 未登记；查看原记录 | 未登记 |  |
| [AT010_current_CDC_recovery_cpu](attempts/AT010_current_CDC_recovery_cpu) | 未登记；查看原记录 | 未登记 |  |

## 本批问题与交付文件


## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
