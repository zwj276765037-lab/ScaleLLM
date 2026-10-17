# E006：已确认资源分布向SLR1集中，模块归属待原生提取

CPU读取E003/E005各自原生physopt报告，版本/器件与阶段一致。旧→新，SLR1 LUT268405→336107（+67702）、CLB Registers319883→435367（+115484）、BRAM tile160.5→468（+307.5）；两侧这三类资源均减少。全局LUT减少13184，SLR1 DSP1875→1835（−40），因此不能用DSP分布趋均衡代替逻辑/存储均衡。

这是同阶段聚合分布变化，不证明每个同一cell发生了移动，也不能分离两项RTL与SSI布局策略的因果。实际SLR1模块贡献、热点归属和连接关系仍待本轮只读查询。[对照表](slr_same_stage_comparison.md)、[来源身份与原行号](slr_same_stage_comparison.json)。

A007已从E005原闭合route日志解析10个失败节点、40条exact unique contender nets及12个附近InstTerms，完整保留原行号和文本；该top10/每节点最多5条样本不代表全部758463失败信号。A006将用精确对象查询，未命中/多driver保留，不做名字猜配。[样本目标](runs/R002/route_failure_sample_targets.json)。

当前A006准备一次打开原physopt检查点的只读会话，先完成完整互斥模块归属×SLR和热点资源，再继续热点并集相关连接及失败样本。尚无新Vivado启动或测量完成结论，未运行新implementation。


---
Published: 2026-10-16T15:44:48.033597+00:00
Publication: P871ba58a1e684339b258eb5aec89f1aa
