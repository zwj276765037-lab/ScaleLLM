# 12 MLP Down A8W4 projection

> **Min/Max/FP 语义修正状态（2026-09-10）**：三层 257 MiB 真实 trace 已用原始
> Group32 Min/Max S35 activation 生成；随后按 AMD FP16 minimum-normal underflow
> 实测语义修正 golden，并完成第二次独立全量重生/逐文件 byte-compare。当前 manifest
> 为 `4074940a6004d6487ef19705caf70bcf542e7c65fccce25d8117831e8883945c`，
> FP 语义模型 SHA-256 为
> `751afbead80f4e393c99fedbed609f997301eaab88b43ed39ddbb9f276e2a09b`。
> robust-clipping 旧数据与“IEEE 舍入后再 FTZ”的旧 FP16 golden 分别完整保留在
> `data_trace_robust_clipping_legacy/` 和
> `data_trace_fp16_round_then_ftz_legacy_20260910/`。修正前 FP16 layer-0 FAIL 永久
> 保留为 diagnostic；修正后的 FP16 RTL 重跑尚未执行，不能提前记为 PASS。

- 状态：`RUNNING`（FP16 golden 修复与双重重生已完成；SC 三层 full-shape trace
  XSIM 的数值/协议均 PASS，但通用输入哈希因 FP16 修正涉及的 generator、manifest
  与非 SC golden 更新而发生当前态漂移，需刷新运行；FP16 修正后重跑、FP32 XSIM
  和三路 OOC 均待执行）
- 2026-09-11 当前态复核：统一 preflight、mini 独立重生和 raw audit 均
  PASS；raw audit 为 `total=203 valid_candidates=57 running=0
  invalid_or_diagnostic=146`。共享主机仍有非 ModularExperiment 的
  Vivado/XSIM，本模块未启动新 run，仍等待 fail-closed 门禁放行。
- 工作单位：448 个 group32 后的一份 physical `16 rows x 12 columns` Down tile
- 完整几何：342 个 physical tiles，最后一 tile 使用 `0x00f` tail mask，共覆盖 4,096 个有效输出
- 主比较：SC S45 group-major state/round-repack 与等 input/tile throughput 的 FP16/FP32 scale application 和 FP32 state/add
- 固定硬件条件：`xcvu9p-flga2104-2L-e`、Vivado 2025.2、100 MHz、`HD.CLK_SRC=BUFGCE_X0Y0`、setup uncertainty 0.150 ns、hold uncertainty 0 ns

## 当前证据等级

| 版本 | full-shape 软件 golden | 新 full/trace XSIM | 100 MHz post-route | 当前结论资格 |
|---|---|---|---|---|
| SC | PASS | layer-0/15/31 数值/协议 PASS；当前通用输入哈希待刷新 | 待测 | 已解释的 RTL 子证据，正式候选需刷新运行 |
| FP16 | 修正后 golden PASS | 修正前 layer-0 diagnostic FAIL；重跑待执行 | 待测 | 暂无可引用 RTL 数值证据 |
| FP32 | PASS | 待测 | 待测 | 仅软件精度/向量证据 |

模块当前没有可引用的三路硬件资源或同吞吐速度结论。早期 production
shared-dual-slice 和 96-lane accumulator 小几何 XSIM 仅证明基础 SC 叶子可以运行，
没有覆盖新的 448-group、342-tile group-major 顶层，不能升级为主结果。

## 正式固定 workload

`experiment/12_mlp_down_a8w4/data/` 包含 12 个 `.mem` 文件和一个
`manifest.json`，合计约 86 MiB。输入顺序严格为
`index = group * 342 + tile`：

- 448 groups × 342 tiles = 153,216 输入事务；
- 每个事务计算 `16 x 12` 输出通道的 group32 contribution；
- 342 个输出 tile，最后一 tile 仅列 0–3 有效；
- 12 个固定 seed：4609–4620，并按 tile 确定性派生；
- SC、FP16 和 FP32 分别保存原生 scale metadata 和硬件语义 golden；
- FP16 workload 含 152,519 个下溢为零的 group contribution，用于覆盖 FTZ/舍入路径。

`verify_vectors.py` 已重新检查全部文件的行数、十六进制位宽、shape、tail
mask 和 SHA-256，结果为：

```text
M12_VECTOR_VERIFY_PASS files=12 fp16_boundary_cases=3
```

manifest SHA-256：

```text
ac8e28c64f8389ba888e65c479c0858da692389f51aab177c2583b191934328e
```

## 软件精度

共同 reference 是 exact integer dot 乘精确 `code / 2^shift` scale 后跨
448 groups 累加的实值结果。FP16 路径为 S17→FP32→FP16、两次 FP16
multiply、FP16→FP32 后进入 FP32 state/add；FP32 路径为 S17→FP32、两次
FP32 multiply、FP32 state/add。

| 版本 | max abs error | mean abs error | RMSE | cosine similarity |
|---|---:|---:|---:|---:|
| SC | `1.5037134e-5` | `6.4344503e-6` | `7.7055634e-6` | `0.9999999999986661` |
| FP16 | `9.4402246e-3` | `1.1507838e-3` | `1.4688116e-3` | `0.9999999519225544` |
| FP32 | `2.4633482e-5` | `4.0462260e-6` | `4.7917034e-6` | `0.9999999999994785` |

当前固定 workload 中，SC 精度显著优于 FP16；FP32 的 mean/RMSE/cosine
略优于 SC，而 SC 的 max absolute error 小于 FP32。这里只是 Down projection
的确定性软件模型结果，正式结论仍要求 RTL 与对应 golden bit-exact，并需要
后续真实 SwiGLU trace 和完整 MLP chain 验证。

## 真实 Llama trace + checkpoint workload

`data_trace/` 已从正式冻结的 Llama-3.1-8B-Instruct trace 和 checkpoint 派生
三份独立 full-shape workload：层 0/15/31，每层使用 2 samples × 8 tokens =
16 rows、448 groups × 342 tiles = 153,216 transactions、65,536 个有效输出。
三层合计 459,648 transactions、196,608 个有效输出，目录约 257 MiB。

权重不是随机 S4：generator 读取各层真实 `down_proj.weight`，调用 production
V5 artifact exporter 完成 normalized folded group32、max-abs/7、ScaleCode
U8/shift6、对 decoded scale 的 round-half-away 和 S4 `[-8,7]` clamp。
activation 来自实际 BF16 `down_proj` pre-hook tensor，经 production 定点
Hadamard 与独立原始 Min/Max A8 reference 量化，量化前 clip 为 0。M12 三路共享 centered S9/W4 payload 和 decoded
scale，只改变 scale 的 SC/FP16/FP32 表示与应用，因此 M11 producer 只计一次。

全量独立临时重生成和逐字节比较已通过：

```text
M12_TRACE_VECTOR_VERIFY_PASS files=38 layers=3 rows=48 transactions=459648 valid_outputs=196608 regenerated=1 fp16_boundary_cases=3 source_tensors=6 manifest_sha256=4074940a6004d6487ef19705caf70bcf542e7c65fccce25d8117831e8883945c
```

相对 raw BF16 activation × checkpoint BF16 weight 的 FP64 dot，逐层 RMSE 为：

| layer | SC | FP16 | FP32 | S24 saturation/版本 |
|---:|---:|---:|---:|---:|
| 0 | `3.9469860e-3` | `5.2208961e-3` | `3.9469214e-3` | 0 |
| 15 | `6.9021009e-3` | `6.9043436e-3` | `6.9020167e-3` | 0 |
| 31 | `1.6302913` | `1.6302909` | `1.6302913` | 6 |

layer 31 的聚合误差由真实输出范围问题主导：三路都在 row 0/8、输出列
788/1384/4062 饱和到 S24 Q16.16 的 ±128 边界。该负面证据已保留，不能用
较小 token 子集规避。层 0/15 没有输出饱和；相对共同量化 FP64 reference，
层 0 的 SC/FP16/FP32 RMSE 分别为 `1.4028e-5/3.4891794e-3/4.3983e-6`，层 15
分别为 `1.3706e-5/1.7102386e-4/4.4057e-6`。修正后 layer-0/15/31 的 FP16
下溢为零 contribution 分别为 `18,816,705/758,988/104,464`。

SC layer-0/15/31 full-shape trace 已完成真实 RTL replay；每层均为
448 groups × 342 tiles = 153,216 transactions、65,536 个有效输出全部逐项匹配，
0 mismatch、input II max=1、首输出延迟 152,892 cycles、总周期 153,234；
layer-0/15 为 0 saturation，layer-31 正确保留 6 个真实 S24 饱和点。正式 run 分别为
`raw/sc/xsim/20260910_122518_down_a8w4_trace_l00_full_448x342_group_major/` 和
`raw/sc/xsim/20260910_125653_down_a8w4_trace_l15_full_448x342_group_major/`、
`raw/sc/xsim/20260910_132657_down_a8w4_trace_l31_full_448x342_group_major/`；三者均
`STATUS=PASS`、exit 0，且运行目录自身 `SHA256SUMS` 仍通过。修正前后只有三层的
`expected_fp16_s24x16x12.mem` 和 manifest 改变，SC 输入、metadata 与
`expected_sc` 均逐字节相同；因此三条运行仍是有效的 SC 数值/协议诊断证据。
不过 runner 当时把三路全部 golden 和共享 generator/manifest 一并纳入通用
`INPUT_SHA256SUMS`，当前统一 raw audit 会因 FP16 语义修正引发的这些 provenance
变化将它们判为 input-hash drift。runner 现已改为只读取并哈希共同输入与所选
variant 的 metadata/golden；为遵守正式门禁，三条 SC 运行仍需在当前 manifest 下
刷新后才能重新列为 `VALID_CANDIDATE`，不能替代 FP16/FP32 或 post-route。

## FP16 layer-0 首跑负结果与根因

正式首跑位于
`raw/fp16/xsim/20260910_135832_down_a8w4_trace_l00_full_448x342_group_major/`。
它自然运行 8:00:42 后结束为 `STATUS=FAIL`、exit 1；153,216 个输入事务、448
groups、342 个输出 tile 均完整通过，`input II max=1`，但 200 个 tile 的 4,608-bit
payload 与旧 FP16 golden 不同。输入 `INPUT_SHA256SUMS` 和结果目录
`SHA256SUMS` 均在修复前逐项通过，因此该失败不是输入漂移、工具中止、事务丢失
或输出重排。

旧 `generate_vectors.py`（SHA-256
`fdb84addb8ef13b589e319aaef4ead8eddc898beb95e23f5d977dac94f0f1bb2`）把 AMD
FP16 multiply 建模为“NumPy/IEEE 舍入后再 FTZ”。M02 的 generated-IP 实测已经
证明，AMD IP 在 minimum-normal 边界会先做 underflow 判定，阈值为
`tiny - smallest_subnormal/4`。对首跑完全相同的 layer-0 `.mem` 做单线程离线
重放后，旧模型与冻结 golden 为 0 element/0 tile 差异；换成已实测 AMD 阈值后
恰好变化 314 个输出 element、分布在恰好 200 个 tile，且 200 个 tile 索引与 RTL
mismatch 列表逐项一致。变化全部发生在第二次 FP16 scale multiply；第一乘为 0
差异。该一一对应证据将问题归因于 golden 语义，而不是修改 RTL 来迎合旧 golden。
失败 run 永久保留为 diagnostic，不能用于 FP16 精度或速度结论。

修正后的 synthetic 与三层 trace 已重生；新旧 trace payload 只有三份
`expected_fp16_s24x16x12.mem` 改变，layer-0/15/31 分别变化
`314 elements/200 tiles`、`117 elements/80 tiles`、`17 elements/15 tiles`。
当前完整性复核为：

```text
M12_TRACE_VECTOR_VERIFY_PASS files=38 layers=3 rows=48 transactions=459648 valid_outputs=196608 regenerated=0 fp16_boundary_cases=3 source_tensors=6 manifest_sha256=4074940a6004d6487ef19705caf70bcf542e7c65fccce25d8117831e8883945c
```

独立 correction auditor 还会校验新旧目录仅三份 FP16 golden 发生 payload 变化、
逐层 element/tile 计数、代表边界位型、失败目录自身哈希与 Layer-0 RTL mismatch
集合，当前结果为：

```text
M12_FP16_CORRECTION_VERIFY_PASS files=38 changed_payloads=3 changed_elements=448 changed_tiles=295 layer0_rtl_mismatch_tiles=200 fp16_boundary_cases=3 manifest_sha256=4074940a6004d6487ef19705caf70bcf542e7c65fccce25d8117831e8883945c
```

## 已准备的公平硬件实现

- SC 使用 production packed A8W4 dot、ScaleCode 整数乘法/移位 recovery、
  192 个 S45 group-major tile-state banks 和共同 S24 round/saturate 输出。
- FP16/FP32 使用同一 packed dot；每个 contribution 在原生 FP scale 路径中
  完成两次乘法，并以 FP32 tile state/add 跨 448 groups 累加。
- 三路完整顶层均以一个 group-major transaction/cycle 为目标；342 tiles
  大于 state read/modify/write latency，因此无需复制核即可避免同地址冒险。
- 正式 OOC 使用相同 256-bit serial physical harness，保留完整 16×12 算术和
  全部 342-tile state banks，避免超宽逻辑总线被错误解释为器件 I/O 需求。

## 静态预检

- `run_serial_xsim.sh`、`run_full_xsim.sh`、`run_matched_ooc.sh` 均通过
  `bash -n`；
- `sc.sources`、`sc_ooc.sources`、`fp.sources`、`fp_ooc.sources` 中的每个
  源文件均存在；
- 三种 OOC top、serial/full TB 顶层及 source list 的模块名已交叉检查；
- `generate_vectors.py` 通过 Python 语法检查，`manifest.json` 通过 JSON
  解析，修正后的 FP16 路径描述与 RTL 一致；
- 元数据修正后再次执行 `verify_vectors.py`，12 份向量哈希仍全部 PASS。
- 后续 OOC 的 `INPUT_SHA256SUMS` 会同时绑定通用 OOC shell/Tcl、模块 launcher、
  source list、generated-IP recipe 和全部 RTL，IP/driver 漂移会被 raw audit 拒绝；
- 新增可复跑的静态合同 verifier，真实解析四份 source list，并绑定六个
  OOC/XSIM top、三种 serial payload 位宽/索引、full-shape 常量和七个 Xilinx
  FP IP latency 与 RTL delay 常量；当前结果为：

```text
M12_STATIC_CONTRACT_VERIFY_PASS source_entries=28 modules=21 tops=6 ip_latencies=7 payload_variants=3 trace_layers=3 nonzero_mini=1 wave_ab=1 vivado_guard=1
```

这些检查只关闭脚本、路径和元数据问题，不能替代 Vivado elaboration 或
behavioral XSIM；当前 SC 三层均已取得实际 full-shape XSIM 资格。

## 当前功耗状态

当前不发布 post-route 功耗数值，因为 SC/FP16/FP32 均尚无通过门禁的 routed DCP。已有 full-shape/mini workload、RTL 与功能证据不能替代 implementation 网表；在 routed DCP 产生前也不能用综合前资源或默认 toggle rate 冒充波形驱动功耗。后续必须按统一的 `100 MHz behavioral XSIM → DUT SAIF → 对应 routed DCP → Vivado report_power` 流程分别测量三路，并报告精确 SAIF 匹配率、置信度、高-X警告及动态能量。

## 下一轮执行顺序

已建立完整 96 pair-lane/192 output-lane、`5 groups × 16 tiles` 的非零小型
workload 和成对 A/B runner。80 个 payload 均非零，64 个 group/tile 有非零算术
贡献（group 0 是定向零边界），三路各 2,944 个有效输出元素全部非零；独立重生
逐字节 PASS，manifest 为
`a7d4b14bf67e6a8ab495b20f055fbd6fcc97ca7093b8e2d76c27311aaf95af23`。

```text
M12_MINI_VECTOR_VERIFY_PASS files=7 groups=5 tiles=16 transactions=80 nonzero_variants=3 fp16_boundary_cases=3 full_subset_bound=1 regenerated=1 manifest_sha256=a7d4b14bf67e6a8ab495b20f055fbd6fcc97ca7093b8e2d76c27311aaf95af23
```

runner 将分别执行默认 WDB 与 debug-off/no-wave，两者的 288 个输出 word、握手、
latency、II 和总周期必须完全一致。当前用户 Vivado/XSIM 活跃，fail-closed 并发
门禁已对 serial A/B、full XSIM 和 OOC 三类入口实测均以 exit 75 拒绝启动；同一
非阻塞 `flock` 还防止 ModularExperiment 自身误并发。A/B 通过后再刷新 full 153,216-transaction
workload，最后才做大型 post-route：

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
./experiment/12_mlp_down_a8w4/run_serial_ab.sh sc 1
./experiment/12_mlp_down_a8w4/run_serial_ab.sh fp16 1
./experiment/12_mlp_down_a8w4/run_serial_ab.sh fp32 1
./experiment/12_mlp_down_a8w4/run_full_xsim.sh sc synthetic nowave
./experiment/12_mlp_down_a8w4/run_full_xsim.sh fp16 synthetic nowave
./experiment/12_mlp_down_a8w4/run_full_xsim.sh fp32 synthetic nowave
./experiment/12_mlp_down_a8w4/run_matched_ooc.sh sc
./experiment/12_mlp_down_a8w4/run_matched_ooc.sh fp16
./experiment/12_mlp_down_a8w4/run_matched_ooc.sh fp32
```

synthetic 三路 full XSIM 通过后，再以第二参数 `trace_l00`、`trace_l15`、
`trace_l31` 严格串行重放三层真实数据，例如：

```bash
./experiment/12_mlp_down_a8w4/run_full_xsim.sh sc trace_l00 nowave
./experiment/12_mlp_down_a8w4/run_full_xsim.sh fp16 trace_l00 nowave
./experiment/12_mlp_down_a8w4/run_full_xsim.sh fp32 trace_l00 nowave
```

所有 Vivado/XSim 命令严格串行。只有三路功能、II/周期、资源、WNS/WHS、
DRC、unrouted 和目录/输入哈希均通过后，本页才会给出 Down 模块硬件结论。
