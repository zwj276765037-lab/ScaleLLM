<div align="center">

# ScaleLLM

**Llama-3.1-8B-Instruct · 16 concurrent requests · FPGA decode**

VCU118 / XCVU9P &nbsp; · &nbsp; Decode16 &nbsp; · &nbsp; 80 MHz &nbsp; · &nbsp; KV up to 128

[Experiment index](docs/EXPERIMENTS.md) &nbsp;·&nbsp; [FPGA performance](#fpga-performance) &nbsp;·&nbsp; [Cycle simulation](#cycle-simulation-results) &nbsp;·&nbsp; [16 requests & outputs](#16-requests--their-recorded-outputs) &nbsp;·&nbsp; [Download evidence](docs/evidence/kv32_kv128_cycle_sim/README.md) &nbsp;·&nbsp; [Run on hardware](docs/DEPLOYMENT.md)

</div>

| Active requests | Executed steps | Generated tokens | FPGA commands |
| :---: | :---: | :---: | :---: |
| **16** | **128** | **1,784** | **8,192** |

Real incremental inference with the released 80 MHz bitstream: all 16 requests reach position 127 using their own valid, committed KV history. The measurements below come from the FPGA's command cycle counters.

**Latest evidence, published 2026-11-02 (Asia/Shanghai):** the board run and the KV32/KV128 cycle comparison are complete. The simulation dataset contains **12 complete command replays and 52 validated stage records**, with byte-exact agreement against the corresponding board captures. Board counters, complete-model wall time, modeled operator timing and power telemetry have separate measurement boundaries; see the [experiment index](docs/EXPERIMENTS.md) for the current results and the preserved historical baselines.

## FPGA performance

![Measured FPGA latency and throughput over KV length](docs/evidence/kv128_chat16/showcase/fpga_performance.png)

One decode step emits **16 tokens** and executes **32 Attention + 32 MLP commands**. The table reports their accumulated FPGA execution time and `16 / FPGA time` throughput.

| KV length | Attention | MLP frontend | FPGA time / step | Aggregate FPGA-time throughput |
| ---: | ---: | ---: | ---: | ---: |
| 20 | 0.546444 s | 0.586748 s | **1.133192 s** | **14.119 token/s** |
| 32 | 0.645800 s | 0.586758 s | **1.232558 s** | **12.981 token/s** |
| 64 | 0.910592 s | 0.586770 s | **1.497361 s** | **10.685 token/s** |
| 96 | 1.175346 s | 0.586740 s | **1.762085 s** | **9.080 token/s** |
| 128 | 1.440162 s | 0.586734 s | **2.026896 s** | **7.894 token/s** |

**Timing boundary:** `Σ DONE_CYCLES / 80 MHz`. CPU Down, LM head, other host work and transfers outside hardware commands are excluded. These are FPGA execution metrics; complete-model wall-clock results are available in the [measurement report](docs/evidence/kv128_chat16/README.md#measured-speed).

[Performance CSV: all 128 steps](docs/evidence/kv128_chat16/results/fpga_performance_rounds.csv) · [8,192 raw command records](docs/evidence/kv128_chat16/results/commands.csv) · [Vector figure](docs/evidence/kv128_chat16/showcase/fpga_performance.svg)

The complete host–FPGA step takes **71.312 s at KV32** and **97.453 s at KV128**, emitting 16 tokens in each target step: **0.224366** and **0.164182 token/s**, respectively. Across the recorded run, 1,784 generated tokens in the defined 9,843.491879 s model window give **0.181236 token/s**. These wall times include host computation, transfers and capture overhead; they are not the FPGA-time throughput in the table above.

## Cycle-simulation results

The released RTL was replayed with real board inputs at core 80 MHz and DDR interface 200 MHz. No synthesis, implementation, programming or release-RTL change was performed. Each KV setting covers Attention layers **0, 8, 16, 24, 31** and Gate/Up layer **0**; all six reported stages are available together only at layer 0. Eleven new replays were completed, and the complete existing KV32 Gate/Up log was reused.

**These are cycle-simulation estimates.** Projection groups run from actual dispatch through the last specified postprocessing result. The table sums time over the same verified layers in both KV settings. Shared weight bytes are counted once for all 16 requests, with efficiency `ΣD / (12.8e9 × ΣT_seconds)` for the corresponding single DDR channel.

| Complete stage | Matched layers | KV32 ΣT / ms | KV128 ΣT / ms | KV32 efficiency | KV128 efficiency |
| --- | ---: | ---: | ---: | ---: | ---: |
| Q + RoPE | 5 | 10.6399375 | 10.6399375 | 61.5943% | 61.5943% |
| K + RoPE + KV quantization | 5 | 4.7402250 | 4.7401500 | 34.5638% | 34.5643% |
| V + KV quantization | 5 | 4.2443250 | 4.2439625 | 38.6021% | 38.6054% |
| O linear projection | 5 | 8.5599375 | 8.5599375 | 76.5613% | 76.5613% |
| Gate/Up + SiLU×Up | 1 | 5.0625500 | 5.0625375 | 90.6168% | 90.6170% |
| KV read + QK/Softmax/PV | 5 | 36.3887500 | 134.6927500 | — | — |

The Attention-core span is **7.27775 → 26.93855 ms per verified layer**, a 3.701494× ratio for these two recorded workloads. Preparation and dependencies are separate. First-weight-request service windows are also reported: for example, KV128 layer-0 O has **76.5613% group efficiency** but **4.5005% full-service-window efficiency**, because the latter includes early prefetch and preceding work. Neither metric is a measured DDR handshake utilization, and the simplified DDR model is not rescaled to board command time.

[Full method and results](docs/evidence/kv32_kv128_cycle_sim/REPORT.md) · [Per-layer data and figures](docs/evidence/kv32_kv128_cycle_sim/README.md) · [Complete board + simulation evidence release](https://github.com/zwj276765037-lab/ScaleLLM/releases/tag/evidence-kv32-kv128-20261102)

## 16 requests & their recorded outputs

All **16 actual requests and their complete captured responses** are shown below. Each generates **110–113 tokens**; together they produce **1,784 tokens**. The run stops at the fixed position-127 boundary, so some responses end mid-sentence. Prompt chat-template delimiters are hidden for readability; generated wording and Markdown markers are preserved.

![Actual requests 01 to 04 and their full recorded responses](docs/evidence/kv128_chat16/showcase/requests_00_03.png)

![Actual requests 05 to 08 and their full recorded responses](docs/evidence/kv128_chat16/showcase/requests_04_07.png)

![Actual requests 09 to 12 and their full recorded responses](docs/evidence/kv128_chat16/showcase/requests_08_11.png)

![Actual requests 13 to 16 and their full recorded responses](docs/evidence/kv128_chat16/showcase/requests_12_15.png)

[Read / copy all 16 responses](docs/evidence/kv128_chat16/REQUESTS_AND_OUTPUTS.md) · [Exact generated token IDs](docs/evidence/kv128_chat16/results/tokens.json) · [Original text log](docs/evidence/kv128_chat16/results/outputs.txt)

## Data & reproduction

The latest combined archive contains the board run, real inputs and captured outputs, raw simulation events, timing tables, figures, source identities and offline verification tools. Its **980 files**, **12 complete command outputs** and **8 published simulation CSVs** pass extraction/hash/recomputation checks. Download the unchanged **781,288,611-byte ZIP**, SHA-256 and validation receipt from the [evidence release](https://github.com/zwj276765037-lab/ScaleLLM/releases/tag/evidence-kv32-kv128-20261102). Replaying RTL still requires the existing project assets and Vivado; offline evidence verification does not require the FPGA or Vivado.

The earlier board-only package remains available separately. It contains raw command and PMBus traces, target input/output/KV captures, exact token records, original receipts and analysis tools. Its **196 archived files** have been verified; the original **116-file Dell transfer** and **11 derived results** pass independent unpack/recomputation checks.

[Download the complete dataset](docs/evidence/kv128_chat16/DOWNLOADS.md) · [Validation receipt](docs/evidence/kv128_chat16/validation.json) · [Measurement methods](docs/evidence/kv128_chat16/README.md) · [VCCINT telemetry](docs/evidence/kv128_chat16/README.md#what-the-power-data-measures)

```bash
# Download and verify the complete board + cycle-simulation archive.
python3 tools/release/verify_cycle_sim_asset.py \
  --url https://github.com/zwj276765037-lab/ScaleLLM/releases/download/evidence-kv32-kv128-20261102/ScaleLLM_KV128_KV32_Decode16_80MHz_20261101.zip \
  --output outputs/ScaleLLM_KV128_KV32_Decode16_80MHz_20261101.zip --full

# Verify, unpack and recompute the recorded board measurements offline.
python3 tools/kv128_board_release.py --output outputs/kv128_board --recompute

# Regenerate the performance plot and all 16 response cards (Matplotlib required).
python3 tools/plot_kv128_showcase.py
```

<details>
<summary><b>Hardware, numerical scope and release identity</b></summary>

The FPGA executes Q/K/V and O projection paths, RoPE, KV handling, QK/Softmax/PV, and MLP Gate/Up plus SiLU×Up, with online Hadamard/A8 and scale recovery. CPU work includes embedding, normalization/residuals, Down and the LM head. See [architecture](docs/HARDWARE_ARCHITECTURE.md) and [deployment](docs/DEPLOYMENT.md).

| Placed resource | Used |
| --- | ---: |
| LUT | 701,775 |
| CLB registers | 954,554 |
| BRAM36-equivalent | 709 |
| URAM | 304 |
| DSP | 5,389 |

The CLB-register count includes 954,552 flip-flops and two AND/OR-configured registers. Core: 80 MHz. DDR user interfaces: 200 MHz. Tool: Vivado 2025.2. These experiments retained the release RTL and bitstream without synthesis, implementation or reprogramming. [Resource/timing evidence](docs/PERFORMANCE_AND_RESOURCES.md).

[Released bitstream](bitstream/ScaleLLM_Final_Decode16_80MHz.bit), SHA-256:

```text
96df1a5c1bf4174921bc02ccd88df4066dece3d62b491acb3106bb90ac0ffc85
```

Command protocol, full-step commit history and recorded LM-head/token consistency checks pass; the 12 selected complete simulation outputs match their board captures byte for byte. An independent full-model numerical oracle has not been established. The optional active1 attempt produced no valid command data. Operator-level cycle simulations are a separate experiment, not included in the FPGA counter metrics displayed here.

Current PMBus results are **VCCINT conditional telemetry**, not whole-board input power or a strict command-active mean. The often-repeated 5.525 W value is a decoded sequential V×I observation, with finite register steps and an unknown sensor measurement aperture. The historical seven-rail wall-clock power experiment is preserved with its original scope; see [power methods and corrections](docs/POWER_MEASUREMENT.md).

This fixed-length run retains 16 active requests through position 127; no EOS token occurred. The [earlier 16×32-token run](docs/evidence/inference_chat16/outputs.txt) is preserved separately.

</details>

Project source: [Apache-2.0](LICENSE). External dependencies and model terms: [NOTICE](NOTICE).
