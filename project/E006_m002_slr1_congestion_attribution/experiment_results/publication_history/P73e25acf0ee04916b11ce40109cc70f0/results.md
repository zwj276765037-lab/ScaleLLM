# E006：首批原生模块归因

当前 E005 physopt 原生 query 分别闭合，完整2,204,250个primitive已互斥归属。SLR1的MLP为248355 LUT、288933 CLB Registers、361 BRAM tile；同根E003为193322/246829/102，增量+55033/+42104/+259。Attention为29578/38447/57，同根增量−31403/−5596/+28.5。两engine合计解释BRAM增加287.5（总增307.5的93.50%），但只解释LUT净增23630、寄存器净增36508；其余模块仍有+44072 LUT与+78976寄存器分布增量待拆分。

以上当前数字已由各自关闭的原生owner报告核验，非从正在写入文件估算。[第一批独立审核与行号](runs/R002/first_attention_mlp_native_review.json)、[旧全局同阶段对照](slr_same_stage_comparison.md)。MLP现仅SLR0/1，SLR2为0；Attention主要SLR2，并非两个engine的LUT/FF都向SLR1集中。native total与exclusive口径、站点非加性和阶段可比范围保持。

MLP元数据672URAM实际分布280/280/112，Attention80个全在SLR2；用途是ScaleCode/shift驻留图，不能视为完整权重cache或单独认定拥塞根因。[RTL用途与容量](runs/R002/metadata_uram_roles.md)。

失败top10节点仅1个在现有10峰窗去重并集内；该样本不能代表全部758463失败信号，热点不能当失败全覆盖。[CPU精确tile交集](runs/R002/failure_nodes_cpu_tile_intersection.json)。

其余原生模块、热点、40失败样本与热点连接仍在同一只读会话继续。用户追加授权查明后定向优化SLR1，由其他SLR分担；先完成当前归因，再据容量和连接预算执行后续优化验证，不热改当前源。


---
Published: 2026-10-16T16:12:41.592455+00:00
Publication: Pd2968abb574e4bf9a5bf9279f88a2d5d
