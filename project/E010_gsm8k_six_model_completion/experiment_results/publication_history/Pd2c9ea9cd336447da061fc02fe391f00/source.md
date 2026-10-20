# E010：GPU0单卡恢复GSM8K补测

用户最新明确“先只用GPU0完成补测实验吧”。本次仅恢复M004/SM020/E010 GPU0补测及原每小时汇报，GPU1实验/诊断/维护保持暂停，M003由原硬件owner独立推进。

R003沿用已冻结单卡计划2e77661b…及15份runtime源，推理/QDQ/评分/数据协议未改。六模型×五配置，5-shot raw greedy strict EM，test1319题/组共39570题，context8192/new4096、BF16 eager、原生KV。native_cache_call_parity_v2和checkpoint_static_content_v1保持，全部30组全新smoke→pilot→formal，旧失败和准备行不导入。

服务器重启后内核/系统NVML580.178.04已匹配；启动器仅3处改为系统nvidia-smi查询，独立审核无阻断，真实预检通过。GPU0 UUID78b42905…独占单worker，CPU16–17/监督14–15；GPU1 UUIDd87ce710…排除。主机≥80GiB、原flock、无正常墙钟/静默强停保持。

用户最新明确停止当前ACC测试并要求修好推理速度。本轮只做GPU0性能诊断/修复与有限验证，不自动恢复完整ACC矩阵。R003已受控停止，原冻结源备份与原始证据保持，性能新来源另登记。


---
Published: 2026-10-18T11:00:57.624384+00:00
Publication: Pfec77bdc0ef54a788e1a0d3812b9c0aa
