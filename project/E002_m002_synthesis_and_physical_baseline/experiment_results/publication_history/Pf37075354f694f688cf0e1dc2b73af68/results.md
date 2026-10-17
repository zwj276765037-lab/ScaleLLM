# E002：阶段结果

fresh create已完成，AT001 exit0，约330秒、峰值进程树RSS约2.74GiB；正常IP outputs与板级工程已生成。AT002正式synth仍在执行；core synth_design已完成并写出DCP，core正式资源报告为CLB LUT755296（63.89%）、FF892881（37.76%）、DSP5445（79.61%）、BRAM844 tiles（39.07%）、URAM752（78.33%）。这是core局部结果，完整board尚无终态；未预填整机综合或物理通过。

核心证据：[正式资源报告](../../hardware/vivado/project/m002_E002_R001_AT001_fresh/scalellm_vcu118_f05.runs/scalellm_vcu118_f05_bd_core_0_synth_1/scalellm_vcu118_f05_bd_core_0_utilization_synth.rpt)。

[物理策略](runs/R005/architecture_review.md)已完成：原综合入口保持冻结，新建M002物理入口并单独记录阶段身份；诊断负slack可继续但不伪造S3 PASS。保留时钟、CDC、DRC、容量和全部原输入验证。

[复位告警源码核查](runs/R005/reset_warning_review.md)已完成：未发现明确优先级冲突，27条为保守结构候选，两个accumulator head-wave的empty ready→lockstep影响必须用真实网表INIT/CE/连接确认；不是已证实FPGA bug，也未豁免告警。

[真实启动回执](runs/R001/attempts/AT001_fresh_create/started.json)。无正式综合/布局/布线PASS；旧E001快验仍按原版本适用范围引用。


---
Published: 2026-10-15T01:46:58.572529+00:00
Publication: P2ff050429f7747e082372e276a858961
