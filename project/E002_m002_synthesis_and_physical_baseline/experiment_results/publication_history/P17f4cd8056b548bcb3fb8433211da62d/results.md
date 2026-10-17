# E002：阶段结果

AT001 fresh create已完成，exit0，约330秒，峰值进程树RSS2.74GiB。AT002的22个OOC和top synth均结束并生成DCP；完整board已link并产出报告；AT002于02:44:24 UTC完成，native/overall exit0，114.28分钟，峰值tree RSS27.06GiB，owned_survivors=[]。正式综合执行完成，时序/覆盖仍不通过。

[完整板级资源](runs/R001/attempts/AT002_fresh_synth/observed_utilization_post_synth.json)：LUT841576/1182240（71.18%）、FF1029313/2364480（43.53%）、DSP5451/6840（79.69%）、BRAM945/2160 tiles（43.75%）、URAM752/960（78.33%），聚合容量未超。

[综合时序](../../hardware/vivado/reports/m002_E002_R001_AT002_fresh_synth/timing_post_synth.rpt)：WNS+0.904ns/TNS0；WHS-0.814ns/THS-49355.641ns，1000183 hold failing；WPWS-0.012ns/TPWS-0.037ns，脉宽检查栏目下5个失败；最差为PCIe硬核Max Skew，不能称已证实高低电平宽度不足。未布局估计，timing FAIL，不能代表物理收敛。

[覆盖检查](../../hardware/vivado/reports/m002_E002_R001_AT002_fresh_synth/check_timing_post_synth.rpt)：三组clock非空互斥，但no_clock530、unconstrained_internal554均集中于两MIG XSDB/arbiter；唯一blackbox是工具dbg_hub_CV占位。1个输入/2个输出缺delay对应PCIe/DDR reset IO，需对象级分类。[CDC](runs/R001/attempts/AT002_fresh_synth/cdc_critical_rows.json)有6条复位相关critical，不能以时钟存在宣告覆盖安全。[DRC](../../hardware/vivado/reports/m002_E002_R001_AT002_fresh_synth/drc_pre_impl.rpt)15927项均warning，无error/critical。

原339输入保持冻结；[检查点身份](runs/R001/attempts/AT002_fresh_synth/synth_checkpoint_bindings.json)覆盖23份run产物及22份实际消费IP DCP，复制品hash逐一一致。XDC puts critical已核实只影响打印，保留原severity；2个XPM无效约束端点范围与29条生产RTL复位warning仍需网表核查。

[R005审核](runs/R005/architecture_review.md)明确：实际工具身份确认后允许诊断init/opt物化debug hub，coverage/blackbox保持PENDING；place前必须重验实际黑盒、no_clock和约束覆盖。新M002物理入口保留全部综合身份与实现专用约束，不写伪S3 PASS。物理入口最终[47项CPU测试](runs/R002/attempts/AT004_physical_diagnostic_final_cpu/status.json)通过，原339输入/45 DCP再次验真。R003/AT001在launch前因属性值格式错误退出1，等价0/1修复后47项回归通过。AT002实际project link完成并保存init.dcp；INIT报告仍有唯一工具dbg_hub_CV、530 no_clock和554 internal端点，A007逐对象验证全部属于两MIG调试链，支持限定诊断OPT。162项当前XDC字节核验一致，真实implementation-only约束已加载；hub属性300MHz与实际50MHz不一致，保持待OPT实际判读。

AT002于03:59:05 UTC结束，exit1，35.89分钟、峰值进程树RSS22.11GiB、无遗留/资源中止。原因是INIT POST探针无法定位指定CDC复位引脚；27类warning寄存器探针已产出，后续定向cone未完成。现保存失败和真实project-init DCP，A006定位并修复查询，准备带完整来源继承的新尝试；尚未运行OPT/place/route，不能把查询失败当RTL反证。

恢复入口的[R002/AT005](runs/R002/attempts/AT005_checkpoint_recovery_cpu/status.json)53项CPU测试通过；原339源/45 DCP、162约束源/52实际读取记录复核。测试后3处仅settings scope/HAP环境记录差异由A007逐行核查，AT003最终字节另行归档，不覆盖AT005。R003/AT003于04:09:35 UTC启动，从真实project-init DCP恢复；原AT002及impl_1仍保留失败状态，新execution_mode为checkpoint_restored_commands。尚无OPT/place/route结果。

AT003检查点读取成功（open_checkpoint约9分钟），时序与约束均从二进制归档恢复；随后入口的PART/NAME复合身份判断失败，导致04:19:04 UTC退出1，9.49分钟、峰值20.64GiB、无资源停止/遗留。尚未查询six targets或执行OPT。DCP包内真实top/part/board/tool正确；当时未保存live属性，不能区分具体触发字段，使用NAME推定逻辑top本身亦不成立。A006修复身份字段并集中收集后再判只读预检，避免每一API假设触发独立重载；失败证据保留。

[R002/AT006](runs/R002/attempts/AT006_recovery_identity_preflight_cpu/status.json)统一恢复预检55项CPU通过；原339/45及162/52身份再次核实。R003/AT004于04:24:24 UTC真实启动，前置收集所有可得属性/关键对象，再汇总身份和结构技术门；尚无实际预检或OPT/place结果。前三次已结束尝试累计45.81分钟，原始失败保留。

AT004实际集中预检通过，restored_preflight.tsv的PREFLIGHT_ISSUES为空：current_design NAME=checkpoint_init、TOP/器件正确，六个literal目标各1（2 FDCE/4 FDRE）、3 reset IO方向、core10ns/UI5ns及7+4链各4级均取得真实对象证据。这回实测确认AT003是NAME与逻辑top混用，预检不代替完整reset/CDC/覆盖安全证明。

原native Tcl另显示OPT之后、place之前显式implement_debug_core；新增自管入口遗漏此动作，先前“OPT自动物化”假设被实际流程否定。AT004源保持冻结，只取完整预检/必要INIT与OPT证据，在place前结束；下一AT补回debug物化，独立debug_materialized/pre_place DCP及全覆盖/零黑盒/DRC/CDC门通过后才place。OPT的工具占位和缺口保持PENDING，不造PASS；见R005阶段纠正及现合同。


---
Published: 2026-10-15T04:35:11.799055+00:00
Publication: Pa46e17b4489149dda24813b6ec159a88
