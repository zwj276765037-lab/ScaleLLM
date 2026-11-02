# Experiment index and current evidence

Updated 2026-11-02 (Asia/Shanghai). The newest evidence is an independent double-buffer RTL validation acquired on 2026-11-02 UTC. Earlier board and sealed-RTL comparisons retain their 2026-11-01 UTC identities. Publication does not constitute a hardware build.

Board results and sealed baselines refer to the released VCU118/XCVU9P Decode16 implementation, core 80 MHz, DDR user interface 200 MHz and Vivado 2025.2. The explicitly identified double-buffer candidate changes an independent RTL copy's buffering/scheduling only and has not been synthesized or deployed. Release bitstream SHA-256:

```text
96df1a5c1bf4174921bc02ccd88df4066dece3d62b491acb3106bb90ac0ffc85
```

## Current results

| Evidence | Workload and coverage | What it establishes | Entry |
| --- | --- | --- | --- |
| Independent continuous double-buffer candidate | Layer 0, KV128, active16; K32 and V8 groups | 640 KV records and full 8 MiB image byte-exact; K32 efficiency 59.863%; V32 estimated 72.676% from V8; no complete Attention or board-speed claim | [Report and limits](evidence/kv_overlap_cycle_sim/REPORT.md), [raw evidence and CSV](evidence/kv_overlap_cycle_sim/README.md) |
| Actual board inference | Llama-3.1-8B-Instruct; 16 active requests; 128 executed steps; position 127 completed with committed positions 0–126 | 8,192 completed commands, 1,784 generated tokens, board command counters and host–FPGA wall time | [Board report](evidence/kv128_chat16/README.md), [commands](evidence/kv128_chat16/results/commands.csv), [tokens](evidence/kv128_chat16/results/tokens.json) |
| KV32/KV128 cycle comparison | Each KV: Attention layers 0/8/16/24/31 and Gate/Up layer 0; 12 complete command results, 52 stages | Real-input replay of frozen RTL; complete output byte agreement; stage time and effective shared-weight efficiency under the documented DDR model | [Simulation index](evidence/kv32_kv128_cycle_sim/README.md), [complete report](evidence/kv32_kv128_cycle_sim/REPORT.md) |
| VCCINT telemetry during the two target steps | 41 qualifying V/I pairs at KV32, 97 at KV128; pair transaction envelopes contained in command BUSY inner windows | Conditional sequential regulator-output telemetry, with sample and command coverage | [Power interpretation](POWER_MEASUREMENT.md), [raw/derived power index](evidence/kv128_chat16/README.md#what-the-power-data-measures) |
| Placed resources and routed timing | Released hardware build, preserved report stage and tool identity | Hardware implementation evidence; unchanged by these experiments | [Resources and performance](PERFORMANCE_AND_RESOURCES.md), [physical closure](PHYSICAL_CLOSURE.md) |

The board run retains 16 active slots until position 127, with fixed generation budgets of 110–113 tokens per request. No EOS occurred in the recorded trajectories. The 128 executed steps include prompt processing; they do not mean 128 newly generated tokens per request. All target-step host Down, LM-head, token and KV commits completed.

## Timing boundaries

For the new candidate, K/V timing is first actual group dispatch to final original KV append acceptance. K32 is 43,791 cycles versus 75,911 sealed cycles. V8 is 9,790 versus 17,046 cycles; candidate V32 is estimated at 36,070, compared with the prior complete sealed V32 replay's 68,206 cycles. The last AXI write response is five cycles later and separate. These are local windows within **one layer**; 32 groups do not mean 32 model layers.

The original quantizer and DDR model are retained. V32's 35,974–36,142-cycle interval is model sensitivity, not a confidence interval. K8 predicts actual K32 within 94 cycles (0.215%). Startup/tail amortization is evaluated using same-run prefixes, not by proportionally rescaling command time. See the [candidate method](evidence/kv_overlap_cycle_sim/REPORT.md).

| Quantity | KV32 target step | KV128 target step | Interpretation |
| --- | ---: | ---: | --- |
| FPGA command time, 64 commands | 1.2325575375 s | 2.0268963625 s | Sum of `DONE_CYCLES / 80 MHz`; excludes host work and transfers outside commands |
| Complete recorded host–FPGA step | 71.312 s | 97.453 s | Includes host processing, transfers and inside-step observation overhead |
| Aggregate step throughput, 16 emitted tokens | 0.2243662 token/s | 0.1641817 token/s | Uses complete step wall time |
| Simulated Attention-core span, each of five validated layers | 7.277750 ms | 26.938550 ms | First KV data-AXI request to final PV acceptance, including overlap and waits once |

Across the whole run, 1,784 generated tokens divided by the defined 9,843.491879 s model window give 0.1812365 token/s. The window begins before asset loading and ends after the final complete step returns; exact boundaries are in the board report. Capture overhead was not separately measured and has not been subtracted.

The simulation's core and DDR domains use one ps timeline within each replay. Commands reset independently, so their absolute timestamps do not form one continuous model execution. Its DDR service model excludes real MIG/SmartConnect, DRAM bank/refresh and host-XDMA timing. Board-versus-simulation whole-command differences are retained without scaling individual stages.

Projection groups include their prescribed postprocessing: Q+RoPE, K+RoPE+KV quantization, V+KV quantization, O through the final linear result, and Gate/Up+SiLU×Up. Preparation and inter-operator dependencies are separate. The first-weight-request service window is also preserved and can overlap other groups. Neither choosing only busy subintervals nor allocating command time by weight size is used.

Shared weight payloads are Q/K/V/O/GateUp = 16/4/4/16/56 MiB per layer, counted once for all 16 requests. Efficiency is `ΣD / (12.8e9 × ΣT_seconds)` per corresponding physical DDR channel. It is an effective-payload/window metric, not measured DDR handshake utilization. Attention-core efficiency is undefined; only its time is reported. The full 32-layer index has 384 rows across the two KV settings, with 52 validated and 332 unmeasured rows left empty.

## Historical datasets retained separately

| Dataset | Original scope | How to use it |
| --- | --- | --- |
| [Earlier inference](evidence/inference_chat16/) | 16 requests, 32 generated tokens each; 50 execution rounds with request retirement | Use its own active-request and KV history. It is not the fixed-active16 KV128 experiment. |
| [Earlier power experiment](evidence/power_chat16/README.md) | Seven FPGA-related regulator output rails across a full model wall-clock window | The historical 11.3648243 W and 39.13065 kJ include host-compute and idle gaps. They are neither all board-input rails nor command-active average power/energy. |
| [Build and physical evidence](evidence/final/) | Original create/compile/placement/routing and verification records | Retain each report's device, tool and Design State. This publication does not change the implementation or certify a new rebuild. |

Historical raw files and archived summaries are retained byte for byte. Current interpretation and documented corrections take precedence over stale descriptive fields inside those originals; in particular, the MAX20751 VID voltage decoding correction is explained in [POWER_MEASUREMENT.md](POWER_MEASUREMENT.md).

## Downloads, provenance and limits

The [double-buffer release](https://github.com/zwj276765037-lab/ScaleLLM/releases/tag/evidence-kv-overlap-20261102) adds an independently hashed archive of candidate/baseline events, KV images, captured inputs and source snapshots. Its [portable verifier](../tools/release/verify_kv_overlap_asset.py) checks every member and recomputes local comparisons without running RTL. Candidate V32, complete Attention, other layers, physical resources/timing and board/full-model gains remain unmeasured.

The [combined evidence release](https://github.com/zwj276765037-lab/ScaleLLM/releases/tag/evidence-kv32-kv128-20261102) contains the unchanged 781,288,611-byte archive, its SHA-256 file and an external extraction/recomputation receipt. Archive SHA-256:

```text
bdd7c7281dace4d26604918da4801bb02e0d8eaf0a0781ab75d7896361b9b38b
```

The 980 archived files include board raw evidence, real captures, simulation phase/event logs, full command outputs, analysis tools and the original methods/coverage receipts. Extraction verification recomputed 24 phase-derived tables and eight final simulation CSVs, checked all 12 command outputs and verified the 116 original board-transfer files. The board-only archive and its 196-file package remain available from [the earlier board download page](evidence/kv128_chat16/DOWNLOADS.md). Large archives are Release attachments; the current report, CSVs, figures and indexes remain readable in `docs/evidence/`.

The source archive retains original paths and run identities for traceability. Public reports provide repository-relative links and archive-member indexes; absolute local paths inside frozen raw provenance are not public download links. Downloading the evidence does not include a runnable copy of every model/build dependency. Offline verification requires Python; rerunning RTL requires the existing project assets and Vivado.

The optional single-active-request attempt failed before issuing commands and is not a measured result. Same-RTL byte agreement and consistency with the recorded LM-head predictions do not establish an independent full-model numerical oracle. PMBus does not establish strict command-active mean power, whole-board input power, activity energy or J/token; these quantities remain unmeasured.
