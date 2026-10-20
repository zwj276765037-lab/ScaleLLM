# E011 当前来源与方法

核心48源及3RTL未改，4显式恢复适配共52 runtime源。严格只接受宽度1二进制cell 1'b0/1，raw cell/pin保留，actual pin仍必需且原完整复位函数/结构/来源检查保留。真实OPT snapshot全CLI资格通过，17受影响回归通过。

AT033启动前已完整离线执行真实launcher准备：创建报告、选择/复制实际继承产物、写新来源回执、逐项来源归档与stage manifest一致检查，达到准确原生调用边界；另将旧parent回执插回继承列表，EXCL正确拒绝且旧字节保留。无模拟native执行。

复用AT031真实218742205B/3cac26c1 OPT DCP，继承native0与外层native1分列。新AT只证明本OPT实际恢复的22850对象/28块及zeroapply，再补原snapshot之后未执行的原生POST/debug/preplace，不重复OPT和全OPT snapshot。


---
Published: 2026-10-19T16:02:32.729621+00:00
Publication: P6673a626b8e34a6e90ab55b6204e67a3
