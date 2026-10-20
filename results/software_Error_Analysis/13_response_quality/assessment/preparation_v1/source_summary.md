# A015 source summary — response quality preparation v1

Scope: M005/SM024, E012/R012. A015 owns only the new response_quality_assessment package, benchmark datasets, assessment and figure outputs. Production, historical experiments, generation/runtime and shared indexes were not changed.

Official sources are pinned and checked in datasets/dataset_manifest.json: AlpacaEval 805 single-turn questions, HF revision 2edc6fad8be6b14ea7230aabfd08188da6b8b814, dataset CC-BY-NC-4.0; MT-Bench 80 two-turn questions, FastChat revision 587d5cfa1609a43d192cedb8441cac3c17db105d, repository Apache-2.0. Alpaca source groups are not semantic categories. MT has eight official categories of ten questions each. Downloaded model answers are not gold or our OUTPUT_ONLY reference; MT GPT-4 auxiliary answers cover only 30 questions, and question hints cover 39.

Implementation: prepare_datasets.py, length_audit.py, pack.py, aggregate.py, plot.py, common.py, test_assessment.py. Frozen identities and actual CPU qualification: ../qualification_cpu_v1/source_ready.json. The source package README gives exact CLI and schema. No inference, external API client or code executor is included.

Evaluation unit: one whole question conversation, not a turn or judge order. Blinded packets contain only opaque case IDs and user/Response A/Response B text. The same judge sees swapped orders. Private map and original generation files must remain unread by the initial judge. All mapped judgements must agree; conflict, missing, failed, truncated and unjudgeable cases remain unresolved. Objective math/coding checks require independent trustworthy evidence and isolated execution if needed.

Primary intervals: pointwise Wilson 95% conditional on resolved questions; question-cluster bootstrap is auxiliary. Independent-question/exchangeability assumptions are unverified; missingness is not corrected, and benchmarks are not pooled. Comparable is not correctness/equivalence/noninferiority. No human review has been performed.
