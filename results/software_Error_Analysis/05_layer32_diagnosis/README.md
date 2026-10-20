# 第32层定位与两出口逐数舍入核验

本目录保留三个不同范围，不混作同一全量因果测量：

- `rounding_audit_15docs/`：[报告](rounding_audit_15docs/report.md)、完整scalar_summary、阈值与原→后值CSV。仅15篇预声明audit文档、1746位置；o/down各7151616个scalar，总14303232。相同保存CURRENT量化输入，区分final cut8、total unrounded-reference loss、同F16出口额外中间舍入差与Host FP32转换；非零原值才进入直接相对误差分母。不能外推为1024篇逐值相对比例。
- [已有1024篇离散出口差](full1024_output_differences.json)：current对同F16 OUTPUT_ONLY出口，所有变化为−1/65536；它不是未舍入原数前/后损失，范围独立保留，附逐文档CSV。
- `causal_diagnostic_3docs/`：[报告](causal_diagnostic_3docs/report.md)、四轨迹分解/逐stage统计。仅3篇、299位置，固定保存hidden30重放第32层，并做条件后缀干预；用于区分本层新增舍入与上游输入差异传播。AC/CB能量有交叉项，不可解释成可加的固定归因百分比。参考仍保留基础量化、ScaleCode、LUT/SwiGLU、共同出口与Host。

[跳变位置Python图](layer32_error_location.png) 使用已有全1024统计，PNG原样复制。主要证据支持MLP残差合并是relative误差跳升点：信号两路相消而误差几乎不相消；不能把它误说为FP32加法自身舍入大。两出口自身舍入小也不等于全32层某量化算子全局因果占比已确定。

`independent_review/`分别保存R010/R011关键独审；`rounding_provenance/`和`causal_provenance/`是原有范围输入/结果与实际退出回执，没有复制模型或raw tensor。来源/SHA见 [清单](../package_sources.json)。
