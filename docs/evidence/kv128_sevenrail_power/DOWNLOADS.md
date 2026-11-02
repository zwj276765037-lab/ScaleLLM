# Download the seven-rail power evidence

[Release page](https://github.com/zwj276765037-lab/ScaleLLM/releases/tag/evidence-kv128-sevenrail-20261102) · [Complete ZIP (56,091,268 bytes)](https://github.com/zwj276765037-lab/ScaleLLM/releases/download/evidence-kv128-sevenrail-20261102/ScaleLLM_KV128_SevenRail_PMBus_20261102.zip) · [SHA-256 sidecar](https://github.com/zwj276765037-lab/ScaleLLM/releases/download/evidence-kv128-sevenrail-20261102/ScaleLLM_KV128_SevenRail_PMBus_20261102.zip.sha256) · [Validation receipt](https://github.com/zwj276765037-lab/ScaleLLM/releases/download/evidence-kv128-sevenrail-20261102/ScaleLLM_KV128_SevenRail_PMBus_20261102.validation.json)

```text
d2ef53b5e14e940bc1277b9c079e517631920bc46f032212cd1495a9fcdfedb2  ScaleLLM_KV128_SevenRail_PMBus_20261102.zip
```

The original archive is unchanged from the local measurement delivery. It contains **229 members** (228 content files plus the manifest), approximately 983 MB uncompressed. All 16 formal-run native files are retained, along with pilot/smoke, failed attempts, configuration/source identities and final numerical outputs. Original FAIL/unknown-exit states are not replaced by the verifier's PASS, which means integrity and numerical recomputation only.

## Archive files

All members are under `kv128_repeat_sevenrail/`; the [complete package manifest](PACKAGE_MANIFEST.json) lists names, byte counts, SHA-256 values and explicit exclusions.

| Archive path under that prefix | Contents |
| --- | --- |
| `REPORT.md`, `PACKAGE.md` | Original complete report, scope and standalone extraction/reproduction instructions |
| `native/main_004/telemetry.jsonl` | Every supported V/I/P read's original bytes, QPC start/end, rail points and sweep records |
| `native/main_004/commands.jsonl` | START, status/BUSY observations, DONE, output/ACK events |
| `native/main_004/workload/` | Twelve window boundaries, command summaries, XDMA records, token and recovery checks |
| `native/probe_001/`, `native/smoke_001/`, `native/main_001..003/` | Pilot, short format check and original failed attempts; not added to the formal repeats |
| `results/main_004_raw_points_v2.csv` | All raw register words and separate V/I/P read envelopes in CSV |
| `results/main_004_analysis_v2.json` | Complete per-window, per-rail, command/BUSY and sensitivity analysis |
| `results/main_004_v2_*.png/.svg` | Six figure pairs: repeats, seven rails, V×I/POUT, common coverage, BUSY/host gaps and conditional points |
| `source/main_004/` | Frozen actual-run measurement/workload scripts; external runtime/model dependencies are not included |
| `source/analysis_final/` | Frozen offline analysis, plotting and focused regression tests |
| `source/references/` | Official-source audit and independent full-data recomputation |
| `provenance/` | Transfer identities, deployment receipts, failures and analysis SHA identities |

The 256 MiB `kv_snapshot.bin` remains in the original local evidence store and is **not in this archive**. Its hash/inspection and restore checks are retained. Superseded derived analyses and Python caches are also excluded. This does not remove any formal power raw log. Local absolute paths inside original provenance identify historical sources, not public download URLs; public Markdown links have been adapted and recorded in [PUBLICATION_MANIFEST.json](PUBLICATION_MANIFEST.json).

## Verify or reproduce

```bash
# Download without authentication, verify all members, recompute all windows.
python3 tools/release/verify_power_repeat_asset.py \
  --download outputs/ScaleLLM_KV128_SevenRail_PMBus_20261102.zip --recompute

# Use an existing downloaded file instead.
python3 tools/release/verify_power_repeat_asset.py \
  --archive outputs/ScaleLLM_KV128_SevenRail_PMBus_20261102.zip --recompute
```

The recomputed analysis SHA-256 must be `a00d62ac8031a1c3dd2b642f0804323c87429f5383106b5c48a2c57ff07f4bf7`. Python 3.11+ standard library suffices. After standalone extraction, use the directory-relative commands in `kv128_repeat_sevenrail/PACKAGE.md`; the frozen source README also gives the original repository-relative entry. [Publisher verification](validation.json).
