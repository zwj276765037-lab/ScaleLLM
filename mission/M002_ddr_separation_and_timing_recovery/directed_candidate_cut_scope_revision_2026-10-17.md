# M002 / E006 R005 与 E008：候选有向边界采集范围修订

当前状态：范围与独立架构规格已核对，允许按本范围连续准备和验证新源码；原生资格与实际运行尚未发生。本文件不授权终止正在正常运行的 E006/R004，也不代表新原生任务已启动。

用户已授权针对 SLR1 的优化及下一轮完整 implementation。R004 的全附着网端点采集包括大量候选之外的时钟负载；截至本修订准备时，两个候选的成员/资源阶段已闭合，C01 完整连接仍正常运行。以下是明确的诊断范围变更，不声称与旧的整网全部端点覆盖相同，不改变功能、时钟或最终物理验收。

## 目标与明确放弃的覆盖

保留所有跨越候选边界的真实有向连接：外部 driver 到候选 load、候选 driver 到所有外部 load，以及候选内部连接和实际附着 canonical nets/aliases。候选时钟、复位、常量、控制、INOUT、未知方向与 top ports 均不得静默丢弃。

仅对已原生证明具有唯一外部 driver、无 INOUT/unknown 且候选成员及连接映射完整的网，允许不枚举同网其他外部普通 IN load。它们连接的是 outside→outside，不属于候选有向 cut。此时必须声明 `outside_peer_leaf_loads=NOT_ENUMERATED`、`full_net_endpoint_coverage=false`，不能报告完整外部 fanout、REF/空间分布或整网端点总数；有向 cut 完整性单独记录。

统一采用 `coverage_version=candidate_directed_cut_v1`；`directed_boundary_complete`、`candidate_leaf_coverage_complete`、`native_role_gate_qualified` 与 `full_net_endpoint_coverage` 分开校验，不能用一个 retained 数量冒充全网完整。详细规格为 [A007 有向边界审核](../../agent/A007/directed_candidate_cut_scope_review_20261017.md)，14040 B / SHA256 `59473b7c7d13549dcf95a8e3948097f5999f824968d1a2889f7b62e1e5262c51`；其中 RAW-only 常量、nonleaf/disconnected 账本、具体资格/回退和时序输出语义均适用。

原 R004 的全热点 UNION 整网补采不再作为新 R005 选型的必需步骤；其未完成状态和原始产物保留，不能改写为完成。已闭合的热点/失败样本/资源仍按原身份引用。新采集只支持两个明确候选的比较，不声称恢复了全热点 UNION 的旧覆盖。

## 原生采集资格与回退

1. 每个实际图重新确定候选 RAW/S/P、物理父与实际 leaf pin 集合。不能仅靠 root 名称前缀推定复制对象归属；E008 使用真实存活/origin-copy/物理父解释，包括 DSP children。候选本地 pins、附着网及全部 aliases 的映射必须闭合。
2. 保存原生 `list_property -class pin` 与 `list_property_value DIRECTION -class pin` 的 schema 证据。只有可证明 built-in pin DIRECTION 的过滤语义覆盖时，才可对同一完整 segments 集合执行原生 `get_pins -leaf -of_objects $segments -filter {DIRECTION != IN}`，获得全部 OUT、INOUT 和非 IN 未知方向。不得用单一 canonical alias 代替全部 segments，不得以少量对象采样推定全图属性覆盖。
3. top ports 完整取得，并按外部 driver/load 解释方向。候选本地 load 与完整 driver/INOUT/unknown 库存联合形成保留端点。候选本地非 LOAD pins 必须出现在 native 角色库存中。获资格的唯一外 driver 分支，不得在资格检查前后调用该网无 filter 的完整 leaf 查询。空方向、查询错误、归属不明或 schema 无法证明时，不使用缩减结论。
4. 候选驱动的 outgoing 网、无/多 driver、INOUT、未知方向或成员/映射不完整的网回退原全端点枚举；无法取得完整回退结果则该项未通过，不把缺失当作零。每网记录所用覆盖模式、资格证据、回退原因和实际保留数量。
5. 所有时序查询仍在完整、未删改的原生设计图上进行。对已解析单 driver 边界网，INGRESS 使用全部候选 LOAD，EGRESS 使用全部外部 LOAD；max/min 各 cap16，不声称完整 cut TNS 或时序签核。无法定向的网单列。

该协议的数学/CPU 检查不替代新原生图资格，预计性能改善尚未实测。详细原生覆盖按上述 A007 规范与实际新源码绑定。普通实现修复在此合同内连续进行，不逐次增设审核文档或用户批准。

## 新 E006 R005

新 R005 的输入仍为 R004 同一 E005 physopt DCP、144 冻结生产输入、C01/C02 字面 root 和原热点/失败样本。重建必要的同图成员/映射后分别取得有向 cut、方向时序及与热点/失败样本的关系；复用的原生资源报告明确标注原 R004 运行身份，不伪作本次新测。候选仍至多选一个，完整性、适用性和物理收益分别判断。

R004 固定运行源码和原始产物保持。仅在 R004 自然结束，或用户另行明确批准本次 R004 诊断切换并完成受控收尾后，才可使用唯一 EDA 资源启动 R005。原用户 R001 停止例外已执行，不能复用为本次停止授权。

## 后继 E008

[原 E008 合同](exact_hotspot_offload_implementation_contract_2026-10-17.md)除附着整网全部端点采集范围外保持。pre-place、place、physopt、route 使用本修订的同一有向 cut 口径，各阶段重新验证资格，不跨图复用成员/位置。对比中明确区分新口径和原全网端点统计。

保留完整 pre-place 资格、80 项保护边界、时钟/CDC/reset/IO、hard/nonexclusive/non-routing-contained SLR2 Pblock、全部实际 P 的 SLR2 合规，以及完整 place→physopt→route、正式 setup/hold/PW 和合法布通验收。时钟/复位安全检查不因外部 peer load 不导出而缩减。

原 b59d1126 源码包与原合同字节保持，新的入口和 manifest 另存。实际执行绑定同时包含原合同、本修订、新源码身份、真实候选选择证据、前置终态及 PID/start/锁收尾，不允许预填支持或执行通过。

## 资源与责任

A006 为唯一 EDA 执行者并负责新源码/实际证据；A007 负责架构覆盖和独立结果核查；主控负责合同、真实选型绑定、摘要和导航。最多三个活跃 agent，无后代，保留他人修改。

单 EDA、CPU0–7/nice5/max8；树 RSS192GiB、MemAvailable<48GiB 持续30秒、磁盘<30GiB 的保护保持。正常进程无墙钟/静默强停。旧工程只读，不改 RTL/IP/ABI/数值/时钟，不运行 bitstream、GPU、板卡、PPL/ACC。
