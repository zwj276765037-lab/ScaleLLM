# R001 · fresh create / synthesis 已完成

execution: completed；AT001 create exit0；AT002 synth native/overall exit0，owned_survivors=[]。真实起止/资源见attempt status.json，精简事实见[synthesis_stage_facts.json](synthesis_stage_facts.json)。原339行输入逐项验证一致，45个实际/原产DCP路径持续绑定。原create/build/run/emitter/prehook保持字节冻结。

完整board资源：LUT841576（71.18%）、FF1029313（43.53%）、DSP5451（79.69%）、BRAM945 tiles（43.75%）、URAM752（78.33%）。setup WNS+0.904ns/TNS0；hold WHS−0.814ns/THS−49355.641ns，1000183 failing endpoints；PW/skew WPWS−0.012ns/TPWS−0.037ns，5 failing checks（已见最差为PCIe Max Skew，专用报告待补）。**timing FAIL**，不是物理结果。

DRC无error/critical，15927 warning原样保留。原严重告警Designutils20-1307（policy XDC中的puts），2个vendor18-401端点、29条生产RTL reset warning及vendor reset warning仍开放；CDC10 Critical6、CDC15 Warning6198，未豁免。严格三clock-family存在/周期/互斥检查通过，但no_clock530、unconstrained内部554、唯一dbg_hub_CV工具占位不能判覆盖或黑盒PASS。reset IO delay缺失为pcie_perstn及双DDR reset_n。

A007已同意在project INIT/OPT中有界核查并物化工具debug hub；OPT POST重新全设计检查blackbox/clock/内部覆盖/DRC，未知缺失停止place前。新入口保持原完整manifest，记录全OOC/实际消费DCP与XDC完整USED_IN/scope/order/hash/真实读取顺序；pre-opt快照标明project-init相位。head-wave INIT/CE、6 reset CDC/3 IO、2 XPM scope、bus-skew和5 PW/skew对象一并有界取证。随后按诊断语义place/physopt→route，不造S3 PASS、不生成bitstream。

本阶段完整网表/报告已通过实际消息通知父主控及A007；父维护共享摘要/事件。新入口适配及物理阶段尚未完成，最终功能/时序/用户验收仍未通过。
