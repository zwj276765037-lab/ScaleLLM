# A007：AT006 布线失败原因有界核查

本轮角色：只读独立审核。执行 completed；判断：本次是实际非法路由，由资源冲突/拥塞导致 route_design 原生失败。适用 E011/R003/AT006 当前现成报告；这是一份原因核查，不新增审核门，也不授权新 AT、EDA 或设计修改。

直接证据：

- `vivado.log:982` 的 Route 35-162 报告 **615,840 条信号因拥塞未合法布通**；`:1078` 的 Route 35-2 明确 `Design is not legally routed`，剩 **797,175 个 node overlaps**。`route_command_result.txt` 为 `route_design -directive Default`、`native_tcl_code=1`；launcher 于 2026-10-20 07:07:38.298052Z 以 native 1 结束。
- `route_failed_status.rpt`：2,031,715 条可布线网 = 1,415,875 条 fully routed + 615,840 条 resource-conflict nets。冲突网约占可布线网 **30.31%**。它与 Route 35-162 的口径相符；797,175 是节点重叠数，615,840 是受冲突影响的网数，不能相加或当作同一计数。
- `vivado.log:922–926` 的 `Failed Nets=0` 定义只包括 `Unrouted+Partially Routed`，同一处仍有 797,175 overlaps。线路已找到连接路径不等于获得互不冲突的合法资源。
- `route_failed_drc.rpt:31,44–46` 仅给 RTSTAT-13 Critical Warning，明确未布通部分显著，故 **RTSTAT-* 路由状态检查不执行**，要求查 `report_route_status`。它没有独立给出 615,840 条冲突网；日志的 DRC `0 Errors` 不能证明合法路由。失败捕获回执的各项 code 0 仅说明诊断保存成功。

当前证据支持的结构性解释：

| physopt 阶段占用 | SLR0 | SLR1 | SLR2 |
| --- | ---: | ---: | ---: |
| 已占用 CLB 站点 | 96.71% | 99.33% | 99.90% |
| CLB LUT | 57.38% | 70.38% | 75.54% |
| CLB Registers | 36.98% | 43.68% | 48.97% |
| URAM | 87.50% | 77.50% | 70.00% |
| DSP | 79.52% | 88.82% | 70.75% |

`utilization_slr_physopt.rpt` 表明三个 SLR 的 CLB 站点均已大量铺开，尤其 SLR1/2，重新摆放和改善局部连接的余地有限；**不能据此声称所有 LUT/FF 已用尽**，也不能仅由占用率证明某种装箱或控制集问题是唯一原因。

`vivado.log:698–707` 的全局路由估计：SLR0–1 总需求 10,915/17,280（63.17%），最挤列 1,792/1,440（约124%）；SLR1–2 总需求 10,766/17,280（62.30%），最挤列 1,617/1,440（约112%），另有超过100%的列。**跨 SLR 总容量仍有余量，但需求集中在少数列。** 这是局部 SLL 拥塞证据，不是唯一根因证明；其估计阶段/口径也不应与 physopt 报表的 49.95%/54.36% 连通占用直接混作一项指标。

最终 `vivado.log:917–954` 还有芯片内部局部拥塞：全局垂直/水平平均利用率仅 49.3364%/46.0815%，但北向 64×64 窗口最高 114.777%，涉及 INT X0–107、Y324–515 的列举窗口；南/东向热点包含 X32–63、Y644–675，东/西向也有 Y352–387 一带。这支持局部通道和连线集中压力，不能用平均值排除拥塞。`:726` 明确路由器已优先尝试布通而放弃部分时序优化，最终仍未合法。

模块定位与限度：

- 最终 top10 重叠节点样本（`vivado.log:983–1070`）直接包含 MLP `projection_repack` 到 SwiGLU `g_row_branch[1]`，以及 `u_shared_compute/parent_head_r`；也包含 `u_tensor/output_mux_group_data_r`、`u_paired_weight/u_local0/mlp_rdata` 和 `d0_smc/.../r_sreg`。所以问题不只是一条支路或一个模块。
- `route_failed_congestion.rpt` 第55–68行可将区域线索对应到 attention projection/compute/front-end、MLP branch0/branch1 kernel/input-front-end/gate/SwiGLU，以及 attention postprocess/KV quantizer。**该报告两节原名为 “Placer Final Level Congestion Reporting” 和 “Router Initial Congestion”**；虽然在失败后保存，其中模块百分比是相应区域报告中的组成信息，不能冒充最终全部冲突网的模块贡献比例。
- 最终 top10 是工具抽取的少量节点及每节点至多5条网，不是615,840条冲突网的全量归因；attention 的证据主要来自区域报告，并未从该 top10 样本量化其最终冲突份额。尚不知道各模块/SLR/内部通道与 SLL 对最终失败分别贡献多少，也不能据本次结果声称某项迁移必然有利或有害、只改一个区域即可成功。

physopt 的现成结果为 `completed=1`、blackboxes=0、`physical_signoff=false`；布线失败发生在原生 route 阶段，不是本次恢复入口的属性/命名资格错误。完整 route 验收与时序收敛均未成立。源与锁的终态收尾仍由 A018 负责，本核查未轮询进程或代替工程收尾。

读取范围：上述小报告；日志640–760、880–1010、1004–1115的有界片段；DRC前91行；SLR crossing前40行。未载入/重哈希大DCP、107MB快照、61MB cells或119MB reset图；未运行原生工具、测试、观察器或归因新实验。

证据目录：`project/hardware/vivado/reports/m003_E011_R003_AT006_successful_place_POST_physopt_route_cwd_fixed/`。

小报告身份（SHA-256）：

- `route_failed_status.rpt`，714 B，`adf8eaf36975b26cdc2bb68e4a60de807694a71fa9d522b4447ecdc0c6e4832a`
- `utilization_slr_physopt.rpt`，6970 B，`d7ac0c6ecfa73e20205553769078853eba39e115f77aa6bde648c1d1f47fd02b`
- `route_failed_congestion.rpt`，39983 B，`f2e76c79a32363ea7424e57b7fdb9d0b6a50ba9dad2575441b9c1b0311da6a60`
- `route_command_result.txt`，118 B，`23f9e0c50085f499109d6a0d1533e43206aeb223c081d624be072483c4d68ee7`
- `route_failed_original_error.tcllist`，586 B，`3424d3c22fd3742c799e9b2141a75786760375cc709e526f6beb88d134a2551b`
- `route_failed_capture_receipts.tsv`，555 B，`33dfb5805ba753783c83428fba96d666c10e5a8f224efaba15146dde927ec15d`
- `launcher_status.json`，993 B，`c82273da52baa10ba0bca3635ce312b3787047fc4035c4337fcf630d4f6e441e`
- `physopt_result.txt`，187 B，`f0e7d3b60d1c9c4ac7e212c77266ef881a1170781915c2323cbcfa847158371f`
- `physopt_command_result.txt`，123 B，`c405c9631523990b23ccdc533ef6c3b317d30b1fb5534ac8180cc8c3fd957685`
