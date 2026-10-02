# Attention RoPE

- Production 锚点：`hap_rope_pair_s24`。
- 输入：Q/K 偶奇 S24 pair 与 S18 sin/cos；V 不进入本模块。
- 输出合同：每 accepted pair 产生一个旋转后的 pair；记录 latency、steady II、pair/s 和饱和计数。
- 当前已经闭环的 FP16/FP32 baseline 从已反量化 Q/K 与对应浮点
  sin/cos 开始，只属于 `operator-only` 子实验；现有结果不包含输入反量化，
  不得标为 boundary-inclusive。

## Boundary-inclusive 主口径（RTL 待验证）

主口径从 projection→RoPE 的真实格式边界开始，而不是再次对已经形成的
S24/FP 值重复计费：

- 共同输入为 projection 整数 correlation、activation/weight scale 元数据和
  S18 sin/cos 系数；workload、pair 顺序及 ready/valid 压力完全一致。
- SC 路径计入 ScaleCode recovery、移位/舍入/饱和形成 S24，然后进入
  production `hap_rope_pair_s24`。
- FP16/FP32 路径计入 correlation 的 int-to-float、两次 scale multiply，
  并计入 S18 sin/cos 到对应 FP 格式的转换；随后在 FP 格式中完成 RoPE，
  只在共同 S24 观察点转换一次。
- Attention 链顶层中 projection→RoPE 连续保持 FP，反量化边界只计一次；
  本模块的孤立 boundary-inclusive 面积不得与模块 02 的同一 scale-apply
  资源重复相加。

### 已冻结的实现合同

为避免把单个 group contribution 冒充完整 projection，本模块的正式工作单位
冻结为一对输出元素的完整 `128 group32 -> projection tail -> RoPE`：

- 每个 group 的共同算术输入是两个已经完成 pre-centered MAC 的 signed S21
  correlation；activation scale 在该 row/group 内共享，两个 weight scale 分属
  偶、奇输出列。SC code/shift 与 FP16/FP32 IEEE scale 都由同一解码实值生成，
  不能由某一路运行结果事后转换得到另一条路径的输入。
- `in_first_group`/`in_last_group` 明确界定 128-group pair；S18 Q2.16 sin/cos
  随 pair 输入并在首 group 接受时冻结。正式 workload 至少覆盖 12 个固定 seed、
  正负 correlation、零值、合法 shift 边界、尾部饱和与周期/伪随机背压。
- SC 每 group 执行 `corr * act_code * weight_code` 后按总 shift 对齐到 S42
  Q18.24，按 production 顺序跨 128 groups 累加，使用与 projection 相同的
  round-half-away-from-zero 和 S24 饱和，然后进入 production
  `hap_rope_pair_s24`。
- FP16 依次执行 `S21 -> FP32 -> FP16`、两次 FP16 multiply、`FP16 -> FP32`；
  FP32 在单精度中执行两次 multiply。两条 FP 路径都在 FP32 state 中跨 128
  groups 累加，随后直接以 FP 形式执行 RoPE，最后只在共同观察点做一次
  FP32→S24 Q8.16 转换。FP16/FP32 都必须计入 S18 Q2.16 sin/cos→对应 FP
  格式的转换。
- 共同输入接受锚点为 production projection lane 的 `II=2`。FP32 add latency
  若形成反馈依赖，baseline 必须以交错 state bank、复制或等价真实 RTL达到
  `II<=2`；不得用一个低吞吐 accumulator 的面积冒充同算力 baseline。任何
  交错 reduction 顺序都必须在 manifest 中冻结并由逐级 IP 语义 golden 验证。
- 主表分别报告 input II、pair 输出间隔、首输出/整批周期和 100 MHz 资源；若
  单核持续 pair rate 低于 SC，则按最小实测整数复制数综合真实 replicated top，
  不能只做面积乘法估算。

该 pair 链刻意从 pre-centered correlation 开始，因此不重复计算模块 02 中三路
共同的 U8/S8 MAC；最终 Attention 非重叠链仍需把共享 MAC、scale boundary 和
RoPE 只实例化一次后重新综合。

## 真实 projection-input 补充捕获

原冻结 trace 只保存 projection 后的 pre/post-RoPE Q/K，无法合法反解本模块
边界所需的 128 组 correlation、activation scale 和 folded-weight scale。
`model/capture_trace_projection_inputs.py` 因此用冻结的两个 input-ID 序列和同一
checkpoint 重新前向，只捕获 q_proj/k_proj 的共同输入。捕获结果保存在
`data_trace_projection_input/`，包含 2 samples × layers `{0,15,31}` 共 6 个
`128×4096` BF16 tensor，并绑定三个实际 Q/K checkpoint shard。

补充捕获同时重新计算完整 Q/K pre-RoPE tensor，与旧冻结 trace 做交叉检查。
layer 0/15 的八次检查逐 bit 相同；layer 31 的四次检查观察到深层 BF16 前向
非 bit-reproducible，不能伪装成 bit-exact。两样本 Q/K 合计保留 824,370 个
bit-pattern mismatch，最坏 normalized RMSE 为 `3.9763205e-3`，最低 cosine 为
`0.999992094591`；门禁为 normalized RMSE `<=0.02` 且 cosine `>=0.9998`。
捕获与独立完整性校验结果为：

```text
M03_PROJECTION_INPUT_CAPTURE_PASS files=6 samples=2 layers=3 qk_checks=12 bit_mismatches=824370 manifest_sha256=53e54b7d88138a83ff1e56fec7653ccdd4206cc12382c7606c616764ccff2ff1
M03_PROJECTION_INPUT_VERIFY_PASS files=6 samples=2 layers=3 qk_checks=12 bit_mismatches=824370 manifest_sha256=53e54b7d88138a83ff1e56fec7653ccdd4206cc12382c7606c616764ccff2ff1
```

这份补充数据来自同一 input IDs/checkpoint 的真实重放，但 layer 31 与原冻结
trace 的差异仍作为 provenance 限制保留；后续精度表同时报告相对本次捕获输入
的 checkpoint FP64 reference 和相对原冻结 BF16 输出的误差。

## 真实 M03 boundary workload

`model/generate_trace_vectors.py` 从上述真实 attention 输入和 checkpoint Q/K
权重生成 12 个 Q/K RoPE pair，每个 pair 完整重放 128 个 group32，共 1,536
transactions。生成器现已切换为 production fixed-point Hadamard + 实验内原始
Min/Max A8；两个对应
weight row 执行 production V5 normalized folded W8 量化；correlation 是真实
centered U8×S8 dot，scale metadata 直接来自两侧 production 量化，不从 Q/K
输出反造。12 个坐标覆盖两个样本、三层、Q/K、不同 token/head/rotary pair。

当前范围、精度和 manifest hash 来自原始 Group32 Min/Max trace。激活量化前
`pre_quant_clip_lanes=0`；correlation 范围 `[-181274,143878]`，ScaleCode
total shift 为 `[31,41]`，全部满足 S21 与 production `[26,47]` 合同。完整
临时重生成与逐字节比较结果为：

```text
M03_TRACE_VECTOR_VERIFY_PASS files=10 pairs=12 transactions=1536 source_tensors=18 regenerated=1 manifest_sha256=0c39d93a305b96deccd0a144d0d41a0c63fe5a265d634ad0487fc8578618b3a5
```

真实范围暴露了一个必须保留的 FP16 负面结果：88 个 S21 correlation 在
`S21→FP32→FP16` 后变为非有限值，污染 53 个最终 accumulator bank、19 个
projection 元素和 60 个 RoPE 中间值；12 个 pair 中 11 个受到影响，最终 22/24
个 FP16 RoPE 输出落到软件定义的 S24 饱和值。相对共同量化 FP64，SC/FP16/FP32
RMSE 分别为 `6.9432013e-6/122.0997312/4.0256286e-6`。该 FP16 行为必须由
Xilinx IP 的真实 trace XSIM 复核；在 RTL PASS 前，它是软件范围证据，不是
硬件结论，也不能通过挑选较小 correlation 的 token 来规避。

生成、校验与后续串行 RTL replay：

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
/home/user/anaconda3/envs/zhouwenjun/bin/python experiment/03_attention_rope/model/capture_trace_projection_inputs.py
/home/user/anaconda3/envs/zhouwenjun/bin/python experiment/03_attention_rope/model/verify_trace_projection_inputs.py
/home/user/anaconda3/envs/zhouwenjun/bin/python experiment/03_attention_rope/model/generate_trace_vectors.py
/home/user/anaconda3/envs/zhouwenjun/bin/python experiment/03_attention_rope/model/verify_trace_vectors.py
./experiment/03_attention_rope/run_boundary_xsim.sh sc 0 trace
./experiment/03_attention_rope/run_boundary_xsim.sh fp16 0 trace
./experiment/03_attention_rope/run_boundary_xsim.sh fp32 0 trace
```

正式补充捕获默认拒绝覆盖已有目录；前三条生成/捕获命令只在重建到新目录或先
完成有意的证据迁移时使用。三条 XSIM 当前尚未执行；后续必须遵守大型
Vivado/XSIM 严格串行。

在上述三路功能、同吞吐、100 MHz post-route、DRC/unrouted 和证据哈希全部
通过前，模块 03 的主结论保持未完成。
