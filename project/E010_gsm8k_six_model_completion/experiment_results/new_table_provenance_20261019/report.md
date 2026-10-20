# 新截图精度表来源与可发表范围核查（2026-10-19）

用户问题：这页数据是否合理、会不会被质疑；用户记得完整评过但忘记原始位置，授权查找。本轮仅CPU读取与统计，不运行模型/GPU/ACC/EDA/板卡，不操作yqh，旧工程严格只读。

**判断：分数趋势和平均值在数值上可成立，归档也能支持部分来源；当前不能把整页表认证为全部标准full-test、同口径且可完整逐题重验的最终结果。** 应公开选用split、GSM子集/评分、实际checkpoint及证据缺口。不能因数值重复或少数配置反超就判错，也不能因表格整齐就判可靠。

找到的主锚：[final_accuracy_comparison.csv](/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/results/_summary/final_accuracy_comparison.csv)。父已选对六个实际checkpoint，逐一对比截图BF16/ScaleCode的6项分数与Avg，共84/84显示值完全相同；见[parent_archived_table_match.json](parent_archived_table_match.json)。该wide表包含更多checkpoint；secondary截图模型精度.csv的Llama base两行不是用户图中数值，不能直接拿它的12行全部背书。

用户图中Llama-3.1-8B的具体数值来自Llama-3.1-8B-Instruct，而旧归档还单独存在base Llama-3.1-8B且分数不同、GSM未评。表里应写明Instruct。Qwen2.5等也应保留完整实际checkpoint名字与版本。

五个选择题任务完整跑的是各自选定的split：

| 任务 | split | N |
| --- | --- | ---: |
| PIQA | validation | 1838 |
| ARC-Challenge | validation | 299 |
| OpenBookQA | validation | 500 |
| HellaSwag | validation | 10042 |
| WinoGrande | dev | 1267 |

因此“选择题完整跑过”的记忆有来源；ARC-c在这里不是standard test1172。MCQA前四指标score_char_norm，Wino score_sum，协议自述gyrot_aligned_lm_eval_style_zero_shot_full_split。不能把这页与后来literature_2048/新GSM8K 5shot严格EM协议直接合并。

**GSM8K并非1319题完整test。** 旧任务说明明确test first-300，逐model provenance和启动脚本max_samples300相互支持；全部30个截图GSM分数均与N300整数正确数兼容，27个不能由N1319的单次正确题数按常规两位小数产生（重复实验平均等另需明确证据）。粒度只作交叉核查，不单独用来证明实际采样数。原始生成jsonl目前未找回，故不能逐格重新计数或认证所有运行max_samples均实际执行。明确来源见旧[任务说明第36行](/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/fix_experiment/source/ScaleLLM_six_model_extended_dataset_experiment_task.md:36)及[启动脚本](/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/experiment/run_final_scalecode.sh:68)。

GSM现存关联scorer尝试####/boxed/numeric_answer/final-answer等模式，必要时取全文最后一个数字；不能直接叫当前固定harness的#### strict EM。历史GSM有后续修复/替换来源，包括Qwen2.5 chat_fewshot_cot_sdpa等。不同模型允许采用事先明确的适配，但同模型各配置的提示/解码/attention/答案解析是否完全匹配，需要实际运行记录证明；当前缺少原生输出与manifest，无法充分确认。

当前找到BF16/ScaleCode逐任务归档及GSM来源摘要；三种对照（A8W8 FP32、A8W4 FP32、A8W4 FP16）18行完整MCQA原始结果尚未定位。归档CSV中source_artifact/records_artifact指向的fpga_llm_project/results具体原生路径现不存在。GSM有kept/replaced/repaired注记，这些是来源线索，不能当重验通过。六个实际checkpoint的ScaleCode最终行均raw_kept_*，若干单项高于BF16仍保留，未见本次已审最终MCQA分数被cap到BF16的改写证据；不据列名指控修改数据。

父重新读图并算了全部30行Avg，均与六个显示分数的算术平均在正常舍入范围内；Qwen3 FP16 Hella应读72.02，初次手录错误及更正记录保留，不能将该手录错误指为表格均值错。见[screenshot_arithmetic.json](screenshot_arithmetic.json)。旧Avg正确并不能补足来源/协议缺口。

**可用范围与建议：** 本页可作为明确限定的历史阶段结果。发布前至少注明MCQA各split/N、GSM8K test first300与答案提取规则、实际模型版本、软件量化模拟属性，并补齐同模型五配置可配对的来源/逐题记录。若声称standard full-test GSM8K或与当前1319题strict EM协议直接比较，应完整补测1319并独立复算，而不是改标签或凭当前表格认证。当前ACC继续暂停，未自行补跑。

详细来源搜索与原生路径缺口见[独立定位报告](raw_search/review.md)、[完整JSON](raw_search/review.json)。已保存SHA、指向路径存在性、模型映射和控制组缺证清单。
