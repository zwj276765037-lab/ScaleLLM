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
- Input non-drift：`final_input_recheck.json`。
- Limits：不是正常综合、implementation、时序/DRC签核、bitstream、板级或全32层数值验收。后续fresh synth入口与现有技术停点见工程报告。
