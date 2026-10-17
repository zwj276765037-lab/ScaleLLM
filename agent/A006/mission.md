# A006 当前任务：SM010 / E006

SLR1资源、热点、连接与失败样本只读归因。独占E006/R001及agent/A006新脚本/launcher/工程报告，单EDA；A007独占R002，主控维护三摘要/goal/mission/results。用户已授权“火速去查明”，见[合同](../../mission/M002_ddr_separation_and_timing_recovery/slr1_attribution_contract_2026-10-16.md)。一次原physopt读取优先，无生产RTL/XDC/IP/构建或E005原证据修改，无新implementation/bitstream/板卡/GPU/PPL/ACC。资源CPU0–7/max8/nice5、RSS192GiB/内存48GiB30s/磁盘30GiB，正常无墙钟/静默强停。无后代；actual model未核实。真实接续[resume_E006.json](resume_E006.json)。

## E005及以前任务（历史）

# A006 当前阶段任务

SM009/E005：新可布性优化implementation；独占构建/监督/物理证据/CPU测试、E005协议/R002/R003/R004/R006及自身记录，R001仿真AT按与A009交接写入。唯一重EDA调度者，3个RTL/TB归A009，不覆盖；不分叉。见[当前执行合同](../../mission/M002_ddr_separation_and_timing_recovery/optimized_implementation_contract_2026-10-16.md)。期望gpt-6.1-sol/xhigh，actual unverified；单lane8CPU/nice5/192GiB与48GiB/30s/disk30GiB，无wall/静默强停。阶段内连续修复/验证，完成后自动新create/synth/place/physopt/route；无bitstream/board/GPU/PPL/ACC。

## E004 历史分析（已结束）

SM008/E004：物理证据分析和一次只读 physopt 诊断。所有权仅 E004/R001 与 agent/A006；生产实现不改，不运行 synth/opt/physopt/place/route/bitstream，不开后代。见[优化分析合同](../../mission/M002_ddr_separation_and_timing_recovery/routability_analysis_contract_2026-10-16.md)。runtime=/root/m002_build_verify；期望gpt-6.1-sol/xhigh，实际未独立核实；单 EDA/8CPU及资源保护继承合同。本次不绑定旧长期对话。

## E003 历史任务（已结束，不恢复）

SM007/E003完整implementation：唯一EDA执行者；拥有生产脚本/检查/测试、E003协议、R001入口核验、R002 place/physopt、R003 route及自身台账。新合同：[完整implementation](../../mission/M002_ddr_separation_and_timing_recovery/full_implementation_contract_2026-10-15.md)。runtime=/root/m002_build_verify，期望gpt-6.1-sol/xhigh，实际模型未独立核验；不分叉。

## E002及更早历史（非当前授权）

# A006 当前阶段任务

SM005/SM006 正式综合与物理实验；新工程create/synth准备。关联E002及[执行合同](../../mission/M002_ddr_separation_and_timing_recovery/implementation_contract_2026-10-15.md)。本轮实际runtime=/root/m002_build_verify，沿用期望gpt-6.1-sol/xhigh；实际配置未另核实。写入边界/资源见合同。

## 历史任务入口

# m002_build_verify

角色：engineering；SM：SM004；M：M002；实验：E001（SM004整合，覆盖SM002/SM003依赖）。

当前合同：[mission/M002_ddr_separation_and_timing_recovery/repair_contract_2026-10-15.md](../../mission/M002_ddr_separation_and_timing_recovery/repair_contract_2026-10-15.md)。实际本轮子任务：/root/m002_build_verify，未绑定任何长期工作对话。

所有权：Vivado脚本/清单/XDC及相关测试；R003、R002原始EDA尝试。资源：agent 1，不分叉；CPU轻量测试，EDA仅A006。工程与重工具边界见合同。

重要阶段通过实际collaboration消息通知主控；结果和源身份留在 E001/R003。最终主控整合三摘要。
