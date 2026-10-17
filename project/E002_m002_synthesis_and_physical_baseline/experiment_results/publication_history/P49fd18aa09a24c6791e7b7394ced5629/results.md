# E002：阶段结果

正式综合已完成：R001/AT001 create exit0；AT002 22个OOC和top synth及完整板级报告完成，2026-10-15 02:44:24 UTC结束，exit0，114.28分钟，峰值进程树RSS27.06GiB，无遗留进程。[综合事实](runs/R001/synthesis_stage_facts.json)及[终态](runs/R001/attempts/AT002_fresh_synth/status.json)保存原始来源。

| 板级资源 | 实际占用 | 比例 |
| --- | --- | --- |
| LUT | 841576 / 1182240 | 71.18% |
| FF | 1029313 / 2364480 | 43.53% |
| DSP | 5451 / 6840 | 79.69% |
| BRAM tiles | 945 / 2160 | 43.75% |
| URAM | 752 / 960 | 78.33% |

[资源报告身份](runs/R001/attempts/AT002_fresh_synth/observed_utilization_post_synth.json)。总量未超，不代表布局可实现。综合估计WNS+0.904ns/TNS0，WHS-0.814ns/THS-49355.641ns、1000183 hold failing；PW栏目5个失败，WPWS-0.012ns/TPWS-0.037ns，最差为PCIe Max Skew。当前timing FAIL，未布局估计不能代表物理收敛。[原时序](../../hardware/vivado/reports/m002_E002_R001_AT002_fresh_synth/timing_post_synth.rpt)

物理阶段：R003/AT002已保存实际project-init DCP；AT001属性格式、AT002 CDC查询、AT003 NAME/TOP复合判断失败均保留。AT004已完成统一恢复预检和完整INIT，实际TOP/PART/BOARD/core100/UI200正确，六CDC目标和三reset IO存在；INIT diagnostic_eligible=1，blackbox1、clock_coverage=PENDING_TOOL_DEBUG_MATERIALIZATION。原530 no_clock/554内部未约束均已核实属于两MIG debug链；6条CDC critical与综合集合一致，无新增critical。真实OPT正在运行，尚无完成receipt/DCP或place结果。

原生流程在OPT后另有implement_debug_core，自管入口需补齐。AT004 OPT本身已实际生成PHY及xsdbm debug核，不能据静态遗漏宣称OPT不会生成；本AT将在place前结束，新AT显式执行原生动作并建立独立pre_place检查。主设计实际clock与有效约束必须实测，零缺时钟计数也不能单独证明频率正确。[阶段审核§5.9–5.14](runs/R005/architecture_review.md)

来源：339综合输入与45 DCP路径冻结；原INIT 162项XDC源/52读取记录保留。AT004恢复project实际cache read/write，两PHY均有no-cache-hit后的真实综合记录（121文件/65,898,981 bytes归档）；debug另存23文件/867,221 bytes、参数及生成DCP。5份被工具清理的worker OOC XDC原bytes/hash缺失，诊断派生产物可复用但不能称完整源重现；生成out XDC字节不证明主设计已采用，后继同OPT DCP恢复时补有效clock/约束/scope。后继实际临时project将恢复禁用cache。

告警边界：XDC puts仅打印的critical保留；两XPM宽匹配各含1 LUT4+1 FDRE，合法FF有效例外尚待定向报告；6条reset CDC及全局IO/复位仍OPEN。A004已用实际INIT LUT/连接限定关闭目标head-wave实例的独立初值及局部优先级疑点，其他样本、replica顺序等价和变换后适用性保留。[复位专项§6](runs/R005/reset_warning_review.md)

物理入口最新已归档受影响CPU回归为[R002/AT006 55项](runs/R002/attempts/AT006_recovery_identity_preflight_cpu/status.json)。后继修复草稿尚非最终执行证据。全部失败尝试与历史发布保留；无布局布线/完整数值/板级签核结论。


---
Published: 2026-10-15T05:05:45.610770+00:00
Publication: P1ed6050e372a4ee2a875cae0aaa6d929
