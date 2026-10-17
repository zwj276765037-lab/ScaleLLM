

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-17T08:36:24.995092+00:00。来源修订：`400c5b08f7ef`。

# E008 / R001 运行结果

[负责人维护的本批运行记录](run.md)

# E008 / R001：C01向SLR2卸载与完整implementation

execution_state: running（AT003真实运行）；verdict: unassessed。

历史AT002_C01_native_policy_fix_full_implementation于2026-10-17T07:14:16.993406Z实际启动，37归档源/45bbc、144输入、原生与本项目唯一EDA已核。[启动事实](attempts/AT002_C01_native_policy_fix_full_implementation/native_start_verified.json)。当时恢复父网表，随后自然失败，见下文真实终态；不能据此读取当前运行。

AT001于05:12:22Z因入口要求不受支持的RLOC_ORIGIN而自然exit1，14项收尾全通过。[原终态](attempts/AT001_C01_slr2_offload_full_implementation/terminal_summary.json)。最小兼容修复26例和独立审核通过；旧3cae、AT001全部证据保留。新实际绑定包含失败终态/修复身份，保持C01及原合同，并将后续同C01常规修复的真实来源登记与重试委派给工程，避免idle Root阻塞。

唯一主动变量为C01 exact branch[1]的SLR2 hard非排他且不限制走线Pblock。恢复E005 debug_materialized DCP，SSI_SpreadSLLs place→Default physopt→Default route；不重复综合/OPT/debug或无关功能测试。实际成员、约束、80保护、全部P落区及完整物理验收保持。正常无墙钟/无输出强停，无bitstream/GPU/板卡/PPL/ACC。


## AT002实际成员子步骤（07:25Z）

父网表恢复完成，实际RAW9514/S9507/P9491成员闭合；16个DSP内部primitive归一到2个实际DSP48E2父，P全UNPLACED。[独立增量核查](../../../../../agent/A007/E008_R001_AT002_actual_stage_review_20261017/pre_place_membership_incremental_review.json)接受10份账本及本次实际artifact身份。仅成员资格成立，resource/native policy/Pblock/完整pre-place和place/physopt/route尚待实际结果；没有停止或新审核等待门。


## AT002真实终态（07:36:55Z）

自然native1/supervisor1：wr

（摘录截断；完整记录见链接。）

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_C01_slr2_offload_full_implementation](attempts/AT001_C01_slr2_offload_full_implementation) | failed | AT001 naturally failed before place in placement_policy: RLOC_ORIGIN unsupported by actual native schema; pre-place literal membership substep accepted, no full pre-place/place/physopt/route completion. No stop or cleanup. 14 clo… | [执行收据](attempts/AT001_C01_slr2_offload_full_implementation/run.json) · [report.md](attempts/AT001_C01_slr2_offload_full_implementation/report.md) |
| [AT002_C01_native_policy_fix_full_implementation](attempts/AT002_C01_native_policy_fix_full_implementation) | failed | Naturally failed at write_xdc -constraints physical (2025.2 invalid option); resource/before policy closed; after/fullpreplace/place/physopt/route not executed; all14 closure checks passed, owners/lane/144inputs closed; C01 physi… | [执行收据](attempts/AT002_C01_native_policy_fix_full_implementation/run.json) · [report.md](attempts/AT002_C01_native_policy_fix_full_implementation/report.md) |
| [AT003_C01_physical_xdc_fix_full_implementation](attempts/AT003_C01_physical_xdc_fix_full_implementation) | running | Same C01 full implementation. Complete restored preplace actually qualified and real place_design SSI_SpreadSLLs running; closed member/resource/policy/Pblock/XDC/index accepted, cut/timing/full global preplace independent review… | [执行收据](attempts/AT003_C01_physical_xdc_fix_full_implementation/run.json) · [report.md](attempts/AT003_C01_physical_xdc_fix_full_implementation/report.md) |

## 本批问题与交付文件


## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
