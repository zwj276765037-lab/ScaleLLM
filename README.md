# ScaleLLM FPGA Hardware

ScaleLLM is a VCU118-oriented Llama-3.1-8B acceleration research project. This
repository contains the reproducible hardware source tree, bit-exact models,
testbenches, host-side runtime scaffolding, and Vivado build scripts for the
current V5 Attention+MLP architecture.

## Source Snapshot Update: 2026-10-02

This update publishes the current ScaleLLM working tree, including software
experiments, module comparisons, quantization corrections, and hardware/Host
source changes. It is a research snapshot, not a qualified board release.
The resource, clock, timing, and throughput figures below describe the
historical snapshot explicitly dated in Current Status; they do not certify
all source changes in this update or the separate active hardware workspace.

Large raw implementation/power evidence, waveforms, and generated full-shape
Down/trace datasets remain local. Their generators and experiment instructions
are included; summaries that reference excluded raw files are not a complete
independently reproducible evidence archive on their own.

## Architecture

- Platform: AMD/Xilinx VCU118, `xcvu9p-flga2104-2L-e`
- Attention: A8W8 ScaleCode with Hadamard processing
- MLP: A8W4 group-32 ScaleCode SwiGLU with Hadamard processing
- MLP kernel geometry: `2 x 8 x 12`, exactly 3,072 DSP48E2 instances
- Full production core: 5,453 DSP48E2 and 752 URAM288 instances
- Metadata: bank-local capture
- W4 internal repacking: legal `3x16 -> 4x12`
- External DDR weight format: unchanged by the internal repacker
- Weight storage: resident across both VCU118 DDR channels
- Runtime model: 32-layer Host/FPGA loop with two interleaved cohorts
- Initial signoff clocks: core/DDR0/DDR1 = `100/300/300 MHz`
- MIG external reference period: `4000 ps`

The algorithm, quantization modes, external weight format, MLP geometry, and
hard-resource identity are frozen. Physical timing fixes may still add local
register replication, buffering, or pipeline state without bypassing the real
Attention or MLP computation.

## Current Status

The 2026-09-08 source snapshot has completed fresh production synthesis and
optimization with zero synthesis/optimization errors. Independent post-opt
and pre-place audits confirmed:

```text
CLB LUTs       765,351 / 1,182,240   64.74%
CLB registers  906,432 / 2,364,480   38.34%
DSP48E2          5,453 / 6,840        79.72%
URAM288            752 / 960          78.33%
BRAM tiles          812 / 2,160        37.59%
MLP DSP48E2       3,072
pre-place DRC errors  0
```

The focused registered SwiGLU OOC implementation passed at 100 MHz with
`WNS/WHS = +0.377/+0.010 ns`. Full-chip placement is still under evaluation.
No accepted full-chip route, bitstream, VCU118 execution, measured token/s, or
measured token/J result is claimed by this repository snapshot.

The current 100 MHz scheduling model estimates:

| Stage or mode | Analytical throughput |
|---|---:|
| Attention cohort stage | 70.58 processed token/s |
| MLP cohort stage | 94.82 processed token/s |
| Same-cohort serial diagnostic | 40.46 processed token/s |
| Ideal two-cohort pipeline limit | 70.58 processed token/s |

These are analytical processed-token rates, not generated-token board
benchmarks. The 60/65/70 token/s acceptance, engineering, and stretch targets
require approximately 15.6/16.9/18.2 GB/s of aggregate useful DDR bandwidth.

## Repository Layout

```text
rtl/                  Attention, MLP, integration, and board RTL
model/                Bit-exact models, exporters, and vector generators
tb/                   SystemVerilog testbenches
tests/                Python contract and unit tests
host/                 XDMA runtime, memory layout, and cohort scheduling
data/                 Deterministic ROMs, manifests, and compact test vectors
docs/                 Source provenance notes
0_Software/           Software evaluation, corrections, and result summaries
ModularExperiment/    Module comparison sources, tests, and result summaries
introduction/         Algorithm descriptions and correction handoffs
vivado/constraints/   OOC, production, and VCU118 constraints
vivado/manifests/     Canonical source graphs
vivado/scripts/       Simulation, synthesis, implementation, and board flows
```

Generated checkpoints, reports, bitstreams, waveforms, caches, full model
weights, and board measurements are intentionally excluded from Git.

## Canonical V5 Entry Points

```text
vivado/manifests/attention_mlp_resource_top_v5_sources.list
vivado/manifests/attention_mlp_production_v5_sources.list
vivado/manifests/attention_mlp_board_core_v5_sources.list
vivado/scripts/run_attention_mlp_production_v5_synth.sh
vivado/scripts/run_attention_mlp_production_v5_pre_place_contract_audit.sh
vivado/scripts/run_attention_mlp_production_v5_route.sh
vivado/scripts/run_create_attention_mlp_vcu118_dual_ddr_v5_bd.sh
```

V4 and focused OOC flows remain for regression and provenance checking. They
must not be substituted for the canonical V5 production source graph.

## Tooling

- Vivado 2025.2
- Python 3
- Icarus Verilog where used by lightweight RTL tests
- Bash

Vivado launchers accept `VIVADO=/path/to/vivado` when the executable is not at
the server-local default path. Heavy production runs require `HAP_JOBS=32` and
must be executed one at a time.

## Reproducibility Boundary

Passing module simulation or OOC timing does not prove full-chip timing or
board operation. A complete hardware result requires fresh production
synthesis, placement, route, nonnegative setup and hold slack, zero DRC and
unrouted nets, bitstream generation, dual-MIG/XDMA integration, real-weight
bit-exact tests, the 32-layer workload, and measured throughput and power.
