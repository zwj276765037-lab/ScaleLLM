# R003 finalizer 候选审核 AT001

结论：候选 ready=false，保留 generated_pending_review。现有89项消费者CPU资格有效；本轮只读检查源码、CLI参数与顺序，没有执行汇总、渲染、发布或追加测试。

不要把本候选复制到 R003/finalizer_readiness.json：该文件缺失时监督器进入 generated_pending_review；文件存在但 ready=false 会触发失败。

冻结 plan：`2e77661b67dc69ed6ae0b75d43580b75975f551cf5a683a498d510e9ba6b1426`。15个运行源与快照、当前 frozen_contract 身份一致。输出只允许当前 Workspace results；旧工程和历史原始CSV/manifests只读。

正式30组、每组1319题，共39570题全部完成并通过资格后，父按下列顺序执行；不得添加 --allow-partial：

1. `/home/user/anaconda3/envs/zhouwenjun/bin/python -B /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/exp/summarize_gsm8k.py --run-root /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/results/gsm8k_full_completion/R003_gsm8k_gpu0_weight_integrity --plan /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/results/gsm8k_full_completion/R003_gsm8k_gpu0_weight_integrity/frozen_inputs/plan.json --output /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/results/gsm8k_full_completion/R003_gsm8k_gpu0_weight_integrity/merged`

2. `/home/user/anaconda3/envs/zhouwenjun/bin/python -B /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/exp/render_accuracy_table.py --input /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/results/gsm8k_full_completion/R003_gsm8k_gpu0_weight_integrity/merged/six_task_with_gsm8k.csv --output-dir /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/results/gsm8k_full_completion/R003_gsm8k_gpu0_weight_integrity/display`

3. `/home/user/anaconda3/envs/zhouwenjun/bin/python -B /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/exp/publish_gsm8k_display.py --run-root /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/results/gsm8k_full_completion/R003_gsm8k_gpu0_weight_integrity --plan /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/results/gsm8k_full_completion/R003_gsm8k_gpu0_weight_integrity/frozen_inputs/plan.json`

三条命令间任何失败均停止；既有 merged/display/backup 不得覆盖或清理后盲目重试。候选环境将 Matplotlib/TMP 写入当前run，但 matrix 不消费这些额外环境字段，后续由父实际设置。

发布前必须核 validation.source_manifest_sha256、source_manifest 的 plan2e7766/formal_sources/frozen_contract 路径和哈希、30组accepted来源及代际资格、CSV/render和MD/PNG/PDF哈希。当前冻结 publisher 没有消费这些完整的来源/计划绑定，因此暂不开放无人审核自动发布；复算与渲染后由父完成来源核验再发布，属于已有授权内技术审核。

正式结果接受数为0；本候选只证明命令与既有程序资格，不能证明尚未完成的正式结果。完整阻断检查和源码SHA见同名JSON。
