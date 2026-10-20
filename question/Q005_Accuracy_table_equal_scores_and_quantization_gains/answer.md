# Q005回答

已按原CSV/BoolQ标签及30组历史记录独立审计。120项量化对BF16的同模型同任务比较中，高18、低96、相同6；相同项整数正确题数确实相同。总分相同不等于逐题答案相同；少数反超可能由选项次序翻转造成，不证明能力或显著性增益。

DeepSeek四配置BoolQ恰为2033/3270，等于全Yes基线，但历史无逐题日志不能确认全Yes；Qwen2.5低分两配置与ordinal1完全混杂，且新旧缓存运行混用，缺少physicalUUID/逐run源与有效tensor证明，不能归因GPU1或量化噪声。现有case标签/位宽/attach汇总未见直接冲突。

完整数字、已知/推断/未知、原始证据和后续验证边界见[审计报告](../../project/E010_gsm8k_six_model_completion/experiment_results/accuracy_table_audit_20261019/report.md)。本轮仅CPU只读审计，ACC继续暂停，未动yqh/M003。
