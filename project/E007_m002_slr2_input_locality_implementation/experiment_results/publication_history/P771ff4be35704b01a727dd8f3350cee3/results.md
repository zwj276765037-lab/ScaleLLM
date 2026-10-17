# E007：当前结果

SLR2定向卸载入口已完成CPU准备和独立源码审核；当前manifest为`b049e0f6897d2c49e3a61154053023c6ca7216ed5d19fe2d89f68c96be7aa059`。[集中审结](runs/R001/independent_entry_review.md)确认F01–F06/N01–N02在审核范围内闭合，结论仅为supported_for_source_preparation_only。

[CPU准备](runs/R001/attempts/AT001_cpu_preparation/report.md)保留原59字面选择器案例及有界导出核查，未重复扫描。受影响REF/pin/clone/查询失败与UNKNOWN分类反例和语法检查通过；CT002、CT003有各自真实命令起止UTC及退出状态，较早命令未记录的UTC保持未知，不从文件时间推造。初次父链适配失败及后续修复均保留。

目标仍为tensor输入bank及MLP capture/Hadamard/四量化器成组硬约束到SLR2。原physopt图候选含40627 CLB FF、31709 raw LUT和8物理DSP，无BRAM/URAM；这是旧图规模，不是已释放面积。当前未打开E007原生DCP，未设置实际Pblock，未执行place/physopt/route。实际API、区域/冲突、完整cut、候选适用性和物理效果仍待核验，不能承诺一次布通。

因E006轻量入口适配已登记的planned管理骨架，E007导入的辅助文件整体hash随之改变。已完成五个实际导入函数的AST身份桥接：E007八个自身源及其余十五个复用源字节均未变，34项manifest引用独立核验一致；原236718ab版本及原独立审结已归档。独立审核已在同一审结追加，新接受范围仍仅源码准备，未重跑59案例或原生阶段。


---
Published: 2026-10-16T23:22:50.965481+00:00
Publication: P4ec33cfa0d8d49c5882065ef3f24876b
