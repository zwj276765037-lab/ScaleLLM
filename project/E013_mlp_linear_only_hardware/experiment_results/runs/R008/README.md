
历史原文已保留：[整理前原文](../../../../../.research-agent/navigation_history/8b0d0b6f9f0765e1584f789ca2aa6ff648269f39a15e75c2e5343dbbd9f50536.md)

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# E013 / R008 运行结果

未发现独立 run.md；原目录和收据保留。



## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_impl](attempts/AT001_impl) | completed | 未登记 | [执行收据](attempts/AT001_impl/result.json) · [input_manifest.json](attempts/AT001_impl/input_manifest.json) |
| [AT002_terminal_bus_skew_query](attempts/AT002_terminal_bus_skew_query) | failed | 未登记 | [执行收据](attempts/AT002_terminal_bus_skew_query/result.json) |
| [AT003_preliminary_bitstream](attempts/AT003_preliminary_bitstream) | completed | 未登记 | [执行收据](attempts/AT003_preliminary_bitstream/result.json) |
| [AT004_routed_constraint_qualification](attempts/AT004_routed_constraint_qualification) | failed | 未登记 | [执行收据](attempts/AT004_routed_constraint_qualification/result.json) |

## 本批问题与交付文件


## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->

Placed阶段实际闭合：place_design native0（1h37m19），saved511010742B DCP SHA cc92d8dcbc90d23b358627ccc7e2ea201b864cfb3092cbc58ddb1850459fa0cb。6份压力报告和14代表窗口原文在placed_pressure_reports_observation.json绑定；CLB SLR0/1/2=83.75/98.28/97.14%，新Placed与旧Physopt/-packthru不可直接相减。估计WNS+0.501与highly-congested警告并列保留，standalone physopt已实际启动，不预判route。

Physopt实际工件：physopt_checkpoint_observation.json及physopt_pressure_reports_observation.json绑定DCP5c8922a05f8ec15ad30fbc2453d2cc163b3c56b20ac52a99b67900f60b70be72/511009344B和6报告。5util原生DesignState=Physopt postPlace；congestion自己仍写Fully Placed/Placer Final Level，非route拥塞。工具明确netlist未改、pre-route估计WNS+0.465/TNS0，route已实际启动，最终质量待终态。

当前Route5.1 Global Iteration0：overlap节点504525→79281→13837→3269→1011，仍在正常迭代、尚非清零。首轮Global/Short新Level5与旧Level7为同类别估计差异，Timing均7；最终route/timing/DRC/CDC另判。10条bus-skew警告原名/首现行在route_bus_skew_warning_observation.json，不能因固定count的冗余位轨迹直接waive。

最新原生里程碑：route_design 2h02m23成功，0error/0critical/243warnings，routed.dcp665825940B/SHAcc34f49bef612472367f7d273596d09dede15128d3b72a2708507e4c6d6c7cc4已绑定routed_checkpoint_observation.json。0failed/unrouted/partial/overlap和Verification成功为实际布线证据；Phase14末CurrentTiming+.002/0/+.010/0仍需正式报告复核，裕量很小。当前正式route_status/timing_summary/DRC/CDC/guard及native/cleanup尚在生成，未完成完整验收；保留10bus-skew与4XPM可选报告边界。

正式Routed报告已完成：route_status全1687352 routable nets均fully routed、0errors；timing_summary setup/hold/pulse失败端点均0，WNS+.002/WHS+.010/WPWS0，详见AT001_impl/formal_timing_observation.json。最差路径GU lane格式计数至MLP CSR rdata[31]，2ps裕量；内部clock/constraint缺失0，外部PERST/DDR reset delay仍1/2。其余CDC/DRC/guard/终态cleanup尚在收集，不宣称完整物理signoff。

UTC23:27:20.753971 AT001_impl自然NATIVE_STAGE_COMPLETED：native0/nullstop/102输入无漂移、40历史owned最终0survivor、peak27.379GiB；39原生工件SHA见terminal_artifact_hashes.json，原quality overall FAIL保持（外部IO1/2及四可选XPM互斥参数错误）。GU37/Down缺席/DSP3072/meta448及Attention/clock/blackbox末图身份均PASS。AT002_terminal_bus_skew_query已UTC23:30:01.828390实际启动，只读同routed DCP补十busD/两reset链/两代表DSP/两SMC范围，不做综合或物理。分项结论见engineering_terminal_summary.json，完整物理验收待集中复核。

最新执行优先级（2026-10-25T00:35:02.240973+00:00）：用户要求先取得工程验证版bitstream。R008/AT002_terminal_bus_skew_query已于2026-10-25T00:30:51.805913+00:00受控SIGTERM结束（raw native=-15、stop=null、changed_inputs=[]），原因USER_PRIORITIZED_PRELIMINARY_BITSTREAM，不是超时/静默/资源保护；归属0survivor且锁释放，30原生工件及partial/未采集状态由priority_cancellation_receipt.json保全。四handshake skew/coverage、十个D及driver、两reset共8级、两DSP代表与d0 SMC已采；d1 SMC不完整保留，不改父AT001原verdict/quality。

R008/AT003_preliminary_bitstream已于2026-10-25T00:32:18.120194+00:00实际启动（PID/SID2623704、32逻辑CPU/192GiB、native8线程），唯一原生流程open原routed.dcp（SHAcc34f49bef612472367f7d273596d09dede15128d3b72a2708507e4c6d6c7cc4）后正常write_bitstream，不重新综合/布局/布线/完整报告，不降DRC或force绕过。目标hardware/vivado/reports/m006_gu_AT003_preliminary_bitstream/native_output/ScaleLLM_MLP_GU_only_ENGINEERING_VALIDATION.bit；当前RUNNING，不能称已生成。该文件标工程验证版，Max-DPO及外部reset签核未完成、原quality FAIL保留，禁止下载/上板；生成交付后继续已授权§12同routed独立副本约束修正。

工程验证版bitstream已交付（2026-10-25T00:45:47.009804+00:00）：R008/AT003_preliminary_bitstream原生native0/nullstop/changed[]/0survivor、锁已释放，verdict PRELIMINARY_BITSTREAM_GENERATED_SIGNOFF_OPEN。Vivado2025.2 write_bitstream原生4m00，25Infos/6Warnings/0CriticalWarnings/0Errors；全流程peak 25301385216B（23.564GiB）。文件 `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM_MLP_fix/project/hardware/vivado/reports/m006_gu_AT003_preliminary_bitstream/native_output/ScaleLLM_MLP_GU_only_ENGINEERING_VALIDATION.bit`，80159259B，SHA256 `66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47`。bitstream_manifest.json绑定原cc34…c7cc4 routed DCP、102输入、工具/生成脚本与原生结果；delivery_receipt.json补0survivor/锁释放。文件仅工程验证，Max-DPO/外部reset签核仍开放，原quality FAIL保留，未下载/上板/GPU。接续§12独立副本约束资格；若物理identity不变则证明已交bit仍对应同物理图，不默认再生成。

§12同routed副本资格已实际启动：R008/AT004_routed_constraint_qualification，UTC2026-10-25T00:53:00.753820+00:00，PID/SID2635964、32CPU/192GiB/8native线程；当前RUNNING。先导出完整ALL effectiveXDC和完整timing ALL重放，零差异byte/clock/12项原生STA指标/同域max-min极值比较，再按A021固定138直连合同精确补集隔离。保持SMC原cut、原DCP/102输入/已交bit字节不改；末尾6物理/网表成员SHA验证同物理identity并绑定66a3…cc47.bit，不默认再次生成。新入口19项CPU检查通过，仅CPU/语法，不称原生query通过。

AT004已于UTC01:18:30.927485自然FAIL：native1/nullstop/changed[]/0survivor/锁释放，peak23432990720B；取消前身份检查发现它已退出，未发送任何信号。真实首次拒绝是ddr0 data集合148074中148042落入原谓词、32未覆盖；名字在旧探针中未导出，不能猜类别，也尚未reset/read任何时序。原生已确认4scope34/34/35/35直连及原50clock/100同域极值；14,386,032基础through集合差68。导出XDC页眉含输出文件名是另一个已识别的比较器问题，尚未执行到该比较，不能把它写为AT004原生失败原因。

**当前运行**：R008/AT005_routed_constraint_qualification已UTC01:35:52.871377启动（PID/SID2662458），唯一EDA，32CPU/192GiB/8线程。新v2入口33项CPU检查原生0、stdout/命令/输入SHA/退出码已保存，仅CPU/语法。先双域≤512差集native/library完整取证，工件关闭后按预冻ADD_EXACT_CAPTURE/EXCLUDE_PROVEN_NONCAPTURE/UNKNOWN分类；未知/冲突会在时序修改前FAIL，不动态source。严格绑定同原cc34 DCP及AT004已关闭原STA100行，fresh50clock须与旧原始身份一致，不继承失败资格。修复工具注释比较为有效scope/有序可执行约束本体精确比较；精确NAME排除带等价scope快筛。zero replay保存独立DCP及六成员原始SHA；六SHA全同是充分证据，若不同不盲认物理改动或放宽。首轮SMC保持原cut；不改原DCP/102源/已交bit，不重综合或物理。未取得终态前不称修正通过。

AT005自然native1/nullstop/changed[]/0survivor：缺类probe的复合一元!不被Vivadofilter接受，尚无32角色事实/未改时序。按普通入口修复以!=/!~ DeMorgan替代并增正负集合partition；34CPU tests/native0。AT006于UTC2026-10-25T01:47:58.361065实际启动，PID/SID2669755；同原routed/bit与绑定原STA基线，唯一EDA32CPU/192GiB/8线程，当前RUNNING。


AT006已于UTC01:57:50.403258自然FAIL：native1/nullstop/changed[]/0survivor，peak20200513536B。原生已关闭全部64角色工件：ddr0/1各16个BITSLICE_CONTROL/PLL_CLK及16个RIU_CLK，IN/IS_CLOCK1，library input/clock1/data0，具有实际clock；系统Python继承Vivado PYTHONHOME/PYTHONPATH后stdlib版本不符，helper在角色决策前失败，任何时序未改。不是UNKNOWN真实角色被猜测排除，原FAIL保留。

**当前运行**：R008/AT007_routed_constraint_qualification已UTC02:00:57.300347启动（PID/SID2700936），唯一EDA，32CPU/192GiB/8线程。新v2入口38项CPU检查原生0（含实际64角色分类、绑定BITSLICE_CONTROL厂商时钟模型、矛盾角色UNKNOWN及污染Python环境下-I隔离），仅CPU/语法。系统Python调用统一-I，库方向input/output显式规范化；每次新原生流程仍先双域≤512完整取证，工件关闭后按预冻三分支处理，不动态source。严格绑定同原cc34 DCP及AT004已关闭原STA100行，fresh50clock须一致；零差异重放核有效scope/有序可执行约束、clock/12指标/同域极值，再执行精确138直连补集。zero replay保存独立DCP及六成员原始SHA；全同是充分证据，不同不盲认物理改变或放宽。首轮SMC保持原cut；不改原DCP/102源/已交bit，不重综合或物理。未取得终态前不称修正通过。
