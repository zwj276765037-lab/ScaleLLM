# GSM8K 双GPU补测 R002

**终态 failed：2026-10-18T02:32:11Z，6/30组smoke完成；Llama3.1 BF16首提示调用一致性门未过。已自然收尾，pilot/formal未开始。后续受控诊断另存，保留本批冻结代码。**

2026-10-18 北京时间10:24:47已实际启动，监督器PID271368。初始两卡分别执行BF16/A8W8；状态随队列推进，以current_state.json为准。启动资格为最终57项worker/汇总与49项调度CPU回归。

[真实启动回执](launch_AT001.json) · [启动资格和证据哈希](prelaunch_readiness_AT001.json) · [已配置自动独立复算与表格更新](finalizer_readiness.json)。

六模型×五配置，正式每格1319题，共39570次生成；两张RTX A6000各一个worker。

- [队列状态](current_state.json)：阶段、活动PID、已完成组、失败与更新时间（真实启动后生成）。
- [冻结执行计划](../../../source/gsm8k_execution_cache_v2_20261018/plan.json)；[验证修订与证据](../../../source/gsm8k_execution_cache_v2_20261018/verification_revision.md)。
- `smoke/`：每格4题训练冒烟；`pilot/`：每格32题训练预跑；`formal/`：每格1319题test。每次尝试独立 AT 目录保存原始文本/token/逐题评分/manifest。
- 所有30组smoke完成后自动pilot；资格、长度和显存门通过后自动formal。失败时停止新发任务并等待已运行worker自然结束。
- 全部正式结果独立复算通过后，`merged/`保存六任务CSV及验证报告，`display/`保存含GSM8K和平均ACC的MD/PNG/PDF。正式数据未完整时不填平均值。

两卡UUID固定分组，CPU16–17/18–19；监督器CPU14–15。正常任务不按墙钟或静默超时强停。NVML仍不可用，以CUDA显存和逐题吞吐为资源证据。JSON记录更新不代表本对话会自动发通知。

旧批[R001](../R001_gsm8k_5shot_8k/README.md)已在smoke数值门自然失败；原证据和冻结源保留，不混入本批。
