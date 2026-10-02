# Llama-3.1-8B-Instruct FP→定点→Hadamard 验证报告

日期：2026-09-11

## 结论

在本次 Llama-3.1-8B-Instruct WikiText2 全量口径中，硬件激活前端可以保留。

- 完整硬件前端相对归档软件 ScaleCode 基线的 PPL 变化为 `-0.01116%`，token accuracy 变化为 `+0.00458` 个百分点；这应解释为数值持平，而不是可泛化的精度提升。
- 全量推理累计检查 `51,489,275,904` 个 S24 Q8.16 前端元素，输入范围为 `[-21.5, 17.75]`，入口饱和为 `0`。
- MLP `down_proj` 的 `30,035,410,944` 个 S32 Q16.16 元素范围为 `[-560, 239]`，入口饱和同样为 `0`。
- 两路 Hadamard 输出饱和和 ScaleCode 格式错误均为 `0`。

因此，就该模型和该 workload 而言，S24 Q8.16 的 **16 个小数位精度和 ±128 动态范围都满足要求**。这比 Qwen2.5-0.5B 的结果更稳；不过它仍不是软件路径的 bit-identical 替代。

## 1. 实际推理 A/B

模型为本地 Llama-3.1-8B-Instruct BF16 checkpoint。数据为 WikiText2 test，block/stride 均为 1024，最多 65,536 输入 token，共 64 blocks、65,472 scoring tokens。三路都使用相同的 Hadamard-folded Attention W8 / MLP W4 权重、eager attention、seed `20260911`、deterministic algorithms 和关闭的 TF32。

| 路径 | PPL | 相对 software | Token accuracy | Accuracy 变化 |
|---|---:|---:|---:|---:|
| software | `8.761912525` | `0` | `53.27163%` | `0` |
| pre_q_only | `8.767853563` | `+0.06781%` | `53.21053%` | `-0.06109 pp` |
| rtl_exact | `8.760934559` | `-0.01116%` | `53.27621%` | `+0.00458 pp` |

`software` 结果与已有归档值 `8.76191252481921` 完全一致，说明本次数据切分和基线实现没有漂移。历史原始 BF16 PPL `8.252565045` 只作为背景数据，不是这次受控 A/B 的基线。

三条路径分别是：

```text
software:
  FP/BF16 -> FP Hadamard32 -> software MinMax A8/ScaleCode

pre_q_only:
  FP/BF16 -> S24 Q8.16（down: S32 Q16.16）
  -> 原 software Hadamard32/A8

rtl_exact:
  FP/BF16 -> S24 Q8.16（down: S32 Q16.16）
  -> integer butterfly -> x11585 -> round/shift -> S27/S35
  -> production integer MinMax A8/ScaleCode
```

上图中的 Down `FP/BF16 -> S32` 只描述 HuggingFace 软件适配器的注入位置；生产 RTL 中该 S32 来自 FPGA 内部 fixed SiLU×Up，不是 Host ingress，也不是 ScaleCode 恢复格式。

## 2. 全量 RTL 前端审计

| 路径 | 元素数 | Group32 数 | 输入范围 | 入口饱和 | H 输出饱和 | ScaleCode 错误 |
|---|---:|---:|---:|---:|---:|---:|
| S24 Q8.16 → S27 Q11.16 | `51,489,275,904` | `1,609,039,872` | `[-21.5, 17.75]` | `0` | `0` | `0` |
| S32 Q16.16 → S35 Q19.16 | `30,035,410,944` | `938,606,592` | `[-560, 239]` | `0` | `0` | `0` |

元素计数与 Llama 的 32 层、7 类投影和 65,472 个 scoring positions 的理论值完全一致，证明所有窗口和 224 个目标 Linear 都执行完成。软件适配器会分别统计 Q/K/V 和 Gate/Up 的逻辑调用；硬件实现可以共享相同输入的前端结果，所以这里是逻辑处理量，不等同于物理传输次数。

## 3. 真实激活误差

从原始 BF16 模型的 8 条固定 calibration prompt 捕获 32,768 个去重 Group32，其中常规 S24 路径 24,576 组，`down_proj` S32 路径 8,192 组。

| 指标 | 结果 |
|---|---:|
| 元素数 | `1,048,576` |
| 输入范围 | `[-15.0625, 9.25]` |
| 入口 / Hadamard 饱和 | `0 / 0` |
| FP→S24 Q8.16 / S32 Q16.16 RMSE | `1.30317e-6` |
| RTL Hadamard 相对 FP64 RMSE | `7.50253e-6` |
| RTL Hadamard SQNR | `91.72 dB` |
| RTL Hadamard cosine | `0.999999999874` |
| software A8 相对 FP-H RMSE | `0.00139630013` |
| hardware A8 相对 FP-H RMSE | `0.00139615248` |
| hardware A8 RMSE 相对变化 | `-0.01057%` |
| hardware/software A8 byte match | `98.73438%` |
| hardware/software A8 cosine | `0.999999856706` |
| 理论界违例 | `0 / 32,768 groups` |

Hadamard 后的定点误差约为软件 A8 量化误差的 `0.54%`，没有成为主要误差源。A8 byte 不要求完全一致：非常小的前端扰动也可能让边界值跨过整数舍入阈值；更关键的是相对共同 FP-H golden 的 RMSE 没有增加。

## 4. 判断边界

本实验能够支持：Llama-3.1-8B-Instruct 在本次 WikiText2 workload 上使用 S24 Q8.16 前端没有可测的 PPL/accuracy 退化，也没有动态范围风险。如果验收线是相对 PPL 增量不超过 `0.1%`，该模型通过。

本实验不能证明：所有 prompt、所有数据集和所有模型都永不饱和；也没有模拟 FPGA 的完整整数 MAC、RoPE、Softmax、attention accumulation 和板级数据通路。`rtl_exact` 的 bit-exact 范围是本次争议的激活前端，后续仍用 folded QDQ 权重和 PyTorch `F.linear`。

## 5. 复现

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/FPtoQ

PYTHON_BIN=/home/user/anaconda3/bin/python \
MODEL_PATH=/home/user/EDA-202/zhuowenjun/fpga_llm_project/configs/models/Llama-3.1-8B-Instruct \
MODEL_TAG=llama3.1-8b-instruct \
DEVICE=cuda:0 \
bash experiment/run_reproduction.sh ppl
```

真实激活捕获与误差分析可将最后的 `ppl` 改为 `capture`。原始结果位于本目录的 `ppl_full/`、`activation_groups.npz` 和 `analysis/`。
