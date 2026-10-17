# A004 当前阶段任务

SM006 reset优先级告警只读核查；核对3个现有RTL的复位控制语义。关联E002及[执行合同](../../mission/M002_ddr_separation_and_timing_recovery/implementation_contract_2026-10-15.md)。本轮实际runtime=/root/m002_rtl_repair，沿用期望gpt-6.1-sol/xhigh；实际配置未另核实。写入边界/资源见合同。

## 历史任务入口

# m002_rtl_repair

角色：engineering；SM：SM002；M：M002；实验：E001（SM004整合，覆盖SM002/SM003依赖）。

当前合同：[mission/M002_ddr_separation_and_timing_recovery/repair_contract_2026-10-15.md](../../mission/M002_ddr_separation_and_timing_recovery/repair_contract_2026-10-15.md)。实际本轮子任务：/root/m002_rtl_repair，未绑定任何长期工作对话。

所有权：RTL、对应TB；R002 worker_report；不写Vivado脚本或Host。资源：agent 1，不分叉；CPU轻量测试，EDA仅A006。工程与重工具边界见合同。

重要阶段通过实际collaboration消息通知主控；结果和源身份留在 E001/R002。最终主控整合三摘要。
