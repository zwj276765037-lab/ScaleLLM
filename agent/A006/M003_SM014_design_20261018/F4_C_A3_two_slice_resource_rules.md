# F4：C-A3两片128位资源分派建议（G2待审）

2026-10-18，A006。工程建议，不是Root选型。仅使用E009已关闭导出，未新载DCP、未改生产。依据：[80块原对象](F4_full_metadata_inventory.json)、[原生池与原占用](F4_C_A3_resource_pool_inventory.json)。提取脚本均exit0并完成hash核验；site是原生关系，下面的池是新设计分派规则，不冒充原lane/cascade。

| 新逻辑片 | 原数据位/深度 | 独占计数的URAM候选池 | 池的全部native CR | 原图占用 | 地址FF/加法/选通的邻近CLB池 |
| --- | --- | --- | --- | --- | --- |
| 0 | [127:0]，81920 | URAM288_X3Y80:Y119，40个实际site | X4Y5=16、X4Y6=16、X4Y7=8 | 20个现meta、20个原生未占、0其他owner | X4Y5/X4Y6中的实际SLICE_X112..141Y300..419，3480个site |
| 1 | [255:128]，81920 | URAM288_X3Y120:Y159，40个实际site | X4Y7=8、X4Y8=16、X4Y9=16 | 40个现meta、0其他owner | X4Y8/X4Y9中的实际SLICE_X112..141Y480..599，3480个site |

两URAM池按逐site集合交集为空；两个CLB池也互斥。CR X4Y7虽然出现两次，其16个URAM site按Y112..119与Y120..127各8个分开，没有重复容量。原80块中60块已在上述X3列，20块在X1/X2；新布局把这20块转入X3原未占20位，算术上不挤出他模块的URAM。SLR1原生320个位、当前248个已占；这个全局余量不是本方案兼容性的替代证据。原未占site也不等于新macro一定可放。

## 具体约束及局部性规则

1. 各片40个URAM实体各加入一个**hard、非独占、非routing-contained**的存储pblock，仅列该片的40个URAM site；两片互斥，不固定单个LOC/BEL，不复用旧URAM序号。新图必须按该片数组原点和真实物理父归并级联子原语，不能用名字推测bit-lane。若工具需要合法级联的多个原生segment，允许片内跨上述三个CR，禁止越出该池或借另一片site；不强行规定旧20级cascade形状。
2. 每片17位独立地址状态及其增量、CE/zero-select逻辑放入该片CLB池：hard、非独占、非routing-contained；不固定单个LOC/BEL。所需只有17位新FF和一个17位独立增量锥，CLB位集是原生候选空间；3480是名义slice数，**不是已测兼容空槽**。新综合/G4须核FF控制集合、CARRY8合法连续位置、宏/祖先约束和IP保留区域交集。不能清理DONT_TOUCH或硬保护取得空间。
3. 内存允许同片跨CR、同一X3物理列内移动；禁止跨URAM列/SLR。每片地址Q至该片全部URAM地址根的clock-region纵向跨度最多2个CR索引（例如5到7，或7到9），横向CR号均X4。各片17位Q的**URAM地址消费者**只属于自己片，不能同时驱动另一片的任一URAM地址输入；自身increment反馈等必要本地逻辑可以读取Q。不能把两个局部计数器综合为同一根。
4. 原公共`rd_fire/wr_fire/rd_port_open_r/rsp_valid_r`、read/write/error计数各一份。本版公共控制器、响应寄存器和响应汇聚**自由合法放置，不施加新soft或hard pblock，不施加CR偏好**；不能复制整个resident。写地址仍广播全部片，写数据按原位序分发；这部分和返回拼接仍可能有长线，完整物理报告必须实测，不声称已经本地化。
5. `rsp_meta_r`按两片各128位同沿写，直接按原位序拼接。其逻辑位数256不变，不增加输出流水或深度bank mux。原输出寄存器能否继续映入URAM/附近FF由新图查验；不得隐含多一拍换级联便利。

## G4不可绕过的反证

- 实际总数必须80 URAM、每片40；未知/跨片归属、ADDR根共源、无负载副本、任一位不覆盖、不兼容macro立即使该机制未通过。preplace核新图对象/成员、约束交集及原生资源资格，不要求尚未布局的新图有LOC；place、physopt、route及相应恢复后才实核LOC、超池和CR跨度。
- 新两组地址寄存器必须各17个存活FF，async reset和事件优先级相同；逐pin映射证明每片URAM实际用自己的Q，原core地址Q不再驱动这两片URAM地址引脚。保护属性只用于34个地址FF/必要层次，不能全设计DONT_TOUCH。
- 每片URAM直接地址根的数量/最大扇出、Q→地址根跨度、FF D锥/CE/clear/clock负载与原12根/17位/204pin行基准并列报告。预期每片约6根是待验证预测，不是旧图lane推导。若未形成更小消费域或仅把长线移到D端，否定局部化收益，不能以计数器数量通过。
- 池或CARRY/控制集合不兼容时，先在SM017停于物理入口，不放宽到全SLR或自动改片数。需要改变池/片数/外部周期则回Root重新冻结；正常工具运行不墙钟强停。
- 缺失旧完整lane/cascade不是本新图分片所必需；新图原生cascade、RDW模式、宏、保护及打包必须G4闭合。现阶段没有必须先新采旧DCP的字段。

## C01配套建议

建议本轮**明确保留旧C01 hard-SLR2策略**，在新M003 overlay重建同一角色范围，不消费旧被拒XDC。C01完整根为`u_mlp/u_serial_command/u_gate_scheduler/u_swiglu/g_row_branch[1].u_branch_leaf`；当前9491物理成员、6 RAMB36+2 DSP及25个DONT_TOUCH按[A007实证](../../A007/M003_SM014_review_20261018/F4_and_G2_preparation.md)核验。它与`u_shared_compute/u_branch1`不同；后者151527/−2.896ns不作为撤销前者的依据。

理由：M2不增加payload FF且A3只占SLR1内存既有/空site，二者均不依赖把C01退回SLR1；现无完整cut TNS或SLL证据支持改变旧卸载，保持这一变量可减少联合变化。风险仍是SLR2原CLB很满；保留不表示证明其最优。新图按原点/角色重建C01物理成员并核祖先约束，不机械要求9491；不得清掉25个保护或固定旧hardblock LOC。Root可据联合审核决定不同策略，工程不得静默变更。
