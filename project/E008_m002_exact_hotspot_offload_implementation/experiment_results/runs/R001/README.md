

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# E008 / R001 运行结果

[负责人维护的本批运行记录](run.md)

# 当前终态：AT004自然布线失败

19:09:25Z原生route失败，702396 node overlaps/547548 congestion failed signals；21:18:30.695127Z native/supervisor1自然结束。14项收尾全true、两observer exit0、无活动EDA/新AT。[终态事实](attempts/AT004_C01_PDU_resume_full_implementation/terminal_facts.json)；[当前压缩结果](../../summary.md)；[详细失败包](attempts/AT004_C01_PDU_resume_full_implementation/failed_route_terminal_summary.json)；[独立审核/最终工程交付](attempts/AT004_C01_PDU_resume_full_implementation/terminal_engineering_delivery_facts.json)。

以下为保留的逐阶段历史，早期running状态不代表当前实态。

# E008 / R001：C01向SLR2卸载与完整implementation

execution_state: running（用户已明确恢复，AT004实际启动）；verdict: unassessed。

历史AT002_C01_native_policy_fix_full_implementation于2026-10-17T07:14:16.993406Z实际启动，37归档源/45bbc、144输入、原生与本项目唯一EDA已核。[启动事实](attempts/AT002_C01_native_policy_fix_full_implementation/native_start_verified.json)。当时恢复父网表，随后自然失败，见下文真实终态；不能据此读取当前运行。

AT001于05:12:22Z因入口要求不受支持的RLOC_ORIGIN而自然exit1，14项收尾全通过。[原终态](attempts/AT001_C01_slr2_offload_full_implementation/terminal_summary.json)。最小兼容修复26例和独立审核通过；旧3cae、AT001全部证据保留。新实际绑定包含失败终态/修复身份，保持C01及原合同，并将后续同C01常规修复的真实来源登记与重试委派给工程，避免idle Root阻塞。

唯一主动变量为C01 exact branch[1]的SLR2 hard非排他且不限制走线Pblock。恢复E005 debug_materialized DCP，SSI_SpreadSLLs 

（摘录截断；完整记录见链接。）

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_C01_slr2_offload_full_implementation](attempts/AT001_C01_slr2_offload_full_implementation) | failed | AT001 naturally failed before place in placement_policy: RLOC_ORIGIN unsupported by actual native schema; pre-place literal membership substep accepted, no full pre-place/place/physopt/route completion. No stop or cleanup. 14 clo… | [执行收据](attempts/AT001_C01_slr2_offload_full_implementation/run.json) · [report.md](attempts/AT001_C01_slr2_offload_full_implementation/report.md) |
| [AT002_C01_native_policy_fix_full_implementation](attempts/AT002_C01_native_policy_fix_full_implementation) | failed | Naturally failed at write_xdc -constraints physical (2025.2 invalid option); resource/before policy closed; after/fullpreplace/place/physopt/route not executed; all14 closure checks passed, owners/lane/144inputs closed; C01 physi… | [执行收据](attempts/AT002_C01_native_policy_fix_full_implementation/run.json) · [report.md](attempts/AT002_C01_native_policy_fix_full_implementation/report.md) |
| [AT003_C01_physical_xdc_fix_full_implementation](attempts/AT003_C01_physical_xdc_fix_full_implementation) | cost_stop | USER_REQUESTED_PDU_SHUTDOWN_PAUSE. Explicit user stop, not method failure or success. Actual place Phase1.3 interrupted; full preplace independently accepted, no current DCP; all14 closure checks/PID/lane/144/source verified. No … | [执行收据](attempts/AT003_C01_physical_xdc_fix_full_implementation/run.json) · [report.md](attempts/AT003_C01_physical_xdc_fix_full_implementation/report.md) |
| [AT004_C01_PDU_resume_full_implementation](attempts/AT004_C01_PDU_resume_full_implementation) | failed | AT004 same-C01 full implementation naturally failed route: native702396 node overlaps/547548 congestion failed signals, native1/supervisor1/no stop/no cleanup. Complete place/physopt independently accepted; failed graph9491 origi… | [执行收据](attempts/AT004_C01_PDU_resume_full_implementation/run.json) · [report.md](attempts/AT004_C01_PDU_resume_full_implementation/report.md) |

## 本批问题与交付文件


## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
