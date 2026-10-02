# MLP product Hadamard and Down A8 scale generation

- Production 几何锚点：`hap_mlp_product_frontend16_q4`、
  `hap_mlp_hadamard32_s32_norm_stream`；本实验用四个本地 S35
  raw-Min/Max A8 drop-in，不修改 production RTL。
- 输入/输出：`16×32 S32` SwiGLU product → `16×32 U8 + 16×U24 metadata`。
- 结构合同：一个 shared II=1 Hadamard engine，4 个 quantizer；不可按 16 rows 完全展开。
- 对比 transform、scale 表示、量化/格式转换和完整 group busy cycle。

## 公平比较边界

三路都从同一 `16×32 S32 Q16.16` SwiGLU product bundle 开始，复用
production 的 shared II=1 S32 Hadamard，并采用四个 quantizer、每个处理四行
的 round-robin 调度：

- `SC`：实验内 S35 raw-Min/Max A8，输出 `zp8/code8/shift8`；
- `FP16`：原生 affine A8，输出 `zp8 + IEEE FP16 scale`；
- `FP32`：原生 affine A8，输出 `zp8 + IEEE FP32 scale`。

三路都从原始 Min/Max ideal scale 生成相同 U8/zp，量化前不裁剪；FP 路径不生成
或读取 ScaleCode。44/36 radix-16 divider 每周期产生四个商位，已扩展为
nearest-even；测试集为 265 个 directed/random（含 half-tie）case，待新 XSIM
确认。每个 FP
quantizer 使用四个 quotient lane，在保持四-quantizer
production 几何的同时达到不低于 SC 的实测 group rate。三-lane 诊断实现的
group II 为 972 cycles，未达到 SC 的 822--854 cycles，因此不进入正式主表。

正式 workload 覆盖完整 448 intermediate groups、16 rows、32 lanes。

由于功能顶层的 S32 输入和 U8+metadata 输出合计超过 20,000 个 on-chip
tile-bus bits，Vivado 会把直接 OOC 顶层误作超量 package terminals 并在 placer
拒绝。正式 post-route 因此为三路添加相同的 32-bit serial load/drain physical
harness；harness 内仍实例化完整 16-row core，量化器几何和 core group II 不变。
资源主表包含整个 physical harness，并同时保留 hierarchical core 报告。

## 真实 Llama trace workload

`model/generate_trace_vectors.py` 直接读取正式 trace 的实际
`swiglu_down_input_bf16`，选择跨 2 samples、layers `{0,15,31}` 与序列首/中/尾
位置的 16 个唯一 row。每行完整保留 14,336 intermediate channels，因此工作量
仍为 448 groups × 16 rows × 32 lanes，而不是缩小形状。BF16 以 nearest-even
转为共同 S32 Q16.16，再执行同一 production Hadamard 和三路 A8 producer。

临时重生成/逐字节 verifier 当前输出：

```text
M11_TRACE_VECTOR_VERIFY_PASS files=8 groups=448 rows=16 lanes=32 source_tensors=6 manifest_sha256=41d658905124eaa841c7e65d6769e0197e78a30f47a6def11ceae06bd4d66548
```

相对原始 BF16 row 的 FP64 normalized Hadamard，SC/FP16/FP32 重构 RMSE 分别为
`1.4611462e-3`、`1.7345517e-3`、`1.2324997e-3`；相对共同 production S35
Hadamard 输出分别为 `1.4592622e-3`、`1.7345393e-3`、`1.2323259e-3`。
BF16→S32、Hadamard、FP scale 均无 saturation/nonfinite，448×16 个真实 row 中
ScaleCode 范围溢出为 0。该 trace 已接入
`run_matched_xsim.sh ... trace`，但真实 RTL replay 尚未执行。

## 复现命令

```bash
./run_divider_xsim.sh
./run_matched_xsim.sh sc 0
./run_matched_xsim.sh fp16 0
./run_matched_xsim.sh fp32 0
./run_matched_xsim.sh sc 1
./run_matched_xsim.sh fp16 1
./run_matched_xsim.sh fp32 1
./run_matched_xsim.sh sc 0 trace
./run_matched_xsim.sh fp16 0 trace
./run_matched_xsim.sh fp32 0 trace
./run_ooc_wrapper_xsim.sh sc
./run_ooc_wrapper_xsim.sh fp16
./run_ooc_wrapper_xsim.sh fp32
./run_matched_ooc.sh sc
./run_matched_ooc.sh fp16
./run_matched_ooc.sh fp32
```

大型 OOC 必须串行执行。
