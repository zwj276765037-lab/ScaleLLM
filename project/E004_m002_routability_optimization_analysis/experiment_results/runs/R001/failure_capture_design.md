# R001：下一次 route 失败状态保留设计（本轮未安装）

责任：A006，SM008。此文只提出具体工程设计，不改生产入口，不重跑 E003。

## 已核事实与缺口

`project/hardware/vivado/scripts/m002_resume_physical.tcl:129` 的 `m002_command` 先记录原生命令 Tcl code，失败后 `return -options $options $result`。因此第169行 `route_design` 失败时，第170行的成功 `m002_post route` 不执行。`run_m002_physical_stage.py:170` 在原生非零时拒绝 `finalize`。这些规则正确保留了失败判定，却未保留失败时仍在内存中的物理设计。

E003/R003/AT001 因此只有原日志、命令和监督证据，没有失败 route DCP、独立 `report_route_status`、正式 routed timing 或完整 route POST。245279 重叠节点和 248289 拥塞失败信号不能用于重建失败全路由图。

## 建议实现边界

下一阶段由生产入口负责人在新 R/AT 中实现：

1. 对 route 单独保留 `catch` 的原始 result、Tcl return code、options（含 errorinfo/errorcode），首先写出不可覆盖的命令回执。
2. 如果 route 返回非零且设计仍打开，调用失败专用捕获器。每个捕获动作独立 `catch`，逐项记录 code、起止时间、结果、真实文件和文件身份；某项失败不阻止其他项，也不覆盖已有产物。
3. 优先 `write_checkpoint` 保存 `route_failed.dcp` 和 `report_route_status`；其后有条件尝试 diagnostic timing summary、congestion/design analysis、DRC。真实支持的参数以2025.2接口为准。失败捕获文件均标记 `diagnostic_failed_route`，禁止命名为成功 closed route 或进入成功准入。
4. 捕获器无论成功或失败，最后按原始 options/result 重新抛出原 route 错误。若设计在 route 前已失败或不存在，则只登记 unavailable，不产生伪 DCP。
5. Python worker 在原生非零分支只封存失败捕获器 manifest、日志、命令/源/约束/DCP 父点身份和真实退出。`native != 0` 继续判失败，不能调用成功 `finalize` 或生成成功 POST。外层 driver/manager 不吞掉非零退出。
6. 成功路径继续原有完整 POST、closed DCP、route-status 一致性和签核检查；失败捕获不放宽任何成功条件。

失败 DCP 保留的是同一次 route 的失败内存状态；不需要再执行 route 来取得该次证据。它不证明设计可用、路由合法或时序通过。

## 实施后的有意义检查

- 注入 native Tcl error 时，捕获完毕后原始 code/result/errorinfo 保持，worker/manager/driver 均非零。
- 一个捕获动作失败时，其后独立动作仍运行；所有失败均在 manifest 中可见。
- 现存产物不被覆盖；父点和源绑定可查，失败 DCP 新建后计算 SHA。
- open/preflight 失败而无设计时，失败捕获安全退出且不伪称已保存设计。
- 成功 route 路径保持原完整 POST，失败捕获 manifest 不能满足成功准入。

此流程只改善下一次失败的可诊断性；不减少拥塞、不改善时序，不能将它计入 RTL 优化收益。
