

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-17T08:36:24.995092+00:00。来源修订：`400c5b08f7ef`。

# E008 · m002_exact_hotspot_offload_implementation

关联：M002 / SM012

## 原始管理记录

- [实验协议](experiment_source/protocol.md)
- [来源摘要](experiment_source/summary.md)
- [结果摘要](experiment_results/summary.md)
- [状态摘要](experiment_status/summary.md)

## 当前结果摘录

# E008：AT003布局前资格通过，已实际进入place

AT003_C01_physical_xdc_fix_full_implementation于2026-10-17T07:43:04.819321Z（北京时间15:43:04）实际启动。39个归档源、b9dc包、所有绑定依赖及144生产输入一致；supervisor1560167/start933552991、native1560384/start933554214，CPU0–7/nice5、项目唯一EDA和lane占用已核。[真实启动事实](experiment_results/runs/R001/attempts/AT003_C01_physical_xdc_fix_full_implementation/native_start_verified.json)。父网表恢复完成；07:52Z实际成员子步骤已闭合，RAW9514/S9507/P9491、16个DSP内部对象归一到2个物理父，全部P当前未布局。10份本次账本经[独立增量核查](../../agent/A007/E008_R001_AT003_actual_stage_review_20261017/pre_place_membership_incremental_review.json)与AT002已审内容逐字节相同，原生资源与before策略已通过，08:05Z实际硬Pblock/物理XDC导出通过且[独立核验](../../agent/A007/E008_R001_AT003_actual_stage_review_20261017/actual_before_pblock_export_review.json)接受：30个SLR2时钟区精确覆盖X0Y10:X5Y14，三项策略=0、P9491、sites78266；1,598,546B真实XDC的9491名字无重复且与P全等。08:18Z原策略保留已真实通过并[独立核查](../../agent/A007/E008_R001_AT003_actual_stage_review_20261017/actual_policy_preservation_review.json)：9525 after全fresh、17schema与before一致，策略值/支持态逐对象相等，前后policy文件字节同，原Pblock0→仅新增指定区域。08:19Z[实际完整端口索引](experiment_results/runs/R001/attempts/AT003_C01_physical_xdc_fix_full_implementation/candidate_pre_place_native_port_index_closed_facts.json)闭合并[独立接受](../../agent/A007/E008_R001_AT003_actual_stage_review_20261017/pre_place_native_index_alias_review.json)：269ports/269groups/2772aliases/2170nativecalls，unknown/disconnected/multigroup=0，167160个buffered alias事件完整。有向cut和四组有界时序已闭合；完整restor

（摘录截断；完整记录见链接。）

## 每个运行批次

| 批次 | 详情 | 具体尝试数量 |
| --- | --- | --- |
| R001 | [本批结果与证据](experiment_results/runs/R001/README.md) | 3 |

## 原工程历史结果


本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
