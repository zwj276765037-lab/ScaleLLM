# Dense128 diagnostic for power/performance measurement

This separate bundle implements `mission/M006_mlp_linear_only_hardware/power_performance_plan_2026-10-25.md` section4 exactly. It is a periodic diagnostic with all128 groups active, not a real model or a guarantee of maximum switching or power. The vector author performed CPU preparation only. Actual Dell operations and measurement belong to the host engineer.

For `c'=column mod32`, group g, row r, lane k and matrix m:

```text
zp = 128
q-zp = (-1)^(k+r+g) * (1 + ((k+3r+g) mod7))
a_code = 17 + ((r+g) mod13)
a_shift = 14 + ((r+g) mod3)
w = (-1)^(k+c'+g+m) * (1 + ((3k+5c'+g+2m) mod7))
w_code = 19 + ((c'+3g+m) mod11)
w_shift = 14 + ((c'+g+m) mod3)
```

`generate_dense.py` evaluates exact signed integer dots/scales/guards for two matrices, 16rows and32base columns across128groups: 4,194,304 MAC per reference pass. It performs arithmetic right shifts into S37/F24, exact S44 group accumulation, one half-away shift8 at the end and asserts no S24 saturation. A32-column period is encoded in original tile16 G/U order and expanded448 times to the complete production files.

`verify_dense.py` independently checks every activation against the scalar contract formula, decodes every field/weight of the initial wire period and checks the formula, compares every byte of all448 weight/metadata/gold periods, and checks padding/reserved/canonical rules. A separate decoded-wire integer pass uses floor division and final quotient/remainder rounding, then compares all1,024base outputs; verified repetition covers all458,752physical outputs. Another72scalar samples explicitly compute all128groups at row/half/tile/tail boundaries, including column14335. No DUT outputs enter any gold computation.

Preparation passed. All65,536 activation differences,2,048 activation codes,117,440,512 S4 weights and3,670,016 weight codes are nonzero. All458,752 output values are nonzero, with229,376positive and229,376negative; range[-3935,3942], no saturation. Actual total shifts cover28..32. Every matrix/half has114,688nonzero results; tail32columns have1,024nonzero results. Full sizes/hashes/literals and source identities are in the bundle's `manifest.json`, `verification.json` and `delivery.json`.

The bundle is `project/E013_mlp_linear_only_hardware/experiment_results/board_validation/diagnostic_gu/dense_active_128_v1`. Its manifest kind is `scalellm_gu_dense_active128_diagnostic_v1`, explicitly `diagnostic_only=true`. Names/sizes match the existing GU transport: two29,360,128B weight halves,7,340,032B metadata,73,728B REC576 and1,376,256B gold. Gold SHA256 is `8d67b8ddd9df84a1e5d72d77b466e1946f4e05d2839302f9680ec6cf8892f48d`.

`dense.DenseArtifacts(bundle)` provides `original.layer_artifact(0,name)` and records with `path/size/sha256/read_verified`, rejecting other layers/Down and invalid identity. It never calls or relaxes the production model loader. `run_dense_gu.py` is an independent copy of the old diagnostic driver with only the new provider/verifier/statistics key and distinct scope, leaving the old runner unchanged. It runs the unchanged production backend, preserves output/DONE/comparison before ACK and defaults to two cohorts and normal release.

After actual host preflight has passed, run locally with modern Python (B and R are absolute board_validation source/results directories):

```bash
PYTHONPATH="$B" python3 "$B/diagnostic_gu/dense_active_128/run_dense_gu.py" --bundle "$R/diagnostic_gu/dense_active_128_v1" --result "$R/<new-dense-correctness-attempt>" --session-factory scalellm_windows_xdma:create_session --cohorts 2 --epoch <fresh-nonzero-epoch> --command-base <fresh-command-id>
```

The factory is the host-owned context manager with CSR/local-DMA methods. The runner supports the same10s backend waits and1MiB I/O chunks; the transport owns cancellable I/O timeouts. The host measurement adapter owns subsequent resident-epoch rebinding, fresh command/buffer generations, native loop and telemetry; this package does not implement measurement or infer power from activity. Separate per-command gold checks/ACKs remain required.

To reproduce into a fresh directory:

```bash
python3 <this-directory>/generate_dense.py --out <new-bundle-directory>
python3 <this-directory>/verify_dense.py <bundle-directory> --out <new-verification-json>
```

`check_runner.py` passed one two-cohort CPU fixture with injected gold/DONE, checking new provider integration, persistence before ACK and final release; it is not device evidence. Original structured/S37 source and binary manifests are unchanged and their source hashes were checked against the prior delivery report. The new manifest preserves generator-time code identities; `delivery.json` separately freezes the final runtime source identities and labels that version boundary. No shared summary/index/RTL/ABI/backend was edited.
