# 顶层端口全集反向连接索引：有界语义审核

结论：对同一不可变设计阶段，**完整端口全集 × 每端口完整连接网/segments** 的反向索引，可以条件性证明与逐候选网 `get_ports -of_objects $segments` 等价。现有本地API文档支持所需连接关系，但尚无本项目该索引的原生完整性、bus对象口径或性能证据，因此当前不是已合格的直接替换。**已核完整segments的NAME元数据可在同阶段缓存复用**，保留相同完整列表和调用证据即可，不必改变端点覆盖。

当前R005保持正常运行，本审核不改scope/源码、不发EDA查询或停止信号。已知NONLOAD查询约0.502s结束；随后没有ALL_TOP_PORTS收据，只能定位在get_ports、端口NAME/DIRECTION、去重及segments NAME等语句之间，不能认定具体慢API。该时间为主控提供的实际观察，本审核未重测。

## 等价条件与证明

设P为当前设计的完整原生port对象集合；A(p)是`get_nets -of_objects $p`返回的全部直接连接网；C(n)是每个网经原生`-segments`取得的完整别名等价类；S是当前候选某网的完整segments集合。建立 `T(p)=union{C(n): n in A(p)}`，按精确原生NAME/对象身份计算 `Q(S)={p in P: T(p)与S相交}`。

当正反两个API描述同一连接关系、P完整且S及C均为同一阶段完整闭包时：直接查询返回的端口必有一个连接网处于S，所以其T与S相交；反之T与S相交意味着某直接连接网的完整别名类与S重合，因此它确实连接该候选网。这是连接关系的转置及集合求交，不依赖端口方向，也不跨buffer或逻辑单元。

本地2025.2文档锚点：[get_ports](../E008_get_pins_semantics_review_20261017/man_get_ports.txt)4–5行默认全部设计ports，67–74行连接指定nets、要求原生对象；[get_nets](../E008_get_pins_semantics_review_20261017/man_get_nets.txt)89–96行连接指定ports，113–116行segments覆盖全部层级。文档没有直接给出bus容器与bit对象的反向等价保证；[port类](class_port.txt)同时描述primary/secondary ports和BUS_*属性，故必须保留并资格化真实对象口径。9472个完整incidence/alias模型比较及36个方向组合相等；七类违反条件的反例已列入[纯CPU模型](../top_port_projection_model_20261017.json)。这不替代原生资格。

## 必须保留的原生资格与证据

1. 在同一个完整design、同一阶段、明确current_instance语境下，执行无方向过滤的完整`get_ports`枚举；不用IOBANK/package-pin数量或候选port采样代替全集，不加`-scoped_to_current_instance`/`-prop_thru_buffers`。保存真实命令、返回码、对象/NAME唯一性及schema；原生关键查询不能用quiet掩盖内部错误。
2. 按实际port对象保存CLASS、NAME、DIRECTION及可用BUS_*／UNCONNECTED信息。`data[0]`和`data[1]`是不同原生身份，Tcl list按原生parser解析，不用glob、前缀、拆空白或手造bus位名。若枚举含bus容器、secondary对象或别名，要原生证明其与原逐网API的返回对象宇宙一致；不能自行丢弃、展开或合并。无法解释则映射资格未通过。
3. 每个port逐一绑定其完整直接net集合，再对不同net取得完整segments闭包；批量get_nets仅返回union会丢失port→net关联，不能单独作为证据。所有空连接、多连接、bus多个canonical组均单列；多个关联不能只留一个canonical。成功空连接可记录disconnected，可用UNCONNECTED交叉核对，矛盾/查询失败不当成空。
4. 端口侧闭包与候选侧完整segments必须以精确身份一致；两个闭包一旦相交却不相等、重复NAME冲突、缺alias或未知映射，应显式未合格。不可只比较任意canonical代表名，也不可用parent_net、top_net或同一clock对象代替完整电气网别名。外部clock端口与BUFG输出属于不同网时，不通过buffer传播或all_fanin补入。
5. 全部top ports均作为outside端点保留：IN→DRIVER、OUT→LOAD、INOUT保留；空/MIXED/UNKNOWN方向也保留并触发原有未解析/完整回退规则。方向未知不影响连接集合求交的完整性，但影响后续唯一driver资格。候选输出网的全部top LOAD仍进入EGRESS时序集合，cap16与原生完整图时序查询不变。
6. 全球索引须保存port全集、每port直接网映射、每别名组完整成员与来源、disconnected/multigroup/unknown账本，以及每候选网求交所用身份。闭合检查须覆盖全部枚举ports而非抽样。少量正反API对照可证伪错误，不能单独证明全图完整；充分依据是完整对象口径、无遗漏的反向映射和闭包一致性。原生对象模型若仍不能解释，保留逐网查询或明确未合格。
7. 每阶段重建或有严格相同设计epoch证据才能复用：R005同一只读图的C01/C02可共享；E008 pre-place、place、physopt、route之间不得仅凭相同port名字或父DCP身份沿用旧索引。复制、改名、连接变化均使缓存失效。
8. 新索引不能伪造旧`ALL_TOP_PORTS command=get_ports -of_objects ...`已执行收据。未来准备应明确记录实际采集模式、完整上游索引身份和每网join依据，并由validator核查；只有覆盖等价证据闭合时，逻辑candidate_directed_cut_v1口径才保持。当前scope及固定源不修改。

## 可独立采用的segments元数据缓存

当前`directed_alias`已经取得完整native segments及NAME，随后alias导出、NONLOAD收据、ALL_TOP_PORTS收据和可能的FULL_LEAF收据又读取同一批NAME。在同阶段无图变更时，可一次保存 **原生handles ↔ 完整NAME列表 ↔ canonical**，后续用该不可变记录填入原有完整`actual_segment_NAMES`字段，仍保存实际query参数。这样减少重复native属性查询，原始证据内容无需压缩或换schema。

必须在第一次获取时验证数量、唯一性和对应关系，并标明后续来源为该完整冻结记录；不能改为只保存count/hash/canonical而丢掉alias集合。若未来想连重复输出也去掉，需另加可完整恢复的身份引用及validator引用闭合，不能用“索引引用存在”掩盖实际命令只用了一个alias（此前F01类缺陷）。同理，已取得port NAME/DIRECTION也可在本阶段复用，但需保存原生handles及同一来源，不将cached值说成重新查询。

该缓存收益不等于当前慢点已定位。全集索引减少逐候选网get_ports调用次数，但新增全集端口邻接与alias闭包成本，可能仍有大clock组；没有原生测量前不承诺加速、内存下降或布通改善。未来准备可分别记录GET_PORTS、PORT_NAME、PORT_DIRECTION、去重、SEGMENT_NAME的起止，以明确瓶颈；不在当前运行中插入或热改。
