# C01/C02：已有成员证据支持的选型前置要点

此页复用同一 E005 physopt 图的 R004 原生资源和 AT002 新生成员账本。AT002 账本已独立离线逐字段核对，原查询失败状态保持；尚未选择候选，仍等待真实 cut 和有界时序。[完整统计与原始身份](candidate_policy_capacity_existing_evidence.json)。

| 已测项目 | C01：SwiGLU 8-row 分支 | C02：Down weight repack |
|---|---:|---:|
| 全部位于 SLR1 的实际 P | 9491 | 7257 |
| 原生 LUT / FF | 1890 / 6317 | 3348 / 3557 |
| DSP48E2 / RAMB36 / URAM | 2 / 6 / 0 | 0 / 0 / 0 |
| 原生 MUXF7 / MUXF8 | 816 / 384 | 0 / 0 |
| 原生 unique control sets | 36 | 32 |
| 热点 S 成员交集 | 8697（91.48%） | 2303（31.73%） |
| 当前触及 CLB／与组外共享／仅本候选 | 1788 / 1776 / 12 | 1347 / 1339 / 8 |

物理父已核：C01 的 16 个 DSP 内部子对象映射到 2 个真实 DSP48E2 父对象，6 个 RAMB36 保留；C02 无 DSP 父归一。不能从 RAW 行数推定 LUT、DSP 或迁移负载。两候选 RAW/P 不相交；表中资源来自 R004 原生 exact-hierarchy 报告，不是本次新测。

保护属性已核：两组 P 的 IS_LOC_FIXED/IS_BEL_FIXED 全为0，USER_SLR_ASSIGNMENT、RLOC、RLOC_ORIGIN、MACRO_NAME 和导出的 actual_PBLOCKS 均为空。C01 有25个 DONT_TOUCH=1：clear_local_r_reg（FDPE）和24个 gate/up capture LUT1；C02 有24个 DONT_TOUCH=1：12列各一组 out/tail write-enable LUT1。必须保留这些控制保护，DONT_TOUCH 本身不等于固定位置。C01另有40个非空 ORIG_CELL_NAME，值为局部 issue_element 寄存器名；不能据此推定根外复制或完整原始对象对应。C02该字段全空。

现有数据没有完整导出候选祖先、继承 Pblock 或组外 macro 搭档，因此空字段仅描述已测 P，不能判“无祖先/宏约束”。E008仍需在真实 pre-place 图重建 RAW/S/P、DSP父与 native-origin 对应，核祖先/硬约束、macro搭档、专用资源及80项保护，不得清除旧约束来制造资格。

SLR2当前原生利用率为 CLB93.07%、LUT54.22%、FF32.63%、BRAM tile44.65%、DSP76.97%、URAM60.00%。LUT/FF等总量有余裕，但CLB站点已很满；C01增加DSP/BRAM与MUX打包要求，C02原生LUT更多、专用块要求较少。两者绝大多数源CLB与组外共享，不能宣称迁移会直接释放1788或1347个CLB，也不能将“当前仅本候选”当保证释放数。实际 hard、nonexclusive、non-routing-contained SLR2 Pblock仍须原生读回完整几何/资源范围，并在新布局检查全部P落区、未放置/未知/丢失对象。

现阶段只支持上述风险比较：C01热点交集更大，C02专用资源要求更少；完整入向/出向连接、控制代价、当前有界setup/hold证据及新实际资格尚不能由资源表替代。全局资源比例不证明打包或布通，不作一次成功承诺。
