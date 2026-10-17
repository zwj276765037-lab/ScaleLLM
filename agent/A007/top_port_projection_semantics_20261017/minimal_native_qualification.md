# 完整 top-port 反向索引：最小可执行资格约束

本补充将[条件语义分析](review.md)收敛为工程可直接执行的自动资格与证据要求。它仅适用于另存的后继采集入口：原 b330/da34、当前 R005 进程和原始证据保持。若当前正常完成，优先现有结果并可继续原 da34。本规格不增加人工批准门、不改变候选或时序覆盖；普通实现修复连续进行，准备完成后集中核验受影响结果。

execution：规格准备完成。verdict：下列自动资格闭合时支持等价 top-port 投影。applicability：同一不可变设计阶段；原生实现与性能尚未测量。review：交 A006 实现与主控整合；不代表新包或实际物理结果已通过。

## 0. 对原获取方式条款的精确替代

主控将用集中补充及新 R006 身份区分本次 acquisition 协议；原 R005、原合同与审核记录原样保留。本规格仅替代[原详细审核](../directed_candidate_cut_scope_review_20261017.md)第 28–35 行所要求的逐候选网 `get_ports -of_objects $segments` 以及原 validator 每网必须存在 ALL_TOP_PORTS 原生命令收据的获取方式条款。新的真实来源是完整端口库存、逐端口全部附着网/segments、端口网组全量原生互查和逐候选 TOP_PORT_INDEX_JOIN 的闭合链。

原 scope 合同“top ports 完整取得”、原详细审核全部 top ports 保留、未知/INOUT 保留、完整候选 directed boundary 和方向时序覆盖要求完全不减。`coverage_version=candidate_directed_cut_v1` 继续标记相同逻辑覆盖；另以 `acquisition_mode` 和 `top_port_reverse_index_v1` 明确原生获取方式改变，不能称为执行过旧命令。即使该网因方向未知而做 full-leaf fallback，全部 top ports 仍可来自已合格索引，不需要伪装成重新做了旧逐网 top 查询；索引未合格时不能使用其残缺结果。

原详细审核第 35 行“成本小”是先前设计估计，本次不沿用为实测事实。当前只准备后继包；若 R005 仍正常，切换需要该次单独停止许可及具体已核准备包，并由唯一执行者先完成真实收尾。本规格和 R006 登记本身不提供停止或启动授权。

## 1. 同一设计阶段与对象上下文

索引绑定 `native_tool / input_identity / stage / point / design_identity / epoch_id / current_instance`。每个 E008 pre-place、place、physopt、route 独立重建；A006 选择 R005 C01/C02 也各自建索引，可简化身份。设计变更、重载或阶段变化使索引失效。相同 port 名字和父 DCP 不能证明 epoch 相同。

本地 2025.2 手册明确：`current_instance .` 才是只读获取上下文；无参数 `current_instance` 会重置到 top，top 返回空字符串，并不是设计对象。最小实现对 `current_instance .` 记录实际命令/code/result 并要求 top 空值。非空时拒绝本阶段索引；不在采集器里默改 scope。若入口本来明确设置 top，可记录其真实 reset，再用 `.` 确认。原始 current_design 身份另存。

所有原生调用都有 BEGIN/END、实际参数、返回码、错误/选项和完整结果或可完整恢复的结果文件引用；不可使用会掩盖内部错误的 `-quiet`。没有 END 只表示未闭合，不是空结果。

## 2. 完整原生端口库存 P

执行无过滤、无 `-scoped_to_current_instance`、无 `-prop_thru_buffers` 的默认 `get_ports`。保存返回对象总数、完整 NAME 顺序、对象→NAME 对应及唯一性。不得改用 package pins、IOBANK、时钟端口或名字前缀筛选。

- 原生 `list_property -class port` 与 DIRECTION 枚举证据单列。NAME、CLASS、DIRECTION 是核心字段；CLASS 必须为实际 port，NAME 空缺、重名身份冲突或向量错位拒绝资格。
- 对每个实际对象保留 DIRECTION 原值。IN、OUT、INOUT、MIXED、UNKNOWN 与成功空值均在库存中；属性调用失败单列，不能改写成成功空值。
- 最小观察字段为 BUS_NAME、BUS_START、BUS_STOP、BUS_WIDTH、BUS_DIRECTION、UNCONNECTED。仅按原生 schema 支持情况读取，分别记录 `VALUE / EMPTY / UNSUPPORTED / QUERY_ERROR`。这些字段不用于筛掉对象；缺少可选属性本身不证明端口缺失。
- 保留实际 bus bit、bus 容器及 secondary 对象，绝不按 BUS_WIDTH 手造位名、不因 BUS_NAME 空值推断 primary/secondary、不自行合并或丢弃。对象宇宙是否与旧全 segments 查询一致，由第 4 项全量原生互查判定。
- 序列化用 Tcl list/字典的原生 parser；不拆空白、不按 glob 重新获取 `data[0]` 等名字。真实调用传原生 handles，完整名称仅作证据与精确集合键。

## 3. 每端口全部连接与完整 segments

对 P 中每个 p 执行一次真实 `get_nets -of_objects $p`，保存全部直接网 A(p)，不能只保留一个或仅保存所有 ports 的邻接 union。每个唯一原生网取完整 `get_nets -segments $n`，保存 handles 与一一对齐的全部 NAME、真实命令和闭包来源。已取得的同 epoch 完整闭包可按精确身份复用，但复用必须指向第一次真实查询；不是伪造另一次执行。

每个闭包必须非空、含所请求网，NAME 唯一且数量对齐。任意两已取得闭包相交时必须全集合相等，不能只比较 canonical。canonical 只是完整集合的确定性标签。缓存同一对象/alias 的完整 tuple 可避免重复属性查询，不得只留 count/hash/canonical。

每个 p 保存完整 `T(p)=union(C(n), n in A(p))` 的可恢复引用。空 A(p) 且查询成功单列 DISCONNECTED；UNCONNECTED 若提供了相反明确值则拒绝资格。查询失败不等于空。多直接网/多闭包全部保留，不挑选首个；只有对象/连接无法解释时拒绝，不因 multiplicity 本身删除数据。

端口索引的 alias 字典必须与候选 `directedGroups` 分离，或用明确的候选键集合隔离导出。索引收集的无关端口网不得进入候选 canonical universe、cut、端点或 timing scope。共享元数据缓存不等于扩大候选范围。

## 4. 完整互查自动关闭 bus/secondary 口径疑点

对端口实际附着的每个唯一完整闭包 C，各执行一次真实 `get_ports -of_objects $full_C_handles`。保存完整实际参数、返回 NAME/DIRECTION、身份与数量。要求：

`native_ports(C) == {p in P | T(p) intersects C}`

比较完整精确对象身份集合，并核对其属性与 P 一致。每个返回对象必须存在于 P，所有 P→C 关系必须被原生反查返回，且不得多出无正向关系的对象。不是抽样，也不能用 native count 相等代替集合相等。bus/secondary 在该设计中的实际表示由这些完整关系原样保留；若产生不同表示而不能精确等同，则当前索引资格失败，不能编造转换。

该反查只覆盖端口真实附着的唯一网组。它不要求对数万个候选网逐一执行旧查询；无 top port 的候选网在完整 P、全部 A(p) 与闭包互查均闭合后，通过不相交得到空集合。端口数为零可以是成功空全集，但必须有实际 get_ports 成功收据、空邻接/闭包/互查账本和闭合身份，不能从文件缺失推断。

不能通过 buffer、clock-source、all_fanin 或其他逻辑传播补入端口。候选内部 BUFG 输出与外部 clock port 是否同一电气网，只由原生完整 segments 决定。

## 5. 候选投影与既有方向/时序语义

对原本候选本地映射形成的每个完整 S，取所有与 S 相交的端口闭包。相交闭包必须等于 S，否则拒绝；按完整原生身份去重后得到 Q(S)。每个 candidate S 必须恰有一个 JOIN 记录，包括成功空投影。不能用单个任意 alias、canonical 前缀或 port 名字推定相交。

TOP_PORT：IN→DRIVER、OUT→LOAD；INOUT、MIXED、UNKNOWN、成功空值原样保留。后四种触发现有 unresolved/full-leaf fallback 规则；它们是端点语义，不能当作可丢弃端口。完整身份/邻接不确定、属性读取失败或闭包失败属于资格错误，另行拒绝。

候选 outgoing 的全部 top LOAD 继续进入原 EGRESS timing 集合；INGRESS 为全部候选 LOAD。原生完整图、max/min cap16、native non-IN 库存、唯一 driver 资格、outside peer LOAD 缩减条件及既有 full-leaf fallback 均保持。新索引不改变 `coverage_version=candidate_directed_cut_v1`，仅改变 acquisition mode。不能声称 full net endpoint coverage 或正式时序签核范围扩大。

## 6. 最小证据 schema 与 validator 行为

以下是逻辑记录类型；A006 可合并为少量 Tcl-list 文件，但必须能完整恢复并独立验证。

| 类型 | 必需内容 |
| --- | --- |
| INDEX_CONTEXT | `schema_version=top_port_reverse_index_v1`、epoch/stage/point/design/input/source 身份、实际 current_instance 和 port schema 响应 |
| PORT_UNIVERSE | 真实默认 get_ports 命令、code、完整原生对象 NAME/CLASS/DIRECTION 与可选属性的值/状态 |
| PORT_ATTACHED_NETS | 每个 P 恰一条，真实 p 参数与 get_nets 响应、全部 net NAME、DISCONNECTED/CONNECTED/MULTIGROUP 状态 |
| PORT_ALIAS_CLOSURE | 每个唯一完整闭包的真实产生查询、全部 NAME/对象对应、所请求 net、后续复用引用 |
| PORT_GROUP_RECIPROCITY | 每个端口附着唯一闭包恰一条真实 get_ports full-segments 响应，全部实际参数和返回端口；与正向映射全集等价检查 |
| INDEX_CLOSED | 所有前置文件的大小/SHA、行数与集合闭合核验、资格布尔值及问题；全部文件正常关闭后产生 |
| TOP_PORT_INDEX_JOIN | 每个原候选 canonical 恰一条，`acquisition_mode=NATIVE_PORT_REVERSE_INDEX_V1`、index/epoch 身份、完整 candidate aliases 或可恢复引用、实际纯索引 join 操作、返回 port NAME/DIRECTION、引用的闭包/互查证据 |

JOIN 是纯投影操作：可以记录真实 Tcl join 命令及其 Tcl 结果码，但不可把它标为执行了原生 `get_ports -of_objects $candidate_segments`，不可伪造原 ALL_TOP_PORTS 收据，也不可把纯计算码称为 native_tcl_code。新 `query_kind=TOP_PORT_INDEX_JOIN` 与原 ALL_TOP_PORTS 分流验证。若使用一个通用 `command` 字段，必须同时标 `execution_kind=PURE_PROJECTION`。

validator 必须从完整 P、每个 A(p)、所有闭包和全部互查重算投影与方向，验证每条实际命令的完整参数，不能仅相信 `qualified=true`、count/hash、预计算 Q 或重复的 `actual_segment_NAMES` 字段。候选 aliases 全集仍由原候选本地映射证据绑定。actual-query 参数与旁边完整列表不一致必须拒绝，保留此前 F01 反例防线。

第 1–4 项任一完整性失败：索引不得发布合格结果。A006 本次选择直接拒绝本阶段，保留原包供明确新尝试回退，是合格的最小实现。若以后同阶段实现回退，必须完整执行旧逐候选 full-segments top-port 查询、记录 `NATIVE_PER_NET_FULL_SEGMENTS` 与失败原因，并由 validator 独立闭合旧路径；不得把残缺索引输出与旧路径混成无标记成功。回退也失败则该阶段失败。以上均为自动资格/普通修复，不是人工审批。

## 7. 一次集中验证与性能边界

工程准备的必要验证是实际完整 collector+validator 组合的正例及有区分力反例：漏一个 bus/secondary port、漏一个 A(p)、缺 alias、重名/错位、闭包相交不相等、原生互查漏/多返回、disconnected 矛盾、字面 UNKNOWN 被删、索引跨 epoch、候选范围被端口网扩入、伪造 ALL_TOP_PORTS 命令。它们是同一受影响路径的集中核验，不为每项设置审核停点。原方向与 timing 测试继续验证 top OUT 的 EGRESS 保留。

原 9472 incidence/alias 模型比较与 36 方向组合仅作已完成数学依据，不重跑冒充新 native 资格。原生性能未知；端口网组反查仍可能昂贵。BEGIN/END 应区分 get_ports、port 元数据、get_nets、segments、互查与纯 join，以真实测量解释成本。任何正常进程不因墙钟/无输出强停。
