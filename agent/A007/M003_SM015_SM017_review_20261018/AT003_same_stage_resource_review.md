# AT003同阶段资源报告子项独立接受

A007以已审且未改动的真实`m003_resource_budget.py`独立CPU重放（chunk408796、exit0），绑定E005同stage基线SHA cd15c3a0及新完整flat/hierarchical原报告。当前原生资源报告已生成，但AT003后报告整体仍failed1；此独立子项不改变原终态。

| 报告范围 | LUT净增 | FF净增 | 固定存储/DSP |
| --- | ---: | ---: | --- |
| 顶层 | +111 / ≤177 | +34 / ≤34 | 全不变 |
| A3 resident u_meta | +40 / ≤96 | +34 / ≤34 | URAM总80，其他不变 |
| M2 shared及self | +76 / ≤81 | 0 / 0 | 全不变 |

全局CARRY8 +4 / ≤8。原生新顶层828874 LUT、报告寄存器1029350（实际FF1029348，另2 AND/OR，与基线口径一致）；meta387 LUT/45FF，shared389143 LUT/479315FF，self11401 LUT/13123FF。对应新hierarchical原行25/510/642/643及flat原行38/43/44/198均已核。

报告净增支持冻结资源上限，不能代替81缓冲、85保护LUT、34 own-address FF、完整13120bit及40+40URAM的实际角色/连接/增量锥。XDC/Tcl入口和collector失败仍须新AT关闭，G4与物理均未通过。[正式JSON](AT003_same_stage_resource_review.json)。
