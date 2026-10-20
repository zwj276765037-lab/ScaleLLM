# F3：数据、D/Q、选择和控制总成本

2026-10-18，A006工程设计预算，未实施/未综合。Root尚未选型；资源预测与实测分开。对应[F2方程](F2_state_sampling_and_assertions.md)、[M2真实分组](F1_F3_C_M2_region_groups.json)、[A3资源池](F4_C_A3_two_slice_resource_rules.md)。

| 项 | 原实现 | 推荐新实现 | 代价与验收预算 |
| --- | --- | --- | --- |
| Parent存储 | H6560+T6560=13120 FF；两entry，固定head | 同13120bit/FF，原field/位序 | **+0FF**、+0payload clock/reset负载；不共享/删除branch ingress |
| Parent CE | 2个LUT6 master，各6560个CE pin | master→42/39 LUT1；81局部CE各1..256 FF | **+81显式LUT1**；unique CE/control sets最多2→81（+79），多1级LUT延迟；不能把FF数量不变当无打包代价 |
| Parent D选择 | serial gate/down 6560bit输入选择；H在full+pop读T，否则读X | 布尔/位序/reader不变；仅按bit组写入 | +0宽mux；每bit T.Q→同bit H.D helper不变。固定CR限制placer优化D/Q，仍需新图和route实核 |
| Parent CE上游 | rst/clear、I/P/E/F逻辑，master driver在SLR2 | 同布尔；两个master下游6560→42/39 | 广播仍跨原S1/S2 CR，81条I0连线存在；输入总长线/一级缓冲延迟可能抵消减负；不声称清空链已收敛 |
| 元数据容量 | 81920×256=20971520bit，实测80URAM | 2×(81920×128)，各40URAM | **总80URAM硬预算**；理论20×(ceil128/72+ceil128/72)=80仅算术，新图必须40+40 |
| 元地址状态 | core17FF，251 Q读者=204URAM pin+47logic | core17保留；resident两helper各17FF，Q真实连接自己的片 | **+34FF、+34 CLK pin、+34 async reset CLR pin**，2个独立17bit增量锥；禁止core Q再打一拍 |
| 元地址D/CE | 原core increment/zero/hold，物理D/CE固定导出缺失 | helper own-Q反馈增量；CE=S|L|R；D=(R&&!S)?own+1:0 | 每helper一个17bit加1、17bit零选择、1个LUT3 CE及1个LUT2 INC；**4个受保护控制LUT**；两新局部CE各17 FF，新control set最多2 |
| 元地址广播 | core A同时读memory、tile/group/logic | S/L传入resident；R复用本地rsp_fire；原A仍读标签/范围 | S新增4个控制LUT输入、R新增4个、L新增2个；实际原生pin扇出G4核。原204个URAM读地址pin改从独立片Q来；自身D反馈保留，原47logic不假定全部消失 |
| 写地址/数据/使能 | 一个17bit wr_addr、256bit data、公共wr_fire | 相同wr_addr广播两片，data切半，共同wr_fire | **+0写地址FF、+0写数据复制、+0写控制器**；原生写ADDR/WE/EN fanout在固定导出不全，G4报告，不把HDL拆片当0物理控制代价 |
| 读token/valid/响应 | 一个token、一个valid、256bit响应逻辑及单计数器组 | 全部各1份、rsp分两半同沿写并拼接 | **+0token/valid/count FF、+0响应逻辑位、+0深度bank返回mux、+0输出级**；URAM输出寄存器/FF吸收方式新图核 |
| A3时钟/清空 | core_clk/core_rst_n、resident原datapath_clear | 时钟不变；helper async reset=core_rst_n，sync S/L/R事件 | 新CLK/CLR负载各34；datapath_clear不接helper reset，公共resident clear语义不变；全设计80边界/E005 input48/outputCE32不变 |

### A3具体资源上限

新增架构状态精确34FF；两17bitincrement若普通CARRY8推断，参考6 CARRY8、34增量LUT，加17位/片零选择参考34 LUT，另4显式控制LUT，合计参考72 LUT。实际工具可合并合法数据逻辑，**G4预算A3新增LUT≤96、CARRY8≤8、FF增量≤34、URAM=80且每片40**；其中FF还须精确识别34新增地址FF，不允许额外可观察pipeline。若响应映射导致额外FF、增量锥跨片共享或超预算，先报告Root核因/重新冻结，不自行放宽预算。

联合推荐M2+A3：新增FF34，显式保留LUT85（M2=81+A3本地控制=4），其余A3数据逻辑包含在96LUT上限内，故**总新增LUT≤177、CARRY8≤8，额外URAM/BRAM/DSP=0**。C01保留不新增实体，overlay本身不计逻辑收益。M2新CE最多81、A3两新counter CE最多2，相对原parent两CE的已知新增控制集合上限合计+81；全局实际control set去重按工具报告，不把这个局部上限当全局实际值。

新图须按模块锥和全局两口径与同平台基线对比LUT/FF/CARRY/BRAM/DSP/URAM、control sets、LOC/宏、时钟及reset/clear fanout；新增逻辑的名义slice需求不等于可兼容空槽。M2有23CR固定粗区域，A3两个地址CLB池X4Y5/6与X4Y8/9，不相交；仍会与其他设计成员共享区域资源，preplace合法资源检查和place打包不能省。

### 延迟、II和未选比较

M2没有寄存级/容量/ready变化，parent原吞吐和因full延迟的credit恢复保持；每个branch ingress及gate/down结果队列原样。A3一份token控制、同沿两片读/写，最早t沿接读、t+1沿消费响应、t+2沿再接读，**最小请求间隔2个clock周期**，上层其他限制可能更长；标签仍用core A，不靠bank mux或额外输出拍改善时序。

完整C-M1双银行参考总payload16576，相对13120 **+3456FF/CLK**；每entry CE负载6560→8288（+1728/entry），输入共享1728bit重复两branch且tail→head复制，全输入选择/D负载也增加。私有2416bit/branch本来各一reader，head-only搬移存在把Q跨区转为D跨区风险；本轮deferred，不与M2混算收益。C-A1单份counter仅+17FF但仍12原直接根；C-A2深度银行有bank选择和256bit返回汇聚成本；本轮推荐deferred，不把它们作为A3的隐含附加项。算术C-R1无具体已测机制，deferred。
