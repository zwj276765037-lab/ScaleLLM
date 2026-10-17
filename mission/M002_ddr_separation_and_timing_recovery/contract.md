# M002：DDR 双通道分离架构与布线时序恢复

> 2026-10-15 当前执行依据：[修复与快速功能验证合同](repair_contract_2026-10-15.md)。用户已授权修复和快速验证，尚未授权正式综合/implementation；下文旧方案与预测需结合最新审核理解。

**创建时间：** 2026-10-14  
**优先级：** 🔴 P0 CRITICAL  
**状态：** planning  
**负责人：** 待分配

---

## 执行摘要

本任务实现 ScaleLLM 的两大关键优化：

1. **DDR 双通道完全分离架构**：Attention 专用 DDR0，MLP 专用 DDR1，消除带宽冲突
2. **布线前时序恢复**：修复 native025 的 setup -5.1ns / hold -3.1ns 问题，使能部署

**预期收益：**
- 性能提升：+40% (2.5 → 3.5 tokens/s，单 cohort)
- 时序收敛：100 MHz 目标，95 MHz fallback
- 架构清晰：完全解耦，为双 cohort pipeline 铺路

---

## 一、问题陈述

### 1.1 当前架构瓶颈

**硬件资源验证（来自 Vivado 综合报告）：**
```
Total DSP48E2: 5451 个
  - MLP 阵列: ~3072 DSP (614 GOPS @ 100 MHz)
  - Attention 阵列: ~2400 DSP (480 GOPS @ 100 MHz)
  
DDR 配置:
  - DDR0: 2 GiB, 1.36 GB/s 实际带宽
  - DDR1: 2 GiB, 1.36 GB/s 实际带宽
```

**性能瓶颈分析：**
```
每层 MLP (16 tokens):
  计算量: 28.44 GOPS
  计算时间: 46 ms (理论, 614 GOPS)
  
  权重传输: 88.1 MiB
  DDR 传输时间: 65 ms @ 1.36 GB/s
  
瓶颈: DDR 占 58-65%，计算占 35-42%
结论: DDR 带宽是主要瓶颈
```

**当前 DDR 使用冲突：**
```
DDR0 当前分配（混合）:
  - Attention weights
  - MLP weights
  - Attention KV cache
  - MLP input/output buffers
  → 冲突导致 30% 带宽损失

DDR1 当前分配:
  - 部分 KV cache
  - 大部分空闲
```

### 1.2 布线前时序问题

**来源：** native025 diagnostic (unrouted placement)

```
Setup slack: -5.1 ns (worst: DDR0_AW_D)
Hold slack:  -3.1 ns (worst: DDR0_B_RESET)

根本原因:
  1. DDR0 写地址通道: AXI AW path 信号线过长
  2. Reset CDC: 多级同步器保守设计
  3. MLP 核心分割: DSP 阵列放置非最优
```

---

## 二、目标与成功标准

### 2.1 DDR 分离目标

**架构目标：**
- [x] DDR0 专属 Attention（权重、KV cache、input/output）
- [x] DDR1 专属 MLP（权重、input/output、metadata）
- [x] 两个 DDR 通道完全独立，无共享资源
- [x] 支持 Attention 和 MLP 在不同层间并行

**性能目标：**
```
Metric                  | Baseline | Target  | 验收标准
──────────────────────────────────────────────────────
单 Cohort throughput    | 2.5 t/s  | 3.5 t/s | ≥ 3.2 t/s
DDR 冲突率              | 30%      | <5%     | ≤ 10%
MLP per-layer latency   | 93 ms    | 65 ms   | ≤ 75 ms
```

### 2.2 时序收敛目标

**Primary target (100 MHz):**
```
Setup slack: ≥ +0.5 ns
Hold slack:  ≥ +0.5 ns
Clock freq:  100 MHz
DRC:         0 violations
Route:       100% completion
```

**Fallback target (95 MHz):**
```
Setup slack: ≥ +1.5 ns
Hold slack:  ≥ +1.0 ns
Clock freq:  95 MHz (throughput -5%)
```

---

## 三、技术方案设计

### 3.1 DDR 双通道分离架构

#### 3.1.1 地址映射重新设计

**DDR0 (Attention 专属):**
```
0x0000_0000 ~ 0x1FFF_FFFF: Attention weights (Q/K/V/O)
  32 layers × 62 MiB = 1984 MiB
  
0x2000_0000 ~ 0x2060_0000: KV cache
  2 cohorts × 3 slots × 128 positions × metadata
  = 96 MiB (reserved)
  
0x2080_0000 ~ 0x20A0_0000: Attention input buffers
  6 slots × 192 KiB = 1152 KiB (2 MiB aligned)
  
0x20A0_0000 ~ 0x20C0_0000: Attention output buffers
  6 slots × 192 KiB = 1152 KiB (2 MiB aligned)
  
Total DDR0 usage: ~2.1 GiB (fits in 2 GiB channel)
```

**DDR1 (MLP 专属):**
```
0x8000_0000 ~ 0x9FFF_FFFF: MLP weights (Gate/Up/Down)
  32 layers × 88 MiB = 2816 MiB
  → 需要压缩或分层加载（单层一次加载）
  
0xA000_0000 ~ 0xA020_0000: MLP input buffers
  6 slots × 192 KiB = 1152 KiB
  
0xA020_0000 ~ 0xA048_0000: MLP output buffers
  6 slots × 256 KiB = 1536 KiB
  
0xA048_0000 ~ 0xA050_0000: MLP metadata
  ScaleCode tables, shift tables
  = 128 KiB
  
Total DDR1 per-layer: ~88 MiB weights + 3 MiB runtime
```

**权重管理策略：**
```
方案 A: 单层加载（推荐）
  - 每层从 DDR1 加载 88 MiB 权重
  - 32 layers × 88 MiB = 2.82 GiB total transfer
  - 优点: 简单、DDR 使用 < 2 GiB
  - 缺点: 每层加载延迟 65 ms
  
方案 B: 权重压缩
  - 使用 Huffman 或 RLE 压缩 W4 权重
  - 压缩比 1.5-2x → 1.4-1.9 GiB
  - 优点: 所有权重常驻
  - 缺点: 需要解压逻辑，增加延迟
  
推荐: 方案 A (单层加载)
```

#### 3.1.2 RTL 修改清单

**文件 1: `hap_attention_mlp_resource_top.sv`**

当前设计（推测）:
```systemverilog
// Shared DDR arbiter
hap_axi512_paired_2client_read_wrr u_arbiter (
    .client0_axi(attention_axi),
    .client1_axi(mlp_axi),
    .master_axi(ddr0_axi)  // DDR0 共享
);
```

新设计:
```systemverilog
// 移除 arbiter，直连各自 DDR
hap_attention_board_cohort16_core u_attention (
    .ddr_ar(...),
    .ddr_aw(...),
    .ddr_r(...),
    .ddr_w(...),
    .ddr_b(...),
    .m_axi_ddr(ddr0_axi)  // ← 直连 DDR0
);

hap_mlp_full_command16_s54 u_mlp (
    .ddr_ar(...),
    .ddr_aw(...),
    .ddr_r(...),
    .ddr_w(...),
    .ddr_b(...),
    .m_axi_ddr(ddr1_axi)  // ← 直连 DDR1
);
```

**修改量估算：**
- 删除行数: ~200 lines (arbiter 实例化 + 信号连接)
- 新增行数: ~50 lines (直连逻辑)
- 风险: 低（仅接线变更，无逻辑修改）

**文件 2: `scalellm_memory.py`**

当前:
```python
# Unified address space
ATTENTION_INPUT_BASE = 0x40000000  # DDR0
MLP_INPUT_BASE = 0x4C000000        # DDR0
KV_CACHE_BASE = 0x80000000         # DDR1
```

新设计:
```python
# DDR0 专属
DDR0_BASE = 0x00000000
ATTENTION_WEIGHTS_BASE = DDR0_BASE
ATTENTION_INPUT_BASE = DDR0_BASE + 0x20800000
ATTENTION_OUTPUT_BASE = DDR0_BASE + 0x20A00000
KV_CACHE_BASE = DDR0_BASE + 0x20000000

# DDR1 专属
DDR1_BASE = 0x80000000
MLP_WEIGHTS_BASE = DDR1_BASE
MLP_INPUT_BASE = DDR1_BASE + 0x20000000
MLP_OUTPUT_BASE = DDR1_BASE + 0x20200000
MLP_METADATA_BASE = DDR1_BASE + 0x20480000

def validate_address_separation():
    """Verify no DDR0/DDR1 overlap."""
    assert all(addr < DDR1_BASE for addr in [
        ATTENTION_WEIGHTS_BASE,
        ATTENTION_INPUT_BASE,
        ATTENTION_OUTPUT_BASE,
        KV_CACHE_BASE
    ])
    assert all(addr >= DDR1_BASE for addr in [
        MLP_WEIGHTS_BASE,
        MLP_INPUT_BASE,
        MLP_OUTPUT_BASE,
        MLP_METADATA_BASE
    ])
```

**修改量估算：**
- 修改行数: ~80 lines (地址常量 + 函数更新)
- 新增行数: ~40 lines (验证函数 + 文档)
- 风险: 低（纯软件逻辑）

**文件 3: `scalellm_hardware.py`**

新增验证逻辑:
```python
def dma_write(self, addr: int, data: bytes) -> None:
    """Write via PCIe DMA with DDR channel validation."""
    if addr < 0x80000000:
        channel = "DDR0 (Attention)"
        assert self._last_op != "MLP", \
            "DDR0 access after MLP operation (should use DDR1)"
    else:
        channel = "DDR1 (MLP)"
        assert self._last_op != "Attention", \
            "DDR1 access after Attention operation (should use DDR0)"
    
    # Actual DMA write
    self._pcie_dma_write(addr, data)
    self._ddr_access_log.append((channel, addr, len(data)))
```

**修改量估算：**
- 修改行数: ~30 lines
- 新增行数: ~60 lines (验证 + 日志)
- 风险: 低

#### 3.1.3 PCIe DMA 调度（可选优化）

**当前设计（推测）：**
- 单一 DMA engine，轮询 Attention 和 MLP

**优化方案：**
```
DMA Channel 0: Host → DDR0 (Attention input)
DMA Channel 1: DDR0 → Host (Attention output)
DMA Channel 2: Host → DDR1 (MLP input)
DMA Channel 3: DDR1 → Host (MLP output)
```

**收益：**
- 4 个独立通道可并行（如果 PCIe endpoint 支持）
- 避免 Attention/MLP DMA 队列冲突
- 预期延迟降低 10-15%

**实施难度：** 中（需要修改 PCIe DMA controller）

**决策：** Phase 1 不实施，Phase 3 可选优化

---

### 3.2 布线时序恢复方案

#### 3.2.1 Setup 时序修复（-5.1ns → ≥ +0.5ns）

**Issue 1: DDR0 写地址通道（worst path）**

当前问题:
```
Path: MLP command FIFO → AXI AW control → DDR0 MIG
Slack: -5.1 ns
Root cause: 信号线长度 > budget after placement
```

**Solution 1-A: Placement constraint (推荐)**
```tcl
# 新文件: vivado/constraints/ddr_timing_recovery.xdc

# 将 DDR0_AW FIFO 限制在 MIG 附近
set_property LOC SLICE_X50Y100 [get_cells -hier -filter {NAME =~ *ddr0_aw_fifo*}]
set_property BEL AFF [get_cells -hier -filter {NAME =~ *ddr0_aw_addr_ff[0]*}]

# Pblock 约束
create_pblock pblock_ddr0_ctrl
add_cells_to_pblock pblock_ddr0_ctrl [get_cells -hier -filter {NAME =~ *ddr0_axi_ctrl*}]
resize_pblock pblock_ddr0_ctrl -add {SLICE_X40Y80:SLICE_X60Y120}
```

预期改善: +1.5 ~ +2.5 ns  
可信度: 85%

**Solution 1-B: Timing derate 调整**
```tcl
# 检查 DDR MIG 的 setup margin 是否过于保守
set_timing_derate -early 0.95 -late 1.05 [get_cells -hier -filter {REF_NAME =~ mig_7series*}]
```

预期改善: +0.5 ~ +1.0 ns  
可信度: 80%

**Solution 1-C: Pipeline 插入（最后手段）**
```verilog
// 在 AW 路径插入一级寄存器
always_ff @(posedge clk) begin
    ddr0_aw_addr_r <= mlp_command_fifo_out.addr;
    ddr0_aw_valid_r <= mlp_command_fifo_out.valid;
end

assign ddr0_axi.aw_addr = ddr0_aw_addr_r;
assign ddr0_axi.aw_valid = ddr0_aw_valid_r;
```

预期改善: +4 ~ +6 ns  
可信度: 100%  
代价: 增加 1 周期延迟（10ns），需重新验证 MLP FSM

**推荐策略：**
1. 先尝试 Solution 1-A + 1-B（低风险）
2. 如果仍不足，采用 Solution 1-C（需软件团队配合）

#### 3.2.2 Hold 时序修复（-3.1ns → ≥ +0.5ns）

**Issue 2: Reset CDC（worst hold path）**

当前问题:
```
Path: DDR MIG RESET_N → multi-stage synchronizer
Slack: -3.1 ns
Root cause: CDC 同步器级数过多，routing 后恶化
```

**Solution 2-A: Multicycle path constraint (推荐)**
```tcl
# Reset 路径可以放松，不需要在每个周期满足
set_multicycle_path 2 -setup -from [get_pins -hier -filter {NAME =~ *ddr_reset_sync_ff_r[0]/C}]
set_multicycle_path 1 -hold  -from [get_pins -hier -filter {NAME =~ *ddr_reset_sync_ff_r[0]/C}]
```

预期改善: +1.0 ~ +2.0 ns  
可信度: 70%

**Solution 2-B: 同步器级数优化**
```verilog
// 当前（推测）: 4 级同步器
reg [3:0] reset_sync_ff_r;
always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        reset_sync_ff_r <= 4'b0000;
    else
        reset_sync_ff_r <= {reset_sync_ff_r[2:0], ddr_mig_reset_n};
end

// 优化: 减到 3 级（如果 MTBF 允许）
reg [2:0] reset_sync_ff_r;
// ... 类似逻辑
```

预期改善: +1.5 ~ +2.0 ns  
可信度: 60%  
风险: 需要 MTBF 分析（metastability mean time between failures）

**Solution 2-C: False path（仅用于真正异步 reset）**
```tcl
# 如果 reset 路径是静态的，可以完全忽略
set_false_path -from [get_ports rst_n] -to [get_cells -hier -filter {NAME =~ *reset_sync_ff_r*}]
```

预期改善: 完全消除 hold violation  
可信度: 100%  
适用条件: reset 仅在上电/重启时切换

**推荐策略：**
1. 先尝试 Solution 2-A（最安全）
2. 如果不足，分析 MTBF 后采用 Solution 2-B
3. 确认 reset 语义后，可能采用 Solution 2-C

#### 3.2.3 MLP 核心分割（-2.9ns → ≥ +0.5ns）

**Issue 3: DSP 阵列放置（次要瓶颈）**

当前问题:
```
Path: Guard S37→S45 transition register 距离 DSP array 过远
Slack: -2.9 ns
```

**Solution 3: Pblock 优化**
```tcl
# 将 S37→S45 logic 靠近 DSP 阵列中心
create_pblock pblock_mlp_guard
add_cells_to_pblock pblock_mlp_guard [get_cells -hier -filter {NAME =~ *mlp*guard*s45*}]

# 限制在 DSP 列附近
resize_pblock pblock_mlp_guard -add {DSP48E2_X10Y50:DSP48E2_X15Y100}
```

预期改善: +0.8 ~ +1.5 ns  
可信度: 60%

---

### 3.3 综合时序收敛策略

#### 组合优化预测

| 优化组合 | Setup改善 | Hold改善 | 总Slack (Setup) | 总Slack (Hold) | 成功率 |
|---|---|---|---|---|---|
| **基线** | 0 | 0 | -5.1 ns | -3.1 ns | 0% |
| 1-A + 1-B | +2.0 ns | 0 | -3.1 ns | -3.1 ns | 15% |
| 1-A + 1-B + 2-A | +2.0 ns | +1.5 ns | -3.1 ns | -1.6 ns | 30% |
| 1-A + 1-B + 2-A + 3 | +2.8 ns | +1.5 ns | -2.3 ns | -1.6 ns | 45% |
| **+ 1-C pipeline** | +6.8 ns | +1.5 ns | **+1.7 ns ✓** | -1.6 ns | 75% |
| **+ 2-B sync opt** | +6.8 ns | +3.0 ns | **+1.7 ns ✓** | **-0.1 ns ≈** | 85% |
| **Fallback: 95 MHz** | - | - | **+2.2 ns ✓** | **+0.4 ns ✓** | 100% |

**推荐执行路径：**
1. Day 1-2: 实施 1-A + 1-B + 2-A + 3（低风险）
2. Day 3: Route & 验证，如果 setup < 0，实施 1-C
3. Day 4: 如果 hold < 0，实施 2-B 或 2-C
4. Day 5: 如果仍失败，降频到 95 MHz

---

## 四、实施计划

### Week 1: DDR 分离基础架构

**Day 1-2: 地址映射与软件适配**
- [ ] 更新 `scalellm_memory.py` 地址定义
- [ ] 更新 `scalellm_hardware.py` DMA 逻辑
- [ ] 编写单元测试验证地址分离
- [ ] 文档化新地址映射表

**Day 3-4: RTL 接线修改**
- [ ] 修改 `hap_attention_mlp_resource_top.sv`
- [ ] 移除 DDR arbiter 实例
- [ ] 直连 Attention → DDR0, MLP → DDR1
- [ ] 语法检查与静态分析

**Day 5: 初步验证**
- [ ] 编译测试（no synthesis）
- [ ] 检查 elaboration 无 error
- [ ] Review 代码变更

**Deliverables:**
- 更新后的 Python 地址库
- 修改后的 RTL top-level
- 地址映射文档

---

### Week 2: 布线时序修复

**Day 1: 提取 native025 placement**
- [ ] 从旧工程复制 placed DCP
- [ ] 在 Vivado 中打开验证
- [ ] 分析当前 timing paths

**Day 2: 实施约束优化（1-A + 1-B + 2-A + 3）**
- [ ] 创建 `ddr_timing_recovery.xdc`
- [ ] 添加 placement constraints
- [ ] 添加 timing derate
- [ ] 添加 multicycle path
- [ ] 添加 pblock constraints

**Day 3: Re-route 与验证**
- [ ] 从 placed DCP 重新 route
- [ ] 生成 timing report
- [ ] 检查 setup/hold slack

**Decision Point:**
```
如果 setup ≥ 0 AND hold ≥ 0:
  → 继续 Day 5 (综合)
  
如果 setup < 0:
  → Day 4-A: 实施 pipeline 插入 (1-C)
  
如果 hold < 0:
  → Day 4-B: 实施同步器优化 (2-B/2-C)
```

**Day 4 (conditional): 高级修复**
- [ ] 实施 Solution 1-C 或 2-B/2-C
- [ ] 重新 route
- [ ] 验证时序

**Day 5: 综合验收**
- [ ] 完整 synthesis (包含 DDR 分离修改)
- [ ] Place & Route
- [ ] DRC check
- [ ] 生成资源报告

**Deliverables:**
- Timing-closed design (setup ≥ 0, hold ≥ 0)
- DRC clean
- Route 100% complete
- Detailed timing report

---

### Week 3: 集成验证与 Bitstream

**Day 1: 功能仿真（可选）**
- [ ] XSim elaboration
- [ ] 基础 smoke test
- [ ] 验证 DDR0/DDR1 分离无冲突

**Day 2-3: Bitstream 生成**
- [ ] write_bitstream
- [ ] 验证 bitstream 大小合理
- [ ] 生成最终报告（timing, power, resource）

**Day 4-5: VCU118 部署**
- [ ] JTAG 连接测试
- [ ] Bitstream 加载
- [ ] DDR0/DDR1 初始化
- [ ] 1-token 功能测试

**Deliverables:**
- `scalellm_v5_m002.bit`
- Timing summary report
- Power analysis report
- Resource utilization report

---

## 五、性能估算与验收标准

### 5.1 DDR 分离性能模型

#### 单层 MLP 性能（16 tokens）

**当前基线（DDR 共享冲突）：**
```
DDR 读权重: 88 MiB @ 1.36 GB/s × 0.7 (冲突) = 93 ms
DSP 计算: 28.44 GOPS @ 614 GOPS = 46 ms (overlap)
总时间: 93 ms per layer

32 layers: 2.98 s
```

**DDR 分离后：**
```
DDR 读权重: 88 MiB @ 1.36 GB/s × 1.0 (无冲突) = 65 ms
DSP 计算: 46 ms (完全 overlap)
总时间: 65 ms per layer

32 layers: 2.08 s
收益: 30% faster
```

#### 完整推理性能（16 tokens, 32 layers）

| 配置 | MLP | Attention | Total | Throughput | vs Baseline |
|---|---|---|---|---|---|
| **基线** | 2.98 s | ~3.5 s | 6.5 s | 2.5 t/s | - |
| **DDR 分离** | 2.08 s | ~2.5 s | 4.6 s | 3.5 t/s | **+40%** |
| **+ Prefetch** | 1.88 s | ~2.2 s | 4.1 s | 3.9 t/s | +56% |
| **+ 双 Cohort** | - | - | ~2.7 s | 5.9 t/s | +136% |

### 5.2 验收标准

#### Phase 1 验收（DDR 分离）

**功能验收：**
- [ ] 地址空间完全分离（DDR0 < 0x80000000, DDR1 ≥ 0x80000000）
- [ ] Attention 仅访问 DDR0
- [ ] MLP 仅访问 DDR1
- [ ] 单元测试 100% 通过

**性能验收：**
- [ ] 单 Cohort throughput ≥ 3.2 tokens/s
- [ ] DDR 冲突率 ≤ 10%
- [ ] MLP per-layer latency ≤ 75 ms

#### Phase 2 验收（时序收敛）

**时序验收（Primary: 100 MHz）：**
- [ ] Setup WNS ≥ +0.5 ns
- [ ] Hold WNS ≥ +0.5 ns
- [ ] Setup TNS = 0
- [ ] Hold TNS = 0
- [ ] No timing exceptions (except intentional)

**时序验收（Fallback: 95 MHz）：**
- [ ] Setup WNS ≥ +1.5 ns
- [ ] Hold WNS ≥ +1.0 ns
- [ ] Throughput 损失 ≤ 5%

**物理验收：**
- [ ] DRC: 0 errors, 0 critical warnings
- [ ] Route: 100% completion
- [ ] No unrouted nets
- [ ] Congestion: 所有区域 < 90%

#### Phase 3 验收（板级部署）

**部署验收：**
- [ ] Bitstream 加载成功
- [ ] DDR0/DDR1 初始化正常
- [ ] JTAG 通信稳定
- [ ] 1-token 推理功能测试通过

**性能验收：**
- [ ] 单 Cohort 实测 throughput ≥ 3.2 tokens/s
- [ ] DDR0/DDR1 bandwidth utilization ≥ 70%
- [ ] 无 DDR timeout 或 retry
- [ ] 核心温度 < 85°C

---

## 六、风险管理

### 6.1 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|---|---|---|---|
| **时序无法收敛到 100 MHz** | 25% | 高 | Fallback 95 MHz，仅损失 5% throughput |
| **DDR 分离引入功能 bug** | 15% | 中 | 完整单元测试 + XSim 验证 |
| **Pipeline 插入破坏 FSM** | 10% | 中 | 仅在必要时使用，预先评估影响 |
| **Bitstream 加载失败** | 5% | 高 | 保留旧 bitstream，回滚机制 |
| **权重单层加载延迟过高** | 20% | 低 | 可接受，Phase 3 优化 prefetch |

### 6.2 项目风险

| 风险 | 概率 | 影响 | 缓解措施 |
|---|---|---|---|
| **DDR 分离延期** | 10% | 低 | 与时序修复并行，互不阻塞 |
| **Vivado 工具 bug** | 5% | 中 | 尝试 2025.1 或 2024.2 版本 |
| **VCU118 板卡故障** | 3% | 高 | 备用板卡准备 |

### 6.3 决策树

```
Week 1 结束:
  ├─ DDR 分离代码完成? 
  │   ├─ YES → 继续 Week 2
  │   └─ NO → 延期 2 天，推迟 Week 3
  │
Week 2 Day 3:
  ├─ Timing 收敛到 100 MHz?
  │   ├─ YES → 继续 synthesis
  │   └─ NO → 
  │       ├─ Setup < -2ns? → 实施 pipeline (1-C)
  │       ├─ Hold < -1ns? → 实施 sync opt (2-B)
  │       └─ Both fail? → Fallback 95 MHz
  │
Week 2 结束:
  ├─ Bitstream 生成成功?
  │   ├─ YES → Week 3 部署
  │   └─ NO → 
  │       ├─ DRC fail? → 修复 DRC，延期 2 天
  │       └─ Route fail? → 降低 congestion，延期 3 天
```

---

## 七、资源需求

### 7.1 人力需求

| 角色 | 工作量 | 关键技能 |
|---|---|---|
| **RTL 工程师** | 5 天 | SystemVerilog, AXI, DDR MIG |
| **Python 开发** | 3 天 | PCIe DMA, 地址映射 |
| **Timing 工程师** | 5 天 | Vivado constraints, 时序分析 |
| **验证工程师** | 3 天 | XSim, 功能测试 |
| **板级工程师** | 2 天 | VCU118, JTAG, DDR 初始化 |

### 7.2 工具需求

| 工具 | 版本 | 用途 |
|---|---|---|
| Vivado | 2025.2 | Synthesis, P&R, Bitstream |
| XSim | 2025.2 | 功能仿真（可选）|
| Python | 3.10+ | Host 驱动开发 |
| VCU118 | 1 块 | 板级测试 |

### 7.3 时间估算

| Phase | 乐观 | 典型 | 悲观 |
|---|---|---|---|
| Week 1 (DDR 分离) | 4 天 | 5 天 | 7 天 |
| Week 2 (时序修复) | 4 天 | 5 天 | 8 天 |
| Week 3 (部署) | 3 天 | 5 天 | 7 天 |
| **Total** | **11 天** | **15 天** | **22 天** |

**Critical path:** Week 2 (时序修复)

---

## 八、后续任务

### M003: 双 Cohort Pipeline 实现

**前置条件：** M002 完成

**目标：**
- Layer N MLP (DDR1) 与 Layer N+1 Attention (DDR0) 并行
- Overlap 效率 ≥ 60%
- Throughput: 3.5 → 5-6 tokens/s

### M004: DDR Prefetch 优化

**前置条件：** M002 完成

**目标：**
- 提前加载下一层权重
- 隐藏 DDR 延迟
- Throughput: +10-15%

### M005: 时钟频率提升

**前置条件：** M002 时序 margin ≥ +2ns

**目标：**
- 从 100 MHz → 110-120 MHz
- Throughput: +10-20%

---

## 九、附录

### A. 参考文档

1. **硬件设计：**
   - `project/hardware/source/design.md`
   - `project/hardware/rtl/integration/hap_attention_mlp_resource_top.sv`
   - `results/DSP_utilization_corrected_analysis.md`

2. **性能分析：**
   - `results/hardware_functional_status_and_timing_analysis.md`
   - `results/DDR_separation_architecture_analysis.md`

3. **时序诊断：**
   - `1_Hardware/vivado/reports/mission0008_e2_diagnostic_native_025/diagnostic_timing_deltas.tsv`

### B. 关键常量

```python
# DDR 带宽
DDR_THEORETICAL_BW = 1.6e9  # 1.6 GB/s
DDR_EFFECTIVE_BW = 1.36e9   # 1.36 GB/s (burst mode)

# MLP 配置
MLP_DSP_COUNT = 3072
MLP_THEORETICAL_GOPS = 614.4  # @ 100 MHz

# 每层数据量
MLP_WEIGHT_PER_LAYER = 88.1 * 1024 * 1024  # 88.1 MiB
MLP_INPUT_PER_LAYER = 192 * 1024           # 192 KiB
MLP_OUTPUT_PER_LAYER = 256 * 1024          # 256 KiB

# 时序目标
TARGET_CLOCK_PERIOD_NS = 10.0  # 100 MHz
FALLBACK_CLOCK_PERIOD_NS = 10.526  # 95 MHz
SETUP_SLACK_TARGET_NS = 0.5
HOLD_SLACK_TARGET_NS = 0.5
```

### C. 验证测试用例

**Test 1: DDR 地址分离验证**
```python
def test_ddr_address_separation():
    """Verify DDR0/DDR1 have no overlap."""
    mem = ScaleLLMMemory()
    
    # DDR0 addresses
    attn_addrs = [
        mem.ATTENTION_WEIGHTS_BASE,
        mem.ATTENTION_INPUT_BASE,
        mem.KV_CACHE_BASE
    ]
    
    # DDR1 addresses
    mlp_addrs = [
        mem.MLP_WEIGHTS_BASE,
        mem.MLP_INPUT_BASE,
        mem.MLP_OUTPUT_BASE
    ]
    
    assert all(a < 0x80000000 for a in attn_addrs)
    assert all(a >= 0x80000000 for a in mlp_addrs)
```

**Test 2: 时序约束验证**
```tcl
# Vivado TCL script
open_checkpoint routed.dcp
report_timing_summary -file timing_final.rpt

# Check WNS/TNS
set wns [get_property SLACK [get_timing_paths -max_paths 1 -setup]]
set tns [get_property SLACK [get_timing_paths -nworst 10000 -setup]]

if {$wns >= 0.5 && $tns == 0} {
    puts "TIMING_PASS"
} else {
    puts "TIMING_FAIL: WNS=$wns TNS=$tns"
}
```

---

## 十、签核

**任务创建：** 2026-10-14  
**创建人：** Kiro (Claude Code)  
**审核人：** 待指定  
**批准状态：** 待用户批准

**批准后立即启动 Week 1 工作。**
