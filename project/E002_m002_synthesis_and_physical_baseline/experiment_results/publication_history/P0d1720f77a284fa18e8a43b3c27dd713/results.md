# E002：阶段结果

AT001 fresh create已完成，exit0，约330秒，峰值进程树RSS2.74GiB。AT002的22个OOC和top synth均结束并生成DCP；完整board已link并产出报告；AT002于02:44:24 UTC完成，native/overall exit0，114.28分钟，峰值tree RSS27.06GiB，owned_survivors=[]。正式综合执行完成，时序/覆盖仍不通过。

[完整板级资源](runs/R001/attempts/AT002_fresh_synth/observed_utilization_post_synth.json)：LUT841576/1182240（71.18%）、FF1029313/2364480（43.53%）、DSP5451/6840（79.69%）、BRAM945/2160 tiles（43.75%）、URAM752/960（78.33%），聚合容量未超。

[综合时序](../../hardware/vivado/reports/m002_E002_R001_AT002_fresh_synth/timing_post_synth.rpt)：WNS+0.904ns/TNS0；WHS-0.814ns/THS-49355.641ns，1000183 hold failing；WPWS-0.012ns/TPWS-0.037ns，脉宽检查栏目下5个失败；最差为PCIe硬核Max Skew，不能称已证实高低电平宽度不足。未布局估计，timing FAIL，不能代表物理收敛。

[覆盖检查](../../hardware/vivado/reports/m002_E002_R001_AT002_fresh_synth/check_timing_post_synth.rpt)：三组clock非空互斥，但no_clock530、unconstrained_internal554均集中于两MIG XSDB/arbiter；唯一blackbox是工具dbg_hub_CV占位。1个输入/2个输出缺delay对应PCIe/DDR reset IO，需对象级分类。[CDC](runs/R001/attempts/AT002_fresh_synth/cdc_critical_rows.json)有6条复位相关critical，不能以时钟存在宣告覆盖安全。[DRC](../../hardware/vivado/reports/m002_E002_R001_AT002_fresh_synth/drc_pre_impl.rpt)15927项均warning，无error/critical。

原339输入保持冻结；[检查点身份](runs/R001/attempts/AT002_fresh_synth/synth_checkpoint_bindings.json)覆盖23份run产物及22份实际消费IP DCP，复制品hash逐一一致。XDC puts critical已核实只影响打印，保留原severity；2个XPM无效约束端点范围与29条生产RTL复位warning仍需网表核查。

[R005审核](runs/R005/architecture_review.md)明确：实际工具身份确认后允许诊断init/opt物化debug hub，coverage/blackbox保持PENDING；place前必须重验实际黑盒、no_clock和约束覆盖。新M002物理入口保留全部综合身份与实现专用约束，不写伪S3 PASS。当前无place/route结果。


---
Published: 2026-10-15T02:46:19.205962+00:00
Publication: P166b241b7c234adca899b34bfd3f114a
