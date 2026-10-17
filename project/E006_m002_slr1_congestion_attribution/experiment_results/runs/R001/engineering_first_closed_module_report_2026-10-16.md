# E006 / R001：首批闭合模块工程报告

本报告仅覆盖已自然关闭的原生global和Attention、MLP、MLP metadata、weight loader查询。原physopt只读会话继续执行，完整module stage、热点、失败样本、连接及终态尚未关闭；不是E006最终交付。平台、源、接口与E005失败终态保持。

输入为E005原closed physopt.dcp（579969232B，SHA256 `766217926d5e8d01137d0ba39f4512dd2337f9fcbcb788525320b5bd0a810a2d`）；实际启动、合同、144冻结输入和4 archived source绑定见[AT001](attempts/AT001_physopt_attribution/input_bindings.json)。本报告来源是[batch001摘要](attempts/AT001_physopt_attribution/closed_owner_batch001_summary.json)及[完整facts](attempts/AT001_physopt_attribution/closed_owner_batch001_facts.json)，后者SHA256 `2c2352c0bff332ea225470fe321ad1f5d755a1f7414e2e89facb3489dcfdcdd0`，含query0回执快照、原生报告身份和精确行号。

## 原生资源分布

每格依次为SLR0 / SLR1 / SLR2。MLP compute与MLP metadata是互斥的不同owner，Attention metadata包含在Attention owner内。

| 原生指标 | global | MLP compute | Attention | MLP metadata | weight loader |
| --- | --- | --- | --- | --- | --- |
| CLB LUTs | 251963 / 336107 / 213681 | 233499 / 248355 / 0 | 0 / 29578 / 198380 | 1579 / 1425 / 562 | 0 / 3512 / 2 |
| CLB Registers | 324527 / 435367 / 257156 | 294608 / 288933 / 0 | 0 / 38447 / 233337 | 1844 / 2050 / 582 | 0 / 6540 / 1 |
| BRAM36K当量 | 151.5 / 468 / 321.5 | 126 / 361 / 0 | 0 / 57 / 296 | 0 / 0 / 0 | 0 / 0 / 0 |
| URAM | 280 / 280 / 192 | 0 / 0 / 0 | 0 / 0 / 80 | 280 / 280 / 112 | 0 / 0 / 0 |
| DSP blocks | 1861 / 1835 / 1755 | 1858 / 1291 / 0 | 0 / 544 / 1752 | 0 / 0 / 0 | 0 / 0 / 0 |
| touched CLB sites，非加和 | 48769 / 49185 / 45848 | 46507 / 42934 / 0 | 0 / 8286 / 43515 | 1017 / 1346 / 285 | 0 / 1613 / 3 |

MLP compute是当前SLR1的主要计算资源所有者，BRAM36K当量361，占全局SLR1 468的77.14%；其288933个CLB FF占SLR1 435367的66.37%。MLP metadata单独占当前SLR1全部280个URAM，三SLR共672；Attention另有80个URAM，均位于SLR2。metadata内容和容量解释以[R002源码审核](../R002/metadata_uram_roles.md)为准，不能称完整W4/W8系数缓存。

这些是当前模块放置归属；尚未由热点与连接证明各模块对局部路由失败的份额，也未验证任何后续迁移的收益。

## 独立核查与计数口径

[A007完整primitive审核](../R002/closed_primitive_ownership_review.json)独立重算2,204,250 unique NAME：互斥owner前缀零差异，全部REF分组和153,056个site-owner sets与原生导出一致。首4owner×3SLR的CLB touched、CLB FF、BRAM当量、URAM、DSP共60项与原生资源报告一致。

raw LUT primitive行数不等于native CLB LUTs；LUT combining使父子/跨owner资源不能强凑加法。SLR1多owner共享SLICE站点23,285；表中touched CLB sites及control sets不作为可累加的独占分配。DSP split primitive行数不作为DSP blocks。DDR owner的all-site FD/LD还含LAGUNA FF，须以实际SLICE子集对照CLB Registers；grouped DDR owner也不等同MIG本体，见[R002外围审核](../R002/peripheral_slr1_primitive_review.json)。

## 原生放置阶段SLL参考

原生报告1.1节：global SLR0/1界面10474、SLR1/2界面8509，总18983；MLP自身跨SLR0/1为7609（0→1为2521，1→0为5088），Attention自身跨SLR1/2为6368（1→2为3949，2→1为2419）。MLP metadata自身为370+161=531，weight loader为5。

来源为同一已关闭的[global](../../../../hardware/vivado/reports/m002_E006_R001_AT001_physopt_attribution/utilization_global_SLR.rpt)、[MLP](../../../../hardware/vivado/reports/m002_E006_R001_AT001_physopt_attribution/utilization_exclusive_mlp_SLR.rpt)、[Attention](../../../../hardware/vivado/reports/m002_E006_R001_AT001_physopt_attribution/utilization_exclusive_attention_SLR.rpt)原生报告。这些是physopt的native SLL读数，不是后续端点计数、流量、完整路由失败分布或成功routed资源；不将owner读数相加推全局。

## 查询成本与待完成项

原生global99s、Attention33s、MLP61s、metadata/loader各6s；core_other用32,829个不连续primitive leaf余集，而前4owner均用1个exact hierarchy root。该余集无重复、内部祖先/后代重叠或越出core前缀，调用处不重新通配/执行cell名字，见[有界构造审核](../../../../../agent/A006/E006_core_other_argument_cpu_audit_2026-10-16.json)。Vivado内部对象解析/聚合算法仍未知，CPU活跃不能替代query覆盖验证。

[16:29:36成本快照](attempts/AT001_physopt_attribution/query_cost_observation_20261016T162936Z.json)中core_other已1084s仍未关闭。后续11项热点native资源报告也接收primitive集合，同physopt各单区原已测54,671–56,489个primitive；UNION实际数待取得。没有已完成的大leaf-list样本支持可靠ETA。当前冻结源不改，不按耗时或静默强停，也不叠加查询；各热点query实际0闭合后先交单区事实，不必等完整stage。

后继优化验收优先采用native exact hierarchy报告与闭合primitive/site/LOC互斥CPU统计，避免照搬大leaf-list report_utilization。当前继续其他owner/detail、10NW/UNION、40原文失败net和全部热点附着canonical连接；正式终态另核144输入、原DCP、archived源、外部输入、所有PID/start、锁和资源。固定窗口拥塞仍UNAVAILABLE，当前没有合法routed时序、CDC/板卡或优化因果签核。
