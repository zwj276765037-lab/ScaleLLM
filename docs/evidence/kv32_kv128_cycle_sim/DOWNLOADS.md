# Complete raw evidence archive

The [GitHub Release](https://github.com/zwj276765037-lab/ScaleLLM/releases/tag/evidence-kv32-kv128-20261102) carries the frozen full evidence package:

- [Cycle-simulation ZIP](https://github.com/zwj276765037-lab/ScaleLLM/releases/download/evidence-kv32-kv128-20261102/ScaleLLM_KV128_KV32_Decode16_80MHz_20261101.zip) — 781,288,611 bytes; SHA-256 `bdd7c7281dace4d26604918da4801bb02e0d8eaf0a0781ab75d7896361b9b38b`.
- [SHA-256 sidecar](https://github.com/zwj276765037-lab/ScaleLLM/releases/download/evidence-kv32-kv128-20261102/ScaleLLM_KV128_KV32_Decode16_80MHz_20261101.zip.sha256).
- [Original extraction/recomputation receipt](https://github.com/zwj276765037-lab/ScaleLLM/releases/download/evidence-kv32-kv128-20261102/ScaleLLM_KV128_KV32_Decode16_80MHz_20261101.validation.json): 980 archived files verified, 12 outputs byte-exact, original phase/CSV results recomputed.

From the repository root, use the [lightweight downloader/verifier](../../../tools/release/verify_cycle_sim_asset.py):

```sh
python3 tools/release/verify_cycle_sim_asset.py \
  --url https://github.com/zwj276765037-lab/ScaleLLM/releases/download/evidence-kv32-kv128-20261102/ScaleLLM_KV128_KV32_Decode16_80MHz_20261101.zip \
  --output ScaleLLM_KV128_KV32_Decode16_80MHz_20261101.zip
```

It checks the frozen size and SHA-256, archive inventory, and selected coverage. Add `--full` to stream-check every archived member's SHA-256 and CRC. If the ZIP is already present, use `--asset path/to/file.zip --full` instead of `--url/--output`. The expected asset identity and stable URL are also [machine-readable](release_asset.json).

For complete **offline analysis recomputation** after extraction, run `python3 tools/operator_timing/cycle_compare_bundle.py verify --folder .` from the extracted archive root. That reads the archived originals and rechecks the selected command outputs, board transfer, phase analyses, and publication CSVs; it does not run the FPGA or XSim. Allow over 10 GB of free space for the extracted raw evidence. The [raw-log index](raw_logs_index.json) lists the exact ZIP member and SHA-256 for every selected command.
