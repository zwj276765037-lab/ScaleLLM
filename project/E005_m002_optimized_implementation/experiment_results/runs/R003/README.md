

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-18T00:06:15.625771+00:00。来源修订：`943abfac7fc3`。

# E005 / R003 运行结果

[负责人维护的本批运行记录](run.md)

# R003 — E005 新综合与独立监督恢复

Execution state: completed_with_supervision_gap
Verdict: 新综合逻辑边界 supported；物理/时序目标未达成

- AT001 fresh_synth 原controller于2026-10-16T02:31:56Z自然完成；原wrapper真实native/aggregate均0。23个原生top/OOC成功，当前实际342源、23生产+22消费/45唯一路径DCP已hash配对并通过新synth_lineage。
- 原supervisor156037在最后01:42:20Z样本后失联，原status.json不存在、原supervisor及leader wait退出UNKNOWN。02:17:17Z独立guard接管同PID/start树/单EDA锁，02:32:00Z自然stop null/final owned空。约34m57s观测缺口保留，资源峰值只指已观测区间。
- 独立closure、frozen anchor和小事实见[完成事实](attempts/AT001_fresh_synth/synth_recovery_completion_facts.json)、[恢复资格](attempts/AT001_fresh_synth/synthesis_supervision_recovery.json)、[来源链](attempts/AT001_fresh_synth/qualified_synthesis_lineage.json)。不补造原wait0，不重综合。
- 实际48个DONT_TOUCH LUT6各256 FDCE/CE，Gate16/Down16 LUT1各384/512 FDRE/CE。10条capture index负载28–32全LUT，wavequal各24LUT6，Gatequal16LUT1，Downqual16LUT1+9metadata CE。
- 同阶段LUT841576→828763（−12813，70.10%）；寄存器+3。锁存器0，dbg_hub_CV×1仍待OPT/debug物化，不能写零黑盒。DSP5451/URAM752/BRAM945不变。
- 综合后WNS+0.904、WHS−0.814、WPWS−0.012ns，时序FAIL；530 no_clock/554 unconstrained及1/2无IO delay对象集合与旧综合相同，须由新物理当前图继续合法处理。formal reset/CDC安全OPEN。
- 原141输入controller结束后全匹配；闭合后4个未被342源绑定的工程入口常规适配，原字节与diff保留。R002/AT007 cwd导入失败保留，AT008正确包根

（摘录截断；完整记录见链接。）

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_fresh_synth](attempts/AT001_fresh_synth) | 未登记；查看原记录 | 未登记 |  |

## 本批问题与交付文件


## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
