# E004：分析依据与适用范围

依据SM008分析合同，使用E003自然失败日志、成功physopt父点、17个已绑定RTL来源及MLP两repacker源码。E003为245279节点重叠/248289拥塞失败信号，无失败route DCP；本轮唯一只读查询只能解释成功physopt布局，不能重建失败路由全图。

原DCP SHA256 c6944eeeafb1d58776f2f3b85ecec61ddd283ff0b367d53b997e2c091696ff91前后保持；native Vivado2025.2、xcvu9p。Hadamard/ScaleCode/format05/数值/ABI/双DDR/core100MHz与UI200+200MHz保持。官方方法见[2025.2笔记](amd_methodology_2025_2.md)，具体计划及原生证据见实验结果。


---
Published: 2026-10-16T00:04:03.634795+00:00
Publication: P05591c5308954d75b5fa89c38198f752
