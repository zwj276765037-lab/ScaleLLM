# GSM8K 双GPU补测 R001

**终态 failed，2026-10-18T02:04:05Z，活动worker已自然收尾。BF16 smoke完成，两个量化case未过原logits门；未启动pilot/formal。后继R002独立冻结，不复用本批结果。**

本批6模型×5配置，正式每格1319题。常驻队列按 smoke → pilot → formal 推进，未过资格门不启动下一阶段。

- [实时队列状态](current_state.json)：实际阶段、GPU、PID、已完成/失败组及更新时间。
- [原生启动回执](launch_AT001.json)；[启动资格](prelaunch_readiness_AT002.json)。
- [监督器输出](supervisor_AT001.stdout.log)；[错误日志](supervisor_AT001.stderr.log)。
- 每组原始输出在 `smoke|pilot|formal/<模型>/<配置>/ATxxx/`，逐题 generation.jsonl、scores.jsonl、summary.json 和 manifest.json。

GPU0/1分别为两张RTX A6000，CPU16–17/18–19。NVML管理查询不可用，CUDA双卡BF16计算与显存已验证；本批以CUDA显存/逐题时间记录资源。未修改系统驱动。

正式结果通过独立复算后放 `merged/`；smoke/pilot分数不填论文表。后台监督器是实际已启动进程，状态以JSON中PID/更新时间和原始worker输出为准；本文件本身不是运行心跳。
