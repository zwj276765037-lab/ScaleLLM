# ScaleLLM Software Core

M001 software-only copy, 2026-10-14. Read-only source:
`/home/user/EDA-202/zhuowenjun/ScaleLLM`. No experiments were run.
The small retained `0_Software` layout preserves local import relationships.
Start with the [algorithm](0_Software/introduction/01_final_scalecode_algorithm.md),
[format 05 specification](0_Software/fix_experiment/source/ScaleLLM_MLP_Down_S32_fix_handoff.md),
then `run_eval_worker.py` and `v5_fullchain.py` below.

## Code Entrypoints

Paths in the first table are under `0_Software/fix_experiment/exp/`.

| Source | Responsibility |
| --- | --- |
| `run_eval_worker.py` | Model loading, QDQ/integer-twin selection, ACC/PPL, bounded node traces |
| `protocol.py` | Frozen prompts, metrics, split identities, context policies, external paths |
| `six_model_matrix.py` | Six checkpoint geometries and five algorithm configurations |
| `merge_eval_shards.py` | Validate and merge task/PPL shards without mixing protocols |
| `summarize_plan.py` | Matched-protocol comparison |
| `summarize_six_models.py` | Matrix validation, result tables, current code identity |
| `prepare_model_identity.py` | Checkpoint content fingerprinting |
| `audit_tokenizer_boundaries.py` | Continuation-token boundary checks |
| `prepare_standard_data.py` | Official ARC split preparation; writes data, not used during migration |
| `run_six_model_eval.py` | Historical two-GPU algorithm evaluation orchestration |
| `run_extended_ppl_eval.py`, `run_extended_ppl_worker.py` | Registered-corpus PPL scheduling/scoring |
| `test_protocol.py`, `test_tokenizer_boundary.py` | Protocol and tokenizer regression sources; not executed |

| Other Source | Responsibility |
| --- | --- |
| `0_Software/experiment/scripts/scale_code_linear/scalepath4_method_inference.py` | Hadamard folding, Group32 quantization, ScaleCode, base Linear adapter |
| `0_Software/experiment/scripts/accuracy_MLP_4bit/mlp4_method_inference.py` | Attention W8 / MLP W4 selection and FP16/FP32 scale controls |
| `0_Software/FPtoQ/experiment/fptoq_core.py` | NumPy FP-to-fixed/Hadamard/A8 numerical reference and error statistics |
| `0_Software/FPtoQ/experiment/torch_frontend.py` | Torch fixed-frontend adapters |
| `0_Software/FPtoQ/experiment/v5_fullchain.py` | Integer Attention/MLP twin, Triton kernels, audit counters, format 05 API |
| `0_Software/FPtoQ/experiment/run_experiment.py`, `capture_model_activations.py` | Group32 error analysis and bounded activation collection |
| `0_Software/FPtoQ/experiment/test_fptoq_core.py`, `test_v5_fullchain.py` | Numerical regression sources; not executed |
| `model/fixbit_v2.py`, `model/mlp_fixed.py` | Scalar fixed-point Attention/MLP helpers; some labels are legacy |
| `model/export_scalellm_llama31_artifacts.py` | Read-only checkpoint access, folded-weight quantization and RoPE helpers used by the twin; full export not run |
| `model/__init__.py` | Local package marker |

## Version Boundaries

QDQ: Hadamard32, Group32, MinMax A8, Attention W8, MLP W4, uint8 code/shift.
No numerical algorithm was changed. `literature_2048` and `hardware_128` are
distinct protocols, not interchangeable baselines.

Format 05: Gate/Up S37/S44/S24 stays unchanged; Down shift `[12,44]`,
S45/F24 guard, S54/F24 accumulator, S32/F16 output. The MLP-only CLI case is
`v5_mlp_down_s32_shift12_ablation`. The full-chain API supports
`down_output_width=32, down_shift12_candidate=True`; the existing
`v5_down_s32_ablation` CLI still selects format 04. Defaults were not changed.
Software approval recorded in the old summary is not RTL/Host approval.

## External Dependencies

Default models: `/home/user/EDA-202/zhuowenjun/fpga_llm_project/configs/models`.
Default data: `/home/user/EDA-202/zhuowenjun/fpga_llm_project/data`.
Set `SCALELLM_EXTERNAL_ROOT`, `SCALELLM_MODEL_ROOT`, `SCALELLM_DATA_ROOT` to
relocate them; workers also accept `--model`, runners `--model-root`/`--python`.
The original runner Python is `/home/user/anaconda3/envs/zhouwenjun/bin/python`.
Dataset relative paths and historical hashes are in
`evidence/literature_2048/data_manifest.json`; extended corpora use
`data/bape_eval/manifest.json`. Weights, tokenizers and datasets were not copied.

Evaluator pins are in `0_Software/fix_experiment/exp/requirements.txt`;
PyTorch is separately `2.10.0+cu128` in the historical stack. The extension
also imports `pyarrow` (no explicit version pin in the original requirements).
No packages were installed or imported to validate runtime availability.

## Migration Check

From this directory, `python3 -B tools/check_migration.py` only hashes and
parses files. It does not import application modules or run tests/kernels.
See [MIGRATION.md](MIGRATION.md), `file_mapping.json` and `static_check.json`.
