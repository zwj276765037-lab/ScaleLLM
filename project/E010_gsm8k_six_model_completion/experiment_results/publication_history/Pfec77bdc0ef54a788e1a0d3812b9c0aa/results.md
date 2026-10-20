# E010：R003 smoke9/30；加速候选CPU验证通过

北京时间2026-10-18T18:32:42.248159+08:00：smoke/pilot/formal分别9/30、0/30、0/30；正式完成及独立接受0/39570。本小时新增3组smoke、12道训练题，正式增量0。

完成Llama-3.2-3B全部5配置，Llama-3.1-8B已通过BF16/a8w8_fp32/a8w4_fp32/a8w4_fp16共4配置；9组均自然exit0、各4训练题，原native-cache v2及完整性qualified通过。当前Llama-3.1-8B/reference_qdq为第10组。训练结果不计正式ACC。

A013加速候选fd26590c…在CPU AT002的42/42测试通过；64MiB+37字节、5次合成实测median旧校验0.180307秒、新比较0.017537秒，即该CPU案例10.281倍。immutable capture0.186135秒另计，CPU18–19、CUDA未初始化。所有交付文件哈希由父重新核对。GPU pinned D2H/全模型/端到端速度未测，不能将10.281倍称为补测提速。A010独立源码审核已真实派发，尚待其结论；候选未接入R003。

GPU0另有yqh的新ScaleLUT attempt03计算PID23186，占12146MiB；本项目worker仍单一，未终止或通知该外部任务。GPU1无计算任务且继续停用。旧R001/R002及全部运行/修复证据保持。


---
Published: 2026-10-18T10:33:13.150285+00:00
Publication: P054226b30875401c9350e1a3e2cb6621
