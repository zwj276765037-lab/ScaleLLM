# C-A1：单read_addr结构下的实际副本机制

2026-10-18；A007；响应Root具体架构核点。execution：相关生产RTL有界只读核查完成；verdict：多计数器并不自动形成多URAM消费簇，需要明确真实连接；applicability：core与resident当前源；review：设计条件，不是方案选入或实现验证。

当前core只向`u_meta.rd_addr`传入一个17bit `meta_read_addr_r`；resident在第29行定义单个256bit `meta_mem[0:DEPTH-1]`，第74–78行只有一个同步读表达式`rsp_meta_r <= meta_mem[rd_addr]`。原counter还驱动core的有效范围判断及response tile/group标签。**若保留该单索引读结构，多放几份等价counter不会自然把不同URAM簇接到不同副本。** 只有实际接入该索引的一份有内存地址负载；其他份若无读者会消失，等价寄存器/逻辑也可能被合并。单靠DONT_TOUCH或pblock保留多份对象不创造独立消费连接。

可以区分三种机制，不能混写收益：

1. **单memory-side副本。** 保留core原counter服务标签/控制，另一个同沿副本只接resident的全部读地址消费者。它可与C-A2深度银行独立实施，真实变化是把core非memory读者与memory读者分开；仍由一组17bit地址承担整个原存储的读地址扇出，不能称作不同URAM簇各有副本。F1须证明这些读者的实际分离和跨度差异，F3计副本更新逻辑及全控制成本，F4限定其保存/放置机制；否则可能只有面积增加。
2. **多个真实读地址消费结构。** 必须在RTL存储组织中让各消费簇各自有可区分的地址引用，并定义同沿采样/数据拼接。逻辑上不必是C-A2深度银行，也可能是有实际证据的宽度划分等，但这已是必须明文冻结的结构决定，不能暗藏在“地址副本”中。具体分区/份数、URAM映射、写端接入、响应汇聚、collision/stall语义和资源预算均待设计；本审核未选入任何新银行数。
3. **精确综合网表复制并重连。** 保留RTL单array亦可能在新图上按真实URAM地址pin拆分fanout，但必须有合法且可复验的复制/重连实现、完整属性/时钟/复位/CE语义、实际pin覆盖和检查器。它是设计网表变换，不是只加一个摆放约束；当前没有这套实现或原生资格证据，不能假定普通overlay自动完成。

对于任何选定路线，F1需要逐位“原driver→原读者集合；新driver→精确新读者集合”，并明确原counter的core标签用途保留；F2证明有效URAM采样沿`local_addr==original_addr`，严格保持async reset、外层system_clear、launch与后置meta_rsp_fire的NBA顺序；datapath_clear含abort不能替代地址事件。`local<=original`增加一拍不合格。F3计D端、加法/选择、CE/reset/clock、请求有效逻辑和响应路径成本；F4/G4分别明确禁止不当合并的最小范围、实际消费者和新图物理资格。

因此：**C-A1不是逻辑上必然依赖C-A2；但“多个URAM消费簇各由本地副本驱动”的强机制在现单读索引结构下尚未成立。** 可选择缩小为单memory-side副本的实证机制，或明确能够产生独立read-address消费者的结构/网表变换；Root需在G2选定，不能等到长implementation中再决定。A006已收到同一核点，正在从既有导出提取实际地址位/URAM/逻辑读者；不为此新增EDA。
