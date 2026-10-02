# M3 Native A8W8 Group32 Lane

All cases use the same 32-lane U8/S8 input, pre-MAC `a-zp` centering, 16 DSP
producer, two-cycle group launch, ready/valid boundary, FIFO depth, and S42
Q18.24 output. Only the scale representation/processing is replaced.

Cases:

- `int_mac_only_probe`: emits the signed S21 group correlation.
- `precenter_scale_code`: production `hap_a8w8_group32_lane_s42`.
- `precenter_fp16_scale`: matched FP16 scale datapath plus S42 conversion.
- `precenter_fp32_scale`: matched FP32 scale datapath plus S42 conversion.

FP cases contain generated AMD floating-point IP in both XSim and routed OOC
results. `run_xsim.sh` is limited to MAC-only and production ScaleCode;
`run_fp_ip_xsim.sh` is the authoritative FP16/FP32 correctness and cycle flow.
