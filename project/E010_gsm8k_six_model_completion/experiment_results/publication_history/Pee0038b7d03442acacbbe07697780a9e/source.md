# E010：GSM8K 六模型五配置补测

M004/SM020，用户已授权两张GPU执行。主指标strict EM，完整test1319，30组39570生成；基线为同checkpoint BF16。

控制量：5shot冻结示例、raw prompt、greedy、8k总窗口/4096输出、BF16 eager、原生KV、固定QDQ实现；各任务均值只在六项齐备后计算。

[详细计划](../../software/0_Software/fix_experiment/source/gsm8k_completion_plan_20261018/plan.md)（路径从项目根读取）；有效配置 `project/software/0_Software/fix_experiment/source/gsm8k_execution_20261018/plan.json`，准备证据 `project/software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018`。
