# M002 RTL 修改完成报告

**完成时间：** 2026-10-14  
**状态：** ✅ RTL 修改完成

---

## 修改总结

### 修改文件

**文件：** `hap_attention_mlp_production_core.sv`

**备份：** `hap_attention_mlp_production_core.sv.backup_m002_20261014_*`

**修改内容：**
1. 添加 M002 修改说明注释（行 1-23）
2. 修改 `hap_axi512_paired_2client_read_wrr` 实例化（行 ~392-423）
   - 禁用 `att_d1` (Attention DDR1)
   - 禁用 `mlp_d0` (MLP DDR0)
   - 保持 `att_d0` (Attention DDR0) ✅
   - 保持 `mlp_d1` (MLP DDR1) ✅

**修改行数：** ~30 行

---

## 修改详情

### Before (原始连接)

```systemverilog
hap_axi512_paired_2client_read_wrr u_paired_weight(
  // ...
  .a0_arvalid(att_d0_arvalid), ... // Attention DDR0
  .m0_arvalid(mlp_d0_arvalid), ... // MLP DDR0 ← 冲突
  .a1_arvalid(att_d1_arvalid), ... // Attention DDR1 ← 冲突
  .m1_arvalid(mlp_d1_arvalid), ... // MLP DDR1
  // ...
);
```

**问题：**
- `p0` (DDR0) = `att_d0` + `mlp_d0` → 冲突
- `p1` (DDR1) = `att_d1` + `mlp_d1` → 冲突

### After (M002 修改)

```systemverilog
hap_axi512_paired_2client_read_wrr u_paired_weight(
  // ...
  
  // Attention → DDR0 only
  .a0_arvalid(att_d0_arvalid), ... // ✅ ENABLED
  
  // MLP DDR0 DISABLED
  .m0_arvalid(1'b0), ...           // ❌ DISABLED (tie to 0)
  
  // Attention DDR1 DISABLED
  .a1_arvalid(1'b0), ...           // ❌ DISABLED (tie to 0)
  
  // MLP → DDR1 only
  .m1_arvalid(mlp_d1_arvalid), ... // ✅ ENABLED
  // ...
);
```

**结果：**
- `p0` (DDR0) = `att_d0` only → 无冲突 ✅
- `p1` (DDR1) = `mlp_d1` only → 无冲突 ✅

---

## 架构变更

### 信号流（修改后）

```
┌─────────────────────────────────────────────────────────────┐
│ Resource Top                                                │
│                                                             │
│  Attention Module                    MLP Module            │
│  ├─ att_d0_* ✅                      ├─ mlp_d0_* ❌        │
│  └─ att_d1_* ❌                      └─ mlp_d1_* ✅        │
└─────────────────┬───────────────────────────┬───────────────┘
                  │                           │
                  ↓                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Production Core: u_paired_weight (Scheduler)                │
│                                                             │
│  a0 ← att_d0 ✅         m0 ← DISABLED ❌                   │
│  a1 ← DISABLED ❌       m1 ← mlp_d1 ✅                     │
│                                                             │
│  p0 = a0 only           p1 = m1 only                       │
└─────────────────┬───────────────────────────┬───────────────┘
                  │                           │
                  ↓                           ↓
          ddr0_axi (DDR0)           ddr1_axi (DDR1)
                  │                           │
                  ↓                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Board Core                                                  │
│                                                             │
│  M_AXI_WEIGHT_C0 → DDR0 SmartConnect → DDR0 MIG           │
│  M_AXI_WEIGHT_C1 → DDR1 SmartConnect → DDR1 MIG           │
└─────────────────────────────────────────────────────────────┘
```

**完全分离：**
- ✅ Attention 仅访问 DDR0
- ✅ MLP 仅访问 DDR1
- ✅ 零冲突

---

## 下一步：验证流程

### 阶段 1：语法检查 (10 分钟)

```bash
cd /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM
vivado -mode tcl

# Vivado TCL
read_verilog -sv project/hardware/rtl/integration/hap_attention_mlp_production_core.sv
check_syntax
```

**预期：** 无语法错误

### 阶段 2：Elaboration (20 分钟)

```tcl
# 读取所有依赖文件
read_verilog -sv [glob project/hardware/rtl/**/*.sv]

# Elaborate
synth_design -top hap_attention_mlp_production_core \
  -mode out_of_context \
  -part xcvu9p-flga2104-2L-e

# 检查
report_methodology
report_drc
```

**验收标准：**
- [ ] Elaboration 成功
- [ ] 无 critical warning
- [ ] 无 unconnected pins（除了悬空的 `a1_arready`, `m0_arready` 等）
- [ ] 无 multi-driven nets

### 阶段 3：RTL 仿真 (4-6 小时)

**创建 Testbench：** `tb_m002_ddr_separation.sv`

```systemverilog
`timescale 1ns / 1ps

module tb_m002_ddr_separation;
  
  // Clock and reset
  reg core_clk = 0;
  reg core_rst_n = 0;
  reg ddr0_clk = 0;
  reg ddr1_clk = 0;
  
  always #5 core_clk = ~core_clk; // 100 MHz
  always #1.667 ddr0_clk = ~ddr0_clk; // 300 MHz
  always #1.667 ddr1_clk = ~ddr1_clk; // 300 MHz
  
  // DUT
  hap_attention_mlp_production_core u_dut (
    .core_clk(core_clk),
    .core_rst_n(core_rst_n),
    // ... 连接其他端口
  );
  
  // Test sequence
  initial begin
    $display("M002 DDR Separation Test");
    
    // Reset
    #100 core_rst_n = 1;
    #100;
    
    // Test 1: Attention access
    $display("Test 1: Trigger Attention");
    trigger_attention();
    #1000;
    check_ddr0_active();
    check_ddr1_idle();
    
    // Test 2: MLP access
    $display("Test 2: Trigger MLP");
    trigger_mlp();
    #1000;
    check_ddr1_active();
    check_ddr0_idle();
    
    // Test 3: Simultaneous (should not conflict)
    $display("Test 3: Simultaneous Attention + MLP");
    fork
      trigger_attention();
      trigger_mlp();
    join
    #2000;
    check_no_conflict();
    
    $display("✅ All tests passed");
    $finish;
  end
  
  task check_ddr0_active();
    assert(u_dut.ddr0_axi_arvalid == 1'b1)
      else $fatal("DDR0 not active");
  endtask
  
  task check_ddr1_active();
    assert(u_dut.ddr1_axi_arvalid == 1'b1)
      else $fatal("DDR1 not active");
  endtask
  
  task check_ddr0_idle();
    assert(u_dut.ddr0_axi_arvalid == 1'b0)
      else $fatal("DDR0 should be idle");
  endtask
  
  task check_ddr1_idle();
    assert(u_dut.ddr1_axi_arvalid == 1'b0)
      else $fatal("DDR1 should be idle");
  endtask
  
endmodule
```

**运行：**
```bash
xvlog -sv tb_m002_ddr_separation.sv
xelab -debug typical tb_m002_ddr_separation
xsim tb_m002_ddr_separation -runall
```

### 阶段 4：综合 (2-3 小时)

```bash
vivado -mode batch -source vivado/scripts/synth_attention_mlp_production_core.tcl
```

**检查：**
- [ ] Synthesis 完成
- [ ] 资源利用率变化 < 5%
- [ ] 无新增 critical warning

### 阶段 5：完整实现 (6-8 小时)

```bash
# 运行完整 BD 生成
cd vivado/scripts
source create_attention_mlp_vcu118_dual_ddr_v5_bd.tcl

# 添加时序约束
add_files -fileset constrs_1 \
  ../../project/hardware/vivado/constraints/ddr_timing_recovery.xdc

# 综合 + 实现
vivado -mode batch -source build_attention_mlp_vcu118_v5_bitstream.tcl
```

**预计时间：** 6-8 小时

**验收标准：**
- [ ] Place + Route 完成
- [ ] Setup WNS ≥ 0 ns @ 100 MHz
- [ ] Hold WNS ≥ 0 ns
- [ ] DRC 全绿

### 阶段 6：Bitstream 生成 (30 分钟)

```tcl
write_bitstream -force scalellm_v5_m002.bit
```

### 阶段 7：板级测试 (2-4 小时)

```bash
# 加载 bitstream
vivado -mode tcl
program_hw_devices [current_hw_device] -force \
  -file scalellm_v5_m002.bit

# Python 测试
cd project/hardware/host
python3 test_ddr_separation_full.py
```

**验收标准：**
- [ ] Bitstream 加载成功
- [ ] DDR 初始化成功
- [ ] 1-token 测试通过
- [ ] 32 层推理成功
- [ ] 吞吐量 ≥ 3.2 tokens/s
- [ ] DDR 分离验证通过（0% 冲突）

---

## 时间估算（完整流程）

| 阶段 | 任务 | 预计时间 | 累计 |
|---|---|---|---|
| ✅ | RTL 修改 | 30 分钟 | 0.5h |
| 1 | 语法检查 | 10 分钟 | 0.67h |
| 2 | Elaboration | 20 分钟 | 1h |
| 3 | RTL 仿真 | 4-6 小时 | 7h |
| 4 | 综合 | 2-3 小时 | 10h |
| 5 | 完整实现 | 6-8 小时 | 18h |
| 6 | Bitstream | 30 分钟 | 18.5h |
| 7 | 板级测试 | 2-4 小时 | 22h |
| **总计** | | **~22 小时** | **~3 天** |

---

## 立即行动

**现在应该执行：**

### 选项 A：快速验证（推荐先做）
1. 语法检查（10 分钟）
2. Elaboration（20 分钟）
3. 确认无 critical 问题

### 选项 B：完整流程（如果快速验证通过）
1. 编写 testbench
2. RTL 仿真
3. 综合
4. 实现
5. 板级测试

---

## 当前状态

**完成：**
- ✅ 架构设计
- ✅ RTL 修改
- ✅ 代码备份

**待完成：**
- ⏸ 语法检查
- ⏸ Elaboration
- ⏸ 仿真验证
- ⏸ 综合实现
- ⏸ 板级测试

---

**我现在应该进行语法检查和 Elaboration 吗？**
