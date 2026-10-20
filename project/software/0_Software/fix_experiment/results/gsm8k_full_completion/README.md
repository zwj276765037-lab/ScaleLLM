# GSM8K 全量补测总入口

范围：六个冻结模型、五种配置，两张 RTX A6000。正式 main/test 每格1319题，共30组/39570次生成。当前可回填的正式组数以各批独立验证报告为准；训练冒烟和pilot不能回填。

| 批次 | 协议/范围 | 状态入口 | 正式结果 |
| --- | --- | --- | --- |
| [R001](R001_gsm8k_5shot_8k/README.md) | 原cache-on/off数值资格门 | 首轮smoke自然失败，已收尾 | 0/30，未启动formal |
| [R002](R002_gsm8k_native_cache_v2/README.md) | 同评估数值口径；显式缓存调用验证v2 | 已自然失败收尾，smoke 6/30；[实际队列状态](R002_gsm8k_native_cache_v2/current_state.json) | 0/30，0/39570题，未启动formal |
| [R003准备决定](../../../../../E010_gsm8k_six_model_completion/gpu0_integrity_recovery_decision_20261018.md) | 原v2门＋运行时权重内容完整性；暂只分配GPU0 | 实现与审核中，尚未启动矩阵，全部阶段0/30 | 0/30，0/39570题 |

2026-10-18北京时间12:03更新（11:45汇报轮次）：10:45–11:45主矩阵新增0组、正式新增0题、诊断新增6次；本轮继续完成AT008–AT010，累计10次。GPU1加载后的目标BF16权重与原checkpoint差16345元素，GPU0同版17/17快照全等；独立审核支持暂不分配GPU1，不推断整卡硬件故障。A011实现全模型权重完整性，A010实现调度/独立汇总接受门及审核；新R003须重做全部smoke/pilot，旧6组不复用。[两卡诊断](preparation_20261018/native_input_diagnosis/analysis_AT008_AT010.json) · [E010最新状态](../../../../../E010_gsm8k_six_model_completion/experiment_status/summary.md)。

[执行配置](../../source/gsm8k_execution_cache_v2_20261018/plan.json) · [验证修订](../../source/gsm8k_execution_cache_v2_20261018/verification_revision.md) · [调度程序](../../exp/run_gsm8k_matrix.py)。新程序使用当前project/software；历史算法及原始结果保留。

自动阶段：30组训练smoke → 30组训练pilot与长度/显存/新进程复现检查 → 30组test全量 → 独立harness评分复算 → 六任务表格。各GPU同时最多一个worker，正常无墙钟或无输出强停。异常停止新任务，保存证据，等待活动worker自然收尾。

结果通过后：合格新批次的`merged/six_task_with_gsm8k.csv`和`merged/validation.json`提供数值/验收；`display/accuracy_table.md/.png/.pdf`提供展示。自动备份后更新用户指定旧results展示文件，旧CSV/manifest保持。Avg. = (PIQA + ARC-e + GSM8K + BoolQ + HellaSwag + WinoGrande)/6，使用未舍入分数，不含PPL。

GSM8K为5-shot raw greedy strict EM，其余五项沿用0-shot likelihood；不要把组合平均描述为统一0-shot。新缓存资格不等于证明cache-on/off逐值等价，原数值诊断仍保留。
