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
- [当前新建回执](../../.research-agent/fresh_section_chats.json) 保存真实独立对话身份；旧chat_setup_receipt.json、chat_visibility_repair.json和codex_binding_input.json仅为已取消操作的历史记录。

大型权重/数据、旧Vivado项目/DCP/波形、完整联合验证证据和历史bitgen验收流程未全量搬入。普通fresh create/synth/place/route的静态源码依赖完整，不代表这些阶段已经跑通。历史bitgen脚本绑定旧冻结证据，未来移植必须另立有效任务，不能直接对只读旧目录运行。
未运行功能测试、RTL仿真、综合、布局布线、GPU、PPL/ACC或板卡。native025仅是失败的未布线诊断，绝非已验证部署基线。

## 下一步

整理任务结束，等待用户后续讨论。下一项工程任务仍以真实可用bitstream为方向，但必须明确新输入版本、正确算法合同和实际验证缺口；不自动继续旧mission。
