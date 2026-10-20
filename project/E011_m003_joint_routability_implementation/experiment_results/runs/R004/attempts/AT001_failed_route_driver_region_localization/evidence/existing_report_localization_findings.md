# AT006现成报告定位结论

直接失败：原生route在Phase9验证结束给Route35-2，797175重叠节点；最终report_route_status为615840资源冲突网。原native1/nullstop及失败DCP保持，AT006源/50身份/锁已闭合。

以下是最终路由验证的top10争用样本，不是全部网/模块贡献排名：

|位置（原生tile/node）|已知具体信号或路径|原vivado.log行|
|---|---|---|
|INT_X57Y687 / BOUNCE_E_15_FT0|projection_repack/projection_s24x16x16[4804,4772,4828,4940]；邻接CLEL_R_X57Y688处SwiGLU branch[1]/up_tile_r_reg[1732,1700,1756,1868]/D|985–999|
|INT_X20Y366、X39Y368、X31Y342 / SS12长线|shared_compute/parent_head_r 各4个实际争用bit|1001–1007、1017–1023、1033–1039|
|INT_X68Y433、X66Y355 / SS12长线|tensor/output_mux_group_data_r与paired_weight/u_local0/mlp_rdata[184,391,437]共享长线资源|1009–1015、1025–1031|
|INT_X79Y390、X79Y420、X79Y461、X79Y378|d0_smc/s00_entry_pipeline/s00_mmu/inst/r_sreg/m_vector_i_reg[1314]_0多个bit；长线、quad及local节点均有争用|1041–1071|

初始区域线索与最终样本分开：route_failed_congestion.rpt第19节为Placer Final、第49行起为Router Initial，所列邻域模块百分比是该时刻区域组成，不能当最终615840网的模块份额。两个边界SLL总估计利用62.30%/63.17%（log698–706），局部列分别最高112%/124%，说明局部跨区供需失衡，不是整条边界总量耗尽。

对“共享SLR1”假设：支持的是两侧各有局部SLL过载、最终多个局部长线/近端节点争用并存；现成报告不能证明冲突主因就是0↔2穿越，也不能证明主要是纯本地拥塞。两个边界各自的SLL资源独立；0→2路径最低需要跨两界，source1分别到0/2则是两支路。全量actual driver端点分类、实际tile→SLR/clockregion及少量真实route资源待R004，只用新图事实定量，不从X/Y或样本占比推导。
