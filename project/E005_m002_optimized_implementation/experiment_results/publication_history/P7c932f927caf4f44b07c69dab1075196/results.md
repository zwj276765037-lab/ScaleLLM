# E005：两项RTL功能验证完成，正式新综合运行中

3处RTL首选改法已完成，生产输入从首版保持；[最终功能事实](runs/R001/rtl_functional_final_facts.json)和[运行记录](runs/R001/run.md)绑定真实输入与原证据。

- Attention AT001：1265488周期原版差分、1263504 slot独立oracle、192中断/196epoch、4完整双wave映像、13591背压检查，通过。[范围与证据](runs/R001/attention_functional_results.md)。
- MLP AT003：生产Down S32/ROWS16/MATRICES1和Gate S24/ROWS16/MATRICES2均通过；分别2477/4821周期差分，49/98独立列FIFO oracle输出，16/17个非法输入检查，背压、consume/refill、reset/clear同拍和终尾均覆盖。[范围与证据](runs/R001/mlp_functional_results.md)。AT002只因TB声明顺序编译失败，原失败保留，v2仅前移声明。
- 两次成功仿真native/监督均0、无墙钟强停/残留。局部功能PASS不证明实际48/32物理driver落实或拥塞/时序改善。
- 最终入口179 CPU检查通过且输入未变；目标器件安装版原生help支持SSI_SpreadSLLs，后三阶段配置为SSI_SpreadSLLs/Default/Default。[入口事实](runs/R002/entry_preparation_facts.json)保留156项前版及两项后变输入的适用范围。
- 新工程create于00:52:14 UTC自然成功结束，native/监督0，无强停/残留，141项冻结输入保持一致。正式新综合R003/AT001已实际启动，[启动记录](runs/R003/attempts/AT001_fresh_synth/started.json)；无墙钟/静默期限。实际综合/IP/DCP身份及80个局部控制边界仍待产出核验，物理阶段尚未开始。

接续异常：23/23原生综合子运行已有成功回执，外层Vivado仍在加载网表/报告。原监督进程消失，资源记录01:42:20→02:17:17 UTC存在缺口；现已同PID接管资源保护与单EDA锁，[实际移交](runs/R003/attempts/AT001_fresh_synth/supervision_handover_20261016T021717Z/started.json)。原状态/资源不覆盖，原native退出码不补造；整体综合报告/80边界核查仍待结束。

新原生Synthesized资源报告已产生并由A007同阶段独立复核：E002→E005 CLB LUT841576→828763（−12813；71.18%→70.10%）、CLB Registers1029313→1029316（含2 AND/OR；纯FF1029311→1029314）；latch0，LUTRAM29200/SRL14551、BRAM945/URAM752/DSP5451均保持，control sets22322→22353。两份报告均有已知dbg_hub_CV占位1，不能称零黑盒；下一阶段OPT/debug继续真实清除与覆盖核验。原报告位于[本轮utilization](../../hardware/vivado/reports/m002_E005_R003_AT001_fresh_synth/utilization_post_synth.rpt)。这是资源改善，不证明80边界或扇出/拥塞收益，outer仍在报告阶段。


---
Published: 2026-10-16T02:25:19.651392+00:00
Publication: P19656e99fd10434f8b98877837f28459
