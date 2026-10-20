# A014：多级舍入设计与独立验收

任务：M005 / SM021–SM023 / E012。首阶段冻结Linear JSONL、oracle、生产CPU回放、误差界和有效域；后续审核实际结果。主合同：../../mission/M005_multistage_rounding_precision/contract.md。

唯一写入：E012 experiment_source/protocol.md；project/software/0_Software/rounding_precision/source/{design,review}.md；本A014四份Markdown。共享索引/JSON由Root维护；不写实现、不改生产/旧树，不启动后代、GPU、EDA或外部进程。A015/A016拥有实现/数据路径，保留他人改动。

设计/独审模型要求gpt-6-astra/xhigh；工程按项目gpt-6.1-sol/xhigh。资源见主合同；本角色仅有界源码读取和文档写入。重要接口/来源缺口用实际collaboration消息回传。
