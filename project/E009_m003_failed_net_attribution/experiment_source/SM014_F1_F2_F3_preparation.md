# SM014 F1–F3准备草稿：未选型、未改生产

本文件只复用已核RTL与合同，不扩展SM013查询。Root的candidate_decision_register.md为选择入口，G1/G2未完成前不实施。

| F1字段（生产TILE_W=9） | 当前捕获和读者 | 全双银行估算 |
|---|---|---|
| activation4608/acode128/ashift96 | parent head/tail，branch0读下8行、branch1读上8行 | 每支2304/64/48，无字段额外复制 |
| weight1536/wcode96/wshift72/mask12 | 两branch ingress都读同一parent Q | 每支1716，新增副本须由实际远隔读者与D端代价支持 |
| down/first/last/tile=12 | 两branch的队列与tag协议 | 每支12，不能改变原子接受 |

现parent head/tail为6560×2=13120bit；全双银行4144×2支×2entry=16576bit，增3456FF。可只选必要字段复制；拆变量名没有连线/位置收益。下游两支各两entry ingress保存不同在途事务，不能删除。所用RTL：hap_mlp_shared_dual_slice16x12_s44_s54.sv 88–124、143–212、215–240、333–352、561–577。实际D端上游在hap_mlp_serial_ddr_command16_v5_s54.sv 492–517；仅把Q靠近支路可能将长线转至该选择器/D端。

F2 parent须逐周期保持：count0/1/2；in_ready只看未满；满时即使同沿pop仍不接受上游；empty push入head、非empty push入tail、full pop搬tail、占用1push+pop替换head；payload无宽reset；reset/clear仅清count。parent clear与branch延后一拍clear需按现实现验证，不能统一成新优先级。

F2 meta：原地址既作URAM request地址，也作返回tile/group。异步reset与system_clear清零、case内ST_LAUNCH&&weight_command_ready赋零、always末尾meta_rsp_fire赋旧地址+1；若launch与rsp_fire同沿发生，后者NBA优先，须保顺序或证明不可达。每个本地副本用相同事件/优先级更新自身next状态，所有有效采样沿等于原地址；不能local<=original多一拍。保留FSM、单pending/token、response推进、stall持有、计数/格式。含abort的datapath_clear不等于原地址清零集合。

F3 meta深度银行仅待评估：10×8192×256可保持容量，需登记新增选择寄存器及256bit返回mux、低13位分发、80URAM实际映射与路径代价；不加返回寄存级。全图SLR0/1/2 occupiedCLB约94.95/99.68/99.92%，不能把SLR2当空区，也不能用occupiedCLB断言LUT/FF槽全满。最终FF/LUT/mux/控制/时钟负载及兼容打包、物理位置须新图验证。

DSP/除法器保持原结构，E005 input48/CE32保留，不重复作为新改造；条件候选仅有全量归因和精确吞吐/位等价证据才纳入。无降频/放宽约束、无新implementation。
