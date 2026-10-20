Latest follow-up: readiness omission correction applied after both shared diagnostics ended; CPU120 PASS and final source boundary are recorded in [post-diagnostic source manifest](../model_diag_review_AT001/readiness_fix_applied_AT001/final_source_manifest.json). The original delivery below applies to its earlier matrix version.

# Bytewise consumer integration — source summary

Owner: A010 `/root/gsm8k_protocol`, engineering. Parent `/root` independently reviews production consumers. Scope is the existing GSM8K integrity-performance preparation; this is a CPU software qualification, not an ACC run.

`checkpoint_static_content_v1` remains the semantic contract. The explicit protocol/identity implementation is `immutable_cpu_chunks_memcmp_full_content_v1`; only a missing implementation field selects legacy. Explicit null, unknown values, and mismatched plan/contract/worker/artifact identities are rejected.

Changes: `gsm8k_protocol.py` validates immutable capture source identities, tensor/storage inventory, captured SHA and byte counts, complete per-phase byte equality, honest derived-root metadata, and an arithmetic 80 GiB post-capture host reserve. Matrix completed-attempt reuse, repeatability, frozen contracts and independent summary consumers propagate the expected implementation from plan/contract. New tests retain full artifact rehashing for semantic fault controls. Prompt construction, scoring rules, numerical kernels and native-cache-v2 semantics are unchanged in the consumer diff.

Source boundary and frozen copies: [source_manifest.json](../source_manifest.json), [consumer_changes.patch](../consumer_changes.patch), `source_frozen/`. Original three consumer sources remain in `before/` with [before_sources.json](../before_sources.json).

- `gsm8k_protocol.py`: `59dfed785c9f54e5618c1a15135b816363e12b8066787564c083ca7f8961917e`
- `run_gsm8k_matrix.py`: `f5afe3c5316fb08fc0c9ce90e858c8963348e0d39607a0193127a203144d46c2`
- `summarize_gsm8k.py`: `9e09b2e95716aa17d09cf7e4d6f84cdb560d2991f0c20396205b30465079e3cc`
- `test_gsm8k_bytewise_consumers.py`: `15acba7d48f50eb8db048c8c412aeb734fc0389b2622f3fd57c336050d074cf7`
- `gsm8k_integrity_bytewise.py`: `17bdabd32e792391622239b32ad81e316fa2ccd688310b4a9fb9bb3f46146542`
- `run_gsm8k_worker.py`: `80aa1938eed007445f764aa45bfde59d404796278782e7d1d63732dee6f29d4f`
- `gsm8k_weight_integrity.py`: `0e11092488523d97acd7ec76776ada669068c70bec1efc190bf5159c43f99121`

Reproduction uses the exact command/environment in [AT003 receipt](../cpu_validation/AT003/receipt.json): CPU 8–9, two numerical-library threads, empty CUDA visibility, project `zhouwenjun` interpreter, bytecode disabled, temporary/cache paths inside this evidence directory. Producer helper/worker are owned by A013; A010 changed neither.
