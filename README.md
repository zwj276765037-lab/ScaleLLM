# ScaleLLM

面向 Xilinx VCU118（xcvu9p-flga2104-2L-e）的 Llama-3.1-8B-Instruct 硬件与软件协同工程。当前 M002 工作包括 Attention / MLP 双 DDR 分离、功能修复及物理实现与时序恢复；保持 Hadamard、ScaleCode 和 format 05 数值规则。

## 工程入口

| 内容 | 入口 |
| --- | --- |
| 软件算法、整数参考与导出 | [project/software](project/software/README.md) |
| RTL、Host、测试与 Vivado 源脚本 | [project/hardware](project/hardware/README.md) |
| 项目目标与数值合同 | [goal/goal.md](goal/goal.md) |
| Mission 与执行合同 | [mission/index.md](mission/index.md) |
| 实验与结果 | [project/index.md](project/index.md) |
| E008 当前实现记录 | [E008 状态摘要](project/E008_m002_exact_hotspot_offload_implementation/experiment_status/summary.md) |
| 原工作台首页快照 | [WORKSPACE_README.md](WORKSPACE_README.md) |

## 本次快照状态

2026-10-17 上传时，E008 / R001 / AT003 已通过完整布局前检查，正在执行 `place_design -directive SSI_SpreadSLLs`，验证 C01 SwiGLU branch[1] 向 SLR2 的定向卸载。尚未取得本轮布局完成、合法布通或正式时序签核结果；不包含可用 bitstream。原工作台及历史记录各有自己的观察时间，以 E008 原始阶段记录区分已完成与未完成范围。

## 仓库范围

本仓库保存当前源码、规格、脚本、测试和有界实验记录。Vivado 生成工程、大型网表/检查点、运行日志、外部模型权重与大型原始报告留在服务器；本次上传不修改或暂停服务器工程。144 项冻结生产输入在上传副本与原件之间逐项校验一致。

历史报告中的服务器绝对路径和哈希按原样保留，部分证据仅在原服务器可读取。工具、模型和外部数据依赖见各工程说明；此快照不承诺在全新机器直接完成构建。

文件身份、排除范围与快照时间见 [EXPORT_MANIFEST.json](EXPORT_MANIFEST.json)。
