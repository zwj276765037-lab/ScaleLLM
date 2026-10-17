# M002 信号流分析报告

**分析时间：** 2026-10-14  
**文件：** `hap_attention_mlp_resource_top.sv`

---

## 关键发现 🎯

### 1. 当前架构已经部分分离！

**重大发现：** `resource_top` 已经暴露了 **4 个独立的 DDR 端口**：

```systemverilog
// Attention 端口（只读，512-bit）
output wire att_d0_arvalid, att_d0_arready, ... // DDR0 read
output wire att_d1_arvalid, att_d1_arready, ... // DDR1 read

// MLP 端口（只读，512-bit）
output wire mlp_d0_arvalid, mlp_d0_arready, ... // DDR0 read
output wire mlp_d1_arvalid, mlp_d1_arready, ... // DDR1 read
```

**关键问题：** 这 4 个端口如何连接到上层的 3 个端口？

---

## 完整信号流分析

### Layer 1: Resource Top（当前文件）

```
hap_attention_mlp_resource_top
├─ Attention 模块：hap_attention_board_core
│  ├─ 输入：
│  │  ├─ m_axi_* (256-bit RW) ← PCIe/Host 数据通道
│  │  ├─ ddr0_axi_* (512-bit RO) ← 连接到 att_d0_*
│  │  └─ ddr1_axi_* (512-bit RO) ← 连接到 att_d1_*
│  └─ 输出：
│     ├─ att_d0_arvalid, att_d0_araddr, ... (DDR0 read)
│     └─ att_d1_arvalid, att_d1_araddr, ... (DDR1 read)
│
└─ MLP 模块：hap_mlp_full_command16_s54
   ├─ 输入：
   │  ├─ mlp_input_* ← 来自 Host（通过 PCIe）
   │  ├─ mlp_command_* ← 命令接口
   │  ├─ gate_ddr0_base_addr, gate_ddr1_base_addr
   │  ├─ down_ddr0_base_addr, down_ddr1_base_addr
   │  ├─ ddr0_axi_* (512-bit RO) ← 连接到 mlp_d0_*
   │  └─ ddr1_axi_* (512-bit RO) ← 连接到 mlp_d1_*
   └─ 输出：
      ├─ mlp_d0_arvalid, mlp_d0_araddr, ... (DDR0 read)
      └─ mlp_d1_arvalid, mlp_d1_araddr, ... (DDR1 read)
```

**关键观察：**
1. ✅ Attention 和 MLP 已经有**独立的 DDR 端口**
2. ✅ 两者都有 `ddr0` 和 `ddr1` 访问能力
3. ⚠️ 所有端口都是**只读**（只有 AR, R 通道，无 AW, W, B）
4. ⚠️ Attention 有额外的 `m_axi_*` 端口（256-bit RW）用于数据

---

### Layer 2: Production Core（推测）

**文件：** `hap_attention_mlp_production_core.sv`（需要查看）

**推测的功能：**
```
可能存在信号合并/仲裁逻辑：

att_d0_* + mlp_d0_* → M_AXI_WEIGHT_C0 (512-bit RO) → DDR0
att_d1_* + mlp_d1_* → M_AXI_WEIGHT_C1 (512-bit RO) → DDR1
attention.m_axi_*   → M_AXI_DATA (256-bit RW) → DDR0
```

---

### Layer 3: Board Core（已知）

**文件：** `hap_attention_mlp_board_core.sv`

**3 个 AXI Master 端口：**
```systemverilog
// Port 1: M_AXI_DATA (256-bit RW)
// 用途：Attention 数据 I/O
// 连接：→ d0_smc → DDR0

// Port 2: M_AXI_WEIGHT_C0 (512-bit RO)
// 用途：合并的 DDR0 权重访问（Attention + MLP）
// 连接：→ d0_smc → DDR0

// Port 3: M_AXI_WEIGHT_C1 (512-bit RO)
// 用途：合并的 DDR1 权重访问（Attention + MLP）
// 连接：→ d1_smc → DDR1
```

---

## 问题分析

### 问题 1：权重端口共享

**当前：**
```
M_AXI_WEIGHT_C0 (DDR0) ← att_d0 + mlp_d0 (通过仲裁/mux)
M_AXI_WEIGHT_C1 (DDR1) ← att_d1 + mlp_d1 (通过仲裁/mux)
```

**结果：** Attention 和 MLP 竞争同一个 DDR 通道

### 问题 2：MLP 无写通道

**观察：** MLP 端口只有 AR/R（read），没有 AW/W/B（write）

**影响：**
- MLP 输出如何写回？
- 可能通过 Attention 的 `m_axi_*` (RW) 端口？
- 或者 MLP 输出通过流式接口（`mlp_out_*`）直接到 Host？

### 问题 3：地址路由逻辑未知

**需要确认：**
- `att_d0` vs `att_d1` 如何选择？（基于地址？）
- `mlp_d0` vs `mlp_d1` 如何选择？
- 仲裁逻辑在哪一层？

---

## 修改方案（修订）

### 方案 C：利用现有 4 端口架构 ⭐⭐⭐

**关键洞察：** 硬件已经有 4 个独立端口，我们只需要：
1. 禁用 Attention 的 DDR1 端口（`att_d1`）
2. 禁用 MLP 的 DDR0 端口（`mlp_d0`）
3. 更新上层路由逻辑

**新架构：**
```
Resource Top (本层修改):
├─ att_d0_* (enabled)  → 路由到 M_AXI_WEIGHT_C0 → DDR0
├─ att_d1_* (disabled) → tie to 0
├─ mlp_d0_* (disabled) → tie to 0
└─ mlp_d1_* (enabled)  → 路由到 M_AXI_WEIGHT_C1 → DDR1

Attention m_axi_* (RW) → M_AXI_DATA → DDR0 (保持)
```

**优点：**
- 最小化修改（仅在 `resource_top` 层）
- 无需修改 Attention/MLP 内部
- 无需修改 BD 层

**需要解决：**
- MLP 写操作路由（如果需要）

---

## 下一步行动

### 立即任务

1. **查看 `hap_attention_mlp_production_core.sv`**
   - 确认信号合并逻辑
   - 理解仲裁机制

2. **确认 MLP 写操作**
   - MLP 输出如何写回？
   - 是否需要写通道？

3. **基于分析更新方案**

---

## 修改预览（方案 C）

### 文件：`hap_attention_mlp_resource_top.sv`

**修改 1：禁用 att_d1**
```systemverilog
// 原代码（行 77-82）：
output wire att_d1_arvalid, ...
input wire att_d1_rvalid, ...

// 修改后：
// output wire att_d1_arvalid, ...  // 删除或注释
// input wire att_d1_rvalid, ...    // 删除或注释

// 内部连接：tie to 0
assign att_d1_arvalid = 1'b0;
assign att_d1_araddr = 32'h0;
// ... 其他信号 tie to 0
```

**修改 2：禁用 mlp_d0**
```systemverilog
// 原代码（行 83-88）：
output wire mlp_d0_arvalid, ...
input wire mlp_d0_rvalid, ...

// 修改后：
assign mlp_d0_arvalid = 1'b0;
assign mlp_d0_araddr = 32'h0;
// ... 其他信号 tie to 0
```

**修改 3：更新 Attention 实例化（行 96-140）**
```systemverilog
u_attention(
  // ... 其他端口
  
  // DDR0 保持连接
  .ddr0_axi_arvalid(att_d0_arvalid),
  .ddr0_axi_arready(att_d0_arready),
  // ...
  
  // DDR1 断开连接
  .ddr1_axi_arvalid(),  // 悬空（内部生成但未使用）
  .ddr1_axi_arready(1'b0),  // 永远 not ready
  .ddr1_axi_rvalid(1'b0),
  .ddr1_axi_rdata(512'h0),
  // ...
);
```

**修改 4：更新 MLP 实例化（行 152-214）**
```systemverilog
u_mlp(
  // ... 其他端口
  
  // DDR0 断开连接
  .ddr0_axi_arvalid(),  // 悬空
  .ddr0_axi_arready(1'b0),
  .ddr0_axi_rvalid(1'b0),
  .ddr0_axi_rdata(512'h0),
  // ...
  
  // DDR1 保持连接
  .ddr1_axi_arvalid(mlp_d1_arvalid),
  .ddr1_axi_arready(mlp_d1_arready),
  // ...
);
```

---

## 预期结果

**修改后的信号流：**
```
Attention:
├─ m_axi_* (256-bit RW) → M_AXI_DATA → DDR0 (数据)
└─ att_d0_* (512-bit RO) → M_AXI_WEIGHT_C0 → DDR0 (权重)

MLP:
└─ mlp_d1_* (512-bit RO) → M_AXI_WEIGHT_C1 → DDR1 (全部)
```

**验证：**
- Attention 仅访问 DDR0 ✅
- MLP 仅访问 DDR1 ✅
- 完全分离 ✅

---

## 风险与未知

### 未知 1：Production Core 层的逻辑

**风险：** 可能有硬编码的信号路由需要修改

**缓解：** 查看 `production_core.sv` 确认

### 未知 2：MLP 写操作

**风险：** MLP 可能需要写通道但当前没有

**缓解：**
- 确认 MLP 输出路径
- 如果是流式输出到 Host，则无问题
- 如果需要写 DDR，需要添加写通道

### 未知 3：地址生成逻辑

**风险：** Attention/MLP 内部如何决定访问 ddr0 vs ddr1？

**缓解：**
- 读取 Attention/MLP 模块代码
- 确认是否基于地址高位选择

---

## 状态与建议

**当前进度：** 信号流分析完成 60%

**下一步：**
1. 查看 `hap_attention_mlp_production_core.sv`（如果存在）
2. 确认 MLP 写操作路径
3. 基于完整分析决定最终方案

**推荐方案：** 方案 C（利用现有 4 端口）

**预计工作量：**
- 代码修改：2-4 小时
- 仿真验证：4-6 小时
- 总计：1 天

**我现在应该查看 `production_core.sv` 吗？**
