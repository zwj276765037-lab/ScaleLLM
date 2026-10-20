# A015 result summary — CPU preparation only

execution_state: completed
verdict: supported_with_scope
applicability: pinned benchmark input preparation and offline assessment contracts; generated response quality is unassessed.

Prepared complete raw and normalized rosters: AlpacaEval 805 questions/805 turns; MT-Bench 80 questions/160 turns; combined input 885 question clusters/965 turns. The two benchmark results will stay separate. A one-question development smoke input was selected before generation solely by shortest original input (alpaca_eval:199); it is not the formal quality sample.

CPU tokenizer audit used the actual local tokenizer/chat template. Alpaca first-turn lengths 13–493 tokens (median31), planned context maximum1005 including512 output tokens. MT first-turn22–359 (median48), planned second-turn envelope1415 including both512-token answer reserves. No roster question exceeds2048 in this planning check. Actual arm-specific second-turn history must still be checked at runtime; no prompt is truncated or excluded.

Actual qualification: 13 CPU contract tests PASS, 0.061 seconds. Tests cover true order reversal, complete two-turn/one-cluster outcomes, conflict and missingness, excerpt validation, source matching, duplicate rejection, pack identity tampering, planned/submitted/resolved denominators, Wilson zero/all/n=1 bounds, reproducible auxiliary bootstrap, and refusal to render with no resolved results. Separate temporary synthetic CLI pack/aggregate runs exited0/0 and CSV checks passed. Synthetic outputs were deleted and were not benchmark measurements.

No model forward, judge request, paid API call, generated benchmark answer, or quality PNG was produced by A015. Source and dataset identities: ../qualification_cpu_v1/source_ready.json. Raw CLI qualification: ../qualification_cpu_v1/offline_cli_log.json. Formal quality evidence awaits Root's generation queue and actual blind scores.
