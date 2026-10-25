# 正式测量中断：只读核查与后继建议

2026-10-25。本文件只记录事实和**未执行的方案**，不授权新压力测试、寄存器写、驱动安装或重启。当前设备操作已结束；所有原生结果保留在 `experiment_results/board_validation/power_performance/attempts/AT_20261025T014505.113183Z_native_formal/`（下称 formal）。

## 已核事实与范围

正式测试完成两个 warmup 的完整输出比较/ACK，随后 idle15s。最后 marker 为 `load_begin`（01:45:19.428938Z）；无 measured 命令成功记录，无 load_end/idle_after/terminal。85 sweep 遥测完成不证明实际负载存在。正式测量 **INTERRUPTED**，不能提供 N≥20 稳态速度、负载功耗、增量、duty 或 energy/job。初始 receipt 中 retained_lease/pending=null 不是异常后排空证明。

Windows 在 01:47:48.5Z 重新启动；Event1001 为 bugcheck0x133 参数1，WER bucket 为 `0x133_ISR_XDMA!unknown_function`。系统事件支持 XDMA ISR 关联，尚未分析 dump 栈，也未确定根因；未复制 dump。重启不是本任务发起。只读恢复通过 hap-dell-direct；原隧道 SSH 超时与系统中断分开留证。

当前（重启后）PnP9018 StatusOK/Problem0；02:00:25Z 的单次独占 control 只读探针通过：IRQ/config ID=`1fc20006/1fc30006`，2004 user-enable=1，2010 channel-enable=3，2040/2044/2048/204c request/pending=0，3014 MSI=1。只打开 control，GENERIC_READ，0次 register 写，最终 handles_closed=true。未重新核应用 ABI/idle/DDR，也未发新 job。脚本为 `probe_control_irq_readonly.py`，SHA `a67456b3ae1b37e7c52579fa001e6716878684b25a6c7f87c0934611110fbf86`；证据 `formal/control_irq_readonly_v2.json`。此前一次过长 EncodedCommand 在 Windows 命令行长度检查阶段失败；随后改为 SCP 暂存独立脚本，失败原件亦保留。

## 当前驱动来源与两个待证机制

setupapi 安装日志指向 `C:\pcie_demo\hap_tools\xdma_driver_win_9018_src\build\x64\XDMA_Driver\Win10_Release\XDMA_Driver\XDMA.inf`。相邻 build 的 XDMA.sys 与当前 System32 驱动均32256B、SHA `1b50d26131c62edd9558d37a686968df5540ac67f38033373b7b99db063684f5`。已收集该目录24份C/H；见 `formal/installed_driver_source_snapshot/`、`driver_source_identity.json`。这是相邻构建产物匹配，未进行可复现重编译/PDB源码绑定。旧2020包SYS的尺寸/hash不同，不用其替代当前来源。

1. **用户中断 mask/reenable 循环，机制证据较强，根因未证。** `libxdma/interrupt.c:377–384` 的 common enable 无条件启用全部 channel/user；399–439 ISR 根据 request 暂时 mask；442–489 DPC 调用工作回调后，477–483 的 FIXME 明确把清源责任交给 userspace，却立即 reenable 先前 pending user IRQ。`sys/driver.c:334–337` 注册所有 user callback；`sys/file_io.c:987–993` 回调只 pulse KEVENT，并不清 GU completion。当前应用仅 open user/h2c/c2h，没有 event_0。打开/read event_0 只改变通知接收，不自动 ACK GU completion。GU completion-level 可一直保持到匹配应用ACK。

   PG195 的 user request(2040)已包含硬件 enable 掩码，因此“C源码未再与enable相与”**不能**证明其是未mask原始源；也不能断言每次DMA IRQ必重启user。单次mask不构成可靠policy，是因为已排队DPC或后续EvtInterruptEnable/XDMA_UserIsrEnable仍可能恢复。当前REQ0快照不证明崩溃时没有IRQ源。

2. **空闲后电源恢复，仍无直接证据。** 对24源文件严格搜索 AssignS0IdleSettings、StopIdle、IdleTimeout、EvtDeviceD0Entry/Exit均无命中。`sys/driver.c:197–207` 只注册PrepareHardware/ReleaseHardware，power-policy callbacks为空。01:58:34Z 的 PowerData size56/MostRecentPowerState1 可解码为最近D0，仅属重启后信息，不能重建故障前D-state转换。来源为 [Microsoft CM_POWER_DATA](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntpoapi/ns-ntpoapi-cm_power_data_s) 与 [DEVICE_POWER_STATE](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/ne-wdm-_device_power_state)。保留“2warmup成功→持handles idle15s→load_begin后无进展”的时间相关性，不把15s直接认定成驱动IdleTimeout。

## 源级最小修订建议（尚未制作/编译/安装驱动）

建议以**设备级 opt-in userIrqAllowedMask=0 的应用CSR轮询模式**为候选，默认策略保持现有其它设备语义，不全局禁用MSI。只针对已确认的GU设备/实例，在中断启用之前固定策略，整个会话不动态切换：

- 在设备 context 保存 allowed mask；common enable、独立user enable、公共 XDMA_UserIsrEnable 都不得放行不允许的user bit；disable路径保留。
- common ISR 只认领符合policy的user request；DPC已有pending在重新启用前仍与policy相与；独立MSI-X user ISR/DPC也遵守同一policy，不能遗漏恢复入口。IRQ enable/IRQ同步使用KMDF已有回调锁语义，不能在已持锁的enable回调重复加锁。
- channel IRQ enable/mask/服务路径完全保留。仅用户IRQ屏蔽不是清completion，也不能替代完整C2H、gold、匹配ACK和lease排空。
- 先用源级单元/模拟寄存器验证“已有pending DPC、重复enable callback、显式UserIsrEnable均不能恢复被policy禁用user0，同时DMA IRQ继续工作”，再集中审查和决定是否构建/安装。当前未核构建链，未制作可安装产物。

这比一次写200c更完整，但仍是待验证候选修复，不能写成0x133已修复。

## 有界后继诊断建议（未执行）

先由控制方确定后继范围，再按新attempt执行：为每次驱动调用在调用前后**立即持久化**UTC、操作、CSR/offset/byte数与返回值，尤其首次resident检查/H2C/START/DONE/C2H/ACK，避免只在命令完成后写结果而丢失最后停点。当前保持不重试START/ACK、超时poison规则。

第一小步只读：系统/PnP/最近D0/应用ABI与idle确认后，独占打开只读节点，单次CSR→保持handles idle15s→单次CSR；不做DMA、不发START，不改电源policy。它只能区分“空闲后基本BAR访问是否出错”，不能排除运行态IRQ或精确证明D-state原因。任一异常即停止，保全事件，不自动restart。

只有IRQ策略与恢复前置得到明确处理后，才考虑一个完整pair、保守poll1ms、全部C2H/gold/ACK并排空的短验证。先验证短间隔，再独立attempt测试idle15s后首pair，每次仅一变量。输出失败/传输错误均停止；不可直接恢复20+正式循环，不能用减少日志、跳过C2H/ACK或新backend清账规避现场。下一轮正式功耗仍需完整idle/load/idle且负载进展可证。
