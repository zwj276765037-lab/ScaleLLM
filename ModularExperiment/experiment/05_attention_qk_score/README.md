# Attention QK score

- Production 锚点：`hap_qk_score_row_128`、`hap_q24k12_group_dot_s40`、`hap_score_group_scale_s35`、`hap_score_accum4_s20`。
- 输入/输出：每 key 消费 4 个 group32，输出一个 clipped S20 Q6.14 score。
- 工作负载：每 row/head 的有效 key 数 `N={1,16,32,64,112,128}`。
- 当前完成的 FP16/FP32 baseline 使用免费给定的已反量化 Q/K 做 dot 与
  `1/sqrt(128)` 缩放，只属于 `operator-only`；必须匹配 score/s。

## Boundary-inclusive 主口径（待实现）

- 孤立模块的共同逻辑输入为 RoPE 后的四份 Q `S24 Q8.16 group32`、每个 key
  的四份 K `S12 group32`、每份 K 的 native scale metadata，以及相同的
  first/last/group/mask sideband。共同观察点仍为 clipped `S20 Q6.14 score`。
- SC 路径保留 Q `S24` 和 K `S12 + code/shift` 缓存，随后直接进入 production
  `hap_qk_score_row_128`；不能把已经包含在 production QK 内的 group scale
  再实现一次。
- FP16/FP32 路径必须从上述整数 payload 自己完成 fixed-to-float、K scale
  multiply、Q format conversion 和 FP cache 写入，之后才可进入已有的共享
  16-lane QK slot。不能继续免费读取当前 `query_group_fp*`/`key_group_fp*`
  文件作为硬件输入。
- FP 前端以 16 个 lane 在 low/high half 间时间复用，目标为每两周期接收并
  缓存一个完整 group32，与 production QK 的 group `II=2` 对齐；不允许用
  32-lane 一周期前端或离线反量化隐藏资源。query load 与 key load 不重叠，
  因此固定格式转换资源应在二者间复用；FP key scale multiplier 与满负载 QK
  multiplier 的并发需求必须真实保留。
- 孤立 boundary OOC 统一包含一个完整 `N=128` key-row cache：SC 保存紧凑
  `S12 + metadata`，FP 保存已反量化 FP16/FP32。缓存深度、descriptor FIFO、
  backpressure reservation 和相同的窄串行 physical harness 都计入资源。
- 新 golden 必须按 Xilinx fixed-to-float、FP16 FTZ/舍入、两级反量化/QK
  multiply 和既定 balanced FP32 reduction 顺序重新生成；现有 operator-only
  golden 只能用于交叉检查，不能假定 bit-exact 相同。

## 与完整 Attention 链的非重叠规则

- 完整链中，Q 在 projection→RoPE 后按各自格式直接传入 QK，K 在 04 native
  producer/cache 后直接读取；03/04 已经实现的转换、量化和 cache 不得在 QK
  再实例化。
- 因而孤立 boundary wrapper 用于回答“从共同整数边界开始，一个完整 QK slot
  的独立成本”，链级顶层用于回答“整个 Attention 的净成本”。两组资源不能
  相加，最终结论只引用真实综合的非重叠链顶层。
- 当前三路 operator-only XSIM/OOC 结果在上述 boundary RTL、至少 10 seeds、
  背压和真实 trace 完成前只能形成保守子结论。

## 旧 FP 输入不可直接复用

`model/analyze_boundary_fp_inputs.py` 按显式 `S12 -> FP -> native scale
multiply` 重新计算当前 operator-only key 输入。45,184 个 lane 中，FP16 有
11,214 个缓存 bit pattern 不同；即使先对旧缓存值应用 QK multiplier 的输入
FTZ，仍有 5,580 个语义差异。根因是 1,412 个 group record 中有 351 个 FP16
scale 本身为 subnormal，显式硬件 multiplier 会先把 scale 输入 flush 为零，
而旧向量把整数与实数 scale 相乘后才一次性转成 FP16。FP32 逐 lane bit 差异为
零。

因此 boundary-inclusive FP16 必须重建 cache 文件与 score golden，不能把旧
`key_group_fp16.mem` 或 `expected_fp16.mem` 复制过去。可重复审计：

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
python3 experiment/05_attention_qk_score/model/analyze_boundary_fp_inputs.py
```

## 已冻结的 12-seed boundary workload

`model/generate_boundary_vectors.py` 已从共同整数边界生成 12 个固定 seed、全部
`N={1,16,32,64,112,128}` 的正式数据。shape 递减为外层、seed 为内层，使
72 个 row 的 terminal-key 更新始终满足 production 协议。数据包括：

- 288 个 Q group、16,944 个 K group、4,236 个 score；
- Q `S24`、K `S12`、SC metadata、FP16/FP32 native scale；
- 显式转换后 Q/K cache 的逐 bit 检查值以及三路 score golden；
- 4,235 个 FP16 subnormal scale record 和 135,367 个因显式 FTZ 变成零的
  nonzero K lane，确保真正覆盖反量化边界。

当前非硬件软件精度 RMSE 为 SC `1.1364282e-4`、FP16
`1.3105242e-2`、FP32 `1.7482514e-5`。FP16 的显著退化来自 native scale
进入 Xilinx half multiplier 时的真实 FTZ 行为；它不能用旧的一次性离线
反量化结果掩盖。向量验证命令：

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
python3 experiment/05_attention_qk_score/model/generate_boundary_vectors.py
python3 experiment/05_attention_qk_score/model/verify_boundary_vectors.py
```

## 真实 Llama trace workload

`model/generate_trace_vectors.py` 从正式 trace 的 post-RoPE Q/K 与捕获的 raw
score 派生 2 samples × layers `{0,15,31}` ×
`N={128,112,64,32,16,1}` × q-heads `{0,17}`，共 72 rows、4,236 scores、
16,944 key group32。GQA 映射固定为 q-head 0/17 → KV-head 0/4。Q 以
nearest-even 转为 S24 Q8.16；K 先转 S24，再逐完整 group32 调用 production
`kv12_quantize_s24`。三路从同一 Q S24 + K KV12/native-meta cache 边界开始，
没有把捕获 FP score 当作硬件输入。

独立 verifier 在临时目录读取 18 个源 tensor、重做全部量化与 golden，并对
19 个产物逐字节比较：

```text
M05_TRACE_VECTOR_VERIFY_PASS files=19 rows=72 scores=4236 key_groups=16944 source_tensors=18 manifest_numeric_rel_tol=1e-13 manifest_sha256=05e530d373bb4173927fddd1a174bfc0a0b9573a1ae692911a33290e13ae4f74
```

相对捕获的 FP32 raw score，SC/FP16/FP32 RMSE 分别为 `2.1699979e-3`、
`4.0669533e-3`、`2.2281306e-3`；这里包含 K KV12 输入量化，以及 production
head scale `5793/65536` 与模型 `1/sqrt(128)` 的差异。相对共同量化输入的
FP64 score，三者 RMSE 分别为 `1.2668754e-4`、`2.5513382e-3`、
`1.7617686e-5`。Q/K BF16→S24 均无饱和，KV12 无 clip，三路 score 也无
±16 clip；真实数据覆盖 96 个 FP16 subnormal scale 和 3,060 个非零 K lane
反量化 FTZ。

该 workload 已接入 `run_boundary_xsim.sh ... trace`，但当前仅为软件证据；
等待共享机器空闲后再串行做 cache+QK RTL replay。

## Boundary RTL 当前实现状态

`rtl/m05_fp_group32_dequant16.sv` 已实现共享 16-lane 的两拍 Q/K 转换前端，
并由 `tb/m05_boundary_frontend_tb.sv` 对 Q cache、K cache、tag/address、II=2
和计数器做逐 bit 检查。FP IP Tcl 与可复现运行脚本也已准备：

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
./experiment/05_attention_qk_score/run_boundary_frontend_xsim.sh fp16
./experiment/05_attention_qk_score/run_boundary_frontend_xsim.sh fp32
```

当前只完成 source/path/shell/vector 静态预检。为遵守大型任务严格串行，上述
XSIM 要在主优先级 12/03 闭环后严格串行执行；未通过
Vivado elaboration/bit-exact 前不得视为硬件证据。

SC 侧 `rtl/m05_sc_qk_boundary_cache.sv` 已加入四份显式 Q S24 register、512
份 `K S12 + metadata` block-RAM cache、共同 II=2 load gate、同步 replay
buffer，并直接连接未修改的 production QK。对应 source list 已准备，但同样
尚未 Vivado elaboration，不能宣称 cache inference、功能或吞吐已经通过。

FP 侧 `rtl/m05_fp_qk_boundary_cache.sv` 已把同一 16-lane conversion/scale
前端、四组转换后 Q、完整 512-group FP K cache、同步 replay buffer 与已有
matched-throughput 16-lane QK slot 放入单一层级。FP16/FP32 固定 wrapper 和
`boundary_fp.sources` 已准备，三路完整逻辑边界现已对齐。

`tb/m05_qk_boundary_cache_tb.sv` 与 `run_boundary_xsim.sh` 现已覆盖完整 12-seed
workload、三路独立 golden、72 次 load/start/replay、周期/伪随机背压、输出
稳定性、mask/index/last sideband、cache/core 计数和 load II=2。TB/source/script
静态预检通过，但尚未 Vivado elaboration。

`rtl/m05_qk_boundary_serial_ooc_wrapper.sv` 现已加入三路共用的 256-bit physical
harness：每条 Q、K 或 start command 固定占四个 input word，每个 score 固定占
一个 output word，完整 cache、boundary conversion 和 QK 算术均保留在物理顶层
内部。对应 smoke TB、SC/FP source lists、FP IP 合并 Tcl、serial XSIM runner 和
100 MHz OOC runner 已通过 shell/Tcl 完整性、source existence、module/endmodule、
256-bit 拼接及 counter expectation 静态检查。它们仍未经过 Vivado elaboration；
任何新增功能、资源或速度结论必须等待 XSIM 与 post-route 门禁。

`create_boundary_all_fp_ip.tcl` 已改为自包含文件，内容与 operator/boundary
两个原始 IP Tcl 的顺序拼接逐字一致。公共 OOC runner 保存的 driver 哈希因此
覆盖全部 FP IP 配置，不再遗漏嵌套 `source` 的传递依赖。
