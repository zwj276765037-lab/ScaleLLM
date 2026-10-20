# A013 结论

没有发现 case 标签与记录的位宽/scale/模块数量串用。Qwen2.5 预期 196 模块，四种量化均报告 196/每 op28。seed、batch、软件版本、checkpoint/data 元数据相同。

已证实的混杂：A8W8/FP16用可见设备1，W4FP32用0；BF16/reference为9月14缓存，三种对照为9月15新跑。没有历史物理UUID，无法映射今日问题卡。没有逐worker code hash；保留代码10份中7份与汇总相符，worker/protocol/merge三份不同；没有逐模块内容/当前完整性证明。异常因果保持 OPEN，不用量化噪声或GPU1故障直接解释。

证据及边界：[review.md](../review.md)、[逐case原始身份](../qwen_case_runtime_identity.json)、[源码身份](../aggregate_code_identity_review.json)。未执行模型或GPU，未恢复ACC。
