# Q001：M002 综合与 implementation 启动判断

> E002最新事实（2026-10-15 11:41 UTC）：正式综合、OPT、debug、入口适配及完整pre_place已完成。最后一次布局AT009在原两小时上限结束，124/native−15，无遗留进程；已到布局后时序优化，但无完整place/physopt回执或DCP，按一次恢复边界停止重复place，route未运行。准备至回执实测减少31分21秒仍不足以在本轮预算内完成；布局中间WNS−1.884ns不是完成报告。当前无活动EDA，物理基线、最终reset/CDC安全与全局验收仍未完成。见[E002状态](../../project/E002_m002_synthesis_and_physical_baseline/experiment_status/summary.md)。以下保留E001修复后的历史判断。

2026-10-15 修复后结论：**可以进入 fresh synthesis 获取当前架构的资源、时钟与告警报告；implementation 还不能直接启动。** 本轮没有执行正式综合或实现，用户授权的修复与快速验证已完成。

权重双逻辑流、专属DDR数据口、Host布局/单层权重生命周期和构建入口已修复。106项Host、49项构建CPU、9项整数参考、四套定向XSim、完整board RTL展开均通过；真实BD构造/validate返回0。[M002阶段报告](../../results/missions/M002_summary.md) 列明原始证据及适用范围。

必须保留的边界：BD有4条跨主地址别名critical（生成译码结构已静态核查，未做真实SmartConnect事务），RTL有历史复位优先级告警；implementation需要当前专属DDR架构适用的物理检查，旧检查不能沿用。未验证完整32层、时序、bitstream或板卡，未测量性能。

历史：修复前[审核](../../results/reviews/M002_readiness_2026-10-15.md)判断不具备启动条件。随后用户要求“开始修复与快速功能验证”，据[本轮合同](../../mission/M002_ddr_separation_and_timing_recovery/repair_contract_2026-10-15.md)执行。本答案更新的是修复后的技术判断，不将主控审核写成用户全局批准。

## 后续解释：为何 implementation 前还需适配检查和处理告警

用户追问后重新核对：直接阻塞是工程入口尚未适配，不是已经证明新架构无法布局布线。build_vcu118_board.tcl 第20行的place/route拒绝是本轮加入的临时保护；后续物理阶段仍调用旧mission0004/0005检查，要求旧Pblock、固定SLR归属和成员数，而这些旧物理XDC已退出M002默认输入。只删开头保护还会在旧检查处失败，需要一起替换为当前设计适用的约束和检查。

告警须分类：4条BD地址重叠已有真实生成译码结构支持跨主地址别名解释，仍缺真实互连事务证明；29条历史reset优先级告警涉及潜在仿真/综合网表差异，需要核查；逐个add_files的性能提示不应作为implementation功能阻塞。处理可以是修复或以证据确认可接受，不要求把全部warning清零。

此前“implementation前必须完成所有告警和互连验证”的说法过于笼统：工程入口适配及新综合产物是当前直接依赖；互连功能补证可以与诊断性物理实验并行，相关未决结论必须保留到最终验收，不能把启动实验和通过验收混为一谈。本轮追问仅做解释与记录，未修改构建/RTL或启动EDA。

## 用户后续执行授权

用户已明确支持“先正式综合取得新网表和报告，再适配物理入口，开展布局布线实验”。已按[新阶段合同](../../mission/M002_ddr_separation_and_timing_recovery/implementation_contract_2026-10-15.md)执行综合、入口适配及有界布局实验，本轮实际终态见页首；此前回答中的待执行状态保留为历史判断，不再构成综合/implementation禁令。
