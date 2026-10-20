# M004：GSM8K 精度补齐

2026-10-18 用户明确授权“可以在exp建立程序开始补测”，并确认“两张 GPU”。本 mission 落实独立软件补测，保留当前硬件主入口 M003。

交付：六个冻结 checkpoint × 五配置，每组 GSM8K main/test 1319题，严格 EM；验收后以 GSM8K 替换当前展示表 ARC-c 并重算六项平均，不补PPL。

详细设计：[补测计划](../../project/software/0_Software/fix_experiment/source/gsm8k_completion_plan_20261018/plan.md)；有效执行配置：[plan.json](../../project/software/0_Software/fix_experiment/source/gsm8k_execution_cache_v2_20261018/plan.json)。相对原准备计划的操作修订：GPU并发1→2，CPU16–17/18–19；数值、数据、提示、评分协议保持。

资源：两张 RTX A6000，各一个worker、batch1，正常无墙钟/静默强停。M003 EDA的CPU0–7和原资源归属保留，软件不启动EDA、不修改RTL/format05。NVML库版本不匹配尚存；两卡CUDA库存、显存和BF16计算已实测通过，采用CUDA内存与worker计数，不能声称NVML利用率可用。系统驱动未修改。

任务：[SM020](tasks/SM020.md)；实验：[E010](../../project/E010_gsm8k_six_model_completion/README.md)。协议实现A010、worker实现A011是本轮真实新建内部子agent，不绑定旧会话；共享索引和调度由本独立工程对话维护，子agent无后代。

阶段：完整身份与CPU对照 → 30组smoke → 30组train pilot/长度和跨进程重复性门 → 30组full test → 独立复算与回填。若pipeline失败，保留证据并做合同内常规修复；协议实质变化另开R。分数高低不决定执行是否完整。

状态：R001双卡smoke真实启动后因原cache-on/off数值门自然失败并完成收尾；R002于2026-10-18T02:24:47Z采用显式新版本验证实际双卡启动，尚无正式test结果。

[缓存验证修订](../../project/software/0_Software/fix_experiment/source/gsm8k_execution_cache_v2_20261018/verification_revision.md)：原R001失败不改；生产生成/量化/评分规则不改，按真实native-cache调用和逐步状态重建资格验证，保留旧容差诊断。
