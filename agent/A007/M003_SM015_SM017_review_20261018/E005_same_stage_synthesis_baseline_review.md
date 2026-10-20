# E005 同阶段综合资源基线独立核验

A007 只读审核 completed；已有 E005/R003/AT001 post-synth 报告可作为 E011/G4 同阶段资源比较基线。新 E011 综合/预算/G4 尚未发生或通过。本结论不需要新 EDA、DCP 读取或旧大表重扫。

原生报告：[hierarchical](../../../project/hardware/vivado/reports/m002_E005_R003_AT001_fresh_synth/utilization_hierarchical_post_synth.rpt)、[flat](../../../project/hardware/vivado/reports/m002_E005_R003_AT001_fresh_synth/utilization_post_synth.rpt)。Vivado 2025.2 build 6299465、xcvu9p-flga2104-2L-e、scalellm_vcu118_f05_bd_wrapper；头部 Design State=Synthesized，实际 report_utilization。2026-10-16 10:20:56 原生报告时间。完整身份及行号见 [JSON](E005_same_stage_synthesis_baseline_review.json)（SHA `cd15c3a0ed905cc283633ca856b92e9815863cf5b282ae5ef055ad2e2472dc2b`）。

| 范围 / 行 | Total LUT | Logic LUT | LUTRAM | SRL | FF/报告Registers | RAMB36 | RAMB18 | URAM | DSP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| u_meta / 510 | 347 | 347 | 0 | 0 | 11 | 0 | 0 | 80 | 0 |
| u_shared_compute / 641 | 389067 | 378323 | 10744 | 0 | 479315 | 192 | 0 | 0 | 3072 |
| shared直属 / 642 | 11325 | 11325 | 0 | 0 | 13123 | 0 | 0 | 0 | 0 |
| top / 25 | 828763 | 785012 | 29200 | 14551 | 1029316 | 933 | 24 | 752 | 5451 |

flat 原生 primitive CARRY8=54364（198行）；raw FF primitive 总数=1029314，报告 Registers 多2个AND/OR。LUT report 是经过合并调整的利用量，不等同 raw LUT1…LUT6 primitive 总和。局部 CARRY 列未提供，不能把 global CARRY 当 u_meta 成本。

来源链已闭合到现有冻结基线：

- E005 current-CDC freeze `a5643a9e…` 的144项 path/bytes/SHA 与 SM014 design_input_identities 全等；此处为身份记录比较，没有重读144生产文件。
- 实际综合 inputs.sha256 `f889d3d9…` 有342项，与144基线共有111项且111 SHA全等，包含88 RTL、4 active XDC、2 data。其余33项没有作为这次综合输入，不能称144项全部被综合消费。
- 较E005最初141项冻结，135不变、6项变化均为工程脚本，后加3项也为恢复脚本/测试；未发现变化RTL/data/active XDC。
- E008 AT004 input_bindings引用相同144冻结；E008与E005 R004 AT003 recovery_parent的synthesis对象完全相等。7个小文件（manifest、build identity、completion、checkpoint元数据两份、supervision closure、frozen anchor）逐项 bytes/SHA实际重核通过，anchor各SHA一致。
- E009 AT003 baseline引用相同a564冻结及E008 failed DCP记录身份。DCP身份仅继承证据，未读/重哈希DCP。
- synth_design实际成功（vivado.log 790行）、完成报告（1099行）和launcher/native exit0相符。原监督曾中断且后被接管，原supervision_continuous=false与不可观测间隔保留，不宣称全程连续监督。

G4应比较同stage、同metric、同scope的新旧报告，并另数精确81个M2 LUT1及A3新34 FF/局部控制与增量锥，核≤96 LUT/≤8 CARRY8。旧failed-route primitive计数仅作历史引用，不用于减法证明新synth预算；新网表实际层次、角色、URAM推断和物理兼容性仍须原生资格验证。

实际核验脚本：[review_E005_synthesis_baseline.py](review_E005_synthesis_baseline.py)，工具chunk `7ab9c7` exit0。第一次脚本因原生日志`COMPLETED:`标点假设失败，原记录保留，修正只影响审查器字符串匹配。
