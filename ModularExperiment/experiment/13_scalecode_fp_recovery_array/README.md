# M13 ScaleCode versus FP recovery-only 96-lane array

## Frozen comparison boundary

The measured datapath is exactly:

```text
S17 dot + activation/weight scale metadata
  -> recovery / native scale application
  -> two S36 Q12.24 contributions per lane
```

Dot-product/MAC, accumulator, cache, projection controller, and output-tile
rounding are excluded.  The formal ScaleCode result uses the experiment-local
`m13_scalecode_recover2_auto` leaf and the same legal total-shift alignment as
M09.  It contains no `use_dsp` or `mult_style` attribute, so Vivado applies its
default mapping policy just as it does for the FP references.  FP16 and FP32
use AMD Floating-Point IP; FP16 preserves its native RNE and subnormal
flush-to-zero behavior.

The earlier `sc` variant instantiates the production
`hap_a8w4_scalecode_recover2_lut` leaf, whose explicit `use_dsp="no"`
attributes reserve DSPs for the surrounding MAC array.  That variant is kept
only as the diagnostic `SC-LUT` architecture and is excluded from the formal
unforced SC/FP comparison.  The formal ScaleCode variant is named `sc_auto`.

## Geometry and throughput

- 96 independent two-column lanes.
- One Scale Recovery Operation (SROp) is defined as recovering one S17 dot
  with its corresponding activation/weight scale metadata into one S36 Q12.24
  contribution.
- Each two-column lane completes two SROps per accepted cycle; the 96-lane
  array therefore completes 192 SROps per active cycle.
- All three variants are configured for intrinsic II=1.
- At the fixed 100 MHz comparison point, a passing continuous run represents
  19.2 GSROp/s.
- Every variant exposes the same wide S17 input and S36 Q12.24 output boundary;
  only native scale metadata width differs.

## Workload and validity

`model/generate_vectors.py` emits 4,096 cycles of independent lane data,
including zero, sign, maximum-safe FP16 integer, total-shift endpoints 21 and
44, and deterministic random cases.  The self-checking testbench compares all
786,432 output contributions against separate bit-accurate SC/FP16/FP32
goldens and reports observed input/output II, first-output latency, and total
cycles.

Formal implementation uses Vivado 2025.2, `xcvu9p-flga2104-2L-e`, 100 MHz,
`HD.CLK_SRC=BUFGCE_X0Y0`, 0.150 ns setup uncertainty, and zero hold
uncertainty.  OOC implementation and power runs must be launched strictly one
at a time.  Power is valid only after post-route netlist activity is mapped to
the routed checkpoint with reported coverage; behavioral-IP SAIF is not a
formal FP power result.

## Reproduction

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
./experiment/13_scalecode_fp_recovery_array/run_xsim.sh sc_auto
./experiment/13_scalecode_fp_recovery_array/run_xsim.sh fp16
./experiment/13_scalecode_fp_recovery_array/run_xsim.sh fp32

./experiment/13_scalecode_fp_recovery_array/run_ooc.sh sc_auto
./experiment/13_scalecode_fp_recovery_array/run_ooc.sh fp16
./experiment/13_scalecode_fp_recovery_array/run_ooc.sh fp32
```

The `result/13_scalecode_fp_recovery_array` summary must distinguish completed
measurements from pending runs and compute energy as:

```text
pJ/SROp = dynamic_power_W / 19.2e9 * 1e12
```
