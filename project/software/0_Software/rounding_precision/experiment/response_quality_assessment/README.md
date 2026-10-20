# Offline response-quality assessment

This package prepares public benchmark text, blindly packs actual paired freely
generated responses, and aggregates two swapped-order judgements from the same
AI-agent judge. It contains no inference engine, API client, or code executor.

The current and OUTPUT_ONLY arms preserve the same base quantization, ScaleCode,
Hadamard, LUT and common-exit rules. The benchmark's downloaded model answers
are auxiliary material, never the numerical reference arm or a universal gold.
AlpacaEval groups are **Source groups**; MT-Bench groups are task categories.
Each complete two-turn MT conversation is one cluster. Benchmarks have separate
overall results and are never merged into one quality score.

All CLIs refuse to overwrite output runs. Run with the project Python and CPU
thread environment fixed to one. Download preparation reads only official small
text at pinned revisions; it does not execute dataset loading scripts.

```bash
python -B prepare_datasets.py --output-dir /new/datasets
python -B length_audit.py --prompts /datasets/prompts.jsonl --model-dir /checkpoint --context-length 2048 --max-new-tokens 512 --output /new/length_audit.json
python -B pack.py --prompts /datasets/prompts.jsonl --responses /generation/responses.jsonl --output-dir /new/pack --batch-size 12
python -B aggregate.py --pack-dir /pack --scores /judgements/batch001.jsonl --scores /judgements/batch002.jsonl --judge-manifest /judgements/judge_manifest.json --output-dir /new/aggregate
python -B plot.py --summary /aggregate/summary.json --output-dir /new/figure
python -B -m unittest discover -s /absolute/path/response_quality_assessment -p 'test_assessment.py' -v
```

Generation rows must preserve `prompt_id`, `cluster_id`, `dataset`,
`source_revision`, zero-based `turn_index`, exact `user_prompt`, and
`responses.current` / `responses.output_only` with actual `text`, explicit
`truncated=false`, and `pair.both_complete=true` to be judge eligible. Missing,
failed, unknown or capped answers remain in the planned-question denominator.
No truncated prompt is accepted. Input selection must precede generated answers.

Only `public/batches/`, `public/score_schema.json`, and `public/rubric.txt` may be
given to the judge. Do not expose `private/`, the original generation records,
or pack manifests that identify original sources until initial scores freeze.
The public allowlist has opaque case ID and user/Response A/Response B text.
Self-identification in actual answer content is not edited or fabricated away.
For each question, answer order is deterministically reversed in a second case;
case ordering is randomized by a private seed, not model quality.

The judge produces strict records with a literal excerpt from each answer,
reason, confidence, flags and actual judge-run ID. A judge manifest must contain:

```json
{"assessment_kind":"preliminary_ai_agent_assessment","judge_run_id":"ACTUAL_RUN_ID","human_reviewed":false,"actual_model":null,"actual_effort":null,"configuration_evidence":null}
```

Replace unknown configuration fields only with evidence; do not copy a desired
model setting into an unverified actual setting. Root owns the actual judge
configuration record. The same judge's swapped orders are not independent judges
or independent samples. A decision resolves only when both mapped orders agree;
conflict, unjudgeable, invalid or missing scores are unresolved. No conflict is
forced into Comparable. Comparable means a material difference was not
established, not semantic equivalence or a proof that both answers are correct.

For math and coding, prefer trustworthy exact-answer or isolated execution checks
when actually available. The pack does not execute model code, infer gold from
another model, or mark an unrun check as passed. Objective checks require their
own source/protocol/output identity and should be cited in judge evidence.

Statistics preserve every planned cluster. Three-class percentages use resolved
clusters, with all-submitted percentages, coverage and unresolved reason counts
alongside them. The primary pointwise 95% intervals are Wilson score intervals
for one categorical indicator per resolved question. They remain nondegenerate
at 0/n and n/n, including n=1. They do not correct unresolved-case selection.
Auxiliary conditional percentile 95% intervals resample whole question
clusters; a multinomial draw implements exactly the categorical cluster bootstrap.
The assumptions of independent/exchangeable benchmark questions are unverified.
Zero/all categories can have degenerate bootstrap intervals and do not prove zero
risk. No missingness correction or noninferiority conclusion is claimed.

The English stacked PNG shows separate benchmark overall rows, the actual
resolved/planned and unresolved counts, and primary Wilson intervals per row.
Interval tables are exported with
the same figure data. With no actual resolved assessments, rendering is refused.
Synthetic contract tests do not create a quality figure or benchmark result.
