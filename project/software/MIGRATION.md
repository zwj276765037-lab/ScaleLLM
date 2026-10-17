# Software Migration

Scope: M001/SM001 software slice, 2026-10-14. Only this software directory
was written. The source tree was never moved, edited or cleaned; shared
indexes, management records and other agents' files were not touched.

42 selected source files, 712,128 bytes; 34 remain byte-identical and 8 have
path-only adaptations (712,183 copied destination bytes). An initial SHA256
snapshot was taken before edits; all 42 source hashes still match it.
Selection is explicit in `COPY_PLAN.json`; `file_mapping.json` records each
absolute source, relative destination, both SHA256 hashes, sizes and
`modified`. New documentation/check tooling has `source=null`.
The mapping/report exclude themselves from recursive self-hashing.

## Source Mapping

| Source Under Old ScaleLLM | Destination / Selection |
| --- | --- |
| `0_Software/fix_experiment/exp` | Same relative path; 14 Python modules + requirements |
| `0_Software/FPtoQ/experiment` | Same relative path; 7 Python modules + requirements |
| `0_Software/experiment/scripts` | Same relative paths; two QDQ method modules only |
| `model` | Same relative path; package marker + three required Python helpers |
| `0_Software/introduction`, `0_Software/fix_experiment/source`, `introduction` | Four algorithm/numerical/protocol specifications only |
| `0_Software/fix_experiment/results/s32_candidate_validation` | Five selected JSON files under `evidence/format05` and `evidence/down_s32` |
| `0_Software/fix_experiment/results/six_model_algorithm_literature_2048` | Two manifests + two CSV tables under `evidence/literature_2048` |

## Path Adaptations

| Modified Source | Change |
| --- | --- |
| `fix_experiment/exp/protocol.py` | New software root; environment-configurable external/model/data roots |
| `fix_experiment/exp/run_eval_worker.py` | Import migrated QDQ/twin, not old workspace software; external model root |
| `fix_experiment/exp/run_six_model_eval.py` | External model root |
| `fix_experiment/exp/run_extended_ppl_eval.py` | External model root |
| `fix_experiment/exp/run_extended_ppl_worker.py` | External model/data roots; registered `data/...` asset paths relative to data root |
| `fix_experiment/exp/summarize_six_models.py` | Hash migrated source paths relative to this software root |
| `fix_experiment/exp/test_tokenizer_boundary.py` | External checkpoint root |
| `model/export_scalellm_llama31_artifacts.py` | Replace broken ancestor-based model default with configurable local model root + Llama-3.1-8B-Instruct |

The first seven paths above have prefix `0_Software/`. Constants, formulas,
rounding, widths, kernels, thresholds and case defaults are unchanged.
Definition AST comparison allows only `code_identity` and `validate_asset`
path changes; all other copied functions/classes are unchanged.

## Retained Evidence

`evidence/format05/final_validation_summary.json` and the handoff are historical
software approval summaries, not new runs. Two strict format 05 ACC manifests
retain ARC-Challenge/WinoGrande evidence. The two `evidence/down_s32` PPL
manifests explicitly describe the intermediate format 04 S32-output candidate,
not a newly executed full format 05 PPL. Do not relabel these runs.
The literature manifests/tables describe the 2026-09-15 QDQ matrix, not the
later fixed-point candidate. Original timestamps, code identities and paths
inside all evidence files remain unchanged; current code identity is the
migration mapping, not those historical identities.

## Not Migrated

All root RTL/Host/EDA trees, `1_Hardware`, `ModularExperiment`, testbench data,
bitstreams, model weights/tokenizers, datasets, activation captures, caches,
logs, task/mission/goal/agent records and bulk historical results stay outside.
GPU queues, legacy launch shells, hardware audit scripts, redundant older
evaluators and workbook builders are not dependencies of the retained core.
Complete candidate shards/traces remain at
`/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/fix_experiment/results/s32_candidate_validation`;
complete six-model evidence remains in the sibling
`six_model_algorithm_literature_2048` directory. These are external provenance,
not imported runtime code.

## Validation Boundary

`static_check.json`: SHA256, Python syntax/compile without bytecode files,
finite local import/script-path inventory, JSON parsing, path-only definition
comparison and external path existence. No GPU, PPL, ACC, RTL/EDA simulation,
numerical regression, model fingerprint rerun or dependency installation.
The checked paths do not prove checkpoint/data content identity or runtime
compatibility. Historical summaries are not independent re-verification.
