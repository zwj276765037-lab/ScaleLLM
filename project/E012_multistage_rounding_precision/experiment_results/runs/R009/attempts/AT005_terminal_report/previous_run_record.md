# R009 — 第32层真实F18/F20出口开发试验

Execution state: running；verdict: inconclusive，尚无整网结果。

AT003实际PID880983/PGID880983/startticks14963283，CPU/GPU资格通过后正在唯一一次模型装配。仅index31o_proj/down_proj使用F24+b guard/acc、F16+b真实输出/int64、HostFP32额外scale2^-b；前31层和其余节点原样。6臂/36开发文档/216forwards，主比较固定ref4，另报matched-format与reference drift。

AT001/AT002由资格在装模型前检出legal_shift漏补b的问题，自然失败并保全；AT003 core_v2修复，GPU实际b0 parity/wide-code/Fraction参考全部通过。不把基础设施/测试失败当作方法失败。

[合同](lastlayer_precision_contract.json) · [冻结协议](attempts/AT003_true_exit_precision_dev36/protocol.md) · [源/输入](attempts/AT003_true_exit_precision_dev36/manifest.json) · [实际启动](attempts/AT003_true_exit_precision_dev36/actual_launch.json) · [当前状态](attempts/AT003_true_exit_precision_dev36/status.json)
