# 模块实验目录

所有模块使用 [`../goal/README.md`](../goal/README.md) 中定义的 `SC`、`FP16`、`FP32`、operator-only、boundary-inclusive 和同吞吐规则。

| 顺序 | 目录 | 功能域 |
|---:|---|---|
| 00 | `00_scale_apply_microkernel` | ScaleCode 恢复与 FP 反量化的最小算术边界 |
| 01 | `01_attention_input_hadamard_a8` | Attention 输入 Hadamard + A8/scale 生成 |
| 02 | `02_attention_a8w8_projection` | Q/K/V/Wo A8W8 projection |
| 03 | `03_attention_rope` | Q/K RoPE |
| 04 | `04_attention_kv12_quantizer` | K/V KV12 量化与 scale metadata |
| 05 | `05_attention_qk_score` | QK score 与 scale 对齐 |
| 06 | `06_attention_softmax` | 稳定 Softmax |
| 07 | `07_attention_pv` | probability × V context |
| 08 | `08_mlp_input_hadamard_a8` | MLP 输入 Hadamard + A8/scale 生成 |
| 09 | `09_mlp_gate_up_a8w4` | Gate/Up A8W4 projection |
| 10 | `10_mlp_silu_multiply` | SiLU(Gate) × Up |
| 11 | `11_mlp_product_hadamard_a8` | SwiGLU product Hadamard + Down A8/scale 生成 |
| 12 | `12_mlp_down_a8w4` | Down A8W4 projection |

每个模块 README 冻结 production 锚点和逻辑输出合同；新增 RTL 前先保持三种 variant 的 wrapper 端口、work-unit 和 testbench 一致。

## Attention baseline seed 的来源

`00`–`07` 下的 `legacy_seed/` 是从
`fpga_llm_project/0_fix_bit_Hadamard/module_experiment/experiment/M1..M9`
机械复制的 FP baseline、testbench、生成器与 Tcl 种子。每个目录同时保存：

- `SOURCE_SHA256SUMS`：原始绝对路径与复制时 SHA256；
- `COPIED_SHA256SUMS`：本实验副本的 SHA256。

这些文件只作为移植起点。旧设计绑定旧 `HAP_new`、150 MHz 约束和旧
workload，未经当前 ScaleLLM RTL 绑定、100 MHz 重跑、同吞吐校准及
post-route 门禁前，不能作为本实验正式结果引用。
