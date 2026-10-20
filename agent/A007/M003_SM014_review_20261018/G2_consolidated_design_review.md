# SM014 / G2 联合设计独立审核

2026-10-18，A007 `/root/m002_physical_architecture_review`。工程包为 A006 `design_delivery_manifest.json`，SHA256 `6d74e85db325a939c8b1ffbd637de6dbd35e2016188bdd0050d62cc5a2b9706b`。

**结论：建议 Root 将 C-M2、C-A3、C-P1（明确保留 C01 hard-SLR2）冻结为同一 M003 版本，C-M1、C-A1、C-A2、C-R1 deferred。未发现阻塞本版 G2 设计冻结的核心未决项。** 正式 selected/deferred 和 G2 决定由 Root 登记，随后按已有授权推进 SM015–SM017；本审核不新增用户批准门，不把后续 RTL/新综合/物理要求提前记为通过。

| 记录维度 | 本次结论 |
| --- | --- |
| execution | 独立设计审核、方程检查、最终身份绑定 completed |
| verdict | DESIGN_APPLICABILITY_ACCEPTED_FOR_ROOT_G2_FREEZE |
| applicability | 仅适用于本 manifest 的 81 区域 CE buffer、两 128-bit 同深度 metadata slice 及明确 C01 策略；不适用于旧 27 逻辑组原型或隐含新增候选 |
| review | A007 independent completed；Root 正式 G2 和用户结果审核均不由本文件代替 |

## 绑定与证据强度

[最终绑定](G2_final_binding_check.json)实际工具 chunk `68f2e3`、exit 0：34 个设计文件共 59,139,703 B 全部与冻结 manifest 的大小/SHA256 一致。执行回执 chunk `7b224a`、exit 0 的输出绑定同一 manifest 与 CPU 收据；144 条输入身份记录逐项等于 E009 baseline 元数据。实际 144 生产输入重哈希由 A006 执行，A007此次只复核记录及 finalizer 源码，不冒充再次读取生产输入。

已独立重建精确组/位/区域关系，核原生 sites 与 80 URAM 小表，审查大表提取算法及其原始输入身份；没有重复扫描 445/115/269 MB 原生大表，没有载入/读取/哈希 DCP、生产改动、信号或锁操作。以前的 G1 限定审核及原始运行记录保持。

冻结包的 `finalization_cpu_receipt.started_utc=0` 是非阻塞收据瑕疵：finalizer 将保存 UTC 的 `start` 变量复用于分组偏移循环。该字段不能作实际开始时间；保留原件，不倒填。`observed_utc`、实际 exit、文件身份及原生执行回执仍分别可用。早期小辅助进程没有留存的 affinity 收据也不事后虚构。A006 所见 EDA 锁空闲仅归因于其实际观察，A007未操作锁。

最终 F4 已删除公共控制/响应的 soft 区域偏好，明确自由合法放置；preplace 对象/约束资格与 place 后 LOC 检查已分开。整合计划与合同一致：SM016 负责检查实现、必要正负对照和联合回归；SM017 才做新综合与 G4 原生实核。正式 overlay 名为 `project/hardware/vivado/constraints/m003_joint_locality.xdc`，漏 overlay、空匹配、错误数量/资源/身份、硬冲突、保护丢失及恢复后失效等负例均已列入。

## 本版候选与可证伪机制

| 候选 | 独立建议及冻结内容 | 必须在后续证伪的条件 |
| --- | --- | --- |
| C-M2 | 生产 TILE_W=9：head 42、tail 39，共 81 个 LUT1 INIT=2；原 13,120 FF 按实际 SLR/CR、bit 顺序、每组至多 256 分组。每 CR 一个 hard、非独占、非 routing-contained pblock。原数据 D/Q、两 entry、branch ingress 和无宽 reset 语义不变。 | 真实 CE pin 必须恰好覆盖；master 仅驱动 42/39 个 buffer 输入；禁止直连旁路、合并、D mux 代替 CE；place 后 buffer/FF 同原 CR/SLR。 |
| C-A3 | `[127:0]`、`[255:128]` 两片，各深 81,920、40 URAM；一份控制器/256-bit 响应。两份独立同沿 17-bit helper 保留 core 原地址状态，生产显式启用 LOCAL_ADDR_COPIES=1，legacy 默认 0。 | 各片实际从自己的 17 Q 读地址；无共根、无闲置副本、无额外拍；同址读写旧值、同沿拼接/标签/反压与原语义一致；新图 40+40、cascade/RDW/物理父/宏及兼容打包必须闭合。 |
| C-P1 | 正式新 overlay 明确保留 C01 hard-SLR2，重新按角色/原点解析成员和保护；SSI_SpreadSLLs / Default / Default；无增量 DCP、无 seed 扫描。 | 不消费旧被拒 XDC，不清保护，不固定旧单 site，不把旧 9,491 成员数写死成新图数量；每阶段/恢复后核真实生效。 |
| C-M1 | deferred；完整双银行增加 3,456 FF/clock，每 entry 增加 1,728 CE 负载；私有字段原已有单读者，head 搬移可能把 Q 长线移到 D。 | 当前无足够相抵收益，不隐含加入 M2。 |
| C-A1 / C-A2 | deferred；单副本仍有原直接根，深度 bank 增加选择及 256-bit 返回汇聚，缺少相应具体物理/时序支撑。 | 不叠加到 A3；deferred 不是已证明方法无效。 |
| C-R1 | deferred；未形成有具体证据支持的位精确算术变换。 | Hadamard、ScaleCode、format05 及现有数值/周期合同保持。 |

C01 完整根为 `u_mlp/u_serial_command/u_gate_scheduler/u_swiglu/g_row_branch[1].u_branch_leaf`，不同于 TOP01 的 `u_mlp/u_serial_command/u_shared_compute/u_branch1`。旧 C01 9,491 物理成员均在 SLR2、6 RAMB36/2 DSP、25 个 DONT_TOUCH，hard pblock 为 CLOCKREGION_X0Y10:X5Y14；直接 LOC/BEL 未固定。不能将直接属性为空扩展为任意祖先无约束。保留 C01 是本版明确的受控选择，未证明其最优。

## 语义、资源和物理预算

[M2 独立方程检查](M2_equation_check.json)真实完成 256 个状态/布尔/数据组合和 2 个 LUT1 真值，精确 CE/D 方程匹配原 case；满 FIFO 当拍 pop 不给输入 credit，reset/clear 只清占用、payload 保持。该检查不是未来 RTL 仿真。

[A3 独立 LUT 检查](A3_LUT_equation_check.json)真实完成全部 1,048,576 个 17-bit 旧状态 × S/L/R 组合：`CE=S|L|R`、`INC=R&&!S`、`D=INC?(old_local+1):0`、`local'=CE?D:old_local`，对应原最终 NBA 优先级。L+R 同沿递增旧值；S 为 system_clear，不能以含 abort 的 datapath_clear 代替；Q 接读不推进地址，禁止 `local<=original` 多打一拍。A006 另有 30,000 存储模型周期、1,083 同址旧值及 3,343 stall 情况检查，仍不等于未来 RTL 或原生 URAM RDW 证明。原最小请求间隔为 2 clock 周期，不宣称吞吐提升。

M2 增加 81 LUT1、0 FF/clock/reset；潜在 CE/control set 从 2 到 81，即 +79。A3 精确新增 34 地址 FF/CLK/异步 CLR pin、两个独立 17-bit increment、4 个保护控制 LUT，预算新增 LUT≤96、CARRY8≤8、FF≤34，URAM 总 80 且各片 40。联合预算新增 LUT≤177、CARRY8≤8、FF=34，URAM/BRAM/DSP 增量 0；85 个显式保护 LUT，已知局部 control-set 增量上限 +81。全局实测资源和控制集合去重须另报。

| A3 片 | URAM 实际池及 CR | 地址 FF/增量/控制 CLB 池 |
| --- | --- | --- |
| 0 | X3Y80..119；X4Y5=16、Y6=16、Y7=8 | X4Y5/Y6，SLICE X112..141 Y300..419，3,480 实际 sites |
| 1 | X3Y120..159；X4Y7=8、Y8=16、Y9=16 | X4Y8/Y9，SLICE X112..141 Y480..599，3,480 实际 sites |

两片 URAM/CLB 集合均不相交；Y7 的两份 8-site 不重复计数。两池合计 60 个旧 metadata 占位加 20 个旧未占位，其他 owner 为 0；原 X1/X2 的 20 个迁往 X3。所有 CR X=4，地址 Q 到其片 URAM 的纵向 CR 差最多 2；独立 hard、非独占、非 routing-contained 存储与地址池，不作单 LOC/BEL 锁定。3,480 是名义 sites，绝非兼容空槽保证。公共控制/响应自由合法放置，写地址/enable/响应长线的成本必须新图实测。

## 剩余实测风险及冻结资格

**TOP01 的 −2.896 ns branch1 clear→rdata 代表路径没有被 M2/A3 直接处理。** 这是本联合版本的剩余实测风险，不能写成已修复、等同 C01 或以候选数量遮蔽。该事实不阻塞本版完整 M003 的 G2 设计冻结：合同允许按实证集中选取/推迟候选，G2 冻结语义、成本和策略，而非预先证明每个热点都已消失。后续同一版本必须复核 TOP01 同角色控制/数据路径及新的最坏路径；它可能继续限制时序/布线，若失败按真实结果处置，不宣称下一次必成功。

其他残余风险为：M2 多一级 LUT 延迟、master→81 buffers 长线、额外 control sets 造成打包碎片及 hard CR 限制；A3 单列级联/宏兼容性、写控制与返回汇聚长线；原 SLR2 高 CLB 占用与 C01 拥塞；全设计可能出现新热点。结构存活不是物理收益，CE 扇出降低不是时序收敛。

E009 canonical 569,597 与报告 547,548 的差 22,049 仍 OPEN，本结论不依赖二者集合相同，不因此重开 EDA。旧固定网集 head D/Q/CE 完整，tail Q/CE 完整但 tail D 缺失；meta Q/CLR 完整但 D/CE 缺失；所有 C pin 未导出。它们不阻塞本版设计方程与不变 D 连接判断；G4 须查新图实际 D/Q/CE/reset/clock。旧 17 地址 Q 的 251 读者为 204 个 URAM pin 加 47 logic，12 个直接 URAM 根不等于全 80 块；旧逻辑 lane/cascade 未测也不冒充已知，新图闭合即可。

SM015/SM016 的生产参数逐周期/位精确回归和检查正负对照、SM017 的新综合预算/消费者/原点/宏/硬约束/80 保护资格，以及 SM018 的真实位置、完整 route、setup/hold/PW/DRC/CDC/reset/IO/bus-skew 和原 +0.5 ns 目标均独立验收。G4 不相容时停于入口并报告 Root，不暗中扩池、改片数、降预算或清保护；正常工具不设墙钟/静默强停。上述后续验收不构成要求 G2 等待未来产物的循环。

工程包、G1 和本次细项审核的全部历史证据保留。本次无实际 RTL 修改、综合、place/route 或功能实现通过声明。
