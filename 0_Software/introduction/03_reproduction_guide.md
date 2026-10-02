# 最终 ScaleCode 复现指南

## 1. 目录与依赖

推荐从 `ScaleLLM/0_Software` 执行。程序需要 Python、PyTorch、Transformers 和 Datasets；依赖名称记录在 `experiment/requirements.txt`。历史结果没有留下可确认的完整环境锁文件，因此该 requirements 文件不虚构版本号。

模型默认位于：

```text
../../fpga_llm_project/configs/models/<model-name>
```

数据默认位于：

```text
../../fpga_llm_project/data/
```

如工程不在这个相对位置，先设置：

```bash
export FPGA_LLM_PROJECT_ROOT=/absolute/path/to/fpga_llm_project
```

## 2. 支持的 12 个最终模型

```text
DeepSeek-R1-Distill-Llama-8B
GLM-4-9B-0414
Llama-3.1-8B
Llama-3.1-8B-Instruct
Llama-3.2-1B-Instruct
Llama-3.2-3B-Instruct
Mistral-7B-Instruct
Qwen2.5-0.5B-Instruct
Qwen2.5-1.5B-Instruct
Qwen2.5-3B-Instruct
Qwen2.5-7B-Instruct
Qwen3-8B
```

## 3. 单模型运行

### 完整验证集 ACC

```bash
bash experiment/run_final_scalecode.sh acc \
  ../../fpga_llm_project/configs/models/Qwen3-8B
```

入口会显式使用：

```text
tasks = piqa,arc_challenge,openbookqa,hellaswag,winogrande
full split; rank_metric=auto; max_length=1024
seed=20260626; deterministic=True; allow_tf32=False
```

### WikiText2 PPL

```bash
bash experiment/run_final_scalecode.sh ppl \
  ../../fpga_llm_project/configs/models/Qwen3-8B
```

入口会显式使用 block size 1024、stride 1024、最大 65,536 输入 token 和 seed 20260618。历史汇总最终得到 64 blocks、65,472 个计分 token。

### GSM8K first-300

```bash
bash experiment/run_final_scalecode.sh gsm8k \
  ../../fpga_llm_project/configs/models/Qwen3-8B \
  Qwen3-8B fair eager
```

第 4、5 个参数分别为 `prompt_style` 和 `attn_implementation`。GSM8K 对 prompt 模板、chat template、thinking 开关、SDPA/eager 和生成长度非常敏感。历史最终表存在按模型修复与替换：例如 Qwen2.5-7B 的最终值来自 `chat_fewshot_cot + sdpa` 重跑。因此此入口提供可复现实验流程，但若要逐值对齐历史 GSM8K，必须同时按 `_summary` 下两个 audit 文件恢复对应模型的旧参数和来源，不能统一使用默认 `fair + eager`。

## 4. 输出位置

归档副本的新结果默认写入：

```text
results/_rerun/final_scalecode_gyrot_aligned_accuracy/
results/_rerun/final_scalecode_quality_accuracy/
results/_rerun/final_scalecode_gsm8k_first300/
```

这与只读历史归档目录分开，可避免覆盖本次整理的结果。

## 5. 结果核对顺序

1. 检查 attach summary：Hadamard=32、group=32、act=8、Attention weight=8、MLP weight=4、scale code=8。
2. 检查模块计数，确认 Q/K/V/O 与 Gate/Up/Down 均被替换，`lm_head` 未替换。
3. ACC 检查每个任务的 `records_complete=True`、`finite=True`、`status=pass`。
4. PPL 检查 64 blocks、65,472 tokens，并与 `results/_summary/final_scalecode_ppl_wikitext2.csv` 比较。
5. 比较 ACC 时使用 `final_accuracy_comparison.csv` 或 `final_scalecode_accuracy_raw_observed.csv`，不要使用带 display cap 的报告表。

## 6. 可复现边界

- 本归档没有重新下载数据、重新运行模型或修改历史结果。
- MCQA 逐任务 CSV 的字段与数据行复制自 repaired 目录，仅将 CRLF 换行统一为 LF；GSM8K 是最终汇总表中的并表值。
- 原始记录里保存了 seed、deterministic、TF32、任务协议和方法摘要；绝对路径仍指向生成结果时的工程位置，这是有意保留的 provenance。
- GPU、CUDA、PyTorch/Transformers 版本没有完整锁定，数值级复现仍应记录实际运行环境。
