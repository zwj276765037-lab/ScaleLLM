

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-20T08:57:35.240611+00:00。来源修订：`cfb9c0cd3fc1`。

# E012 / R009 运行结果

[负责人维护的本批运行记录](run.md)

# R009 — 第32层真实F18/F20出口开发试验

Execution state: running；verdict: inconclusive，尚无整网结果。

AT003实际PID880983/PGID880983/startticks14963283，CPU/GPU资格通过后正在唯一一次模型装配。仅index31o_proj/down_proj使用F24+b guard/acc、F16+b真实输出/int64、HostFP32额外scale2^-b；前31层和其余节点原样。6臂/36开发文档/216forwards，主比较固定ref4，另报matched-format与reference drift。

AT001/AT002由资格在装模型前检出legal_shift漏补b的问题，自然失败并保全；AT003 core_v2修复，GPU实际b0 parity/wide-code/Fraction参考全部通过。不把基础设施/测试失败当作方法失败。

[合同](lastlayer_precision_contract.json) · [冻结协议](attempts/AT003_true_exit_precision_dev36/protocol.md) · [源/输入](attempts/AT003_true_exit_precision_dev36/manifest.json) · [实际启动](attempts/AT003_true_exit_precision_dev36/actual_launch.json) · [当前状态](attempts/AT003_true_exit_precision_dev36/status.json)

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_true_exit_precision_dev36](attempts/AT001_true_exit_precision_dev36) | 未登记；查看原记录 | 未登记 | [manifest.json](attempts/AT001_true_exit_precision_dev36/manifest.json) |
| [AT002_true_exit_precision_dev36](attempts/AT002_true_exit_precision_dev36) | 未登记；查看原记录 | 未登记 | [manifest.json](attempts/AT002_true_exit_precision_dev36/manifest.json) |
| [AT003_true_exit_precision_dev36](attempts/AT003_true_exit_precision_dev36) | completed | Repeated development first36 documents; true last-layer output format overlay, main common ref4 plus matched-format and reference-drift pairs. No heldout/ACC/PPL/RTL timing claim. | [执行收据](attempts/AT003_true_exit_precision_dev36/result.json) · [manifest.json](attempts/AT003_true_exit_precision_dev36/manifest.json) |
| [AT004_cpu_postprocess](attempts/AT004_cpu_postprocess) | 未登记；查看原记录 | 未登记 | [manifest.json](attempts/AT004_cpu_postprocess/manifest.json) |
| [AT005_terminal_report](attempts/AT005_terminal_report) | 未登记；查看原记录 | 未登记 |  |

## 本批问题与交付文件


## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
