# AT004 最终布线失败独立审核

execution：原生 route 自然失败，五项失败诊断及 locality_route_failed 成功保存，监督进程自然结束。verdict：合法布线 FAIL；失败图 setup/hold/脉宽诊断均 FAIL；C01 实际 SLR2 符合性保持；正式 reset/CDC/IO 安全 OPEN。review：本记录完成原生失败与保存诊断审核，输入/进程/资源收尾单列。

| 同阶段最终指标 | 旧 E005 | 本次 E008 | 变化 |
| --- | ---: | ---: | ---: |
| node overlaps | 1,148,579 | 702,396 | −38.8465% |
| 拥塞失败信号/资源冲突 nets | 758,463 | 547,548 | −27.8082% |

本次原生日志 254584 行 Route35-162、254702 行 Route35-2 和失败 route-status 报告相互一致。2,031,733 个 routable nets 中，1,484,185 fully routed、547,548 resource conflicts。Phase8 的 unrouted/partial=0 及 timing 报告标题 Routed 不推翻最终非法布线。计数下降是不同全局物理解的结果，不能归因 C01、声称固定热点改善或接近布通。

时间分层：北京时间 10/18 03:09:25 捕获原生 route 错误；03:28:37 完成失败 DCP/status/timing/congestion/DRC 五项诊断并从 route wrapper 返回；05:18:17 Vivado 在 locality_route_failed 完成后重抛原错误退出；05:18:30.695127 监督终态。native/监督均 1，stop_reason=null、natural=true、无 cleanup。这些时间不能全部计作纯 route 耗时，也不能把模型容量错误当作本次布线失败原因。

失败图 WNS −12.413 ns、TNS −915,419.312 ns、418,798 setup 违例端点；WHS −0.125 ns、THS −41.550 ns、3,264 hold 违例端点；WPWS −0.664 ns、TPWS −2.171 ns、8 个脉宽/偏斜违例端点。均为非法路由图诊断，不能签核。DRC 为 1 个 RTSTAT-13 Critical Warning、15,917 Warning、0 Error；RTSTAT-13 明确未运行完整 routed-net 状态检查，0 Error 不等于布通。

当前实际 C01 原始 9,491 个物理成员逐名对应、全部存活于 SLR2，无缺失/替换；Pblock 和位置数据相互一致，compliance 纯函数重放与产物完全一致。该迁移事实保持，但本次配置未通过完整物理验收；不能由一次失败推断所有定向卸载方法无效。

五项失败诊断原生回执均 0。失败 DCP 为 765,705,446 字节，SHA 由工程证据提供；本审核只核文件大小和原生保存消息，没有读取或 hash DCP。无成功 route.dcp、成功 route POST 回执、最终 bus-skew 报告；此前 6 条未 populate 路径和 1 个 ignored 组仍是覆盖缺口。locality 成功仅说明失败图采证完成。

最终自适应拥塞 N/S 为 64×64、E/W 为 32×32，旧 E005 四方向均为 64×64，坐标也有变化；不能将四方向最大值直接解释为固定窗口改善。完整 cut/有界时序文件已保存并绑定，本次有界审核未重放其中所有端点或 native alias。

详见 [JSON 审核记录](route_failed_native_terminal_review.json)。未启动 EDA、新 implementation，未控制进程或锁，未改生产文件。
