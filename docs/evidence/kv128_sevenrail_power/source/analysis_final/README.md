# Frozen offline analysis

> These are archived instructions for the original local/ZIP layout. In a public Git checkout, use `python3 tools/release/verify_power_repeat_asset.py --download outputs/ScaleLLM_KV128_SevenRail_PMBus_20261102.zip --recompute` from the repository root. The raw JSONL inputs are in the Release archive, not this readable Git subset.

These scripts only read copied JSON/JSONL files and write new local outputs. They do not access Dell or the board. From the ScaleLLM repository root, the following single command recomputes the final analysis JSON (choose a new output name if the example already exists):

```bash
PYTHONDONTWRITEBYTECODE=1 python3 0_Source/command_active_power/kv128_repeat_sevenrail/source/analysis_final/kv128_sevenrail_windows.py --metadata 0_Source/command_active_power/kv128_repeat_sevenrail/native/main_004/telemetry.json --jsonl 0_Source/command_active_power/kv128_repeat_sevenrail/native/main_004/telemetry.jsonl --windows 0_Source/command_active_power/kv128_repeat_sevenrail/native/main_004/workload/windows.jsonl --commands 0_Source/command_active_power/kv128_repeat_sevenrail/native/main_004/commands.jsonl --target-period-ms 140 --output /tmp/kv128_sevenrail_recompute.json
```

The expected SHA-256 of the JSON output is `a00d62ac8031a1c3dd2b642f0804323c87429f5383106b5c48a2c57ff07f4bf7`, identical to `results/main_004_analysis_v2.json` when run with the archived raw files and this Python implementation. The result status is `PARTIAL_WITH_LIMITS`; `raw_record_validation_status=PASS` refers only to parser and provenance checks. Six Attention/MLP windows have real common-coverage gaps and null full-window means. The controller's original `FAIL` receipt is preserved separately.

CPU-only regression tests, including known PMBus raw codes and window-boundary bracketing, can be run with:

```bash
PYTHONPATH=0_Source/command_active_power/kv128_repeat_sevenrail/source/analysis_final python3 -m unittest test_kv128_sevenrail_analyze test_kv128_sevenrail_windows -v
```

`kv128_sevenrail_figures.py` renders the six indexed PNG/SVG figure pairs from the validated analysis JSON and the archived raw telemetry. The figures show raw points, time coverage and gaps, BUSY/host intervals, and BUSY-conditional point distributions; they do not estimate strict physical active power.
