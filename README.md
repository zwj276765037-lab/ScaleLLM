# ScaleLLM

面向 Xilinx VCU118（xcvu9p-flga2104-2L-e）的 Llama-3.1-8B-Instruct 硬件与软件协同工程，保持 Hadamard、ScaleCode 和 format 05 数值合同。

## 当前版本：M003 已定义

2026-10-18，已建立 **M003：联合可布线改造与完整实现验收**。七个子任务覆盖失败网络归因、联合设计冻结、RTL 改造、物理约束与功能回归、新综合、完整布局布线和全局验收。主合同及验收矩阵已通过独立文档审核；工程状态为 planned，尚未启动 M003 RTL 修改、仿真、综合或 implementation。

| 内容 | 入口 |
| --- | --- |
| M003 完整合同与子任务 | [主合同](mission/M003_joint_routability_closure/contract.md) · [任务导航](mission/M003_joint_routability_closure/README.md) |
| 验收要求 | [验证矩阵](mission/M003_joint_routability_closure/verification_matrix.md) |
| 独立文档审核 | [审核记录](results/reviews/M003_definition_review_2026-10-18.md) |
| 软件算法、整数参考与导出 | [project/software](project/software/README.md) |
| RTL、Host、测试与 Vivado 源脚本 | [project/hardware](project/hardware/README.md) |
| 项目目标与数值合同 | [goal/goal.md](goal/goal.md) |
| 最新实际实验 | [E008 结果](project/E008_m002_exact_hotspot_offload_implementation/experiment_results/summary.md) · [状态](project/E008_m002_exact_hotspot_offload_implementation/experiment_status/summary.md) |
| 原工作台首页快照 | [WORKSPACE_README.md](WORKSPACE_README.md) |

最近实际实验 E008/R001/AT004 已自然布线失败：702396 个重叠节点、547548 条冲突网络；C01 的 9491 个物理对象实际位于 SLR2，但尚未合法布通。终态收尾与独立核验已完成。M003 承接这些证据，不将任务定义完成视为优化有效或布通成功。

## 仓库范围

保存当前源码、规格、脚本、测试和有界实验记录；保留远端已有的 `ScaleLLM_pictures` 图片。Vivado 生成工程、大型 DCP/网表、运行日志、模型权重、大型原始证据和本地会话回执保留在服务器。本次推送不修改生产源、不启动或中断工程运行。

144 项冻结生产输入在服务器原件与发布副本之间逐项核对。历史服务器绝对路径及哈希原样保留，部分证据只能在服务器读取；此源码快照不包含可用 bitstream，也不承诺在全新机器直接构建。

文件身份、排除范围及快照时间见 [EXPORT_MANIFEST.json](EXPORT_MANIFEST.json)。
