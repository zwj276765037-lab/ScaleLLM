# GU-only production-shape diagnostic protocol

M006/E013 board preparation, 2026-10-25. The author owns only this source directory and `experiment_results/board_validation/diagnostic_gu/`. Existing RTL, ABI, backend, production catalog validation and frozen evidence are unchanged. Dell/JTAG/PCIe operations belong solely to the host engineer. This author ran CPU preparation only.

The target is the engineering bit with SHA256 `66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47`, GU ABI v7/caps `0x1d`, 16 rows, K4096, 128 groups and Gate/Up each N14336. Max-DPO and external-reset signoff remain open. Actual device readiness is a prerequisite for using the runner; generated inputs cannot qualify a device that reads all ones.

The numerical authority is [mlp_fixed.py](../../../../../hardware/model/mlp_fixed.py), `mlp_recover_guard_s37()` and `round_shift_away_zero()`, together with the [GU design](../../../../../../PRO_plan/ScaleLLM_MLP_Gate_Up_Only_Dual_DDR_Design.md) and [v7 ABI](../../../../../hardware/source/mlp_linear/abi_gu_only.json). For every row/column/group, compute `dot=sum32((q-zp)*w_s4)` in S17, `raw=dot*a_code*w_code` in S33, align to F24 by a left shift or signed arithmetic right shift using total shift 20..44, and check S37. Accumulate all 128 groups in S44. Apply half-away-from-zero shift8 exactly once, then saturate to S24. Zero codes have canonical zero data/shift/zero-point. No DUT output is used to generate or adjust gold.

The weight byte authority is [the original exporter](../../../../../software/model/export_scalellm_llama31_artifacts.py), `_write_mlp_tile()`, `pack_w4()` and `pack_mlp_meta()`. Record index is `(2*tile16+matrix)*128+group`, where matrix0=Gate and matrix1=Up. Each logical half stores eight output columns per tile, 32 low-nibble-first S4 weights per column, 128 B per record. Metadata stores 16 U8 codes, 16 six-bit shifts, then four zero bytes, 32 B per record. Both logical halves reside on physical DDR1. An additional bounded audit directly calls the original exporter for all 128 groups of tiles0/1/447/448/894/895 and both matrices and compares the emitted bytes.

Every bundle contains two 29,360,128 B weight files, 7,340,032 B metadata, 73,728 B input REC576 and 1,376,256 B interleaved GU gold. It is explicitly marked `diagnostic_only=true`, not a model or 32-layer catalog. `DiagnosticArtifacts.original.layer_artifact(0,name)` returns immutable hash/size-verified records, satisfying the unchanged backend interface for GU-only artifacts. Other layers and Down artifacts are rejected.

The `structured` case uses groups0/1/126/127. All 896 tiles, 16 rows, two matrices and both logical halves have nonzero results. Group0 carries row/lane/column/matrix markers and total shift20; group1 covers shift25, with columns0/1 isolated exact +0.5/-0.5 ties at shift24; group126 gives deliberate positive/negative S24 saturation at columns7/8; group127 covers shift44 and signed right shift. Column14335 remains a nonsaturated marker. The sparse active groups avoid a full dense GEMM.

The `s37_cancellation` supplement uses groups0..14 for 8 groups of w=+7 and 7 groups of w=-8, all q-zp=255 and both codes255 at total shift20. Their exact sum is zero. Group15 and group127 add small signed, row/column/matrix-dependent values at shift24. Individual guards are outside S36 but fit S37; the final outputs do not saturate. A hypothetical S36-truncated guard produces different outputs, including the recorded first witness. This supplements the structured case and is not needed to start the first numerical command.

`generate.py` computes source gold before packing. `verify.py` independently decodes all weight, metadata and REC576 wire data, recomputes every output using multiplication/floor division, and checks 120 separate Python-integer scalar coordinates. It also audits every inactive group and all padding/canonical fields, and cross-checks the existing REC576/output codecs. `selfcheck_runner.py` injects explicit CPU fixture outputs/DONE solely to test driver ordering and failure preservation; those results are not board or RTL evidence.

From the project root, reproduce a fresh bundle without overwriting evidence:

```bash
python3 project/E013_mlp_linear_only_hardware/experiment_source/gu_only/board_validation/diagnostic_gu/generate.py --out <new-structured-directory> --case structured
python3 project/E013_mlp_linear_only_hardware/experiment_source/gu_only/board_validation/diagnostic_gu/verify.py <bundle-directory> --out <new-verification-json>
```

After the host engineer has passed actual CSR/readiness/scratch preflight, this is the single-command entry (replace `B` and `R` with absolute paths, choose a fresh attempt directory):

```bash
PYTHONPATH="$B" python3 "$B/diagnostic_gu/run_gu.py" --bundle "$R/diagnostic_gu/structured_v1" --result "$R/<new-actual-GU-attempt>" --session-factory scalellm_windows_xdma:create_session --cohorts 1
```

`B` is `project/E013_mlp_linear_only_hardware/experiment_source/gu_only/board_validation`; `R` is `project/E013_mlp_linear_only_hardware/experiment_results/board_validation`. The factory returns a context manager; its entered object supplies `read32/write32/h2c_write_local/c2h_read_local`. The current host engineer runs the modern Python backend locally and uses a persistent Windows RPC session. The runner uses 1 MiB transfer chunks, backend metadata/GU timeout10s, and the transport must supply its own cancellable I/O deadline. Closing transport does not reset hardware. No device is discovered or programmed by this package.

The first command uses layer0/cohort0/buffer0 and command/request/epoch1 unless explicitly set. `--cohorts 2` adds cohort1/buffer3 in the same staged epoch and releases the layer only after both ACKs. For one cohort the existing backend intentionally retains its layer lease; the driver does not call the two-cohort release API. Fresh attempt IDs/epochs must be selected consistently with the actual board state. Do not create a second backend to bypass an outstanding lease or failure.

Before ACK, the runner persists the complete output, every DONE/status snapshot and the full byte/value comparison, including the first mismatched matrix/row/column and S24 values. On numerical mismatch it preserves DONE/pending/lease and submits no later cohort. On transport/backend failure it records diagnostics and does not reset or retry commands automatically. The host engineer owns real driver/device/bit identities and raw remote logs. Only actual successful execution can support a GU board-local numerical claim; it cannot establish full-model accuracy, 32-layer execution, Host Down performance or physical/reset signoff.
