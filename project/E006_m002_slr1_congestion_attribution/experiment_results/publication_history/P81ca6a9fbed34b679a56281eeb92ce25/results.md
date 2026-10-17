# E006：首批原生模块归因

当前 E005 physopt 原生 query 分别闭合，完整2,204,250个primitive已互斥归属。SLR1的MLP为248355 LUT、288933 CLB Registers、361 BRAM tile；同根E003为193322/246829/102，增量+55033/+42104/+259。Attention为29578/38447/57，同根增量−31403/−5596/+28.5。两engine合计解释BRAM增加287.5（总增307.5的93.50%），但只解释LUT净增23630、寄存器净增36508；其余模块仍有+44072 LUT与+78976寄存器分布增量待拆分。

以上当前数字已由各自关闭的原生owner报告核验，非从正在写入文件估算。[第一批独立审核与行号](runs/R002/first_attention_mlp_native_review.json)、[旧全局同阶段对照](slr_same_stage_comparison.md)。MLP现仅SLR0/1，SLR2为0；Attention主要SLR2，并非两个engine的LUT/FF都向SLR1集中。native total与exclusive口径、站点非加性和阶段可比范围保持。

MLP元数据672URAM实际分布280/280/112，Attention80个全在SLR2；用途是ScaleCode/shift驻留图，不能视为完整权重cache或单独认定拥塞根因。[RTL用途与容量](runs/R002/metadata_uram_roles.md)。

失败top10节点仅1个在现有10峰窗去重并集内；该样本不能代表全部758463失败信号，热点不能当失败全覆盖。[CPU精确tile交集](runs/R002/failure_nodes_cpu_tile_intersection.json)。

其余原生模块、热点、40失败样本与热点连接仍在同一只读会话继续。用户追加授权查明后定向优化SLR1，由其他SLR分担；先完成当前归因，再据容量和连接预算执行后续优化验证，不热改当前源。

## 外围与接收边界

已关闭完整primitive表按实际SLICE站点筛选，SLR1除Attention/MLP外107987个CLB FF；主要为XDMA25894、d1_smc16458、d0_smc16457、u_tensor16455、host_split14841等。d0/d1 MIG本体在SLR1均无CLB FF，不能将互联/适配压力误说成MIG本体争抢。两路SMC+u_tensor+host_split合计64211，而E003扣除两engine与XDMA后的全部SLR1寄存器仅19241，因此这四类合计增加至少44970（非各自delta、非相同cell迁移）；旧同细子模块分布缺失，不补造精确变化。[CPU拆分](runs/R002/peripheral_slr1_primitive_review.json)。

DDR slice非SLICE FF已由实际SITE_TYPE确认全部为LAGUNA：d0在SLR1/2各1211，d1在SLR1/0各1098。后续放置需保持跨区接口关系，不能当普通CLB逻辑任意迁移。[位置类型核验](runs/R002/ddr_non_slice_ff_site_types.json)。

完整归属清单已核NAME唯一、前缀owner和全计数一致；SLR1有23285个SLICE站点由多个owner共享，owner站点数不可相加。[独立清单核验](runs/R002/closed_primitive_ownership_review.json)。

## 后继候选与诊断进度

[SLR2输入局部性候选](runs/R002/input_frontend_locality_candidate.md)已完成CPU事实与内部规划审核：tensor输入bank + frontend capture/Hadamard/四量化器，40627 CLB FF、31709 raw LUT、8DSP、无BRAM/URAM；不移cache/bundle/compute/DMA。77,360 primitive中114常量未放置，实际候选组均在SLR1；该组触及13230 SLICE仅976独占。当前仍未实施，热点/端点适用性待补。[后继合同草案](../../../mission/M002_ddr_separation_and_timing_recovery/slr2_input_locality_candidate_contract_2026-10-17.md)仅planned。

原native core_other以32829个离散leaf调用report_utilization，显著慢于前4个exact hierarchy调用，仍CPU活跃、无终态；后续11窗同机制可能昂贵。正在独立目录准备轻量替代，先补失败/热点/连接，原生只exact hierarchy，未取得热点native LUT明示NOT_QUERIED。原用户正常进程不强停边界保持：未得到明确切换授权前，不中断当前、不另开EDA。替代入口尚未运行。


---
Published: 2026-10-16T16:56:13.808517+00:00
Publication: P5fa515a56d8a4f939fd86ae42a8ca01e
