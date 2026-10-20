# E010：准备核查结果

六checkpoint完整文件指纹全部匹配历史；协议CPU对照9项、worker CPU回归24项已通过；1319正式prompt逐字节对齐harness，六tokenizer共7914输入均<=4096（最大1658）。

原始证据：`project/software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/model_identities/validation.json`、`project/software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/protocol/cpu_parity_AT002.json`、`project/software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/protocol/input_preparation_AT001/tokenizer_audit.json`。GPU实际推理和精度结果尚待启动回执，当前可入表0/30。
