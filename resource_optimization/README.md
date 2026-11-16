# Resource optimization: all-DSP ScaleCode recovery

This is the **2026-11-15 board-validated `dsp_all` version** for VCU118 / XCVU9P, Decode16, 80 MHz core and two 200 MHz DDR user interfaces. The exact bitstream SHA-256 is:

```text
5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7
```

Use the hardware and evidence in this directory for this version. The public `deploy/scalellm.py` entry now defaults to this all-DSP image; follow the [deployment and reproduction guide](deployment/README.md). The repository-root `project/hardware` and `bitstream` retain the historical `96df1a5c…` release; it requires the explicit `legacy` deployment profile. Historical KV128 and power measurements retain their earlier image identity.

[Download the tested bitstream](hardware/bitstream/ScaleLLM_Final_Decode16_80MHz.bit) · [Frozen source](hardware/source/) · [Resource CSV](results/resources.csv) · [Machine-readable results](results/summary.json) · [Exact generated tokens](results/board/inference/outputs.json) · [Large artifacts](#complete-raw-evidence-and-routed-checkpoint)

## Hardware change and source identity

The four `use_dsp` attributes in [hap_a8w4_scalecode_recover2_lut.sv](hardware/source/project/hardware/rtl/mlp/hap_a8w4_scalecode_recover2_lut.sv) change from `no` to `yes`. The module retains its historical name. All other RTL, ROM, ABI and XDC inputs are unchanged. This is separate from the earlier double-buffer RTL experiment.

The [original candidate manifest](hardware/provenance/candidate_manifest.json) binds **106 source inputs**: 79 RTL files, two ROMs, one ABI description, 23 Vivado files and the original Python builder. All 106 exact files are included under `hardware/source/`. The candidate leaf SHA-256 is `f645dbf2e78f7ea2f1cc372cbe1cfd97c3b7ff3b63ca612a6dec29308786facb`.

[Actual build and resume scripts](hardware/build_scripts/) preserve the experiment's commands, paths and historical receipts. They are an as-run record; machine paths require adaptation for another installation. The original builder under the source snapshot retains its historical limits and is not a newly validated portable entry for this candidate. Final implementation used 96 available logical CPUs with Vivado's measured maximum of 32 threads; the active guardian disabled fixed elapsed-time termination while retaining memory and disk checks. The native setup/hold/pulse, routing, DRC and bus-skew acceptance checks remained enabled. A rebuild is not claimed to produce identical placement or bitstream bytes. Vivado 2025.2, its IP catalog, licenses and the official VCU118 board files remain external dependencies.

## Final routed resources and timing

All values in this table are from the **final routed** design.

| Resource | Used | Available | Utilization |
| --- | ---: | ---: | ---: |
| LUT | 632,446 | 1,182,240 | 53.50% |
| CLB registers | 936,372 | 2,364,480 | 39.60% |
| Occupied CLB | 136,026 | 147,780 | 92.05% |
| DSP | 5,773 | 6,840 | 84.40% |
| BRAM36 equivalent | 709 | 2,160 | 32.82% |
| URAM | 304 | 960 | 31.67% |

There are 936,370 flip-flops plus two AND/OR-configured registers. SLR0/1/2 occupied CLB percentages are **92.46 / 99.11 / 84.57%**. The 96 recovery leaves use four DSPs each, or 384 in total. Their hierarchical LUT attribution sums to 49,638; cross-hierarchy combining means this is not an independently additive resource cost.

| Final physical check | Result |
| --- | ---: |
| Setup WNS / TNS | +0.009 ns / 0 |
| Hold WHS / THS | +0.008 ns / 0 |
| Failing setup / hold / pulse endpoints | 0 / 0 / 0 |
| Fully routed / routable nets | 1,625,124 / 1,625,124 |
| Routing errors | 0 |
| DRC Error / Critical Warning | 0 / 0 |
| Bus-skew constraints | 94 MET; minimum slack +3.103 ns |

[Utilization](results/physical/route/utilization.rpt) · [Per-SLR report](results/physical/route/utilization_slr.rpt) · [Timing](results/physical/route/timing_summary.rpt) · [Physical acceptance](results/physical/final_physical_acceptance.json) · [Bus-skew evidence](results/physical/final_bus_skew_audit/)

## Controlled resource comparison

These two rows use the same **post-physopt** stage and common build context.

| Candidate | LUT | DSP | Occupied CLB | Setup WNS | Hold WHS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Wider recovery multiplication in DSP (`dsp_raw_only`) | 645,270 | 5,581 | 132,516 | +0.498 ns | -0.588 ns |
| All recovery multiplications in DSP (`dsp_all`) | 632,446 | 5,773 | 136,026 | +0.028 ns | -0.641 ns |
| All minus wider-only | **-12,824** | **+192** | **+3,510** | | |

Both rows precede routing and have negative hold margins. Final routed timing closure belongs to `dsp_all`. The wider-only route was stopped by the old eight-hour limit; that is **STOPPED_TIME_LIMIT**, not proof that it cannot route. The user then removed fixed time termination and the all-DSP run completed. Original selection, stop and handoff receipts are preserved in the [comparison evidence](results/comparison/) and raw archive.

The older published 701,775-LUT / 5,389-DSP result is from a different implementation and a Fully Placed report. Its entire difference from this final routed design is not attributed solely to DSP attributes. SLR1 CLB occupancy is still 99.11%; no capacity claim for moving Down into the FPGA is established. **Down remains on the CPU.**

## Dell board validation

The exact new bitstream was programmed into volatile SRAM using Vivado Hardware Manager 2022.2. An initial all-ones PCIe read was resolved by restarting only the exact XDMA device. The host was not rebooted, the driver was unchanged and configuration Flash was not written.

| Test | Result |
| --- | --- |
| Final magic, ABI, clock, layouts, formats and idle/error state | PASS |
| DDR0 and DDR1 actual write/readback | 196,608 bytes each, byte-exact |
| Selected operator replays | **12/12 full outputs byte-exact** |
| Original end-to-end requests | **16 × 32 generated tokens = 512** |
| Complete rounds / hardware commands | **50 / 3,200** |
| Token, position, epoch and retirement trajectory | PASS |
| Actual submit / two complete descriptors / output / ACK chain | PASS, 934,209 IO records |
| Selected KV32 commands within the full run | Six input/output hash pairs match the sealed reference |
| Native exit / final quiescence / handles | 0 / true / closed |

The 12 replays cover Gate/Up layer 0 and Attention layers 0, 8, 16, 24 and 31 at each of KV32 and KV128. They are selected-command coverage. The full model regression uses the original normal-retirement 16-request workload, not the earlier 128-step fixed-active-count benchmark.

The final [outputs.json](results/board/inference/outputs.json) is **identical as a complete 12,126-byte file** to the original reference, SHA-256 `975c342521ebe538da25cf9d52426c7a65c57632fa256375c2930ce26e04a034`. Native process time including full startup hashes was **3,368.984946 s (56 min 8.985 s)**. The runtime report's model window is 3,312.597651 s; it starts after startup asset verification. Neither value is a pure FPGA execution time.

Inference peak RSS was 2,510,462,976 bytes. The stage peak for owned processes was 2,886,406,144 bytes. No memory/disk guard fired, and fixed elapsed-time termination stayed disabled. Final identity and all 38 runtime source files were rechecked. Owned processes exited, the lease was released, and this candidate was left resident in volatile SRAM.

[Regression audit](results/board/inference/regression.json) · [Operator results](results/board/replay/report.json) · [Closure receipt](results/board/board_stage_closure.json) · [Transfer verification](results/board/transfer_verification.json)

This establishes regression equivalence to the sealed results. An independent complete-model mathematical oracle remains **NOT_ESTABLISHED**. A separate seven-rail power retest is now available below. A complete 128-step model run has not been performed with this bitstream.

## Seven-rail power retest

The November 15 all-DSP retest completed all twelve planned windows and native process cleanup. Its status is **PARTIAL_WITH_LIMITS**: only idle1, idle3 and full3 have complete common telemetry coverage. The other nine full-window means remain null.

| Workload, n=3 | Covered-time mean ± repeat SD / W | Common coverage | Full-window means |
| --- | ---: | --- | ---: |
| Idle | **11.091 ± 0.006** | 99.96046–100.00000% | 2/3 |
| Repeated Attention | **11.343 ± 0.016** | 97.52732–98.32836% | 0/3 |
| Repeated MLP frontend | **11.826 ± 0.047** | 96.87886–98.36237% | 0/3 |
| Complete KV128 step | **11.139 ± 0.013** | 99.19497–100.00000% | 1/3 |

These are means over each repeat's actual common covered intervals; the 11.139 W complete-step result is not a three-repeat full-window mean. The new pilot set 150 ms / 450 ms; the historical retest used 140 ms / 420 ms. Sensor-window and whole-board-input limits remain. See the [new report](power_retest/REPORT.md), [independent audit](power_retest/source/independent/main_001_independent.json), [download and recomputation instructions](power_retest/README.md), and [raw evidence Release](https://github.com/zwj276765037-lab/ScaleLLM/releases/tag/resource-optimization-power-20261115).

## Verify and use the publication

From the repository root:

```bash
python3 resource_optimization/verify_publication.py
```

The check validates every version-directory file, the 106 frozen source inputs and the exact tested bitstream. To program the new image, start your Hardware Manager server, discover the exact cable target/device, then run the included strict Tcl entry with all four arguments:

```text
vivado -mode batch -source resource_optimization/hardware/program/program_sram.tcl -tclargs localhost:3121 EXACT_TARGET xcvu9p_0 FULL_PATH_TO_NEW_BIT
```

Use the bit under `resource_optimization/hardware/bitstream/`. The Tcl verifies its exact size/SHA and requires the explicit target and unique XCVU9P. Programming is volatile SRAM only. Perform the documented post-program identity and DDR checks before inference. The archived board runtime is the Dell as-run version; only its whole-run wall termination was removed. The root portable deployment wrapper now selects this image by default. Its new independent-directory qualification is tracked in [deployment stage results](deployment/source/results.md).

## Complete raw evidence and routed checkpoint

Large artifacts are attached to the [resource-optimization-20261115 release](https://github.com/zwj276765037-lab/ScaleLLM/releases/tag/resource-optimization-20261115), targeted at this branch. Exact sizes and SHA-256 values are in [downloads.json](downloads.json).

- [Complete raw evidence ZIP](https://github.com/zwj276765037-lab/ScaleLLM/releases/download/resource-optimization-20261115/ScaleLLM_Resource_optimization_20261115_evidence.zip): original build/functional/physical reports, board logs, failures, runtime source identity and complete XDMA trace, with a per-member hash inventory.
- [Final routed DCP](https://github.com/zwj276765037-lab/ScaleLLM/releases/download/resource-optimization-20261115/ScaleLLM_Resource_optimization_Decode16_80MHz_routed.dcp): 668,816,413 bytes; SHA-256 `3780de3ab72a506a63ee1d59ecea6c7d26e1f2f29ceb7aa5be2ee81acb867259`.

```bash
python3 resource_optimization/verify_publication.py --archive /path/to/ScaleLLM_Resource_optimization_20261115_evidence.zip --checkpoint /path/to/ScaleLLM_Resource_optimization_Decode16_80MHz_routed.dcp
unzip /path/to/ScaleLLM_Resource_optimization_20261115_evidence.zip -d raw
python3 raw/mlp_scalecode_dsp_board/board_test/scripts/verify_inference.py --repository-root . --board-test-root raw/mlp_scalecode_dsp_board/board_test
```

The final command recomputes the 512-token, 50-round, 3,200-command audit offline; it does not access hardware. The original experiment notes and scripts preserve their original local paths and historical state. In particular, the build-time bitstream receipt says `board_programming=NOT_RUN`; the later board closure supplies the actual November 15 PASS. Model weights, vendor tools, licenses and installed drivers are not redistributed.
