# Matrix scheduler CPU review

Latest boundary: [AT007 source freeze](matrix_freeze_AT007.json) supersedes the AT004 status below. Its 49 CPU tests passed with identical entry/exit matrix, worker, and test hashes. Fixed GPU slots now persist across all stages/retries; completed and failed-resume sources must prove the assigned actual physical GPU UUID and matching single CUDA visibility. R002 explicitly uses `native_cache_call_parity_v2`; every native step, finite/cache structure, corruption negative control, narrow one-step EOS exception, and same-device repeatability is checked. The failed v1 numerical diagnostics remain unchanged as diagnostics in v2. See [R002 independent decision review](cache_review_AT002.md).

The finalizer dispatch was preserved, remains CPU-only, and writes logs named by supervisor attempt to avoid retry collisions. Tests cover all three stage queues under different mock worker durations and two successive finalizer invocations. AT006 passed its 49 assertions but detected a concurrent worker-source update and deliberately records `success=false`; only the source-stable AT007 qualifies the final source.

One bounded recovery limitation was reported and explicitly deferred by the controller: an OS launch failure before the worker creates an AT directory can leave precreated stdout/stderr logs, and the current directory-count attempt allocator may select the same number on retry. These logs must be preserved; this review does not claim that recovery case was repaired. There are no current smoke-launch blockers from this review.

The following text records the earlier AT004 review and its then-applicable source boundary.

The corrected scheduler passed 35 CPU safety tests. The test file is `exp/test_gsm8k_matrix.py`; the matrix, worker, and protocol source files were read only during this subtask. [Latest audit evidence](matrix_cpu_safety_AT004.json) includes source hashes, test identity, CPU affinity, and execution scope. [Review status](matrix_review.json) separately records implementation qualification and exact applicability. The earlier 23-test audit remains in AT003 for its earlier matrix version.

The two initial smoke-launch blockers were reported and corrected by the parent: completed attempts now validate frozen execution identity and artifact/row integrity before reuse or stage selection; children inherit their GPU lock FD, and supervisor exceptions drain existing children naturally before releasing parent locks. The fault test launched an explicit short CPU Python stand-in, injected a second-slot launch error, and verified that the first child had finished, `state.active` was empty, and its lock FD had been inherited. No GPU worker, GPU operation, or EDA process was started.

Coverage includes positive smoke/pilot/formal source fixtures; stale plan, checkpoint, and source identities even with self-consistent new checksums; artifact corruption; duplicate and mismatched generation rows; denominator and formal full-split checks; valid completed reuse; refusal to reuse stale identities; and refusal to launch formal without pilot. Repeatability checks use the actual `verification.records` schema and cover reordered records, changed prompt/token evidence, duplicate IDs, empty prefixes, and reuse of the same attempt. The budget gate permits one capped generation out of 32 and blocks two out of 32.

There are no remaining smoke-launch blockers from this review. The parent closed the three follow-ups reported with AT003: scores-row coverage/identity and score values are checked against generated text; `verification.json` is bound to the manifest's embedded generation verification; and formal checks the maximum pilot allocated/reserved peak plus 20% against each allocated GPU's free memory. New CPU tamper tests and mocked memory tests passed for these fixes. A failed pilot gate does not query CUDA; an insufficient memory gate does not launch a formal worker. Both empty prefixes and nonterminal short prefixes are rejected; a matching short prefix ending in the pinned EOS is accepted.

All CUDA memory queries were mocked in these tests. Actual CUDA memory, generation/cache/QDQ behavior, full formal accuracy, and final independent rescoring remain parent/worker responsibilities.

The first two audit files are retained as failed test-fixture attempts. They initially lacked fields added by the concurrently updated scheduler, then lacked the relative few-shot file after moving the fixture plan to a temporary directory. These were fixture failures, not GPU/EDA attempts or method results. AT003 and AT004 are successful audits of their respective recorded sources.

Reproduce on CPU:

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 taskset -c 8,9 /home/user/anaconda3/envs/zhouwenjun/bin/python project/software/0_Software/fix_experiment/exp/test_gsm8k_matrix.py --audit-output <new-audit-json>
```
