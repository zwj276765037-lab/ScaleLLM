# 当前任务：M006 MLP线性投影硬件工程

## 2026-10-25 最新授权：准备 XDMA 驱动修复并续测

持续测量遇 Windows bugcheck 0x133，WER 关联 XDMA ISR；重复用户中断仅为有依据的机制候选，根因尚未闭合。用户明确答复“继续准备修复，完成后续测量”。允许在独立工作副本准备最小 user IRQ policy 修复、远程只读工具核查、普通编译、离线验证和原驱动恢复材料；不覆盖安装源或冻结证据。工程唯一 Dell owner 仍为 `/root/board_host_prepare`，Astra `/root/board_contract_review` 集中审核，最多 Root+2、无后代。此授权尚不包含替换/加载系统驱动、签名信任或启动策略改变、主机重启；完成具体候选与恢复方案后再向用户确认安装。原功耗测量结果只含有效空闲和探索性速度，正式 measured N=0，负载功耗与持续吞吐尚未建立。

[驱动修复准备合同](M006_mlp_linear_only_hardware/driver_repair_contract_2026-10-25.md) · [部分实测结果](../project/E013_mlp_linear_only_hardware/experiment_results/board_validation/power_performance/measurement_summary.md)

## 2026-10-25：功耗与计算速度实测

用户要求“我需要你测量功耗、计算速度”。Dell唯一操作owner继续为`/root/board_host_prepare`；`/root/board_contract_review`核计数/功耗口径与集中审核。复用已通过GU bit和独立诊断gold，做有界重复计时及真实只读遥测，区分硬件phase、主机传输/调度端到端、空闲/有负载平均功耗和占空比；无可用遥测时明确缺测，不用估计冒充实测。源/结果放既有board_validation下measurement与power_performance新目录，旧证据不覆盖。禁止电源配置写、驱动安装、bit/RTL修改及主机重启。

[本轮授权](../project/E013_mlp_linear_only_hardware/experiment_results/board_validation/power_performance/authorization.json) · [测量合同](M006_mlp_linear_only_hardware/power_performance_plan_2026-10-25.md)


## 2026-10-25 最新授权：Dell 实际上板验证

本轮限定结果：指定bit已加载；CSR/双DDR有限回环、结构化与S37两例共4个生产GU命令通过，共1,835,008个S24/5,505,024B与独立gold完全一致。旧全FF首读经精确PCIe端点重启恢复，无主机重启。见[实际结果](../project/E013_mlp_linear_only_hardware/experiment_results/board_validation/execution_summary.md)。完整模型与Max-DPO/external reset全签核仍开放。

用户在确认远程上板条件后要求“你能操控dell进行吗”，本轮按上下文实际执行：指定 AT003 工程 bit 的易失 SRAM 配置、PCIe 重发现、Windows XDMA 接口适配、只读 v7 CSR/状态、有限双 DDR scratch DMA，再在各依赖通过后执行完整生产形状 GU 诊断与独立整数 gold 比较。该当前授权取代下方旧“不下载/上板”的阶段范围限制；不改写原 manifest/冻结证据，不把板测当作 Max-DPO/外部 reset 全签核。无需逐项再问用户批准普通适配/验证。

Dell 唯一设备操作 owner 为 `/root/board_host_prepare`；`/root/board_gu_vectors` 独占新增诊断数据/参考/runner，不访问板卡；Root 维护任务授权与汇总。最多 Root+2，无后代；不争用 A022 重 EDA，不自动重启主机、安装驱动或写 Flash。ABI不符、DDR/core未就绪、timeout/短IO/数据不符保留现场并停止依赖步骤。详细范围见 [上板计划](M006_mlp_linear_only_hardware/board_validation_plan_2026-10-25.md)。


## 2026-10-25：VCU118 上板测试准备

用户指定 AT003 工程验证 bitstream，并说明 Dell 主机已通过 PCIe 连接 VCU118，要求准备上板测试。本轮执行 bitstream 身份核验、Dell/PCIe/JTAG/驱动只读预检、测试入口准备和分阶段验证计划；不把历史“未开启板卡范围”作为准备工作的阻断。实际下载与计算状态按新证据分别记录，不能从准备完成推断已上板通过。原 Max-DPO、外部 reset 签核开放及冻结证据保持。

本轮内部代理：`/root/board_host_prepare`（工程，启动参数 gpt-6.1-sol/xhigh）负责独立 board_validation 工具与远程预检；`/root/board_contract_review`（架构，启动参数 gpt-6-astra/xhigh）负责有界测试合同；Root 负责整合。两者无后代，不改 A022 正在运行的 AT004 约束资格输入或争用重 EDA。

- [测试计划](M006_mlp_linear_only_hardware/board_validation_plan_2026-10-25.md)
- [本轮证据](../project/E013_mlp_linear_only_hardware/experiment_results/board_validation/)

2026-10-24用户已授权创建子智能体完成新工程搭建，硬件工程是首要目标。唯一根为`Workspace/ScaleLLM_MLP_fix`。

- [合同](M006_mlp_linear_only_hardware/contract.md)；[实现计划](../PRO_plan/ScaleLLM_MLP_Linear_Only_Dual_DDR_Implementation_Plan.md)。
- SM025：A021架构/接口冻结；SM026：A022硬件实现与集成；SM027：验证与新根构建，按依赖推进综合/物理。
- [E013工程状态](../project/E013_mlp_linear_only_hardware/experiment_status/summary.md)是当前工程进展入口。
- Root维护共享记录，A021/A022已通过子智能体工具启动；不绑定旧聊天或恢复历史进程。

下方为克隆时保留的旧M003状态，不能作为当前运行事实或覆盖本次授权。

---

# 当前大mission：M003 联合可布线改造与完整实现验收

**最新用户要求：高效长运行，不再依赖用户反复追问。** A018已被实际followup为持续工程执行：正常工具等待交给机器终态事件，结束即分析/普通修复/续跑；Root保持本轮任务以衔接必要独立G4审核。取消此前“只完成启动便结束代理轮次”的交付方式，不恢复高频读日志或逐阶段播报，按小时有界分析、有实质问题及最终结果再报告。现有AT029正常运行与原资源保护保持，不能重复启动或强停。[持续执行决定](../.research-agent/decision_inputs/M003_continuous_event_execution_20261019.json)。

**最新用户执行指令：创建6.1-sol快速进行验证，有问题再告知。** Root已实际创建`/root/m003_sol61_verification`（请求gpt-6.1-sol/xhigh），接替原A006承担本轮project/唯一EDA；原A006只读、A007单次独审。立即复核AT027终态并冻结综合产物、实际启动后续资格验证，常规修复连续。低token要求仍有效：不恢复高频观察器/模型驻留等待，Root按小时有界分析，仅实质问题或最终结果通知；此前当轮“只读不启动”已由本次执行授权取代。[实际委派与所有权](../.research-agent/decision_inputs/M003_sol61_verification_execution_20261019.json)。

**最新用户运行方式：仅每小时一次有界分析，停止持续盯进程及按阶段高频唤醒。** A007只读观察器已核身份退出；已有EDA和自动资源保护继续。每次只查看最新状态/新增证据，给出简短分析后结束，不用等待循环模拟定时。当前会话无本地定时唤醒工具，自动排程尚未建立；不冒称会自行按时唤醒。见[频率与执行记录](../.research-agent/decision_inputs/M003_hourly_analysis_policy_20261019.json)。

**2026-10-20最新：AT006已自然布线失败，原生Route35-2确认797175个重叠节点，最终route_status确认615840条资源冲突网。** 原尝试07:07:38Z监督结束native1/stop=null/owned_survivors空，route_failed.dcp及status/timing/congestion/DRC已保存；正式route POST未执行。完整place/physopt及其结构资格通过不代表可合法布通。现有证据显示局部跨SLR列需求0–1最高124%、1–2最高112%（对应总需求仅63.17%/62.30%），physopt占用CLB站点SLR0/1/2为96.71%/99.33%/99.90%，支持严重局部互连/打包压力；不将占用站点等同LUT槽耗尽，不将告警或top样本当唯一根因。用户随后明确要求“详细定位到底哪个地方无法布线成功”：A018已获派发，先现成报告离线归因，必要时新批次有界只读载入失败DCP，交付区域→模块→具体信号通路及覆盖/未知；不改RTL/XDC、不启动新implementation。单EDA、原资源保护及正常无墙钟/静默强停保持。M003整体未完成。

[验证提速与执行决定](M003_joint_routability_closure/validation_efficiency_2026-10-19.md)

[重启后恢复合同](../mission/M003_joint_routability_closure/server_restart_resume_2026-10-18.md) · [工程状态](../project/E011_m003_joint_routability_implementation/experiment_status/summary.md)。

[主合同](M003_joint_routability_closure/contract.md) · [启动授权](M003_joint_routability_closure/execution_start_2026-10-18.md) · [E009三摘要入口](../project/E009_m003_failed_net_attribution/README.md) · [候选决定表](M003_joint_routability_closure/candidate_decision_register.md)。

顺序：SM013归因 → SM014四表/集中选型 → SM015 RTL＋SM016入口/回归 → SM017新综合/结构资格 → SM018完整实现 → SM019全局验收。按技术依赖连续推进，常规修复不新增用户逐项批准。G2已选定M2+A3+C-P1；工程于11:17:41实际开始E011/AT001，常规阶段按已授权连续执行。

E008/AT004仍为最近实际物理基线：自然route失败，702396重叠节点/547548冲突网，9491个C01对象全SLR2；14项收尾已独立核验。M002未成功，依赖是架构/证据承接，不要求其先布通。PDU暂停已解除。

数值/ABI/双DDR/core100MHz/DDR UI200MHz、80保护和验收保持；单EDA、原资源保护、正常无墙钟/静默强停；最多3活跃含Root、无后代，不重绑旧会话，不改旧工程/冻结证据，无bitstream/板卡/GPU/PPL/ACC。

<!-- research-agent:identity-index:begin -->
## Registered identities

This index records identity and links only. Execution, conclusions and user decisions remain in the linked records.

| Mission | Title | Contract | Summary |
|---|---|---|---|
| M001 | clean_project_migration | [contract](../mission/M001_clean_project_migration/contract.md) | [summary](../results/missions/M001_summary.md) |
| M002 | ddr_separation_and_timing_recovery | [contract](../mission/M002_ddr_separation_and_timing_recovery/contract.md) | [summary](../results/missions/M002_summary.md) |
| M003 | joint_routability_closure | [contract](../mission/M003_joint_routability_closure/contract.md) | [summary](../results/missions/M003_summary.md) |
| M004 | gsm8k_accuracy_completion | [contract](../mission/M004_gsm8k_accuracy_completion/contract.md) | [summary](../results/missions/M004_summary.md) |
| M005 | multistage_rounding_precision | [contract](../mission/M005_multistage_rounding_precision/contract.md) | [summary](../results/missions/M005_summary.md) |
| M006 | mlp_linear_only_hardware | [contract](../mission/M006_mlp_linear_only_hardware/contract.md) | [summary](../results/missions/M006_summary.md) |
<!-- research-agent:identity-index:end -->
