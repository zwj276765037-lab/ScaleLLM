# E010：R003单GPU0 smoke已完成6/30组

北京时间2026-10-18 17:30窗口：新R003 smoke6/30，pilot0/30，formal0/30；正式完成及独立接受0/39570。新增6组smoke、24道训练题；不计正式ACC。

完成组：Llama-3.2-3B-Instruct全部5配置（bf16/a8w8_fp32/a8w4_fp32/a8w4_fp16/reference_qdq），以及Llama-3.1-8B-Instruct/bf16。六组worker均自然exit0，manifest/summary完整、每组4题，原native-cache v2及静态完整性qualified均通过；本小时核实原始文件和SHA。

当前第7组Llama-3.1-8B-Instruct/a8w8_fp32正在GPU0初始化/完整性准备。GPU1继续停用，无计算客户端。已完成3B组实耗约7–9分钟/组，8B BF16约16分钟；完整性和加载成本均计入，不按纯生成吞吐估计全量剩余时间。

旧R001/R002失败及重启前准备保持，不导入新组数；R003本次六组与历史R002六组为不同原始运行。最终仍须全30组/39570条并独立复解码评分及来源/完整性绑定核验，才能更新结果表和六项平均。


---
Published: 2026-10-18T09:31:33.832163+00:00
Publication: Pa1fbea98af2c4a07a6f06fca3e93b8b8
