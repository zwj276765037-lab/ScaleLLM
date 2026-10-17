# AT001 · cpu_preparation

本 AT 汇总真实 CPU 检查和后继源闭合，不是新原生运行。各 CPU 命令实际退出状态与可支持的时间范围见 [工具观察转录](evidence/actual_CPU_execution_observations.json)；没有记录逐命令起止 UTC，明确保留 null，不从文件时间补造。2026-10-16T17:34:05.284292+00:00 是交付记录的真实创建时间，不是验证命令或 Vivado 启动时间。

实际有界导出核查与 59 个 Python/Tcl 字面案例通过；初次父适配发现 E005 不存在独立 OPT 命令收据，改为引用已验证的真实原生日志 OPT 证明后，父链 CPU 检查通过。后续 RAW/S/P 术语桥接证明 selector 函数未变，未重跑全量导出或 59 案例。当前 physopt 参考 RAW=77360、排 GND/VCC 后 S=77246、归并 DSP 内部对象后的 P=77182。

最终源码 Python AST、Tcl info-complete 与 CLI help 通过；原生选择器/API、SLR2 区域展开/readback、完整 cut 和物理阶段尚未执行。父链 CPU 收据适用于其中明确记录的 adapter 修订，最终新会话仍会重新核验真实父链和当前图。

[集中交付与源码身份](evidence/prepared_entry_delivery.json)包含可执行命令与必要依赖，具体源保持在 agent/A006/slr2_input_locality。当前 E006 原会话保留；E007 未取 EDA 锁、未创建物理 started.json、未运行 EDA。run.json 的登记终态由主控依据本次真实收据更新，模板/计划不代替实际执行。

集中审核后的最新准备修订见 [修复交付](evidence/prepared_entry_delivery_runtime_fixes.json)。旧 807c1c67 manifest 和源字节已独立快照保留。literal selector 未改，59案例继续引用；bindable/REF规则实改，通过旧REF分布逐类核查及反例验证，不声称该逻辑 unchanged，也未重扫676MB导出。

受影响 CPU 检查有实际命令、起止 UTC、退出状态及最终源码快照：[CT001](evidence/runtime_fix_CPU_execution_CT001.json)为 17:47:46.374307–17:47:46.494420 UTC，exit0；补全 raw DSP/祖先拒绝检查后的[CT002](evidence/runtime_fix_CPU_execution_CT002.json)为 17:49:58.354965–17:49:58.477198 UTC，exit0。当前源码由 CT002 覆盖，原生 API/几何/宏与SLR政策、完整cut、切口时序及物理阶段仍未执行。实际后继必须先满足真实 E006 收尾与单EDA资源依赖。

尾部复核再收口两项：[当前尾部修订](evidence/prepared_entry_delivery_tail_fixes.json)拒绝失败/未执行/属性不支持的全局 origin 查询；切口 net 汇总不再把未知语义默认算成数据/控制。[CT003](evidence/runtime_fix_CPU_execution_CT003.json)于 17:55:32.710222–17:55:32.873539 UTC 完成新反例及语法检查，两步均 exit0，原 729ca173 修订保持快照。当前源码身份由 CT003 和最新 manifest 覆盖；CT002中未改的 REF/pin/对象对应检查按函数 AST 证据继续引用。未重扫原始导出、未重跑59案例、未运行原生 API 或 EDA。

A007已在[同一独立审结](../../independent_entry_review.md)追加最终 236718ab 修订审核：F01–F06/N01–N02 源准备缺陷闭合，审核范围内剩余源码缺陷为空。此结论只允许据真实前置条件推进原生资格，不代表 E006 已完成、资源已释放或 E007 实际实现通过。
