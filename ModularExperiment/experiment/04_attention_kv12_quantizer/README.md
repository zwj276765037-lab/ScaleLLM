# Attention KV12 quantizer

- Production 锚点：`hap_kv12_quantizer4` 与 4 个 `hap_kv12_quantizer` worker。
- 输入/输出：每批 4 rows 的 `32×S24` → 每 row 一份 `32×S12 + meta16`。
- SC 结果不得产生保留码 -2048；记录 scale code/shift 合法性与量化误差。
- 无 ScaleCode baseline 将 K/V 保持为 FP16/FP32；模块级与 cache-inclusive 资源必须分开报告。

## 真实 Llama K/V trace workload

`model/generate_trace_vectors.py` 从冻结的 Llama-3.1-8B-Instruct trace 中读取
post-RoPE K 和 V BF16 tensor。固定选择 8 个
`(sample, layer, token, kv_head)` 坐标，覆盖 samples `{0,1}`、layers
`{0,15,31}` 和 12 个源 tensor；每个坐标按 K、V 交替生成两个 batch，每个
batch 含完整 head-dim 的四个连续 group32。因此 workload 总计 16 batches、
64 records、2,048 lanes，K/V 各 32 records。

共同边界是 BF16 先按 nearest-even 转成 S24 Q8.16。SC 路径逐 group32 调用
production `kv12_quantize_s24`，输出 S12 与 ScaleCode meta16；FP16/FP32 从同一
S24 值直接转换并写入 native-FP cache。三路没有共享 SC 量化后的 lane 值。
当前真实样本中 S24 saturation、KV12 clip、保留 `-2048` 和 zero-scale record
均为 0。

正式数据位于 `data_trace/`。独立 verifier 会在临时目录重做源 trace hash、
BF16 解码、S24 转换、production KV12 量化、FP golden 和全部文件生成，然后
逐字节比较：

```text
M04_TRACE_VECTOR_VERIFY_PASS files=7 batches=16 records=64 lanes=32 source_tensors=12 manifest_sha256=ac31392da0a79bfbc512be83ebcb4b0476ef2d16eb958ef7f33699ab6bcc0065
```

相对共同 S24 输入，SC KV12/FP16/FP32 的 RMSE 分别为
`8.9869041e-4`、`6.7434958e-7`、`0`；相对原始 BF16 则为
`8.9869062e-4`、`1.1960909e-6`、`1.0301219e-6`。这只是软件精度与输入完整性
证据，不能作为真实 trace RTL PASS 或新的资源/周期结论。

复现数据与校验：

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
python3 experiment/04_attention_kv12_quantizer/model/generate_trace_vectors.py
python3 experiment/04_attention_kv12_quantizer/model/verify_trace_vectors.py
```

`run_boundary_xsim.sh` 的第三个参数选择 `synthetic|trace`，并把实际数据目录
显式传给 Vivado/TB。例如：

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
./experiment/04_attention_kv12_quantizer/run_boundary_xsim.sh sc 0 trace
./experiment/04_attention_kv12_quantizer/run_boundary_xsim.sh fp16 0 trace
./experiment/04_attention_kv12_quantizer/run_boundary_xsim.sh fp32 0 trace
```

这些 XSIM 命令尚未执行；必须等待当前 M09 FP32 OOC 结束，并继续遵守大型
Vivado/XSIM 严格串行。运行时 `INPUT_SHA256SUMS` 会覆盖 generator、verifier、
production model、冻结 trace manifest、数据文件、RTL/TB/source list 和 FP IP
配置；FP run 还保存实际生成 XCI 的哈希。
