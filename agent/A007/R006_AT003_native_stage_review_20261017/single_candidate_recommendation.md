# E008 单候选独立审核：选择 C01

**建议本轮仅将 C01 的 `g_row_branch[1].u_branch_leaf` 迁往 SLR2，按已授权 E008 合同开展一次完整 implementation。** 现有实测支持它是两候选中更值得验证的热点卸载方案；不承诺一次布通或时序收敛。由 Root 绑定已接受的 `3cae179e3af5e831bcfd5030a2751b0b0c8b734d7c159a29d359ed2055dd4496` E008 入口，A006 执行，不新增批准门。

准确候选根：`scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_swiglu/g_row_branch[1].u_branch_leaf`。

| 同图比较 | C01：本轮推荐 | C02：本轮不选择 |
|---|---:|---:|
| 热点 S 成员交集（复用 R004） | 8697 | 2303 |
| 全部原位于 SLR1 的 P（复用 R004） | 9491 | 7257 |
| 普通已定位边界逻辑对，假设候选迁 SLR2、组外固定 | 7124 | 12235 |
| 完整入口／出口 LOAD 时序集合 | 20534 / 945 | 16103 / 3222 |
| 有界入口／出口 setup 最差 slack，ns | +1.416 / +1.848 | +2.537 / +2.537 |
| 有界入口／出口 hold 最差 slack，ns | −0.128 / +0.035 | −0.055 / −0.027 |
| 原生 LUT / FF（复用 R004） | 1890 / 6317 | 3348 / 3557 |
| DSP / RAMB36 / MUXF7 / MUXF8（复用 R004） | 2 / 6 / 816 / 384 | 0 / 0 / 0 / 0 |

C01 覆盖的热点成员约为 C02 的 3.78 倍，普通边界逻辑对少 41.8%。这里的“普通”仅排除 clock/reset/constant 类，保留 mixed/unknown 语义；它们是有向逻辑连接对，不是 SLL 导线、带宽或路由拥塞实测。C01 的 6144 条数据边界对来自 projection_repack 的 3072 个输入网；出口共 945 对，其中 896 对接 row-ring BRAM。其余控制与 sibling branch 耦合仍须由实现处理，不能称为物理独立模块。

C02 的普通入口 9572 对、普通出口 2663 对。入口分别有 3241 对来自 down_scheduler、5638 对来自 w4_frontend 的两个 half、620 对来自 join；出口有 1716 对进入 gate_scheduler、513 对进入 half0、208 对进入 shared_compute。多数 LUT/BRAM 管脚落入 mixed/unknown 分类，不能把没有 known_data 分类解释成没有数据跨区成本。C02 与原 40 条失败样本中 3 条真实别名相交，C01 为 0；这只是有限样本关系，不是全部拥塞因果证明。C02 较好的当前 setup 裕量、较简单的专用块需求均已计入权衡；其热点覆盖较少且普通跨区边界更多，因此本轮不选它。

主要风险仍是 SLR2 现有 CLB 占用 93.07%、C01 的 MUX/DSP/BRAM 打包要求、−0.128 ns 入口 hold，以及 setup 最坏路径超过 94% 的网络延迟。两候选大部分源 CLB 与组外共享，不能承诺释放全部触及站点。以上时序是原 E005 physopt 图的有界 `-through` 查询，每方向 max/min 各上限 16、nworst 1；未测完整 cut TNS，不是迁移后或 route 后签核。路径起终点可均在组外或组内，查询依据是穿过完整边界 LOAD 集合。

E008 唯一变量维持候选根 → hard、nonexclusive、non-routing-contained 的 SLR2 Pblock。保留 RTL/IP/ABI、Hadamard、ScaleCode、format 05、时钟和原保护约束；真实入口中的成员／物理父／origin／祖先和约束资格检查、完整 place → physopt → route 与签核均继续现有合同。资格不成立应按真实失败记录，不能清除保护或偷偷换候选。

执行：R006/AT003 六阶段与十一查询 native0，2026-10-17T04:45:04.960209Z 自然结束，native0/supervisor0，无 stop、无 cleanup。独立复核 231 个非 DCP 身份，包括 144 个生产输入、12 个 runtime 源、44 个外部绑定和 30 个复用输入；12 个原 PID/start 身份已消失，观察时 `/proc/locks` 无该 lane 记录。DCP 内容哈希归属工程收尾验证，审核者没有读取或哈希 DCP。后续实际获取单 EDA lane 由 A006 负责。

判断：支持 **C01 单变量物理实验**；C02 的未选择不构成方法反驳。适用范围：原 E005 physopt 图的 R004 资源与 R006/AT003 完整候选 cut、有界时序；实际优化有效性和全局收敛由 E008 结果判断。审核：候选证据及 AT003 自然收尾接受，无新增准备或用户批准停点。

证据：[C02 实际 cut/timing 重放与成本明细](C02_cut_timing_review.json)、[C01 cut](C01_cut_review.json)、[C01 timing](C01_timing_review.json)、[原始资源与容量复核](../R005_python_environment_review_20261017/candidate_policy_capacity_existing_evidence.json)、[自然终态审核](natural_terminal_review.json)。C02 使用原归档 cut/join/timing 算法重放，结果与工程 native_result 完全相等；仅在审核进程中以 DCP-safe wrapper 替代内容读取，闭合标记、点／epoch、来源、原始账本和 DCP 绑定均独立核对。
