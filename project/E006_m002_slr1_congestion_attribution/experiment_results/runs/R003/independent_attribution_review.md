# E006/R003 实际归因独立审核

## 首批设备映射（2026-10-17）

已独立核验5个真实query0及原始绑定，open_checkpoint耗时566秒；工具2025.2、器件xcvu9p-flga2104-2L-e、blackboxes=0。10个失败节点的tile和node原字串逐项对应原失败route日志；本次原生GRID X/Y均与原日志前两坐标数值一致（并非据名字推算），10份已绑定NW tile集合的成员关系独立复算均吻合。

9个样本tile在SLR1，NODE06 `INT_X74Y716/NN4_W_BEG4` 在SLR2。只有NODE10 `INT_X37Y469/INT_NODE_GLOBAL_12_INT_OUT0` 位于十峰窗UNION，分别命中NW001–007及NW009；其余9个无成员，与此前CPU tile交集一致。详见[独立事实](independent_initial_device_mapping_review.json)。

execution：这5个query审核完成，完整failure_samples尚未闭合；verdict：设备映射成立，十峰窗只覆盖10个失败tile样本中的1个；applicability：工具选择的top10节点及每个实际列出的4个net，不外推全部失败分布；review：独立部分阶段审核。

这限制了“十峰窗代表全部布线失败”的解释。窗外不等于无拥塞；NODE06在SLR2也不能单独反驳候选。NODE09的NET034输入写使能已在原日志中列出，但实际候选端点与跨区关系仍等failure_samples闭合，不能由net名称或tile归属直接推断。候选热点交集与连接适用性待后续真实阶段。


## 已闭合热点与失败样本的候选判读（2026-10-17）

[独立原始交集](independent_candidate_raw_intersections.json)来自单次有界流式核查的 30.9 MB UNION 与 2.71 MB failure endpoint 文件；没有重扫 676 MB 全设计 primitive 导出。[一致性与身份桥接复核](independent_closed_stage_consistency_and_helper_bridge_review.json)进一步核对工程闭合 stage facts、精确源身份和下述关键计数。

十窗去重 UNION 为 103313 个 primitive，全部在 SLR1；MLP 79277、Attention 10986、DDR1 4462、weight_loader 3021、interconnect_other 3004、core_other 1664、weight_metadata 889、debug 10。原生热点利用率没有查询，primitive/BEL/站点指标不能写成 native LUT 总数。MLP 的主要热点子项包括 shared_compute/u_branch1 40327、gate/u_swiglu 13224、gate/u_projection_repack 7873 和 down/u_weight_repack 2303；这些观察用于选择下一诊断范围，不直接证明迁移收益。

原输入前端候选在 UNION 仅有 1042 个非恒量 primitive（约 1.01%）：796 FF、186 raw logic LUT、30 CARRY8、20 MUXF7、10 MUXF8，触及 310 个 SLICE。完整候选此前的 13230 个 touched site 中 12254 与候选外逻辑共享，976 exclusive；touched sites 不能当作全部可释放 CLB。

40 个精确失败样本字符串解析为 40 个独立 canonical net，全部有单 primitive driver；4877 个端点为 40 drivers + 4837 loads，其中 657 loads 位于 UNION。43 个已知跨 SLR loads 属于 4 条 DDR0→Attention 网络，与原输入候选无关。REF-aware分类含 2778 enable loads、1672 逻辑功能未分类、344 UNKNOWN_REF_PIN、30 register data、12 arithmetic data、1 logic primitive；IS_CLOCK 没有查询，未知逻辑 pin 不能因名字推断为 payload/clock/reset。

原输入候选仅命中 NET013、NET025、NET034 三条网，分别是 input_beat_write_enable[40]、input_buffer_row_r[12][255]_i_1_n_0、input_beat_write_enable[31]。三网各有 1 LUT driver 和 256 FDRE.CE loads，共 771 个候选内部端点，全部在 SLR1，没有候选外端点或未知 parent；三网在 UNION 的端点交集为 7、7、9。这说明样本含分散的局部 CE 路径，不能支持“输入候选边界是主要全局瓶颈”或“迁走能修复主要热点”的结论。

主控通过真实消息决定将原输入候选降为探索对照，当前不作为下一完整 implementation 默认首选。此为主控依据闭合证据作出的排序决定，不伪装成新用户原话，也不将 E007 已接受的历史源码准备审核撤销为失败。E007 原生资格及物理收益仍未运行/未验证。

## 查询异常与 helper 身份闭合

R003 hotspot_connections 因 `Selected cell property alignment differs` 失败；当时传入 ensure_cell_data 的首批是 9 个对象（VCC、SYNC_reg、iSYNC_WORD_reg[0..6]），涉及 debug 的 const1 网络。哪一列导致异常尚未由原生 probe 证明，不能直接写成已定位 LOC 或 REF_NAME。UNION net locations/endpoints 当时均为 0 bytes，不能当成完整连接导出。工程已将空值对齐风险纳入新通用 helper 和 R004 probe；E007 同类假设也需要源修补并重绑，不能从旧准备审核推导修补已通过。

工程 terminal_summary 报告 R003 自然 1/1、无 stop/cleanup/survivor、输入身份保持、lane 已释放；本节仅引用工程终态，不冒称 A007 已完成整套 terminal 独立重审。已闭合 failure_samples、hotspot_ownership 与 exact_hierarchy_resources 的 query0 仍可按各自覆盖使用。工具退出失败不反驳候选方法。

candidate facts 原来绑定 mutable helper 路径的 18021-byte / `ffe74c6a...` 版本，当前 helper 后来改为 18429-byte / `93283e41...`。A007 已核工程归档桥接：旧源码原尺寸/完整 SHA 匹配，旧/新 `refined_class` AST 逐字相同（canonical AST SHA `8341c5d87ed825a0fc4b4ca2d2368d701ea05e47cb3e1c9ae21d12119c92a7a0`），原 candidate facts 未改。归档桥接使旧分类来源可复现，不能据此称 mutable path 从未变化。

## R004 两个独立候选的最小区分采集

权威 [R004 targets](../R004/independent_candidate_targets.json) 固定 C01 为 SwiGLU `g_row_branch[1].u_branch_leaf`，C02 为 Down `u_weight_repack`，literal 根下 primitive descendants；C01/C02 分开采集和评判，不能拼盘。三个 RTL 权威源已另核与 E005 冻结清单一致，未改 RTL。

C01 旧 UNION 有 8697 primitive，输出是 32-bit product 与 12/3/5-bit 标签、握手/状态，但输入仍有 3072-bit payload。独立完整资源、实际切口和失败样本关系尚待采集；不能把整个 SwiGLU/quantizer 的失败关系转嫁给 producer1。C02 旧 UNION 有 2303 primitive，旧全图 7260 行中 7257 在 SLR1、3 未放置；原 raw LUT/FF 为 3688/3557、touched sites 1347，均不是 native 合计。NET001 的 1144 loads 中只有 576 在 repack，其余 512 在 w4_frontend/u_half0、56 在 join；NET037/038 各 143 loads 是内部控制关联。C02 输入 2048+224 位、输出 1536+168 位的源接口意味着两侧 cut 都需要实测，不能靠逻辑规模较小推断低跨 SLR 代价。

R004 在原 physopt DCP 上测各自 RAW/S/P、实际 DSP/存储映射、native root×SLR资源、固定/Pblock/SLR/RLOC 约束、全部 attached canonical nets 的 IN/OUT/INOUT/top endpoints，以及 incoming/outgoing 的 min/max 各 cap16 条当前时序路径；原 UNION 连接修复覆盖保持。未知项明确保留，source bit/net/pin 不换算成 SLL。SLR2 的总资源余量仅为必要条件，其 93.07% occupied CLB 仍使共享 packing 和控制集成为约束。两候选 `candidate_supported=false`，待同图闭合后择一或说明二者不能迁移的原因。

execution：有界 CPU 原始交集、一致性和身份审核完成；R004 native 待执行。verdict：局部资源/样本关系可复核，主瓶颈因果与迁移收益仍 inconclusive。applicability：固定 E005 physopt、十峰窗与 40 失败样本；原 legacy IN/OUT 覆盖不等于完整候选 cut。review：独立阶段报告，非用户最终验收。
