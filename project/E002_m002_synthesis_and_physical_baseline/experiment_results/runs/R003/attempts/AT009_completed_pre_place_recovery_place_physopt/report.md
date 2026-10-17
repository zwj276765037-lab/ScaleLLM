# AT009 · 已完成pre_place状态恢复后place/physopt

execution=running；真实开始2026-10-15T09:41:02.527929+00:00，固定截止2026-10-15T11:41:02.527929+00:00。exec19950、supervisor3528457、leader3528459。显式--pre-place-report指向AT008同397261751B/e58d8970...debug_materialized DCP。当前为实际恢复；尚无本次live guard、place或physopt完成证据。

AT012已新增13恢复+6managed测试通过，96不变legacy复用；真实完整debug POST及祖先父链通过，五脚本安装身份冻结。新AT继承原完整pre_place测量，历史opt/debug命令receipt保持原位置；只实际执行fresh bounded restore sanity/native DRC→place→physopt。没有重新执行OPT/debug及全套pre-place POST，也不继承原partial placement内存进度。

1EDA、affinity0–7、nice5、threads8、RSS≤192GiB、MemAvailable≥48GiB/30s、disk≥30GiB，2h不延期。若没有新的完整物理DCP，不重复place；若得到真实完整DCP，只恢复其缺失阶段。reset/CDC安全OPEN；无route父链/bitstream/板卡/GPU/PPL/ACC。


实际恢复成功：open_checkpoint elapsed8m16s，restored_preflight空问题；fresh m002_live_pre_place_restore native0，166s、BB0/DRC blockers0/clock_groups verified1。check_timing内部缺clock/未约束端点/重复clock等均0，允许reset IO1in/2out；hub输入/2输出/530C同50MHz mmcm_clkout5_1、原source/master/driver/period匹配，300MHz metadata冲突仍保留。新pre_place phase=restored_completed_pre_place，历史POST和本次live guard明确分离。日志Command:place_design及预条件DRC0Errors已实际出现；无新opt/debug receipt、无place/physopt完成receipt或DCP。

真实成本：本次stage start→pre_place receipt 748.398s，AT008同口径2629.541s，前置开销减少1881.143s（约31.35min）；进入place时余107.53min。实际new native guard166s，open8m16；数据基于各自stage start和receipt文件mtime，见pre_place_restored_facts.json，不代表完成时间保证。固定11:41:02Z截止不变。


## 原始终态与本阶段结束

AT009于2026-10-15T11:41:11.046467+00:00按原2h上限结束，managed124/native−15、stage_wall_timeout；owned_before_reap=[3528459]、owned_survivors=[]。资源记录全部6个PID/start_ticks以及预先实测supervisor3528457/start916982212，共7个确切进程身份均已不在。exec19950完成124，峰值树RSS32.278GiB。原status保留，不补造被终止wrapper未生成的implementation_run.log或launcher success。

最后完整原生子阶段为Phase4.1.1.2 BUFG Replication/checksum2673ec0ef，最后工具累计1h38m37s；停止于4.1.1.3 Post Placement Timing Optimization。无place/physopt成功receipt、无place.dcp/physopt.dcp，closed_physical_points为空，无route父链。原始final log128349B/SHA b3029451d0e077b22066341bf955f166b91b5c0ad4be334f1f018d7699f99242，来源与7个身份核验在terminal_facts.json。

本次前置开销已实测减少31m21.143s，但仍没有完整物理恢复点；不将内存中已完成GlobalPlace/DetailPlace当可恢复DCP，不追加预算，不重复place。R004 route NOT_RUN。私有missing-physical候选与v1审核字节已持久归档unexecuted_missing_physical_candidate，installed=false、CPU回归/真实物理父链/额外EDA均NOT_RUN。final_live_source_preservation.json确认五live脚本与AT009 stage_sources完全一致、新候选测试未安装、EDA lane锁已释放。

新自然观察保留：Place30-1229本次100唯一可见cell与AT008相同且后续抑制，不是完整总数；Place30-1995两DDR1网的水平BUFCE_ROW programmable delay cap4无时间单位，不能说4ns或两个失败；place内部BUFG insertion10候选全部因placement/routing conflicts跳过，inserted/replicated均0，后续replication候选0。Estimated WNS−1.884/TNS−1349.388属于布局内部中间估计，不是完整placed/route报告、独立后继physopt或route DRC失败；见对应warning/intermediate facts及R005 §5.32。formal reset/CDC safety OPEN、timing/physical signoff未完成。
