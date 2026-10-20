# 历史精度表：相同ACC与量化反超BF16的只读审计（2026-10-19）

本轮角色为工程实现与验证，使用research-agent证据规范。输入为用户截图对应的literature_2048历史六模型/五配置结果。原始旧工程仅只读；本轮未运行模型、GPU、ACC、EDA或板卡，未控制yqh任务，没有修改旧表分数。

已完成父级CPU统计与两项独立审计：30组merged、31个实际贡献worker分片、599个历史文件清单。当前可以解释总分现象并指出证据缺口；不能从汇总分数还原逐题预测或确认异常因果。

**BF16并未普遍低于量化。** 对截图五个已测任务，按同模型/同任务比较4个量化方案与BF16，合计120项：量化更低96项（80%），更高18项（15%），相同6项（5%）。不把待测GSM8K纳入，不把含ARC-Challenge的旧CSV macro列冒充当前六项Avg。

少数反超不违反量化规律。量化扰动可能使接近决策边界的选项次序变化，既改对一部分题，也改错另一部分题；BF16不是该有限测试集0/1正确数的数学上界。Llama3.1 WinoGrande，BF16937/1267→A8W4 FP32 941/1267，即73.95%→74.27%，只净增4题。Llama3.2 ScaleCode WinoGrande866→877（+11题），BoolQ2568→2588（+20题）。这些净增不能单独证明能力提升、正则化收益或统计显著；需要逐题discordant counts/配对分析。

**本表相同分数确实是相同正确总数，不能仅解释为保留两位小数。** 已核所有13对显示相同的case/task组合（含同一组内多种配对），未舍入值对应的整数正确数均相同。总正确数相同不代表逐题答案、logits或有效权重相同：例如改对10题又改错10题，ACC不变。另有可能分数变化未跨argmax边界；本批缺逐题记录，无法区分这些机制。记录中量化attach数量/每op与各model_spec匹配，未发现直接标签/位宽串用证据，但attach汇总不是有效tensor内容的独立证明。

**DeepSeek BoolQ是需要复核的退化线索。** 实际BoolQ3270题中True/Yes2033、False/No1237。始终选择Yes的准确率恰为2033/3270=62.17125382262997%。BF16及三种W4配置未舍入分数均与此完全相同，A8W8为2032/3270。因此应重点检查答案偏置/评分适配，不能把62.17%完全不变直接当作量化鲁棒性证据。aggregate相等并不证明所有题都选Yes；同分的混合预测也可能存在。历史记录未保存逐题预测、候选似然或logits，故本轮无法确证。

DeepSeek历史评测为zero-shot固定raw prompt的候选loglikelihood比较，没有生成thinking再抽取答案；是否因chat/thinking格式不适配而低分，需要对照验证，当前只是假设。其BoolQ全部3270题记录tokenizer-boundary fallback，协议审计表明五case一致；是否存在fallback适配影响也不能仅凭计数断言，需逐题分数。

**Qwen2.5异常幅度不能直接归为量化噪声。** 已记录的A8W8 FP32/A8W4 FP16两组较低分都在CUDA_VISIBLE_DEVICES=1；BF16/A8W4 FP32/ScaleCode在0。且BF16/ScaleCode是前一天cached结果，另三对照是后一天新跑。方法与设备、时间批次混杂。设备记录只有ordinal和RTX A6000名称，没有physicalUUID，不能把9月ordinal1直接映射为当前的问题GPU或据此判故障根因。

Qwen2.5正确目标是28层×7投影=196模块，四量化配置的报告均符合；seed、batch、版本、checkpoint/data身份记录一致。但各worker没有独立运行代码hash、有效权重全内容/存储完整性记录；汇总只有一套code identity，目前保留源码有3项与其不同，说明不能用现存源码倒证全部旧运行，不能据此断言当时一定用了不同源码。历史记录的协议/身份一致性提供支持，仍不足以消除设备与实现混杂。

**结论与下一步范围。** 相同总分和偶尔小幅反超可以是正常的离散ACC现象；DeepSeek BoolQ多数类签名、Qwen2.5设备/批次混杂是具体待复核项。现有证据不能证明量化方案全面优于BF16，也不能直接判旧分数错误或GPU故障。本轮保持ACC暂停。后续如获恢复实验指令，应首先用同一可核physical GPU、同版冻结源、相同实际backend/提示/tokenizer/评分进行小范围配对复测，保留每题sample_id、gold、候选分数、预测、正确性及翻转方向，分别统计标签分布和错→对/对→错，再决定能否作为算法增益证据。不改变原始旧结果。

证据：

- [父级表统计与BoolQ数据SHA](table_statistics.json)
- [协议/逐题日志独立审计](protocol_review/review.md)及[原始审计JSON](protocol_review/review.json)
- [设备/方法/代码身份独立审计](implementation_review/review.md)及[逐case运行身份](implementation_review/qwen_case_runtime_identity.json)
- [原始汇总CSV](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/evidence/literature_2048/six_model_summary.csv)
