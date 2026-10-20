# GSM8K CPU protocol results

Execution completed; CPU protocol qualification passed. These results qualify prompt construction, scoring, frozen input reconstruction, and tokenizer budgets for the recorded sources. They do not establish GPU/cache/QDQ behavior or GSM8K accuracy.

| Check | Observed result | Evidence |
| --- | --- | --- |
| CPU tests | 9 passed | [cpu_parity_AT002.json](../cpu_parity_AT002.json) |
| Formal prompt bytes vs installed harness | 1,319 compared, 0 mismatches | Same parity record |
| Train prompt bytes vs installed harness | 32 pilot and 4 smoke compared, 0 mismatches | Same parity record |
| Score boundary and deterministic generated cases | 335 cases, strict/flexible extraction and correctness matched | Same parity record; individual cases retained |
| Official gold scoring | 1,319 gold responses, both metrics matched | Same parity record |
| Test answer isolation | All 1,319 answers perturbed, 0 prompt changes | Same parity record |
| Input identity guards | Dataset and schedule tampering rejected | Same parity record |
| Portable snapshot reconstruction | Smoke/pilot/formal requests identical to source; hashes rechecked | [input_manifest.json](../input_preparation_AT001/input_manifest.json) |
| Tokenizer budgets and installed encoding parity | 7,914 formal inputs, 0 over budget, 0 token ID mismatches | [tokenizer_audit.json](../input_preparation_AT001/tokenizer_audit.json) |

| Tokenizer | Maximum input tokens | Budget |
| --- | ---: | ---: |
| DeepSeek-R1-Distill-Llama-8B | 1,404 | 4,096 |
| GLM-4-9B-0414 | 1,436 | 4,096 |
| Llama-3.1-8B-Instruct | 1,434 | 4,096 |
| Llama-3.2-3B-Instruct | 1,434 | 4,096 |
| Qwen2.5-7B-Instruct | 1,658 | 4,096 |
| Qwen3-8B | 1,658 | 4,096 |

The first test attempt failed before any test ran because the independent reader used `str.splitlines()`, which treats legitimate U+2028 characters inside JSON strings as line boundaries. Its evidence is retained as [cpu_parity.json](../cpu_parity.json). The independent reader now separates JSONL records only at LF. The request implementation already iterated file lines and was unaffected. The successful rerun retains its separate attempt record.

Scoring preserves first strict marker, last flexible numeric match, task regex normalization order, and exact strings such as `18.0` versus `18`; it does not replace these with numeric tolerance. Tokenization preserves checkpoint-native special tokens and forbids truncation.

Follow-up scheduler review: 35 CPU safety tests passed for the source identities in [matrix_cpu_safety_AT004.json](../matrix_cpu_safety_AT004.json). Completed-source identities, artifact/row coverage, scores, verification binding, cross-process prefixes, stage prerequisites, inherited GPU lock descriptors, natural child drain after a supervisor exception, and mocked formal memory gates were checked. [Review](../matrix_review.md) separates CPU qualification from actual GPU execution.

Latest R002 scheduler delivery: [AT007](../matrix_cpu_safety_AT007.json) passed 49 tests and verified unchanged source hashes throughout the run. It adds fixed same-device slots across stages, hard actual-UUID checks including failed-attempt imports, explicit v1/v2 separation, per-step native-cache hard gates, qualified early-EOS N/A, and distinct finalizer retry logs. Actual producer-to-consumer ordinary/EOS CPU integration was also checked by A011. R001's numerical failures are preserved; [independent review](../cache_review_AT002.md) assesses the controller's explicit v2 revision without reclassifying those failures. No GPU or formal generation was executed by A010.
