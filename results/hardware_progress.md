# 硬件实验进度

| M/SM/E | 当前版本 | 功能仿真 | 综合 | 实现/时序 | 上板 | 剩余事项 |
| --- | --- | --- | --- | --- | --- | --- |
| M002 / SM007 / E003 | 冻结设计/默认策略；150项恢复入口CPU及真实来源验证通过 | 复用输入未变的E001范围 | 复用正式综合 | place/独立physopt命令、DCP和完整POST成功；正式physopt WNS−1.290/WHS−0.620ns。route运行5小时17分45秒自然失败1：245279重叠节点/248289拥塞失败信号；无route DCP/完整最终报告 | 未运行 | 本轮已结束，无残留EDA；最后完整恢复点physopt，未合法布通、时序及正式CDC安全未签核 |
| M002 / SM005–006 / E002 | E001最终源；339综合输入与45 DCP路径冻结 | 复用输入未变的E001范围 | fresh create/synth完整完成，exit0；LUT71.18%、DSP79.69%、URAM78.33% | OPT、debug与完整pre_place完成；AT009准备减少31分21秒后仍在布局后时序优化达到2小时上限，124/−15，无完整place/physopt DCP；布局中间WNS−1.884ns/TNS−1349.388ns，非完成报告。已停止重复place，无活动EDA；独立physopt/route未运行 | 未运行 | 完成布局/布线基线未取得；跨SLR放置、时钟与高扇出告警影响待测；正式reset/CDC/约束安全和完整功能待验 |
| M002 / SM002–004 / E001（历史前置） | 2026-10-15修复源，各AT保存hash | 四套定向XSim通过；非完整32层模型 | 完整RTL展开通过；该阶段未正式综合 | 该阶段未运行 | 未运行 | BD地址别名critical、历史reset告警、真实互连事务 |

[阶段报告](missions/M002_summary.md)和[E002状态](../project/E002_m002_synthesis_and_physical_baseline/experiment_status/summary.md)给出当前证据及边界；正式综合执行完成不代表覆盖、物理时序或板级通过。已取得真实资源报告，尚无吞吐、时序收敛或可用bitstream结论。
