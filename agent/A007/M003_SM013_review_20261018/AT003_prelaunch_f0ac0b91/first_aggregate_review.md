# AT003 初次分类小表独立审核

execution：已关闭首轮小表的有界审核完成；固定 deep/时序仍运行。verdict：分组表算术及选择表计数接受，原始端点重建、计数解释和 G1 待完成。applicability：6 份 `evidence/first_aggregate` 固定快照，实际身份见[机器记录](first_aggregate_review.json)。review：初步阶段审核，没有选入候选。

848 个唯一主组、顺序/并列字典序、连续 rank 与总和 **569,597** 已独立核对；前20组 **436,749**。补充冲突网6761、合并union443368/569597＝77.8389%仍待终态ID级复算。这是整组分类覆盖。

从全部主组小表重算，**535,331** 个网的驱动与全部可见负载同在一个已知SLR；已知源且非本地负载集合12,194，源SLR未知22,051，已知源而负载SLR未知21。前三为branch1/SLR2 151,527、Attention array/SLR1 84,058、branch0/SLR0 55,822。不能把多数冲突直接归为跨SLR线，也不能从端点同SLR推定实际route范围、唯一根因或某RTL改造必有效。

`deep_selected.tsv` 实际 **20,534** 个唯一网；每TOP组16个代表，另含全部固定补充、以及非冲突补充网。实际字典序代表与原始inventory标签成员关系等待完整raw audit。不能把77.8389%写成全部已深查。80保护表实际48/16/16个唯一cell、DONT_TOUCH均1；功能/物理保护全项验收仍分开。

CONSTANT 22,050 由归档aggregate按driver REF_NAME=GND/VCC定义，与canonical/report差22,049接近但不相同；不能删constant或用数量接近宣称解释。source SLR未知也不同于driver未知。head13,509/tail6,561/meta35均是固定网名模式的网计数，不是payload位宽或所需副本数。

终态后集中核完整raw映射、type与位置交叉类别、固定deep选择和实际属性/时序，再判断候选关键证据与G1。无新原生查询或大表重复扫描。
