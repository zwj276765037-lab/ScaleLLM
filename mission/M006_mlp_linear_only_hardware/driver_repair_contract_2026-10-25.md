# M006：Windows XDMA user IRQ0 polling 候选修复合同

状态：**准备范围冻结，允许工程连续实现/编译/离线验证；尚未安装或设备复测**。用户已要求“继续准备修复，完成后续测量”；当前Root将安装视为需具体候选、签名与恢复方案齐备后的一次确认，不把普通修复拆成逐项审批。该确认将覆盖确定候选的安装与所列有界复测；此前不做driver install/load、trust/testsigning修改、重启、寄存器写或GU job。原正式测量仍为HOST_INTERRUPTED，0 measured，原始证据不变。

唯一工程owner为 `/root/board_host_prepare`，在独立 `driver_repair` 副本实现；审核者 `/root/board_contract_review` 仅维护本合同及 `power_performance/review.md`。其他人同时工作，不回退他人文件，不覆盖已安装包、原源码快照、RTL/ABI/bit或历史证据。资源最多8CPU/8GiB，不启动EDA/GPU；无后代。

## 问题与候选机制

已安装XDMA.sys为32,256B，SHA `1b50d26131c62edd9558d37a686968df5540ac67f38033373b7b99db063684f5`；同目录build binary与其匹配，24份源快照size/SHA已核。shared ISR读取user request后mask，DPC仅通知KEVENT便按软件pending重新enable；GU完成源需等完整C2H、gold比较及应用ACK后才清除。PG195规定source已高时enable也产生中断，因此可形成重复IRQ的候选机制。WER bucket为`0x133_ISR_XDMA!unknown_function`，但缺崩溃时调用栈/ISR频率，**候选修复不等于根因已证**。

0x2040 userRequest按PG195已含硬件enable mask；没有软件AND不证明raw源绕过mask。单次用户态mask可能被已排队DPC、重新Enable callback或公开Enable API恢复，不能作为耐久修复。24份源无显式S0 idle设置或15秒timeout，当前修复不触碰power policy。

## 固定实现合同

1. 新增独立per-device `userIrqAllowedMask`，默认`0xffffffffU`。显式专用编译开关默认off；仅当开关on且已成功识别PCI vendor/device为`10ee:9018`时固定为 **`0xfffffffeU`，只禁止user0**。其它user位/设备及开关off保持原策略。身份读取失败不能在专用路径中静默误认；沿已有失败处理停止初始化。policy在SetupInterrupts及任何enable callback前确定，运行期间不由硬件enable瞬时值、用户event开闭或新IOCTL修改。当前GU bit只有user0，但不扩大到禁全部16位。
2. 同一policy必须覆盖现有全部五处user W1S（原interrupt.c:383/482/542/584/694）、shared/per-user ISR认领、DPC派发及re-enable。Enable callback明确W1C清掉policy禁止位；软件pending中禁止位不能在后续DPC重开，也不派发给user callback。导出UserIsrEnable对被禁止事件返回明确不支持，不虚报成功。正常Disable路径保留。
3. policy表示长期“允许哪些user IRQ”；不能在DPC简单AND当前硬件enable来替代它，ISR已临时mask的正常事件会被错误抑制。保持现有interrupt lock与回调IRQL约束，IRQ路径不引入阻塞、分页调用、睡眠或用户态等待。
4. **DMA channel IRQ、engine work、DMA寄存器/描述符/超时、MSI模式、power policy、应用CSR ABI和先copy/compare后ACK全部不变。**不能全局关MSI或提前应用ACK；仅开event0也不会清FPGA源。实验包限定已核Dell9018实例与本polling诊断，失去user0通知是显式行为；主机继续从应用CSR识别DONE/error/reset_required。
5. 不开发通用event ACK/re-arm协议，不新增runtime开关或电源设置。必要兼容修复可在授权准备范围连续完成，但如涉及DMA/power/ABI行为，先报告为合同范围变化，不静默扩展。

## 离线验证：证明反馈被切断且DMA可继续

至少执行下列事件序列；优先编译实际候选C函数配WDF/MMIO stub，或从源可追溯提取并记录提取范围/SHA。只做文本搜索、复制mask表达式或重写算法的测试不能单独满足此项。

硬件模型采用独立规范：request=source AND enable；W1C仅屏蔽不清source；W1S将低enable位开到高且source仍高时产生新IRQ；DMA cause/enable独立。callback只通知事件，source保持至模拟应用ACK。给每个序列有限步数，记录IRQ/DPC/callback/DMA-work/enable演变。

| 序列 | 期望与区分力 |
| --- | --- |
| 原allow-all代码，user0源保持高，ISR→DPC | 重复触发达到有限步数界；证明harness可暴露本候选反馈，不能先假定旧代码通过 |
| 专用9018 policy、user0高 | 不认领/派发/re-enable禁止位；不得出现user0自激 |
| 注入旧pending user0，再运行DPC或Enable callback | 不复活user0；验证单次BAR mask无法提供的持久策略 |
| 同时DMA cause与user0源高，共享IRQ | engine work仍执行、channel使能按旧行为恢复，user0不恢复；明确未以关全部IRQ消除问题 |
| user1与非9018/开关off | 允许事件及旧策略保持；有源清除时一次服务并可接收下一事件 |
| UserIsrEnable(0)、MSI-X user路径 | 禁止事件拒绝且无enable写复活；其它允许事件按原行为 |
| 关键mutation | 去掉DPC恢复policy或把Enable改回全enable，应使至少一个上述测试失败；避免“测试只是实现文本镜像” |

每项可用同一小harness完成，勿扩成新驱动框架。编译实际x64 Release候选并记录WDK/compiler/flags/log/源diff/hash、SYS/INF/CAT身份、签名验证与目标平台；可同时编译默认off用于回归。离线stub通过不代表WDF/IRQL/真实PCIe运行通过，构建通过不代表驱动可安装或已解决蓝屏。工具缺失则明确NOT_BUILT，停止在真实依赖，不擅自安装工具、证书或启用testsigning。

## 交付、集中审核与后续设备边界

工程交付独立patch/源码、机理测试原始输出及mutation结果、实际构建日志、签名状态、源→产物身份表，并保留原oem113.inf/对应driver-store包、原SYS SHA、精确PnP实例与现行服务配置。恢复方案必须明确如何回到原包及核回原hash/PnP状态，不能靠覆盖System32单文件；当前只准备恢复命令/物料，不运行。

候选完成后集中审核一次；普通修复与相应离线验证不重新索取确认。若需实际安装及继续测量，Root先向用户展示具体候选、预计影响、测试与恢复方案，取得**一次安装及有界复测确认**。不为每个命令新增批准门。确认之前不碰设备写/job/driver install/load/reboot。

届时拟按以下顺序执行（本合同只设计）：核精确实例/候选hash及user0禁用、DMA channel enable保持→一个完整pair验证C2H/gold/ACK→idle15s后的单次完整pair验证首次访问→少量稳定pairs。每次驱动调用前后先落持久化标记，记录IRQ模式/enable/DONE/error；首错停止、不自动重启或重提。只有这些界限内稳定通过后，才延续原测量合同的2warmup、至少20有效命令及idle/load/idle真实遥测；恢复通信、样本数或负载状态不足均不能拼接冒充正式结果。为区分修复效应，先固定保守轮询，暂不同时引入poll0性能优化或电源策略改变。

详细G5、Max-DPO、external reset仍OPEN。本任务的准备通过、候选安装、设备数值通过、持续测量完成与根因归属分别记录。
