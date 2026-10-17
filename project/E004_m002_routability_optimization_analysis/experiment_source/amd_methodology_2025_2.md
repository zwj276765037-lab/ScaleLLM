# 本轮采用的 AMD 方法依据

主控于2026-10-16查阅AMD官方UG949 **2025.2**，与本工程Vivado版本一致。以下是方法适用边界，不是本设计已取得的优化效果。实际命令支持和物理数据由R001保存；RTL事实由R002/R003保存。

| 官方来源 | 方法要点 | 对本设计的约束 |
| --- | --- | --- |
| [Use Alternate Placer and Router Directives](https://docs.amd.com/r/2025.2-English/ug949-vivado-design-methodology/Use-Alternate-Placer-and-Router-Directives) | 布局通常比路由策略更影响拥塞；SpreadLogic用于分散逻辑，SSI_BalanceSLLs/SSI_SpreadSLLs分别针对跨SLR分配和高连接区域；使用同阶段拥塞报告比较 | 不把同一失败布局再交router当作首选。候选directive须由安装版本核实；一次改变一个有明确物理机制的策略，避免无界扫参。文档对AlternateCLBRouting注明UltraScale适用，目标xcvu9p为UltraScale+，实际适用性不能仅凭名字推断 |
| [Limit High Fanout Nets in Congested Areas](https://docs.amd.com/r/2025.2-English/ug949-vivado-design-methodology/Limit-High-Fanout-Nets-in-Congested-Areas) | 拥塞区的高扇出及紧时序可能导致聚集和资源竞争；驱动复制/全局资源须结合实际负载分布 | 优先分析MLP已知跨SLR大扇出控制的端点位置。BUFG曾全部跳过，不能视作自动兜底；全局MAX_FANOUT或强插BUFG不列默认修改 |
| [Follow Control Set Guidelines](https://docs.amd.com/r/2025.2-English/ug949-vivado-design-methodology/Follow-Control-Set-Guidelines) | 典型容量按CLB寄存器数/8计算；7.5%到15%为建议减少，超过15%为要求减少；局部集合密度仍需布局分析 | 当前22410/(2364480/8)=7.58%，刚进入建议区。不能凭此或99.11%CLB站点占位断言全局control-set碎片主导失败。详细报告的slice loads有重叠，不能相加冒充独占站点 |
| [SLR Crossing for Wide Buses](https://docs.amd.com/r/2025.2-English/ug949-vivado-design-methodology/SLR-Crossing-for-Wide-Buses) | 跨SLR宽总线流水可减轻长线压力；至少三级的具体建议针对超过250MHz宽总线 | 本core100MHz，不能机械要求三级；先确认真实跨界连接，再评估流水位置、有效位/ready同步、周期变化及吞吐。不因增加寄存器便假定布线改善 |
| [Disable LUT Combining](https://docs.amd.com/r/2025.2-English/ug949-vivado-design-methodology/Disable-LUT-Combining) | LUT组合会增大slice输入输出连接；若拥塞区组合比例超过40%，可尝试限制组合 | 需要目标区域真实比例支持。当前站点占位高，全局关闭可能消耗更多位置；只列有证据后的小范围备选，不能先全局关闭再声称提高可布性 |

官方指导没有给出本设计布通概率，也没有保证任何directive成功。最终仍需同源功能验证、真实网表/布局测量和合法route终态；pre-route timing、局部拥塞估计与最终布线结果分别解释。

补充：A007实际核对[UG904 2025.2 Available Directives](https://docs.amd.com/r/2025.2-English/ug904-vivado-implementation/Available-Directives)与[Implementation Strategy Descriptions](https://docs.amd.com/r/2025.2-English/ug904-vivado-implementation/Implementation-Strategy-Descriptions)，形成SSI_SpreadSLLs首选、SSI_SpreadLogic_high条件后备的工程判断。准确作用范围、选择理由和启动前安装版本核验义务见[R003 §11](../experiment_results/runs/R003/architecture_plan.md)。官方策略描述不等于本轮已运行策略，也不把整个implementation strategy的组合参数套入只改变place directive的方案。
