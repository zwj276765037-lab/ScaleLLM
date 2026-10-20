# F4：C-M2按原生clock region分区的组合CE分发

工程建议，Root尚未选定。权威逐bit/逐FF分组是[F1_F3_C_M2_region_groups.json](F1_F3_C_M2_region_groups.json)，由现有E009 parent FF对象及原生sites表生成，完整输入hash见该表。**采用head42/tail39=81组，旧27逻辑组方案不采用。**

## 固定对象及实现

各entry分别按实际`(SLR,clock_region)`分桶，桶内按原packed bit索引递增，每256bit切一组。head23个CR→42组，tail20个CR→39组；每侧6560bit，覆盖完整、无重复、无未知桶。所有FF的D/Q位序不变，head与tail可有不同bit分组，但同bit tail→head关系不变。多字段/不连续bit的同组仅共享CE，不合并或复制数据。

每组一个显式`LUT1 #(.INIT(2'b10))`，`I0`接该entry精确原CE布尔，`O`接此组全部FF的CE。仅在81个LUT1实例设`DONT_TOUCH=yes`，CE输出网设`KEEP=yes`；不对整个parent、算术或内存DONT_TOUCH。原两个CE master的下游分别42/39个I0，不能同时保留其至payload CE的直连，也不能在D端实现一个代替CE的mux。无注册buffer、无额外clear级、无新时钟、无宽payload reset。

## 本版物理规则

1. 每个原生CR建立一个hard、非独占、非routing-contained pblock，加入该CR全部实际SLICE site；同CR内的所有M2 buffer及对应原payload FF加入**同一个**pblock，避免把每组同一片区域重复算作多份容量。其余设计可合法共享剩余资源。不固定单FF/LUT LOC或BEL。
2. 81个buffer与13120个payload FF均按权威表绑定原CR。该规则没有要求任何原FF迁出原SLR/CR；旧落点仅作为粗粒度区域身份，不加载增量DCP或保留单site。所有group在一个CR内，CE路由仍可绕行，不声称routing-contained。
3. 23个CR逐项的head/tail FF量、buffer数、原生slice数见权威表`region_costs`。这些native slice是区域资源总集合，不是空闲/兼容槽。新CE集合最多81，相对原2增加79，可能破坏与其他FF/LUT的控制集合共包装；FF不变也有打包代价。
4. G4在preplace核实际寄存器/原点、每bit所属组、FF REF与固定/macro/祖先约束、控制集合和各CR合法site交集，尚未place不要求LOC。若原FF被优化/重命名，按ORIG与bit追溯，禁止按模糊通配少取或重复取。若有不兼容硬约束不清掉它，不自动把成员移到别区。
5. place及后续每阶段核每组buffer和其全部FF同CR、同SLR，逐CE pin真实唯一driver、分组fanout≤256、master仅42/39个buffer输入。任何未分区、合并buffer、变D mux、失配、跨CR或超扇出均使结构机制未通过；不能用“网名保留”替代。若硬CR限制导致合法化/时序恶化，报告Root重新冻结，不能临时改成soft或恢复27组。

## 上游、数据和风险

原主CE仍接reset/clear/occupancy/push/pop逻辑，控制路径多一级LUT1；root至81个buffer的输入长线仍存在。原TAIL −2.977ns、12.026ns路由是有界参照，不能推算优化后WNS。独立CE分段与同CR约束是待验证机制，不是已验证收益。

原input mux仍由serial command的gate/down相位产生全部6560bit；head仍在full+pop时接tail，其他写入接input。该提案不增加这些D输入的逻辑负载/复制，不改变head/tail Q读者。保持原CR也可能限制placer优化D/Q线，且组内bit可能分散在该CR；完整route必须对D、Q、CE/clear、clock的路径/拥塞同时报告，不能只看CE fanout。

本提案不复制branch ingress两entry或parent payload，不移除branch ingress；与C-M1数据银行是不同候选。新增81LUT可优先与现有FF附近合法LUT资源共包装，但兼容性由新图/placer验证，不能以全SLR LUT利用率推断一定能装下。
