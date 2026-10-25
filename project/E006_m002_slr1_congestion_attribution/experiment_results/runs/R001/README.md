

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# E006 / R001 运行结果

[负责人维护的本批运行记录](run.md)

# R001 — E006 / SM010 SLR1资源、热点与连接归因

Execution state: running
Verdict: unassessed
Applicability: 当前E005 closed physopt.dcp，只读归因；E005 route失败与全局验收状态不改。

AT001已实际启动原生Vivado2025.2/VCU118/xcvu9p-flga2104-2L-e；原physopt恢复和完整primitive导出已自然完成，global与Attention/MLP/metadata/loader首4owner原生query均0，后续查询在同一原生会话继续。精确argv/cwd、source/contract/原DCP/144freeze和外部target身份见实际[started](attempts/AT001_physopt_attribution/started.json)及[input_bindings](attempts/AT001_physopt_attribution/input_bindings.json)。父工程状态、正式安全OPEN、数值/ABI/双DDR/时钟保持。只对自然闭合query交付局部事实，不把部分完成当整stage或终态。

单EDA，CPU0–7/nice5/max8；RSS192GiB、MemAvailable48GiB持续30秒、disk30GiB保护，无墙钟/静默强停。独占R001和A006，R002为A007独立分析/审核，主控维护三摘要与共享正文；不创建后代，不热改原E005或生产树。

连接范围为10NW实际cells去重UNION所附着全部完整canonical nets，端点仅primitive leaf DIRECTION IN/OUT，INOUT和top ports未枚举。NO_PRIMITIVE_DRIVER不等于无真实driver；类别OTHER可含未识别的存储/DSP控制拼写，后续只能用实际REF/REF_PIN_NAME细化，不按名字猜协议。native资源与primitive hist/site/BEL归属分列，DSP split refs不当DSP个数，sharedsite/重叠区不相加，fixed拥塞UNAVAILABLE。

## AT001实际原生启动

2026-10-16T15:51:42.925759Z实际detach，native metadata15:51:44.063950Z；supervisor942046/start927846090、leader942061。只打开原E005 closed physopt.dcp（766217926d…），原生日志已明确open并加载正确part；4原PID/start、CPU0–7/nice

（摘录截断；完整记录见链接。）

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_physopt_attribution](attempts/AT001_physopt_attribution) | failed | Original full readonly diagnostic INTERRUPTED_INCOMPLETE by explicit user-authorized replacement, not a method refutation; original partial closed queries preserved. Supervisor termination and wrapper post-integrity NameError are… | [执行收据](attempts/AT001_physopt_attribution/run.json) · [report.md](attempts/AT001_physopt_attribution/report.md) |

## 本批问题与交付文件

- [engineering_first_closed_module_report_2026-10-16.md](engineering_first_closed_module_report_2026-10-16.md)

## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
