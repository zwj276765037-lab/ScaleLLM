# E011 当前来源与方法

当前诊断针对AT006原生route_failed.dcp，设计为G2 M2+A3+C-P1/core48/3RTL；原AT035 G4与AT001成功place lineage保持。AT006补完整place POST后固定physopt Default→route Default，不重place。实际route自然失败及所有原始失败证据保全。

R004/AT001以已验证E009 scalar collector为基础，v2 package71c7aa76经独审及Root接受；单次只读载图，全量CONFLICTS native对象→alias闭包→canonical→完整leaf/top-port endpoint，actual driver模块/sourceSLR/loadSLR互斥主组。保留常量、unknown与report差异。全量之后仅top20×4/每端点类8/固定最终36seed union做有界deep，>4096 load不deep、每网2048 node上限；无全芯片route-node展开、时序命令、笛卡尔积或设计修改。

节点导出覆盖和区域映射完整性分开，未映射node显式UNKNOWN。local/相邻/两界/未知为每网互斥最低端点跨界需求，不等于实际route包含范围；两界下直接0↔2与source1两支路分开。142预定代表网真实route资源只支持样本内结论。原v1及窄修CPU反例/prepare/gate保持。


---
Published: 2026-10-20T09:13:04.148798+00:00
Publication: P56b95df73ae74a4aa8a2da2ff67b3445
