# ScaleLLM 立即行动计划

**生成时间：** 2026-10-14  
**文档目的：** 从功能验证完成到部署的 1-4 周行动指南  
**优先级：** 🔴 P1 最紧急

---

## 快速现状

| 维度 | 状态 | 备注 |
|---|---|---|
| 硬件功能验证 | ✅ PASS | Down-S32 完整实现、软件验证通过 |
| 综合 | ⏳ 待进行 | 预期通过 |
| 布线前时序 | ❌ FAIL | Setup -5.1ns, Hold -3.1ns |
| 修复可行性 | 🟡 75% | 多措施组合预期恢复 |
| 部署就绪 | 🔴 2-3 周 | 依赖时序修复通过 |

---

## Week 1-2: 布线时序紧急修复（🔴 BLOCKING）

### 目标
```
Setup slack @ 100 MHz: -5.1ns → ≥ +0.5ns
Hold slack @ 100 MHz:  -3.1ns → ≥ +0.5ns
```

### 立即行动清单

#### Step 1: 提取 native025 placement DCP（Day 1）

```bash
# 新工程中检查是否有可用的 placed DCP
cd /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/hardware
find . -name "*.dcp" | grep -i place

# 如果没有，从旧工程复制（只读）
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/1_Hardware/vivado/reports/mission0008_e2_diagnostic_native_025
# 查找 checkpoint DCP
```

**关键文件：**
- `impl_1_placed.dcp` 或 `*.checkpoint`

#### Step 2: Vivado placement refinement（Day 1-2）

创建新 XDC 约束文件：`vivado/constraints/timing_recovery.xdc`

```tcl
# 1. DDR 关键路径 location 约束
# DDR0_AW 命令路径相关 flops 靠近 MIG 控制器
set_property LOC SLICEX Y [get_cells ddr0_aw_fifo_ff_*)
set_property LOC SLICEY Z [get_cells ddr0_ar_fifo_ff_*)

# 2. MLP 中心逻辑紧凑放置
set_property PBLOCKS mlp_core [get_cells hap_mlp_shared_dual_slice16x12_s44_s54]
set_property GRIDASSIGN mlp_core:DSP48E2_X10Y0 [get_cells */dsp_lane[0]]
# ... 继续约束其他 DSP48E2

# 3. Reset CDC 路径放松（在 post-place 阶段）
set_multicycle_path 2 -setup -from [get_cells ddr_reset_sync_ff_r[0]] -to [get_cells */reset_n]
set_multicycle_path 1 -hold  -from [get_cells ddr_reset_sync_ff_r[0]] -to [get_cells */reset_n]
```

**关键参数：**
- DISTANCE: DDR MIG 到 AW/AR FIFO < 100 units
- DSP 行对齐：S37→S45 transition 在 DSP 阵列中心

#### Step 3: Vivado 中重新 route（Day 2-3）

```tcl
# Vivado 中打开 placed DCP
open_checkpoint impl_1_placed.dcp

# 读入新约束
read_xdc vivado/constraints/timing_recovery.xdc

# 关键参数优化
set_property ROUTE_EFFORT HIGH [current_design]
set_property STRATEGY "MoreTimingClosure" [get_runs impl_1]

# 重新 route
route_design

# 检查时序
report_timing_summary -file timing_post_route_recovery.rpt
report_timing -slack_lesser_than 0 > timing_failures_detail.rpt
```

**预期输出：**
- `timing_post_route_recovery.rpt`: 新 timing report
- 目标：setup/hold slack 趋向 ≥ 0

#### Step 4: 验证与决策（Day 3）

```bash
# 1. 检查时序是否通过
grep "WNS\|TNS\|slack" timing_post_route_recovery.rpt

# 2. 检查 DRC
report_drc -file drc_post_recovery.rpt
```

**决策树：**

```
如果 Setup ≥ +0.5ns AND Hold ≥ +0.5ns:
  ✅ 时序 PASS → 继续 Step 5 (bitstream)

如果 Setup < 0 OR Hold < 0 但改善 >1.5ns:
  🟡 部分改善 → 应用第二轮约束优化或降频到 95 MHz

如果改善 <1.0ns:
  🔴 失败 → 考虑降频备选方案
```

#### Step 5: DRC 与 Route Completion 验收（Day 3-4）

```bash
# DRC 必须全绿
report_drc -severity ERROR  # 应该为空

# 布线完成率 100%
report_route_status
# Unrouted: 0
```

---

## Step 6-7: 综合与 Bitstream（Day 4-5）

前提：timing PASS

```bash
# 生成 bitstream（不部署，仅验证）
write_bitstream -force scalellm_v5.bit

# 生成所有文档
report_timing_summary -file final_timing_report.rpt
report_power -file final_power_report.txt
report_resources -file final_resources_report.txt
```

---

## Week 2: 并行工作 - DDR 优化方案设计（🟡 P2）

**前提条件：不阻塞 timing 修复，可并行进行**

### DDR 双通道负载均衡设计

#### Task 1: 当前 DDR 使用情况分析

```python
# 新文件：project/hardware/analysis/ddr_usage_analysis.py

# 分析：
# - DDR0 current: MLP input (6144 beats) + MLP output (8192 beats) + metadata
# - DDR1 current: Attention KV cache (variable)
# 
# 改进方案：
# - DDR0: MLP input (6144) + Attention KV cache
# - DDR1: MLP output (8192) + Attention weights
```

**输出：**
- `ddr_usage_summary.txt`: 当前分配与建议新分配
- `ddr_address_remapping_table.xlsx`: 地址映射变更

#### Task 2: 张量 DMA 修改方案

**关键 RTL 文件：**
```
project/hardware/rtl/integration/hap_mlp_tensor_dma_bridge.sv
  - 修改 H2C 读地址生成：0x0000_0000 → base_input_ddr0
  - 修改 C2H 写地址生成：保持在 DDR1_base + offset
  
project/hardware/host/scalellm_memory.py
  - INPUT_BASE: 0x00000000 (DDR0) ✓ 不变
  - OUTPUT_BASE: 0x80000000 → 0x80000000 + DDR1_offset ✓ 改为 DDR1
  - KV_CACHE_BASE: 0x00200000 → 0x00200000 + (MLP_input_size) ✓ 改为 DDR0
```

**预期文件修改：**
- `hap_mlp_tensor_dma_bridge.sv`: +50 ~ 100 lines (address decode)
- `scalellm_memory.py`: +20 ~ 30 lines (DDR config)
- `scalellm_hardware.py`: +10 ~ 15 lines (new DDR mappings)

#### Task 3: 硬件测试用例

```bash
# 新 TB: project/hardware/tb/hap_mlp_tensor_dma_dual_ddr_tb.sv
# - 验证 H2C reads from DDR0
# - 验证 C2H writes to DDR1
# - 验证 KV cache in DDR0 不冲突
```

---

## Week 3: Bitstream 部署与基准测试（第一阶段）

### 前提
- Timing 已 PASS
- Bitstream 已生成

### 部署步骤

#### Step A: VCU118 初始化（Day 1）

```bash
# 环境准备
export XILINX_VIVADO=/opt/Xilinx/Vivado/2025.2
source $XILINX_VIVADO/settings64.sh

# 验证 JTAG 连接
python3 -B project/hardware/host/scalellm_board.py --probe

# 加载 bitstream
python3 -B project/hardware/host/scalellm_board.py \
  --program scalellm_v5.bit
```

#### Step B: 功能验证（Day 2）

```bash
# 简单推理测试（1 token, 1 layer）
python3 -B project/software/0_Software/fix_experiment/exp/run_eval_worker.py \
  --model meta-llama/Llama-3.1-8B-Instruct \
  --hardware \
  --layers 1:1 \
  --tokens 1 \
  --output /tmp/verify_output.pkl
```

#### Step C: 性能基准（Day 3）

```bash
# 吞吐测试
python3 -B project/hardware/host/benchmark_mlp_throughput.py \
  --batch_size 16 \
  --token_count 128 \
  --output /tmp/throughput_baseline.txt

# 结果格式：
# MLP H2C latency: X µs
# MLP gate+down latency: Y µs
# MLP C2H latency: Z µs
# Total per token: X+Y+Z µs
# Estimated tokens/s: 1e6 / (X+Y+Z)
```

**预期基准（参考值）：**
- Token/s: 5-15 tokens/s （依赖布线后的实际 timing）

---

## 风险缓解计划

### 如果时序无法恢复到 100 MHz

**Fallback A: 降频到 95 MHz**
```tcl
set_property PERIOD 10526 [get_clocks core_clk]  # 10.526 ns ≈ 95 MHz
```
- 吞吐降低 ~5%
- 时序 margin 增加到 +1.5 ~ +2.5 ns
- 预期 100% 可行

**Fallback B: 降频到 90 MHz**
```tcl
set_property PERIOD 11111 [get_clocks core_clk]  # 11.111 ns = 90 MHz
```
- 吞吐降低 ~10%
- 时序 margin 增加到 +3 ~ +4 ns
- 备选方案

**Fallback C: Pipeline 插入（仅限最坏情况）**
- 在 DDR 命令路径插入一个寄存器级
- 需要修改 MLP controller FSM
- 风险高，不推荐

---

## 并行工作流（Gantt 概览）

```
Week 1:
  Day 1-2: 布线 placement refinement + route
  Day 2-3: DDR 使用分析 (并行)
  Day 3-4: Timing 验收、综合、Bitstream

Week 2:
  Day 1-3: DDR 张量 DMA 修改 (并行)
  Day 2-5: 硬件测试 TB (并行)

Week 3:
  Day 1: VCU118 初始化、Bitstream 部署
  Day 2: 功能验证
  Day 3: 性能基准测试

Week 4 (Optional):
  Day 1-5: DDR 优化验证、部署新版本
```

---

## 质量检查清单

### Timing 恢复 PASS 标准

- [ ] Setup slack ≥ +0.5 ns @ 100 MHz
- [ ] Hold slack ≥ +0.5 ns @ 100 MHz
- [ ] No timing exceptions (except intentional)
- [ ] DRC: 0 violations (only informative rules)
- [ ] Route: 100% completion
- [ ] No hold violations on critical paths

### 部署前检查清单

- [ ] Bitstream 生成成功
- [ ] Bitstream 大小合理 (~50-100 MB)
- [ ] JTAG 连接验证
- [ ] DDR0/DDR1 初始化正常
- [ ] 1-token 推理功能测试通过
- [ ] 性能基准数据采集

### DDR 优化验收标准

- [ ] H2C 延迟 < 2 µs (相比 baseline 有 20% 改善)
- [ ] C2H 延迟 < 2.5 µs
- [ ] DDR 利用率 > 70%
- [ ] 无 DDR 超时或重试

---

## 关键联系点

如果遇到问题，检查以下文档：

1. **功能验证已验收**
   - `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/results/alignment_verification_2026-10-14.md`

2. **硬件功能与时序详解**
   - `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/results/hardware_functional_status_and_timing_analysis.md`

3. **DDR 性能分析**
   - 上述文件中 Section 4

4. **新 goal.md（强制对齐原则）**
   - `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/goal/goal.md`

---

## 最后：决策点确认

**Q1: 需要做功能仿真吗？**  
A: **不需要**。Down-S32 已完整验证，XSim 是可选的精益验证。

**Q2: 100 MHz 能达到吗？**  
A: **75% 可能**。如果不行，降到 95 MHz（仅损失 5% 吞吐）。

**Q3: 何时可以部署到板卡？**  
A: **布线 timing PASS 后立即生成 bitstream**，约 2-3 周。

**Q4: DDR 优化必须在部署前完成吗？**  
A: **不必须**。可以先部署基础版本（100 MHz），然后逐步优化。

---

**下一步：启动 Day 1！**
