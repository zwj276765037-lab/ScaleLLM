# A007：AT018 snapshot 纯源码成本核查

本次为不阻塞 AT018 的源级辅助审核。只读取当前 m003_joint_checks.tcl：30,835 B，SHA256 6e2e0343a43d3c429725e7da5367727b7c395c6757202c4e45f6ad16883e935d。未运行 Tcl、CPU 测试或 EDA，未读/哈希 DCP，未查询进程、原生日志、输出目录或资源状态，未修改生产源。

结论：源码确有重复层次查询、逐对象共享 net 查询、重叠 fan-in 遍历和整包证据保留路径；没有发现 Tcl 自递归、遍历同一输出列表同时扩张它的循环，或正常路径持续累积打开文件的机制。原生 API 是否做全图扫描、缓存或保留内部 collection，无法从 Tcl 源码确定。下列项是可检验的成本候选，不能定位当前执行语句、证明卡死、解释 A006 报告的 RSS 数值，或证明 snapshot 修复已通过。正常原生运行继续，本审核不增加 G4 门。

源码位置均指 [checks6e2e](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/hardware/vivado/scripts/m003_joint_checks.tcl:341)。

| 路径与源码位置 | 确定的源级事实 | 可检验的成本边界 |
| --- | --- | --- |
| resolve：162–207、snapshot_body：343–344 | resolve 每次在165清空 resolved，再重建角色；不命中已有结果返回。正常路径含4个 one 根身份查询、payload/buffer/original-address各1个过滤查询、meta与C01各1个 primitive_scope，共9次 get_cells -hier 调用，另加条件成立时的 DSP 祖先查询。 | -hier/-filter 是面向当前设计的层次查询，结果被名称/资源条件筛选；原生实现是否完整扫描全设计未知。snapshot 若到达344，会再执行一次解析，而不是复用两次已完成 apply 的解析结果。 |
| primitive_scope / physical：87–107 | root 含首个“[”时先截短 broad，再通过 prefix 恢复精确范围；每个被纳入的 DSP 子 primitive 可沿祖先逐级调用 one。最终 lsort -unique 在映射之后。 | 更宽的中间候选可能包含同族兄弟层次；多个 DSP 子 primitive 的共同祖先查询无缓存。最终去重不消除之前的重复查询。此机制与已审 AT017 apply 源级路径一致，此处只指出 snapshot resolve 会再进入它。 |
| payload：348–359 | 按冻结配置 P=13,120。每 FF 固定查询5个端口，再各重查一次 D/Q，再作 D driver/Q load 的2次 leaf 查询；成功走完整段时为9P=118,080次 get_pins 调用。get_nets 为每 FF 2+k 次，其中 k 是5个端口中返回非空 pin 的数量，0≤k≤5。 | 这是静态调用计数，不是本次原生已执行次数或复杂度。D/Q 的 pin 与 net 查询重复；C、CE、R 的共享信号也逐 FF 使用 -segments 并保存返回的完整 NAME 值。没有在此 FF 循环内显式调用 get_cells -hier；不能据此断言这些 API 内部一定是局部 O(1)。 |
| cell_row：321–332 | 每行一次 list_property，随后11个 supported_prop 复用该支持列表；NAME/REF另取，PBLOCKS查询一次。LOC为空时跳过站点/SLR/CR查询。固定角色部分有17+13120+81+34+80=13,332次 cell_row，另加其他 helper 和 C01 行。 | 已修的“每属性重复枚举 list_property”没有在 cell_row 回归。每对象一次枚举仍可能是大量调用；placed 情形额外站点查询会增加成本。不能将13,332乘11当作 list_property 调用数。 |
| buffers/master：362–374 | 每个 buffer O 导出所有 leaf load，并逐 pin 取 owner。每个 group 又查询 I0 所在 master net 的 driver 与完整 load 列表。 | 若当前实际图满足冻结的 head42/tail39共享 master 连接，同一 head 列表会导出42次、tail导出39次，合计42²+39²=3,285个 load 名称出现；这是条件下的重复输出量，不是本次实测连通性。 |
| address / URAM fan-in：377–409 | 34个 address D 各调用一次 all_fanin -flat -startpoints_only。80个 URAM 的每个 ADDR* 输入再各调用一次，非ADDR不调用；无同 cone/endpoint 缓存、深度限制或模块边界限制。 | 总调用数为34+A，A是当前实际枚举到的 URAM ADDR* 输入数，源码不能给出 A 的原生值。重叠 cone 可被重复遍历；-startpoints_only限制返回端点种类，不代表遍历成本或结果大小有常数上界。这不是 timing path 枚举。 |
| helper/memory/pblock/site：391–448 | helper 输入与选中的 memory 输入逐 pin查询 net/driver；URAM每个 cell_row后另做一次完整 list_property 清单并逐属性取值。pblock的4个 prop各自再次 list_property；actual_sites与target_sites分开采集。 | URAM完整清单是每cell额外一次，不是每属性再枚举。共享输入/net与相同站点集合存在重复采集/输出可能。C01目标使用整个SLR2站点集合，大小需实际数据，不能据源码填数字。 |
| 证据累积 / JSON：344、346–460、305–311、464–467 | cells/edges/inputs/pins/controller/pblocks/target_sites/helper_pins/configs/boundaries等在函数开头初始化并一直保留；jobject生成字段串，jarray生成每行编码串列表再join，465再组装整个JSON作为puts参数。 | 峰值可同时含原生设计、角色映射、全部行、编码中间串和最终文本。具体倍数由Tcl对象共享/复制及native collection实现决定，不能简单按每个变量数翻倍。保持当前schema必然保留重复字段的输出字节；单靠查询缓存不会消除它们。 |
| 文件与输出时序：411–418、464–482 | 正常路径每个URAM属性文件在该cell循环内打开后关闭；最后JSON打开、一次puts、关闭，再调用Python验证。异常wrapper保存原errorinfo/errorcode并重抛，不循环重试。 | 正常路径不是同时打开80个URAM文件。若属性读取/写入或JSON编码在open之后抛错，缺finally可能留下当前handle至退出，但源码不支持“正常循环持续泄漏全部handle”的结论。异常仍保留原错误。 |

缓存必须以单次 snapshot 的固定设计视图为边界：

- 最稳妥的是 snapshot 入口新建、退出丢弃的局部 dict。现有 namespace cache 仅在第8行初始化，在此文件没有其他使用；resolved每次清空重建，ancestor_pblocks仅供apply使用并在267重置，snapshot不利用它。
- pin/net的完整实际NAME可以作为键的一部分，不能用叶名、截短层次、预期组号或单纯器件PART代替对象身份。还需区分 -segments、-leaf、-flat、过滤条件、方向及实际输入对象集合。不得为提高命中率静默排序/去重输出；顺序、重复项和所有现有拒空/错误语义必须保持。
- 同一pin的重复查询可先按精确pin身份复用。跨FF共享C/CE/R的复用，必须先保留每个实际pin到实际net/segment的映射证据，不能用冻结设计“应该相连”代替原生观测。不同层次的net别名或segment不能未经等价核验合并为一个键。构造共享键本身也可能需要查询。
- 任何 open_run/open_checkpoint/link/restore/close 改变当前设计或对象生命周期后都不可复用旧handle；即便NAME相同也可能是新对象。OPT/physopt、ECO、debug插入、复制/合并/常量化等可改变 pin/net/fan-in。placement/routing、overlay/约束变化还可能改变LOC/BEL/PBLOCK/固定属性等字段。采用每snapshot清空可保守覆盖跨phase失效；不能按“源码未改”或“NAME没变”跨snapshot/OPT复用。
- 缓存只减少重复API调用及部分NAME转换。各JSON row仍包含原有完整字段，最终序列化重复字节仍在；Tcl可能共享缓存值引用，也可能因类型转换/编码产生副本，需实测。缓存键和值本身亦占内存，低复用率的逐pin缓存可能增加峰值。流式写出或去重schema属于另外的实现变化，不能由本次静态核查直接采用或降低完整性要求。

关于集合生命周期，局部nets、fanin、startpoints、refs、config等在各自迭代中重设/覆盖，输出列表只遍历源集合后追加；没有自己递归嵌套自己，也未把新追加的输出重新作为同一循环输入。global resolved只保存当前角色图，ancestor_pblocks保留最近一次apply的祖先缓存但不会被snapshot追加。上述“没有显式无限增长路径”不排除有限但巨大的重复返回集、原生缓存或工具内部问题。

若后续真实错误栈或新的冻结诊断允许验证，应按实际落点区分候选，而不是由当前静默选择结论：

| 实际栈落点 | 后续可检验的量；须保留原验收 |
| --- | --- |
| 353/357/358：payload pin/net | 单次返回的segment/driver/load数、完整NAME字节量、同实际net映射的重复次数、一次查询与下一次查询的耗时/结果等价。保持13,120全覆盖和D/Q原拒空。 |
| 379/406：all_fanin | 精确endpoint、返回startpoint数、重复cone比例、输出字节量；核ADDR拒空和全部本地状态/连接要求，不截断cone充作完整证据。 |
| 323/413/47：属性枚举 | 对象身份、支持列表长度、该调用是否返回、后续逐属性读的耗时。不得把长耗时等同挂死或盲删必需属性。 |
| 103/41：层次/DSP解析 | broad与最终精确范围的候选数量、DSP子primitive到共同父对象的复用次数；保留实际归属、去重和兼容性守卫。 |
| 465：序列化 | 行数、各字段/数组编码字节量、编码前后资源样本；分开看数据采集与编码峰值，完整schema与验收保持。 |

没有 URAM 部分文件的观察，至多说明观察时尚未看到第411行之后的文件产物，无法唯一定位到resolve、payload、buffer、address/helper、第一URAM的pin查询或其他前置步骤。总JSON到464才打开；wrapper错误栈到捕获错误后才写。缺这些文件既不是修复成功证据，也不是当前确切调用位置证据。本次不读取这些运行产物，完全沿用A006提供的带时点观察，不作新的实时判断。

execution：本静态辅助审核 completed；verdict：仅源级成本/缓存失效候选，原生原因未评定；applicability：checks6e2e；review：真实消息发A006/Root后另记送达。AT018真实图/预算/终态、restore与严格G4继续以原生产物和独立审核为准。
