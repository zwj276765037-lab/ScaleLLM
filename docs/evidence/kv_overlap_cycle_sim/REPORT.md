# K/V projection and postprocessing overlap

## Result and scope

This independent RTL candidate reaches **59.8625% K32 effective weight
efficiency**, versus 34.5331% for the sealed reference, in a complete local
32-group K simulation. Eight V groups reach 66.9418%; their calibrated V32
estimate is **72.6765%**. Quantization is not accelerated.

These results support the feasibility of projection/postprocessing overlap
under the retained AXI service model. They do not establish a complete
Attention-command, model or board speedup. The older ideal-scheduling figures
61.3% / 74.3% are not used as measured results.

| Configuration | Value |
| --- | --- |
| Model / real capture | Llama-3.1-8B-Instruct / layer 0, command 8129 |
| Active requests / history | 16 / KV128, valid committed positions 0–126, current position 127 |
| Core / DDR interface | 80 MHz / 200 MHz |
| Reference FPGA | VCU118, XCVU9P, Decode16 |
| Release bitstream SHA-256 | `96df1a5c1bf4174921bc02ccd88df4066dece3d62b491acb3106bb90ac0ffc85` |
| Candidate change | Two-bank buffering and projection/postprocessing scheduling in an isolated RTL copy |
| Retained modules | Projection array, RoPE, four quantizers, numerical/rounding rules and original KV DMA path |
| Executed scope | Natural Q prefix, all 32 K groups, first eight V groups, then drain and stop |
| Validation status | `FRAGMENT_PASS`; full candidate V32 and complete Attention `NOT_RUN` |

The sealed reference and candidate use identical inputs, weight assets,
testbench, AXI service budget and 83-file compiled source closures except for
the Attention top. The 93 original release-source identities were checked
unchanged. No synthesis, implementation or FPGA programming took place.

## Timing and effective payload

For each local projection window, start is the **first actual even-tile group
dispatch** and end is the **last original `kv_append_valid && kv_append_ready`
acceptance**. The span includes projection memory waits, computation, scale
restoration, postprocessing, buffered waits and append backpressure. Front-end
preparation before this dispatch is excluded. Event timestamps use one
simulation axis in picoseconds; one core cycle is 12,500 ps.

The final AXI B response follows the last append by five core cycles (62.5 ns)
in both selected runs and is reported separately in `summary.csv` and
`groups.csv`. Bank release and the final empty-bank checks are also preserved
in the raw trace. Thus the primary endpoint is append acceptance, not write
response completion or whole-command completion.

Each group accepts 256 internal W8 payloads of 512 bytes: 128 KiB/group.
K32/V32 use 4 MiB; V8 uses 1 MiB. The additional 32 bytes of metadata per
internal payload are excluded from effective weight bytes D. These are
internal accepted weight-code payloads, **not DDR beat counters**. Sixteen
requests share D; it is not multiplied by sixteen.

```text
T_seconds = (last_append_ps - first_dispatch_ps) * 1e-12
effective_bandwidth = D_bytes / T_seconds
efficiency = D_bytes / (12.8e9 * T_seconds)
```

The denominator is the relevant single physical channel's 12.8 GB/s peak.
This metric includes K/V postprocessing, so it must not be silently presented
as matrix-only execution efficiency or measured DDR bus occupancy.

## Local results

| Scope / evidence | Sealed cycles | Candidate cycles | Sealed / candidate time, µs | Sealed / candidate efficiency | Gain, percentage points | Local speedup |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| K32, both simulated | 75,911 | 43,791 | 948.8875 / 547.3875 | 34.5331% / 59.8625% | 25.3295 | 1.7335× |
| V8, both simulated | 17,046 | 9,790 | 213.0750 / 122.3750 | 38.4466% / 66.9418% | 28.4952 | 1.7412× |
| V32, candidate estimated | 68,206 | 36,070 estimated | 852.5750 / 450.8750 estimated | 38.4342% / 72.6765% estimated | 34.2423 estimated | 1.8909× estimated |

Candidate effective bandwidth is 7.6624 GB/s for K32, 8.5685 GB/s for V8,
and an estimated 9.3026 GB/s for V32.

The V32 reference is the earlier complete, validated sealed replay
`cycle_compare_l0_a_kv128_001`, using the same real input and DDR model.
Its V dispatch is 4,707,131,250 ps and its final original KV append is
5,559,706,250 ps, giving 68,206 cycles. It is not this run's V8 extrapolation
(68,190 cycles). The raw phase-event file is included in the archive with
SHA-256 `d5c12df3c477ae75f5f9aea4d06e40181c15ca14a7845d1ebaef862a8e0da1c6`.

## Startup/tail amortization and V32 estimate

The following are prefixes of the **same continuous candidate runs**, from
first dispatch through the selected group's final append:

| Groups | K cycles | K efficiency | V cycles | V efficiency |
| ---: | ---: | ---: | ---: | ---: |
| 2 | 3,734 | 43.8779% | 3,247 | 50.4589% |
| 4 | 6,406 | 51.1520% | 5,436 | 60.2796% |
| 8 | 11,749 | 55.7801% | 9,790 | 66.9418% |
| 16 | 22,438 | 58.4152% | — | — |
| 32 | 43,791 | 59.8625% | — | — |

Let `a_g` be group g's dispatch time in core cycles, using zero-based groups.
Use `II = median(a_g - a_(g-1), g=2..6)` and `T32_est = T8 + 24*II`.
The five observed K intervals are 1339/1333/1340/1332/1339 cycles; the V
intervals are 1097/1092/1095/1091/1098. V has II=1095 and
`9790 + 24*1095 = 36070` cycles.

Applying the same procedure to K8 predicts 43,885 cycles, compared with the
actual K32 value 43,791. Actual minus prediction is −94 cycles / −0.2147%.
This checks the procedure on K; it does not prove that all later V intervals
will remain identical. Using observed V interval extrema produces
35,974–36,142 cycles, or **72.5317–72.8704%**. This is model sensitivity,
not a statistical confidence interval or a guaranteed error bound.

In the equivalent model `T_N ≈ N*II + C`, K has C=1037 cycles and V C=1030.
The equivalent fixed-overhead fraction falls from 8.826% at K8 to 2.363% at
predicted K32, and from 10.521% at V8 to 2.856% at predicted V32. **C is a
fitted equivalent overhead, not a directly measured sum of startup and drain
stalls.** Each candidate projection group still spans 1069 cycles; observed
postprocessing-to-append spans are 1304–1332 cycles for K and 1061–1089 for V.
No halving of quantization latency is assumed.

## Correctness, overlap and waits

Each selected run covers 160 unique projection waves, 8192 K RoPE pairs,
10,240 internal W8 acceptances and 640 original KV append/AW/B records.
Append order, command/layer/slot/epoch/position/K-or-V/head/group tags,
S12 data, metadata and AXI write-address order match. Reconstructing the
8 MiB image from the captured initial image and appends reproduces both
final images byte for byte, SHA-256
`40c81c7f31a3ede0af6927a2036b24f82a7468c6389b0df898281d6b337c2a9b`.

The candidate issues actual next-group array operations during postprocessing:
15,872 issue events for K and 3584 for V. The sampled peak bank occupancy is
two. The observed producer wait condition (even tile waiting for a free bank)
accounts for 7984 K cycles and 140 V cycles. This identifies a K postprocessing
bottleneck and the benefit of overlap; it does not partition every unrecorded
wait into DDR, arithmetic or quantizer stalls. Final bank-empty checks pass.

## DDR model and limits

The retained AXI RAM model shares a 64-byte service budget per 5 ns per
physical channel between weight and data interfaces. It preserves the DUT's
request/ready backpressure and channel arbitration; buffering does not create
an extra memory channel or an increased service budget. It omits detailed
MIG refresh/bank timing, SmartConnect and host-XDMA timing. Candidate and
reference use the same model without scaling their durations to board cycles.

The earlier complete released-RTL layer-0 Attention envelope was 34.8240125 ms
in simulation versus 45.0212375 ms on board. That comparison is available in
the [released-RTL report](../kv32_kv128_cycle_sim/REPORT.md); it demonstrates
why these local simulation improvements cannot be equated with board gains.
This candidate stops after V8 drain, so **no full-command improvement is
reported**. Full candidate V32, Attention outputs, layers 8/16/24/31,
physical resource/timing closure, power and FPGA/model speedups are untested.

## Reproducibility

[Raw downloads](DOWNLOADS.md) include source snapshots, testbench and analysis
tools, run/build manifests, raw events, captured inputs and KV images, the
older complete V32 reference trace and historical failed/prototype attempts.
Only the two continuous runs indexed by [results.json](results.json) feed
the current result. The [verification receipt](validation.json) recomputes
timing/efficiency and checks all 833 inventoried members, source identities,
record order and image correctness. It runs without Vivado or FPGA access.
