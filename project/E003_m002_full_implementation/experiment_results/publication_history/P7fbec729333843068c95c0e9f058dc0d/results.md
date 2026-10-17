# E003：阶段结果

129项CPU检查已通过：14项新profile、13项既有恢复、6项隔离和96项既有物理检查本次均执行。真实339综合输入、45 DCP路径及AT008完整debug/pre_place资格通过；5份生产/测试文件已安装，Tcl、RTL、XDC不改。主控独立核5份安装后hash一致。[检查结果](runs/R001/attempts/AT001_full_implementation_profile_cpu/validation_result.json)、[实际源资格](runs/R001/attempts/AT001_full_implementation_profile_cpu/actual_source_qualification.json)、[安装身份](runs/R001/attempts/AT001_full_implementation_profile_cpu/installation.json)。

本次实际Vivado于2026-10-15 12:22:11.492419 UTC启动，已完成原AT008完整debug/pre_place恢复及本次live guard，已实际进入place_design。当时尚无新的place/physopt/route完成结果，后续进展见下。[实际启动](runs/R002/attempts/AT001_full_pre_place_restore_place_physopt/actual_eda_started.json)。

启动时记录的监督起点12:21:48.608023 UTC及12h/24h预算属于原配置；用户随后明确取消固定墙钟强停。无wall监督已于12:32:57 UTC实际接管，主控直接核旧supervisor为T、当前worker/Vivado启动身份连续、新watchdog活跃；旧timer不再执行，后继route同样无wall。8CPU/nice5/原资源保护保持。[实际预算](runs/R002/attempts/AT001_full_pre_place_restore_place_physopt/effective_budget.json)。

基线来自[E002总报告](../../E002_m002_synthesis_and_physical_baseline/experiment_results/engineering_final_report_2026-10-15.md)：综合、OPT/debug/pre_place已完成，原AT009无完整布局DCP，不能继承部分布局。新授权与E002旧政策、原失败均分开。负时序可继续诊断布线，完整物理与最终时序/安全验收分别判断。无bitstream/板卡/GPU/PPL/ACC。

无wall接管经过两个实际隔离CPU进程自检，未修改冻结生产代码或原启动合同；新补充身份独立绑定。实际native计算进程3678249/start917949130/PG3677864在接管后CPU计数增加17749 ticks，保持同一运行。[接管回执](runs/R002/attempts/AT001_full_pre_place_restore_place_physopt/supervision_handoff/handoff_effective.json)、[连续性](runs/R002/attempts/AT001_full_pre_place_restore_place_physopt/supervision_handoff/post_handoff_continuity.json)。

本次live guard native0/174秒，blackboxes0、DRC blockers0、clock groups verified；内部no_clock/未约束/multiple/generated/loops均0，原3个reset IO缺delay保留。实际hub关系及530端点通过限定诊断，300MHz声明与50MHz实际的旧元数据差异保留。12:37:41 UTC不可变日志前缀已记录真实place命令及Phase1.1完成，精确native启动时刻未取得。主控核place-start事实所引用8项小证据身份一致。[布局启动事实](runs/R002/attempts/AT001_full_pre_place_restore_place_physopt/place_started.json)。

14:36:01 UTC实际place_design命令成功，native Tcl0、耗时2小时1分35秒；主控直接核原生receipt及成功日志。随后原生write_checkpoint成功，place.dcp已生成，14:39观察时阶段POST仍在生成，place_result的completed=0是未完成状态，不预填正式报告通过。独立physopt/route尚未执行。[实际place命令](../../hardware/vivado/reports/m002_E003_R002_AT001_full_pre_place_restore_place_physopt/place_command_result.txt)。

新增Place46-14高拥塞告警；过程拥塞表全局及SLR0各方向Global/Long/Short Region Size均64×64，SLR1/2为16/32/64混合。Region Size不是利用率或失败数。过程WNS−1.858ns不是正式placed/route时序结论。A007已独立核告警范围，不能据此判不可布或归因某模块；正式拥塞/SLR/时序报告及实际route结果待产生。原USER_SLL_REG、DDR1 delay capped4、10个BUFG候选跳过仍保留，不热改策略。[独立审核§4](runs/R004/architecture_review.md)。

工程已对closed place.dcp完成全包CRC、文件稳定性及part/top/board/Vivado2025.2身份检查：579080094 bytes，SHA256 `37591435c8f95383a0910978b986c035a102c762b24b69b76e59b63d49e905f7`。主控另独立核阶段facts的原生命令、冻结日志快照、无wall配置3项小文件身份；未重复扫描大DCP。[布局检查点事实](runs/R002/attempts/AT001_full_pre_place_restore_place_physopt/place_checkpoint_facts.json)。


---
Published: 2026-10-15T14:41:33.094907+00:00
Publication: P82bfa439729c47ea8dbb24d4c4c5c5be
