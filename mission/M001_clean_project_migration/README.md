

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-18T00:06:15.625771+00:00。来源修订：`943abfac7fc3`。

# M001 · clean_project_migration

[任务合同](contract.md) · [任务总结](../../results/missions/M001_summary.md)

## 执行子任务与主控审核

| 子任务 | 定义 | 完整审核历史 |
| --- | --- | --- |
| SM001 · preserve_and_organize | [定义](tasks/SM001.md) | [审核](../../results/reviews/SM001.md) |

## 关联实验


## 任务总结原文摘录

# M001：最终汇总

任务：核心工程整理；2026-10-14 完成。仅静态组织验收，不是硬件验收。

## 对目标的实际进展

新根：`/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM`。
旧根：`/home/user/EDA-202/zhuowenjun/ScaleLLM`，未删除、移动、改写或清理。
目录以 `project/software` 和 `project/hardware` 为实现入口；保留一个当前任务和一页有效目标，不搬整套历史 goal/mission/result。

## 小任务、关键数据与阶段决定

| 范围 | 来源文件 | 字节一致 | 仅路径适配 | 静态检查 |
| --- | ---: | ---: | ---: | --- |
| [软件](../../project/software/README.md) | 42 | 34 | 8 | 28个Python语法、SHA256、路径及有限依赖检查通过 |
| [硬件](../../project/hardware/README.md) | 239 | 235 | 4 | 5个manifest/88个叶文件、105个构建输入、40个Python语法、2个shell语法、12个Tcl完整性检查通过 |

主控在子任务结束后分别重跑 `software/tools/check_migration.py` 和 `hardware/tools/migration.py verify`，退出均为0。没有导入/执行软件数值模型或运行真实硬件工具。
全部281个复制源文件的SHA256与初始快照一致；数值算子、RTL、XDC、生产manifest和阈值未改。硬件普通参考引用接到新 `software/0_Software`，其 `v5_fullchain.py` 与旧文件字节一致。
新工程磁盘占用约7.2 MiB，旧工程约60 GiB；体积不是算法压缩结果，而是排除了生成物和大型数据。

用户随后明确取消此前绑定，要求只在ScaleLLM分区创建四个独立新对话。已使用thread/start新建，核验无fork来源、无父会话、无项目/代理绑定，每个仅一轮就绪确认，普通分区列表可见。此前误建和fork入口已解除关联并归档，原有四个历史对话保留。主控/研究gpt-6-astra/xhigh，工程gpt-6.1-sol/xhigh，问答gpt-6.1-sol/默认强度。自动通信停用，C001属于原入口历史证据。见 [当前对话入口](../../agent/work_chats.md) 与 [新建回执](../../.research-agent/fresh_section_chats.json)。

## 整合验证、限制和未完成项

- [软件来源清单](../../project/software/file_mapping.json) 与 [静态报告](../../project/software/static_check.json)。
- [硬件来源清单](../../project/hardware/migration/source_dest_sha256.json) 与 [静态报告](../../project/hardware/migration/static_checks.json)。
- [硬件外部依赖](../../project/hardware/migration/external_dependencies.json) 明确原始输入、工具链、报告和未移植bitgen脚本。
- [当前新建回执](../../.research-agent/fresh_section_chats.json) 保存真实独立对话

（摘录截断；完整记录见链接。）

## 相关决定、变更与讨论

- [README](../../results/README.md)
- [C001 · M001 初始化通信核验，非工程实验任务。请确认你能读取新根目录及当前仅整理、不改旧工程、不运行 EDA/GPU/板卡的边界。](../../communication/C001_M001%20%E5%88%9D%E5%A7%8B%E5%8C%96%E9%80%9A%E4%BF%A1%E6%A0%B8%E9%AA%8C%EF%BC%8C%E9%9D%9E%E5%B7%A5%E7%A8%8B%E5%AE%9E%E9%AA%8C%E4%BB%BB%E5%8A%A1%E3%80%82%E8%AF%B7%E7%A1%AE%E8%AE%A4%E4%BD%A0%E8%83%BD%E8%AF%BB%E5%8F%96%E6%96%B0%E6%A0%B9%E7%9B%AE%E5%BD%95%E5%8F%8A%E5%BD%93%E5%89%8D%E4%BB%85%E6%95%B4%E7%90%86%E3%80%81%E4%B8%8D%E6%94%B9%E6%97%A7%E5%B7%A5%E7%A8%8B%E3%80%81%E4%B8%8D%E8%BF%90%E8%A1%8C%20EDA_GPU_%E6%9D%BF%E5%8D%A1%E7%9A%84/thread.md)

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
