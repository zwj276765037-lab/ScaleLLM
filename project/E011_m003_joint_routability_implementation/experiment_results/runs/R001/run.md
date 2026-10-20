# R001 — SM015/SM016同版实施与验证

Execution state: completed local execution；verdict: bounded functional/entry checks passed, overall routability unassessed；review: G3a accepted, G3b final v3 independent verdict pending.

真实工程起点为AT001/actual_engineering_start.json的2026-10-18T03:17:41.961478Z。选定C-M2+C-A3+C-P1，G2 4424c426、SM014 manifest6d74e85d；生产三RTL按selected_RTL_applied.json实际变化，branch计算体未变。当前入口41源manifest62d55ff9，19源初版与41源v2原件保全。144基线实际文件137相同，仅三所选RTL与四公共入口计划变化。

AT001因相对$0校验收尾失败；AT002五个本地native通过并获独立接受，随后新增实际core测试仅因PASS marker未独占行导致launcher失败，原native打印覆盖PASS；AT003只修标记后完成core边界和无force实际production smoke，并完成最终288 tests（42项资格/来源/Tcl/probe项含其中）。各AT/job原始退出、命令、输入和工具身份、预归档、资源/PID-start/无幸存证据保持，未覆盖失败结果。

独立期望为保全旧RTL、独立内存/token/队列/整数算法；覆盖实际生产TILE9、compat default TILE2、A3mode1/default0、81920容量及边界/非法/碰撞/背压/优先级。完整actual core测试明确force边界，production smoke无force但没有完整层命令或DDR事务；二者不冒充整板E2E。详细影响-回归映射与当前manifest身份见experiment_source/G3b_delivery_v3.md/json及protocol.md。

工具与平台为XSim/Vivado2025.2 Build6299465、VU9P VCU118；单EDA、CPU0–7/nice5/max8、RSS192GiB/MemAvailable48GiB持续30s/disk30GiB、无墙钟/静默强停。全部native job已排空，无M003综合/place/route。TOP01−2.896ns与22,049差异保持OPEN。
