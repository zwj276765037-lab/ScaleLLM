# GU-only next version: engineering scope

Status: AUTHORIZED_FOR_IMPLEMENTATION, active R006 GU-only implementation. User approved execution after the plan; A021 owns the complete abi_gu_only.json and PRO plan. R005 supplementary diagnostics were cancelled by Root stage decision with 116 inputs unchanged and zero survivors; original v6 sources/results remain. New GU-only files and production graph are implemented, module tests have actual PASS evidence, and G4R production integration is running. This note separates the original resource expectations below from new measured results, which remain authoritative in each attempt.

The next version keeps FPGA Gate/Up linear projection and moves the original Down calculation to the Host. The model still contains Down. The Host must reproduce the existing format05 integer Down boundary and rounding; FP32 is not a substitute for that contract. Attention continues to use physical DDR0 and GU continues to use physical DDR1.

## Authorized hardware changes and their dependency proof

| Area | Required change | Retained behavior / proof |
| --- | --- | --- |
| Compute wrapper | Remove Down launch/run states, sequential cache adapter, Down scheduler, GU/Down wide input multiplexers and Down telemetry drivers | Existing GU scheduler, W4 readers, dual 8x12 shared dot kernels, S44 Gate/Up accumulation, S24 projection and GU repack |
| Shared compute | Statically remove each branch's Down S54 accumulator and Down output queue; remove Down tag/data routing | Both 8x12 kernels and their 3,072 DSP remain; prove integer GU outputs unchanged |
| Tensor DMA | Remove the Down 8,192-bit output payload/serializer and opcode-dependent record selection | REC576 GU input, 6,144-bit S24 GU records, ordered AXI B completion and fault drain |
| Activation cache/parser | Store only 128 GU groups; reject unsupported opcode before ownership or memory mutation | Canonical REC576 validation, sequential write order, seal, GU random read and safe clear. BRAM savings are unknown because of primitive granularity |
| Metadata resident | Remove both Down AB banks and associated ready/response/control paths; change commit to require complete GU data only | GU AB banks, epoch identity, complete write count and safe bank switching |
| Metadata loader/scheduler | Remove Down load phase, issue/delivery counters and source stream | GU physical DDR1 metadata loading and ordered delivery |
| Job/CSR | Apply the new ABI/capability identity and GU-only descriptor validation; reject opcode2 atomically; reserve former Down fields according to A021's contract | Descriptor snapshot, admission first error, epoch, DONE, final-B barrier, ACK, ABORT, fault recovery and hard-clear semantics |
| Production graph/build | Use explicit GU-only modules/source closure; forbid Down scheduler/accumulator/repack/resident instances in the actual netlist | Attention 44-source byte baseline, DDR0/DDR1 wiring, clock/reset structure and single-owner resource protections |

Only disabling opcode2 in software is insufficient: unused Down logic must be absent from the selected production source graph or statically eliminated, with netlist checks proving its absence. Legacy RTL and tests remain available as historical numerical references.

## Resource and SLR expectations

Root/A021's mutually exclusive hierarchy subtotal for objects proposed for removal is 60,468 LUT, 47,398 FF, 192 RAMB36, 224 URAM and one DSP. This is the existing objects' occupancy, not a predicted post-change utilization delta. Additional multiplexers/control may simplify; placement, packing and duplication may change. The two shared kernels' 3,072 DSP remain. Shrinking the activation cache from 448 to 128 groups does not guarantee fewer BRAMs.

R005's native saved-Physopt placement already places 49,193 of 49,260 SLICE sites in SLR1. Its native congestion report names `branch0/u_down_accum` among local congested-window occupants (for example 19% in South Global level6), alongside the retained dot kernel and GU accumulator. Removing Down therefore targets real occupied structures in a congested region. The remaining shared kernels, GU metadata, Attention occupancy in SLR1, wide control distribution and fixed DDR endpoints can still limit routing. A new synthesis and actual physical run are needed to decide whether it is enough.

No resource percentage or overlap reduction is promised. The present implementation failed with 545,088 overlapping nodes and has no exported failed-route DCP; R005 uses the earlier saved Physopt DCP and keeps that phase distinction.

## DDR proof

`ddr_binding.json` records hashes and six exact interface edges from the actual generated constructor BD, plus the source trace for the two logical reader halves. `M_AXI_DATA` and `M_AXI_WEIGHT_C0` terminate on physical DDR0. `M_AXI_MLP_DATA` and `M_AXI_WEIGHT_C1` terminate on physical DDR1. Both Attention logical readers use `ddr0_clk`; both MLP logical readers use `ddr1_clk`, and the dedicated paired reader routes the two halves to the corresponding physical port. Existing `gate_ddr0`/`gate_ddr1` field names identify logical halves and do not imply a split of GU weights across the two physical DDRs.

## Verification sequence

1. Update schema-derived headers, exact source closure and static production shape/capability checks together. Compile and elaborate the actual production hierarchy, including the board module-reference boundary.
2. Regress cache/parser, GU scheduler, GU tensor DMA, metadata bank loading/commit, descriptor/CSR admission, job completion/fault priority and safe recovery. Add explicit opcode2/no-side-effect and nonzero reserved-Down-field rejection tests according to the final contract.
3. Compare real shared-kernel GU integer results against the independent Host oracle at bounded output shape with all 128 input groups, group/K-varying values, scale/shift diversity, tail columns and backpressure. Retain full-production GU scheduling coverage separately.
4. Run GU-only production integration with two cohorts, metadata epoch reuse, malformed REC prefix/drain, final-B delay, ABORT, BRESP error, physical DDR framing fault and real clear/reset paths. Reuse earlier unchanged arithmetic evidence only with an explicit dependency map; earlier GU+Down integration is not automatically a GU-only control proof.
5. Create a new Vivado project and synthesize the GU-only source graph. Require actual absence of all Down-only instances and the original nonlinear FPGA MLP stages, while retaining Attention and the two real shared kernels. Report formal board utilization and per-SLR distribution separately.
6. Run one qualified physical flow with the existing clock/DDR responsibilities. Preserve route legality, setup/hold, unconstrained, DRC and CDC judgments independently. Compare SLR packing, retained module locality, crossing statistics and representative congestion windows at matched stages. Do not rerun the old implementation unchanged.

Host Down validation and performance measurements are distinct from FPGA Gate/Up acceptance. No board throughput or Host latency is claimed by this plan.
