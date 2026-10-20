

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-20T08:57:35.240611+00:00。来源修订：`cfb9c0cd3fc1`。

# E012 / R004 运行结果

[负责人维护的本批运行记录](run.md)

# R004 — 冻结1024文档的正式数值测量

状态：采集未完成，Q001已停止；verdict: inconclusive。2026-10-19 13:45（UTC+8），G003/AT005在汇总收尾阶段触及既定900秒墙钟预算，cost_stop/exit124；源码未变、worker已回收。完整成功attempt覆盖112篇（B001 16篇及G001/G002各48篇），其中仅B001的16篇已完成独审。队列记录160篇durable输出另含失败AT005的48篇，不能当作160篇完整验收；其余864篇未启动。全1024采集和原全量后处理均未完成，六列完整图依赖任务随原队列失败停止，最终图未生成。后继新采集计划尚未启动。开发批R003/AT010不并入正式文档统计。

以下13:00启动段及自动出图描述均为历史记录，当前状态以上述停止回执为准。

以上数量是2026-10-19 13:00（UTC+8）的启动快照。剩余有限队列Q001已在后台启动，固定24组、总墙钟23400秒；[启动证据](queues/Q001/root_launch_receipt.json)记录自有进程身份。进度写入`queues/Q001/queue_events.jsonl`，终态才生成`queue_receipt.json`。25份独审、全1024聚合、主图及可读报告只在完整采集后自动执行，预定输出为`analysis/Q001/`。后台启动不表示这些未来产物已经存在，也不表示精度保持通过。

本批严格延续M005 v3数值协议：同基础量化、整数权重、LUT及共同出口，比较当前中间位宽与保留中间精度的参考；逐文档记录同输入局部误差和两条自由传播轨迹的32层及末端误差，不运行ACC/PPL。

输入唯一来自R003/AT009冻结token流，与AT001同一1024源文档（web512/news256/reviews256），103700实际token、最大128，不重新取样、不padding。输入计划固定2:1:1域交织且保持各域内既定顺序，预定15审计候选不按数值结果更换；重复来源簇和token前缀分别核查。

AT001准备输入顺序、身份与64个逻辑批次边界，不做模型推理，已经完成。AT002测量B001的16文档，484.95秒完成且源码未变、工作进程已回收。余下B002–B064按成本合为24个预先冻结的运行组，共1008文档；每组至多48文档、1个预定审计文档，保留全部32层原始hidden的组至多32文档。分组仅依据已测时间、存储与冻结审计名单，不依据误差。每一实际启动另记AT，CPU1/RSS8GiB/GPU24GiB、最多900秒、全attempt256MiB及当前GPU资源准入保持不变。队列遇失败、触限、源码变化或覆盖不足即停，不重试、不删样、

（摘录截断；完整记录见链接。）

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_frozen_formal_input_plan](attempts/AT001_frozen_formal_input_plan) | completed | CPU input plan preparation only; numerical measured0 | [执行收据](attempts/AT001_frozen_formal_input_plan/run.json) · [report.md](attempts/AT001_frozen_formal_input_plan/report.md) |
| [AT002_formal_batch_b001_numerical](attempts/AT002_formal_batch_b001_numerical) | completed | First formal numerical group B001:16/1024 docs,1645 real tokens,32 layers/doc,384 local sites/doc,no task metrics. Full execution and selected raw arithmetic audit complete;numerical preservation verdict not yet established. | [执行收据](attempts/AT002_formal_batch_b001_numerical/run.json) · [report.md](attempts/AT002_formal_batch_b001_numerical/report.md) |
| [AT003_formal_group_g001_b002_b004](attempts/AT003_formal_group_g001_b002_b004) | completed | execution only; five numerical nodes plus propagation; independent numerical verdict pending | [执行收据](attempts/AT003_formal_group_g001_b002_b004/run.json) · [report.md](attempts/AT003_formal_group_g001_b002_b004/report.md) |
| [AT004_formal_group_g002_b005_b007](attempts/AT004_formal_group_g002_b005_b007) | completed | execution only; five numerical nodes plus propagation; independent numerical verdict pending | [执行收据](attempts/AT004_formal_group_g002_b005_b007/run.json) · [report.md](attempts/AT004_formal_group_g002_b005_b007/report.md) |
| [AT005_formal_group_g003_b008_b010](attempts/AT005_formal_group_g003_b008_b010) | cost_stop | execution only; five numerical nodes plus propagation; independent numerical verdict pending | [执行收据](attempts/AT005_formal_group_g003_b008_b010/run.json) · [report.md](attempts/AT005_formal_group_g003_b008_b010/report.md) |

## 本批问题与交付文件


## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
