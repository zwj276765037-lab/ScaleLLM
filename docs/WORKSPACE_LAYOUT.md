# 工程目录与发布范围

本次整理把面向部署的入口集中到根 README、`deploy/` 和 `docs/`，并生成独立可搬移的发布包。保留研究记录原路径，以维持原始报告、输入哈希和验收引用。没有对 Git 历史进行改写，也没有向远程仓库发布。

## 使用者需要的文件

| 路径 | 用途 |
| --- | --- |
| `README.md` | 当前功能、限制和部署导航 |
| `deploy/` | 可移植推理/模型准备/硬件构建入口、依赖、配置示例与固定身份的运行依赖 |
| `project/hardware/rtl/` | Attention、GU、板级集成 RTL；实际生产源由 GU-only manifest 选择 |
| `project/hardware/vivado/{scripts,constraints,manifests}/` | Vivado 构建脚本、约束及源文件清单 |
| `project/hardware/{host,model}/` | Host 协议、数值格式、模型导出与参考实现 |
| `docs/PERFORMANCE_AND_RESOURCES.md` | 端到端性能、功耗、资源的统一报告 |
| `docs/evidence/performance_resources/` | 资源层级表及本次报告使用的可携带小型证据 |
| `tests/` | 部署和发布完整性检查 |
| `tools/package_release.py` | 生成发布目录、归档和逐文件 SHA-256 清单 |
| `bitstream/` | 根目录提供已测 bitstream 副本与 SHA256SUMS，便于直接使用工作区默认配置 |
| `dist/ScaleLLM_VCU118/` | 实际生成的干净部署目录，包含 `bitstream/` |
| `dist/ScaleLLM_VCU118.tar.gz` | 可搬到另一台机器的完整发布包 |

部署包在保留相对路径的前提下只选择所需文件；不会整体复制 40,000 多个历史文件。使用者从部署指南准备自己的模型工件、驱动和工具环境。

## 本地保留的研究与复现材料

| 路径 | 保留理由 | 是否随公开部署包分发 |
| --- | --- | --- |
| `project/E013_mlp_linear_only_hardware/experiment_results/board_validation/` | 已完成的 FPGA 输出、完整参考、命令轨迹、测量和独立审核 | 仅选用小型报告证据；完整原始目录保留在本地 |
| 上述目录内 `end_to_end_results/artifacts/` | 已导出的真实模型资产，避免下一次部署重新导出 | 否；使用者自己获取模型并导出 |
| `project/hardware/vivado/reports/` | 原生资源、时序、布局布线证据及关键 DCP/bitstream | 指定已测 bitstream 和选定小型报告 |
| `project/hardware/vivado/project/*/*.runs` | 原综合日志、结果和 checkpoint | 否 |
| `project/hardware/vivado/project/*/{*.srcs,*.xpr,*identity.json}` | 构建配置和构建来源记录 | 否；公开包提供可再生构建入口 |
| `project/E001_*` 至 `project/E012_*`、`results/` | 历史成功与失败证据，可能被设计判断引用 | 否 |
| `mission/`、`agent/`、`communication/`、`question/`、`.research-agent/` | 研究管理与讨论历史 | 否 |
| `docs/history/README_before_release_2026-10-25.md` | 整理前首页的完整留档 | 否 |

## 缓存清理规则

`tools/clean_workspace.py` 默认仅生成清理计划，`--apply` 才执行。它只处理明确列出的本地生成目录，拒绝删除 Git 已跟踪文件、链接目标或观察到被进程占用的目录。

本次选择的缓存：

- 两个已结束 constructor 工程的 `.gen`、`.cache`、`.ip_user_files`；可由对应构建脚本与 AMD 工具/IP 重新生成。
- Vivado 的 `.Xil`、`.tmpCRC`、`.cache`。
- 工作源码目录下可再生的 Python `__pycache__`；冻结源码快照和实验结果目录不参与递归清理。

`.srcs`、`.xpr`、constructor identity、`.runs`、原始资源/时序报告、DCP、bitstream、模型工件、冻结输入和失败证据保留。清理前后核验已测 bitstream 与其 routed DCP 的 SHA-256。

生成文件删除后，旧 constructor 清单中这些缓存文件的逐字节重验不再可执行；原清单和本次删除前哈希继续保留。需要重新构建时按构建指南创建新工程，不能把已清理的旧 `.xpr` 当作完整构建缓存。

Linux `/proc` 的权限限制会使部分其他账户的进程不可读；清理回执记录该数量。可读进程没有占用目标目录，工程 owner 确认本项目没有活跃 EDA；正在另一个 `Workspace/ScaleLLM` 内运行的工程未被修改。

实际清理完成：删除 2,916 个可再生文件，释放分配空间 **3,889,287,168 B（3.622 GiB）**。已测 bitstream、routed DCP 与全部 102 个父构建源文件的 SHA-256 核验一致。详见 [清理汇总](evidence/workspace_cleanup/summary.json)。本地另保留清理前计划与逐文件删除回执；发布包只携带汇总。

## 重新生成与校验发布包

在完整研究工作区执行：

```bash
python3 tools/package_release.py
python3 tools/package_release.py --verify dist/ScaleLLM_VCU118
```

生成器按 `deploy/release_files.json` 白名单复制文件，核验已测 bitstream 的固定大小与 SHA，检查常见凭据模式，并产生 `RELEASE_MANIFEST.json`、`.tar.gz` 和归档 `.sha256`。构建发布包不执行 FPGA 计算、不安装驱动。

解压后可直接校验包内所有文件：

```bash
python3 tools/package_release.py --verify .
```

生成完整发布包的源选择引用本地原始证据，所以在仅有部署包时应使用 `--verify`；推理和构建不依赖本地研究管理目录。
