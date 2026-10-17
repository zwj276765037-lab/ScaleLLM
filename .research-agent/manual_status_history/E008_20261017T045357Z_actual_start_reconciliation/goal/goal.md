# ScaleLLM：项目目标与硬件-软件对齐规范

> 最新工作：R004两候选资源已闭合并按本次用户例外受控收尾，旧完整cut/时序/UNION未完成。R005的owner和Python环境问题已修复；AT003于北京时间09:51:16真实启动，原生载图前环境预检通过，继续C01/C02有向边界比较。新implementation尚未启动。[当前实测](../project/E006_m002_slr1_congestion_attribution/experiment_results/summary.md)。

> 后继授权：用户明确要求定向优化后开启下一轮implementation；原SM011/E007输入前端候选与入口保留为探索对照。当前按[有向cut范围修订](../mission/M002_ddr_separation_and_timing_recovery/directed_candidate_cut_scope_revision_2026-10-17.md)选择下一实现范围；[SM012/E008原合同](../mission/M002_ddr_separation_and_timing_recovery/exact_hotspot_offload_implementation_contract_2026-10-17.md)其余正式验收保持。新口径1d612c65共通入口已准备并独立核查，同类环境适配同步处理，候选未选择，尚无新implementation。

> 当前阶段（2026-10-16）：E005优化后的完整implementation及补采已全部结束，合法布通失败：1148579重叠路由节点、758463拥塞失败信号，失败DCP和诊断已保存。局部功能通过，新综合及完整place/physopt流程完成；布线前setup改善，hold仍失败。R006两批只读补采均自然成功、独立复核完成，144冻结输入与原检查点保持。整体执行failed、方法判断inconclusive，用户结果审核未记录；M002全局目标未完成。[E005当前结果](../project/E005_m002_optimized_implementation/experiment_results/summary.md)。本次依据[SM009合同](../mission/M002_ddr_separation_and_timing_recovery/optimized_implementation_contract_2026-10-16.md)，正常进程无墙钟/无输出强停；算法、数值、ABI、双DDR和时钟保持。

E003已结束基线：150项CPU与实际图/来源验证通过；新的完整place POST已经关闭此前CDC代表源适配问题，结构/fanout及内部时钟覆盖通过，8条CDC限定分类、新未分类0。正式安全仍OPEN；完整physopt POST通过，但正式时序FAIL。实际route已因拥塞/节点重叠自然失败，最终routed产物未取得，本轮结束。

## 核心使命

在 Xilinx VCU118（xcvu9p-flga2104-2L-e）FPGA 上实现 **Llama-3.1-8B-Instruct** 的高效推理加速。

**交付物不是代码或综合 PASS，而是：**
- 算法正确、可实现、可部署、可测量的完整硬件-软件系统
- 从 Host CPU 到 FPGA Attention + MLP 加速再回 Host 的真实闭环推理
- 精确可验证的端到端数值一致性与性能测量

### 历史资源与性能记录（不作为 M002 当前测量）

**Total DSP48E2：** 5451 个（来自 Vivado 综合报告）
- MLP 阵列：~3072 DSP（Shared Gate/Up 1536 + Dedicated Down 1536）
- Attention 阵列：~2400 DSP
- 理论算力：1090 GOPS @ 100 MHz

**DDR4 配置：**
- DDR0: 2 GiB, 64-bit @ 200 MHz UI = 1.6 GB/s 理论 / 1.36 GB/s 实际
- DDR1: 2 GiB, 64-bit @ 200 MHz UI = 1.6 GB/s 理论 / 1.36 GB/s 实际

**性能瓶颈分析（关键发现）：**
- DDR 带宽：58-65% 时间（主要瓶颈）
- DSP 计算：35-42% 时间
- 结论：DDR 是瓶颈，不是计算算力

---

## 硬件-软件对齐原则（强制性）

**本项目建立一个不可逾越的对齐边界：**

> **硬件实现必须准确对应软件算法的每一个细节。硬件不得偏离软件设计。任何硬件创新、优化或"简化"都需要先通过软件数值验证，反向工程写入软件双胞胎（twin），然后重新验证整体 ACC/PPL。未经软件批准的硬件偏差视为功能缺陷，不是"设计选择"。**

### 对齐检查表

| 维度 | 软件权威来源 | 硬件实现文件 | 对齐状态 | 验证义务 |
|---|---|---|---|---|
| **量化配置** | `01_final_scalecode_algorithm.md` | `hap_a8w4_slice8x12_group_s37.sv` | ✓ 完全对齐 | 功能仿真无数值偏差 |
| **Hadamard 变换** | `v5_fullchain.py::_fwht32_int` | `design.md` 5 级蝴蝶+乘 11585+除 65536 | ✓ 完全对齐 | RTL 仿真对比数值 |
| **Gate/Up 数值** | `v5_fullchain.py` S37/S44/S24 | `hap_a8w4_slice8x12_group_s37.sv` | ✓ 完全对齐 | 无溢出计数，PPL 通过 |
| **SwiGLU 符号扩展** | `ScaleLLM_MLP_Down_S32_fix_handoff.md` §2.1 | `hap_mlp_silu_mul.sv:123-124` `{{8{lane[23]}}, lane}` | ✓ 已实现 | 对比 MLP-only 输出 |
| **Down-S32 修改** | `fix_handoff.md` §3 冻结合同 | `hap_mlp_down_group_major_accum_s54.sv` | ✓ 已实现 | 无饱和、无格式错误、无溢出 |
| **Down 输出格式** | S32/F16 修复 | CSR 0x2AC Down saturation 计数 | ✓ 已承诺 | 验证计数为 0 |
| **Attention 完整** | A8W8 shifts[26,47], S42/S24 | `hap_attention_board_cohort16_core.sv` | ✓ 完全对齐 | 完整 32 层仿真验证 |

---

## 数值合同（不可修改）

本项目冻结下列数值边界。**任何偏差都需要重新验证完整 ACC/PPL，并在项目记录中暴露为风险。**

### Host ↔ FPGA 接口

| 方向 | 数据格式 | 步长 | 说明 |
|---|---|---|---|
| Host → FPGA (MLP 输入) | S24/F16 | 2^-16 | RMSNorm FP32 下转 |
| FPGA → Host (MLP 输出) | **S32/F16**（新） | 2^-16 | Down 末级不能再是 S24 |
| Attention 输入/输出 | S24/F16 | 2^-16 | 不变 |

### 核心计算路径

#### Gate/Up 路径（不变）
```
Host S24/F16
→ Hadamard32 (S27/F16)
→ Group32 A8 + ScaleCode (U8 + 2×U8 metadata)
→ Gate/Up W4 × A8
→ Guard S37/F24 → Accumulator S44/F24 → Output S24/F16
→ [临时] 送入 SwiGLU
```

#### SwiGLU 融合（修复完成）
```
Gate/Up S24/F16 (每个 lane)
→ 按 bit[23] 符号扩展到 32-bit: {{8{lane[23]}}, lane}  ← 关键修复点
→ SiLU LUT 计算 (8193 项，@1/256 spacing)
→ Up S24/F16 相乘 → S48/F32
→ Round half-away → S32/F16 ← 新修复
```

#### Down 路径（修复完成）
```
S32/F16 SwiGLU product
→ Hadamard32 (S35/F16)
→ Group32 A8 + ScaleCode
→ Down W4 × A8
→ Guard S45/F24（新） → Accumulator S54/F24（新）
→ Round half-away → Output S32/F16（新，不再 S24）
→ Host residual add (FP32)
```

#### Down Shift 范围（修复）
- 旧范围：[20, 44] ← 导致 391M 格式错误 + 65.6M 溢出
- 新范围：[12, 44] ← 支持 layer 31 最小 shift
- **Down S45 guard 禁止 zero-guard；所有 shift [12,19] 贡献进入 S45/S54**

### Attention 完整合同（不变）
```
A8W8, shifts [26,47], S42 accumulation, S24 output
GQA32/8 heads, head_dim 128, KV cache 12 positions
QK ±16 clamp, Softmax delta[-16,0] clamp, Softmax LUT 257-entry U17 @ 1/256
```

---

## 成功标准

以下条目是最终验收目标；历史的 ✓ 标记不是当前 M002 通过证据。当前实际覆盖以 [M002 汇总](../results/missions/M002_summary.md) 为准。

### Level 1：数值准确性（必须）
- ✓ 软件 `v5_fullchain.py` 完整 Llama-3.1-8B forward pass，ACC/PPL 已通过（MLP-only & Full V5）
- ✓ 硬件功能仿真中，Gate/Up + SwiGLU + Down 链路与软件输出**字节级一致**（无舍入差异）
- ✓ 完整 32 层、两个 cohort 上下文无数值偏差
- **验证方法：** 软件提取参考 golden 向量 → XSim 对比 → 位精确匹配或文档化舍入差异

### Level 2：硬件验收标准
- ✓ 综合 PASS（无错误/警告，仅允许标准 Vivado 信息）
- ✓ 实现 (Place & Route) PASS
  - Setup time >= 0 ns（core 100 MHz）
  - Hold time >= 0 ns
  - 所有约束满足（no TNS violations）
- ✓ DRC 全绿（无 physical design rule violations）
- ✓ 布线完成率 100%

### Level 3：板级验收标准
- ✓ Bitstream 生成无错误
- ✓ VCU118 板卡加载成功
- ✓ Host ↔ DDR0/DDR1 通信正常
- ✓ Host → FPGA → Host 完整推理闭环一次通过
- ✓ 吞吐、延迟、功耗测量（当前无 token/s 门槛，记录实际数据）
- ✓ 完整 Llama-3.1-8B 推理、覆盖所有 32 层、无挂死/错误

### Level 4：最终质量标准
- ✓ 完整项目文档（算法、接口、验证结果）
- ✓ 生成的 bitstream、Host 驱动、artifact 版本号一致
- ✓ 所有审计计数器（饱和、溢出、格式错误）为 0
- ✓ 没有"有限性"异常或跳过的验证环节

---

## 平台与约束

- **器件：** Xilinx Virtex UltraScale VCU118（xcvu9p-flga2104-2L-e）
- **核心时钟：** 100 MHz（目标，非测量）
- **内存：** 独立 DDR0/DDR1，UI 200 MHz，2 GiB 本地/通道
- **工具：** Vivado 2025.2，XSim，Python 3.10+（带 NumPy/PyTorch）
- **模型格式：** MLP format `0x48384605`, ABI `0x00050000`；Attention format `0x48384103`, ABI `0x00020000`
- **外部依赖：** 权重、完整测试数据留在只读源目录，via 路径引用

---

## 关键缺口与风险

### 当前已解决 ✓
1. Down-S32 修复：设计完成，RTL 已实现，软件验证通过
2. SwiGLU 符号扩展：已在 `hap_mlp_silu_mul.sv` 正确实现
3. Hadamard 数学：软件与硬件规格完全对齐

### 当前未验证 ⚠
1. **功能仿真链路**：未运行完整 Gate/Up → SwiGLU → Down RTL 仿真对比 v5_fullchain.py
2. **完整 32 层闭环**：仅有 MLP-only 软件全量 ACC/PPL 通过；完整 Attention+MLP 链路未上硬件仿真
3. **布线后时序**：当前E003 route因拥塞/节点重叠自然失败，无完整routed报告；最后正式physopt WNS−1.290ns、WHS−0.620ns，时序仍FAIL。旧native025为历史证据
4. **DDR 延迟路径**：Host 反馈延迟、dual cohort 上下文切换开销未量化
5. **完整 bitstream 部署**：未在 VCU118 板卡上运行

---

## 双 DDR 完全分离架构（核心创新）

### 架构原则

**Attention 专用 DDR0，MLP 专用 DDR1，通过 PCIe 完全解耦。**

```
┌────────────────────────────────────────────────────────────┐
│                      HOST (PCIe)                           │
│  FP32 RMSNorm → Residual Add → Layer管理                   │
└─────┬──────────────────────────────────────────┬───────────┘
      │ PCIe H2C/C2H                             │ PCIe H2C/C2H
      ▼                                          ▼
┌─────────────────────┐              ┌─────────────────────┐
│  DDR0 (Attention)   │              │  DDR1 (MLP)         │
│  2 GiB, 1.36 GB/s   │              │  2 GiB, 1.36 GB/s   │
│                     │              │                     │
│  - Attn Weights     │              │  - MLP Weights      │
│  - KV Cache         │              │  - Input/Output     │
│  - Input/Output     │              │  - Metadata         │
└──────┬──────────────┘              └──────┬──────────────┘
       │                                    │
       ▼                                    ▼
┌─────────────────────┐              ┌─────────────────────┐
│ Attention Accel     │              │ MLP Accel           │
│ ~2400 DSP           │              │ ~3072 DSP           │
└─────────────────────┘              └─────────────────────┘
```

### 数据流时序（Per Layer）

**串行依赖（Transformer 标准）：**
```
Layer N:
  Step 1: Attention (DDR0)
    Host → DDR0: Input S24
    Attention 计算
    DDR0 → Host: Output S24
    Host: Residual + RMSNorm
    
  Step 2: MLP (DDR1)
    Host → DDR1: Input S24
    MLP 计算
    DDR1 → Host: Output S32
    Host: Residual + RMSNorm
```

**双 Cohort Pipeline（并行优化）：**
```
Time    Cohort 0        Cohort 1        DDR0      DDR1
─────────────────────────────────────────────────────────
T0      L0 Attn        Idle            Active    Idle
T1      L0 MLP         L1 Attn         Active    Active  ← 并行
T2      L2 Attn        L1 MLP          Active    Active  ← 并行
T3      L2 MLP         L3 Attn         Active    Active  ← 并行
```

### 历史性能预期（当前架构未验证）

下表保留早期预测来源，不用于 M002 的性能结论。当前 Attention 两逻辑半流共用 DDR0，MLP 两逻辑半流共用 DDR1；MLP 采用 84 MiB 单层 slot，需要计入 Host 按层加载开销，原常驻权重/双通道模型不可直接复用。

| 配置 | 单 Cohort | 双 Cohort |
|---|---|---|
| 当前基线（DDR 共享冲突） | 2.5 tokens/s | 3.8 tokens/s |
| DDR 分离 | 3.5 tokens/s | 5.3 tokens/s |
| + Prefetch 优化 | 3.9 tokens/s | 6.6 tokens/s |
| + 时钟 110 MHz | 4.3 tokens/s | 7.3 tokens/s |

---

## 实现路线图

### Phase 1：软件数值基线（已完成 ✓）
- [x] Hadamard + ScaleCode 量化算法设计与实现
- [x] MLP-only 全量 ACC/PPL 验证通过
- [x] Full V5（Attention+MLP）软件链路验证通过
- [x] Down-S32 修复与完整 Llama-3.1-8B 软件孪生验证
- [x] 硬件-软件对齐验证完成（5451 DSP, 性能瓶颈分析）

### Phase 2：DDR 分离架构与布线时序修复（当前 M002）
- [ ] 布线前时序修复
  - Setup slack: -5.1ns → ≥ +0.5ns
  - Hold slack: -3.1ns → ≥ +0.5ns
  - 目标：100 MHz，fallback 95 MHz
  
- [ ] DDR 双通道完全分离
  - DDR0 专属 Attention
  - DDR1 专属 MLP
  - 地址映射重新设计
  - RTL top-level 接线修改
  
- [ ] 综合与实现
  - 综合 PASS（无 Critical Warning）
  - Place & Route 完成
  - DRC 全绿

### Phase 3：板级部署与性能验证
- [ ] Bitstream 生成与 VCU118 部署
- [ ] 单 Cohort 基准测试
- [ ] 双 Cohort Pipeline 实现
- [ ] DDR prefetch 优化
- [ ] 完整 32 层性能测量

---

## 项目纪律与禁区

### ✓ 允许
- 在软件验证完成后的 RTL 改进、优化、bug 修复
- 硬件综合后的时序约束调优
- 文档、脚本、测试改进

### ⚠ 需要用户明确授权才能进行
- 改变量化策略（Hadamard 点数、group size、bit 宽）
- 改变 MLP/Attention 算法逻辑
- 改变数值边界或精度等级
- 扩展/缩小 DDR 使用

### ✗ 禁止（需要重新立项）
- "简化" Gate/Up 或 Down 数学（如跳过 Hadamard、用 shift 代替 scale）
- 改变符号扩展、舍入策略（除非在软件孪生中预先验证）
- 移除或宽松审计计数器
- 用旧 S24 Down 格式或任何其他历史候选
- 宣称综合 PASS 等同于功能正确或上板通过

---

## 当前任务与交付

**当前 mission：** M002目标仍未完成。SM009/E005本次优化与完整implementation、只读补证据及内部审核已结束；合法布通FAIL，尚无成功routed签核。[本次结果](../project/E005_m002_optimized_implementation/experiment_results/summary.md)、[主控审核](../results/reviews/SM009.md)。不自动原样重复route，后续依据真实热点/连接证据选择受控对照；数值、接口、时钟和全局验收不变。

E001快速验证和E002正式综合/OPT/debug/pre_place为前置。E003已完成place及独立physopt的DCP/完整POST，正式physopt时序仍FAIL；R003/AT001 route实际19065秒后自然exit1，245279重叠节点、248289拥塞失败信号，没有最终route DCP/完整报告。全部进程已自然退出，无时间/资源强停。原证据保留，[E003状态](../project/E003_m002_full_implementation/experiment_status/summary.md)为失败终态。完整数值、时序和板级目标未验收。

**当前地址与兼容合同：** Attention 32 层 1280 MiB 常驻 DDR0；KV 96 MiB 仅保留地址，未新增外部 KV 生命周期；MLP 四 artifact 共 84 MiB 在 DDR1 按层加载并由 lease 保护。六个逻辑权重 CSR 保持 local offsets，layout ID 0x2B8=0x4D303032 与数值 format05/ABI 分开验证。

**执行边界：** 允许首选两项RTL、受影响测试与构建/物理入口修复、新综合和完整implementation；不扩大为bitstream、GPU、PPL/ACC或板卡，不改变数值/接口/时钟合同。

---

## 历史参考

旧工程 `/home/user/EDA-202/zhuowenjun/ScaleLLM` 完整保留。

- native025 候选：failed, unrouted diagnostic（不是可用基线）
- 旧 Down S24 设计：已废弃（输出饱和 18,044 次）
- 当前只读源路径参见 [migration/external_dependencies.json](../project/hardware/migration/external_dependencies.json)

---

## 修订记录

- **2026-10-14**：初次写入，整理 M001 后基准版本
- **2026-10-14**：硬件-软件对齐核心检查完成，纳入强制性对齐规范和验证标准

- **2026-10-15**：更新 M002 修复合同和实际地址图；将历史性能预测与验收目标和当前证据明确分开。
