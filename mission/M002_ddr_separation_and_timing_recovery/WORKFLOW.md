# M002 工作流程：DDR 双通道分离 + 布线时序修复

> 历史计划保留，不能作为当前运行入口。当前用户授权、接口和验证顺序见 [2026-10-15执行合同](repair_contract_2026-10-15.md)。下文旧地址、推测RTL、native025继续路由及验收模板不表示当前方案或已通过结果。

**目标：** 3.5 tokens/s (+40%)  
**优先级：** 🔴 P0 CRITICAL  
**预计工期：** 1 周

---

## 工作流程总览

```
阶段 1: DDR 双通道分离实现
  ↓
阶段 2: 布线时序修复
  ↓
阶段 3: 综合与实现
  ↓
阶段 4: 部署与验收
```

---

## 阶段 1：DDR 双通道分离实现

### 1.1 地址映射重新设计

**目标：** DDR0 专属 Attention，DDR1 专属 MLP

**文件：** `project/hardware/host/scalellm_memory.py`

**当前地址：**
```python
# 混合在 DDR0
ATTENTION_INPUT_BASE = 0x40000000
MLP_INPUT_BASE = 0x4C000000
KV_CACHE_BASE = 0x80000000  # DDR1
```

**新地址映射：**
```python
# DDR0 (Attention 专属) - 0x0000_0000 ~ 0x7FFF_FFFF
DDR0_BASE = 0x00000000
ATTENTION_WEIGHTS_BASE = DDR0_BASE                    # 0x0000_0000
ATTENTION_INPUT_BASE = DDR0_BASE + 0x20800000        # 0x2080_0000
ATTENTION_OUTPUT_BASE = DDR0_BASE + 0x20A00000       # 0x20A0_0000
KV_CACHE_BASE = DDR0_BASE + 0x20000000               # 0x2000_0000

# DDR1 (MLP 专属) - 0x8000_0000 ~ 0xFFFF_FFFF
DDR1_BASE = 0x80000000
MLP_WEIGHTS_BASE = DDR1_BASE                         # 0x8000_0000
MLP_INPUT_BASE = DDR1_BASE + 0x20000000              # 0xA000_0000
MLP_OUTPUT_BASE = DDR1_BASE + 0x20200000             # 0xA020_0000
MLP_METADATA_BASE = DDR1_BASE + 0x20480000           # 0xA048_0000

def validate_address_separation():
    """验证 DDR0/DDR1 地址无重叠。"""
    ddr0_addrs = [ATTENTION_WEIGHTS_BASE, ATTENTION_INPUT_BASE, 
                  ATTENTION_OUTPUT_BASE, KV_CACHE_BASE]
    ddr1_addrs = [MLP_WEIGHTS_BASE, MLP_INPUT_BASE, 
                  MLP_OUTPUT_BASE, MLP_METADATA_BASE]
    
    assert all(addr < DDR1_BASE for addr in ddr0_addrs), "DDR0 地址错误"
    assert all(addr >= DDR1_BASE for addr in ddr1_addrs), "DDR1 地址错误"
```

**验收标准：**
- [ ] 所有 Attention 地址 < 0x8000_0000
- [ ] 所有 MLP 地址 ≥ 0x8000_0000
- [ ] 单元测试通过

---

### 1.2 Host 驱动适配

**文件：** `project/hardware/host/scalellm_hardware.py`

**修改内容：**
```python
def send_attention_input(self, cohort: int, layer: int, data: np.ndarray):
    """发送 Attention 输入到 DDR0。"""
    addr = self._get_attention_input_addr(cohort, layer)
    assert addr < 0x80000000, "Attention 必须使用 DDR0"
    self.dma_write(addr, pack_s24_q16(data))
    self._log_ddr_access("DDR0", "Attention Input", addr, len(data))

def send_mlp_input(self, cohort: int, layer: int, data: np.ndarray):
    """发送 MLP 输入到 DDR1。"""
    addr = self._get_mlp_input_addr(cohort, layer)
    assert addr >= 0x80000000, "MLP 必须使用 DDR1"
    self.dma_write(addr, pack_s24_q16(data))
    self._log_ddr_access("DDR1", "MLP Input", addr, len(data))

def _log_ddr_access(self, channel: str, op: str, addr: int, size: int):
    """记录 DDR 访问，用于验证分离效果。"""
    self._ddr_log.append({
        "channel": channel,
        "operation": op,
        "address": f"0x{addr:08X}",
        "size": size,
        "timestamp": time.time()
    })

def get_ddr_separation_stats(self):
    """获取 DDR 分离统计。"""
    ddr0_count = sum(1 for x in self._ddr_log if x["channel"] == "DDR0")
    ddr1_count = sum(1 for x in self._ddr_log if x["channel"] == "DDR1")
    return {
        "ddr0_accesses": ddr0_count,
        "ddr1_accesses": ddr1_count,
        "separation_ratio": ddr0_count / (ddr0_count + ddr1_count) if ddr0_count else 0
    }
```

**验收标准：**
- [ ] Attention 操作仅访问 DDR0
- [ ] MLP 操作仅访问 DDR1
- [ ] 统计接口工作正常

---

### 1.3 RTL Top-Level 修改

**文件：** `project/hardware/rtl/integration/hap_attention_mlp_resource_top.sv`

**当前设计（推测）：**
```systemverilog
// 共享 DDR arbiter
hap_axi512_paired_2client_read_wrr u_arbiter (
    .client0_axi(attention_axi),
    .client1_axi(mlp_axi),
    .master_axi(ddr0_axi)  // 都接 DDR0
);
```

**新设计：**
```systemverilog
// 移除 arbiter，直连各自 DDR
// Attention → DDR0
hap_attention_board_cohort16_core u_attention (
    .clk(clk),
    .rst_n(rst_n),
    // ... 其他信号
    
    // DDR0 AXI interface (直连)
    .m_axi_ddr_arid(ddr0_axi.arid),
    .m_axi_ddr_araddr(ddr0_axi.araddr),
    .m_axi_ddr_arlen(ddr0_axi.arlen),
    .m_axi_ddr_arvalid(ddr0_axi.arvalid),
    .m_axi_ddr_arready(ddr0_axi.arready),
    
    .m_axi_ddr_rid(ddr0_axi.rid),
    .m_axi_ddr_rdata(ddr0_axi.rdata),
    .m_axi_ddr_rresp(ddr0_axi.rresp),
    .m_axi_ddr_rlast(ddr0_axi.rlast),
    .m_axi_ddr_rvalid(ddr0_axi.rvalid),
    .m_axi_ddr_rready(ddr0_axi.rready),
    
    .m_axi_ddr_awid(ddr0_axi.awid),
    .m_axi_ddr_awaddr(ddr0_axi.awaddr),
    .m_axi_ddr_awlen(ddr0_axi.awlen),
    .m_axi_ddr_awvalid(ddr0_axi.awvalid),
    .m_axi_ddr_awready(ddr0_axi.awready),
    
    .m_axi_ddr_wdata(ddr0_axi.wdata),
    .m_axi_ddr_wstrb(ddr0_axi.wstrb),
    .m_axi_ddr_wlast(ddr0_axi.wlast),
    .m_axi_ddr_wvalid(ddr0_axi.wvalid),
    .m_axi_ddr_wready(ddr0_axi.wready),
    
    .m_axi_ddr_bid(ddr0_axi.bid),
    .m_axi_ddr_bresp(ddr0_axi.bresp),
    .m_axi_ddr_bvalid(ddr0_axi.bvalid),
    .m_axi_ddr_bready(ddr0_axi.bready)
);

// MLP → DDR1
hap_mlp_full_command16_s54 u_mlp (
    .clk(clk),
    .rst_n(rst_n),
    // ... 其他信号
    
    // DDR1 AXI interface (直连)
    .m_axi_ddr_arid(ddr1_axi.arid),
    .m_axi_ddr_araddr(ddr1_axi.araddr),
    .m_axi_ddr_arlen(ddr1_axi.arlen),
    .m_axi_ddr_arvalid(ddr1_axi.arvalid),
    .m_axi_ddr_arready(ddr1_axi.arready),
    // ... 其他 AXI 信号（类似 Attention）
);
```

**验收标准：**
- [ ] 移除 arbiter 模块
- [ ] Attention 直连 DDR0
- [ ] MLP 直连 DDR1
- [ ] Elaboration 通过

---

## 阶段 2：布线时序修复

### 2.1 创建时序约束文件

**文件：** `project/hardware/vivado/constraints/ddr_timing_recovery.xdc` (新建)

```tcl
################################################################################
# DDR 时序修复约束
# 目标: Setup/Hold ≥ +0.5 ns @ 100 MHz
################################################################################

# 1. DDR0 写地址通道 Placement 约束
# 问题: setup -5.1ns, DDR0_AW FIFO → MIG 路径过长
# 解决: 将 FIFO 靠近 MIG 控制器

set_property LOC SLICE_X50Y100 [get_cells -hier -filter {NAME =~ *ddr0_aw_fifo_ff*}]

create_pblock pblock_ddr0_ctrl
add_cells_to_pblock pblock_ddr0_ctrl [get_cells -hier -filter {NAME =~ *ddr0_axi_ctrl*}]
resize_pblock pblock_ddr0_ctrl -add {SLICE_X40Y80:SLICE_X60Y120}

# 2. Timing Derate 调整
# 检查 DDR MIG setup margin 是否过于保守
set_timing_derate -early 0.95 -late 1.05 [get_cells -hier -filter {REF_NAME =~ mig_7series*}]

# 3. Reset CDC Multicycle Path
# 问题: hold -3.1ns, Reset 同步器路径
# 解决: Reset 路径放松，不需要每周期满足

set_multicycle_path 2 -setup -from [get_pins -hier -filter {NAME =~ *ddr_reset_sync_ff_r[0]/C}]
set_multicycle_path 1 -hold  -from [get_pins -hier -filter {NAME =~ *ddr_reset_sync_ff_r[0]/C}]

# 4. MLP 核心分割 Pblock
# 问题: setup -2.9ns, Guard S37→S45 距离 DSP 过远
# 解决: 将 guard logic 靠近 DSP 阵列

create_pblock pblock_mlp_guard
add_cells_to_pblock pblock_mlp_guard [get_cells -hier -filter {NAME =~ *mlp*guard*s45*}]
resize_pblock pblock_mlp_guard -add {DSP48E2_X10Y50:DSP48E2_X15Y100}

################################################################################
# 备用方案（如果上述约束不足）
################################################################################

# Solution 1-C: Pipeline 插入（仅在必要时启用）
# 需要修改 RTL，在 AXI AW 路径插入一级寄存器
# set_property MAX_FANOUT 10 [get_nets -hier -filter {NAME =~ *ddr0_aw_*}]

# Solution 2-B: 同步器级数优化（仅在必要时启用）
# 需要修改 RTL，减少 reset 同步器级数
# set_false_path -from [get_ports rst_n] -to [get_cells -hier -filter {NAME =~ *reset_sync_ff_r*}]
```

**验收标准：**
- [ ] 约束文件语法正确
- [ ] Placement constraints 覆盖关键路径
- [ ] Multicycle path 正确配置

---

### 2.2 从 native025 提取 Placement

**前置条件：** 需要 native025 的 placed DCP

**步骤：**
```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/1_Hardware/vivado/reports/mission0008_e2_diagnostic_native_025

# 查找 placed checkpoint
find . -name "*.dcp" | grep -i place
```

**在 Vivado 中操作：**
```tcl
# 打开 placed DCP
open_checkpoint <path_to_placed.dcp>

# 读入新约束
read_xdc ../../Workspace/ScaleLLM/project/hardware/vivado/constraints/ddr_timing_recovery.xdc

# 检查约束是否生效
report_methodology
```

---

### 2.3 时序优化迭代

**工作流程：**
```tcl
# 1. Re-route from placed DCP
route_design

# 2. 生成 timing report
report_timing_summary -file timing_iteration_1.rpt
report_timing -max_paths 100 -slack_less_than 0 -file timing_violations.rpt

# 3. 分析 critical paths
report_timing -max_paths 10 -delay_type min_max -file timing_details.rpt

# 4. 根据结果决策
#    如果 setup ≥ 0 AND hold ≥ 0: 继续综合
#    如果 setup < -2ns: 实施 Solution 1-C (Pipeline)
#    如果 hold < -2ns: 实施 Solution 2-B (Sync opt)
#    如果仍失败: Fallback 95 MHz
```

**Decision Tree:**
```
检查 timing report:
  ├─ Setup WNS ≥ +0.5 ns AND Hold WNS ≥ +0.5 ns
  │   → ✅ 时序收敛，继续综合
  │
  ├─ Setup WNS < -2 ns
  │   → ⚠️ 实施 Solution 1-C: Pipeline 插入
  │   → 修改 RTL: 在 AXI AW 路径插入寄存器
  │   → 重新 route
  │
  ├─ Hold WNS < -2 ns
  │   → ⚠️ 实施 Solution 2-B: 同步器优化
  │   → 减少 reset 同步器级数 (4→3)
  │   → 重新 route
  │
  └─ 多次迭代仍失败
      → 🔴 Fallback: 降频到 95 MHz
      → 修改时钟约束: 10ns → 10.526ns
      → 重新 route
```

**验收标准：**
- [ ] Setup WNS ≥ +0.5 ns (理想) 或 ≥ 0 ns (最低)
- [ ] Hold WNS ≥ +0.5 ns (理想) 或 ≥ 0 ns (最低)
- [ ] TNS = 0 (无 timing violations)

---

## 阶段 3：综合与实现

### 3.1 完整综合

**前置条件：** 时序收敛（setup/hold ≥ 0）

**Vivado 操作：**
```tcl
# 1. 读入所有源文件（包含 DDR 分离修改）
read_verilog -sv [glob project/hardware/rtl/**/*.sv]
read_xdc project/hardware/vivado/constraints/*.xdc

# 2. 综合
synth_design -top hap_attention_mlp_resource_top \
             -part xcvu9p-flga2104-2L-e \
             -mode out_of_context

# 3. 生成综合后 timing report
report_timing_summary -file timing_post_synth.rpt

# 4. 检查资源利用率
report_utilization -file utilization_post_synth.rpt -hierarchical

# 5. 检查是否有 Critical Warnings
# 如果有，必须修复
```

**验收标准：**
- [ ] Synthesis 完成，无 error
- [ ] 无 Critical Warning（允许 Info/Warning）
- [ ] 资源利用率 < 90%（LUT, FF, BRAM, DSP）
- [ ] Post-synth timing 预估合理

---

### 3.2 Place & Route

**Vivado 操作：**
```tcl
# 1. Optimize design
opt_design

# 2. Place design
place_design -directive Explore
report_timing_summary -file timing_post_place.rpt

# 3. Physical optimization
phys_opt_design -directive Explore

# 4. Route design
route_design -directive Explore
report_timing_summary -file timing_post_route.rpt

# 5. 最终 DRC check
report_drc -file drc_final.rpt

# 6. 生成所有报告
report_power -file power_final.rpt
report_utilization -file utilization_final.rpt -hierarchical
report_route_status -file route_status.rpt
```

**验收标准：**
- [ ] Place 完成，无 unplaced cells
- [ ] Route 100% 完成，无 unrouted nets
- [ ] Setup WNS ≥ 0 ns, Hold WNS ≥ 0 ns
- [ ] DRC: 0 critical violations
- [ ] Congestion < 95% in all regions

---

### 3.3 Bitstream 生成

**Vivado 操作：**
```tcl
# 1. 写入 checkpoint（备份）
write_checkpoint -force routed.dcp

# 2. 生成 bitstream
write_bitstream -force scalellm_v5_m002.bit

# 3. 验证 bitstream 大小
# VCU118: 预期 50-100 MB

# 4. 生成配置 BIN (optional)
write_cfgmem -format BIN -size 256 -interface SPIx4 \
             -loadbit "up 0x0 scalellm_v5_m002.bit" \
             scalellm_v5_m002.bin
```

**验收标准：**
- [ ] Bitstream 生成成功
- [ ] 文件大小合理（50-100 MB）
- [ ] 无 generation errors

---

## 阶段 4：部署与验收

### 4.1 VCU118 部署

**环境准备：**
```bash
# 1. 连接 JTAG
source /opt/Xilinx/Vivado/2025.2/settings64.sh
vivado -mode tcl

# 2. 检测板卡
connect_hw_server
open_hw_target
current_hw_device [get_hw_devices xcvu9p_0]
```

**加载 Bitstream：**
```tcl
# 1. 加载到 FPGA
set_property PROGRAM.FILE {scalellm_v5_m002.bit} [current_hw_device]
program_hw_devices [current_hw_device]

# 2. 验证加载成功
refresh_hw_device [current_hw_device]
# 检查 DONE LED 是否点亮
```

**DDR 初始化验证：**
```python
# Python Host 驱动测试
import scalellm_hardware as hw

board = hw.ScaleLLMBoard()
board.connect()

# 1. DDR0 初始化测试
board.ddr_write(0x00000000, b'\x00' * 1024)  # DDR0
data = board.ddr_read(0x00000000, 1024)
assert data == b'\x00' * 1024, "DDR0 初始化失败"

# 2. DDR1 初始化测试
board.ddr_write(0x80000000, b'\xFF' * 1024)  # DDR1
data = board.ddr_read(0x80000000, 1024)
assert data == b'\xFF' * 1024, "DDR1 初始化失败"

print("✅ DDR0/DDR1 初始化成功")
```

**验收标准：**
- [ ] JTAG 连接成功
- [ ] Bitstream 加载无 error
- [ ] DDR0 读写测试通过
- [ ] DDR1 读写测试通过

---

### 4.2 功能测试

**1-Token 测试：**
```python
import numpy as np
from scalellm_hardware import ScaleLLMBoard
from host.scalellm_memory import pack_s24_q16, unpack_s32_q16

board = ScaleLLMBoard()

# 1. 准备测试数据（1 token, layer 0）
input_activation = np.random.randn(1, 4096).astype(np.float32)
input_s24 = pack_s24_q16(input_activation)

# 2. 测试 Attention (DDR0)
print("Testing Attention on DDR0...")
board.send_attention_input(cohort=0, layer=0, data=input_s24)
board.trigger_attention(layer=0)
output_attn = board.read_attention_output(cohort=0, layer=0)
print(f"✅ Attention output shape: {output_attn.shape}")

# 3. 测试 MLP (DDR1)
print("Testing MLP on DDR1...")
board.send_mlp_input(cohort=0, layer=0, data=input_s24)
board.trigger_mlp(layer=0)
output_mlp = board.read_mlp_output(cohort=0, layer=0)
output_mlp_fp32 = unpack_s32_q16(output_mlp)
print(f"✅ MLP output shape: {output_mlp_fp32.shape}")

# 4. 验证 DDR 分离
stats = board.get_ddr_separation_stats()
print(f"DDR0 accesses: {stats['ddr0_accesses']}")
print(f"DDR1 accesses: {stats['ddr1_accesses']}")
assert stats['ddr0_accesses'] > 0, "DDR0 未使用"
assert stats['ddr1_accesses'] > 0, "DDR1 未使用"
```

**验收标准：**
- [ ] Attention 功能正常
- [ ] MLP 功能正常
- [ ] DDR0 仅 Attention 访问
- [ ] DDR1 仅 MLP 访问
- [ ] 输出数值合理（无 NaN/Inf）

---

### 4.3 性能测量

**完整 32 层推理测试：**
```python
import time
from transformers import AutoTokenizer

# 1. 准备输入（16 tokens）
tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-3.1-8B-Instruct")
input_text = "The quick brown fox jumps over the lazy dog and"
tokens = tokenizer.encode(input_text)[:16]

# 2. 运行完整推理
start_time = time.time()

for layer in range(32):
    # Attention
    board.send_attention_input(cohort=0, layer=layer, data=hidden_states)
    board.trigger_attention(layer=layer)
    attn_out = board.read_attention_output(cohort=0, layer=layer)
    
    # Host residual + RMSNorm (模拟)
    hidden_states = residual_add_and_norm(hidden_states, attn_out)
    
    # MLP
    board.send_mlp_input(cohort=0, layer=layer, data=hidden_states)
    board.trigger_mlp(layer=layer)
    mlp_out = board.read_mlp_output(cohort=0, layer=layer)
    
    # Host residual + RMSNorm
    hidden_states = residual_add_and_norm(hidden_states, mlp_out)

end_time = time.time()

# 3. 计算性能
total_time = end_time - start_time
throughput = 16 / total_time  # tokens/s

print(f"Total time: {total_time:.2f} s")
print(f"Throughput: {throughput:.2f} tokens/s")
print(f"Target: ≥ 3.2 tokens/s")
print(f"Result: {'✅ PASS' if throughput >= 3.2 else '❌ FAIL'}")

# 4. DDR 带宽统计
ddr_stats = board.get_ddr_bandwidth_stats()
print(f"DDR0 bandwidth utilization: {ddr_stats['ddr0_util']:.1f}%")
print(f"DDR1 bandwidth utilization: {ddr_stats['ddr1_util']:.1f}%")
print(f"DDR conflict rate: {ddr_stats['conflict_rate']:.1f}%")
```

**验收标准：**
- [ ] 32 层推理成功完成
- [ ] Throughput ≥ 3.2 tokens/s（理想），≥ 3.0 tokens/s（最低）
- [ ] DDR0 利用率 > 60%
- [ ] DDR1 利用率 > 60%
- [ ] DDR 冲突率 < 10%（理想），< 15%（最低）
- [ ] 核心温度 < 85°C
- [ ] 无 DDR timeout 或 retry

---

### 4.4 最终验收报告

**报告内容：**

**1. 功能验收：**
- [x] DDR0/DDR1 地址完全分离
- [x] Attention 仅访问 DDR0
- [x] MLP 仅访问 DDR1
- [x] 1-token 测试通过
- [x] 32 层推理通过

**2. 时序验收：**
- [x] Setup WNS ≥ +0.5 ns @ 100 MHz（或 ≥ 0 @ 95 MHz）
- [x] Hold WNS ≥ +0.5 ns
- [x] DRC: 0 critical violations
- [x] Route: 100% completion

**3. 性能验收：**
- [x] Throughput: _____ tokens/s (目标 ≥ 3.2)
- [x] DDR0 util: _____% (目标 > 60%)
- [x] DDR1 util: _____% (目标 > 60%)
- [x] Conflict rate: _____% (目标 < 10%)
- [x] Temperature: _____°C (目标 < 85)

**4. 性能对比：**
```
Metric              | Baseline | M002    | Improvement
─────────────────────────────────────────────────────
Throughput          | 2.5 t/s  | ___ t/s | ____%
DDR Conflict        | 30%      | ___%    | ____%
MLP per-layer time  | 93 ms    | ___ ms  | ____%
```

**5. 遗留问题与风险：**
- 列出未解决的问题
- 潜在风险评估
- 后续优化建议

**6. 后续任务建议：**
- M003: 双 Cohort Pipeline
- M004: DDR Prefetch 优化
- M005: 时钟频率提升

---

## 备用方案与风险管理

### Fallback Plan 1: 降频到 95 MHz

**触发条件：**
- 时序优化迭代多次后仍无法收敛 100 MHz
- Setup WNS < -1 ns 且无法通过约束改善

**执行步骤：**
```tcl
# 修改时钟约束
set_property PERIOD 10.526 [get_clocks core_clk]  # 95 MHz

# 重新 route
route_design -directive Explore

# 验证时序
report_timing_summary
# 预期: Setup WNS ≥ +1.5 ns, Hold WNS ≥ +1.0 ns
```

**影响：**
- Throughput: 3.5 → 3.3 tokens/s (-5%)
- 仍符合最低验收标准（≥ 3.0 tokens/s）

---

### Fallback Plan 2: 分阶段交付

**如果一周内无法完成所有工作：**

**阶段 1 交付（最小可行）：**
- ✅ DDR 分离架构实现
- ✅ Python 驱动更新
- ✅ RTL 修改完成
- ⏸ 时序修复延后

**阶段 2 交付（下周）：**
- ✅ 时序收敛
- ✅ Bitstream 生成
- ✅ 板级部署

---

### 高级修复方案（仅在必要时使用）

**Solution 1-C: Pipeline 插入**

**触发条件：** Setup slack < -3 ns 且约束优化无效

**RTL 修改：**
```systemverilog
// 在 AXI AW 路径插入一级寄存器
// 文件: hap_mlp_tensor_dma_bridge.sv

always_ff @(posedge clk) begin
    if (!rst_n) begin
        ddr_aw_addr_r <= '0;
        ddr_aw_valid_r <= 1'b0;
    end else begin
        ddr_aw_addr_r <= mlp_command_addr;
        ddr_aw_valid_r <= mlp_command_valid;
    end
end

assign m_axi_ddr_awaddr = ddr_aw_addr_r;
assign m_axi_ddr_awvalid = ddr_aw_valid_r;
```

**影响：**
- 增加 1 周期延迟（10 ns @ 100 MHz）
- Setup 改善 +4 ~ +6 ns
- 需要重新验证 MLP FSM 时序

---

**Solution 2-B: 同步器优化**

**触发条件：** Hold slack < -2 ns 且 multicycle path 无效

**RTL 修改：**
```systemverilog
// 减少 reset 同步器级数：4 → 3
// 文件: hap_ddr_reset_synchronizer.sv

// 当前（4 级）
reg [3:0] reset_sync_ff_r;

// 优化（3 级）
reg [2:0] reset_sync_ff_r;

always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        reset_sync_ff_r <= 3'b000;
    else
        reset_sync_ff_r <= {reset_sync_ff_r[1:0], ddr_mig_reset_n};
end

assign reset_sync = reset_sync_ff_r[2];
```

**影响：**
- Hold 改善 +1.5 ~ +2.0 ns
- 需要 MTBF 分析（确保 metastability 安全）

---

## 验收检查清单

### 功能验收 ✓
- [ ] DDR0 地址 < 0x8000_0000
- [ ] DDR1 地址 ≥ 0x8000_0000
- [ ] Attention 仅访问 DDR0
- [ ] MLP 仅访问 DDR1
- [ ] 单元测试 100% 通过
- [ ] 1-token 测试通过
- [ ] 32 层推理通过

### 时序验收 ✓
- [ ] Setup WNS ≥ +0.5 ns @ 100 MHz（或 ≥ 0 @ 95 MHz）
- [ ] Hold WNS ≥ +0.5 ns
- [ ] Setup TNS = 0
- [ ] Hold TNS = 0
- [ ] DRC: 0 critical violations
- [ ] Route: 100% complete
- [ ] Congestion < 95%

### 性能验收 ✓
- [ ] Throughput ≥ 3.2 tokens/s（理想）或 ≥ 3.0 tokens/s（最低）
- [ ] DDR0 bandwidth util > 60%
- [ ] DDR1 bandwidth util > 60%
- [ ] DDR conflict rate < 10%（理想）或 < 15%（最低）
- [ ] Core temperature < 85°C
- [ ] No DDR timeout/retry

### 文档验收 ✓
- [ ] Timing reports 完整
- [ ] Power analysis 完成
- [ ] Resource utilization 报告
- [ ] DRC final report
- [ ] 最终验收报告提交

---

## 关键文件清单

### 需要修改的文件

**Python (2 files):**
- `project/hardware/host/scalellm_memory.py` - 地址映射
- `project/hardware/host/scalellm_hardware.py` - DMA 逻辑

**RTL (1 file):**
- `project/hardware/rtl/integration/hap_attention_mlp_resource_top.sv` - Top-level 接线

**Constraints (1 new file):**
- `project/hardware/vivado/constraints/ddr_timing_recovery.xdc` - 时序约束

### 需要生成的文件

**Vivado Checkpoints:**
- `routed.dcp` - 布线完成的 checkpoint

**Bitstream:**
- `scalellm_v5_m002.bit` - FPGA 配置文件

**Reports:**
- `timing_post_route.rpt` - 最终时序报告
- `utilization_final.rpt` - 资源利用率
- `power_final.rpt` - 功耗分析
- `drc_final.rpt` - DRC 检查结果
- `route_status.rpt` - 布线状态

**Verification:**
- `M002_final_verification_report.md` - 最终验收报告

---

## 立即启动清单

**准备工作：**
1. 环境配置
   ```bash
   source /opt/Xilinx/Vivado/2025.2/settings64.sh
   cd /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM
   ```

2. 检查源文件
   ```bash
   ls project/hardware/host/scalellm_memory.py
   ls project/hardware/rtl/integration/hap_attention_mlp_resource_top.sv
   ```

3. 准备 native025 DCP
   ```bash
   cd /home/user/EDA-202/zhuowenjun/ScaleLLM/1_Hardware/vivado/reports/mission0008_e2_diagnostic_native_025
   ls *.dcp
   ```

**开始执行阶段 1：DDR 分离实现**

---

**创建人：** Kiro  
**日期：** 2026-10-14  
**状态：** ✅ 准备就绪
