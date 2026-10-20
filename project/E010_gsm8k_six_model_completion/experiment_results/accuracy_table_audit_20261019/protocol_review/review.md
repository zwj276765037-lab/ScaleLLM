# literature_2048 协议与原始记录独立核查

A010 工程实验；CPU8–9，CUDA可见性为空，只读旧根，无torch/模型导入、GPU/EDA/进程操作或ACC恢复。已核30组merged、31个实际贡献的complete worker分片；599个原始文件的窄域清单及SHA见[文件清单](AT002/raw_tree_file_inventory.json)，[执行回执](AT002/receipt.json)。其中DeepSeek Reference-QDQ由两个recovery分片合并；失败尝试保留但未作为完成结果。

同一模型五配置的记录中，checkpoint fingerprint和完整文件身份列表（含tokenizer）相同，model identity仅created_at时间戳有差异。去掉case后的协议、context2048、zero-shot/full-split、数据split/行数/源SHA、task prompt/choice/target定义、metric策略及软件版本相同。四个量化case的attach模块数量/per-op计数均匹配各自model_spec，四case覆盖相同；BF16本来不做quant attach。这里验证的是历史记录的一致性，未重新加载权重或验证每个真实attached tensor。

指标为PIQA/ARC-Easy/ARC-Challenge/HellaSwag的acc_norm，BoolQ/Winogrande的acc；不能把六项都称为同一种ACC。Reference-QDQ的GLM/Llama3.1/Llama3.2/Qwen3记录缺失两个fallback计数字段，核心样本与截断统计仍相同；不能把缺字段默认为已验证为零。DeepSeek五case的完整truncation/fallback audit一致，BoolQ均记录3270个fallback documents/requests。

**未找到逐题预测、候选似然/logits或隐藏samples/cache文件。** 31份worker的lm_eval_raw均无顶层samples/逐题响应字段；599文件窄域清单无sample/cache/prediction/logit/sqlite候选。results.samples和n-samples只是样本总数，fewshot_config.samples=null也不是预测。现存旧worker可见log_samples=False，audit请求cache_requests=False；HFLM logits_cache=True不能当作已落盘的逐题logits。故相同ACC只证明相同答对总数；无法确认它们逐题相同、翻转几题，或DeepSeek是否全选yes。父级另核的多数类基线可以作为异常线索，不能由aggregate反推所有预测。

DeepSeek记录的是原始固定模板、zero-shot multiple-choice候选loglikelihood评估，不是生成thinking再抽取答案。缺chat/thinking可能是待检验的协议解释，但没有对应对照，也没有逐题分数/输出能证明这是低分原因。量化改变分数后可能同时修正部分错误并引入新错，因此少量ACC高于BF16不违反数学规律；本批缺逐题输出，不能量化这两类变化或证明显著改善。

**来源边界：** 当前旧根worker/protocol文件SHA与汇总experiment_manifest所记SHA不同；未发现由本审计持有的对应历史冻结源码。因此现存log_samples=False代码只能作静态佐证，直接缺证结论来自实际保存的worker JSON和文件清单。源/硬件身份的进一步判定由A013单独负责。本审计不重算父级负责的表统计和BoolQ标签分布。

详细字段比较及输入SHA见[review.json](review.json)、[逐case证据](AT002/case_protocol_evidence.json)。首轮审计因一个recovery分片未记tokenizer_boundary_policy而KeyError，原回执/脚本保留；AT002将缺项记unknown后完成，同一授权目录，没有扩大搜索。
