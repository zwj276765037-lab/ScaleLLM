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

物理阶段：R003/AT004已取得真实OPT命令成功receipt（exit0，37分32秒）及218,404,246-byte优化DCP。blackboxes从1降至0，no_clock530→0、内部未约束554→0；仍有PCIe/DDR三reset IO缺delay需对象级分类。优化后LUT828255（70.06%）、FF1021363（43.20%）、BRAM941 tiles（43.56%），DSP5451/URAM752保持。[OPT身份与资源](runs/R003/attempts/AT004_complete_recovery_preflight_opt_place_physopt/opt_command_facts.json)

OPT未布局时序：WNS+0.904ns/TNS0，WHS-0.814ns/THS-48989.652ns、992151 hold failing；PW栏目WPWS-0.012ns/TPWS-0.037ns、5失败，timing仍FAIL。默认DRC15914项均warning，无error/critical。[时序](../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/timing_opt.rpt) / [覆盖](../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/check_timing_opt.rpt) / [DRC](../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/drc_opt.rpt)

AT004于05:30:21 UTC受控结束，整体exit125/native-15、65.96分钟、峰值31.17GiB；未place，完整POST未结束。停止请求的OPT命令/DCP/BB0/clock证据已绑定；原status记录owned_survivors=[3161784]，终止后核查该PID及PGID均消失，补充清理receipt单独保留，不覆盖原status。后继只复用实际成功OPT产物，重取中断报告，不能宣称AT004整体成功或物理准入通过。

原生脚本另有显式implement_debug_core，本机手册及真实OPT证明OPT本身已自动实现debug。后继调用用于沿用原生顺序，并独立建立pre_place检查。实际OPT DCP嵌入约束已逐字节归档，不含OOC sl_iport/XSDB_CLK 3.333ns；hub范围只有BSCAN TCK50ns的create_clock。具体hub输入/输出/530扇出关系仍需live核验，不能只用零缺时钟数量判断周期正确。[阶段审核§5.13以后](runs/R005/architecture_review.md)


来源：339综合输入与45 DCP路径冻结；原INIT 162项XDC源/52读取记录保留。AT004恢复project实际cache read/write，两PHY均有no-cache-hit后的真实综合记录（121文件/65,898,981 bytes归档）；debug另存23文件/867,221 bytes、参数及生成DCP。5份被工具清理的worker OOC XDC原bytes/hash缺失，诊断派生产物可复用但不能称完整源重现；生成out XDC字节不证明主设计已采用，后继同OPT DCP恢复时补有效clock/约束/scope。后继实际临时project将恢复禁用cache。

告警边界：XDC puts仅打印的critical保留；两XPM宽匹配各含1 LUT4+1 FDRE，合法FF有效例外尚待定向报告；6条reset CDC及全局IO/复位仍OPEN。A004已用实际INIT LUT/连接限定关闭目标head-wave实例的独立初值及局部优先级疑点，其他样本、replica顺序等价和变换后适用性保留。[复位专项§6](runs/R005/reset_warning_review.md)

最终物理入口[R002/AT008 84项CPU](runs/R002/attempts/AT008_opt_recovery_debug_final_cpu/status.json)通过（78物理+6隔离）；原339源/45 DCP及真实AT004父链PASS，31原PID身份事后均不存在。R003/AT005于05:37:04 UTC实际启动，从同OPT恢复，不重跑OPT；实际布局前检查仍待结果。AT005实际恢复后hub输入/两输出/530扇出同mmcm_clkout5_1（20ns/50MHz），共享实际MMCM/BUFG来源，无OOC3.333ns残留；cache实际已禁用，预检issues空。新资源/时序与原OPT相同。AT005于06:01:09 UTC正常退出1、24.09分钟、峰值20.65GiB、无资源中止/遗留；唯一技术门失败为未分类CDC。实际Critical共8条，相比INIT精确4条保留、2条旧source移除、4条新增：2个core ready CDC10代表source变化及2个CDC11。两ready的原INIT/OPT源锥都含div_rst与calDone，实际源锥由6减至4个cell、两反相LUT移除及FDCE CLR极性反转支持等效折叠解释；仍需显式pin alias。CDC11定位为同UI的gate base与HostSplit多同步分支，尚无强制RTL重设计反例。[A004专项§7](runs/R005/reset_warning_review.md)。主控采纳A007精确8项及实际链/扇出/有效极性条件；命中时只允许诊断place，最终reset/CDC safety仍OPEN。工程准备门前有界补证并复用同身份完整报告，不重跑OPT。全部失败尝试与历史发布保留，无place/route或全局功能签核。


后继入口[R002/AT009](runs/R002/attempts/AT009_cdc_reset_diagnostic_reuse_cpu/status.json)93项CPU（87物理+6隔离）通过，真实339源/45 DCP与AT005→AT004完整来源核验通过。精确复用14份已完成报告，实际结构/极性/源扇出重新采集。R003/AT006于2026-10-15 06:18:56 UTC实际启动，从AT005的397273730-byte OPT DCP（SHA b209decf…71021）恢复；不重跑OPT，实际准入和place结果仍待。


---
Published: 2026-10-15T06:20:38.289929+00:00
Publication: P109264b009dc4b73a32204a1278059d3
