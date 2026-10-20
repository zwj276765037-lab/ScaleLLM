# E010：GPU0单卡恢复GSM8K补测

用户最新明确“先只用GPU0完成补测实验吧”。本次仅恢复M004/SM020/E010 GPU0补测及原每小时汇报，GPU1实验/诊断/维护保持暂停，M003由原硬件owner独立推进。

R003沿用已冻结单卡计划2e77661b…及15份runtime源，推理/QDQ/评分/数据协议未改。六模型×五配置，5-shot raw greedy strict EM，test1319题/组共39570题，context8192/new4096、BF16 eager、原生KV。native_cache_call_parity_v2和checkpoint_static_content_v1保持，全部30组全新smoke→pilot→formal，旧失败和准备行不导入。

服务器重启后内核/系统NVML580.178.04已匹配；启动器仅3处改为系统nvidia-smi查询，独立审核无阻断，真实预检通过。GPU0 UUID78b42905…独占单worker，CPU16–17/监督14–15；GPU1 UUIDd87ce710…排除。主机≥80GiB、原flock、无正常墙钟/静默强停保持。


---
Published: 2026-10-18T09:58:36.210000+00:00
Publication: P5a1ce05052ff4b1bbc478828b24041a2
