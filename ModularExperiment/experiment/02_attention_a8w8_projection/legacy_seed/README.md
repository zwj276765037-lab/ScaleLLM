# M4 Matched 8x16 Projection Tile

The main comparison begins after the activation cache and ends at a common
8-row x 16-column S24 tile.  Every case uses 128 active lanes, pre-MAC `a-zp`,
32-element groups, 128 hidden groups, the same input cadence, ready/valid
contract, tile accumulator, and output backpressure.

Cases:

- `int_mac_only`: common MAC producer and S42 accumulator, no scale operation.
- `scalecode`: production ScaleCode lane arithmetic.
- `fp16`: generated AMD half-precision scale arithmetic and S42 conversion.
- `fp32`: generated AMD single-precision scale arithmetic and S42 conversion.

`hadamard_a8_scalecode` is reported separately by combining the measured M1
frontend service with this experiment's ScaleCode tile service. It is not used
to change the scale-path fairness boundary.

All four XSIM cases pass. Routed OOC is complete for all four cases. The final
FP reports are in `artifacts/ooc/fp16_reroute` and
`artifacts/ooc/fp32_rerun`; these supersede earlier incomplete FP run logs.
