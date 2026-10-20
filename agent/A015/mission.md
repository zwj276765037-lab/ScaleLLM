# A015：M005 v3纯数值算术对照实现

当前授权：实际实现ScaleCode高精度参考与当前多次舍入对照；已有ACC不重跑，移除本轮PPL/ACC/任务非劣效。M005 / SM021–SM023 / E012，A014合同和独审，A016数据/runner，Root共享整合与GPU reference。

唯一代码写域：rounding_precision/experiment/numerical_reference/{policy,exact_reductions,current_nodes,model_compat}.py及test_numerical_*.py，但不含A016的inputs/runner/plot测试；gpu_reference.py及test_gpu_reference.py属Root。保留所有其他人的改动。生产、旧工程、A016文件只读。

资源CPU1线程/RSS8GiB/test pilot300秒；无GPU/无后代。新冻结消费期间不改代码，普通数值修复在真实收尾后继续，不新增批准门。

验收：六开关和共同SwiGLU/Host诊断，current与活动V5一致，exact q/rem/d对独立Fraction spot一致，tiny HF兼容接口通过；真实32层与正式规模证据另由Root/A016运行，不把CPU/tiny成功等同全模型完成。
