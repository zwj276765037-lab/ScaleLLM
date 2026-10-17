# 2026-10-17 热点与候选优先级更新

E006/R003实际10峰窗UNION共103313条primitive记录，其中MLP79277（76.735%）。原输入前端迁移组在UNION中只有1042条（约1.01%），40失败样本网只命中其中3条组内CE网，合计23/657样本热点负载。主控据此把该组降为探索对照，暂不作为下一完整implementation默认首选。其源码准备仍可复用，但没有实际迁移/布线结果。

更直接的候选为SwiGLU独立8-row分支和Down权重重排，R004已于北京时间07:57实际启动，在同一原physopt图比较两者的实际资源、完整边界和控制关系，不能只看热点数量就搬移。R003连接导出发生单元属性批量对齐失败；具体属性及空值行为尚待原生probe定位。已保留自然失败终态及正确闭合的数据；该错误按工程范围修复，不反驳物理方案。[当前事实与原始证据](../../project/E006_m002_slr1_congestion_attribution/experiment_results/summary.md)。

SLR2现有原生资源余量为180399 LUT、531004 CLB FF、398.5 BRAM36等效、128 URAM和525 DSP；未占用CLB站点3412个，站点已占93.07%。SLR1↔2当前使用8509/17280 SLL。它具备分担资源的空间，但打包、局部布线与新增跨区连接仍须实际实现验证；源码位宽或cut端点数不能直接抵扣SLL容量。[SLR用量](../../project/hardware/vivado/reports/m002_E005_R004_AT003_current_CDC_bound_OPT_place_physopt/utilization_slr_physopt.rpt)、[器件总容量](../../project/hardware/vivado/reports/m002_E005_R004_AT003_current_CDC_bound_OPT_place_physopt/utilization_physopt.rpt)。

以下按阶段保留此前候选与概念说明；涉及“首选”的旧判断已由上述实测更新。

---

# 2026-10-17 实测更新（归因进行中）

已从E005当前physopt取得实际模块表：SLR1 MLP为248355 LUT、288933 CLB寄存器、361 BRAM tile，同根旧图分别增加55033、42104、259；Attention的SLR1 LUT/寄存器反而减少31403/5596，BRAM增加28.5。两引擎之外还有107987个CLB寄存器集中在SLR1，主要是XDMA、双DDR SmartConnect、tensor与host_split等适配结构；MIG控制器本体的SLR1寄存器为0。DDR独占访存并未约束这些片上单元的位置。见[E006当前实测与来源](../../project/E006_m002_slr1_congestion_attribution/experiment_results/summary.md)。

其他SLR可以分担，但须连同紧密相关的数据/控制一起调整。当前[首选候选](../../project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R002/input_frontend_locality_candidate.md)将tensor输入bank与MLP capture/Hadamard/四量化器作为一组移向SLR2，缓存与主计算保留；约40627 CLB FF/31709 raw LUT/8DSP，尚未实施或证明收益。用户已授权归因清楚后定向优化和完整implementation，E007入口CPU准备及独立源码审核完成；实际布局布线尚未启动。

SLR2相对适合接收这一组：现有空CLB站点3412个，SLR0只有491个；剩余DSP为525个与419个，本组选用8个。SLR2现有站点占用仍为93.07%，因此只能把这些数作为容量依据，不能保证打包或布线成功。本组选中单元与组外逻辑共享12254个SLICE，只有976个站点为本组独占，不能把触及的13230个站点全部算成迁移后释放面积。

成组选择有明确的数据边界：把12288-bit输入的生产与接收放在同组，保留bundle/cache到主计算的宽接口，源码载荷边界主要为256-bit读入与四量化器合计1120-bit输出。实际跨区net、控制往返、时序和SLL使用必须从新图完整cut测量，不能用这些源码位宽替代。

用户已明确允许切换这一次只读慢统计；原进程真实收尾及文件完整性经独立复核，轻量E006/R003于北京时间2026-10-17 07:17启动。已核原core_other调用为32829个leaf各生成一张资源表，用时13980秒；这些表不能作为一个原生模块汇总使用。新入口避开该调用，优先补失败样本、实际热点与连接。现有有效模块表保留，热点/端点及全局失败关联仍在核查，合法布通尚未解决。[实际切换与范围审核](../../project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R003/independent_switch_and_lean_review.md)。

以下保留E006启动前的概念解释和查询方法，涉及“尚未取得模块表”的表述是当时证据状态，以本次更新及E006摘要为当前状态。

---

# 回答：DDR专属访问不自动形成SLR物理隔离

DDR0向Attention、DDR1向MLP提供专属的权重与数据通道；计算、buffer、重排、控制和片上连线仍位于同一FPGA的三个SLR中。DDR划分改变访存归属和通路，既不增加DSP/LUT/布线容量，也不自动指定引擎的放置范围。[接口约定](../../project/hardware/source/m002_dedicated_ddr.md)

当前M002自有约束没有给Attention/MLP加入各占一SLR的区域限制；旧mission0004/0005分区约束被构建入口明确排除，IP引脚/时钟约束仍有效。SSI_SpreadSLLs是布局搜索策略，不是引擎独占区域合同。[约束策略](../../project/hardware/vivado/constraints/ddr_timing_recovery.xdc)、[物理入口](../../project/hardware/vivado/scripts/m002_physical.tcl)。

## 当前设计必须跨SLR

E005各自physopt的层次资源报告中，Attention为227958 LUT / 2296 DSP，MLP为481854 LUT / 3149 DSP。单SLR DSP容量2280，因此二者各自均无法全部装入一个SLR；两个引擎的资源需求也不均等。三个SLR承载两个各需至少两个SLR的引擎，至少一个SLR必须共享资源，但这一容量论证本身不能确定共享必然发生在SLR1，也不能说明具体哪一模块导致失败。

单SLR DSP容量来自同一器件原生Used/Util%容量反演，并与总6840 DSP核对；复用容量是合法的，旧引擎分布不当作E005当前分布。[当前层次报告第83/92行](../../project/hardware/vivado/reports/m002_E005_R006_AT002_closed_place_physopt_readonly/physopt/utilization_hierarchy_depth7.rpt)、[器件容量推导](../../project/E004_m002_routability_optimization_analysis/experiment_results/runs/R003/target_physical_evidence.json)。

## 当前实测分布

| 原生physopt指标 | SLR0 | SLR1 | SLR2 |
| --- | ---: | ---: | ---: |
| CLB站点占用 | 99.00% | 99.85% | 93.07% |
| LUT使用率 | 63.94% | 85.29% | 54.22% |
| CLB Registers使用率 | 41.18% | 55.24% | 32.63% |
| Block RAM Tile使用率 | 21.04% | 65.00% | 44.65% |
| URAM使用率 | 87.50% | 87.50% | 60.00% |
| DSP使用率 | 81.62% | 80.48% | 76.97% |

[当前原生SLR报告](../../project/hardware/vivado/reports/m002_E005_R004_AT003_current_CDC_bound_OPT_place_physopt/utilization_slr_physopt.rpt)。SLR1实际承载最多LUT、寄存器和BRAM；99.85%是站点已有占用，不是LUT槽位全部满，且不能由剩余LUT比例直接推算可用布线空间。控制集合兼容性、专用资源列、时序与连线关系会约束可打包和可移动性，但本轮尚未分离其各自因果贡献。

同报告SLR0↔1使用10474 SLL，SLR1↔2使用8509 SLL。SLR1同时面对两侧跨界连接；总量尚未达到全边界容量，并不排除列级和局部通道拥塞，也不能仅凭这两项数字判定中间SLR失败的唯一原因。

补采的新峰12行对应10个区域均位于SLR1，区域两两重叠、SLICE站点均有primitive占用。Gate的1917个源相对跨SLR叶负载是引擎内部控制连接，DDR分离不会自动消除它。当前没有E005完整的模块×SLR资源和热点连接归属分解，因此不能给出“MLP/Attention/PCIe各占SLR1多少”或把旧E003层次分布直接套用。[最终独立审核](../../project/E005_m002_optimized_implementation/experiment_results/runs/R005/final_internal_review.md)。

## 工程含义

DDR分离的访存设计与片上拥塞是两个同时需要满足的要求。接下来若做物理归因，应使用当前DCP的模块×SLR资源、热点中的模块贡献、主要宽连接及跨SLR控制关系，确定一个有容量余量和接口预算的放置/结构候选；不能直接硬性把每个完整引擎压入一个SLR。这里只说明后续所需证据，未运行新EDA、改约束或改变算法。

## 追问：这些怎么查

用户追问：“这些怎么查”。本次仅检查已有报告和已验证查询脚本，没有打开新的Vivado会话或修改生产工程。

1. **模块×SLR资源表。** 打开E005 R004/AT003的原physopt.dcp；对Attention、MLP、权重缓存/前端、DDR0/1、PCIe及其余互联分别执行原生`report_utilization -cells [get_cells <精确实例路径>] -slr`，逐级展开SLR1贡献最大的子模块。该组合接口已经在E004同版Vivado实际成功，但E005尚缺完整这张交叉表。匹配必须唯一、空匹配报错；父子层次不相加，不同模块可能共享CLB站点，站点数也不能直接求和。
2. **热点内模块占用表。** 复用已测的NW001–NW010实际tile名单，按tile→site→primitive查对象，再按完整层次路径分组，输出各区域及去重并集的模块资源构成。10区全部重叠，分别统计与并集统计分开；LUT/BRAM/DSP资源单位沿用原生口径，DSP拆分primitive不能按行数当DSP个数。该步骤补的是当前空间对象的层次归属，无需重测拥塞等级。
3. **模块间与跨SLR连接表。** 对上述主要模块和热点相关net合并hierarchical segments、去重到完整net，取真正driver及leaf load pins的LOC/site/SLR；统计源模块→目的模块、源SLR→目的SLR、数据/CE/reset等类别、跨区叶端数及源到负载的空间范围。多driver/未放置/未知类别单列，不猜值。net数、leaf pin数、SLL数和实际路由资源分开，不能把附着segment数当成跨窗net或流量。
4. **与真实失败位置交叉验证。** 先复用失败route日志已有冲突节点及信号样本，将其net归属与上述热点/模块对应；日志只有top10节点、每节点最多5条信号，明确样本范围。若后续需要更广的实际冲突归属，再在独立只读会话打开route_failed.dcp，验证安装版实际支持的枚举接口与覆盖范围；不预先承诺能完整提取所有冲突，也不把拥塞热点直接当作全局失败分布。

优先完成前两张表，确定SLR1空间内的主要贡献者，再用第三张表解释连接压力、第四项核对其是否与失败一致。这些观察能缩小原因范围；确认某项改动的因果收益仍需后续受控实现对照。

现有可复用入口：[已验证位置/连接/窗口查询实现](../../agent/A006/physical_supplement/reviewed_v1/readonly_physical_supplement.tcl)、[E004模块×SLR实际报告示例](../../project/E004_m002_routability_optimization_analysis/experiment_results/runs/R001/attempts/AT001_readonly_physopt_diagnostics/utilization_SLR_Attention.rpt)、[本次完整层次总表](../../project/hardware/vivado/reports/m002_E005_R006_AT002_closed_place_physopt_readonly/physopt/utilization_hierarchy_depth7.rpt)。后续若执行，使用新批次/输出目录、固定原DCP身份，沿用单EDA/8CPU/nice5与资源保护、正常进程无墙钟强停，不覆盖E005原证据。
