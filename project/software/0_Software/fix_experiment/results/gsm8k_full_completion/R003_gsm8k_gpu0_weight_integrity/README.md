# R003：GPU0单卡完整性补测

用户最新指令“先只用GPU0完成补测实验吧”。2026-10-18已在重启后核对设备、15份冻结runtime源、两组既有准备资格及启动器独立适配审核，并真实启动单GPU0队列。全部30组固定GPU0，worker CPU16–17、监督器CPU14–15，GPU1实验/诊断/维护继续暂停。

实际启动与状态以launch_AT001.json、current_state.json及各worker manifest/summary为准。重启后系统驱动/NVML580.178.04匹配，改用系统nvidia-smi查询；旧私有工具保留。每小时提醒已在原定时器恢复，不创建重复任务。

冻结计划和15份推理来源未改；5-shot raw greedy strict EM、native_cache_call_parity_v2、checkpoint_static_content_v1保持。全部30组新smoke→pilot→formal，历史R001/R002和准备行不导入。正式共39570题，独立复解码/复算/身份和完整性全通过后才回填当前Workspace/project/software/0_Software/fix_experiment/results并计算六项平均。
