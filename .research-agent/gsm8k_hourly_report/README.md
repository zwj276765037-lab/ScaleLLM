# GSM8K 每小时进度汇报

用户明确要求：“一小时汇报一次进度”。已设置本机 cron 每分钟检查到期时间，每3600秒唤醒当前既有工程对话；首次2026-10-18北京时间11:45。即使进展不变，每次也汇报阶段、完成组/题数、两卡任务、异常和下一步。补测完整完成并交付后关闭enabled；用户要求停止也关闭。

本会话未提供automation_update接口，采用本机调度与当前用户Codex控制通道。不是ChatGPT Scheduled里的原生任务。当前thread ID由CODEX_THREAD_ID及实时thread/read的cwd/name核实，没有重新绑定旧会话，没有联系其他会话或外部收件人。

实际连通性probe已被本对话收到；[安装与cron读回回执](installation_receipt.json)、[配置](config.json)、[逐次投递记录](receipts/)保留。接受投递不等于已经完成报告；定时运行结果以本对话实际消息为准。机器及Codex服务须运行；连接失败留证，投递结果不确定则停止重发避免重复，须核实后解除。

程序：project/software/0_Software/fix_experiment/exp/report_gsm8k_hourly.py。此程序仅负责向当前对话投递进度读取请求，不加载模型、不修改冻结实验源、不管理GPU/EDA进程。cron配置安装前原样备份在crontab_before.txt。
