# Llama-3.1-8B-Instruct format-v3 整数孪生验证报告

Matched BF16 baseline：`/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/fix_experiment/results/algorithm_precision_full/bf16_hardware_128/merged/manifest.json`

Checkpoint fingerprint：`f32c0adabc4443d374a0ebac6dcb0c5425b2e88aa84c54420ae040117794efe6`（`/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/fix_experiment/results/six_model_algorithm_literature_2048/model_identities/Llama-3.1-8B-Instruct.json`）

正式 worker 的历史 manifest 未内嵌 `model_identity`；本报告使用同一本地 checkpoint 路径已有的逐文件 SHA-256 身份文件补充 provenance，强制验证器会重新计算全部14个文件的 SHA-256；本流程不回写或伪造 worker manifest 字段。

本报告只把指定的完整 ACC/PPL manifest 纳入主结果；smoke、8-block Down-S32 和 RTL-zero-guard 均明确标注，不得冒充当前硬件通过结果。

## 执行状态

本轮 MLP-only/Full V5 ACC 已按用户指令停止，状态为 `paused_incomplete`；现有完整 PPL、Attention ACC 与节点 trace 保留有效，但缺失的 MLP/Full ACC 不得由部分请求进度替代。

| Case | 任务 | 已处理 likelihood requests | 总请求 | 进度 | 可报告 ACC |
|---|---|---:|---:|---:|---|
| v5_mlp | hellaswag | 3,907 | 40,168 | 9.7% | 否 |
| v5 | hellaswag | 8,775 | 40,168 | 21.8% | 否 |

The evaluator aggregates four likelihood choices per sample only after the task completes. Partial request progress is not an unbiased or reportable ACC result and is not resumable by the current worker.

## 总体判定

| 配置 | Macro ACC | ΔACC (pp) | ACC判定 | PPL | ΔPPL | PPL判定 | 合同 | 总判定 |
|---|---:|---:|---|---:|---:|---|---|---|
| Matched BF16 | 0.753853 | +0.000 | — | 17.208506 | +0.000% | — | valid | BASELINE |
| Attention-only | 0.754337 | +0.048 | PASS | 17.313385 | +0.609% | PASS | valid | PASS |
| MLP-only | — | — | — | 27.801928 | +61.559% | FAIL | valid | INCOMPLETE |
| Full V5 | — | — | — | 27.639944 | +60.618% | FAIL | valid | INCOMPLETE |

## 位宽与格式结论登记

`SUPPORTED_CURRENT_SCOPE` 只表示当前指定模型、数据和 context=128 范围内未观察到失败；它不是缩窄位宽的授权。

| ID | 模块/边界 | 当前格式 | 状态 | 严重度 | 动态/静态证据 | 必须动作 |
|---|---|---|---|---|---|---|
| post_rmsnorm_s24_f16 | Post-RMSNorm activation / Hadamard input | S24, 16 fractional bits (range [-128, 127.9999847]) | SUPPORTED_CURRENT_SCOPE | closed | activation_elements=75732353024; fp_to_fixed_saturation=0; hadamard_saturation=0 | Keep S24/F16 for the measured scope; do not relabel it Q16.16. |
| attention_shift_25 | Attention A8W8 Group32 ScaleCode recovery | S42 guard; legal total_shift [26,47] | NOT_REPRODUCED_CURRENT_TWIN | closed | current full ACC format_error=0; current min=28; historical_pre_update_failure=True | Keep the active [26,47] RTL contract for the measured scope; retain the historical shift-25 record and add 24/25/26 boundary regression vectors so future model exports fail closed. |
| attention_qk_pm16_clamp | QK score boundary | S20/F14 storage with an explicit ±16 clamp | OPEN_QUALITY_RISK | medium | WikiText-2 qk_score_clip=63628049; layer31 boundary=1.989% | Use final ACC to decide; first ablate a wider clamp inside the existing S20/F14 native range before adding bits. |
| softmax_probability_u16_counter | Softmax probability output | U16 probability; internal clamp counter not exported | OBSERVABILITY_GAP | medium | hap_softmax_row_128 connects clamp_count to prob_clamp_count_unused | Expose the counter through the top/status register and mirror it in the software audit. |
| mlp_internal_s37_s44_s46 | MLP recovery and accumulation | Group S37/F24; Gate/Up S44/F24; Down S46/F24 | SUPPORTED_CURRENT_SCOPE | closed | guard_overflow=0; accumulator_overflow=0 | Keep the active S37/S44/S46 production path. |
| mlp_down_s24_f16 | MLP Down projection output boundary | S24/F16 (range [-128, 127.9999847]) | CONFIRMED_FAILURE | critical | MLP-only saturation=20251; Full-V5 saturation=18044; layer31 trace reference_abs_max=587.87 | Change only the Down output boundary to signed 32-bit with 16 fractional bits, then rerun full PPL and six-task ACC. |
| mlp_down_output_abi_chain | MLP Down output RTL/DMA/Host ABI | S24/F16 across accumulator finalize, scheduler/repack, 6144-bit tile, 24 AXI256 beats and Host unpack | CONFIRMED_CONTRACT_GAP | critical | active production sources retain out_projection_s24, 16x16x24 payloads, OUTPUT_TILES*24 DMA beats and unpack_s24_q16; widening only the S46 accumulator does not remove the final S24 saturation | Use S32/F16 for the correctness-first implementation and propagate it through the Down-only finalizer, shared slice/queue, scheduler/repack, serial/full command, resource/production top, tensor DMA and Host unpack/buffer sizing. Change each 16x16 output tile from 6144 bits/24 AXI256 beats to 8192 bits/32 beats and the Host C2H payload from 192 KiB to 256 KiB; keep the MLP input and Gate/Up boundaries at S24/F16. |
| mlp_down_s32_validation | Proposed MLP Down S32/F16 replacement | Software diagnostic only; not current RTL | VALIDATION_GAP | high | diagnostic evaluated_blocks=8; full_stream=False; layer31 observed reference_abs_max=587.87, so S27/F16 is the minimum width for that trace while S32/F16 remains the safe ABI choice | Require full WikiText-2 PPL, all six ACC tasks and a full-stream pre-saturation range sweep before freezing S27/S28/S32; use S32/F16 for the correctness-first implementation. |
| artifact_mlp_format_id | Checked-in deployment artifact | 0x48384602 | DEPLOYMENT_BLOCKER | critical | expected=0x48384603; observed=0x48384602 | Regenerate/migrate artifacts after the final format contract is frozen. Because Down S32/F16 changes the output ABI, do not reuse 0x48384603; assign a new synchronized RTL/Host/artifact ID (recommended 0x48384604). |

## MLP Down S32/F16 迁移闭环审计

该审计检查当前 active production closure，不修改 RTL。当前设计仍是 S24/F16，因此迁移状态必须保持显式不完整，不能把内部 S46 误报为输出已经加宽。

状态：`migration_incomplete`（4/15）

| 检查项 | 模块 | 结果 | 当前观察 |
|---|---|---|---|
| down_finalizer_s32_f16 | Down S46/F24 accumulator finalizer | FAIL | current source still exports LANES*24 and saturate_s24 |
| shared_gate_s24_preserved | Shared Gate/Up result boundary | PASS | present |
| shared_down_s32 | Shared Down result boundary | FAIL | current down_s24x16x12 |
| down_scheduler_repack_s32 | Down scheduler and 12→16 inverse repack | FAIL | current scheduler/repack ports remain S24 |
| serial_command_s32 | serial command | FAIL | current 16x16x24 S24 port |
| full_command_s32 | full command | FAIL | current 16x16x24 S24 port |
| resource_top_s32 | resource top | FAIL | current 16x16x24 S24 port |
| production_core_s32 | Production core wiring | FAIL | current wire is 6144-bit S24 |
| tensor_dma_s32_payload | MLP tensor DMA output | FAIL | current 6144-bit tile and 24 beats/tile |
| tensor_dma_input_s24_preserved | MLP tensor DMA input | PASS | present |
| host_s32_output_boundary | Host C2H MLP output boundary | FAIL | current shared 192 KiB S24 buffer and unpack_s24_q16 path |
| host_s24_input_preserved | Host H2C post-RMSNorm input | PASS | present |
| format_id_v4_synchronized | RTL/Host/artifact incompatible ABI identity | FAIL | rtl_04=False; host_04=False; artifact=0x48384602 |
| down_s32_saturation_telemetry | Down S32 terminal saturation observability | FAIL | no dedicated exported Down terminal saturation counter |
| production_source_closure | Active V5 production manifest | PASS | 8/8 required sources present |

## 软件/Host 回归证据

| suite | 状态 | tests | 说明 |
|---|---|---:|---|
| fptoq_frontend | pass | 8/8 | `['/home/user/anaconda3/envs/zhouwenjun/bin/python', '/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/FPtoQ/experiment/test_fptoq_core.py', '-q']` |
| evaluation_protocol | pass | 6/6 | `['/home/user/anaconda3/envs/zhouwenjun/bin/python', '/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/fix_experiment/exp/test_protocol.py', '-q']` |
| tokenizer_boundary | pass | 2/2 | `['/home/user/anaconda3/envs/zhouwenjun/bin/python', '/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/fix_experiment/exp/test_tokenizer_boundary.py', '-q']` |
| format_v3_rtl_static_contract | pass | 2/2 | `['/home/user/anaconda3/envs/zhouwenjun/bin/python', '/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/fix_experiment/exp/test_format_v3_static_contract.py', '-q']` |
| mlp_scalar_model | pass | 11/11 | `['/home/user/anaconda3/envs/zhouwenjun/bin/python', '/home/user/EDA-202/zhuowenjun/fpga_llm_project/0_fix_newdataflow_Hadamard/HAP/tests/test_mlp_fixed.py', '-q']` |
| artifact_contract | pass | 8/8 | `['/home/user/anaconda3/envs/zhouwenjun/bin/python', '/home/user/EDA-202/zhuowenjun/fpga_llm_project/0_fix_newdataflow_Hadamard/HAP/tests/test_scalellm_artifacts.py', '-q']` |
| host_hardware_contract | pass | 5/5 | `['/home/user/anaconda3/envs/zhouwenjun/bin/python', '/home/user/EDA-202/zhuowenjun/fpga_llm_project/0_fix_newdataflow_Hadamard/HAP/tests/test_scalellm_hardware.py', '-q']` |
| v5_cuda_integer_twin | deferred_user_pause | —/15 | `['/home/user/anaconda3/envs/zhouwenjun/bin/python', '/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/FPtoQ/experiment/test_v5_fullchain.py', '-q']` |

## 六任务零样本 ACC

口径：`lm-evaluation-harness==0.4.11`、zero-shot continuation likelihood、context=128、六任务等权 macro。

| 配置 | 任务 | 指标 | ACC | BF16 | Δ (pp) | stderr | 样本数 | 合同 |
|---|---|---|---:|---:|---:|---:|---:|---|
| Matched BF16 | piqa | acc_norm | 0.814472 | 0.814472 | +0.000 | 0.009070 | 1838 | valid |
| Matched BF16 | arc_easy | acc_norm | 0.797138 | 0.797138 | +0.000 | 0.008252 | 2376 | valid |
| Matched BF16 | arc_challenge | acc_norm | 0.553754 | 0.553754 | +0.000 | 0.014527 | 1172 | valid |
| Matched BF16 | boolq | acc | 0.832722 | 0.832722 | +0.000 | 0.006528 | 3270 | valid |
| Matched BF16 | hellaswag | acc_norm | 0.794961 | 0.794961 | +0.000 | 0.004029 | 10042 | valid |
| Matched BF16 | winogrande | acc | 0.730071 | 0.730071 | +0.000 | 0.012476 | 1267 | valid |
| Attention-only | piqa | acc_norm | 0.814472 | 0.814472 | +0.000 | 0.009070 | 1838 | valid |
| Attention-only | arc_easy | acc_norm | 0.793771 | 0.797138 | -0.337 | 0.008302 | 2376 | valid |
| Attention-only | arc_challenge | acc_norm | 0.558874 | 0.553754 | +0.512 | 0.014510 | 1172 | valid |
| Attention-only | boolq | acc | 0.831804 | 0.832722 | -0.092 | 0.006542 | 3270 | valid |
| Attention-only | hellaswag | acc_norm | 0.794662 | 0.794961 | -0.030 | 0.004031 | 10042 | valid |
| Attention-only | winogrande | acc | 0.732439 | 0.730071 | +0.237 | 0.012442 | 1267 | valid |

## WikiText-2 全量 PPL

口径：raw-v1 test 全流、128-token 非重叠 block、丢弃尾部、每个 block 首 token 不计 NLL。

| 配置 | PPL | BF16 | Δ | Δ% | blocks | scoring tokens | full | 合同 |
|---|---:|---:|---:|---:|---:|---:|---|---|
| Matched BF16 | 17.208506 | 17.208506 | +0.000000 | +0.000% | 2257 | 286639 | True | valid |
| Attention-only | 17.313385 | 17.208506 | +0.104879 | +0.609% | 2257 | 286639 | True | valid |
| MLP-only | 27.801928 | 17.208506 | +10.593422 | +61.559% | 2257 | 286639 | True | valid |
| Full V5 | 27.639944 | 17.208506 | +10.431438 | +60.618% | 2257 | 286639 | True | valid |
| Down-S32 diagnostic | 17.577764 | 15.963785 | +1.613979 | +10.110% | 8 | 1016 | False | diagnostic_ablation_not_hardware |

## 合同与根因审计

| 配置 | format error | guard overflow | accumulator overflow | output saturation |
|---|---:|---:|---:|---:|
| Attention-only | 0 | 0 | 0 | 0 |
| MLP-only | 0 | 0 | 0 | 20251 |
| Full V5 | 0 | 0 | 0 | 18044 |

- 当前 MLP RTL 内部为 S37/S44/S46，但 Down 最终边界仍为 S24 Q8.16；Down-S32 仅是软件因果诊断。
- `invalid_format_error` 表示结果精确模拟了 RTL 的非法 shift 置零行为，但硬件格式合同失败，不能写成硬件精度通过。
- 非零 output saturation 必须结合 `linear_audit_by_module.csv` 定位，不得笼统归因给 RoPE 或 Softmax。

## layer 0/15/31 节点 trace

| domain | layers | 每层要求节点数 | 完整 | manifest |
|---|---|---:|---|---|
| attention | 0,15,31 | 7 | True | `/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/fix_experiment/results/llama31_rope_softmax_fixedpoint_hardware128_v3/node_trace/manifest.json` |
| mlp | 0,15,31 | 7 | True | `/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/fix_experiment/results/llama31_rope_softmax_fixedpoint_hardware128_v3/node_trace_mlp/manifest.json` |

| case | domain | layer | node | cosine | NMSE | max abs error | score boundary/valid |
|---|---|---:|---|---:|---:|---:|---:|
| v5_attention | attention | 0 | rope_q_local | 1.0000000000 | 1.767e-11 | 1.52374e-05 | 359/264192 |
| v5_attention | attention | 0 | rope_k_local | 1.0000000000 | 1.386e-11 | 1.52332e-05 | 359/264192 |
| v5_attention | attention | 0 | kv12_key | 0.9999984912 | 3.023e-06 | 0.0312195 | 359/264192 |
| v5_attention | attention | 0 | kv12_value | 0.9999986444 | 2.713e-06 | 0.000969887 | 359/264192 |
| v5_attention | attention | 0 | qk_score_cumulative | 0.9999999994 | 3.941e-09 | 0.00124854 | 359/264192 |
| v5_attention | attention | 0 | softmax_local | 0.9999999836 | 3.650e-08 | 0.000162172 | 359/264192 |
| v5_attention | attention | 0 | pv_local | 0.9999999186 | 1.628e-07 | 1.1843e-05 | 359/264192 |
| v5_attention | attention | 15 | rope_q_local | 1.0000000000 | 2.278e-11 | 1.52523e-05 | 43/264192 |
| v5_attention | attention | 15 | rope_k_local | 1.0000000000 | 8.214e-12 | 1.52192e-05 | 43/264192 |
| v5_attention | attention | 15 | kv12_key | 0.9999984470 | 3.111e-06 | 0.0311584 | 43/264192 |
| v5_attention | attention | 15 | kv12_value | 0.9999985593 | 2.882e-06 | 0.00389862 | 43/264192 |
| v5_attention | attention | 15 | qk_score_cumulative | 0.9999999999 | 7.840e-09 | 0.00120614 | 43/264192 |
| v5_attention | attention | 15 | softmax_local | 0.9999999929 | 2.175e-08 | 0.000262371 | 43/264192 |
| v5_attention | attention | 15 | pv_local | 0.9999999982 | 3.598e-09 | 1.18116e-05 | 43/264192 |
| v5_attention | attention | 31 | rope_q_local | 1.0000000000 | 1.463e-11 | 1.52413e-05 | 5256/264192 |
| v5_attention | attention | 31 | rope_k_local | 1.0000000000 | 7.771e-12 | 1.52015e-05 | 5256/264192 |
| v5_attention | attention | 31 | kv12_key | 0.9999985234 | 2.953e-06 | 0.0317383 | 5256/264192 |
| v5_attention | attention | 31 | kv12_value | 0.9999986586 | 2.683e-06 | 0.0150452 | 5256/264192 |
| v5_attention | attention | 31 | qk_score_cumulative | 0.9999999994 | 6.338e-09 | 0.00114745 | 5256/264192 |
| v5_attention | attention | 31 | softmax_local | 0.9999999935 | 2.178e-08 | 0.000237669 | 5256/264192 |
| v5_attention | attention | 31 | pv_local | 0.9999999998 | 4.904e-10 | 1.17432e-05 | 5256/264192 |
| v5_mlp | mlp | 0 | mlp_gate_projection | 0.9977355166 | 4.549e-03 | 0.0721378 | — |
| v5_mlp | mlp | 0 | mlp_up_projection | 0.9966395685 | 6.761e-03 | 0.0409618 | — |
| v5_mlp | mlp | 0 | mlp_silu_lut_local | 0.9999435975 | 1.128e-04 | 0.00209062 | — |
| v5_mlp | mlp | 0 | mlp_swiglu_round_local | 0.9999998452 | 3.096e-07 | 7.62939e-06 | — |
| v5_mlp | mlp | 0 | mlp_swiglu_cumulative | 0.9982421132 | 3.537e-03 | 0.0346839 | — |
| v5_mlp | mlp | 0 | mlp_down_projection_local | 0.9982923386 | 3.445e-03 | 0.0483499 | — |
| v5_mlp | mlp | 0 | mlp_down_projection_cumulative | 0.9976449922 | 4.784e-03 | 0.0575423 | — |
| v5_mlp | mlp | 15 | mlp_gate_projection | 0.9985766474 | 2.856e-03 | 0.389437 | — |
| v5_mlp | mlp | 15 | mlp_up_projection | 0.9959446899 | 8.172e-03 | 0.125771 | — |
| v5_mlp | mlp | 15 | mlp_silu_lut_local | 0.9999972363 | 5.527e-06 | 0.0021406 | — |
| v5_mlp | mlp | 15 | mlp_swiglu_round_local | 0.9999999963 | 7.317e-09 | 7.62939e-06 | — |
| v5_mlp | mlp | 15 | mlp_swiglu_cumulative | 0.9948128954 | 1.047e-02 | 0.234386 | — |
| v5_mlp | mlp | 15 | mlp_down_projection_local | 0.9954494395 | 9.167e-03 | 0.0554076 | — |
| v5_mlp | mlp | 15 | mlp_down_projection_cumulative | 0.9904654787 | 1.938e-02 | 0.0956658 | — |
| v5_mlp | mlp | 31 | mlp_gate_projection | 0.9992727557 | 1.458e-03 | 0.761328 | — |
| v5_mlp | mlp | 31 | mlp_up_projection | 0.9991872832 | 1.630e-03 | 0.47078 | — |
| v5_mlp | mlp | 31 | mlp_silu_lut_local | 0.9999997958 | 4.084e-07 | 0.00215564 | — |
| v5_mlp | mlp | 31 | mlp_swiglu_round_local | 1.0000000000 | 1.845e-11 | 7.62939e-06 | — |
| v5_mlp | mlp | 31 | mlp_swiglu_cumulative | 0.9994516989 | 1.251e-03 | 18.2945 | — |
| v5_mlp | mlp | 31 | mlp_down_projection_local | 0.8664657705 | 2.578e-01 | 459.87 | — |
| v5_mlp | mlp | 31 | mlp_down_projection_cumulative | 0.8656172846 | 2.576e-01 | 454.086 | — |

## 预注册阈值

- Attention-only：Macro ACC 下降不超过 1.0 pp；PPL 相对上升不超过 10%。
- MLP-only：Macro ACC 下降不超过 1.0 pp；PPL 相对上升不超过 10%。
- Full V5：Macro ACC 下降不超过 1.5 pp；PPL 相对上升不超过 15%。
- format error、非预期 guard/accumulator overflow 必须为 0。
- 质量阈值通过与硬件合同通过是两个独立条件，二者均通过才能声称当前硬件定点链路保持精度。

## 可复核产物

- 主指标：`/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/fix_experiment/results/llama31_rope_softmax_fixedpoint_hardware128_v3/case_metrics.csv`
- case 判定：`/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/fix_experiment/results/llama31_rope_softmax_fixedpoint_hardware128_v3/case_summary.csv`
- 节点 trace：`/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/fix_experiment/results/llama31_rope_softmax_fixedpoint_hardware128_v3/node_trace.csv`
- 硬件计数器：`/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/fix_experiment/results/llama31_rope_softmax_fixedpoint_hardware128_v3/hardware_audit.csv`
- Linear 模块审计：`/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/fix_experiment/results/llama31_rope_softmax_fixedpoint_hardware128_v3/linear_audit_by_module.csv`
