# GU 上板功耗与速度：当前有效结果

2026-10-25。状态 **PARTIAL / 正式持续测试中断，驱动修复准备已授权**。

| 指标 | 已取得结果 | 适用范围 |
|---|---|---|
| 空闲功耗 | 约 11.3 W | 7 路被监测电源输出之和；21 个有效 sweep，按时间加权 11.2780 W，采样中点覆盖 12.93 s |
| GU 硬件 compute 窗口 | 约 7.35 ms/命令 | 6 个成功探索样本；100 MHz 名义时钟，含硬件内等待；非持续吞吐验收 |
| 等效算力 | 约 0.511 TOPS | 生产形状 16×4096×14336、Gate/Up 两矩阵，按 MAC=2 ops；基于 pilot 两个 measured 样本的中位 compute 窗口 7.353005 ms |
| 正式有效 measured 命令 | 0 | 两个 warmup 成功，进入 load 阶段后无 measured 完成记录 |
| 有负载功耗、增量功耗、持续吞吐、能耗/命令 | 尚未建立 | 正式测试被 Windows 蓝屏中断，不能从遥测完成推断真实负载持续存在 |

7 路电源和不是整板输入功耗，也不是 FPGA 裸片功耗。三路 MAX20751 READ_POUT 的编码分辨率为 2 W，合计约 ±3 W 半步量化范围；这不是完整测量精度，平均不能消除系统量化。后三项未经有效负载采样，不能计算可信能效。

生产形状的每个命令计 1,879,048,192 MAC / 3,758,096,384 ops。compute/load/writer/stall 计数相互重叠，禁止相加为端到端时间。原生 host 观测、传输与输出比较时间另保留在每次运行 receipt，不把 SSH/RPC 延迟算为 FPGA 计算耗时。探索样本完整输出均通过独立整数 gold 比较后 ACK；不能替代正式 N≥20 的持续结果。

## 中断与处理

正式运行出现 bugcheck 0x133；Windows WER 指向 XDMA ISR。已安装驱动的源码有用户完成源尚未被应用 ACK 清除时在 DPC 中重开用户中断的路径，构成重复中断候选机制，尚未证明为全部根因。机器已重新开机，用户确认桌面正常；重启后仅完成设备/control 只读核查，应用 ABI/idle 未重新验证，无新 job。

用户已授权准备驱动修复。当前只制作独立候选、离线验证、编译与恢复材料，安装前提交具体方案确认。原驱动、原 bitstream、冻结源与本次失败证据保留。

## 证据

- [图与独立复算数据](figures/partial_measurements.json)
- [初测图](figures/partial_measurements.png)
- [集中审核](review.md)
- [正式运行中断摘要](attempts/AT_20261025T014505.113183Z_native_formal/interruption_summary.json)
- [驱动准备授权](driver_repair_authorization.json)
- [只读核查与后继方案](../../../experiment_source/gu_only/board_validation/measurement/interruption_followup.md)
