# M001：精简工程迁移与工作入口重建

## 痛点与证据

用户于 2026-10-14 要求将旧 ScaleLLM 的核心工程整理到 Workspace/ScaleLLM，避免历史运行物和管理文档遮蔽真正目标。
源目录：`/home/user/EDA-202/zhuowenjun/ScaleLLM`，必须完整保留，不删除、不移动、不改写。

## 本次要改变什么

新工程以 `project/software` 和 `project/hardware` 为唯一实现入口。
复制必要源码、构建脚本、约束、接口规格和小型测试输入；大型权重、原始验证数据、Vivado 工作目录及历史 mission/results 留在源目录，以明确路径引用。
记录来源、复制范围、文件校验和、必要路径适配和未完成项。按 research-agent 建立目标、当前任务、三角色和四个真实项目对话；工具不可用时如实记录未绑定状态，不伪造对话。

## 范围、资源和停止条件

仅允许写入 `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM`。
本轮是复制整理，不改变算法、RTL行为、数值合同或验收阈值。只做目录、依赖、语法及清单检查，不运行 EDA、RTL 仿真、GPU、板卡或 PPL/ACC。
最多两个临时整理 agent，各自只写 software/hardware；主控独占共享管理记录。整理结束后等待用户，不恢复旧物理任务。

## 小任务与阶段决策

SM001：software/hardware 核心复制、来源校验、入口和当前状态整理；独立写入边界由主控分配。

## 当前状态与下一步

completed：software/hardware 核心复制、必要路径适配、hash/静态依赖检查和四个真实工作对话已完成。完整结果见 [M001 汇总](../../results/missions/M001_summary.md)。
没有启动新的 EDA/仿真/模型/板卡任务；后续工程执行等待用户新指令。
