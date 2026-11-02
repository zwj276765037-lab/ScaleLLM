# Double-buffer RTL evidence downloads

Download from the [GitHub evidence release](https://github.com/zwj276765037-lab/ScaleLLM/releases/tag/evidence-kv-overlap-20261102):

- [Raw evidence ZIP](https://github.com/zwj276765037-lab/ScaleLLM/releases/download/evidence-kv-overlap-20261102/ScaleLLM_KV128_DoubleBuffer_RTL_20261102.zip)
- [SHA-256 sidecar](https://github.com/zwj276765037-lab/ScaleLLM/releases/download/evidence-kv-overlap-20261102/ScaleLLM_KV128_DoubleBuffer_RTL_20261102.zip.sha256)
- [Offline verification receipt](https://github.com/zwj276765037-lab/ScaleLLM/releases/download/evidence-kv-overlap-20261102/ScaleLLM_KV128_DoubleBuffer_RTL_20261102.validation.json)

The ZIP is **52,735,101 bytes**, with **833 inventoried files**, plus its
`BUNDLE_MANIFEST.json` and `READ_ME.txt` container metadata. Its SHA-256 is:

```text
33a48f18163db8bbed4a9a34bead9206f8c4c77c55cc69c33a8cd6b37a61a3ad
```

The [machine-readable asset identity](release_asset.json) and
[member inventory](archive_members.json) are checked into the repository.
The release is supplementary evidence; it contains no replacement bitstream.

## Contents and selected runs

| Archive path | Contents |
| --- | --- |
| `0_Source/kv_overlap_validation/runs/fragment_candidate_continuous_001/` | Selected candidate raw events, coverage, group boundaries, KV image and manifest |
| `0_Source/kv_overlap_validation/runs/fragment_baseline_continuous_001/` | Selected sealed-reference records for the same input and testbench |
| `0_Source/kv_overlap_validation/runs/build_*` | Compiled source snapshots and build provenance; generated simulator caches excluded |
| `0_Source/kv_overlap_validation/results/` | Frozen comparison, summary/groups/prefixes CSVs and figures |
| `0_Source/kv_overlap_validation/provenance/` | Independent recalculation, source-integrity and execution receipts |
| `project/hardware/experiments/kv_overlap_validation/` | Independent candidate RTL, observation testbench and analysis/plot tools |
| `0_Source/operator_timing_kv32/kv128_compare/` | Selected real captured descriptor/input/RoPE/KV/output files and older complete sealed V32 events |
| `tools/release/` | Evidence packaging and portable verification scripts |

Earlier prototypes and unsuccessful attempts remain as historical evidence;
their inclusion does not make them accepted runs. Absolute paths in original
manifests identify the capture workspace; they are not public links.
Model weights, simulator executables/caches and private workstation files
are excluded. Weight identities remain recorded. The archive supports offline
verification; a fresh RTL replay additionally requires the matching model
assets and Vivado environment.

## Verify without Vivado or an FPGA

From a current repository checkout, with Python 3.11 or newer:

```bash
python3 tools/release/verify_kv_overlap_asset.py \
  --download outputs/ScaleLLM_KV128_DoubleBuffer_RTL_20261102.zip \
  --receipt outputs/kv_overlap_verification.json
```

The download destination must not already exist. For an existing download:

```bash
python3 tools/release/verify_kv_overlap_asset.py \
  --archive outputs/ScaleLLM_KV128_DoubleBuffer_RTL_20261102.zip
```

Verification checks ZIP/member hashes and CRCs, both compiled source closures,
640 append records and write ordering, reconstructed 8 MiB KV images, local
cycles/efficiencies, the V32 extrapolation and the earlier complete reference
V32 endpoint. It does not rerun RTL or board inference. See the checked-in
[PASS receipt](validation.json) and [method report](REPORT.md).

The earlier [board and released-RTL evidence](../kv128_chat16/DOWNLOADS.md)
remains independently downloadable. The double-buffer candidate's results
must not be substituted for those board measurements.
