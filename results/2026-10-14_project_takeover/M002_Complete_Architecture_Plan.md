# M002 完整架构设计与实现计划

**任务：** 设计并实现 DDR 双通道完全分离的完整加速器  
**范围：** 架构设计 → RTL 实现 → 仿真验证 → 综合实现 → 板级测试  
**目标：** 可部署的完整系统

---

## 阶段 0：架构设计与决策 🎯

### 当前系统分析

**现有架构（V5）：**
```
VCU118 Board
├─ PCIe (XDMA)
├─ DDR4_0 (2 GiB @ 300 MHz)
│  └─ SmartConnect (3 slaves)
│     ├─ S0: core/M_AXI_DATA (Attention + MLP 混用)
│     ├─ S1: core/M_AXI_WEIGHT_C0
│     └─ S2: Host PCIe
│
├─ DDR4_1 (2 GiB @ 300 MHz)
│  └─ SmartConnect (2 slaves)
│     ├─ S0: core/M_AXI_WEIGHT_C1
│     └─ S1: Host PCIe
│
└─ Core @ 100 MHz
   ├─ Attention Engine
   │  ├─ 内部：att_d0_*, att_d1_* (read-only)
   │  └─ 路由到：M_AXI_DATA, M_AXI_WEIGHT_C0/C1
   │
   └─ MLP Engine
      ├─ 内部：mlp_d0_*, mlp_d1_* (read-write)
      └─ 路由到：M_AXI_DATA, M_AXI_WEIGHT_C0/C1
```

**问题识别：**
1. `M_AXI_DATA` 被 Attention 和 MLP 共享
2. SmartConnect 仲裁导致冲突
3. 带宽利用率低（DDR 冲突 30%）

---

## 架构设计方案

### 方案对比

#### 方案 A：完全重新设计端口（理想但复杂）

**新架构：**
```
VCU118 Board
├─ DDR4_0 (Attention 专属)
│  └─ SmartConnect (2 slaves)
│     ├─ S0: core/M_AXI_ATTENTION (新端口)
│     └─ S1: Host PCIe
│
├─ DDR4_1 (MLP 专属)
│  └─ SmartConnect (2 slaves)
│     ├─ S0: core/M_AXI_MLP (新端口)
│     └─ S1: Host PCIe
│
└─ Core
   ├─ Attention → M_AXI_ATTENTION (512-bit RO)
   └─ MLP → M_AXI_MLP (512-bit RW)
```

**优点：**
- 完全分离，无冲突
- 架构清晰
- 性能最优

**缺点：**
- 需要修改多层 RTL
- 需要重新生成 BD
- 工作量大（3-5 天）

#### 方案 B：重用现有端口（务实方案）⭐

**改进架构：**
```
保持 3 个端口，重新定义语义：

M_AXI_DATA (256-bit RW) → 改为 "Attention Data"
  ├─ 内部：仅连接 Attention I/O
  ├─ 外部：连接 d0_smc → DDR0
  └─ 用途：Attention Input/Output/KV cache

M_AXI_WEIGHT_C0 (512-bit RO) → 改为 "Attention Weights"
  ├─ 内部：仅连接 Attention 权重读取
  ├─ 外部：连接 d0_smc → DDR0
  └─ 用途：Attention Q/K/V/O 权重

M_AXI_WEIGHT_C1 (512-bit RO+RW) → 改为 "MLP Channel"
  ├─ 内部：连接 MLP 全部访问（权重+数据）
  ├─ 外部：连接 d1_smc → DDR1
  └─ 用途：MLP Gate/Up/Down 权重 + I/O
  ⚠️ 需要升级为 read-write
```

**优点：**
- 保持端口数量不变
- BD 修改最小
- 工作量适中（1-2 天）

**缺点：**
- M_AXI_WEIGHT_C1 需要升级为读写
- 需要仔细的信号路由

---

## 选择方案 B：务实方案

**理由：**
1. 工作量可控（1-2 天）
2. 复用现有基础设施
3. 效果充分（完全分离）
4. 风险适中

---

## 详细实现计划

### 阶段 1：RTL 内部信号重路由 (6-8 小时)

#### 1.1 分析当前信号路由

**需要查看的文件：**
```
hap_attention_mlp_resource_top.sv
  ├─ Attention 输出：att_d0_*, att_d1_*
  ├─ MLP 输出：mlp_d0_*, mlp_d1_*
  └─ 如何路由到 3 个外部端口？
  
hap_attention_mlp_production_core.sv
  ├─ 可能有内部 arbiter/mux
  └─ 需要理解信号流
  
hap_attention_mlp_board_core.sv
  ├─ 3 个 AXI master 端口
  └─ 如何连接到 production_core？
```

**行动：** 读取并绘制完整的信号流图

#### 1.2 修改 resource_top 内部路由

**文件：** `hap_attention_mlp_resource_top.sv`

**修改内容：**
```systemverilog
// 当前（推测）：可能有类似这样的路由
// wire combined_data = (attention_request) ? att_data : mlp_data;

// 新设计：完全分离
// Attention → 仅使用 att_d0
// MLP → 仅使用 mlp_d1

// 1. Attention 路由（仅 DDR0）
assign attention_data_ar* = att_d0_ar*;  // Read address
assign attention_data_r*  = att_d0_r*;   // Read data
assign att_d0_arready = attention_data_arready;
assign att_d0_rvalid = attention_data_rvalid;
// ... 其他信号

// 2. Attention 权重路由（仅 DDR0）
assign attention_weight_ar* = att_d0_ar*;  // 如果有独立权重端口
// 或者合并到 attention_data

// 3. MLP 路由（仅 DDR1，需要 RW）
assign mlp_ar* = mlp_d1_ar*;   // Read address
assign mlp_r*  = mlp_d1_r*;    // Read data
assign mlp_aw* = mlp_d1_aw*;   // Write address ← 关键！
assign mlp_w*  = mlp_d1_w*;    // Write data   ← 关键！
assign mlp_b*  = mlp_d1_b*;    // Write response
```

**关键修改：**
1. 删除 Attention 对 DDR1 的所有连接（att_d1_*）
2. 删除 MLP 对 DDR0 的所有连接（mlp_d0_*）
3. 确保 MLP 有完整的读写通道

#### 1.3 修改 production_core 层

**文件：** `hap_attention_mlp_production_core.sv`

**修改：** 移除可能存在的内部 arbiter/mux

#### 1.4 修改 board_core 层

**文件：** `hap_attention_mlp_board_core.sv`

**修改端口语义（不改名字）：**
```systemverilog
// M_AXI_DATA → Attention Data (DDR0)
// 输入：来自 Attention I/O
// 输出：到 DDR0 SmartConnect

// M_AXI_WEIGHT_C0 → Attention Weights (DDR0)
// 输入：来自 Attention 权重读取
// 输出：到 DDR0 SmartConnect

// M_AXI_WEIGHT_C1 → MLP All (DDR1)
// 输入：来自 MLP 全部访问
// 输出：到 DDR1 SmartConnect
// ⚠️ 需要确保有 AW, W, B 通道（当前可能只有 AR, R）
```

**关键：** 检查 M_AXI_WEIGHT_C1 是否已有写通道

---

### 阶段 2：BD 层修改 (2-4 小时)

#### 2.1 更新 SmartConnect 配置

**文件：** `create_attention_mlp_vcu118_dual_ddr_bd.tcl`

**修改：**
```tcl
# 当前配置
d0_smc: 3 slaves (DATA, WEIGHT_C0, Host)
d1_smc: 2 slaves (WEIGHT_C1, Host)

# 新配置（可能需要调整）
d0_smc: 3 slaves
  S0: M_AXI_DATA (Attention Data)
  S1: M_AXI_WEIGHT_C0 (Attention Weights)
  S2: Host PCIe

d1_smc: 2 slaves
  S0: M_AXI_WEIGHT_C1 (MLP All, 确保支持写)
  S1: Host PCIe
```

**关键：** 验证 M_AXI_WEIGHT_C1 的 SmartConnect 配置支持读写

#### 2.2 重新生成 BD

```bash
cd /path/to/vivado/scripts
source create_attention_mlp_vcu118_dual_ddr_v5_bd.tcl
```

---

### 阶段 3：RTL 仿真验证 (4-6 小时)

#### 3.1 创建 Testbench

**文件：** `tb_ddr_separation.sv`

**测试场景：**
```systemverilog
// Scenario 1: Attention 访问
task test_attention_access();
  // 1. 触发 Attention 读取
  attention_trigger = 1'b1;
  @(posedge clk);
  
  // 2. 监控 M_AXI_DATA (应该活跃)
  wait(m_axi_data_arvalid == 1'b1);
  assert(m_axi_data_araddr < 32'h8000_0000) 
    else $error("Attention accessing DDR1!");
  
  // 3. 监控 M_AXI_WEIGHT_C1 (应该空闲)
  assert(m_axi_weight_c1_arvalid == 1'b0)
    else $error("MLP active during Attention!");
endtask

// Scenario 2: MLP 访问
task test_mlp_access();
  // 1. 触发 MLP 读取
  mlp_trigger = 1'b1;
  @(posedge clk);
  
  // 2. 监控 M_AXI_WEIGHT_C1 (应该活跃)
  wait(m_axi_weight_c1_arvalid == 1'b1);
  assert(m_axi_weight_c1_araddr >= 32'h8000_0000)
    else $error("MLP accessing DDR0!");
  
  // 3. 监控 M_AXI_DATA (应该空闲)
  assert(m_axi_data_arvalid == 1'b0)
    else $error("Attention active during MLP!");
endtask

// Scenario 3: 写操作验证
task test_mlp_write();
  // MLP 写操作应该在 M_AXI_WEIGHT_C1 上
  mlp_write_trigger = 1'b1;
  @(posedge clk);
  
  wait(m_axi_weight_c1_awvalid == 1'b1);
  assert(m_axi_weight_c1_awaddr >= 32'h8000_0000)
    else $error("MLP write to wrong DDR!");
endtask
```

#### 3.2 运行仿真

```bash
cd /path/to/vivado
vivado -mode batch -source run_tb_ddr_separation.tcl
```

**验收标准：**
- [ ] Attention 仅访问 DDR0 地址 (< 0x8000_0000)
- [ ] MLP 仅访问 DDR1 地址 (≥ 0x8000_0000)
- [ ] MLP 写操作正确路由到 DDR1
- [ ] 无信号冲突或 X 态

---

### 阶段 4：Elaboration 验证 (1 小时)

```tcl
# Vivado 中快速验证连接
read_verilog -sv [glob rtl/**/*.sv]
synth_design -top hap_attention_mlp_board_core -mode out_of_context -part xcvu9p-flga2104-2L-e

# 检查连接
report_methodology
```

**验收标准：**
- [ ] Elaboration 通过，无 error
- [ ] 无 unconnected pins
- [ ] 无 multi-driven nets

---

### 阶段 5：综合 (2-3 小时)

```bash
cd vivado/scripts
vivado -mode batch -source synth_attention_mlp_board_core.tcl
```

**验收标准：**
- [ ] Synthesis 完成
- [ ] 无 Critical Warning
- [ ] 资源利用率 < 95%
- [ ] Post-synth timing 估算合理

---

### 阶段 6：完整实现 (6-8 小时)

#### 6.1 Implementation

```tcl
# Place
place_design -directive SSI_SpreadLogic_high

# Phys Opt
phys_opt_design -directive AggressiveExplore

# Route
route_design -directive AggressiveExplore
```

#### 6.2 时序验证

**目标：**
- Setup WNS ≥ 0 ns @ 100 MHz
- Hold WNS ≥ 0 ns
- TNS = 0

**Fallback：** 95 MHz（如果 100 MHz 不收敛）

#### 6.3 DRC 检查

```tcl
report_drc -file drc_final.rpt
```

**验收标准：**
- [ ] 0 critical violations
- [ ] Route 100% 完成

---

### 阶段 7：Bitstream 生成 (30 分钟)

```tcl
write_bitstream -force scalellm_v5_m002.bit
```

---

### 阶段 8：板级测试 (2-4 小时)

#### 8.1 加载 Bitstream

```bash
vivado -mode tcl
program_hw_devices [current_hw_device] -force \
  -file scalellm_v5_m002.bit
```

#### 8.2 功能测试

```python
# Python 测试脚本
from scalellm_hardware import ScaleLLMBoard
from ddr_access_logger import get_global_logger

board = ScaleLLMBoard()
board.connect()

# DDR 初始化
board.ddr_init()

# 运行 1-token 测试
result = board.run_single_token_inference(layer=0)

# 验证 DDR 访问
logger = get_global_logger()
stats = logger.get_statistics()

assert stats['separation_ok'], "DDR 分离验证失败"
print(f"✅ DDR 分离验证通过")
```

#### 8.3 性能测试

```python
# 32 层完整推理
throughput = board.run_full_inference(num_tokens=16)

print(f"吞吐量: {throughput:.2f} tokens/s")
print(f"目标: ≥ 3.2 tokens/s")

assert throughput >= 3.2, "性能不达标"
```

---

## 总时间估算

| 阶段 | 任务 | 预计时间 | 累计 |
|---|---|---|---|
| 1 | RTL 信号重路由 | 6-8 小时 | 8h |
| 2 | BD 修改 | 2-4 小时 | 12h |
| 3 | RTL 仿真验证 | 4-6 小时 | 18h |
| 4 | Elaboration | 1 小时 | 19h |
| 5 | 综合 | 2-3 小时 | 22h |
| 6 | 完整实现 | 6-8 小时 | 30h |
| 7 | Bitstream | 0.5 小时 | 30.5h |
| 8 | 板级测试 | 2-4 小时 | 34h |
| **总计** | | **~34 小时** | **~4-5 天** |

**考虑调试和迭代：** 预计 **1-2 周**

---

## 关键风险与缓解

### 风险 1：M_AXI_WEIGHT_C1 不支持写

**症状：** 端口只有 AR/R 通道，没有 AW/W/B

**缓解：**
- Plan A：添加写通道（需要修改接口）
- Plan B：使用 M_AXI_DATA 作为 MLP 数据通道（需要重新设计）

### 风险 2：时序不收敛

**缓解：**
- 应用 `ddr_timing_recovery.xdc`
- 降频到 95 MHz
- 调整 floorplan

### 风险 3：仿真发现功能 bug

**缓解：**
- 充分的仿真覆盖
- 分阶段测试
- 保留回滚点

---

## 验收标准（完整）

### RTL 验收
- [ ] 信号路由正确
- [ ] Elaboration 通过
- [ ] 仿真验证通过
- [ ] Attention 仅连接 DDR0
- [ ] MLP 仅连接 DDR1

### 综合验收
- [ ] Synthesis 完成
- [ ] 无 Critical Warning
- [ ] 资源利用率 < 95%

### 实现验收
- [ ] Place + Route 完成
- [ ] Setup WNS ≥ 0 ns
- [ ] Hold WNS ≥ 0 ns
- [ ] DRC 全绿

### 板级验收
- [ ] Bitstream 加载成功
- [ ] DDR 初始化成功
- [ ] 1-token 测试通过
- [ ] 32 层推理成功
- [ ] 吞吐量 ≥ 3.2 tokens/s
- [ ] DDR 分离验证通过

---

## 下一步行动

**立即开始：**
1. 阶段 1.1：分析当前信号路由
   - 读取 `hap_attention_mlp_resource_top.sv`
   - 绘制完整信号流图
   - 理解当前架构

2. 基于分析结果决定：
   - 方案 B 是否可行？
   - M_AXI_WEIGHT_C1 是否支持写？
   - 是否需要调整方案？

**我现在开始阶段 1.1：分析信号路由吗？**
