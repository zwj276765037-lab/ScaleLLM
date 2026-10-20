最新更正：主锚为wide final_accuracy_comparison.csv六checkpoint，Llama必须选Instruct；secondary截图CSV的base两行不属于用户新截图。见[映射](../actual_checkpoint_source_mapping.json)。此前12行/60显示值验证只针对secondary归档，不代表完整30行截图。

# 新表定位结果

已匹配 12 行 BF16/ScaleCode、60 个 MCQA 值，归档 SHA 全部与 source_manifest 登记一致。实际记录样本数：1838/299/500/10042/1267，split 为相应 validation/dev，指标为前四 `score_char_norm`、Wino `score_sum`。GSM provenance 明确 first300；逐题原始路径目前缺失，不能重验严格 EM。

三控制组 18 行只有部分历史 GSM 审计源指针，未定位完整原始 MCQA 记录。六模型 ScaleCode 实际为 `raw_kept_*`，高于 BF16 的单元格仍保留；另有明确历史 GSM 修复/重跑替换，不能与 display cap 混称。详见 [review.md](../review.md) 和 [历史合并审计](../historical_GSM_merge_audit.json)。
