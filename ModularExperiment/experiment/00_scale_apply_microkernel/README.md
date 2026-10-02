# Scale application microkernel

- Production 锚点：`hap_a8w8_group32_lane_s42`、`hap_a8w4_scalecode_recover2_lut`。
- SC：`dot × activation_code × weight_code` 后按 shift 对齐到 guard domain。
- FP16/FP32：相同整数 dot 转换为浮点并乘对应 activation/weight scale。
- 输出合同：A8W8 一份 group contribution（目标 II=2）；A8W4 两列 group contribution（目标 II=1）。
- 本目录隔离 scale 应用成本；完整 projection 的资源与速度在 02/09/12 中测量。
