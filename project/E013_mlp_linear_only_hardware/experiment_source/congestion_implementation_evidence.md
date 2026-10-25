# 当前拥塞的工程证据与待证范围

本说明对应R004/AT001_impl的冻结网表、原生运行日志与AT004正式综合hier报告。证据哈希和实际日志行见attempt内`congestion_implementation_observation.json`。当前仅为归因候选，未做第二次EDA，未改运行中的104输入。

当前route Phase5.2的两个中间重叠节点数为1729692、921600，表明本轮正在减少冲突；不是冲突net数、最终route结果，也不是可与旧最终失败数直接相减的同阶段数据。Route35-447/448/581及level7真实方向窗口仍保留。

## 已有直接证据

| 对象 | 实际证据 | 物理含义与边界 |
|---|---|---|
| shared两分支和GU请求控制 | 当轮Physopt32-1132记录request_wr_ptr/gather、ingress_wr_ptr/down/weights网扇出1968–2076；受timing/macro限制，参与该优化的loads只124–136 | 宽FIFO的控制广播确实存在；124–136不是整网优化后的最终扇出，尚未证明这些网主导全局拥塞 |
| 保留共享计算阵列 | 正式综合u_mlp424521 LUT/509711FF；两branch各188937 LUT/233096FF/1536DSP，合计占MLP约89% LUT | Host移走非线性后，主体线性阵列及其内部连接仍保留；资源比例不等于拥塞比例 |
| 输入/FIFO/结果宽链 | 外部activation4096bit U8+384bit meta；每branch内部activation2304bit S9与weights1536bit共指针写入；GU输出6144bit、Down重排输出8192bit | 静态宽连接与选择/使能网络不会因运行时只执行一个job而消失；未测其实际跨SLR分布 |
| 重排模块 | GU/Down projection repack分别9370/8290 LUT，保留输出历史/重排边界 | SwiGLU宽链删除不等于所有宽重排链删除；需终态后的实际SLR/跨界报告 |
| 驻留metadata空间 | u_meta_bank672 URAM，Attention80，全板752 | metadata占用大量固定位置硬存储列；可能约束相邻逻辑布局，但尚无该DCP逐SLR归属，不先判某SLR装满 |
| DDR和跨SLR基础设施 | Place30-1229命中d0_mig_slice triple_slr的USER_SLL_REG建议；Physopt32-1483在DDR0 wready→MIG slice网报告约束/宏阻止重写 | 固定DDR端点与跨SLR基础路径仍有实际代价；不是当前原生ERROR，也不据此认定唯一根因 |

## “调度问题”的判断边界

任务级GU/Down互斥、cache/metadata/compute/DMA握手和故障恢复已有真实功能证据，但功能正确只证明数据和协议。物理实现仍实例化全部分支、FIFO与连线；改变job的先后顺序不能自动减少这些占用和布线。

调度器的硬件组织则确有物理候选：GU request FIFO和shared ingress FIFO采用宽payload与共同写指针/使能，当轮原生日志已标出这些控制网的高扇出。此项需要与实际SLR归属、拥塞区域和跨界网关联后，才判断是否应做局部控制复制、存储/数据分片或流水边界调整；当前未选改造，也未把FSM功能PASS当作物理结构合理的证明。

最终将分别回答局部压力是否下降、是否足够合法布通。按既定SLR计划，优先采保留shared/metadata的逐SLR资源和实际SLICE、代表新旧热点窗、最多400条跨界路径；父route日志与实际保存DCP阶段严格区分。当前冻结运行继续，不因这些候选先热改约束或重启。
