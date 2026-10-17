# M002 阶段 4：综合与实现计划

**任务：** 完整的 Vivado 综合、实现与 bitstream 生成  
**目标：** 生成可部署的 bitstream  
**预计时间：** 6-8 小时（综合+实现）

---

## 综合与实现流程

### 前置条件 ✅

1. **Python 层修改完成**
   - `scalellm_memory.py` ✅
   - 单元测试通过 ✅

2. **时序约束准备**
   - `ddr_timing_recovery.xdc` ✅

3. **RTL 代码**
   - 当前保持不变（使用现有 RTL）
   - 通过 Python 层实现 DDR 分离

---

## 构建流程步骤

### Step 1: 环境准备

```bash
# 设置 Vivado 环境
source /opt/Xilinx/Vivado/2025.2/settings64.sh

# 设置工程路径
export HAP_ROOT=/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM
export HAP_PROJECT_DIR=$HAP_ROOT/vivado/project/attention_mlp_vcu118_v5_dual_ddr
export HAP_JOBS=32
```

### Step 2: 添加时序约束

```tcl
# 在 Vivado 中添加 M002 约束
add_files -fileset constrs_1 \
  $HAP_ROOT/project/hardware/vivado/constraints/ddr_timing_recovery.xdc

# 设置约束优先级
set_property PROCESSING_ORDER LATE \
  [get_files ddr_timing_recovery.xdc]
```

### Step 3: 综合 (Synthesis)

**预计时间：** 1-2 小时

```tcl
# 运行综合
reset_run synth_1
launch_runs synth_1 -jobs $HAP_JOBS
wait_on_run synth_1

# 检查综合结果
open_run synth_1
report_timing_summary -file $out/timing_post_synth.rpt
report_utilization -file $out/utilization_post_synth.rpt
```

**验收标准：**
- [ ] 综合完成，无 Critical Warning
- [ ] 资源利用率 < 95%
- [ ] Post-synth timing 估算合理

### Step 4: 实现 (Implementation)

**预计时间：** 4-6 小时

#### 4.1 Opt Design

```tcl
opt_design -directive ExploreArea
report_timing_summary -file $out/timing_post_opt.rpt
```

#### 4.2 Place Design

```tcl
place_design -directive SSI_SpreadLogic_high
report_timing_summary -file $out/timing_post_place.rpt
report_utilization -file $out/utilization_post_place.rpt

# 检查关键指标
set setup_wns [get_property SLACK [get_timing_paths -setup -max_paths 1]]
set hold_wns [get_property SLACK [get_timing_paths -hold -max_paths 1]]

puts "INFO: [M002] Post-place Setup WNS: $setup_wns"
puts "INFO: [M002] Post-place Hold WNS: $hold_wns"
```

**Decision Point 1：**
```
如果 setup_wns < -2.0:
  → 应用额外的 placement 优化
  → phys_opt_design -directive AggressiveExplore
  
如果 setup_wns < -5.0:
  → 考虑降频到 95 MHz
  → 或启用 pipeline 插入方案
```

#### 4.3 Physical Optimization

```tcl
phys_opt_design -directive AggressiveExplore
report_timing_summary -file $out/timing_post_physopt.rpt
```

#### 4.4 Route Design

```tcl
route_design -directive AggressiveExplore
report_timing_summary -file $out/timing_post_route.rpt
report_route_status -file $out/route_status.rpt
report_drc -file $out/drc_final.rpt
```

**验收标准：**
- [ ] Route 100% 完成
- [ ] Setup WNS ≥ 0 ns
- [ ] Hold WNS ≥ 0 ns
- [ ] DRC: 0 critical violations

**Decision Point 2：**
```
如果 route 失败或 timing 不收敛:
  → Fallback Plan A: 降频 95 MHz
  → Fallback Plan B: 修改 floorplan
  → Fallback Plan C: 放松某些约束
```

### Step 5: Bitstream 生成

```tcl
# 写入 checkpoint
write_checkpoint -force $out/routed.dcp

# 生成 bitstream
write_bitstream -force $out/scalellm_v5_m002.bit

# 生成报告
report_power -file $out/power_final.rpt
report_utilization -hierarchical -file $out/utilization_final.rpt
```

**验收标准：**
- [ ] Bitstream 生成成功
- [ ] 文件大小合理（50-100 MB）
- [ ] 无 generation errors

---

## 预期结果

### 时序目标

| Metric | 当前 (native025) | 目标 (M002) | Fallback |
|---|---|---|---|
| Setup WNS | -5.1 ns | +0.5 ns | 0 ns @ 95MHz |
| Hold WNS | -3.1 ns | +0.5 ns | 0 ns |
| Setup TNS | 负值 | 0 | 0 |
| Hold TNS | 负值 | 0 | 0 |

### 资源利用

| Resource | V5 Total | Expected | Utilization |
|---|---|---|---|
| LUT | ~1,000,000 | ~750,000 | ~75% |
| FF | ~2,000,000 | ~850,000 | ~43% |
| BRAM | 1,280 | ~950 | ~74% |
| DSP48E2 | 5,453 | ~5,200 | ~95% |

### 布线状态

- Route completion: 100%
- Congestion: < 95% in all regions
- No unrouted nets

---

## 完整构建脚本

创建 `build_m002.tcl`:

```tcl
#!/usr/bin/env tclsh
# M002 完整构建脚本

# 1. 环境设置
set root /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM
set project_dir $root/vivado/project/attention_mlp_vcu118_v5_dual_ddr
set out_dir $root/vivado/reports/m002_build_[clock format [clock seconds] -format "%Y%m%d_%H%M%S"]
file mkdir $out_dir

# 2. 打开工程
open_project $project_dir/attention_mlp_vcu118_v5_dual_ddr.xpr

# 3. 添加 M002 约束
set m002_xdc $root/project/hardware/vivado/constraints/ddr_timing_recovery.xdc
if {[file exists $m002_xdc]} {
    add_files -fileset constrs_1 $m002_xdc
    set_property PROCESSING_ORDER LATE [get_files ddr_timing_recovery.xdc]
    puts "INFO: [M002] Added timing recovery constraints"
} else {
    puts "WARNING: [M002] Constraints file not found: $m002_xdc"
}

# 4. 综合
puts "INFO: [M002] Starting synthesis..."
reset_run synth_1
launch_runs synth_1 -jobs 32
wait_on_run synth_1

if {[get_property PROGRESS [get_runs synth_1]] != "100%"} {
    error "Synthesis failed"
}

open_run synth_1
report_timing_summary -file $out_dir/timing_post_synth.rpt
report_utilization -file $out_dir/utilization_post_synth.rpt
puts "INFO: [M002] Synthesis completed"

# 5. 实现
puts "INFO: [M002] Starting implementation..."
reset_run impl_1
launch_runs impl_1 -jobs 32
wait_on_run impl_1

if {[get_property PROGRESS [get_runs impl_1]] != "100%"} {
    error "Implementation failed"
}

# 6. 打开实现结果并检查
open_run impl_1
set setup_wns [get_property SLACK [get_timing_paths -setup -max_paths 1]]
set hold_wns [get_property SLACK [get_timing_paths -hold -max_paths 1]]

puts "INFO: [M002] Setup WNS: $setup_wns ns"
puts "INFO: [M002] Hold WNS: $hold_wns ns"

# 7. 生成报告
report_timing_summary -file $out_dir/timing_post_route.rpt
report_route_status -file $out_dir/route_status.rpt
report_drc -file $out_dir/drc_final.rpt
report_power -file $out_dir/power_final.rpt
report_utilization -hierarchical -file $out_dir/utilization_final.rpt

# 8. 检查时序
if {$setup_wns < 0 || $hold_wns < 0} {
    puts "ERROR: [M002] Timing not met:"
    puts "  Setup WNS: $setup_wns ns"
    puts "  Hold WNS: $hold_wns ns"
    report_timing -setup -max_paths 10 -slack_less_than 0 \
        -file $out_dir/timing_violations.rpt
    error "Timing not met"
}

# 9. 生成 bitstream
puts "INFO: [M002] Generating bitstream..."
write_checkpoint -force $out_dir/routed.dcp
write_bitstream -force $out_dir/scalellm_v5_m002.bit

puts "INFO: [M002] Build completed successfully"
puts "INFO: [M002] Output directory: $out_dir"
puts "INFO: [M002] Bitstream: $out_dir/scalellm_v5_m002.bit"
```

---

## 执行方式

### 方式 1：命令行（推荐）

```bash
cd /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM
source /opt/Xilinx/Vivado/2025.2/settings64.sh

# 运行构建脚本
vivado -mode batch -source vivado/scripts/build_m002.tcl
```

### 方式 2：Vivado GUI

```bash
# 启动 Vivado
vivado &

# 在 Tcl Console 中
source /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/vivado/scripts/build_m002.tcl
```

### 方式 3：使用现有构建系统

```bash
# 如果项目有 Makefile
cd /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM
make bitstream HAP_EXTRA_XDC=project/hardware/vivado/constraints/ddr_timing_recovery.xdc
```

---

## 时间估算

| 阶段 | 预计时间 | 说明 |
|---|---|---|
| 环境准备 | 10 分钟 | 设置路径、添加约束 |
| Synthesis | 1-2 小时 | 取决于机器性能 |
| Opt Design | 20 分钟 | - |
| Place Design | 1-2 小时 | 最耗时 |
| Phys Opt | 30 分钟 | - |
| Route Design | 2-3 小时 | 最耗时 |
| Bitstream | 10 分钟 | - |
| **总计** | **6-8 小时** | 一个工作日 |

---

## Fallback 策略

### Plan A: 降频 95 MHz

```tcl
# 修改时钟约束
set_property PERIOD 10.526 [get_clocks core_clk]  # 95 MHz

# 重新运行 implementation
reset_run impl_1
launch_runs impl_1 -jobs 32
```

**影响：** 吞吐量 -5%

### Plan B: 放松约束

```tcl
# 临时放松某些非关键路径
set_max_delay 12.0 -from [get_clocks core_clk] -to [get_pins *debug*]
```

### Plan C: 修改 Floorplan

```tcl
# 调整 Pblock 位置
resize_pblock pblock_ddr0_axi_ctrl -add {SLICE_X0Y0:SLICE_X40Y60}
```

---

## 验收清单

### 综合验收

- [ ] Synthesis 完成，无 error
- [ ] 无 Critical Warning
- [ ] 资源利用率 < 95%

### 实现验收

- [ ] Place 完成
- [ ] Route 100% 完成
- [ ] Setup WNS ≥ 0 ns
- [ ] Hold WNS ≥ 0 ns
- [ ] DRC: 0 critical violations

### Bitstream 验收

- [ ] Bitstream 生成成功
- [ ] 文件大小 50-100 MB
- [ ] 所有报告生成完整

---

## 下一步

**如果综合成功：**
1. 生成 bitstream
2. 进入阶段 5：板级部署
3. 性能验证

**如果时序不收敛：**
1. 分析 timing report
2. 应用 Fallback Plan
3. 迭代优化

---

**状态：** 准备执行  
**预计完成：** 6-8 小时  
**下一步：** 执行 `build_m002.tcl`
