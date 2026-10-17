# E007 / R001：入口集中独立审核

execution：初轮有界源码审核完成，工程修复待回传。verdict：当前修订需修正后才能作为实际启动入口；没有新增用户批准门。applicability：已交付 CPU 准备源，不代表实际 pre-place/API/几何/cut 或物理结果通过。review：A007 内部审核，已实发主控及 A006。

审查身份与逐项定位见 [事实 JSON](independent_entry_review.json)。初始 delivery 为 5839 B / `cad3b93ce1a44bac7e104650429e933f928b3e85925e9d4852184daebda0863a`；manifest 为 8340 B / `807c1c67fae277df08147485e420c3e92d69aa711f26eb0df974062837fa1ccd`。30 项有界 manifest 身份及自有 Python AST 已独立核对。未读取大 DCP 或重扫 676 MB primitive 导出。

## 初轮需修正项

| 项 | 实际问题与所需修正 |
| --- | --- |
| F01 | pin 分类只看名称，DSP.C 被当作 CLOCK，未知默认 data/control。用 REF/REF_PIN/实际 clock 证据，保留 unknown。 |
| F02 | 所选 clock/IO 被静默滤除，BRAM/URAM/未知 REF 却默认可绑。误选须显式拒绝，DSP 父须属于预定 Hadamard。 |
| F03 | 缺失原对象、未知来源新增对象仍可得到 compliance=true；cut 在阶段真实 clone/P 归并之前导出。须先核真实对应、解释移除、查完整 membership/属性，再以阶段 P 测 cut 和 100% SLR2 服从。 |
| F04 | RLOC/macro 仅记录，未核组外搭档/明确 SLR assignment；add 后未核既有 membership 保留。补有界冲突及前后读回，不能清除原约束。 |
| F05 | 缺切口 scoped min/max 诊断；全局 worst32 不能证明切口路径。补声明上限/覆盖的边界路径及物理位置、owner/domain 字段，CPU 聚合 net/pin/cell/fanout/pair，避免大 leaf utilization。 |
| F06 | 收尾未核启动绑定的 stage_inputs 清单自身身份；E006 closeout 只核 JSON，未核其引用证据。补绑定与引用身份收尾。 |

独立纯函数反例：`C, IS_CLOCK=0 → CLOCK`；未知 pin → `DATA_OR_OTHER_CONTROL`；`RAMB36E2/URAM288/UNKNOWN_PRIMITIVE → bindable=true`；1 个 missing 与 1 个未知来源新增同时存在时 `compliance_established=true`。这些是程序逻辑反例，没有伪装成原生图结果。

另外保留两项有界检查：N01 将实际 clock-region 对象 NAME 与 resize 的 `CLOCKREGION_` token 分开并严格读回，当前仅是兼容风险，未声称 Vivado 已失败；N02 最终聚合读取已有 phase receipt 的 `post_code/locality_code`，使明确诊断失败不会被其余完整产物掩盖。

## 已保持的入口义务

真实 E005 成功 place/physopt 来源及 debug_materialized 父链通过原 `parent_recovered_place/pre_place_evidence` 校验，没有伪造 timeout 或独立 OPT 收据。175 约束来源、162 registered XDC、全部原时钟、live pre-place、reset/CDC/IO 和 80 结构 POST 继续继承；新图仍须实际资格。

runner 保持非阻塞单 EDA 锁、实际 E006 managed terminal 及 PID/start 闭合、CPU0–7/nice5/max8、RSS192 GiB、MemAvailable48 GiB/30 s、磁盘30 GiB；无墙钟/静默强停。阶段 POST/locality 异常重抛；native0 还必须通过三阶段 result/integrity/compliance 和合法 route 才能给正面执行结果。

CPU 的 59 个字面 selector 案例与旧 physopt 导出只支持该图的选择结果；RAW/S 术语桥接不验证新的原生对象、API 或约束。父链 CPU 回执对应其明确记录的旧 adapter 修订。新工程修复后仅复核改动及相关反例，不扩大测试/资料范围；实际 E006 当前正常运行，A007不控制进程。

## 修复复核

待 A006 集中回传固定修订及针对性 CPU 证据；本文件及 JSON 为唯一集中审结，后续补记修复身份和各项结论。

## 集中修复复核（最新）

execution：F01–F06/N01–N02 的有界修复复核完成。verdict：**源码准备审核通过**，本范围无未关闭的源码缺陷。applicability：最终 manifest `236718abd0577d12c64369da9c8d1ed13ed3050b4473a8a4486d47e9cb47eca6`（9059 B，8自有/16复用）；不等于实际启动资格、原生 API 或物理结果通过。review：内部审结，没有新增用户审批门。

| 项 | 修复闭合证据 |
| --- | --- |
| F01/F02 | REF-aware pin 分类、物理 REF allowlist、原始 DSP 类型及 Hadamard 祖先均显式核验。unknown 端点及 unknown-only/mixed net 汇总保留，clock/reset 等类别仍另报非排他 unknown incidence。 |
| F03 | 原生 ORIG 对应先形成实际 P，再导出完整 cut；未解释 missing/new、组外 clone 或 membership 差异拒绝。原生属性不可用、查询未执行/失败在 Tcl 和 Python 两层拒绝，真实 query 回执身份进入 reconciliation。 |
| F04 | 对相关 cell/ancestor 政策和全部原 Pblock 属性/成员作前后核对；macro/相对位置/明确 SLR 冲突或无法核验时拒绝，原约束不清除。 |
| F05 | 端点增加 BEL/site/tile/clock-region、owner/domain 与 unknown 原因；实际 P 切口的 ingress/egress/unresolved 各 min/max 路径入口已准备，每方向/类型最多16条。原全局 timing/POST 保持。 |
| F06/N02 | 收尾检查绑定的 stage_inputs 清单自身及 E006 所引用终态/证据身份；即使 native0，显式 POST/locality code 也必须均0才能正面聚合。 |
| N01 | 真实 `XnYm`/`CLOCKREGION_XnYm` 与 resize token 分开，仍须实际 site/SLR 展开读回，不复制历史坐标。 |

中间 `729ca173` 修订曾残留两条路径：ORIG 查询失败仍可当空集合，以及 net 汇总吞并 unknown。均已实际通知工程并由最终修订修复；原修订快照、初轮 `807c1c67` 源和回执保留。最终变更集中于对应函数，原 controller、16复用helper、真实父链与175来源适配、时钟/POST和监督策略未变。

验证已核最终33项 manifest 身份、CT002当时16项原/快照身份、CT003的17项嵌入身份，并核初轮 manifest+11份源/回执保留。CT002真实 exit0 覆盖23类旧REF、6物理/2rawDSP拒绝、11pin、9reconcile及region token；CT003两步实际 exit0，起止 `2026-10-16T17:55:32.710222–17:55:32.873539Z`，覆盖4失败/缺证拒绝、1合法query及4unknown分类。A007再独立执行这9个小型纯函数检查，结果相同。59个字面selector案例未重跑：selector函数未变；bindable已改并有对应新检查，未沿用“全部未变”说法。

CT003内prepare打印的是中间manifest `ba7ff6ec…`；最终 `236718ab…` 更新了CPU收据绑定，8份执行源均匹配CT003快照，不冒充又执行过一次原生验证。完整身份及适用范围见伴随 JSON 的 `repair_review`。

实际原生属性/API、macro/SLR/相对放置兼容性、pre-place集合、clone对应、SLR2几何、完整cut和timing仍 **NOT_RUN**。cap16不是完整路径枚举或每一clock-pair最坏路径，full-cut TNS仍NOT_MEASURED；fanout/模块-时钟-SLR汇总须基于未来闭合端点做CPU归纳。实际E006闭合与候选适用性、PID/start退出和单EDA资源释放仍按原合同取证，本审核不证明这些依赖已满足，也不承诺下轮布通。

## lean helper 身份桥接复核（2026-10-17）

原源码准备接受现适用于新 manifest `b049e0f6897d2c49e3a61154053023c6ca7216ed5d19fe2d89f68c96be7aa059`（10,047 B）。独立核对全部 34 项引用身份、8 个 E007 自有源与其余 15 个复用源均保持；唯一依赖变更为 lean runner 整文件从 `cdf4c9d8` 更新为 `00d39932`，五个实际导入 helper AST 及 canonical AST hash 逐项相同。CPU bridge `0fd8eb35`（8,315 B）与 producer `a9c56ea6` 已核；旧 `236718ab` manifest 原样归档。差异仅为该依赖身份、新 CPU bridge 引用及其出处，没有重审执行主体或重跑 59 selector 案例。

execution：有界独立桥接审核完成；verdict：原源准备审结仍适用；applicability：精确新 manifest，原生资格、实际集合/几何/cut/timing 和物理结果仍 NOT_RUN；review：内部审核通过，不增用户门。E006/R003 已实际加载 DCP，候选热点/失败端点适用性继续待该阶段闭合。桥接前本审结 MD/JSON 另存同目录 `_before_lean_helper_bridge`，早期问题与回执不覆盖。


## Optional property 与方向时序源修补（2026-10-17）

新 manifest `b54d7539d9715330ef80c3dec88d95476f1dfba27c6f63d680ba759379bc477b`（11499 B）的 37 身份引用已独立核验，见 [专项桥接复核](independent_property_and_directional_bridge_review.json)。B049→7f6→b54 两次变更限于 scalar 空值对齐、实际 IS_CLOCK/top 必要列及方向 cut 时序；六个其他自有源、七个 selector/REF/physical/resolve proc，以及 constrain/topology 体均保持。新 property helper 与 R004 实际归档相同；新方向选择 proc 逐字相同，当前 E007 的纯 Tcl 反例已独立重放通过。7f6 hooks 是逆补丁恢复且匹配旧 manifest 精确 bytes/SHA 的副本，不把重建说成原时刻已归档。

该结论仅接受探索对照入口的源码修补；原输入候选仍非默认首选，E007 原生资格、完整cut和implementation未运行。不得把旧银行/8DSP/no-BRAM等资格直接用于C01/C02。R004运行不依赖此复核。未重跑59项selector套件、未开EDA、未改生产树。
