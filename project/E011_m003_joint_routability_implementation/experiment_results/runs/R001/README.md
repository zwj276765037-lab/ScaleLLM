

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-20T08:57:35.240611+00:00。来源修订：`cfb9c0cd3fc1`。

# E011 / R001 运行结果

[负责人维护的本批运行记录](run.md)

# R001 — SM015/SM016同版实施与验证

Execution state: completed local execution；verdict: bounded functional/entry checks passed, overall routability unassessed；review: G3a accepted, G3b final v3 independent verdict pending.

真实工程起点为AT001/actual_engineering_start.json的2026-10-18T03:17:41.961478Z。选定C-M2+C-A3+C-P1，G2 4424c426、SM014 manifest6d74e85d；生产三RTL按selected_RTL_applied.json实际变化，branch计算体未变。当前入口41源manifest62d55ff9，19源初版与41源v2原件保全。144基线实际文件137相同，仅三所选RTL与四公共入口计划变化。

AT001因相对$0校验收尾失败；AT002五个本地native通过并获独立接受，随后新增实际core测试仅因PASS marker未独占行导致launcher失败，原native打印覆盖PASS；AT003只修标记后完成core边界和无force实际production smoke，并完成最终288 tests（42项资格/来源/Tcl/probe项含其中）。各AT/job原始退出、命令、输入和工具身份、预归档、资源/PID-start/无幸存证据保持，未覆盖失败结果。

独立期望为保全旧RTL、独立内存/token/队列/整数算法；覆盖实际生产TILE9、compat default TILE2、A3mode1/default0、81920容量及边界/非法/碰撞/背压/优先级。完整actual core测试明确force边界，production smoke无force但没有完整层命令或DDR事务；二者不冒充整板E2E。详细影响-回归映射与当前manifest身份见experiment_source/G3b_delivery_v3.md/json及protocol.md。

工具与平台为XSim/Vivado2025.2 Build6299465、VU9P VCU118；单EDA、CPU0–7/nice5/max8、RSS192GiB/MemAvailable48GiB持续30s/disk30GiB、无墙钟/静默强停。全部native job已排空，无M003综合/place/route。TOP01−2.896ns与22,049差异保持OPEN。

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_selected_RTL_and_functional_integration](attempts/AT001_selected_RTL_and_functional_integration) | failed | Native helper simulation printed PASS; whole attempt failed final relative $0 checksum lookup. No RTL failure or successful G3a claimed. No survivor or resource stop. Absolute entry retry AT002. | [执行收据](attempts/AT001_selected_RTL_and_functional_integration/run.json) · [report.md](attempts/AT001_selected_RTL_and_functional_integration/report.md) |
| [AT002_native_functional_absolute_entry](attempts/AT002_native_functional_absolute_entry) | failed | five accepted local native jobs preserved; actual core test xsim printed coverage PASS but exact-marker launcher validation failed because marker included metrics on same line; no RTL failure or resource stop | [执行收据](attempts/AT002_native_functional_absolute_entry/run.json) · [report.md](attempts/AT002_native_functional_absolute_entry/report.md) |
| [AT003_core_boundary_and_registered_entry](attempts/AT003_core_boundary_and_registered_entry) | completed | SM015/SM016 selected-version native core/production smoke and full288 model/algorithm/builder/safety/qualification checks completed; independent G3b final review pending; no new synthesis/place/route | [执行收据](attempts/AT003_core_boundary_and_registered_entry/run.json) · [report.md](attempts/AT003_core_boundary_and_registered_entry/report.md) |

## 本批问题与交付文件


## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
