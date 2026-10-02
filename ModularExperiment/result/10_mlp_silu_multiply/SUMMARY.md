# 10 MLP SiLU(Gate) × Up

- 状态：`RUNNING`（operator-only 硬件子实验完成；12-seed 与真实 trace 两套 boundary 软件向量 PASS；双 lane boundary RTL/TB 已静态预检，Vivado elaboration/XSIM/OOC 待执行）
- 工作单位：一个 `SiLU(gate) × up` 结果；production 顶层为两条 row-local lane
- 比较版本：四级 SC 定点近似流水、FP16 与 FP32 `exp/add/div/mul` 非阻塞流水
- 统一实现条件：Vivado 2025.2，`xcvu9p-flga2104-2L-e`，100 MHz，`HD.CLK_SRC=BUFGCE_X0Y0`，setup uncertainty 0.150 ns，hold uncertainty 0 ns

## Boundary-inclusive 软件证据

正式 workload 使用 12 个固定 seed、每 seed 512 个 Gate/Up pair，共 6,144
vectors。9 个 `.mem` 保存共同 S24 Q8.16 输入、显式 FP16/FP32 fixed-to-float
值和三路 S32 Q16.16 reference。独立 verifier 已用 production
`mlp_fixed.swiglu_product_s32` 和 8192-entry SiLU LUT 重算全部 SC golden，并
核对转换值、记录宽度/数量和全部哈希：

`M10_BOUNDARY_VECTOR_VERIFY_PASS files=9 seeds=12 vectors=6144`

manifest SHA256：
`a9f253be24dd48fc54297900c91f44268c963d81b10ac9618809ed1b811bc568`；
二次生成的 `data_boundary/` 聚合哈希保持不变。

| 软件路径 | max abs error | mean abs error | RMSE | cosine |
|---|---:|---:|---:|---:|
| SC | `1.1897728e-1` | `5.7314607e-3` | `1.4572631e-2` | `0.999999999511126` |
| FP16 | `1.7698705` | `4.1818830e-2` | `1.1364612e-1` | `0.999999970330409` |
| FP32 | `1.1106603e-4` | `5.7883154e-6` | `9.9087905e-6` | `0.999999999999997` |

误差相对稳定 FP64 `SiLU(gate)×up`。workload 覆盖 3,090 个负 Gate、3,053 个
正 Gate、8 个 S24 endpoint 和 SiLU LUT 两侧区间；三路软件输出均未发生 S32
饱和。双 lane boundary RTL/TB 与运行脚本已经落盘并通过静态完整性预检；实际
Xilinx fixed-to-float/exp/add/div/mul 数值、协议、周期、资源和时序仍必须等待
Vivado elaboration、boundary XSIM 与 OOC，当前没有新增硬件 PASS 结论。

## 真实 trace 软件证据

真实 workload 从正式 trace 选择 2 samples、layers `{0,15,31}`、8 个覆盖全序列
的 token，以及从 14,336 intermediate channels 以 stride 112 均匀抽取的
128 个通道，共 6,144 个 Gate/Up pair。BF16 Gate/Up 都以 nearest-even 转为
共同 S24 Q8.16；每条坐标与 12 个源 tensor 的 payload hash 均被保存。

`M10_TRACE_VECTOR_VERIFY_PASS files=11 vectors=6144 source_tensors=12
manifest_numeric_rel_tol=1e-13
manifest_sha256=bc7b6a64fe7efd65692b9baf91b190c0a7e7ad1b9023aa4211c2eed0ee16492b`

| 软件路径 | max error vs raw trace | RMSE vs raw trace | cosine vs raw trace | RMSE vs common S24 |
|---|---:|---:|---:|---:|
| SC | `6.2571238e-3` | `2.1860990e-4` | `0.9999995425668361` | `2.1860979e-4` |
| FP16 | `2.5256057e-3` | `8.4334996e-5` | `0.9999999339884561` | `8.4334977e-5` |
| FP32 | `9.4334681e-6` | `4.4131891e-6` | `0.9999999998135269` | `4.4128258e-6` |

Gate/Up BF16→S24 和三路 S32 输出都没有饱和。真实分布覆盖 4,028 个负 Gate、
2,116 个正 Gate，但没有越过 ±16 LUT 边界，所以 directed synthetic workload
仍是极值/分段覆盖的必要组成部分。runner 已支持 `... trace`，尚未执行 RTL
trace XSIM，以上不能计作新的硬件结果。verifier 对硬件 payload 保持逐字节比较；
manifest 结构和非浮点字段严格相等，仅浮点归约指标允许 `1e-13` 相对容差。

## 功能、精度和周期

| 版本 | 功能/精度 | 稳态输入 II | 首输出延迟 | 512-vector 周期 |
|---|---|---:|---:|---:|
| SC | PASS，512 vectors，bit-exact，0 mismatch | 1 | 4-stage production pipe | 540 |
| FP16 operator-only | PASS，容差内 0 mismatch；MAE 0.582031 S32 LSB，max 256 LSB | 1 | 54 cycles | 592 |
| FP32 operator-only | PASS，当前 golden 下 MAE/max error 均为 0 | 1 | 74 cycles | 612 |

三种单 leaf 均可持续接受 1 element/cycle，因此匹配单 leaf 吞吐不需要额外复制。相同 512-vector 回归下，SC 相对 FP16 的整批周期加速为 `592/540 = 1.096×`，相对 FP32 为 `612/540 = 1.133×`；差异来自 FP 流水的填充/排空延迟，不代表稳态 II 高于 1。

## 100 MHz post-route 结果

### 单 leaf

| 版本 | LUT | FF | DSP48E2 | BRAM36 | WNS (ns) | WHS (ns) | 推导 Fmax (MHz) | DRC | Unrouted | 有效性 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SC | 200 | 104 | 2 | 6 | 5.551 | 0.024 | 224.770 | 0 | 0 | VALID |
| FP16 operator-only | 3391 | 9432 | 5 | 0 | 4.928 | 0.012 | 197.167 | 0 | 0 | VALID |
| FP32 operator-only | 6034 | 15388 | 5 | 0 | 2.967 | 0.010 | 142.178 | 0 | 0 | VALID |

### Production 两 lane (`x2`) 顶层

| 版本 | LUT | FF | DSP48E2 | BRAM36 | WNS (ns) | WHS (ns) | 推导 Fmax (MHz) | DRC | Unrouted | 有效性 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SC x2 | 400 | 208 | 4 | 12 | 5.182 | 0.021 | 207.555 | 0 | 0 | VALID |
| FP16 operator-only x2 | 6782 | 18864 | 10 | 0 | 4.468 | 0.011 | 180.766 | 0 | 0 | VALID |
| FP32 operator-only x2 | 12354 | 30790 | 10 | 0 | 3.874 | 0.010 | 163.241 | 0 | 0 | VALID |

`x2` 数据来自真实双 lane 顶层的综合与布局布线，不是单 leaf 资源的算术估算。SC 和 FP16 恰为单 leaf 的两倍；FP32 顶层由工具实现后为单 leaf 两倍再加 286 LUT、14 FF，因此正式表保留真实顶层数值。

## Operator-only 有效子结论

所有版本均达到相同的 2 elements/cycle production 逻辑输出算力，且 100 MHz setup/hold、DRC 和 unrouted 门禁全部通过。以真实 `x2` 顶层为主：

| 对比 | LUT 节省 | FF 节省 | DSP 节省 | SC 的 BRAM36 代价 | 512-vector 周期加速 |
|---|---:|---:|---:|---:|---:|
| SC 相对 FP16 | 94.10%（少 6382） | 98.90%（少 18656） | 60.00%（少 6） | 多 12 | 1.096× |
| SC 相对 FP32 | 96.76%（少 11954） | 99.32%（少 30582） | 60.00%（少 6） | 多 12 | 1.133× |

该结果证明，在已经反量化为浮点输入、且 FP baseline 不承担 int-to-float/scale multiply 成本的保守 operator-only 口径下，当前 SC SiLU 路径仍显著减少 LUT、FF 和 DSP，并降低短批完成周期；代价是每条 SC lane 使用 6 个 BRAM36 保存 SiLU 查表 ROM。boundary-inclusive 反量化边界尚未综合，因此本节不能替代最终主结论。

## 100 MHz post-route 功耗估算（behavioral SAIF）

以下是“基于仿真波形的 post-route 估算”，不是板级实测。功耗回归使用与 routed `x2` 顶层完全一致的双 lane DUT，重放 6,144 个 `SiLU(gate) × up` 产品并施加周期性 backpressure；behavioral XSIM 预热 100 ns 后记录 DUT SAIF，再导入对应 routed DCP 执行 Vivado 2025.2 `report_power`。

| 版本 | SAIF 时长 (µs) | 匹配网表节点 | 置信度 | 动态功耗 (W) | 器件静态 (W) | 总片上 (W) | 动态能量 (nJ/product) | 资格 |
|---|---:|---:|---|---:|---:|---:|---:|---|
| SC x2 | 38.295 | 295 / 1,203（24.52%） | Medium | 0.018 | 2.470 | 2.488 | 0.112 | VALID |
| FP16 x2 | 38.805 | 449 / 29,929（1.50%） | Medium | 0.138 | 2.471 | 2.610 | 0.872 | diagnostic low coverage |
| FP32 x2 | 39.005 | 671 / 51,319（1.31%） | Medium | 0.268 | 2.473 | 2.741 | 1.701 | diagnostic low coverage |

动态能量按 `dynamic_power × SAIF_duration / 6144` 计算。SC 的 SAIF 覆盖充分且无高-X警告，可作为正式模块估算；FP behavioral IP 与综合网表 primitive 的内部命名对应不足，匹配率仅 1.50%/1.31%，所以 FP 数值只作为低覆盖近似，不支持正式功耗倍数结论。约 2.47 W 静态值属于整颗 VU9P 模型，不是这两个 lane 的独占静态功耗。

## 已核验证据

- SC XSIM：`raw/sc/xsim/20260908_142059_silu_mul/`
- FP16 XSIM：`raw/fp16/xsim/20260908_153339_operator_only_single_leaf/`
- FP32 XSIM：`raw/fp32/xsim/20260908_153414_operator_only_single_leaf/`
- SC single OOC：`raw/sc/ooc/20260908_154006_sc_mlp_silu_mul_single_100mhz/`
- FP16 single OOC：`raw/fp16/ooc/20260908_154406_fp16_silu_operator_only_single_100mhz/`
- FP32 single OOC：`raw/fp32/ooc/20260908_154912_fp32_silu_operator_only_single_100mhz/`
- SC x2 OOC：`raw/sc/ooc/20260908_155505_sc_mlp_silu_mul_x2_100mhz/`
- FP16 x2 OOC：`raw/fp16/ooc/20260908_155846_fp16_silu_operator_only_x2_100mhz/`
- FP32 x2 OOC：`raw/fp32/ooc/20260908_160449_fp32_silu_operator_only_x2_100mhz/`
- 功耗证据：SC `raw/sc/power/20260912_124329_saif_post_route_100mhz/`；FP16/FP32 低覆盖诊断分别为 `raw/fp16/power/20260912_124556_saif_post_route_100mhz/`、`raw/fp32/power/20260912_124843_saif_post_route_100mhz/`

以上六个 OOC 目录均为 `STATUS=PASS`、`valid=1`，并已通过各自 `SHA256SUMS` 全量核验。

## 排除的诊断结果

- `raw/fp16/xsim/20260908_153250_operator_only_single_leaf/`：用于确认 Half→Q16.16 IP 端口限制；正式实现先扩为 FP32 再转 S32。
- `raw/sc/ooc/20260908_153515_sc_mlp_silu_mul_100mhz/`：未加载 SiLU ROM，已显式标为 `FAIL`，不得引用。
