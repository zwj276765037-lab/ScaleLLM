# KV128 board measurements — 2026-11-01

This is the completed **board-measurement** release for ScaleLLM on VCU118/XCVU9P, Decode16, core 80 MHz, DDR user interface 200 MHz, and the Vivado 2025.2 release. It contains the actual inference outputs, command counters, host timing, captured tensors/KV, PMBus transactions, and the original completion and failure records. Operator-level cycle simulations are a separate experiment and are not included in this release.

## Fixed hardware and workload

Bitstream SHA-256:

```text
96df1a5c1bf4174921bc02ccd88df4066dece3d62b491acb3106bb90ac0ffc85
```

The current bitstream and production RTL were retained; no synthesis, implementation, programming or hardware reset was performed for this measurement. Identity is supported by the release-file hash, runtime/CSR checks and recorded boot identity; independent configuration-memory bitstream readback was not performed.

- Model: Llama-3.1-8B-Instruct, the existing ScaleCode/KV12 numerical configuration.
- Sixteen original requests remain active through position 127. Positions 0–126 are produced by actual preceding inference and committed per layer/request; they are not synthetic KV padding.
- The complete run has **128 steps, 8,192 FPGA commands, and 1,784 generated tokens**. All 16 slots end at logical position 128.
- Prompt lengths: `19,18,17,18,16,17,19,18,17,16,17,19,18,17,17,17`. Each request generates 110–113 tokens, totaling 1,784.
- EOS retirement was disabled for this fixed-length measurement. The recorded trajectories actually contain **zero EOS occurrences**. This is not the earlier 16 requests × 32 generated tokens experiment, and 128 steps does not mean 128 generated tokens per request.
- KV32/position31 and KV128/position127 are two positions of the same real inference run. Hidden states, scales and KV contents also differ; this is not a controlled experiment changing only KV length.

## Measured speed

| Target step; 16 active requests, all 32 layers | KV32 / position31 | KV128 / position127 |
| --- | ---: | ---: |
| Attention DONE_CYCLES, sum of 32 commands | 51,663,975 | 115,212,977 |
| MLP DONE_CYCLES, sum of 32 commands | 46,940,628 | 46,938,732 |
| All 64 commands, cycles | 98,604,603 | 162,151,709 |
| FPGA command time, cycles / 80 MHz | 1.2325575375 s | 2.0268963625 s |
| Complete measured step wall time | 71.312 s | 97.453 s |
| Actual tokens emitted in this step | 16 | 16 |
| Aggregate step throughput | 0.2243662 token/s | 0.1641817 token/s |

The complete model timing window is **9,843.491879 s**, giving **0.1812365 generated token/s aggregated over all 16 requests**. The launcher window is 9,851.671488 s. The sum of steps that emitted at least one token is 8,835.490 s; its 0.2019130 token/s excludes pure-prefill steps and inter-step work, and includes early mixed prefill/decode steps.

The `model_wall_s` interval starts after source/request/driver preflight and result-directory creation, before asset loading/hash checks, tokenizer, device open, allocation and resident load. It ends just after the final `runtime.step()` returns, before final text decoding, quiescence checks, device close and final save. It includes runtime instrumentation/capture. `step_wall_s` encloses the whole step: 32 layer preparations, 64 FPGA commands, DMA, CPU Down, LM head and token commit. The launcher interval additionally covers its identity/lease checks and cleanup, but excludes later inventory/transfer. Exact definitions are retained in [`summary.json → speed_scope`](results/summary.json).

The final step includes measured host layer preparation of 16.607 s, CPU Down of 43.060 s, and LM head of 0.719 s. Total capture overhead was not separately established and remains null. No residual time is assigned to an unmeasured category or subtracted to claim a faster result.

FPGA command time excludes work outside hardware commands. For example, 16 / 2.0268963625 = 7.8938422 token/s is only a **command-time-normalized quantity**, not measured complete-model throughput. Register count C and the accept-to-result edge envelope C+1 are retained separately.

## Actual tokens and correctness

- [All prompts and generated text](results/outputs.txt).
- [Exact token IDs, per-request counts, first-token latency and EOS records](results/tokens.json).
- [All 8,192 command records](results/commands.csv); filter `common_kv` to 32 or 128 for the two 64-command target steps.
- [Captured-payload checks](results/capture_verification.json): 12 complete target command captures, Attention at layers 0/8/16/24/31 and Gate/Up at layer 0, at both KV lengths. Other commands have counters/runtime traces; this is not a claim that all 8,192 tensor outputs were separately dumped.

Checks passed for command order, descriptors, active masks, position/epoch history, transfer lengths, completion/error/ACK protocol, 128 full LM-head/token-commit steps, final quiescence and closed inference handles. Emitted token IDs agree with the actual recorded LM-head top-1 predictions. An **independent full-model numerical oracle is not established**; readable text or agreement with a captured prediction does not establish that oracle.

## What the power data measures

Only the verified **VCCINT regulator output** is measured here through PMBus. Each sample is the product of sequential `READ_VOUT` and `READ_IOUT` transactions. Eligible observations require the entire V/I read-pair envelope to lie inside the same command's conservative BUSY window.

| KV | Command | Eligible V/I pairs | Commands with observations | V×I median | Observed range |
| --- | --- | ---: | ---: | ---: | ---: |
| 32 | Attention | 24 | 24/32 | 5.7375 W | 5.525–8.925 W |
| 32 | MLP | 17 | 17/32 | 5.5250 W | 5.525–11.050 W |
| 128 | Attention | 87 | 32/32 | 5.5250 W | 5.525–8.925 W |
| 128 | MLP | 10 | 10/32 | 5.5250 W | 5.525–5.525 W |

There are 27,953 raw V/I pairs in the KV32 collection and 30,547 in KV128; 41 and 97 qualify, respectively. These cover 41/64 and 42/64 target commands. All raw transactions, rejected pairs, timestamps, command associations and raw register words are preserved. A V/I read pair takes about 10.6 ms at the median. The sensor's physical measurement aperture/update lag and absolute accuracy have not been established.

READ_POUT returned codes spaced by **2 W** (including 6/8/10/12 W). The observed VOUT is 0.85 V; the IOUT code step is 0.5 A, giving a **0.425 W V×I code step**. Decimal arithmetic does not improve the sensor's physical precision. In KV128, 87 of 97 eligible pairs equal 5.525 W; repeated values do not demonstrate constant execution power.

These are **BUSY-contained telemetry observations**, not strict execution-period mean power. Samples are not time-integrated, coverage is unequal, the measurements are sequential rather than randomized repeats, and temperature was not an independently controlled variable. Do not interpret a lower median as evidence that KV128 consumes less power. Whole-board input power, seven-rail totals, strict active mean, active energy and J/token remain **NOT_ESTABLISHED/null**.

![VCCINT conditional observations; IQR describes samples, not measurement accuracy](results/vccint_kv32_kv128_conditional.png)

[SVG figure](results/vccint_kv32_kv128_conditional.svg) · [Power summary](results/power_summary.json) · [KV32 sample CSV](results/power_kv32.csv) · [KV128 sample CSV](results/power_kv128.csv)

## Download, verify and recompute

Download the complete archive from [DOWNLOADS.md](DOWNLOADS.md); its parts and hashes are described by [`package.json`](package.json). All archive parts are committed to `main`; no Git LFS client is required. The helper automatically assembles parts when necessary, verifies their SHA-256, verifies the archive and every extracted file, and rejects an existing nonempty output directory.

From the repository root, with Python 3.10 or newer:

```bash
python3 tools/kv128_board_release.py --output outputs/kv128_board --recompute
```

The recomputation is offline and uses only Python's standard library. It does not access the FPGA or re-run inference. It independently rechecks the original 116-file Dell inventory (**790,194,966 bytes**), recomputes command, commit, token, capture and VCCINT results, and compares 11 derived outputs against the release. JSON comparisons ignore object-key order only; array order, values and types remain significant. The extracted `verification.json` records the result. The committed [`validation.json`](validation.json) is the actual publisher-side unpack/recompute receipt.

The archive contains all files under the completed board experiment, including raw `native/run_002/`, the earlier read-only `run_001/`, derived results, capture/launcher snapshots, requests, original receipts and local provenance. The [file manifest](MANIFEST.json) gives each archive member's size and SHA-256. Analysis/transfer/power-plot scripts and relevant provenance are included; regenerate the plot with its archived script and Matplotlib/NumPy if needed. Online `results/` files are copies of the final archived results; preliminary results remain only in the archive and are labelled as such.

## Preserved failures and limitations

- The first main attempt only completed read-only identity checks and issued no inference command. The second main attempt is the complete 128-step run.
- The launcher's last polling field still says 127 committed rounds; the final model records, 128 commit events and command chain prove 128 complete steps. The original field is not rewritten.
- The outer main SSH session returned 255. Its exact exit time/cause and an independent SSH log are unavailable; the remote completion chain and transferred-file integrity are independent evidence of completion, not a fabricated remote-shell exit code.
- Both sampler receipts retain `SAMPLING`/`exit_code=null`. Complete raw data and independent PID/birth-time observations establish that the collectors exited. Their status is `RAW_COMPLETE_EXIT_CODE_UNKNOWN`, not a claimed normal process exit.
- The optional active1 branch failed before issuing any command. Its 550.726 s attempt remained within its 600 s limit; seven failure files (3,511 bytes), process-exit observations and lease release are retained. A reserved Windows `aux.stop` name failed during stopping; the initial pre-command stall was not independently localized. No active1 speed, power or simulation result is claimed.

This dataset supplements the [earlier 16×32-token experiment](../inference_chat16/outputs.txt); it does not replace its raw records or turn its different power scope into a current measurement.
