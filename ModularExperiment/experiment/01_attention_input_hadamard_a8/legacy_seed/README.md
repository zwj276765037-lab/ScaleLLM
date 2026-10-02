# M1 Hadamard + Robust A8 Frontend

Cases:

- `hadamard_only`: `hap_hadamard32_norm_stream`
- `direct_robust_a8`: Robust A8 without Hadamard, using the same S24 source
  groups sign-extended to S27
- `hadamard_robust_a8`: current shared-one-Hadamard/eight-quantizer frontend

The production regression tests are retained as correctness/backpressure gates.
Dedicated benchmark testbenches use no output backpressure to measure intrinsic
latency, II, and total work cycles. Routed OOC runs are stored in `artifacts/`.

Run the current fixed-point gates with:

```bash
./run_fixed_current.sh
```

The direct frontend ablation is a separate experiment-only wrapper so that the
cache and eight quantizers remain on the same boundary as the proposed case.

