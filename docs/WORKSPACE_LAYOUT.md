# Public project layout

The repository contains the current 80 MHz Decode16 design and its portable deployment/build entries. Historical experiments remain in Git history and the `prefill` branch.

| Path | Purpose |
| --- | --- |
| `bitstream/` | Exact board-tested image, SHA-256 and artifact identity |
| `deploy/scalellm.py`, `deploy/final/` | Public inference CLI and guarded hardware builder |
| `deploy/export_model.py` | Export your licensed checkpoint to the required numerical layouts |
| `deploy/driver/` | Driver preparation patch, observed source hashes and instructions |
| `deploy/vendor/runtime/` | Small frozen transport/math/resource dependencies |
| `project/hardware/rtl/` | Current Attention, MLP and board integration RTL |
| `project/hardware/vivado/` | Portable scripts, constraints and recursive source manifests |
| `project/hardware/{host,model}/` | ABI, runtime, model export and numerical helpers |
| `project/hardware/{data,tb,tests}/` | ROMs and focused transport/build checks |
| `examples/` | Editable text prompts and exact measured token-ID requests |
| `docs/evidence/final/` | Resource/timing excerpts and portable-entry validation |
| `docs/evidence/inference_chat16/` | Original generation outputs, receipts and FPGA counters |
| `docs/evidence/power_chat16/` | Historical seven-rail telemetry over the full 16×32 wall-clock window; not whole-board or strict command-active power |
| `docs/evidence/kv128_chat16/` | Fixed-active16 real KV128 history, 1,784 tokens, 8,192 command counters, captured tensors and VCCINT conditional telemetry |
| `docs/evidence/kv32_kv128_cycle_sim/` | Sealed-RTL command replays, 12 selected commands, 52 valid stage results, matched KV32/KV128 tables and evidence downloads |
| `tools/` | Reproducible measurement analysis and release packaging |
| `tests/` | CPU runtime, deployment and release-integrity tests |

`.gitattributes` preserves file bytes across Linux and Windows checkouts so newline conversion cannot invalidate the recorded identities.

The three inference/power evidence generations have different scopes. The
original requests stop after 32 new tokens each and retire independently; the
KV128 benchmark keeps sixteen requests active through position 127. The cycle
comparison uses selected captured commands and a declared AXI service model;
it is not another full-model board run or a new FPGA build. Its 384-row coverage
table retains 332 unmeasured stage rows as empty values, and its complete
five-projection-plus-core coverage is layer 0 only. See
[performance and resources](PERFORMANCE_AND_RESOURCES.md) and
[power measurement](POWER_MEASUREMENT.md) before comparing quantities across
these directories. Frozen raw records keep their original failures and unknown
exit codes; later explanations do not rewrite those records.

`RELEASE_MANIFEST.json` records every distributed file's size and SHA-256. The package tool separately pins the exact accepted bitstream, checks frozen runtime/build dependencies and rejects omitted inputs. `deploy/release_files.json` is the explicit file selection; packaging does not traverse model weights or build workspaces.

```bash
python3 tools/package_release.py verify
python3 tools/package_release.py build --output dist/ScaleLLM_Final_Decode16_80MHz
python3 tools/package_release.py verify dist/ScaleLLM_Final_Decode16_80MHz
```

The archive uses sorted paths and normalized timestamps/ownership. Extract it anywhere and run `python3 tools/package_release.py verify` from its root. Package building requires only Python's standard library and does not open a board or run Vivado.

Maintainers deliberately refresh the integrity manifest after reviewing source changes with `python3 tools/package_release.py seal`. A changed runtime/build source also requires its own source manifest to be reviewed and updated. Local `build/`, `dist/`, `outputs/`, `runs/`, `models/`, `artifacts/`, virtual environments and caches are excluded from verification's public-file scan. Other unlisted files cause verification to fail.
