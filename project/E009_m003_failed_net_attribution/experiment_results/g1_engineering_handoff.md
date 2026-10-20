# E009 / SM013 G1工程交付：固定范围独立审核接受，报告差额仍OPEN

AT003/f0ac0b91固定包已于2026-10-18 02:11:43.478705Z自然完成，native0/supervisor0、stop_reason=null，无强停、cleanup、survivor或来源差异。11个登记PID/start及观察器均已消失，唯一EDA锁空；144生产输入与13归档完整。没有生产RTL/XDC改动、综合、implementation或板级运行。AT001/AT002两次适配自然失败及原证据保持；本次singleton属性修复已通过完整原生2914086元素身份资格。

## 总体口径与主组

| 项目 | 实测值 | 限界 |
|---|---:|---|
| 原生CONFLICTS对象行 | 2886261 | raw→alias映射完整 |
| unique native segments | 2914086 | 包含固定补充；无重复或矛盾 |
| canonical CONFLICTS | 569597 | 848互斥主组总和一致 |
| 本次native report冲突网 | 547548 | 差22049仍OPEN，不强配常量桶 |
| 原生端点行 | 7135972 | leaf/top-port，非连接对笛卡尔积 |
| 前20完整组 | 436749 | 非16代表样本数 |
| 固定补充冲突网 | 6761 | 与前20交集142 |
| 合并union | 443368 / 569597 = 77.8389% | 整组分类覆盖，非深查完成率 |
| 精确deep唯一ID | 20534 | 20组各lex前16+全部supp ID/tag逐项核对 |

前三组分别是MLP branch1 SLR2→SLR2 151527、Attention projection array SLR1→SLR1 84058、MLP branch0 SLR0→SLR0 55822。535331同已知SLR端点、12194已知源且含非本地负载集合；这些是网分类，不能直接推时序关键性、拥塞因果或搬迁收益。SLR2不是空的接收区，必须结合既有occupied-CLB与新综合/物理证据决策。

## 固定补充的候选事实

| tag范围 | canonical总数 | 冲突canonical | 冲突源/负载事实 |
|---|---:|---:|---|
| parent head模式 | 13509 | 5058 | 2408为SLR2→SLR0，1720为SLR1→SLR0,SLR2；另有本地与小交集 |
| parent tail模式 | 6561 | 1551 | 942 SLR2本地、608 SLR1本地、1 SLR2→SLR1,SLR2 |
| meta_read_addr模式 | 35 | 20 | 20均SLR1→SLR1 |

这些是冻结regexp模式命中的网及派生helper/alias，不能当作RTL字段宽度或有效载荷位数。原生已保存完整候选端点、属性/LOC/BEL/固定标志/来源名与site→tile；G2要从真实驱动与读者选择字段，不能只按网名改变量。只读字段布局准备另见experiment_source/SM014_parent_field_layout_baseline.json：生产TILE_W9，head/tail各6560bit，完整双branch×两entry选项payload+3456FF，仅算术预算、未选型。现有branch ingress是不同在途存储，不可删除。

## 有界时序的适用性

28组×max/min共56命令全部native code0；其中52报告含104路径，4报告（TOP09/TOP10 max/min）无路径。归档Tcl先对每tag取lex前16个网，再对这些网的全部leaf IN pin并集总取lex前16，max_paths2/nworst1。离线重放精确deep_targets并按候选端点重建该集合；104路径均在DATA表实际pin或合法primitive输入弧命中。验证排除了Command头、launch/capture clock与launch C/CLK clock-to-Q；clock-only/source-C反例被拒绝。

多个Command头打印相同XDMA对象，原报告不改；native实参列表未另行dump，故以冻结Tcl/现有端点重建与路径体适用性支持，不把显示头疑点默默抹去。当前失败DCP仍未合法布通，代表slack不等于签核或完整cut TNS。

具体代表：meta max +8.668ns/min +0.186ns，覆盖地址自身逻辑；parent-head max +2.403ns，实际包含cache响应/metadata error链；parent-tail max -2.977ns为maintenance_soft_clear→tail[0]/CE、route12.026/total12.559ns；branch1 TOP01 max -2.896ns为clear_kernel_row[0]→MLP控制rdata、route11.776/total12.289ns。它们只证明这些有界路径事实，不能将HEAD/TAIL标签泛化为全部payload关键路径。

## 未知与处置

CONSTANT22050全为source SLR UNKNOWN：22042有负载、8无负载；均无UNKNOWN负载。unknown driver/multidriver/INOUT均0。另1非constant source-SLR UNKNOWN与21 load-SLR UNKNOWN共22 canonical全部在deep20534及F1 head/tail/meta补充之外；完整ID和规范模块已列physical_unknown_disposition。精确unknown owner未在固定deep导出即NOT_MEASURED，不能猜LOC；仅阻塞实际依赖这些未知物理事实的候选。未解释native report与canonical差22049保持OPEN，不通过删常量或近似数相等来宣称EXACT。

完整重叠节点→网映射、full cut TNS、per-net SLL为NOT_MEASURED；702396重叠节点是历史独立资源指标。A007已完成独立综合审核，接受固定查询分类/union/deep与104代表DATA路径适用性，建议Root限定推进SM014 F1–F4；+22049仍OPEN，不记无条件G1 PASS。正式G1处置与选型由Root登记，工程不替代该判断；当前没有新EDA任务。

## 可审核入口

- [工程终态/输入/进程/锁复核](runs/R001/attempts/AT003_failed_route_full_attribution_scalar_fix/terminal_facts_v3.json)
- [独立原始映射/分组/union/deep/type审计](runs/R001/attempts/AT003_failed_route_full_attribution_scalar_fix/independent_raw_attribution_audit_v3.json)
- [原始审计工具实际exit回执](runs/R001/attempts/AT003_failed_route_full_attribution_scalar_fix/independent_audit_execution_receipts.json)
- [DATA-only时序scope与104路径](runs/R001/attempts/AT003_failed_route_full_attribution_scalar_fix/timing_scope_offline_audit_v2.json)
- [时序scope实际exit/CPU负例回执](runs/R001/attempts/AT003_failed_route_full_attribution_scalar_fix/timing_scope_v2_execution_receipt.json)
- [22个物理未知及范围处置](runs/R001/attempts/AT003_failed_route_full_attribution_scalar_fix/physical_unknown_disposition.json)
- [完整主组表](runs/R001/attempts/AT003_failed_route_full_attribution_scalar_fix/evidence/native/module_region_summary.tsv)
- [最终覆盖和未知](runs/R001/attempts/AT003_failed_route_full_attribution_scalar_fix/evidence/native/unknowns_and_coverage.json)
- [候选端点](runs/R001/attempts/AT003_failed_route_full_attribution_scalar_fix/evidence/native/candidate_endpoints.tsv)
- [深查单元属性](runs/R001/attempts/AT003_failed_route_full_attribution_scalar_fix/evidence/native/deep_cells.tsv)

## 最新独立审核回执

[A007 G1综合审核](../../../agent/A007/M003_SM013_review_20261018/G1_consolidated_review/review.md)（SHA256 02edb7af891a59cb95d863119d3c1e064125076b4e37cfe6ca2cfa59a3269af3）已真实送达；[本实验收讫绑定](runs/R001/attempts/AT003_failed_route_full_attribution_scalar_fix/G1_independent_review_received.json)。工程execution completed、verdict inconclusive保持，正式Root阶段登记尚待。
