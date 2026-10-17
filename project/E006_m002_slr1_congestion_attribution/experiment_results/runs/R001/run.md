# R001 — E006 / SM010 SLR1资源、热点与连接归因

Execution state: running
Verdict: unassessed
Applicability: 当前E005 closed physopt.dcp，只读归因；E005 route失败与全局验收状态不改。

AT001已实际启动原生Vivado2025.2/VCU118/xcvu9p-flga2104-2L-e；原physopt恢复和完整primitive导出已自然完成，global与Attention/MLP/metadata/loader首4owner原生query均0，后续查询在同一原生会话继续。精确argv/cwd、source/contract/原DCP/144freeze和外部target身份见实际[started](attempts/AT001_physopt_attribution/started.json)及[input_bindings](attempts/AT001_physopt_attribution/input_bindings.json)。父工程状态、正式安全OPEN、数值/ABI/双DDR/时钟保持。只对自然闭合query交付局部事实，不把部分完成当整stage或终态。

单EDA，CPU0–7/nice5/max8；RSS192GiB、MemAvailable48GiB持续30秒、disk30GiB保护，无墙钟/静默强停。独占R001和A006，R002为A007独立分析/审核，主控维护三摘要与共享正文；不创建后代，不热改原E005或生产树。

连接范围为10NW实际cells去重UNION所附着全部完整canonical nets，端点仅primitive leaf DIRECTION IN/OUT，INOUT和top ports未枚举。NO_PRIMITIVE_DRIVER不等于无真实driver；类别OTHER可含未识别的存储/DSP控制拼写，后续只能用实际REF/REF_PIN_NAME细化，不按名字猜协议。native资源与primitive hist/site/BEL归属分列，DSP split refs不当DSP个数，sharedsite/重叠区不相加，fixed拥塞UNAVAILABLE。

## AT001实际原生启动

2026-10-16T15:51:42.925759Z实际detach，native metadata15:51:44.063950Z；supervisor942046/start927846090、leader942061。只打开原E005 closed physopt.dcp（766217926d…），原生日志已明确open并加载正确part；4原PID/start、CPU0–7/nice5、kernelFLOCK由942046持有、actual archived sources均核符，见[原生启动观察](attempts/AT001_physopt_attribution/native_started_observation.json)。

输入绑定8420B/SHA4dbaf3d6aabf1996cbabe7064dab5d955360f88fe2447a124bf967105f9c0c2f，含新合同、144freeze、原DCP、E005前终态、A007精确hierarchy/40net样本、10NW实际tile名单及archived源码。新query/supervisor位于agent/A006/E006_slr1_attribution，实际启动源码固定；只做Python AST/Tcl完整性结构检查，没有新增回归或API试跑。

执行顺序：module_resources（全量互斥primitive归属和native exact-owner/cut×SLR、native总量与33额外根/候选）→hotspot_ownership（10NW各区与去重UNION逐cell及native资源）→failure_samples（10实际node tile GRID/SLR/NW关系及40原文exactnet，缺席不猜名）→hotspot_connections（全部UNION附着完整canonical nets与全部真实leaf端点/owner×SLR矩阵）。每stage独立关闭回执、立即里程碑交付，连接范围不是全设计net census。原生DCP加载与实际查询结果/自然终态待核，正常无墙钟/无输出强停。

所有native hierarchy totals与exclusive primitive cut分列，cross-hierarchy LUT combining允许子级LUT和偏离parent；DSP split refs只作primitive hist，site及原生DSP资源分开。共享site与重叠区域不相加，fixed congestion仍UNAVAILABLE。A007 owns R002，主控维护三摘要和共享正文，运行源不热改。

## 首批自然闭合owner事实

已固定[batch001摘要](attempts/AT001_physopt_attribution/closed_owner_batch001_summary.json)和[完整facts](attempts/AT001_physopt_attribution/closed_owner_batch001_facts.json)，含原生query回执快照、报告身份/行号、实际archived source/合同核对。MLP BRAM36K当量SLR0/1/2=126/361/0，Attention=0/57/296；MLP metadata URAM=280/280/112。首4owner×3SLR的CLB touched sites、CLB FF、BRAM当量、URAM与DSP共60项和A007完整primitive/site独立审核一致。raw逻辑LUT行数不能替代native CLB LUTs；DDR非SLICE FF不能混入CLB Registers。

可独立审核的[首批模块工程报告](engineering_first_closed_module_report_2026-10-16.md)汇集5项原生资源表、SLL参考、口径和实际查询成本；这是部分闭合交付，不代替E006完整终态。

完整primitive为2,204,250个unique NAME；A007独立owner前缀匹配零差异，REF组及153,056 occupied site-owner sets全等，见[R002独立审核](../R002/closed_primitive_ownership_review.json)。SLR1多owner共享SLICE=23,285，owner触碰站点不得加作全局独占站点。native其他owner/detail、热点、失败样本、连接及终态仍待闭合；主控与A007已实际消息收到首批事实。
