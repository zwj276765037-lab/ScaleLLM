# Attention PV

- Production 锚点：`hap_pv_tile16_s43`。
- 输入/输出：N 个 U16 probability 与 `16×S12 + meta16` V，输出 16 个 S24 context。
- 物理合同：一个 16-column leaf；每 head 时间复用 8 个 tile，不允许按 8 套并行核计算资源。
- 当前完成的 FP16/FP32 baseline 使用免费给定的浮点 probability 与已反量化
  V，只属于 N=128 `operator-only`；匹配 context tile/s 和完整 head latency。

## Boundary-inclusive 主口径（RTL/TB 已落盘，待 Vivado 验证）

- 孤立模块从共同 U16 probability、`16×S12 + scale metadata` V 和相同 mask/
  key/tile sideband 开始；FP 计入 probability conversion、V dequant、FP row
  cache 与缓冲，SC 计入 production integer multiply/ScaleCode shift alignment。
- 完整 Attention 链中 probability 直接保持 Softmax 的 FP 输出，V 直接读取
  native-FP KV cache；上游已经计入的转换不得在 PV 重复计费。
- 最终按真实 8-tile/head 时间复用实现综合 QK→Softmax→PV 非重叠链顶层；
  当前 FP16×19/FP32×21 复制结果只是有效的 operator-only 下界。

## 已冻结的 boundary workload

`model/generate_boundary_vectors.py` 已生成 12 seeds ×
`N={128,112,64,32,16,1}` 的正式软件数据，共 72 rows、4,236 key
transactions。共同输入为 production Softmax 产生的 U16 probability、
`16×S12` V 和 native scale metadata；13 个 `.mem` 同时保存 FP16/FP32
显式 probability conversion、V scale conversion/cache 和三路 S24 context
reference。独立 verifier 用 production `pv_row_tile16_s24` 重算全部 SC 输出并
检查文件/生成器/model 哈希。manifest SHA256 为
`8088bb9f1f0fe50150f30c75bf45084721d04ed0a27aea341b79a51a9d89a4b0`。

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
python3 experiment/07_attention_pv/model/generate_boundary_vectors.py
python3 experiment/07_attention_pv/model/verify_boundary_vectors.py
```

当前 verifier 输出 `M07_BOUNDARY_VECTOR_VERIFY_PASS files=13 rows=72
keys=4236 lanes=16`，二次生成目录聚合哈希完全一致。软件覆盖 145 个 FP16
probability FTZ、1,060 个 FP16 subnormal native scale、16,957 个非零 V lane
反量化后变零，以及三路各 16 个 S24 饱和输出。这些数据尚未经过新 boundary
RTL/XSIM，不能作为新增硬件结果。

## 真实 Llama trace workload

`model/generate_trace_vectors.py` 从正式 PASS 的 Llama-3.1-8B trace 派生与
上述 TB 完全相同的 72-row/4,236-key 几何：2 samples × layers
`{0,15,31}` × `N={128,112,64,32,16,1}` × q-heads `{0,17}`。GQA 映射固定为
q-head 0/17 → KV-head 0/4；每个 key 先把 V 的 head-dim 0–31 作为完整 group32
以 nearest-even 转为 S24 Q8.16，再调用 production `kv12_quantize_s24`，PV
明确读取该 group 的 head-dim 0–15 tile。概率由捕获的 FP32 probability
nearest-even 转为 U16 Q0.16。SC、FP16、FP32 因而从同一 U16+KV12/native-meta
边界开始。

独立 verifier 会在临时目录重新读取 12 个源 tensor、重做全部量化和三路
golden；13 个 `.mem` 和 coordinate CSV 逐字节比较，manifest 结构与非浮点字段
严格相等，浮点归约指标允许 `1e-13` 相对容差：

```text
M07_TRACE_VECTOR_VERIFY_PASS files=15 rows=72 keys=4236 lanes=16 source_tensors=12 manifest_numeric_rel_tol=1e-13 manifest_sha256=ce9eac6783699b0c84ea55314541aa4a784c824ab817056f0acaf232e52f465b
```

相对捕获 probability/BF16 V 的 FP64 PV，SC/FP16/FP32 RMSE 分别为
`7.0642112e-5`、`6.5395644e-3`、`7.0731914e-5`；相对共同 U16+KV12
输入的 FP64 PV，三者 RMSE 分别为 `4.6099882e-6`、`6.5371985e-3`、
`4.1184005e-6`。三路 S24 saturation 均为 0。输入量化单独报告：probability
RMSE `4.4738652e-6`（N=1 的 12 个精确 1.0 被 U16 上限饱和），KV12 V 相对
BF16 trace 的 RMSE `1.8590829e-4`，BF16→S24 无饱和、KV12 无 clip。

该真实 workload 已接入 `run_boundary_xsim.sh ... trace`，但只在共享机器空闲时
串行启动；所以这里只是可重建的软件 workload/精度证据，
不是 RTL trace replay PASS。

## Boundary RTL/TB 状态

三路 boundary RTL、TB、自包含 FP IP Tcl 和 XSIM/OOC 脚本已经落盘并通过
静态预检。SC 直接复用 production `hap_pv_tile16_s43`。FP 从共同 U16
probability、16×S12 V 和 meta16 开始：

- U16 Q0.16 probability 与 16 路 S12 V 转为 FP32，FP16 路再 narrow；
- 组合逻辑把合法 meta16 精确编码为 `code/2^shift` 的 FP32 scale，FP16
  路通过同一 narrow IP 得到 native Half；
- 16 路 FP multiply 完成 V dequant，transaction-order FIFO 对齐
  first/last、probability 与 V，之后进入已验证的 x19/x21 同吞吐 farm；
- reservation counter 覆盖转换流水和最终 FIFO，非阻塞 IP 下游受阻时会在
  共同边界反压，不会静默丢 transaction。

独立静态检查已对全部 4,236 个 meta16 重算 FP32/FP16 scale bit pattern，与
冻结的 `value_scale_fp32/fp16.mem` 完全一致。TB 使用 72 个 variable-N row，
覆盖 continuous/periodic backpressure、输出稳定、三组输入/转换/core 计数、
row/saturation 计数，并预注册三路 S24×16 exact 比较。

这些检查不等价于 elaboration。尤其 17 路 fixed-to-float、18 路 FP16 narrow
的实际 latency/FTZ 语义和并行 valid 对齐必须由首次 XSIM 验证；当前不得将
新 RTL/TB 记作硬件 PASS。

09 与 12 的当前串行队列完成后，按以下顺序执行：

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
./experiment/07_attention_pv/run_boundary_xsim.sh sc 0
./experiment/07_attention_pv/run_boundary_xsim.sh sc 1
./experiment/07_attention_pv/run_boundary_xsim.sh fp16 0
./experiment/07_attention_pv/run_boundary_xsim.sh fp16 1
./experiment/07_attention_pv/run_boundary_xsim.sh fp32 0
./experiment/07_attention_pv/run_boundary_xsim.sh fp32 1
./experiment/07_attention_pv/run_boundary_xsim.sh sc 0 trace
./experiment/07_attention_pv/run_boundary_xsim.sh fp16 0 trace
./experiment/07_attention_pv/run_boundary_xsim.sh fp32 0 trace
./experiment/07_attention_pv/run_boundary_ooc.sh sc
./experiment/07_attention_pv/run_boundary_ooc.sh fp16
./experiment/07_attention_pv/run_boundary_ooc.sh fp32
```

所有命令必须严格串行；失败证据原样保留，禁止降频或把 x18/x20 的低吞吐
baseline 替代正式 x19/x21 farm。
