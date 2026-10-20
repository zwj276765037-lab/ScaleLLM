# 全1024篇数值误差与词表统计

范围为 Llama-3.1-8B-Instruct 的32层、固定真实文本前缀；web512/news256/reviews256，共103700位置、128256词表。没有任务ACC/PPL或自由生成结论。

- [最终Python图](final_precision.png) 与 [全部图源数据](final_precision_source_data.json)。PNG逐字节复制。
- [完整1024文档aggregate](integrated_aggregate.json) 保留每文档13项指标、32层传播及logit覆盖。13项读表见 [operator_error_summary.csv](operator_error_summary.csv)。前11项先在每文档跨预定义sites取最大tensor relative L2，再汇总1024文档分布，不能解释为第32层或所有scalar的合池误差。Attention四投影×32=128 sites，RoPE两路×32=64，其余各32。
- `whole_mlp` 固定同一MLP入口，参考内部重算动态量化；`fixed_residual` 固定同一second-residual base，只比较MLP变化后的和，均非自由轨迹整体归因。`gating_exit_loss` 比较实际LUT输出×Up的精确未舍入乘积与S32/F16共同出口，包含共享出口损失。最后两项final_hidden/logits才是配对完整轨迹。
- [逐层P50/P95/P99/max](layer_error_summary.csv) 包含32个decoder输出、final norm和logits；[旧传播说明](layer_propagation_summary.json) 保留原始说明。所有relative L2数值单位是百分数。
- [词表覆盖](vocabulary_coverage.csv) 的epsilon是原始logit单位，条件为绝对logit差不超过epsilon；score比例分母为13300147200，document比例要求一篇内全部score均满足，分母1024。
- [Top1统计](top1_summary.json)：102647/103700匹配、1053翻转，只表示数值Top1一致性。
- [TV摘要](TV_summary.csv) 明确分离位置等权与文档等权；[TV完整JSON](tv_aggregate.json)、[每位置CSV](per_position_tv.csv)、[每文档CSV](per_document_tv.csv) 全保留。TV fraction是概率质量，百分数为100×TV，不是relative L2。
- `provenance/` 保存正式session、输入roster与冻结计划。JSON中的原始绝对source paths与SHA原样保留；其中13项/coverage/Top1继承R005已冻结数据，经R006全部1024旧head指标和final hidden身份一致后合并，TV为R006实测。没有复制模型权重/原始tensor。

固定配额集合仅作描述统计，未把位置或词表项视为独立文档，未新增无条件置信区间。所有文件来源和副本SHA见 [package_sources.json](../package_sources.json)。
