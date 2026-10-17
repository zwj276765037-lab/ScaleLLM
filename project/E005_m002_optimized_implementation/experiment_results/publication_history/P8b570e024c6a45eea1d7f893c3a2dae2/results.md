# E005：功能通过，新综合自然完成，进入物理准备

Attention AT001与MLP AT003完成原版逐拍对比及独立oracle，指定局部功能PASS；[最终功能事实](runs/R001/rtl_functional_final_facts.json)。Attention1265488周期差分、1263504独立slot检查；Down/Gate分别2477/4821周期差分、49/98独立输出及16/17项有意非法输入场景。MLP AT002声明顺序编译失败保留，AT003仅前移声明。最终179项入口CPU通过，新create自然0；[入口事实](runs/R002/entry_preparation_facts.json)。

R003/AT001新综合与完整外层报告于2026-10-16 02:31:56 UTC自然完成，原wrapper真实native/exit均0；23个原生综合运行完成。342项实际综合输入已核一致。监督接管于02:32:00 UTC自然结束、stop_reason=null且无残留；[接管终态](runs/R003/attempts/AT001_fresh_synth/supervision_handover_20261016T021717Z/status.json)。原监督缺失及01:42:20→02:17:17 UTC观测缺口保留，原监督wait/exit UNKNOWN，不补造原status。进入物理所需独立恢复closure与45份DCP身份配对正在完成。

原生新综合网表80个局部控制逐项通过：Attention48 LUT6各256 FDCE/CE，Gate16 LUT1各384 FDRE/CE，Down16 LUT1各512 FDRE/CE；INIT、DONT_TOUCH及实际负载均匹配。10条capture_index仅28–32个LUT输入负载。此为综合网表机制落实，物理局部性和拥塞收益待测；[独立结构审核](runs/R005/synthesis_structure_preterminal_review_evidence.json)。

E002→E005同Synthesized阶段：CLB LUT841576→828763（−12813，71.18%→70.10%），CLB Registers1029313→1029316（含2 AND/OR），latch0；LUTRAM29200、SRL14551、BRAM945、URAM752、DSP5451保持。control sets22322→22353；Attention input LUT18648→6421。两份均有dbg_hub_CV占位1，需OPT/debug处理；[资源审核](runs/R005/synthesis_utilization_preterminal_review_evidence.json)。

综合估计WNS+0.904ns/TNS0，WHS−0.814ns/THS−49356.691ns，最差脉宽裕量−0.012ns，时序未通过。530缺时钟、554内部未约束端点及6条critical CDC与旧综合同阶段身份完全相同。下一阶段必须按新实际图处理；正式reset/CDC安全OPEN，布通与物理时序均未验收。


---
Published: 2026-10-16T02:35:50.242913+00:00
Publication: P7c932f927caf4f44b07c69dab1075196
