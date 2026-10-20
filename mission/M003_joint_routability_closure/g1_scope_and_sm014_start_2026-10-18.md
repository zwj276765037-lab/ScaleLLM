# M003：G1限定接受与SM014实际推进决定

2026-10-18，Root项目主控；依据用户已授权连续执行、E009工程交付及A007 G1独立综合审核。此次为主控技术处置，不冒充用户对结果的批准。

## 决定和适用范围

**LIMITED_ACCEPT_FOR_SM014_DESIGN_AND_CANDIDATE_EVALUATION。** SM013固定取数执行completed；归档CONFLICTS查询的569597 canonical、848互斥组、union/精确deep选择及104代表DATA路径的有界适用性接受。原生报告547548与其差22049仍OPEN，完整报告级归因与任何优化收益inconclusive；不登记无条件G1 PASS，不删除常量凑数。

立即推进SM014 F1–F4及候选比较，不等待无关缺口，也不自动新开EDA。选型依据必须指向已测具体网/端点/控制/物理事实；不得依赖“569597与报告547548是相同精确集合”、未测overlap-node映射、full-cut TNS或per-net SLL。若实际候选依赖这些缺项，该候选先补最小必要证据或deferred。22个非constant物理未知全部不在当前deep与HEAD/TAIL/META范围，不阻塞已有候选设计；一旦选型扩及这些对象重新检查依赖。

当前没有selected候选，G2未通过；SM014是设计/离线分析阶段，生产RTL、XDC、构建和验收保持。G2前不启动修改或implementation。原SLR2 C01必须在联合决定中明确处置，不能静默沿用或删除。

## 当前事实与主要关注

AT003于02:11:43Z自然native0/supervisor0、stop_reason=null；144输入和13档案完整，进程/观察器已退出、EDA锁释放。A007于约02:30Z交付独立审核，随后等待Root技术处置；主控于本记录恢复阶段衔接。

535331个网两端同已知SLR不证明路由始终本地，也不否定少数高扇出跨区网的影响。parent head范围有5058冲突网，2408为SLR2→SLR0、1720为SLR1→SLR0/2；应拆真实payload字段与helper。tail代表maintenance_soft_clear→CE为−2.977ns、branch1控制代表为−2.896ns，均仅代表路径，要求成本表同时覆盖D/Q与CE/clear/clock；不能只复制宽payload而漏控制压力。

## 实际分工和交付

- A006：唯一工程集成者，消费现有已关闭candidate_endpoints、deep_cells、site/tile、alias及RTL字段/状态准备；输出可审核F1–F4、每项具体修改/排除建议、真实D/Q/读者映射、资源及控制总成本、原C01取舍、策略和测试映射。拥有`agent/A006/M003_SM014_design_20261018/`及自身状态。可顺序执行必要离线统计，不重复全表审计，不新载DCP，不改冻结包或生产源。
- A007：独立审核新设计，拥有`agent/A007/M003_SM014_review_20261018/`及自身状态。可先从已核证据准备F4/门槛核查，避免与A006重复扫描；审核真实语义、上游/下游/控制总成本及候选依赖，无EDA。
- Root：独占mission/goal/results、候选最终selected/rejected/deferred及联合冻结；收到阶段交付即处理，不把技术门误作新的用户批准。

最多3活跃含Root，无后代；不重绑外部会话。其他工作也在本工程，所有人保留并适配他人修改。轻量分析与重工具额度分别管理，单EDA与原CPU/内存/磁盘保护、正常无墙钟/静默强停保持。

F2必须逐项保持：满FIFO当拍pop不给上游credit、两entry/原子pop/宽payload无复位；meta同沿launch与meta_rsp_fire按原最终NBA优先，不能用datapath_clear替换或旧Q再打一拍。C-A2/C-R1仅粗组计数不足以选入，必要时deferred并说明。已测端点不足的兼容位置/真实新图身份留G4闭合，不能凭空写坐标。

## 证据

- [工程交付](../../project/E009_m003_failed_net_attribution/experiment_results/g1_engineering_handoff.md)
- [独立G1审核](../../agent/A007/M003_SM013_review_20261018/G1_consolidated_review/review.md)
- [终态](../../project/E009_m003_failed_net_attribution/experiment_results/runs/R001/attempts/AT003_failed_route_full_attribution_scalar_fix/status.json)
- [候选决定表](candidate_decision_register.md)
