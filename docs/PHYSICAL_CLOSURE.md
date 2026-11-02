# Physical closure of the published Decode16 bitstream

This records the actual reader011 flow that produced the published
`96df1a5c…c0ffc85` bitstream and provides the same two global hold-repair commands
for a newly built routed design. The final checkpoint is identified by SHA256
`3b6e401051cef12ba14ff4ebe9e9b3ef142fcdddfa851b0053c97cf718e608c3`.
Neither that checkpoint nor the historical incremental reference is required
by the fresh source build or portable hold-repair stages.

The later [KV128 board measurement](evidence/kv128_chat16/README.md) and
[KV32/KV128 cycle comparison](evidence/kv32_kv128_cycle_sim/README.md) retained
this published design. They performed no synthesis, implementation or
programming. Their complete command-output replays and 52 valid stage results
do not replace the physical timing evidence below, establish a new routed
utilization count, or validate a fresh portable physical rebuild.

## Historical implementation settings

The original run used Vivado 2025.2, `xcvu9p-flga2104-2L-e`, core 80 MHz and
DDR UI 200 MHz, strategy `Vivado Implementation Defaults`, and four threads.
Its recorded run properties were:

| Setting | Actual requested value |
| --- | --- |
| OPT_DESIGN / PLACE_DESIGN / PHYS_OPT_DESIGN / ROUTE_DESIGN directives | `Default` |
| Pre-route PHYS_OPT_DESIGN | enabled |
| POWER_OPT_DESIGN / POST_PLACE_POWER_OPT_DESIGN / POST_ROUTE_PHYS_OPT_DESIGN | disabled |
| Extra options on these steps | empty |
| AUTO_INCREMENTAL_CHECKPOINT | 0 |
| INCREMENTAL_CHECKPOINT | explicitly selected prior routed design |

The prior reference had SHA256
`194edcab5b22c7126594846637b1c78acedc25a7765371f553398ee0d8b67490`.
The native sequence was `opt_design`, `read_checkpoint -incremental`,
`place_design`, `phys_opt_design`, and `route_design`. Although the requested
run directives were `Default`, Vivado explicitly reported that the incremental
flow selected `RuntimeOptimized` and would override placement, post-placement
physical optimization and routing directives. Its native command-comparison
report expands the load to `read_checkpoint -directive RuntimeOptimized
-incremental ...`; subsequent placement/routing messages also print `Default`.
Both observations are retained in the evidence. The successful result should
not be described as an entirely nonincremental default-strategy implementation.

Placement reused the prior physical design extensively; the original routed
reuse report/log listed 1,694,379 fully reused nets (98.96%). This is a dependency
of that historical physical result. The portable `impl` stage clears both
manual and automatic incremental checkpoint selection and starts without it.
A fresh placement can therefore differ substantially. Replaying the identical
incremental flow would require the identified historical reference, which is
not distributed. A user-owned compatible prior checkpoint can support a new
incremental experiment, but does not reproduce that reference's identity.

## Actual route and hold-repair chain

The initial implementation wrapper reached its eight-hour ceiling after the
native route command had completed, during subsequent reporting. Its preserved
post-physical-optimization checkpoint was SHA256
`2ef123f16de402e46561a4013a4febe11cb04cc80a16151d6a12b051f60bc823`.
A separate recovery opened that checkpoint and ran bare `route_design`, then
saved the design before reports. An earlier recovery attempt exceeded its
20-minute checkpoint-load ceiling; the completed recovery allowed 40 minutes
for loading. No synthesis, placement, source/XDC or clock change occurred in
these recovery steps.

| Completed step | Exact physical command | WNS / WHS (ns) | Hold failures | Saved checkpoint SHA256 prefix |
| --- | --- | --- | --- | --- |
| Route recovery | `route_design` | +0.017 / −0.121 | 4 | `1341b09f19009f2d` |
| SLR hold repair | `phys_opt_design -sll_reg_hold_fix` | +0.017 / −0.025 | 1 | `fcb392772acece79` |
| Remaining hold repair | `phys_opt_design -hold_fix` | +0.017 / +0.002 | 0 | `3b6e401051cef12b` |

Both physical optimizations were global commands: no `-from`, `-to`, `-cells`,
net selector, manually imposed LOC/BEL or custom numerical parameter was passed.
The first command selected four cross-SLR candidate nets and moved four
existing receive registers from Laguna into ordinary slices, adding no cells.
The second selected the remaining net and inserted one LUT1 buffer; it added no
FF or ZHOLD delay element. Both commands performed native route finalization.
After each, the actual design was still fully routed with zero routing errors,
so the conditional `route_design -preserve` branch was **skipped** in both
historical attempts. No extra global route was silently run after these repairs.

The original observation script checked four known DDR200 paths before and
after repair. Their shared hierarchy prefix was
`scalellm_final_decode16_bd_i/<slice>/inst/w15.w_multi/triple_slr.fwd.slr_`:

| Slice | Source stage/register | Destination stage/register | Payload bits |
| --- | --- | --- | --- |
| `d0_mig_slice` | `master/common.pipe[1].laguna_m_payload_i_reg` | `middle/common.pipe[0].laguna_s_payload_d_reg` | 134, 360, 314 |
| `d1_mig_slice` | `middle/common.pipe[2].laguna_m_payload_i_reg` | `slave/common.pipe[0].laguna_s_payload_d_reg` | 116 |

These exact endpoints and their observed Laguna/slice coordinates served as
identity and diagnostic checks; they did not restrict either optimization.
The final buffer was inserted on the DDR0 receive-register output for payload
bit 314. The large `write_iphys_opt_tcl` output was an audit artifact and was
not replayed as an input. Its historical placement/coordinates must not be
applied to a fresh design.

The completed route recovery took 9,648.481 seconds, the SLR repair 3,277.736
seconds and the final hold repair 2,704.658 seconds including checkpoint loads,
saves and reports. The original resource ceilings were one active native job,
four threads on CPUs 0–3, nice increment 10, 192 GiB RSS, 64 GiB available RAM
and 30 GiB free disk. Timings and resource use of a fresh run can differ.

The final checkpoint had WNS +0.017 ns, WHS +0.002 ns, WPWS 0.000 ns, no failing
setup/hold/pulse endpoints and all 1,712,169 routable nets routed. The subsequent
normal bit-generation DRC had no Errors or Critical Warnings. The original
bit-generation operation consumed this same checkpoint, producing the published
80,159,263-byte artifact.

## Explicit portable repair stages

The current builder provides `hold-sll` and `hold`, adapted from the original
compact repair Tcl. Each command performs **one** explicitly chosen physical
optimization on the supplied newly routed checkpoint. There is no automatic
retry loop. Both check tool, part, top, 80/200/200 MHz clock identities, input
hash and complete error-free routing before physical optimization. These native
options can operate on a fresh routed design of this top, but its critical
paths and convergence are determined by its actual placement and timing.

Prepare a new build workspace using [BUILD_HARDWARE.md](BUILD_HARDWARE.md).
After fresh implementation, inspect its reports. If cross-SLR hold failures
remain with clean setup timing, run:

```bash
python3 deploy/final/build_hardware.py stage --work /absolute/path/to/new-build \
  --stage hold-sll --source-dcp /absolute/path/to/new-build/impl/reports/routed.dcp \
  --timeout 7200 --rss-gib 192
```

A nonzero exit for remaining timing failures retains
`hold-sll/reports/routed.dcp` and the full reports. It produces no bitstream.
If the remaining report warrants the second historical method, explicitly run:

```bash
python3 deploy/final/build_hardware.py stage --work /absolute/path/to/new-build \
  --stage hold --source-dcp /absolute/path/to/new-build/hold-sll/reports/routed.dcp \
  --timeout 7200 --rss-gib 192
```

A hold stage saves `post_physopt.dcp` immediately after the physical command,
even if the command fails. It queries route status; only incomplete or erroneous
routing triggers `route_design -preserve`. It then saves the new routed or
failed-route checkpoint before reporting. Remaining setup/hold/pulse failures,
route errors, or Error/Critical Warning DRC findings cause a nonzero stage exit.
A failed physical command retains a diagnostic checkpoint, which is not an
accepted result. Existing stage directories cannot be overwritten.

Once the selected result passes, explicitly choose that checkpoint for bit
creation. The bit stage repeats the same identity, timing, route and DRC gates:

```bash
python3 deploy/final/build_hardware.py stage --work /absolute/path/to/new-build \
  --stage bitstream --source-dcp /absolute/path/to/new-build/hold/reports/routed.dcp \
  --timeout 2400 --rss-gib 192
```

The underlying implementation is
[`release_hold_repair.tcl`](../project/hardware/vivado/scripts/release_hold_repair.tcl);
identity/publication checks are shared with the normal builder in
[`release_reports.tcl`](../project/hardware/vivado/scripts/release_reports.tcl).
The portable stage has no historical DCP SHA, individual endpoint or coordinate
requirement. It preserves the physical command sequence and acceptance policy,
while omitting the original experiment-specific endpoint observer and audit
bookkeeping. All six published XDC files and numeric RTL remain unchanged.

## Evidence and validation scope

[`physical_closure_recipe.json`](evidence/final/physical_closure_recipe.json)
binds original source/result/log hashes, full checkpoint hashes, timing and
routing at each step. Its excerpts retain original log line numbers and remove
private machine paths. The successful recipe above is historical native
measurement, not a new execution of the portable stages.

The original fresh validate/create checks ran earlier driver versions, recorded
in [`build_validation.json`](evidence/final/build_validation.json). The added
repair/selected-checkpoint commands were checked with CPU tests of the actual
Tcl control flow and Python launcher wiring. The tests use simulated native
commands and do not establish physical convergence. These additions and full
fresh synthesis/implementation/bit generation have not been run through EDA.
See [`physical_closure_cpu_tests.json`](evidence/final/physical_closure_cpu_tests.json).
