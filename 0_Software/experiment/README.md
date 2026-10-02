# 最终 ScaleCode 实验程序归档

本目录归档最终采用的 `mlp_w4_scalecode` 数值参考实现及 ACC/PPL/GSM8K 推理入口。归档日期为 2026-09-10；原程序仍保留在 `fpga_llm_project/scripts`，未移动、未覆盖。

## 最终方法

- Hadamard block：32。
- 量化 group size：32，沿线性层输入维分组。
- 激活：A8，无符号非对称 MinMax，不做分位数/MSE/alpha clipping。
- Attention `q_proj/k_proj/v_proj/o_proj`：W8，有符号对称量化。
- MLP `gate_proj/up_proj/down_proj`：W4，有符号对称量化。
- GLM 的 `gate_up_proj` 按 MLP 处理。
- `lm_head` 不量化。
- scale：8-bit `code` 加 8-bit `shift`，解码值为 `code * 2^(-shift)`。

精确公式见 `../introduction/01_final_scalecode_algorithm.md`。

## 程序布局

- `scripts/scale_code_linear/scalepath4_method_inference.py`：Hadamard、A8/W8 和 ScaleCode 基础实现。
- `scripts/accuracy_MLP_4bit/mlp4_method_inference.py`：在基础实现上把 MLP 权重改为 W4，是最终主方法。
- `scripts/accuracy_MLP_4bit/scala_code_accuracy/run_gyrot_aligned_quality_accuracy.py`：完整验证集选择题 ACC。
- `scripts/accuracy_MLP_4bit/run_mlp4_quality_accuracy.py`：WikiText2 PPL 及旧版 quality/accuracy 入口。
- `scripts/accuracy_MLP_4bit/run_mlp4_gsm8k_accuracy.py`：GSM8K first-300。
- `scripts/scale_code_linear/run_s11_cross_model_*.py`：上述脚本依赖的公共评测函数及 A8W8 参考入口。
- `run_final_scalecode.sh`：按最终参数启动单模型 ACC、PPL 或 GSM8K。
- `SOURCE_MANIFEST.csv`：原文件与归档文件的 SHA256。

## 归档副本的两项路径调整

量化和评测逻辑没有改动，仅对归档副本做了两项可移植性调整：

1. 模型/数据根目录由环境变量 `FPGA_LLM_PROJECT_ROOT` 指定；未设置时自动回退到同一工作区的 `fpga_llm_project`。
2. 新运行的默认输出写入 `0_Software/results/_rerun`，不会覆盖历史结果。

## 快速运行

在 `ScaleLLM/0_Software` 下执行：

```bash
bash experiment/run_final_scalecode.sh acc ../../fpga_llm_project/configs/models/Qwen3-8B
bash experiment/run_final_scalecode.sh ppl ../../fpga_llm_project/configs/models/Qwen3-8B
bash experiment/run_final_scalecode.sh gsm8k ../../fpga_llm_project/configs/models/Qwen3-8B Qwen3-8B fair eager
```

ACC 和 PPL 命令已显式锁定最终量化参数、数据规模和随机性参数。GSM8K 的历史最终表由多轮修复结果并表，不同模型使用过不同 prompt/attention 实现；精确说明见复现文档，不能假定一条统一 GSM8K 命令会逐位重现全部历史数值。
