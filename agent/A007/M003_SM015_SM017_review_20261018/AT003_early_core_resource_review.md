# AT003 core OOC资源小阶段独立审核

A007已核新旧实际原件及保全副本4份SHA、相同Vivado2025.2 build/器件/设计与Synthesized阶段，独立抽取全部资源行。新报告来自当前core原生report_utilization，命令完成回执可定位；未读取DCP。

| 同core指标 | E005旧 | E011新 | 增量 |
| --- | ---: | ---: | ---: |
| CLB LUTs（报告合并后口径） | 742483 | 742594 | +111 |
| FF | 892884 | 892918 | +34（全部FDCE；FDRE不变） |
| CARRY8 | 53863 | 53867 | +4 |
| URAM | 752 | 752 | 0 |
| Block RAM Tile | 844 | 844 | 0 |
| DSP | 5445 | 5445 | 0 |

LUT1…6原语和增量为+112，与合并后报告+111区分；LUTRAM/shift-register、833 RAMB36+22 RAMB18均不变。这些core合计与冻结总上限一致，但不能证明81 buffer/85保护LUT、两片各40URAM、helper own-address或各机制增量锥。完整顶层同stage预算、23产22用新来源、新图/G4及物理仍待；不把局部报告提前写成全综合或G4通过。[完整审核JSON](AT003_early_core_resource_review.json)。
