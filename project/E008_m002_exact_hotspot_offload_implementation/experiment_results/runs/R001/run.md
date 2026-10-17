# E008 / R001：C01向SLR2卸载与完整implementation

execution_state: running（AT003真实运行）；verdict: unassessed。

历史AT002_C01_native_policy_fix_full_implementation于2026-10-17T07:14:16.993406Z实际启动，37归档源/45bbc、144输入、原生与本项目唯一EDA已核。[启动事实](attempts/AT002_C01_native_policy_fix_full_implementation/native_start_verified.json)。当时恢复父网表，随后自然失败，见下文真实终态；不能据此读取当前运行。

AT001于05:12:22Z因入口要求不受支持的RLOC_ORIGIN而自然exit1，14项收尾全通过。[原终态](attempts/AT001_C01_slr2_offload_full_implementation/terminal_summary.json)。最小兼容修复26例和独立审核通过；旧3cae、AT001全部证据保留。新实际绑定包含失败终态/修复身份，保持C01及原合同，并将后续同C01常规修复的真实来源登记与重试委派给工程，避免idle Root阻塞。

唯一主动变量为C01 exact branch[1]的SLR2 hard非排他且不限制走线Pblock。恢复E005 debug_materialized DCP，SSI_SpreadSLLs place→Default physopt→Default route；不重复综合/OPT/debug或无关功能测试。实际成员、约束、80保护、全部P落区及完整物理验收保持。正常无墙钟/无输出强停，无bitstream/GPU/板卡/PPL/ACC。


## AT002实际成员子步骤（07:25Z）

父网表恢复完成，实际RAW9514/S9507/P9491成员闭合；16个DSP内部primitive归一到2个实际DSP48E2父，P全UNPLACED。[独立增量核查](../../../../../agent/A007/E008_R001_AT002_actual_stage_review_20261017/pre_place_membership_incremental_review.json)接受10份账本及本次实际artifact身份。仅成员资格成立，resource/native policy/Pblock/完整pre-place和place/physopt/route尚待实际结果；没有停止或新审核等待门。


## AT002真实终态（07:36:55Z）

自然native1/supervisor1：write_xdc -constraints physical被2025.2拒绝。资源/before policy已闭合，9525对象unsupported RLOC_ORIGIN全native0/空；区域成员/站点回读已写，但after/全pre-place/place/physopt/route未执行。[终态审计](attempts/AT002_C01_native_policy_fix_full_implementation/terminal_summary.json)14项全通过、原进程退出/144保持/lane释放。工程建立一行API兼容修复与独立delta审核后直接新AT，不覆盖AT002，不新增审批门。


## 当前AT003真实启动（07:43:04Z）

[实际启动事实](attempts/AT003_C01_physical_xdc_fix_full_implementation/native_start_verified.json)：39归档源/b9dc、144输入、supervisor1560167/native1560384的PID/start与唯一项目EDA已核。07:42:53先发起launcher，07:43:04才真正native启动。仅一行write_xdc -type physical修复经9例/115身份独立delta接受，工程按a024委派直接绑定c8c3来源后续跑，无新审批门。当前恢复父图；完整export/after/preplace及place/physopt/route待实际结果。11 fresh scope对象正确构成为10 root/ancestor+1 u_silu内部层级，总scope9525。


AT00307:52Z实际父图恢复与成员子步骤闭合，10份账本已独立增量接受；RAW9514/S9507/P9491、16DSP内部→2父、P全未布局。07:53Z新原生资源资格执行中；export/after/fullpreplace与物理阶段均未完成。


AT00308:05Z真实硬SLR2 Pblock与物理XDC导出闭合，08:08Z[独立接受](../../../../../agent/A007/E008_R001_AT003_actual_stage_review_20261017/actual_before_pblock_export_review.json)：30区全覆盖X0Y10:X5Y14、三policy0、P9491/site78266；XDC1598546B/9491名字与P全等。after新鲜逐对象schema/策略一致性仍进行，无preservation/完整pre-place/place/physopt/route结论。


AT00308:18Z原策略保留闭合并独立接受：9525fresh after/17schema、前后policy文件字节同、原Pblock0→仅指定新区域。08:19Z完整原生端口索引闭合并独立接受，269ports/269groups/2772aliases/2170calls、167160buffered alias事件完整；[索引捕获](attempts/AT003_C01_physical_xdc_fix_full_implementation/candidate_pre_place_native_port_index_closed_facts.json)。08:23Z有向cut仍正常导出，timing/global完整preplace/物理阶段未完成。


## AT003真实进入place（08:33Z前，08:35Z观测）

[完整restored preplace阶段事实](attempts/AT003_C01_physical_xdc_fix_full_implementation/pre_place_closed_stage_facts.json)记录原策略/cut/四组timing/restore全门，原源与144保持，restore guard native0、blackbox0/DRCblocker0/clockgroups1。实际日志已调用place_design SSI_SpreadSLLs并进入Phase1.3；全独立复核继续，无新等待门。当前未place完成/未physopt/未route。有界未布局入setup/hold+6.158/-0.074、出+6.859/+0.081ns，不做跨阶段改善或签核结论。
