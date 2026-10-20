# E010：执行协议

权威规范：`project/software/0_Software/fix_experiment/source/gsm8k_completion_plan_20261018/plan.md`；本次有效配置：`project/software/0_Software/fix_experiment/source/gsm8k_execution_cache_v2_20261018/plan.json`。

GPU并发按最新用户授权为2；CPU16–17/18–19。NVML不可用的限制保留，以 `project/software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/environment/cuda_preflight.json` 的双卡CUDA计算/显存回执确认本轮可运行基础条件，正式模型资格仍需smoke/pilot。

完整权重重新哈希均匹配历史；全prompt/评分/tokenizer独立CPU对照已通过。数值程序不改旧历史，输入原始证据不覆盖。原始运行放current fix_experiment/results/gsm8k_full_completion/R002_gsm8k_native_cache_v2，所有启动命令、GPU/CPU、源/数据身份和进度由常驻supervisor及worker落盘。

最终每格需1319唯一test样本并独立复算，辅指标不能代替strict；PPL不在范围。

R001原数值门failed与冻结源码保留。R002采用native_cache_call_parity_v2，见当前plan旁verification_revision.md；这不代表原cache-on/off全词表容差门通过。后处理顺序：独立harness复算全部正式样本→新表MD/PNG/PDF→备份后更新用户展示文件，历史CSV/manifest不改。
