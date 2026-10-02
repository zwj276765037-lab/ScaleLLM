# Attention A8W8 projection

- Production 锚点：`hap_projection_core16x16_w8_reuse`、`hap_a8w8_array_16x16_s42_col3`。
- 覆盖 phase：Q、K、V 和复用同一 array 的 Wo。
- 几何：physical 8 rows × 16 columns、group32、lane II=2、两个 wave/16-row cohort。
- 输出合同：128 group32 累加后产生 S24 projection tile；FP baseline 输出等价 FP tile，并在共同观察点比较实值。
- FP 版本必须复制/流水到不低于 SC 的 tile 输出率后才能比较资源。

## FP16 非有限值语义探针

真实 projection 输入范围分析已经发现 Q/K/V correlation 可超过 IEEE FP16
最大有限值。`run_fp16_nonfinite_probe.sh` 使用与正式 matched baseline 相同的
production group32 MAC 和 AMD Floating-Point IP 链，定向覆盖 FP16 溢出阈值、
真实 Q/K/V 极值以及 `Infinity x 0`，并逐项记录
`S21 -> FP32 -> FP16 -> mul -> mul -> FP32 -> S42` 的实际 bit pattern。
run 结束后，独立 verifier 还会检查 22 条记录的 case 顺序、精确 MAC
correlation、S21-to-FP32 bits、浮点分类标志、S42 payload 和汇总计数，并把
通过验证的映射冻结为 run 目录中的 `semantic_map.json`。

该探针只定义 Xilinx IP 的硬件语义，不把溢出美化为正确输出。必须等当前大型
OOC 结束后串行运行，取得 PASS、输入/IP/目录哈希后，才能据此生成 M02 正式
真实 trace golden：

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
./experiment/02_attention_a8w8_projection/run_fp16_nonfinite_probe.sh
```

## 真实 Q/K/V projection trace

`model/generate_trace_vectors.py` 已实现正式 trace 生成链，但具有硬门禁：只有找到
`STATUS=PASS`、exit status=0、且目录 `SHA256SUMS` 覆盖的
`semantic_map.json` 才会继续；当前探针尚未运行，因此执行生成器会明确以状态 1
退出，并且不会创建 `data_trace/` 文件。

门禁打开后，生成器会从经过 provenance 验证的 attention-input capture 和同一
checkpoint 权重构造 18 个真实 `8x16x128` tile：

- 2 samples × layers `{0,15,31}` × `{Q,K,V}`；
- 每 tile 128 个 group32，共 2,304 transactions 和 2,304 个 S24 输出；
- Q/K 强制包含 M03 已验证的真实 token/RoPE-pair weight rows，不允许过滤掉
  FP16 overflow；
- V 在八个分散真实 token 上，从全部 1,024 个输出行选择 max-abs correlation
  最大的 16 行，作为明确披露的真实范围压力测试；
- SC/FP16/FP32 共享同一 U8 activation、S8 weight、zero point 和最终 S24
  观察点，仅 scale metadata/application 路径不同。

`model/verify_trace_vectors.py` 检查全部文件宽度、记录数、源 trace/capture/
checkpoint/semantic-map 哈希、tile 坐标、S21/shift 范围和非有限值覆盖；默认还会
临时完整重生成并逐字节比较，`--integrity-only` 用于 runner 的启动门禁。

真实 trace TB 在每个 tile 后保留八个 drain cycles，使 accumulator 的流水化
overflow diagnostic 有时间变成 sticky error，再允许 clear。若 FP16 非有限值
转换导致 S42 accumulation overflow，该 run 必须保留为 `FAIL` 范围证据，不能
通过提前 clear 掩盖。

待语义探针 PASS 后，严格串行运行：

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
python3 experiment/02_attention_a8w8_projection/model/generate_trace_vectors.py
python3 experiment/02_attention_a8w8_projection/model/verify_trace_vectors.py
./experiment/02_attention_a8w8_projection/run_matched_xsim.sh sc 0 trace
./experiment/02_attention_a8w8_projection/run_matched_xsim.sh fp16 0 trace
./experiment/02_attention_a8w8_projection/run_matched_xsim.sh fp32 0 trace
```
