# GSM8K CPU protocol preparation

Scope: M004 / SM020 / E010, A010. Implement the raw five-shot GSM8K request and scorer contract, independently compare it with installed lm-evaluation-harness 0.4.11, and qualify all six tokenizers. This delivery does not include generation, model weight loading, or GPU/EDA work.

Implementation files: `exp/gsm8k_protocol.py`, `exp/test_gsm8k_protocol.py`, and `exp/prepare_gsm8k_inputs.py` under the current `fix_experiment` root. The module exports `DEFAULT_PLAN`, `load_plan`, `prepare_requests`, `score_response`, `sha256_file`, `canonical_hash`, and `atomic_json`. Requests contain original gold answers; only train demonstration answers enter prompts. Both scores use the installed task's string extraction and normalization semantics.

Authority: [original plan](../../../../../source/gsm8k_completion_plan_20261018/plan.json), fixed five-shot schedule, and exact train/test bytes. The old plan's planning/authorization metadata is retained unchanged; the parent owns current execution authorization and resource scheduling. The CLI creates a portable copy with relative input locations and preserves original plan bytes in `source_plan.json`. Changed dataset/schedule hashes fail closed. Existing preparation directories are rejected to preserve earlier attempts.

References and implementation SHA-256 identities are recorded in [source_identity.json](../source_identity.json). The independent oracle uses installed GSM8K YAML, `ConfigurableTask.fewshot_context`, the installed sampler, `RegexFilter`, `TakeFirstFilter`, `Task.process_results`, and `HFLM.tok_encode`. Only dataset download is replaced with exact local export mapping. No oracle templates, scoring rules, or samplers are patched.

Reproduction from repository root:

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 taskset -c 8,9 /home/user/anaconda3/envs/zhouwenjun/bin/python project/software/0_Software/fix_experiment/exp/test_gsm8k_protocol.py --audit-output <new-evidence-json>
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false taskset -c 8,9 /home/user/anaconda3/envs/zhouwenjun/bin/python project/software/0_Software/fix_experiment/exp/prepare_gsm8k_inputs.py --output-dir <new-empty-attempt-directory> --tokenizer-audit
```

Actual CPU affinity was 8–9, CUDA visibility was empty, and thread limits were two. Formal generation parameters were not changed. The tokenizer audit loads tokenizers locally with no remote code and no model weights.

Follow-up scope: independently audit the parent-owned matrix scheduler and implement `exp/test_gsm8k_matrix.py` only. It uses temporary worker-shaped fixtures, an explicit CPU subprocess for exception/drain testing, and mocks all CUDA memory queries. The matrix and worker implementations remain parent/worker-owned. Reproduction and source boundaries are in [matrix_review.md](../matrix_review.md).

Latest ownership supplement: after R001 sources were preserved, the parent explicitly delegated `run_gsm8k_matrix.py` and its test to A010 for fixed-slot GPU identity and R002 verification-contract support. Worker/numerical code remained owned by A011/controller. The final source freeze and qualified test identity are in [matrix_freeze_AT007.json](../matrix_freeze_AT007.json); implementation ownership is no longer limited to the earlier read-only matrix review.
