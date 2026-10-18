# E008 / AT003：PDU停机暂停与续接边界

用户明确要求服务器关机更换PDU，停止工程并等待通知。08:44:00.987566Z向已重核PID/start的本任务supervisor发SIGTERM；08:44:09.782954Z监督清理真实结束，native=-15/supervisor=125。14项终态收尾通过，所有已登记PID身份退出、唯一EDA锁释放；两个只读observer均真实exit0，无自动重试或后继AT。

已完成：同C01、b9dc一行兼容修复与独立delta、39运行归档源、144生产输入、完整restored preplace及独立审核。place实际进入Phase1.3时按用户要求停止，没有place/physopt/route完成，方法结论未评估；raw status的completed仅表示监督器已结束，raw物理helper的failed仅表示非零中断，不是方法反驳。

AT003报告中没有新DCP。不能恢复中途place。用户明确恢复后，先核验主机/工具/生产144/消费源/原合同与唯一EDA锁，再另开实际新AT，从已保存debug_materialized.dcp重新加载、同C01约束与完整资格后重做place→physopt→route。不自动使用E005基线physopt.dcp代替本次C01过程。

合法同C01恢复父DCP：project/hardware/vivado/reports/m002_E005_R004_AT003_current_CDC_bound_OPT_place_physopt/debug_materialized.dcp，396068466B / 8451b2a86885d5ebb7bcb58dc24c352ac442492425c174269f9a803bb39c202f。

消费包：agent/A006/E008_physical_xdc_fix/E008_entry/prepared_manifest.json，20262B / b9dcabf46f82b505e0a49de9a2c14eb013b7d71937e2d2805a9538f7545227bb。
执行绑定：.research-agent/decision_inputs/E008_R001_AT003_C01_physical_xdc_fix_execution_20261017.json，14144B / c8c3a3eaf6bb13d2315bf678eec2c7ea9eceb72a15f7773f64e409c03894454a。
PDU授权：.research-agent/decision_inputs/E008_user_PDU_shutdown_stop_and_pause_20261017.json。

真实停止总证据：[user_PDU_stop_closeout_20261017.json](user_PDU_stop_closeout_20261017.json)；[终态事实](terminal_facts.json)；[完整preplace](pre_place_closed_stage_facts.json)。全部原始源、日志、报告、数据和历史attempt保留。不生成bitstream，不开展GPU/板卡/PPL/ACC。当前保持暂停，必须等待用户新恢复通知。
