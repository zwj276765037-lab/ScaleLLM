# ScaleLLM

面向 Xilinx VCU118（xcvu9p-flga2104-2L-e）的 Llama-3.1-8B-Instruct 软硬件工程，保持 Hadamard、ScaleCode 和 format 05 数值合同。

## 当前版本：M003 已执行，完整实现未布通

2026-10-20：M003 联合版本已完成RTL修复、限定功能验证、新综合，以及实际布局和物理优化；E011/R003/AT006完整place/physopt阶段检查通过，route原生自然失败，最终797175个重叠路由节点、615840条资源冲突网。失败检查点和原始诊断已保存在服务器。当前E011/R004对同一失败检查点的只读原生取数已自然完成；初步离线归因已保存，独立结果审核尚未结束。

| 内容 | 入口 |
| --- | --- |
| 硬件RTL、Host、测试与Vivado构建源 | [project/hardware](project/hardware/README.md) |
| 软件算法、整数参考与实验 | [project/software](project/software/README.md) |
| 当前时序、资源与条件性能估算 | [硬件指标](results/hardware_metrics.md) |
| 当前硬件实验与原始记录索引 | [E011](project/E011_m003_joint_routability_implementation/README.md) |
| M003合同、设计冻结与验收 | [任务入口](mission/M003_joint_routability_closure/README.md) |
| 当前任务与项目目标 | [mission](mission/current.md) · [goal](goal/goal.md) |
| 现成失败报告的具体冲突位置 | [定位记录](project/E011_m003_joint_routability_implementation/experiment_results/runs/R004/attempts/AT001_failed_route_driver_region_localization/evidence/existing_report_localization_findings.md) |
| 工作台首页原文快照 | [WORKSPACE_README.md](WORKSPACE_README.md) |

资源为本版physopt postPlace实测：LUT801147（67.77%）、寄存器1021742（43.21%）、DSP5451（79.69%）、BRAM941（43.56%）、URAM752（78.33%）；CLB站点占用98.65%。目标core100MHz尚未收敛，physopt WNS−2.753ns；失败route图时序不能作为合法布线签核。阵列理论算力与历史tokens/s模型均是有条件估算，当前没有上板吞吐或可用bitstream。

## 仓库范围

本次更新保存当前源码、规格、脚本、测试、结果图表和有界记录，保留已有ScaleLLM_pictures图片与提交历史。Vivado生成工程/大型网表、原始张量/模型权重、工具缓存、大型运行记录和本地会话回执保留在服务器，不随源码快照上传。排除范围和导出文件SHA见[EXPORT_MANIFEST.json](EXPORT_MANIFEST.json)。

这是运行期间的逐文件稳定快照，记录文件可以来自快照时间窗内不同阶段；生产源文件在副本与服务器间单独核对。历史绝对路径与原始哈希保留，部分链接只在原服务器有效。本次同步不改动当前生产源或EDA进程。
