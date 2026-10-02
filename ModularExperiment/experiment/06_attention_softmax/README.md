# Attention Softmax

- Production 锚点：`hap_softmax_row_128` 及 exp/reciprocal/probability leaves。
- SC：S20 Q6.14 score → U16 probability；stable max-subtraction，257-entry exp LUT。
- FP16/FP32：同一有效 key/mask 的稳定浮点 Softmax。
- 必须分别报告 row 总 latency、probability 输出 phase II、probability/s、概率和误差、KL 与 top-1 match。

## 当前与主口径

- 当前完成的是 N=128 `operator-only`：FP16/FP32 直接接收浮点 score，不包含
  QK 输出边界；FP 复制核、row buffer、分发、顺序退休、仲裁和 backpressure
  已计入。
- 孤立 boundary-inclusive 对照必须从共同 S20 score/mask 开始并计入
  fixed-to-float、格式缓存和相同 sideband 边界。
- 完整 Attention 链中 FP score 直接来自 FP QK 并保持 FP，只在真实 Q/K
  dequant 边界计费一次；因此最终主结论需要 QK→Softmax 链顶层重新综合，
  不能把孤立转换器与上游重复相加。
- 正式软件 workload 已覆盖 12 seeds × `N={128,112,64,32,16,1}`，并生成
  KL divergence、probability-sum error 和 top-1 reference；在新 boundary RTL、
  三路 XSIM 和 OOC 完成前，当前 N=128 硬件数据仍只作为有效子实验。

## 已冻结的 boundary workload

`model/generate_boundary_vectors.py` 从共同 S20 Q6.14 score/mask 边界生成 72
个 row、4,236 个有效 score。8 个 `.mem` 文件包含 row length、共同 S20、
FP16/FP32 显式转换值以及三路 U16 probability reference；独立 verifier 会检查
文件宽度/数量/哈希，并用 production `fixbit_v2.softmax_row_u16` 重算全部 SC
golden。覆盖包括 17 个 single-visible row、15 个 tied-maximum row、914 个
masked score，以及正负 `16.0` 端点。manifest SHA256 为
`373f0e918dd55d660c8f130950b6bd29c98b3dd2a4562843633bdd367ac1ce17`。

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
python3 experiment/06_attention_softmax/model/generate_boundary_vectors.py
python3 experiment/06_attention_softmax/model/verify_boundary_vectors.py
```

当前 verifier 输出 `M06_BOUNDARY_VECTOR_VERIFY_PASS files=8 rows=72
scores=4236`，且二次生成的目录聚合哈希完全一致。这只冻结软件 workload；
FP16 reference 仍需用 Xilinx IP XSIM 测量实际偏差，不能据此宣称硬件 bit-exact。

## Boundary RTL/TB 状态

共同 S20 Q6.14 score/mask 边界的三路 RTL、TB、FP IP Tcl、XSIM/OOC 脚本已
落盘并通过静态预检。SC 直接复用 production `hap_softmax_row_128`；
FP16/FP32 分别计入 S20→FP32 与可选 FP32→FP16 转换、保序 sideband/score
FIFO，然后进入已验证的 x22/x26 同吞吐 farm。reservation counter 同时覆盖
转换中和 FIFO 中的 score，避免非阻塞转换器在下游背压时溢出。

TB 使用全部 72 rows/4,236 scores，检查 variable-N first/last、mask、输出顺序、
continuous/periodic backpressure 下的数据稳定性，以及
input/conversion/core/output/row counters。SC 与 FP32 预注册为 exact U16；
FP16 容差预注册为 128 U16 LSB（此前 N=128 硬件 workload 的 max 为 96），
首次 boundary XSIM 后只能依据保留的诊断证据收紧或解释，不能为通过而放宽。

`create_boundary_all_fp_ip.tcl` 为自包含 IP 配置，公共 OOC runner 保存的
driver 哈希覆盖 operator 与边界转换 IP。当前仅完成静态预检，Xilinx IP 实际
端口/latency、功能、周期、资源和时序仍待 Vivado elaboration、XSIM 与 OOC，
不得记作硬件 PASS。

09 与 12 的当前串行队列完成后，按以下顺序执行：

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
./experiment/06_attention_softmax/run_boundary_xsim.sh sc 0
./experiment/06_attention_softmax/run_boundary_xsim.sh sc 1
./experiment/06_attention_softmax/run_boundary_xsim.sh fp16 0
./experiment/06_attention_softmax/run_boundary_xsim.sh fp16 1
./experiment/06_attention_softmax/run_boundary_xsim.sh fp32 0
./experiment/06_attention_softmax/run_boundary_xsim.sh fp32 1
./experiment/06_attention_softmax/run_boundary_ooc.sh sc
./experiment/06_attention_softmax/run_boundary_ooc.sh fp16
./experiment/06_attention_softmax/run_boundary_ooc.sh fp32
```

所有命令必须严格串行；首次失败目录原样保留，禁止通过放宽容差、降频或减少
x22/x26 farm 核数升级为正式结论。
