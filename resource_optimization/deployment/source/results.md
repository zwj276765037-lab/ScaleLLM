# 部署复现阶段结果

状态：**REPOSITORY_WORKFLOW_PREPARED — FULL_LIVE_DEPLOYMENT_QUALIFICATION_NOT_RUN**。开始日期 2026-11-16，基线提交 `648c0e18d0c403df90d4eb5e0f85eeaed6daf140`。

## 已核实的原始缺口

- 原默认入口 `dry-run` 返回 PLAN_VALID，但解析到历史根目录位流；新 all-DSP 位流被原入口的固定 SHA 检查拒绝。
- 原功耗准备/恢复脚本依赖作者运行目录和私有完整 KV 快照。
- 原驱动基线尚无可获取的固定公开来源闭合。

## 本阶段验收

| 项目 | 当前结果及范围 |
| --- | --- |
| 默认 all-DSP、显式 legacy、位流双重身份检查 | CPU PASS；实际 SRAM 编程待运行 |
| 编程回执绑定主机和本次 OS boot | CPU PASS；旧 boot/其他主机回执被拒绝 |
| 普通推理与独立 KV128 策略、关闭累计时间限制 | CPU PASS；28 项部署测试通过 |
| 新鲜捕获/原参考比较及失败边界 | CPU PASS；9 项采集测试通过 |
| 可获取驱动源码 | 固定第三方镜像加桥接及既有补丁的内容闭合 PASS；AMD 官方原始 archive 身份仍未确认；新驱动安装 NOT_RUN |
| 官方模型固定内容 | `meta-llama/Llama-3.1-8B-Instruct@07eb05b21d191a58c577b4a45982fe0c049d0693` 与实际 checkpoint 内容一致；模型许可/访问为外部前提 |
| 新目录全量模型导出 | PASS；原生 exit 0，1055.02 秒，300 个 payload / 8,809,861,154 bytes 全部实际哈希与原实测资产一致 |
| 便携功耗流程 | Linux CPU 15 PASS / 1 Windows native SKIP；另在 Windows 原生2项参数测试 PASS、两个 PowerShell 文件解析 PASS；历史 raw 复算整份 JSON EXACT；板端测量 NOT_RUN |
| 独立 Windows Python/公开源码目录 | PASS；新 CPython 3.12.10 / venv 安装18个锁定依赖，公开包完整校验；使用既有兼容驱动，未改变系统 Path、驱动或 boot policy |
| Windows 无板入口及模型 | PASS；dry-run、preflight --models、prepare 的16槽原始 token 一致；335个新导出文件含元数据在接收端逐大小/SHA通过 |
| 新入口普通上板推理 | NOT_RUN |
| 新入口固定活跃16请求完整128步/8192命令 | NOT_RUN |
| 新鲜 KV 来源与便携功耗上板 | NOT_RUN |
| 仓库交付内容 | 本指南、公开源码、固定依赖、测试、模型导出身份及可复算历史实验材料；新完整板测不作为本轮上传前置 |

导出采用独立公开源码快照和新的 Python 环境，输出目录先前不存在。硬件 manifest SHA256 为 `45ed3c211c4939e83d5f2efc39731970692317dfa540520ca8c16e525a99e8f6`，与原 manifest 完全相同。新 CPU manifest SHA256 为 `8484b00767aa6e38b7fe88daca6f477ff90ec6b2ada13739b95918074213dfcb`；时间/来源记录不同，但全部11个 CPU payload 的尺寸和实际 SHA256 与原资产一致。源码快照未在导出期间改变。

原硬件与 November 15 功耗证据保持不变。新导出成功、CPU 测试成功或已有驱动的独立目录运行均不能表述为全新主机驱动安装验收。发布参考回归一致也不等于独立完整模型数学 oracle。

本轮按用户澄清聚焦仓库整理和发布。未启动 SRAM 编程、CSR/DMA 访问、模型板测、功耗板测或驱动编译/安装，未持有板卡租约。测试准备中额外 `-I` 启动参数导致导入失败，去掉该额外参数后公开入口通过。Windows 参数测试首次失败的原因是测试夹具在 PowerShell 5.1 将 JSON 数组多包一层：外层 Count=1、内层 Object[]；改为直接赋值后 Count=6 且原6项逐值回环断言全部通过。只修测试夹具，功耗启动器及 runtime manifest 未改。原失败和最后原生 exit 0 回执均保留。

整合集成测试实际执行96项，Linux 95 PASS / 1 Windows native SKIP；该跳过项随后在Windows连同静态编码调用点共2项全部PASS。驱动准备器8项另行PASS。Windows还实际执行了 `benchmark-kv128 --dry-run` 并原生退出0；这只验证执行计划，不算KV128板测。
