# E011 来源与方法

M003冻结设计为M2+A3+C-P1，G2 SHA4424c426；3份生产RTL未变。当前实际48源manifest SHA42dafce33f4727734dcf169b285a3decfcfa18d78d10f9a36463b4bea7c904d5。原AT003的23个完成综合producer/22个实际消费DCP是本版新综合网表；其外层native1及所有历史失败/受控停止保留。

AT027在该新图恢复完整后报告，严格采同次51项实际复位来源、函数、INIT及pin极性，保留cell空属性；六源NAME及独立clock按真实连通组取证，原断言覆盖/预算/保护保持。AT027已自然native0，194 current/archive与48源匹配，最终导出checker及恢复综合freeze已完成。

AT028复用该冻结包和未变功能/入口回归，不重新综合或重跑已通过仿真。已实际启动原生INIT完整prefix→显式opt_design→真实debug条件→完整阶段检查/preplace保存。真实G4包由A007独审绑定后才可衔接固定place SSI_SpreadSLLs/physopt Default/route Default，无incremental或seed sweep。

本轮工程owner A018，原A006只读；A007独审，Root维护全局记录。CPU0–7/max8/nice5、单EDA及原资源保护/禁区保持。

---
Published: 2026-10-19T10:56:13.311146+00:00
Publication: P50addadf8f9b4c93a34a3af8d457e417
