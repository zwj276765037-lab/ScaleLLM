# FP→Q 后再做 Hadamard 的精度验证

## 结论

硬件路径可以保留，但结论是有条件的：

1. 对未发生入口饱和的 Group32，S24 Q8.16（MLP down 为 S32 Q16.16）的量化误差不会被归一化 Hadamard 放大。这个结论由正交性严格保证，不依赖激活分布。
2. production 系数 `11585/65536` 相对 `1/sqrt(32)` 的缩放误差只有 `2.05005e-5`；把该误差与末级 `2^-16` LSB 舍入都计入后，也有逐组可计算的严格 L2 上界。
3. Llama-3.1-8B-Instruct 的 65,472-token WikiText2 A/B 中，完整 RTL 激活前端相对归档软件算法的 PPL 变化为 `-0.0112%`，token accuracy 变化为 `+0.00458` 个百分点，即数值持平。全量 `51,489,275,904` 个 S24 前端元素无入口饱和，Hadamard 和 ScaleCode 格式错误也均为 0。
4. Llama 的 32,768 个不重复真实 Group32 样本上，完整 RTL Hadamard 相对 FP64 的 SQNR 为 `91.72 dB`；硬件 A8 相对 FP-H 的 RMSE 没有升高，理论界违例为 0。
5. Qwen2.5-0.5B-Instruct 的同口径 PPL 增量为 `+1.060%`，token accuracy 下降 `0.0916` 个百分点；全量 8,447,459,328 个 S24 前端元素中有 260 个饱和，占 `3.08e-6%`。这说明模型间差异主要应结合动态范围和端到端传播判断。
6. 该结论不能外推到高饱和率。显式 overflow probe 会严重失真；部署时仍须监控 FP→S24 saturation count。

通用论证和 Qwen 数字见 [results/REPORT.md](results/REPORT.md)；Llama 完整结果见 [results/llama3.1-8b-instruct/REPORT.md](results/llama3.1-8b-instruct/REPORT.md)。

## 比较的三条路径

```text
software:
  FP/BF16 activation -> FP Hadamard32 -> software MinMax A8/ScaleCode

pre_q_only:
  FP/BF16 activation -> S24 Q8.16（down: S32 Q16.16）
  -> 原 software Hadamard32/A8

rtl_exact:
  FP/BF16 activation -> S24 Q8.16（down: S32 Q16.16）
  -> integer butterfly -> x11585 -> round/shift -> S27/S35
  -> production integer MinMax A8/ScaleCode
```

三路使用相同的 Hadamard-folded weight、Attention W8、MLP W4、数据、token 切分和随机种子，只替换激活前端。

这里的 `down: S32 Q16.16` 是模型适配器在 `down_proj` 边界注入的生产格式模拟。真实 RTL 的 S32 由 FPGA 内部 fixed SiLU×Up 生成，不是 Host 输入；它也不是 ScaleCode 恢复基线。

## 快速复现

纯数值测试只依赖 NumPy：

```bash
cd ScaleLLM/0_Software/FPtoQ
bash experiment/run_reproduction.sh fast
```

真实激活采样需要 PyTorch、Transformers 和本地模型：

```bash
PYTHON_BIN=/home/user/anaconda3/bin/python \
  bash experiment/run_reproduction.sh capture
```

完整 65,536 输入 token PPL A/B：

```bash
PYTHON_BIN=/home/user/anaconda3/bin/python \
  bash experiment/run_reproduction.sh ppl
```

默认模型和数据均取当前工作区，可以用 `MODEL_PATH`、`MODEL_TAG`、`CALIBRATION_PATH`、`WIKITEXT_PATH`、`DEVICE` 覆盖。例如复现 Llama：

```bash
PYTHON_BIN=/home/user/anaconda3/bin/python \
MODEL_PATH=/home/user/EDA-202/zhuowenjun/fpga_llm_project/configs/models/Llama-3.1-8B-Instruct \
MODEL_TAG=llama3.1-8b-instruct \
  bash experiment/run_reproduction.sh ppl
```

## 目录

- `experiment/fptoq_core.py`：NumPy bit-exact 前端、误差界和统计。
- `experiment/test_fptoq_core.py`：与 `ScaleLLM/model/fixbit_v2.py` 的逐向量一致性测试。
- `experiment/capture_model_activations.py`：从真实 Transformer 捕获有限且去重的 Group32。
- `experiment/torch_frontend.py`：模型级 S24 Q8.16 / S32 Q16.16 与 RTL exact 前端适配器。
- `experiment/run_model_ppl.py`：受控 WikiText2 A/B。
- `results/`：已生成的原始 JSON/CSV、激活 trace 和结论报告。
