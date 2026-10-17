# SM007 / E003：完整 implementation 工程总报告

负责人 A006 `/root/m002_build_verify`；2026-10-16（本地日期）。本轮工程执行和证据收尾已结束，当前无本轮活动 EDA。

**结论：一次冻结默认策略的实际 place→独立 physopt→route 已执行至自然退出；本次合法布通明确 FAIL。**place、physopt 及新的完整 POST/父链通过；route 原生核验失败并返回1，未取得合法最终 route DCP、完整 route POST 或正式布线后时序。E003 的全局执行/方法判断由主控按合同记 failed/inconclusive；单次物理失败不外推方法普遍无效。

## 实际物理链

| 阶段 | 实际执行与产物 | 判断范围 |
| --- | --- | --- |
| place | R002/AT001实际 `place_design` native0，7295秒，closed DCP SHA `37591435c8f95383a0910978b986c035a102c762b24b69b76e59b63d49e905f7` | 原完整place POST因两个DDR1 AUX代表源选择变化自然失败；该失败保留 |
| 恢复与独立 physopt | R001/AT002完成150项CPU和真实来源/worker入口验证并安装5文件；R002/AT002从closed place重新fresh guard→完整新place POST→独立physopt0（1106秒）→closed DCP/完整POST/成功父链 | 未重跑place/OPT/debug；原失败与新资格分开。physopt DCP SHA `c6944eeeafb1d58776f2f3b85ecec61ddd283ff0b367d53b997e2c091696ff91`、568389035B、全部25 ZIP成员CRC通过 |
| route | R003/AT001从上述成功physopt父点实际恢复，`route_design`于2026-10-15 17:27:55–22:45:40 UTC执行，19065秒，native Tcl1 | 自动失败DRC包含在命令时间内；任务内日志18814.9秒不是完整命令耗时。合法性FAIL，完整route POST未运行 |

CPU验证、归档/安装与来源：[R001/AT002报告](runs/R001/attempts/AT002_placed_CDC_recovery_cpu/report.md)。完整physopt执行及终态：[R002/AT002](runs/R002/attempts/AT002_closed_place_POST_physopt/report.md)。本次route的绑定事实：[最终事实](runs/R003/attempts/AT001_full_route/route_terminal_completion_facts.json)、[独立资源/终态复算](runs/R003/attempts/AT001_full_route/terminal_facts.json)、[详细过程报告](runs/R003/attempts/AT001_full_route/report.md)。

本次route前实际只新跑common identity/object preflight；完整timing/DRC/结构与安全诊断资格来自刚闭合且hash-bound的physopt父点，未补造place式fresh live guard。具体[本次恢复范围](runs/R003/attempts/AT001_full_route/route_restore_scope.json)。

## 实际失败与计数边界

原生Phase8 Route finalize的Routable Net Status报failed/unrouted/partially routed nets均0，但同时有245279 node overlaps，且该摘要排除driverless/loadless等不可布net。Phase9 Verifying routed nets随后实际报告248289 signals因拥塞失败、Verification failed和Route35-2 `Design is not legally routed`。245279是重叠节点，248289是signals，不将任何一个改称最终unrouted net数。缺少独立`report_route_status`的routable/fully_routed/routing_errors全字段，不能仅凭三个0声称严格全布通。

路由继续自然经过Depositing Routes、Post-Route Event Processing和工具自动失败DRC，DRC日志为0 Errors；之后仍为`route_design failed`、Common17-39和native1。自动DRC0不能覆盖路由合法性失败，Depositing Routes不等于写出DCP。

Phase5.2内部节点观察1861520→988355→501530的局部下降保留；Phase5.3新观察2025963表明跨迭代不单调，局部73.058%降幅不是implementation完成百分比。原生默认router曾因拥塞宣布优先布通所有nets而非时序优化，这属于默认命令内部行为，没有人为改策略/seed/LOC/XDC。

本次原生日志还保留初始route估算Global/Short与Timing level7、SLL0–1 demand21886/17280（126.66%，列峰208.125%）以及finalize时Global64×64方向窗口/阈值0.85表。它们和placer-final level6、GR Congestion0是不同阶段/口径；不合并为单一拥塞指标，不从有限冲突样本直接推出全设计RTL/SLR根因。独立物理解释见[A007审核](runs/R004/architecture_review.md)。

## 时序与正式安全

最后完整正式物理报告仍为成功physopt阶段：WNS−1.290ns、TNS−762.165ns、setup失败980；WHS−0.620ns、THS−2150.556ns、hold失败33141；PW相关全0。它们是pre-route估计互连，时序FAIL。

本次unfinished route的中间Route35-416仅报告WNS−17.994ns、TNS−2261923.747ns、WHS/THS=N/A；不是正式最终routed时序，也不能与正式physopt同口径归因。此次route没有`timing_route.rpt`。正式reset/CDC/重汇合、release/事务和整系统数值/板级安全仍OPEN；诊断8条CDC分类不替代正式签核。

## 自然终态、资源与进程所有权

route stage监督17:17:27.705894–22:45:51.707572 UTC，19704.001678秒（5小时28分24.001678秒）。native Vivado、worker、manager和总driver均1；driver链22:45:51.717252 UTC记failed。stop_reason=null，timeout/global_deadline=null，无wall/no-output或资源强停。实际exec session65371也自然返回1。

3882原始资源样本独立复算与监督status完全相等：峰值树RSS27882639360B（25.9677GiB），MemAvailable最低432796045312B（403.0727GiB），磁盘最低487714902016B（454.2199GiB）。未突破单EDA、CPU0–7/max8/nice5及原资源保护。

worker3964212/start919720736、launcher3964561/start919724273、launcher子3964580/start919724277、native3964652/start919724289，加manager3964207/start919720731与driver3866160/start919105949，六个原始身份均不存在。owned_survivors为空。对现存`.m002_eda.lock`实际非阻塞独占成功并立即释放，文件保留；没有启动任何新EDA。

## 实际可得性与当前停点

本次report/attempt、Vivado工作根、当前impl_1及native_run_receipts有界检查无本轮新失败DCP；原生日志没有写出route检查点。本次`route.dcp`、独立`route_status_route.rpt`、正式route timing/DRC/check_timing/CDC/reset graph、integrity、route result/admission和diagnostic_evidence均缺失。原因是`m002_command route`返回1原样抛出，随后`m002_post route`未执行；Python native非0资格失败也未进入finalize。这是实际物理失败，不能作为普通解析/报告错误自动补跑，且没有合法失败route DCP可恢复缺失POST。

已保全原始成功与失败记录、冻结源、原生命令和当前终态；最后完整恢复点仍为成功physopt DCP。当前不再发起EDA或新策略。没有修改RTL/IP/XDC/时钟、接口、Hadamard/ScaleCode/format05/数值规则，也未运行bitstream、板卡、GPU、PPL/ACC。后续架构或实现策略由主控集中评判；本报告不产生新尝试或自动优化授权。
