

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-18T00:06:15.625771+00:00。来源修订：`943abfac7fc3`。

# E001 / R003 运行结果

[负责人维护的本批运行记录](run.md)

# R003 — E001 · 构建与快速验证

Recorded: 2026-10-14T23:39:37.167430+00:00

Execution state: completed
Verdict: bounded_checks_pass_with_retained_warnings
Review: pending_project_controller

主控后续记录（2026-10-15）：限定范围核查已完成，见 [SM004审核](../../../../../results/reviews/SM004.md)；以上 pending 是工程交付时状态，非当前主控状态。用户全局验收未发生。

负责人：SM004/A006。详见[工程终态报告](worker_report.md)。

- Exact commands/cwd：各`attempts/ATxxx/command.json`或`commands.json`；工具原始`argv.txt`见报告目录。
- Host/tools：host user，Linux 6.17.0-35，Python3.12.3；Vivado/XSim2025.2，版本原文见工具report `tool_versions.txt`。
- Code/constraint/IP identity：各attempt `inputs.sha256`，完整RTL `elab_inputs.sha256`，BD `constructor_inputs.sha256`；真实内部BD参数与hash见AT007 `bd_address_decode_evidence.json`。
- Times/exits：各attempt `status.json`与工具`launcher_status.txt`；原始失败/受控终止保留，未覆盖。
- Oracles：CPU独立整数有限向量/Host边界，真实功能TB及独立字节地址oracle由R002负责人维护；BDD仅参数/连线配置与边界重算，未做SmartConnect全事务模拟。
- Qualified results：AT006 CPU49/49+static PASS；AT004 fullboard -rtl PASS，88RTL/0blackbox；AT007实际validate_bd_design退出0且保留4条地址别名critical和1条性能critical。
- Functional tool records：R002/AT002 DATA、AT003 CSR、AT008权重完整组、AT009真实前端XSim PASS；各选源适用性见`applicability_recheck.json`。
- Input non-drift：`final_input_recheck.json

（摘录截断；完整记录见链接。）

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_cpu_builder_and_environment](attempts/AT001_cpu_builder_and_environment) | 未登记；查看原记录 | 未登记 |  |
| [AT002_complete_board_rtl_elaboration](attempts/AT002_complete_board_rtl_elaboration) | 未登记；查看原记录 | 未登记 |  |
| [AT003_cpu_current_build_contract](attempts/AT003_cpu_current_build_contract) | 未登记；查看原记录 | 未登记 |  |
| [AT004_final_complete_board_rtl_elaboration](attempts/AT004_final_complete_board_rtl_elaboration) | 未登记；查看原记录 | 未登记 |  |
| [AT005_final_cpu_and_static_contract](attempts/AT005_final_cpu_and_static_contract) | 未登记；查看原记录 | 未登记 |  |
| [AT006_final_cpu_and_static_contract](attempts/AT006_final_cpu_and_static_contract) | 未登记；查看原记录 | 未登记 |  |
| [AT007_actual_bd_validation](attempts/AT007_actual_bd_validation) | 未登记；查看原记录 | 未登记 |  |

## 本批问题与交付文件

- [worker_report.md](worker_report.md)

## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
