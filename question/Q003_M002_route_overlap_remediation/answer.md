# Q003：回答与验证

## 直接回答

重叠节点是多条不同信号竞争同一物理布线资源。消除冲突要降低局部连接需求，或让端点与线路分布到可用资源；70 万个节点不是 70 万个独立 RTL 错误，一条网可能涉及多个冲突节点。

本轮定向落区已实现，但仍有 547548 / 2031733（约 26.95%）可路由网络存在资源冲突。主控判断：下一轮优先调查并准备**现有寄存器/缓冲的分区本地化、硬块入口布局和连接/面积约简**；跨 SLR 移动与 router 策略作为有测量依据的配套变量。当前证据没有支持一个必然布通的改动。

| 优先方向 | 具体做法 | 判断依据与限制 |
| --- | --- | --- |
| MLP 宽数据分发 | 核 parent_head 每组消费者真正需要的位，将现有捕获/缓冲按分支或区域组织，源与消费寄存器就近；必要时只对远隔消费域复制同拍状态。 | 最终冲突样本 #4/#5 重复同 4 条总线位，#7 为另 4 位；不能以样本次数推断全量占比。不是简单从原 Q 再加一拍；须保持 D/CE/reset、valid、背压及事务次序。 |
| DSP / URAM 邻域 | 让操作数、地址、控制的驱动寄存器与对应硬块成组安排，降低跨区长线；保留入口布线空间。 | 样本 #1 为 MLP DSP 周边，#2 为 Attention meta URAM 地址。不能把逻辑强塞入更小 hard Pblock，局部过密会加重引脚接入冲突。 |
| 量化面积与连接 | 核两处 divider 的真实资源与扇出归属，先找精确位宽/重复计算的等价约简，再按真实输入速率考虑资源复用。 | 样本 #3/#9 参与冲突，但不证明其为最大根因。现有实现已经有流水和并行度优化，不能将泛化“加流水/减少并行”当作新方案。除法、舍入和数值规则保持；复用可能增加 mux、入口集中、II 和反压。 |
| 跨 SLR 列分布 | 明确源/负载和物理列映射后，调整跨界端点的横向分布；成组迁移时衡量减少的局部压力与新增跨界连接。 | 初始 SLL 估计在 SLR0–1 / SLR1–2 的单列峰值为 159% / 121%，说明局部压力，不能当最终分配或直接换算成坐标约束。 |
| 策略对照 | 在明确变化及相同验收下测试物理策略，观察是否真正降低最终冲突。 | 策略可能产生不同解，但当前大量冲突不足以支持原样重跑能解决。hold 修复和拥塞问题分别验证，保持原时钟与正式验收。 |

## 证据、假设与局限

本轮已审 physopt 的 occupied CLB 站点比例为 SLR0/1/2：94.95% / 99.68% / 99.92%；LUT 槽使用率为 54.79% / 71.73% / 76.31%。这表明很多站点已接入设计，同时站内仍有逻辑槽余量；实际可打包性受专用资源、控制集合、时钟及布线制约。不能把 SLR2 继续当作宽裕接收区，也不能将空余 LUT 百分比当作可自由迁入的容量。全局位置重排不全部归因于 C01。

A006 本轮有界源码核查进一步限定候选：MLP shared 入口已有非旁路双 entry、固定 head/tail；TILE_W=9 时 payload 为 6560 bit，激活分给上下两个八行分支，权重共享。第一候选应重组现有 head/tail 捕获点，保持同拍 D/CE/reset、两分支原子消费及精确更新规则，而非给旧 Q 添加一拍。Attention meta 已有占用 token 本地化，但同步 URAM 读口地址仍由上层寄存器直接送入；地址分发/深度银行需保持 pending 和响应时序。DSP 已有输入/乘积/修正输出寄存级；MLP 量化已经两 divider lane、每轮四次比较减法并迭代 11 轮，Attention 为八个 divider、每个八轮。不能重复宣称这些模块尚未流水或未做并行度优化。

最终 top10 和自适应拥塞表支持上述调查方向，不能给 547548 条失败网络做完整归因。报告中有 Attention、MLP、存储及 MIG 信号混合竞争，模块名单出现或消失不等于该模块拥塞解决。下一步最有价值的诊断是从已保存失败 DCP 得到失败网络的模块×区域归属、关键源/负载跨度和跨 SLR 列需求，限定输出范围并复用已有证据；此次尚未执行新的 DCP 查询。

证据：

- [最终路由状态](../../project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation/route_failed_status.rpt)。
- [最终冲突日志](../../project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation/vivado.log)，254583 行开始的 10 节点样本。
- [当前 physopt 分 SLR 资源](../../project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation/utilization_slr_physopt.rpt)，69/72/92/93 行的独立资源口径。
- [SLL 与约束覆盖审核](../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/route_initial_global_warnings_review.md)。
- [A007 优化优先级评判](../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/route_overlap_optimization_priorities_20261018.md)。
- [MLP shared 当前 RTL](../../project/hardware/rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s54.sv)：82、110–124、154–157、190–193、215–240 行；[调用方](../../project/hardware/rtl/mlp/hap_mlp_serial_ddr_command16_v5_s54.sv) 492 行。
- [Attention metadata 当前 RTL](../../project/hardware/rtl/attention/hap_weight_meta_resident.sv)：29、42–51、74–78 行；[调用方](../../project/hardware/rtl/attention/hap_attention_board_cohort16_core.sv) 270–282 行。
- [MLP DSP 当前 RTL](../../project/hardware/rtl/mlp/hap_a8w4_pack2_dsp.sv)：30、46–52 行；[MLP quantizer](../../project/hardware/rtl/mlp/hap_mlp_robust_a8_quantizer_s35.sv) 395、459–480 行；[Attention quantizer](../../project/hardware/rtl/attention/hap_robust_a8_quantizer.sv) 370 行。

## 工程影响与验证

原 E008 合同仅改变 C01 的位置要求，没有减少 RTL 连接需求。涉及寄存器分区、算子结构或流水延迟的后继工作须写清新的受影响范围，保留 Hadamard、ScaleCode、format05、ABI、双 DDR、时钟及 80 个保护边界，不以改变金标准或放宽约束取得通过。

后继验证顺序为：失败归因并选择最小候选 → 独立数值/协议与吞吐验证 → 需要时新综合 → 检查实际局部连接与资源/SLL列分布 → 完整 route。最终要求无未布通/冲突网络，且 setup/hold/PW、DRC、CDC/reset/IO 与 bus-skew 精确覆盖分别满足原验收。每个候选收益均以新实测判断，节点数下降不能替代合法布通。

本问题的解释已完成；工程缺陷未解决，拟议优化尚未实施或验证。
