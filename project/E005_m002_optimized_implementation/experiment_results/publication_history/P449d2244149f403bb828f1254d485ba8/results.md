# E005：两项RTL功能验证完成，新工程创建中

3处RTL首选改法已完成，生产输入从首版保持；[最终功能事实](runs/R001/rtl_functional_final_facts.json)和[运行记录](runs/R001/run.md)绑定真实输入与原证据。

- Attention AT001：1265488周期原版差分、1263504 slot独立oracle、192中断/196epoch、4完整双wave映像、13591背压检查，通过。[范围与证据](runs/R001/attention_functional_results.md)。
- MLP AT003：生产Down S32/ROWS16/MATRICES1和Gate S24/ROWS16/MATRICES2均通过；分别2477/4821周期差分，49/98独立列FIFO oracle输出，16/17个非法输入检查，背压、consume/refill、reset/clear同拍和终尾均覆盖。[范围与证据](runs/R001/mlp_functional_results.md)。AT002只因TB声明顺序编译失败，原失败保留，v2仅前移声明。
- 两次成功仿真native/监督均0、无墙钟强停/残留。局部功能PASS不证明实际48/32物理driver落实或拥塞/时序改善。
- 最终入口179 CPU检查通过且输入未变；目标器件安装版原生help支持SSI_SpreadSLLs，后三阶段配置为SSI_SpreadSLLs/Default/Default。[入口事实](runs/R002/entry_preparation_facts.json)保留156项前版及两项后变输入的适用范围。
- 新工程create已于00:46:50 UTC实际启动；141项生产源/脚本/XDC/manifest已冻结，[启动记录](runs/R002/attempts/AT006_fresh_create/started.json)。实际生成IP及综合消费DCP将在后续阶段绑定；正式综合和物理结果尚未取得。


---
Published: 2026-10-16T00:50:20.103877+00:00
Publication: P69f70c2ecf2e47568514dd6cb7eefb78
