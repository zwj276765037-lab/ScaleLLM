# GSM8K CPU protocol status

- execution_state: completed
- verdict: supported for CPU protocol qualification only
- applicability: recorded GSM8K main local bytes, fixed five-shot schedule, installed lm_eval 0.4.11 task metadata 3.0, six tokenizers, recommended v1 budget
- review: engineering self-check and independent installed-interface comparison completed; parent owns experiment acceptance
- current_stage: handoff to parent scheduler and generation worker
- blocker: none within A010 scope
- resources: actual affinity CPUs 8–9; CUDA_VISIBLE_DEVICES empty; no GPU, model weights, EDA, or descendants launched
- progress: 1,319 formal prompt comparisons, 335 score boundary cases, 1,319 gold comparisons, and 7,914 tokenizer inputs completed
- next_step: parent integrates execution plan and source identities; worker conducts authorized smoke/pilot and generation/cache/QDQ qualification

Shared interface is implemented. Snapshot, request hashes, tokenizer audit, successful and failed test evidence, and exact source identities are linked in the [results summary](../experiment_results/summary.md). No formal model-generated GSM8K answers exist in this subtask, and this evidence contributes no accuracy-table cells.

Current task events were sent to the active parent through actual collaboration messages. Parent maintains A010/project-wide state; this subtask does not write shared indexes or agent bindings.

Follow-up matrix audit completed: 35/35 CPU tests passed, with no remaining smoke-launch blockers identified for the recorded source version. Scores/verification binding and the formal peak-memory-plus-20% gate were added by their parent owner and covered by CPU negative/positive tests. Actual CUDA memory was not queried here. Latest source boundary: [matrix_review_AT004.json](../matrix_review_AT004.json).

Current final boundary: [matrix_freeze_AT007.json](../matrix_freeze_AT007.json), 49/49 CPU tests and unchanged source hashes. Matrix/test ownership was explicitly delegated to A010 for fixed slots, actual GPU UUID validation and the centrally decided R002 `native_cache_call_parity_v2` contract. This task is completed and code is frozen. No new smoke-launch blocker was found; the documented pre-worker log/AT-allocation recovery limitation is deferred to the controller. Actual R002 launch, 30-group qualification, formal generation, independent rescoring and publication remain controller/worker responsibilities.
