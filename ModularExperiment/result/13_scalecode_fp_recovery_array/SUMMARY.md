# M13 ScaleCode / FP Recovery-only 96-lane 完整对比

## 1. 当前状态

- `SC-auto`、FP16、FP32：功能仿真均为 `PASS`，0 mismatch，输入/输出 II=1。
- 三路 100 MHz post-route OOC：均为 `PASS`，WNS/WHS 非负，DRC error=0，
  unrouted net=0。
- post-route SAIF 功耗：`FAIL_NETLIST_SIM`，尚无有效 dynamic W 或
  pJ/SROp；不得用失败仿真或 vectorless estimate 填充功耗表。
- 旧 `SC-LUT` 使用 production leaf 的 `use_dsp="no"` 强制映射，只保留为
  production-mapping diagnostic，不进入“无特殊映射”的正式算法对比。

## 2. 实验边界与模块身份

统一测量边界为：

```text
S17 dot + activation/weight scale metadata
  -> recovery / scale application
  -> 每 lane 两路 S36 Q12.24 contribution
```

本实验排除 dot-product/MAC、accumulator、cache、projection controller 和 tile
输出舍入。

本实验统一定义一次 **Scale Recovery Operation（SROp）** 为：

```text
一个 S17 dot
+ 这个 dot 对应的一组 activation scale 和 weight scale 元数据
-> 完成数值恢复并产生一个 S36 Q12.24 contribution
= 1 SROp
```

ScaleCode、FP16、FP32内部实现需要的乘法、移位和格式转换不同，但只要生成一个
上述统一边界的 contribution，就统一计为一次 SROp。因此这里的“相同算力”严格
指 **相同 SROp/s**，不是内部乘法次数相同，也不是完整 Attention/MLP GEMM TOPS。

| 名称 | 模块身份 | 映射策略 | 是否正式公平对比 |
|---|---|---|---|
| SC-auto | 实验目录中的 ScaleCode 等价算术 leaf；不是 production RTL 原样实例 | 无 `use_dsp`/`mult_style`，Vivado默认映射 | 是 |
| FP16 | 实验 recovery reference，使用 AMD Floating-Point IP | Vivado/AMD IP默认实现 | 是 |
| FP32 | 实验 recovery reference，使用 AMD Floating-Point IP | Vivado/AMD IP默认实现 | 是 |
| SC-LUT diagnostic | 实例化 ScaleLLM production `hap_a8w4_scalecode_recover2_lut` leaf | production RTL明确 `use_dsp="no"` | 否，仅诊断 |

SC-auto 与 production SC-LUT 的算术、位宽和流水行为相同，区别是 SC-auto 删除
了强制 LUT 属性。96-lane 顶层也是实验复制阵列，不代表 ScaleLLM 系统中真实的
实例数量。

## 3. 每 lane 的真实硬件运算

| 版本 | 每 lane 每个输入的主要运算 | 每 lane 输出 |
|---|---|---:|
| SC-auto | 2×`U8×U8` code乘法 + 2×`S17×U16` dot/code乘法 + 2×shift求和 + 2×Q24可变移位 | 2 SROp |
| FP16 | 2×S17→FP32→FP16 + 4×FP16乘法 + 2×FP16→FP32→S36 | 2 SROp |
| FP32 | 2×S17→FP32 + 4×FP32乘法 + 2×FP32→S36 | 2 SROp |

SC-auto 默认综合后，每 lane 的两个 17×17 乘法映射为2个DSP；两个8×8 code
乘法保留在 LUT 中。因此96 lane总计192 DSP。FP16每 lane使用4 DSP，FP32每
lane使用8 DSP。

## 4. 算力、吞吐与周期

统一几何为96 lane、每 lane两路输出、II=1：

```text
SROp/cycle = 96 lane × 2 SROp/lane ÷ II = 192
@100 MHz scale-recovery compute = 192 × 100 MHz = 19.2 GSROp/s
multiply launch/cycle = 96 lane × 4 multiply/lane = 384
@100 MHz multiply rate = 38.4 Gmul/s
```

整数、FP16、FP32乘法的位宽和代价不同，所以 `Gmul/s` 不能直接视为等价 TOPS；
跨数制的统一算力指标是上述定义的 `GSROp/s`。

| 版本 | lane | SROp/lane | 实测II | SROp/cycle | 内部乘法/cycle | 内部乘法类型 | 首输出延迟 | 4,096-vector总周期 | @100 MHz统一算力 | 内部乘法发射率（非统一算力） |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| SC-auto | 96 | 2 | 1 | 192 | 384 | INT 8×8 + 17×17 | 3 cycles | 4,099 | 19.2 GSROp/s | 38.4 Gmul/s |
| FP16 | 96 | 2 | 1 | 192 | 384 | FP16 | 29 cycles | 4,125 | 19.2 GSROp/s | 38.4 Gmul/s |
| FP32 | 96 | 2 | 1 | 192 | 384 | FP32 | 28 cycles | 4,124 | 19.2 GSROp/s | 38.4 Gmul/s |

4,096-vector功能测试每路检查786,432次 SROp，也就是786,432个 S36 Q12.24 contribution，全部为
0 mismatch。三路稳态吞吐相同，周期差异只来自流水填充和排空。

## 5. Post-route资源与时序

下表同时列出 Vivado 标准 `CLB LUTs Used` 和 LUT primitive 数量，避免混用两种
统计口径。资源横向比较应优先使用 `CLB LUT`。

| 版本 | CLB LUT | LUT primitive | FF | CARRY8 | DSP48E2 | DSP/lane | BRAM/URAM | WNS | WHS | 推导Fmax | Fmax推导算力 | 资格 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SC-auto | 48,734 | 57,191 | 1,921 | 1,160 | 192 | 2 | 0/0 | +5.881 ns | +0.030 ns | 242.78 MHz | 46.61 GSROp/s | VALID |
| FP16 | 79,307 | 85,799 | 145,441 | 6,152 | 384 | 4 | 0/0 | +5.549 ns | +0.0096 ns | 224.68 MHz | 43.14 GSROp/s | VALID* |
| FP32 | 96,574 | 101,351 | 171,841 | 6,152 | 768 | 8 | 0/0 | +5.927 ns | +0.0068 ns | 245.55 MHz | 47.15 GSROp/s | VALID* |
| SC-LUT diagnostic | 105,182 | 128,423 | 20,929 | 5,576 | 0 | 0 | 0/0 | +4.673 ns | +0.010 ns | 187.72 MHz | 36.04 GSROp/s | DIAGNOSTIC |

`Fmax推导算力 = 192 SROp/cycle × 推导Fmax`。这些Fmax来自100 MHz post-route slack外推，
并未在该频率重新实现和仿真；正式共同工作点仍是100 MHz。

`VALID*` 审计说明：FP16/FP32 完成后，launcher `run_ooc.sh` 为接入 SC-auto而
修改，导致当前输入哈希复核仅该launcher文件漂移；RTL、AMD IP配置、DCP、时序、
DRC和route结果未变化。SC-auto输入哈希全部通过。

## 6. 同吞吐资源效率

所有行均固定在100 MHz、19.2 GSROp/s，因此下面反映的是完成相同scale恢复
吞吐所需的资源。

| 版本 | GSROp/s / 1k CLB LUT | CLB LUT / SROp-per-cycle | MSROp/s / DSP | 相对SC-auto的CLB LUT | 相对SC-auto的DSP |
|---|---:|---:|---:|---:|---:|
| SC-auto | 0.3940 | 253.82 | 100.0 | 1.000× | 1.000× |
| FP16 | 0.2421 | 413.06 | 50.0 | 1.627× | 2.000× |
| FP32 | 0.1988 | 502.99 | 25.0 | 1.982× | 4.000× |
| SC-LUT diagnostic | 0.1825 | 547.82 | N/A（0 DSP） | 2.158× | N/A |

正式默认映射对比中，SC-auto相对FP16：

- CLB LUT减少38.55%；
- FF减少98.68%；
- DSP减少50.00%；
- 首输出延迟减少89.66%（29→3 cycles）。

SC-auto相对FP32：

- CLB LUT减少49.54%；
- FF减少98.88%；
- DSP减少75.00%；
- 首输出延迟减少89.29%（28→3 cycles）。

## 7. 功耗状态

功耗 workload 为4,096个独立向量循环16次，共65,536 active cycles、
12,582,912次 SROp。目标流程为：

```text
post-route DCP
  -> timing netlist + SDF
  -> 65,536-cycle XSIM
  -> full-DUT SAIF
  -> same-DCP report_power
```

首次 SC-auto运行中，netlist和SDF导出成功，但 `xelab` 使用的 primitive timing
模型无法绑定FDRE/DSP的SDF路径，累计83,339条相关警告，最后报：

```text
ERROR: [XSIM 43-3462] Unable to annotate SDF delays in the design.
```

结果目录状态为 `FAIL_NETLIST_SIM`，SAIF未生成，FP16/FP32功耗未启动。因此当前：

| 版本 | Dynamic power | pJ/SROp | 状态 |
|---|---:|---:|---|
| SC-auto | 无有效数据 | 无有效数据 | FAIL_NETLIST_SIM |
| FP16 | 无有效数据 | 无有效数据 | NOT_STARTED |
| FP32 | 无有效数据 | 无有效数据 | NOT_STARTED |

功耗修复后统一使用：

```text
pJ/SROp = dynamic_power_W / 19.2e9 × 1e12
                = dynamic_power_W × 52.083333
```

## 8. 已核验证据

- SC-auto XSIM：`raw/sc_auto/xsim/20260913_140115_recovery_array96_4096vectors/`
- SC-auto OOC：`raw/sc_auto/ooc/20260913_140135_sc_auto_recovery_only_array96_100mhz/`
- FP16 XSIM：`raw/fp16/xsim/20260912_205818_recovery_array96_4096vectors/`
- FP16 OOC：`raw/fp16/ooc/20260913_072407_fp16_recovery_only_array96_100mhz/`
- FP32 XSIM：`raw/fp32/xsim/20260912_211016_recovery_array96_4096vectors/`
- FP32 OOC：`raw/fp32/ooc/20260913_085750_fp32_recovery_only_array96_100mhz/`
- 功耗失败证据：`raw/sc_auto/power/20260913_141058_post_route_timesim_saif_100mhz/`

## 9. 下一步

1. 修正 timing-netlist primitive library/SDF annotation流程并先做短周期冒烟测试；
2. 冒烟测试通过后再运行65,536-cycle SC-auto、FP16、FP32完整功耗；
3. 只接受SAIF精确匹配率不低于80%的结果；
4. 补齐dynamic W、pJ/SROp和能效结论。
