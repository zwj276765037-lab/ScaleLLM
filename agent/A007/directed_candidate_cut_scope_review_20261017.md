# 候选完整有向边界：范围与采集规格提案

**判断：在下述原生资格成立时，可用于候选选型、候选相关跨 SLR 连接和现有 cap16 方向时序。它是新的覆盖范围，不等价于旧合同的“候选附着整网全部外部端点”。** 新 E006/R005 的 C01/C02 同图比较，以及 E008 pre-place/place/physopt/route 四阶段，应采用同一个 coverage version。当前 R004 正常运行及固定 E008 b59 源保持不动，本记录不启动实验、不授权停止，也不承诺提速或下一次布通。

execution：独立方法与规格审核 completed。verdict：数学边界成立；原生过滤/实际集合资格待执行。applicability：精确实际 S/P、完整 alias 和原生方向语义成立的同一设计点。review：A007 规格建议，供主控集中修订范围和 A006 新目录准备；不是已有采集通过或用户验收。

## 1. 精确对象与证明

令 I 为本阶段实际迁移组拥有的 native leaf pins，所属对象由 S/P 和实际物理父映射确定。leaf 的 OUT 是 DRIVER、IN 是 LOAD；top port 的 IN 是 DRIVER、OUT 是 LOAD。INOUT 及其他/空方向不强行定向。top ports 不属于迁移组，但全部保留。

对已解析唯一 driver d 的 canonical net n，完整有向边为 d→l，l 遍历该 net 的所有 LOAD。候选 cut 是成员关系不同的边：`inside(d) != inside(l)`。若 d 在组外，所有跨边界边恰为 d→组内 LOAD；组外→组外 LOAD 不属于 cut。若 d 在组内，全部组外 LOAD 必须取得；同网组内 LOAD 也保留，因而候选内部连接没有被削弱。

因此，允许缩减的唯一分支是：**完整原生角色查询证实恰好一个 driver，driver 在 I 外，无 INOUT、无方向/归属/连接资格未知，且 I 完整。** 此分支保留 I 的全部实际 leaf pins、所有实际 driver、全部 top ports，以及原 RAW 账本中需保留的非迁移常量等关联 pins。仅将其余已知组外 leaf LOAD 的完整 endpoint 记录标为 NOT_ENUMERATED。

常量 GND/VCC 的 RAW 归属与迁移成员关系分开：其 driver 即使名称在候选 root 内，也不能因此算作可迁移 S/P。常量 driver 和候选负载仍保留。原有候选非 leaf/父接口 pins 也保留在独立原始账本，不能拿它们替代真正 leaf pins。没有连接的候选 pin 明确记录，不从本地集合悄然删除。

## 2. 直接原生过滤：不得先取得百万 leaf 全集再裁剪

本次重新核对了本地 2025.2 API 文档：

- `doc/eng/man/common/list_property` 明确支持 `list_property -class pin`，返回指定对象类的属性。
- `doc/eng/man/common/list_property_value` 明确支持 `list_property_value DIRECTION -class pin`，返回该类枚举属性的合法值。
- `doc/eng/class/pin` 列出 built-in DIRECTION enum 和 IS_LEAF。
- `get_pins` 支持 `-leaf -of_objects <nets> -filter <expression>`；`filter` 文档明确：缺少被引用属性的对象不会被返回。

**资格门**：后继实际运行应先保存 pin class schema、DIRECTION enum 原生响应、实际工具版本及返回码，证明该 native pin 类具有此内建方向属性；核对实际候选 leaf 与随后返回对象的 NAME/DIRECTION 列支持、长度和值。不能用某一 REF/某个对象的抽样来声称所有 pin 的属性完备。若本工具版本不能提供此 class-level 保证、属性/API 不支持、返回异常或方向模型不一致，则该优化不获资格；回退完整范围或明确停止该采集为 unqualified。不要假定 `DIRECTION != IN` 会选中缺属性的对象。

在资格成立后，对原本完整的 `$segments` 对象集合直接执行：

```tcl
get_pins -leaf -of_objects $segments -filter {DIRECTION != IN}
get_ports -of_objects $segments
```

这仍使用全部 native segments，未把排序 canonical alias 换成单代表。第一条在原生命令内部筛选，返回全部 leaf OUT、INOUT 和其他/空的非 IN 值；不能只查询 OUT 后假设没有 INOUT/unknown。第二条完整保留 top ports，包含作为外部 peer LOAD 的 top OUT，成本小且保持 top 关联证据。

用于资格的命令应显式 catch 并记录错误，避免用 `-quiet` 的内部错误吞并语义把失败误写成有效空集合。返回对象逐项校验：OUT 记 driver，INOUT/空/其他值记 unresolved 并回退；若过滤返回 IN、列错位或对象身份不一致，记录异常并回退，不猜测。候选本地已知 OUT/INOUT/unknown pins 在此 net 的角色查询中必须全部出现；缺失则不能进入缩减分支。

driver 计数是去重后的 native leaf OUT 与 top IN 的并集；重复记录保留 raw count，同 NAME 不同角色直接视为异常。零 driver、多 driver、任意 INOUT 或角色未知都走原完整枚举路径。若唯一 driver 属于候选，也走完整枚举，保留全部内部及外部 LOAD。**已资格的唯一外 driver 分支不得再调用该 net 的无 filter 全 leaf 查询。** 原生实现内部是否仍遍历大量对象、成本是否降低尚未实测，不能承诺。

## 3. 完整候选 leaf 集合与 pin→net 对应

候选负载不从全网百万对象中事后挑选，而从本阶段受审实际 S/P 本地取得：

1. R005 使用当前 physopt 图的实际 C01/C02 S/P；E008 每个阶段使用该阶段 resolve/reconcile 后的实际 P。pre-place 允许正常 UNPLACED，place 以后仍要求实际 P 全部位于 SLR2。
2. 完整保留原 RAW/S/P、原生 NAME/REF、origin 与实际物理父证据。对于 DSP48E2 物理父，取得其真正 native primitive 子对象/leaf pins 并核实父映射；不能只使用父的非 leaf 接口。P 中位于 literal root 外的 native-origin copies 必须同样展开。root prefix、replica 后缀和历史 physopt 数量均不是证明。
3. 对每个实际 leaf owner 取得 native pins，保存 NAME、DIRECTION、native leaf 属性和实际 raw/physical owner。核对 local leaf 覆盖整个已解析 S/P；缺失父、未解释对象、未知归属或不支持的 API 使窄范围不获资格。对黑盒等实际 leaf 对象保留原生证据，不因不是惯常 FF/LUT 就删去；E008 原资源迁移资格仍单独约束其可接受性。
4. 建立本地 pin→native net→完整 alias group 的映射。首版可对每个候选 native pin 使用 `get_nets -of_objects <actual pin object>`，对已见 net segment 缓存 `get_nets -segments` 的完整集合；这是候选本地工作量，不请求外部 clock LOAD。可批取的映射优化由工程另证，不用推断的 pin 名或缓存旧阶段 net 对应代替。
5. 不连网、多个不一致 canonical group、非 leaf 原始 pin、RAW-only 常量关联分别记账。完整原始候选 pin 的附着 net universe 必须与旧定义对应；未知关联 net 回退完整范围或标失败。每个 native candidate leaf 在 retained ledger 中具有完整连接去向或明确 disconnected 状态。

上述映射使每个 net 的候选 LOAD 已知，省去全网 LOAD 的 NAME/REF/LOC/BEL/spatial/domain 读取。对保留的候选 leaf、driver、top ports 才获取完整必要属性。给 inside 打标必须依据实际 local leaf 集合/物理映射，不因为采集不到某个外部对象的细节就把它猜成 inside 或 outside。

## 4. 回退与 unknown 的界线

以下至少触发该 net 的原 all-segments 全 leaf 与全部 top 范围：零/多 driver，leaf 或 top INOUT，方向未知/空，class schema 未获资格，native query 错误，列对齐异常，candidate leaf/alias/物理归属不完整，原生角色查询遗漏本地已知非 LOAD pin。回退仍失败则明确 unqualified/failed，不能借缩减范围通过。

被保留端点的 REF_PIN 语义、IS_CLOCK、LOC/SLR 或时钟域若无法确定，要保留 UNKNOWN 并限制相应分类/物理结论，不按名字猜成数据或某个 SLR。若未知会影响 driver/inside 解析，则必须回退。仅为了省略的组外 peer LOAD 没有采集 REF/位置，本身属于声明过的未测范围；不能称该部分“没有 unknown”或“已完整分类”。

所有 clock/reset/constant 的候选端点和实际 driver 都保留，不以其高扇出为理由删除。原正式完整时钟、CDC/reset/IO、80 保护、全局 timing/DRC/route/资源和物理 POST 检查保持。

## 5. cap16 与跨 SLR 解释

- 已解析 ingress 的方向时序集合仍是该边界网的全部 inside LOAD；egress 仍是全部 outside LOAD，包含 top LOAD。与旧全网导出所得的这两个集合可以精确一致。实际命令继续保留 `-max_paths 16 -nworst 1`、max/min、查询对象列表及原生报告；不是 full-cut TNS。
- unresolved 网回退并保持单独 UNRESOLVED scope，不挪到 ingress/egress。没有边界的 internal 网不伪装成边界时序。
- 时序查询仍在完整未改的原生设计上计算，省略外部 peer 的导出不会从 timing engine 删除它们的电气负载。因而取得的路径延迟仍包含工具实际分析的完整设计影响。
- 完整保留所有涉及候选的 driver→load 连接及端点实际物理父/SLR，可计算这些连接当前是否跨 SLR。未知/未放置/top 的 SLR 单列，不补猜。clock/reset/constant/data/control/unknown 分开；一个逻辑连接或 pin 不是一个 SLL，也不等于活动流量或带宽。
- “全部候选 P 移至 SLR2、其余位置固定”的变化量仅是假设比较。实际完整 placement 可移动组外逻辑；新范围不能描述被省略 peer 的迁移、拥塞或外部→外部布线变化。全局原生报告仍负责全局结果。

## 6. 可用于选型的证据与明确放弃项

同一固定 DCP、相同 coverage version 的 C01/C02，可以比较：实际资源/控制集、热点与失败样本交集、site sharing、完整候选 ingress/egress fanout与端点分类、候选相关跨 SLR 连接、相同 cap16、SLR2实际容量及资格冲突。这足以支持“至多一个候选值得进入验证”的相对判断；不能证明一次布通。资源、热点、共享 site 等原查询不改，也不以 cut 数量单独选型。

新范围明确放弃：外来 driver 的全部组外 peer LOAD 名单、位置/SLR包络、REF/clock-domain分布、共享接收者聚类、全 canonical net 的全部端点/fanout/未知类别统计，以及依赖这些 peer 的外部→外部拥塞因果解释。若没有另一次范围明确的原生计数，也不能继续输出“完整 external fanout/leaf_pins/endpoint_total”。旧 R004 的全网总量不得与新 retained 数量同列当作同口径变化。

## 7. 输出契约与两条流程的适配

建议使用独立名称/目录及 `coverage_version=candidate_directed_cut_v1`，至少保存：

- actual stage/DCP/S/P/候选 leaf 集合身份；完整 aliases 和本地 pin→net 映射；原生 class schema与非 LOAD filter 命令/响应/返回码。
- 每 net 的 `scope_mode`：`RESOLVED_EXTERNAL_DRIVER_DIRECTED_CUT` 或 `FULL_ENUMERATION_FALLBACK`/`FULL_ENUMERATION_CANDIDATE_DRIVER`，以及明确 reason。
- 每条保留 endpoint 的 role、inside_RAW/S/P、原生 REF/clock/位置字段及 `retained_reason`；全部 top ports 保留。
- ingress 缩减网：`outside_peer_leaf_loads=NOT_ENUMERATED`，`full_native_leaf_count=NOT_MEASURED`，`exported_endpoint_rows=<实际行数>`；不以 0 表示未采。若将来另外有原生计数，须单列计数来源，不能冒充名单/位置齐全。
- `directed_boundary_complete`、`candidate_leaf_coverage_complete`、`native_role_gate_qualified` 与 `full_net_endpoint_coverage` 分开。前者只有全资格及所有 net 完整/合格回退后才可 true；缩减 net 的最后一项必须 false。
- cap16 expected/actual查询集合、fallback/unqualified网清单、保留端点分类总量。分类字段写成 retained/candidate-boundary scope，禁止沿用完整全网含义。

源码准备建议：在新目录复用 b59 的 exact membership、物理归一、origin、策略/几何、正式验收和单 EDA guard；将 cut 拆成 local candidate leaf+映射、class/role gate、选范围、保留端点富属性导出四步。不要在判定之前对 all-segments 无 filter 的全部 pins 执行 `ensure_cells` 或 `pin_columns`。调整 adapter 的 cut-summary、compliance、方向统计和 closed marker，使其验证新边界完整性且拒绝旧 full-net 字段的混用。

新 E006/R005 对两候选只做同图同口径比较；新 E008 从 pre-place 到 route 每阶段重新构建实际 local leaf/alias/role，不能跨 place/physopt 沿用过期对象和位置。R005 的切换、执行依赖和 E008 实际选择/来源绑定由主控登记；本建议不改当前 R004 的执行合同。b59 归档保留，新版本不得覆盖旧运行证据。

旧 UNION 全端点补采不是上述候选 cut 选型的必要条件。若主控调整未来范围而不再要求该探索项，必须明确记为未完成/不在新范围，不能记 completed。当前 R004 若仍正常推进，其已授权后续工作不因本提案自动取消；只有真实自然终态或另一次明确用户停止例外才能解除当前执行占用。

## 8. 证据与检验层级

纯 CPU 有限图检验覆盖 1–4 个端点、DRIVER/LOAD/INOUT/UNKNOWN、组内 leaf/组外 leaf/RAW-only leaf/top port，以及资格有/无，共 139808 例。513 例实际省略 peer LOAD；全部保留数学 cut、候选/RAW/top/unknown对象及原方向时序集合。见 [model check](directed_cut_scope_model_check_20261017.json)，SHA256 `50afacd78b65be93f614bab3a8cd19f32f656c7a01b5d46739363093400756c2`。这是显式前提下的图模型校验，不证明 Vivado API、当前候选 native leaf 完备性、实际提速或物理成功。

此前单 alias 替代 all-segments 的语义审核仍为 UNKNOWN，本协议没有采用那个替换。新协议的减少来自**原生方向过滤加实际候选本地集合**，不是丢弃候选时钟/复位/常量或降低正式验收。
