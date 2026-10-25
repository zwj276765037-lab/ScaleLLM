# M006 GU-only 实际上板阶段集中审核 — 2026-10-25

**结论：LIMITED_PASS，当前实际测试范围无阻断。** 指定工程验证版已在 Dell/VCU118 完成 SRAM 配置、恢复后 CSR 校验、双 DDR 有界读写与恢复，以及两套完整生产形状诊断各两个 cohort。四个 GU 命令合计 **5,505,024 输出字节 / 1,835,008 个 S24 值**，本审核重新读取实际输出文件，逐字节与冻结 gold 比较，全部相等。Max-DPO、external reset 签核仍 OPEN。

| 维度 | 记录 |
| --- | --- |
| execution | 本次只读集中审核 completed；未操作 Dell、未写设备、未运行 EDA |
| verdict | LIMITED_PASS：本 bit、当前 Dell 驱动/transport、两套结构化诊断的板级局部功能 |
| applicability | bit SHA `66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47`；GU-only v7/caps `0x1d`；16 rows/K4096/N14336；两个诊断 bundle |
| review | 本角色独立证据审核完成，供 Root 集中整合；不冒充用户最终验收或 G5 完整签核 |

当前执行授权见 [execution_authorization_20261025.json](execution_authorization_20261025.json)。唯一 Dell owner 为 `/root/board_host_prepare`。本审核不增加逐项批准门，不改冻结 XCI/RTL/ABI/旧报告。下列历史失败保留原状态。

## 1. 下载、恢复与基本通信

| 实际步骤 | 审核结果与证据 |
| --- | --- |
| SRAM program | [program 原始输出](AT_20261025T011600.863121Z_program/program_and_probe.stdout.txt)：指定 cable `210308B76D50`、target `xcvu9p_0`，bit 80,159,259 B / 指定 SHA，program/probe exit=0。使用 Dell Vivado/hw_server 2022.2 实际成功，不因生成版本 2025.2 推断需升级工具。没有 flash 写入 |
| 配置状态 | [configuration_observation](AT_20261025T011722.916109Z_collect_program/configuration_observation.json)：三 SLR 的 CRC_ERROR=0、INIT_B internal/pin=1、DONE internal/pin=1。本审核复算其原始 `configuration.stdout.txt` SHA，匹配 `6fdc0be75c717fb36a7290b0bac7dc10821ba4e27baaabb763f1f472c498b7ad`。仅此项本身不证明应用功能 |
| 首次 CSR 失败 | [原失败](AT_20261025T012136.428143Z_csr/result.json)及同目录快照：16 个读数均 `ffffffff`，身份检查失败；hardware_writes=false、scratch未跑。未把该次改写成 PASS |
| 精确设备恢复 | [restart 原始输出](AT_20261025T012357.782981Z_pcie_restart/restart.stdout.txt)：仅 `PCI\VEN_10EE&DEV_9018&SUBSYS_000710EE&REV_00\4&3533FCBB&0&0008`，`pnputil /restart-device` 成功/exit0；不是整机重启。前置 scan 与失败诊断仍保留，不能单凭“restart后读通”断言唯一根因 |
| 恢复后 P3 | [三份快照](AT_20261025T012429.910764Z_csr_after_restart/csr_snapshots.json)完全一致：Attention `48384103/00020000`，MLP format/ABI `48384605/00070000`，memory `4d303032`，linear ABI/caps/layout `4d4c0002/1d/1`，job status=8，owner/paired=20，其余所查错误/maintenance=0 |
| P4 两 DDR | [scratch_result](AT_20261025T012513.161146Z_dual_ddr_scratch/scratch_result.json)：两路 local `7fff0000`，Host `7fff0000/ffff0000`，各4096 B。审核重新比较原始 bin：写DDR0后DDR0=pattern且DDR1=原页，写DDR1后两pattern各自正确，最终两路恢复读回均逐字节等于原页，无alias。只证明该两页及本次路径 |

DDR readiness 仍明确为本版双 MIG ready 门控 core reset 所支持的推断，并由两路实际 DMA 成功补充；没有伪造独立 calibration CSR 读数，也不以本次成功替代外部复位全协议验证。

## 2. BAR 规格澄清与旧计划修正

旧计划把“OS 必须分配 4 GiB PCIe BAR”作为进入 DMA 的前置条件过强，**该阻断条件不适用于当前已实证路径**。三个不同层面的证据必须分列：

- **构造/生成参数**：`project/hardware/vivado/scripts/create_mlp_gu_board.tcl` 显式设置 `pf0_bar0=1 MiB/64bit`、`pf0_bar2=4 GiB/64bit`；constructor 下 `scalellm_vcu118_f05_bd_xdma_0_0.xci` component 参数仍如此，generated `PF0_BAR0_APERTURE_SIZE=0x0D`、`PF0_BAR2_APERTURE_SIZE=0x19`。这是实际源记录，本审核不将其删改或声称从未配置过4GiB BAR。
- **Windows 实际已分配资源**：[restart 原始资源](AT_20261025T012357.782981Z_pcie_restart/restart.stdout.txt)为 `0x70600000–0x706fffff`（1 MiB）及 `0x705f0000–0x705fffff`（64 KiB）。Win32 资源范围本身不标明每段的 PCIe BAR index，本审核不擅自给这两段编号。配置参数与此观察存在差异；本次没有完成其来源归因。
- **DMA AXI 地址窗口**：构造中的 XDMA M_AXI 对 DDR0/1 分别映射 `[0,80000000)` 和 `[80000000,100000000)`。H2C/C2H 提交的是该 AXI device address，不要求把每个 DMA 地址直接映射成同大小 CPU MMIO BAR。实际 Host `ffff0000` 的 scratch 及后续 DDR1 GU 读写已经通过，证明本次所用地址在当前路径可达。

因此不要求扩大 BAR、修改 XCI、重装驱动或重启主机；保留上述非阻断差异，不能由实际1MiB+64KiB反推整个4GiB地址空间已穷举验证。CSR `user` endpoint 与 XDMA 内部 `control` endpoint 仍按实际驱动明确区分。

## 3. 诊断数据、独立参考与首错行为

审核对象：[structured_v1](diagnostic_gu/structured_v1/manifest.json)、[s37_cancellation_v1](diagnostic_gu/s37_cancellation_v1/manifest.json)，以及 [runner](../../experiment_source/gu_only/board_validation/diagnostic_gu/run_gu.py)、`diagnostic.py`、`verify.py`。均显式 diagnostic_only，不冒充真实模型权重或32层catalog。每套包含两份29,360,128 B GU weights、7,340,032 B metadata、73,728 B REC576和1,376,256 B gold；本审核重新复算全部10个数据文件SHA/size并匹配manifest。

两套已有 wire oracle 分别核458,752个输出、120个Python标量坐标，原 exporter 有界 tile parity 通过。审核检查其数学和packing实现后，另用不导入生成器/验证器的临时只读脚本，从实际权重 nibble、28 B metadata、REC576 字节直接按128groups×32lanes重算每套120坐标（rows0/7/8/15、两matrix、half/块边界与尾列14335），全部匹配实际gold；本次抽查不伪称独立重算所有458,752值。

| 用例 | 已核覆盖 |
| --- | --- |
| structured_v1 | groups0/1/126/127；全16行、两matrix、两logical half、896tiles；shift20/24/25/44；±0.5 half-away ties；正负值；S24双侧饱和；非饱和尾列标记。458,752输出均非零，189,095负/269,657正，64个饱和值 |
| s37_cancellation_v1 | groups0..14大正负项严格抵消，groups15/127留下小结果；guard最大绝对值67,917,312,000合法S37，审核抽查最大partial绝对值475,421,184,000合法S44；输出范围−48..7160、无饱和。假设S36截断时，独立抽查120/120坐标输出不同，能够识别此类丢位而非被最终饱和遮蔽 |

两条参考路径遵守 S17 dot→S33 raw→S37/F24对齐→S44所有group精确累计→一次half-away shift8→S24饱和。验证器检查metadata末4 B、REC576 padding/reserved、canonical zero和全部inactive group为零。不能将稀疏结构化成功外推任意真实权重或完整模型精度。

runner先落盘完整output、DONE和逐字节/value comparison，只有数值PASS才ID ACK；异常或mismatch保留首错、pending/lease，不自动reset、不发第二cohort。[CPU负例](diagnostic_gu/driver_cpu_selfcheck_v1/result.json)验证mismatch不ACK/不再START，只作为软件行为证据。实际测试未注入板级故障，故不声称板上fault recovery覆盖。

## 4. 四个生产 GU 命令的实际结果

| attempt | 命令与身份 | 本次独立核对 |
| --- | --- | --- |
| [structured](AT_20261025T012608.431477Z_gu_structured_2cohorts/receipt.json) | epoch1/request1/commands1,2，cohort0/buffer0及cohort1/buffer3 | 两份输出各1,376,256 B逐字节等于gold SHA `23e993b366a9e90580237ab63474f2813bf0f6009aced7f701ba2bc6893b20bc`；所有DONE身份/计数匹配；两次ACK后status=8；release=true/lease=null；exit0 |
| [S37补例](AT_20261025T012650.455542Z_gu_s37_2cohorts/receipt.json) | 主例release后新epoch2/request2/commands3,4，同两cohort/buffer | 两份输出各1,376,256 B逐字节等于gold SHA `dcc2ffa2238305741006f99055f897ed4bf4423daed79e554614e71d7144c631`；所有DONE身份/计数匹配；两次ACK后status=8；release=true/lease=null；exit0 |

四次DONE status=`0x60a`（phase6、completion/quiescent置位），opcode1、input73728/output1376256/records1792、DONE_ERROR/admission均0；后ACK status=8。cohort1的cohort_buffer=`0x00030001`，命令/request/epoch逐次符合上表。审核重新核每份receipt的7个代码身份当前SHA，全部一致，包括backend、runtime、codec与有效ABI `318cf64064354aed52943fd21909aa8b67f11ca8fb565a37c65441d522d4938a`。

两attempt的 `execution_identity.json` 绑定同一local/remote Windows桥 SHA `ff64ca61a9bb1345d55fd805e4c43f67c13538de1f58db60580453e1a369fa91`、8 CPU/8 GiB、no_retry；S37明确引用前一已release的lease。桥使用overlapped I/O、5秒deadline、CancelIoEx及未排空buffer quarantine；RPC有界返回，异常禁止后续I/O。本次成功不等于已经真实故障注入验证所有取消分支。

本轮可接受“指定工程验证版的SRAM加载、恢复后CSR、两DDR有界DMA、两套生产GU诊断通过”。不增加未来测试作为本次通过条件；完整32层、Host Down/Attention链、真实模型精度、吞吐性能、所有DDR地址及G5未闭合签核均不在本结论覆盖。最终只读idle/本任务进程清理由Dell owner单独收尾，Root据其实际回执整合；审核本身没有监控或清理他人进程。
