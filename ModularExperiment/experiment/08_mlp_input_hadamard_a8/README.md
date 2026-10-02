# MLP input Hadamard and A8 scale generation

- Production 几何锚点：`hap_mlp_input_frontend16_compact_cache`、
  `hap_mlp_hadamard32_s24_fold4`；本实验用四个本地 raw-Min/Max A8 drop-in，
  不修改 production RTL。
- 输入/输出：`16×32 S24` → `16×32 U8 + 16×U24 metadata`。
- 输出算力按一个完整 16-row group bundle 计；保留 fold4 的时间复用事实。
- 对比 ScaleCode metadata 与 FP16/FP32 scale 的生成、缓存、读取资源和整批周期。

## 公平比较边界

三路都从同一 `16×32 S24 Q8.16` bundle 开始，经过同一个 production
fold4 normalized Hadamard，再由四个 row-time-multiplexed quantizer 生成 A8
payload，并原子写入两个 production-depth 的八行 ping-pong cache：

向量生成器直接绑定 `model/fixbit_v2.py::hadamard32_normalized`，不依赖共享
生成脚本曾经暴露的私有 `hadamard()` helper；Hadamard 与刺激生成脚本的哈希分别
写入 manifest，避免共享脚本重构后出现假通过或无法重生。

- `SC`：实验内 raw-Min/Max A8，metadata 为 `zp8/code8/shift8`；
- `FP16`：独立 affine A8 量化，scale 为 IEEE FP16；
- `FP32`：独立 affine A8 量化，scale 为 IEEE FP32。

FP 路径不先运行 SC quantizer，也不读取 ScaleCode。三路 U8/zp 都由原始
Min/Max ideal scale 和 nearest-even 生成，量化前 clip 恒为 0。正式 baseline 复用模块
01 已验证的三路、8-cycle 商单元 quantizer；四个 quantizer 的调度和 SC
production 一致。

## 真实 MLP 输入 workload

冻结 trace 原先只有 Gate/Up 输出，没有其共同 projection 输入，禁止从输出反推
输入。`data_trace_mlp_input/` 使用冻结 input IDs、同一 checkpoint 和同一
CUDA/BF16 eager 环境重新前向，直接捕获 `gate_proj` 输入，并用新算出的 Gate/Up
对冻结 tensor 做 provenance 检查。层 0/15 bit-exact；层 31 共保留
5,316,910 个 BF16 bit mismatch，最坏 normalized RMSE 为 `4.8446746e-3`，
最低 cosine 为 `0.999988273647`，通过预先固定的 `0.02/0.9998` 门禁：

```text
M08_MLP_INPUT_VERIFY_PASS files=6 samples=2 layers=3 checks=12 bit_mismatches=5316910 manifest_sha256=281da5fef1979b0f8c0199497cb0117948d3ce530e0aeeb094f4eae96c50b9e7
```

`data_trace/` 从这 6 个 tensor 选择跨样本、层和 token 的 16 个真实 row，并完整
展开 128 个 group32。S24 输入、Hadamard 饱和、zero-scale row 和量化前 clip
均为 0。SC/FP16/FP32 相对共同 Hadamard
实值的 RMSE 分别为
`1.5539701e-3/1.4622940e-3/1.4613934e-3`。完整重生成结果为：

```text
M08_TRACE_VECTOR_VERIFY_PASS files=8 rows=16 groups=128 lanes=32 source_tensors=6 manifest_sha256=e04b0a936474d28aef119ac027c5d99d41efe4b0b4e3acf16b49d8db54cfcd94
```

上述 PASS 是输入/golden 证据，三路 trace RTL replay 尚未执行。

## 复现命令

```bash
./run_matched_xsim.sh sc 0
./run_matched_xsim.sh fp16 0
./run_matched_xsim.sh fp32 0
./run_matched_xsim.sh sc 1
./run_matched_xsim.sh fp16 1
./run_matched_xsim.sh fp32 1
./run_matched_xsim.sh sc 0 trace
./run_matched_xsim.sh fp16 0 trace
./run_matched_xsim.sh fp32 0 trace
./run_matched_ooc.sh sc
./run_matched_ooc.sh fp16
./run_matched_ooc.sh fp32
```

大型 OOC 必须串行执行。正式结果写入
`../../result/08_mlp_input_hadamard_a8/raw/<variant>/`。
