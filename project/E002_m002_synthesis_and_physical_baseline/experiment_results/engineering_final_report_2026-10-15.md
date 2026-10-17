# E002 工程阶段总报告 · 2026-10-15

本轮有界执行已结束。新的正式综合、OPT、debug物化和严格布局前诊断已完成；唯一一次完成pre_place恢复仍在两小时上限结束，没有完整place/physopt DCP，route未运行。M002物理与最终时序目标未完成，成本中止不反驳算法或代替设计失败结论。

## 阶段证据与适用范围

| 阶段 | 实际结果 | 原始来源 |
| --- | --- | --- |
| fresh create/synth | exit0；2026-10-15 02:44:24 UTC结束，综合114.279min、峰值进程树27.06GiB；339源/45实际DCP身份冻结 | [R001事实](runs/R001/synthesis_stage_facts.json) |
| OPT/debug/pre_place | OPT实际native0；完整7 async+4 AUX+3 HostSplit链、14网表导出、688实际BRAM写口、精确8 Critical CDC获得限定诊断资格；内部缺clock/未约束端点为0。正式reset/CDC安全仍OPEN | [AT008 pre_place](../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/pre_place_evidence.json) |
| 最终恢复入口CPU | AT012新增13恢复与6 managed隔离实际执行PASS；96未变legacy诊断测试复用AT011，不能说115项全部新跑；完整真实debug POST hook与AT008父链PASS | [AT012状态](runs/R002/attempts/AT012_post_debug_pre_place_recovery_cpu/status.json) |
| AT009恢复/live guard | 同e58d8970...debug DCP实际open8m16s；fresh native guard0/166s，BB0、DRC blockers0、clock groups verified；530个debug端点保持同50MHz关系。新的live回执与原POST/历史命令分离 | [恢复事实](runs/R003/attempts/AT009_completed_pre_place_recovery_place_physopt/pre_place_restored_facts.json) |
| AT009 place终态 | 09:41:02.527929→11:41:11.046467 UTC，managed124/native−15、stage_wall_timeout，无遗留；峰值32.278GiB。最后完成4.1.1.2 BUFG Replication，停止于4.1.1.3；无place/physopt成功receipt或DCP | [原终态及7身份复核](runs/R003/attempts/AT009_completed_pre_place_recovery_place_physopt/terminal_facts.json) |
| R004 route | NOT_RUN，未发出route_design，没有route attempt/DRC/完成率/时序或DCP；没有合格physopt父链 | [未运行原因](runs/R004/not_run_reason.json) |
| bitstream/板卡/GPU/PPL/ACC | NOT_RUN，本轮未授权 | [合同](../../../mission/M002_ddr_separation_and_timing_recovery/implementation_contract_2026-10-15.md) |

正式综合资源为LUT841576/71.18%、DSP5451/79.69%、URAM752/78.33%；OPT为LUT828255/70.06%、FF1021363、BRAM941、URAM752、DSP5451。总资源未超不代表已合法完成物理实现。

完整布局前报告仍为WNS+0.904ns/TNS0/setup0，WHS−0.814ns/THS−48989.652ns/hold992151，WPWS−0.012ns/TPWS−0.037ns/PW-skew5，timing FAIL。debug声明300MHz与实际50MHz的metadata不符原样保留；实际source/master/driver/period及530端点关系得到限定诊断检查，不能据此关闭正式debug或系统安全签核。

## 一次恢复的实测成本与停止边界

AT009 stage start→pre_place receipt为748.398s，AT008同口径为2629.541s，前置减少1881.143s（31m21.1s），进入place时保留107m31.6s。锚点为原managed start与原receipt最后写入mtime；它衡量完成布局前开销，不是精确native place开始时间，也不保证物理完成时间。详见[成本锚点](runs/R003/attempts/AT009_completed_pre_place_recovery_place_physopt/cost_time_anchors.json)。原partial GlobalPlace内存进度没有恢复。

AT009完成GlobalPlace及DetailPlace并推进到Post Placement Timing Optimization，但内存中的进度不是可恢复检查点。最后工具累计时间为1h38m37s，对应最后完整子阶段；不能将它误当完整place耗时或成功。原11:41:02.527929 UTC截止未延长；其后约8.5s为监督停止/回收收尾。原status保留before_reap=[3528459]、survivors=[]；全部6个受管PID/start_ticks及事先实测supervisor身份共7个均not_present。

没有新的完整物理点，按已约定边界停止place恢复链，不再相同place重试，不启动route。不补造被终止wrapper未生成的implementation_run.log、launcher成功或项目impl_1成功。

## 新自然观察与未关闭项

- Place30-1229：100个唯一可见cell与AT008可见集合相同，后续native suppression；不是完整影响总数，不能推断DDR1未受影响。USER_SLL_REG物理意图未满足，未据警告热改RTL/XDC。
- Place30-1995：DDR1 `c0_riu_clk` 与 `u_bufg_divClk_0` 的水平BUFCE_ROW programmable delay控制值cap4，原因BITSLICE_CONTROL_PLL_RIU MAX_SKEW。文字未给时间单位，不能称4ns或两个失败；原OPT正slack及PCIe的−0.012ns不同硬核规则不能代替当前物理结论。
- place内部BUFG insertion：10候选、inserted0/driver replicated0、10因placement/routing conflicts跳过；随后BUFG replication候选0。原始10个网对象已归档。Estimated WNS−1.884/TNS−1349.388是布局中间估计，不能当完整placed报告、独立后继physopt或route DRC失败。
- 原Physopt32-1132的部分高扇出可优化loads小于总fanout、XPM valid-exception API不可用、PW报告默认limit1及post-OPT辅助枚举NOT_RUN等限制继续保留；不把有限报告覆盖升级为完整分类。

准确对象与不可变日志前缀见AT009的[SLR警告](runs/R003/attempts/AT009_completed_pre_place_recovery_place_physopt/place_30_1229_warning_facts.json)、[DDR1时钟警告](runs/R003/attempts/AT009_completed_pre_place_recovery_place_physopt/place_30_1995_warning_facts.json)、[BUFG中间事实](runs/R003/attempts/AT009_completed_pre_place_recovery_place_physopt/post_place_bufg_opt_intermediate_facts.json)；有界架构解释见[R005 §5.30–5.33](runs/R005/architecture_review.md)。

## 最终源码与交付状态

五个live脚本与AT009冻结来源逐字相同，lane锁已释放，无活动EDA；[保全回执](runs/R003/attempts/AT009_completed_pre_place_recovery_place_physopt/final_live_source_preservation.json)可核查。Hadamard、ScaleCode、format05与接口/数值/100MHz合同未改变，旧工程只读保留。

预备的missing-physical续接草稿及v1审核字节已[持久留存](runs/R003/attempts/AT009_completed_pre_place_recovery_place_physopt/unexecuted_missing_physical_candidate/status.json)，installed=false，CPU回归/真实物理父资格/额外EDA均NOT_RUN。静态审核不代替执行；没有实际closed点，不安装、不运行该候选。当前源码中的AT012恢复分支只反映已经验证的本轮预放置恢复，不能据候选模板或bookkeeping声称物理阶段通过。

工程交付包括[R003完整过程](runs/R003/worker_report.md)、[R004未运行说明](runs/R004/worker_report.md)、本报告及不可变原始日志/身份。主控据这些证据集中评判SM006与M002；本报告不关闭最终时序、reset/CDC/release/事务安全或完整32层数值与板级验收。
