

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-20T08:57:35.240611+00:00。来源修订：`cfb9c0cd3fc1`。

# E001 / R004 运行结果

[负责人维护的本批运行记录](run.md)

# R004 — 独立整数参考与数值源身份核查

execution_state: completed；verdict: supported；负责人：父主控。

- [AT001 回执](attempts/AT001_numeric_reference/run.json) 与 [日志](attempts/AT001_numeric_reference/output.log)：9 项既有整数参考测试通过，退出码 0，0.367 秒。覆盖 half-away 舍入、SiLU、SwiGLU、packed A8W4 穷举、group 边界、format05、Gate/Down 位宽与 shift、product Hadamard 和 A8S35；没有修改独立期望。
- [AT002 回执](attempts/AT002_numeric_source_identity/run.json) 与 [逐文件比较](attempts/AT002_numeric_source_identity/comparison.json)：170 个文件与 M001 迁移目标冻结 hash 一致，包括 Attention/MLP 数值 RTL、整数模型、ROM/golden 和全部 42 个 software 输入。

每次回执记录 UTC 时间、Python 3.12.3、工作目录、命令及源身份。AT001 执行期输入未变。此结论仅支持现有 CPU 整数合同与数值源码未改变，不是 RTL 数值端到端、完整 32 层、PPL/ACC 或板级功能证明。

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_numeric_reference](attempts/AT001_numeric_reference) | completed | 9 CPU integer-reference tests; excludes architecture/performance model and all RTL/32-layer/board claims | [执行收据](attempts/AT001_numeric_reference/run.json) |
| [AT002_numeric_source_identity](attempts/AT002_numeric_source_identity) | completed | Hardware attention/MLP numerical RTL, integer models, ROM/golden data plus all 42 migrated software inputs; no functional simulation | [执行收据](attempts/AT002_numeric_source_identity/run.json) |

## 本批问题与交付文件


## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
