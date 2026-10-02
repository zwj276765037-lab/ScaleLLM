# MLP Gate/Up A8W4 projection

## Scope

- Production arithmetic anchor: packed two-column A8W4 group32 dot products
  from `hap_a8w4_group32_pack2_s17` and ScaleCode recovery from
  `hap_a8w4_scalecode_recover2_lut`.
- Physical geometry: `16 rows x 12 columns`, implemented as 96 two-column
  lanes.  Each output tile accumulates 128 hidden-dimension group32 inputs.
- Common observation point: one `16 x 12` S24 Q8.16 Gate/Up tile with the
  external 16-column ordering and legal `0xfff`, `0x0ff`, or `0x00f` column
  masks preserved.
- Fairness rule: SC, FP16, and FP32 all start from the same S9 activations,
  S4 weights, and their native scale metadata; all accept one group32 per
  cycle and produce one tile per 128 accepted groups.  Resource results use
  complete 96-lane tops, not leaf-area multiplication.

The fixed target is `xcvu9p-flga2104-2L-e`, Vivado 2025.2, 100 MHz,
`HD.CLK_SRC=BUFGCE_X0Y0`, 0.150 ns setup uncertainty, and zero hold
uncertainty.

## Compared implementations

### ScaleCode

`m09_sc_gate_up_tile` keeps the production integer dot and ScaleCode recovery
leaves.  A contribution is formed with integer code multiplication and shift
alignment, accumulated in S43, rounded/saturated once at the S24 output, and
retired through a two-entry result FIFO.

The initial regression around the production
`hap_mlp_shared_dual_slice16x12_s43_s45` wrapper passed when consecutive tiles
reused the same payload, but a distinct-tile workload exposed a drain-boundary
bug: the final recovered contribution could require a following transaction
as an implicit flush token.  That behavior can mix the last group/tag at a
tile boundary and is not suitable for a standalone matched comparison.

The experiment therefore uses `m09_sc_a8w4_lane2_accum`.  It does not replace
the numerical leaves: it delays first/last/shift tags beside the explicit
three-cycle recovery pipeline, accumulates the contribution carrying the
matching tag, and pushes the final sum without needing a later input.  The
production issue and this experiment-local handshake/tag correction must be
reported separately; passing this module is not a claim that the original
wrapper already has the corrected drain behavior.

### FP16 and FP32

`m09_fp_gate_up_tile` uses the same production packed integer dot producer.
Each dot is then converted to floating point, multiplied by its activation
scale and weight scale in floating point, and accumulated across 128 groups by
an AMD Floating-Point accumulator configured for rate one.  `TLAST` terminates
each 128-group tile; only the completed sum is converted to the common S24
output.

- FP32: S17-to-FP32, two FP32 multiplies, rate-one FP32 accumulator,
  FP32-to-S24.
- FP16: S17-to-FP32-to-FP16, two FP16 multiplies, rate-one FP16 accumulator,
  FP16-to-FP32-to-S24.

The accumulator IP uses its extended internal accumulator and truncate
toward-zero output behavior.  The Python golden models this configuration,
including FP16 round/FTZ effects.  The FP baselines therefore include the
integer-to-FP and native-scale application boundary rather than receiving a
free pre-dequantized contribution.

## Workload and checks

`model/generate_vectors.py` creates 12 fixed seeds, 12 tiles, and 1,536
group32 transactions.  It includes full and tail masks, signed extrema,
structured and random inputs, zero/very small FP16 contributions, and separate
SC/FP16/FP32 goldens.  `data/manifest.json` records shapes, seeds, accuracy
against the common exact-scale reference, and SHA-256 for every `.mem` file.

The matched tile test checks:

- all 1,536 inputs and 12 output tiles;
- bit-exact agreement with each implementation's own hardware-semantic
  golden;
- input II, output II, first-output latency, and total cycles;
- continuous output and periodic output backpressure;
- payload stability while `out_valid && !out_ready`.

The narrow 256-bit serial harness separately verifies the exact physical OOC
top interface and avoids an unrealistic multi-thousand-pin OOC boundary.  It
retains the complete `16 x 12` arithmetic inside the measured hierarchy.

### Real Gate/Up trace workload

`data_trace/` consumes the independently verified M08 pre-Gate/Up capture and
the exact checkpoint weights; it does not reconstruct MLP inputs from Gate/Up
outputs.  It contains six physical tiles covering Gate and Up at layers
0/15/31, 16 real token rows per tile, five full `0xfff` masks and one real
14336-channel tail with `0x00f`.  生成器现使用 production normalized Hadamard、
实验内原始 Min/Max A8 和
normalized folded W4 quantization generate the common centered S9/S4 payload
and decoded native scales.

The regenerated Min/Max workload contains 768 group transactions and 131,072
valid correlations in `[-7384,6959]`; total scale shift is `[26,37]`.
Pre-quantization clip, S24 input, Hadamard and final
output saturation, W4 pre-clamp events and FP16 non-finite contributions are
all zero; 830 FP16 contributions flush/round to zero.  Relative to the common
quantized FP64 reference, SC/FP16/FP32 RMSE is
`5.6047257e-6/2.7056551e-4/4.5015972e-6`.  Full regeneration and byte
comparison pass with:

```text
M09_TRACE_VECTOR_VERIFY_PASS files=14 tiles=6 transactions=768 valid_outputs=1024 source_tensors=6 manifest_sha256=d2837d2118ac00bf70519277c26dbb8e2ffa1c12d28f0588caa3e5fd13af5c63
```

This is software/input evidence until all three trace XSIM runs pass.

## Reproduction

Run simulations one at a time:

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
./experiment/09_mlp_gate_up_a8w4/run_matched_xsim.sh sc 0
./experiment/09_mlp_gate_up_a8w4/run_matched_xsim.sh fp16 0
./experiment/09_mlp_gate_up_a8w4/run_matched_xsim.sh fp32 0
./experiment/09_mlp_gate_up_a8w4/run_matched_xsim.sh sc 1
./experiment/09_mlp_gate_up_a8w4/run_matched_xsim.sh fp16 1
./experiment/09_mlp_gate_up_a8w4/run_matched_xsim.sh fp32 1
./experiment/09_mlp_gate_up_a8w4/run_matched_xsim.sh sc 0 trace
./experiment/09_mlp_gate_up_a8w4/run_matched_xsim.sh fp16 0 trace
./experiment/09_mlp_gate_up_a8w4/run_matched_xsim.sh fp32 0 trace
./experiment/09_mlp_gate_up_a8w4/run_serial_xsim.sh sc 1
./experiment/09_mlp_gate_up_a8w4/run_serial_xsim.sh fp16 1
./experiment/09_mlp_gate_up_a8w4/run_serial_xsim.sh fp32 1
```

Run the three large implementation jobs strictly serially:

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
./experiment/09_mlp_gate_up_a8w4/run_matched_ooc.sh sc
./experiment/09_mlp_gate_up_a8w4/run_matched_ooc.sh fp16
./experiment/09_mlp_gate_up_a8w4/run_matched_ooc.sh fp32
```

Each formal result directory contains `STATUS`, `exit_status.txt`, source/input
hashes, and either XSIM metrics or the post-route checkpoint, utilization,
timing, DRC, route-status, `summary.json`, and directory-level `SHA256SUMS`.
Only `STATUS=PASS`, zero exit status, nonnegative WNS/WHS, zero DRC errors,
zero unrouted nets, and successful hash verification qualify for the summary.
