# ScaleLLM 工作对话

项目根目录：`/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM`。分区：**ScaleLLM**。

按用户最新指令新建四个独立对话，不继承旧会话历史、不绑定旧代理。每个入口仅完成一轮就绪确认，没有启动工程任务。此前绑定已取消，误建入口仅归档；原有历史对话保留。

| 对话 | 职责 | 打开 |
| --- | --- | --- |
| 项目主控与架构评判 | goal、顶层mission、索引、模型策略、阶段审核与总结果 | [进入对话](codex://threads/01a13a6e-64bf-7062-b50d-2d552967da43) |
| 工程实现与验证 | 实现代码、实验、原始运行证据与三份实验摘要 | [进入对话](codex://threads/01a13a6e-670c-7af1-8e53-150ebecd6d15) |
| 研究探索与瓶颈分析 | source中的论文、方法、瓶颈证据与候选验证方案 | [进入对话](codex://threads/01a13a6e-695f-74f1-bb45-edb5dec919f1) |
| 技术问答 | question中的问题、回答与可定位证据 | [进入对话](codex://threads/01a13a6e-6ba9-7c32-afe8-03df6d2a7caf) |

三个主agent使用职责名称。A编号仅作为兼容既有记录的内部标识，不能作为对话标题。
技术问答是独立用户入口，需要实验时先明确任务和写入负责人。
当前只有分区入口，未建立代理绑定或自动通信。创建回执：`.research-agent/fresh_section_chats.json`。
