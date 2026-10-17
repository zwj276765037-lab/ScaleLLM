# E006：已确认资源分布向SLR1集中，模块归属待原生提取

CPU读取E003/E005各自原生physopt报告，版本/器件与阶段一致。旧→新，SLR1 LUT268405→336107（+67702）、CLB Registers319883→435367（+115484）、BRAM tile160.5→468（+307.5）；两侧这三类资源均减少。全局LUT减少13184，SLR1 DSP1875→1835（−40），因此不能用DSP分布趋均衡代替逻辑/存储均衡。

这是同阶段聚合分布变化，不证明每个同一cell发生了移动，也不能分离两项RTL与SSI布局策略的因果。实际SLR1模块贡献、热点归属和连接关系仍待本轮只读查询。[对照表](slr_same_stage_comparison.md)、[来源身份与原行号](slr_same_stage_comparison.json)。

A007已从E005原闭合route日志解析10个失败节点、40条exact unique contender nets及12个附近InstTerms，完整保留原行号和文本；该top10/每节点最多5条样本不代表全部758463失败信号。A006将用精确对象查询，未命中/多driver保留，不做名字猜配。[样本目标](runs/R002/route_failure_sample_targets.json)。

R001/AT001于2026-10-16 15:51:44.063950 UTC实际启动，监督942046、leader942061，原生已加载指定xcvu9p器件并打开E005当前physopt检查点；当前恢复中，尚无新模块/热点结果。单EDA/CPU0–7/nice5/max8与资源保护保持，正常无墙钟/无输出强停。查询按模块资源、热点、失败样本、热点连接四stage分别关闭；不重跑implementation。


---
Published: 2026-10-16T15:52:56.898554+00:00
Publication: Pef24420cb5d7441cb795ff92a3ccd8ff
