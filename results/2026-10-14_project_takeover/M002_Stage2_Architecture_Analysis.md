# M002 阶段 2：RTL 架构分析

**分析时间：** 2026-10-14  
**目标：** 理解当前 DDR 连接并规划修改

---

## 当前架构分析

### 1. 模块层次结构

```
hap_attention_mlp_resource_top (compute core)
├─ hap_attention_board_core (Attention)
│  ├─ M_AXI_DDR0 → att_d0_* (AR, R channels)
│  └─ M_AXI_DDR1 → att_d1_* (AR, R channels)
│
└─ hap_mlp_full_command16_s54 (MLP)
   ├─ M_AXI_DDR0 → mlp_d0_* (AR, R, AW, W, B channels)
   └─ M_AXI_DDR1 → mlp_d1_* (AR, R, AW, W, B channels)
```

### 2. Block Design 连接（当前）

**Core 模块输出端口：**
```tcl
core/M_AXI_DATA         → d0_smc/S00_AXI  (DDR0)
core/M_AXI_WEIGHT_C0    → d0_smc/S01_AXI  (DDR0)
core/M_AXI_WEIGHT_C1    → d1_smc/S00_AXI  (DDR1)
```

**SmartConnect 仲裁器：**
```
d0_smc (DDR0):
  S00: M_AXI_DATA       (Attention + MLP 数据?)
  S01: M_AXI_WEIGHT_C0  (Channel 0 权重)
  S02: Host PCIe        (Host 访问)
  → M00: DDR0 MIG

d1_smc (DDR1):
  S00: M_AXI_WEIGHT_C1  (Channel 1 权重)
  S01: Host PCIe        (Host 访问)
  → M00: DDR1 MIG
```

### 3. 问题识别

**当前架构的问题：**

1. **M_AXI_DATA 端口含义不明确**
   - 可能同时包含 Attention 和 MLP 的数据访问
   - 连接到 DDR0，但 MLP 也可能需要访问

2. **权重端口 C0/C1 是镜像分布**
   - C0 → DDR0, C1 → DDR1
   - Attention 和 MLP 权重可能都在两个通道上

3. **需要确认内部路由**
   - 查看 `hap_attention_mlp_resource_top.sv` 内部信号
   - 确定 `att_d0/d1` 和 `mlp_d0/d1` 如何映射到外部端口

---

## 端口映射分析

### 查看 resource_top 输出端口

从 `hap_attention_mlp_resource_top.sv` 文件（行 33-80），我看到以下输出端口：

**PCIe/AXI-Lite (控制平面):**
```systemverilog
output wire m_axi_arvalid, m_axi_arready, ...
output wire m_axi_awvalid, m_axi_awready, ...
```

**DDR 数据平面（推测）:**
- 文件中没有直接暴露 `att_d0_*`, `att_d1_*`, `mlp_d0_*`, `mlp_d1_*`
- 说明这些信号在内部被路由/合并了

### 需要查找的内容

1. **Top-level wrapper**
   - 在 BD 中，`core` 是如何实例化的？
   - `core` 的哪些端口映射到 `M_AXI_DATA`, `M_AXI_WEIGHT_C0`, `M_AXI_WEIGHT_C1`？

2. **信号合并逻辑**
   - 是否有 arbiter/mux 将 `att_*` 和 `mlp_*` 信号合并？
   - 合并逻辑在哪里？（resource_top 内部？还是 BD 层？）

---

## 修改策略

### 方案 A：在 resource_top 内部分离（推荐）

**修改位置：** `hap_attention_mlp_resource_top.sv`

**步骤：**
1. 添加 4 个独立的 AXI master 端口：
   ```systemverilog
   // Attention DDR0 (read-only)
   output wire att_ddr0_axi_arvalid, ...
   
   // MLP DDR1 (read-write)
   output wire mlp_ddr1_axi_arvalid, ...
   output wire mlp_ddr1_axi_awvalid, ...
   ```

2. 内部连接：
   ```systemverilog
   // Attention 仅连接 DDR0
   assign att_ddr0_axi_arvalid = att_d0_arvalid;
   assign att_ddr0_axi_araddr = att_d0_araddr;
   // ... 其他 AR, R 信号
   
   // MLP 仅连接 DDR1
   assign mlp_ddr1_axi_arvalid = mlp_d1_arvalid;
   assign mlp_ddr1_axi_araddr = mlp_d1_araddr;
   // ... 其他 AR, R, AW, W, B 信号
   ```

3. 删除未使用的连接：
   - `att_d1_*` (Attention 不再使用 DDR1)
   - `mlp_d0_*` (MLP 不再使用 DDR0)

### 方案 B：在 BD 层重新路由

**修改位置：** `create_attention_mlp_vcu118_dual_ddr_bd.tcl`

**步骤：**
1. 修改 core 端口：
   ```tcl
   # 当前
   core/M_AXI_DATA       → d0_smc/S00_AXI  (DDR0)
   core/M_AXI_WEIGHT_C0  → d0_smc/S01_AXI  (DDR0)
   core/M_AXI_WEIGHT_C1  → d1_smc/S00_AXI  (DDR1)
   
   # 修改后
   core/M_AXI_ATTENTION  → d0_smc/S00_AXI  (DDR0)
   core/M_AXI_MLP        → d1_smc/S00_AXI  (DDR1)
   ```

2. 简化 SmartConnect：
   ```tcl
   d0_smc: 2 slaves (Attention + Host)
   d1_smc: 2 slaves (MLP + Host)
   ```

---

## 推荐方案

**选择方案 A：在 resource_top 内部分离**

**理由：**
1. **更清晰的抽象层次**
   - resource_top 负责 Attention/MLP 分离
   - BD 仅负责物理连接

2. **最小化 BD 修改**
   - BD 是 Vivado 生成的，手动修改容易出错
   - resource_top 是 SystemVerilog，更容易维护

3. **灵活性**
   - 未来可以在 resource_top 内部添加调试逻辑
   - 不影响 BD 结构

**风险：**
- 需要修改 resource_top 的端口列表
- BD 需要重新生成（但修改最小）

---

## 下一步行动

1. **确认当前信号映射**
   - 查看 BD 中 `core` 模块的实际端口
   - 确认 `M_AXI_DATA` 等信号的含义

2. **设计新的端口接口**
   - 定义 `M_AXI_ATTENTION_DDR0`
   - 定义 `M_AXI_MLP_DDR1`

3. **修改 resource_top**
   - 添加新端口
   - 内部信号重新路由
   - 删除未使用的端口

4. **更新 BD 脚本**
   - 修改连接逻辑
   - 简化 SmartConnect 配置

---

**状态：** 分析完成，等待执行修改
**下一步：** 查看 BD 中 core 的实际端口定义
