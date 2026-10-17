# E008 / R001：C01向SLR2卸载与完整implementation

execution_state: running；verdict: unassessed。

AT001_C01_slr2_offload_full_implementation于2026-10-17T04:50:44.658893Z实际启动。[启动收据](attempts/AT001_C01_slr2_offload_full_implementation/started.json)、[35源/144输入/原生/唯一资源核验](attempts/AT001_C01_slr2_offload_full_implementation/native_start_verified.json)。当前恢复父网表，尚无place/physopt/route完成结果。

唯一主动变量为C01 exact `g_row_branch[1].u_branch_leaf`的SLR2 hard非排他且不限制走线Pblock。恢复E005 debug_materialized DCP，SSI_SpreadSLLs place→Default physopt→Default route；不重复综合/OPT/debug或无关功能测试。实际运行入口3cae，真实选择和前置终态见[执行绑定](../../../../../.research-agent/decision_inputs/E006_R006_AT003_C01_selected_E008_execution_20261017.json)。

每阶段重验实际成员、约束、80保护和全部P落区；合法route与正式setup/hold/PW/CDC/reset/IO分别验收。单EDA及资源保护、正常无墙钟/无输出强停保持。无bitstream、GPU、板卡、PPL/ACC。
