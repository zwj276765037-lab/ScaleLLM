# A011 当前实际交付：静态内容完整性修复

已交付checkpoint_static_content_v1完整闭环，原生成5函数与native_cache_call_parity_v2的AST保持。CPU专用22项、最终联合82项稳定通过；A010消费者89项及源码独立审通过。GPU0 Llama3.1 BF16与a8w4_fp32分别4/4训练smoke自然成功，原v2及全部15阶段完整性均过，A010独立接受两终态；QDQ实测224模块同GPU/fullshape重建与2个_H_CACHE条目通过。

[完整交付回执](../../project/software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/weight_integrity_v1_delivery/delivery_receipt.json)；[来源](../../project/software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/weight_integrity_v1_delivery/experiment_source/summary.md)；[结果](../../project/software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/weight_integrity_v1_delivery/experiment_results/summary.md)；[状态](../../project/software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/weight_integrity_v1_delivery/experiment_status/summary.md)。

最后GPU进程309848于04:52:24Z自然结束，GPU0锁已释放；当前空闲hold供父维护交接，无后续CUDA/GPU任务。无EDA或后代。正式GSM8K仍0/30；父负责维护及R003全新资格/正式运行，不自动启动矩阵。GPU1维修由独立任务负责。R001/R002冻结与原始失败保持。

## 早期v2 CPU交付历史

# A011 实际交付

worker v2、独立汇总及渲染已交付；最终57项source-stable CPU联合检查通过。

[最终证据](../../project/software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/worker_verification_v2_cpu/AT001/receipt.json)；[E010结果摘要](../../project/E010_gsm8k_six_model_completion/experiment_results/summary.md)。

适用：当前冻结源码与native_cache_call_parity_v2。原R001数值门失败保留，CPU验证不等于正式精度完成。已通过内部实际消息交付父负责人；无GPU/EDA/后代。
