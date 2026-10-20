# 新表原始来源：最终定位结论

正确主锚：`/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/results/_summary/final_accuracy_comparison.csv`。按DeepSeek、GLM、**Llama-3.1-8B-Instruct**、Llama-3.2-3B-Instruct、Qwen2.5-7B-Instruct、Qwen3六checkpoint选行；父级已在`parent_archived_table_match.json`核84/84个BF16/ScaleCode显示格。旁边的`截图模型精度.csv`只保存这组中的其他10行，它的Llama两行是base，不能当用户截图的Instruct。最初两个anchor匹配的发现与纠正前报告均保留；准确映射见[actual_checkpoint_source_mapping.json](actual_checkpoint_source_mapping.json)。

逐模型`accuracy_bf16_fullsplit.csv`/`accuracy_scalecode_fullsplit.csv`是仍可读取的逐任务归档。正确六checkpoint对应60条MCQA归档行保存在[actual_screenshot_MCQA_archive_rows_AT002.json](actual_screenshot_MCQA_archive_rows_AT002.json)，追加Instruct两份归档SHA也匹配source_manifest。原始记录真实声明的样本数为PIQA validation1838、ARC-Challenge validation299、OpenBookQA validation500、HellaSwag validation10042、WinoGrande dev1267，records_complete=True，协议`gyrot_aligned_lm_eval_style_zero_shot_full_split`；主指标前四score_char_norm、Wino score_sum。**“完整选择题split”有归档依据，ARC这里是validation299，不能等同标准test1172。**

GSM8K由另行并表加入。逐模型provenance明确first300，关联脚本默认和sh命令均max_samples300，不是完整test1319。source/records路径指向`fpga_llm_project/results/0_Final_results/.../gyrot_aligned_accuracy/`，GSM修复记录指向`fpga_llm_project/results/All_results/...`，这两个原始results根目前不存在。故没有本次可读取的原生逐题JSONL/CSV来重数GSM、重验各次解码、预测或严格EM。旧关联scorer采用多种答案标记并可fallback全文最后一个数字，再做归一化数字字符串相等；不能直接称为当前harness的#### strict EM，也不能无raw就确证每格实际采用同一scorer。

三种量化控制配置共18行，**尚未定位完整MCQA原始汇总/个体记录**；仅有历史GSM审计值和源指针，见[actual_control_18row_source_status_AT002.json](actual_control_18row_source_status_AT002.json)。BF16/ScaleCode定位成功不能为余下18行整体背书。未继续盲搜或扩大实验。

六实际checkpoint的ScaleCode最终Display Cap Status均为raw_kept_*；其30个MCQA值与已读归档raw fraction一致，高于BF16的GLM OBQA/Wino、Llama-Instruct ARC/Wino、Qwen2.5 Wino、Qwen3 PIQA仍保留。没有从这些最终行发现裁剪至BF16的数值修改证据。历史GSM确有不同运行/修复来源替换，例如Qwen2.5 BF16 NA*→90.67/ScaleCode NA*→88.00（chat_fewshot_cot_sdpa），Qwen3 ScaleCode84.67→88.67、Llama3.2 ScaleCode62.67→67.33；DeepSeek ScaleCode60.67来源注记含fixed-point-tail修复、300/300。应保留运行/来源边界，不能凭列名指控capping，缺失raw也意味着这些修复尚不能在本次重验。

详细字段、源路径存在性、历史替换注记、输入SHA与限制见[review.json](review.json)、[receipt.json](receipt.json)。CPU8–9/empty CUDA，无torch/模型/GPU/EDA/进程操作，旧文件只读，E010正式完成数未因此增加。
