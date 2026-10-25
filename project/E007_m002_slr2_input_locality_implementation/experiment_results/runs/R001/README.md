

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# E007 / R001 运行结果

[负责人维护的本批运行记录](run.md)

# R001 — E007 CPU入口准备与源码审核

Execution state: completed（仅CPU入口准备和独立源码审核）
Verdict: supported_for_source_preparation_only

[AT001](attempts/AT001_cpu_preparation/report.md)汇总真实CPU命令、修复、逐次身份与范围；[集中独立审结](independent_entry_review.md)确认最终236718ab修订在审核范围内的F01–F06/N01–N02已闭合。较早CPU命令起止UTC未记录，明确未知；CT002/CT003仅记录对应检查的实际命令时间，不作为整个准备阶段的起止时间。初次父链适配检查失败及修复均保留。

本批次未运行Vivado、未打开新DCP、未设置实际Pblock。实际API/几何/完整cut和物理结果仍待验证；E006热点/端点归因与实际进程/锁收尾未完成。E007物理实验总体仍planned，R002/AT001为预定路径且尚未启动。

## 后续仅依赖身份桥接

当前manifest更新为b049e0f6：E006最小planned骨架准入适配改变了被导入runner的文件hash，实际五个导入helper函数AST、八个E007自身源和其他十五个复用源未变。A007已在[集中审结](independent_entry_review.md)追加该有界桥接；原审结与236718ab保留快照。此项不是重跑先前CPU案例或原生验证，原AT001终态及其当时源码身份保持。

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_cpu_preparation](attempts/AT001_cpu_preparation) | completed | CPU preparation and independent source review completed. 59 selector cases and original bounded export check reused; changed REF/pin/origin/UNKNOWN logic has affected-case checks. Native API, actual selectors, geometry/conflicts,… | [执行收据](attempts/AT001_cpu_preparation/run.json) · [report.md](attempts/AT001_cpu_preparation/report.md) |

## 本批问题与交付文件

- [independent_entry_review.md](independent_entry_review.md)
- [independent_entry_review_before_lean_helper_bridge.md](independent_entry_review_before_lean_helper_bridge.md)

## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
