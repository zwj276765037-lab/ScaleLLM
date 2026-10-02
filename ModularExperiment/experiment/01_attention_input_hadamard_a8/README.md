# Attention input Hadamard and A8 scale generation

- Production 几何锚点：`hap_attention_frontend_8row`、`hap_hadamard32_norm_stream`；
  本实验用 `m1_minmax_a8_quantizer_dropin.sv` 替换旧 robust quantizer，
  不修改 production RTL。
- 输入/输出：8-row wave 的 S24 group32 → U8 group32 + U24 metadata。
- 对比重点：ScaleCode 生成/存储与 FP16/FP32 scale 生成/存储的资源、周期和误差。
- 输出算力按完整 row/group bundle 的握手计，不按内部 32 个 lane 重复计数。

## 正式 native-FP baseline 边界

```text
共同 8×32 S24
  -> production normalized Hadamard
  SC   -> experiment raw-Min/Max A8       -> U8 + zp/code/shift -> 2×128 cache
  FP16 -> native affine A8 quantizer      -> U8 + zp/FP16 scale -> 2×128 cache
  FP32 -> native affine A8 quantizer      -> U8 + zp/FP32 scale -> 2×128 cache
```

SC/FP quantizer 都直接从原始 group32 的 `low=min(raw_min,0)`、
`high=max(raw_max,0)` 计算 ideal-scale U8/zero-point，使用 nearest-even，且不做
量化前 clipping。native-FP 不生成或读取
ScaleCode code/shift。FP scale 的硬件输入先在 Q24 中直接求出，再通过真实
fixed-to-float IP 写入 cache；FP16 使用 `Q24→FP32→FP16` 两级转换。

## 真实 Attention 输入 workload

`data_trace/` 从 M03 已独立验证的 projection-input 补充捕获中选择 8 个真实
token row，覆盖 samples `{0,1}`、layers `{0,15,31}`，并完整展开每行 128 个
group32。三路共享相同 BF16→S24 输入以及 production normalized Hadamard；
SC/FP16/FP32 使用同一个独立 Min/Max U8 golden。

正式向量包含 128 个 `8 rows × 32 lanes` bundle，S24 输入饱和、Hadamard
饱和、zero-scale row 和量化前 clip 均为 0。相对共同 Hadamard 实值，
SC/FP16/FP32 RMSE 分别为
`1.7589088e-3/1.6618187e-3/1.6601894e-3`。完整临时重生成与逐字节比较为：

```text
M01_TRACE_VECTOR_VERIFY_PASS files=8 rows=8 groups=128 lanes=32 source_tensors=6 manifest_sha256=4713b31c9e82c8fe119ee266a26288f06eb9852585de3386197d73792c509afe
```

该 PASS 只证明输入、golden 与 provenance 完整，尚不等于 trace RTL replay
PASS。

运行：

```bash
./run_matched_xsim.sh sc 0
./run_matched_xsim.sh fp16 0
./run_matched_xsim.sh fp32 0
./run_matched_xsim.sh sc 1
./run_matched_xsim.sh sc 0 trace
./run_matched_xsim.sh fp16 0 trace
./run_matched_xsim.sh fp32 0 trace
./run_matched_ooc.sh sc
```
