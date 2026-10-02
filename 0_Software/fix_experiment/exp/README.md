# ScaleLLM 论文口径 ACC/PPL 实验

该目录提供两套明确隔离的协议：

- `literature_2048`：完整 official split；ACC 使用 `lm_eval==0.4.11` 的
  0-shot request/metric；PPL 使用完整 WikiText-2 test、2048-token
  非重叠 block 和 tail-drop。该协议运行 BF16 与纯算法 `reference_qdq`；
  不能运行 V5 硬件孪生，因为 V5 Attention/RoPE 的生产合同只支持 0..127。
- `hardware_128`：仍使用完整 ACC split，但 lm-eval 最大长度和 PPL block
  均为 128。超过 128 token 的 PIQA choice 用滚动窗口评分全部 choice
  token，不丢样本。仅允许与同协议 BF16 基线比较，不能与论文 2048 PPL
  或 ACC 绝对值横比。

默认解释器是：

```text
/home/user/anaconda3/envs/zhouwenjun/bin/python
```

准备/校验数据：

```bash
cd /home/user/EDA-202/zhuowenjun
/home/user/anaconda3/envs/zhouwenjun/bin/python \
  ScaleLLM/0_Software/fix_experiment/exp/prepare_standard_data.py
```

运行完整论文计划（先 BF16/Reference-QDQ-2048，再 matched
BF16-128/V5-128；每个阶段都同时占用 GPU0 和 GPU1）：

```bash
ScaleLLM/0_Software/fix_experiment/exp/run_dual_gpu_eval.sh \
  --plan paper \
  --output ScaleLLM/0_Software/fix_experiment/results/paper_full
```

只运行可与文献对齐的 BF16 口径：

```bash
ScaleLLM/0_Software/fix_experiment/exp/run_dual_gpu_eval.sh \
  --plan literature \
  --output ScaleLLM/0_Software/fix_experiment/results/bf16_literature
```

运行纯算法 matched pair（BF16-2048 后运行 Reference-QDQ-2048）：

```bash
ScaleLLM/0_Software/fix_experiment/exp/run_dual_gpu_eval.sh \
  --plan algorithm \
  --output ScaleLLM/0_Software/fix_experiment/results/algorithm_reference
```

已有 BF16-2048 基线时，只运行纯算法。两张 RTX A6000 已验证 ACC
`batch_size=32`、PPL `batch_size=1` 可以稳定运行：

```bash
ScaleLLM/0_Software/fix_experiment/exp/run_dual_gpu_eval.sh \
  --plan algorithm-only \
  --batch-size 32 \
  --ppl-batch-size 1 \
  --output ScaleLLM/0_Software/fix_experiment/results/algorithm_reference_full
```

`reference_qdq` 保留算法定义中的 Hadamard32、Group32 activation A8、
Attention W8、MLP W4 与 8-bit ScaleCode；Attention、RoPE、KV cache 和
残差路径使用模型原生软件实现，不引入 S24、KV12 或 128-token 硬件限制。

只运行硬件 matched pair：

```bash
ScaleLLM/0_Software/fix_experiment/exp/run_dual_gpu_eval.sh \
  --plan hardware \
  --output ScaleLLM/0_Software/fix_experiment/results/v5_matched
```

当前 V5 软件孪生已与 MLP format-v3 对齐：合法 total shift 为 `[20,44]`，
Group32 guard 为 S37，Gate/Up 与 Down accumulator 分别为 S44/S46，完整
format ID 为 `0x48384603`。`--allow-format-errors` 仅保留给超出当前格式合同的
RTL zero-guard 诊断；这种输出仍会标成 `complete_invalid_format_error`。

隔离验证定点 Attention（Q/K/V、RoPE、KV12、QK、Softmax、PV、Wo），同时
保持 RMSNorm、residual、MLP 和 LM head 为原生 BF16，可直接运行：

```bash
CUDA_VISIBLE_DEVICES=0 /home/user/anaconda3/envs/zhouwenjun/bin/python \
  ScaleLLM/0_Software/fix_experiment/exp/run_eval_worker.py \
  --case v5_attention --protocol hardware_128 \
  --tasks piqa,wikitext2 \
  --model fpga_llm_project/configs/models/Llama-3.1-8B-Instruct \
  --output ScaleLLM/0_Software/fix_experiment/results/v5_attention_smoke
```

`v5_attention` 的 Wo S24 Q8.16 输出会在消融边界转回 BF16，目的是单独测量
Attention 定点误差；完整 Host-FP32 residual/RMSNorm + Attention/MLP 硬件链路
仍由 `v5` 表示。

快速检查使用 `--limit 1`。任何非零 limit 都会在 manifest 中强制记录
`full_split=false` 和 `literature_comparable=false`。

主要输出：

```text
<output>/
  data_manifest.json
  bf16_literature_2048/
    gpu0.log
    gpu1.log
    shard_gpu0/manifest.json
    shard_gpu1/manifest.json
    merged/manifest.json
    merged/summary.csv
  reference_qdq_literature_2048/...
  bf16_hardware_128/...
  v5_hardware_128/...
  paper_manifest.json
  paper_summary.csv
```

`paper_summary.csv` 只会计算同名协议、相同上下文下 BF16 与
Reference-QDQ/V5 的差值，拒绝把 `hardware_128` PPL 与
`literature_2048` PPL 相减。

如果 BF16 基线位于另一结果目录，可在算法完成后显式引用；汇总器仍要求
两边都是 full split：

```bash
/home/user/anaconda3/envs/zhouwenjun/bin/python \
  ScaleLLM/0_Software/fix_experiment/exp/summarize_plan.py \
  --root ScaleLLM/0_Software/fix_experiment/results/algorithm_reference_full \
  --baseline-manifest \
  ScaleLLM/0_Software/fix_experiment/results/paper_full_strict/bf16_literature_2048/merged/manifest.json
```
