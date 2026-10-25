

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# E005 / R006 运行结果

[负责人维护的本批运行记录](run.md)

# R006：各自closed place/physopt DCP的只读比较补采

execution_state: completed
verdict: 合同比较只读测量已完成；R004/AT004合法布通FAIL保持
applicability: 仅SM009/E005 R004/AT003各自closed place/physopt。AT002两phase各60query0及AT003两phase各15query0均已自然0/0闭合；新峰仅保留48来源行中的12峰行→10unique区域映射，fixed拥塞UNAVAILABLE，不代表routed签核。

本批工程收尾已完成，当前无活动EDA。AT001 pre-EDA准入失败原样保留；AT002完成80边界/94net/14上游/原placed device映射/旧48窗/层次等补采，AT003按主控确认的原合同比较义务只补新最坏峰区域。两次均在各自精确closed DCP只读执行，无重放物理命令或写checkpoint。144生产输入、两原DCP、实际源码与来源绑定保持，全部原PID-start无活体，实际锁释放与资源复算已核；A007独立审核完成。见[工程最终报告](../../engineering_final_report_2026-10-16.md)、[AT002终态](attempts/AT002_closed_place_physopt_readonly/readonly_terminal_summary.json)、[AT003终态](attempts/AT003_new_peak_windows_readonly/readonly_terminal_summary.json)。

AT002空new_peak_source_reports检查仅N/A，未作为新峰已测证据；AT003独立补齐12峰/10区域。新旧fixed拥塞无已验证API，明确UNAVAILABLE，occupancy不是拥塞等级，缺席不是0。本轮不再自动开启新implementation或额外实验。以下保留原计划和各阶段实际历史。

## 原始补采范围与计划（历史）

目标是补充80边界与14上游控制源的实际driver REF/位置/SLR、leaf pins与unique cells单位、逐SLR负载和位置包络、源相对精确跨SLR负载、三个精确层次利用率、旧48个原生窗口的实际GRID/tile/site/SLR资源与连接分布。56个原placed LOC以同part实际device拓扑映射，不能改用physopt LOC替代。fixed-window原生拥塞API若未获实际支持，明确UNAVAILABLE；资源/连接占用不是拥塞等级，缺席不能记为0。

非生产草稿位于`agent/A006/physical

（摘录截断；完整记录见链接。）

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_closed_place_physopt_readonly](attempts/AT001_closed_place_physopt_readonly) | 未登记；查看原记录 | 未登记 |  |
| [AT002_closed_place_physopt_readonly](attempts/AT002_closed_place_physopt_readonly) | 未登记；查看原记录 | 未登记 |  |
| [AT003_new_peak_windows_readonly](attempts/AT003_new_peak_windows_readonly) | 未登记；查看原记录 | 未登记 |  |

## 本批问题与交付文件


## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
