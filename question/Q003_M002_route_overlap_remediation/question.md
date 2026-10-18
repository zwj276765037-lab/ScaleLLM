# Q003：M002_route_overlap_remediation

## 用户原问题与背景

2026-10-18 用户原问题：“这些重叠节点到底怎么解决”。背景是 E008/R001/AT004 自然布线失败，最终 702396 个重叠节点、547548 条拥塞失败信号；C01 的 9491 个物理对象已经实际迁到 SLR2。

用户随后明确希望知道具体修改项，并要求“一次到位，一次修改完毕”。已进一步形成[联合修改范围与完成标准](../../mission/M002_ddr_separation_and_timing_recovery/joint_routability_change_plan_2026-10-18.md)：集中收敛RTL、物理约束、测试和入口，区分已确定语义与待归因冻结的物理配置；未承诺一次布通。

## 关联与负责人

M：M002；SM：SM012；E：E008；承接角色：controller。

问题类型：技术解释与后继优化判断。状态：answered；工程拥塞缺陷仍未解决，候选收益待验证。

## 证据版本与处理范围

依据本轮保存的 Vivado 2025.2 / xcvu9p 失败日志、route status、拥塞报告、已审 physopt 分 SLR 资源及当前冻结 RTL。此次只读解释和候选评判，未修改 RTL/约束、未运行 EDA 或启动下一次 implementation。沿用 research-agent/hardware-agent 与原算法、数值、接口、时钟和保护边界；新架构或延迟/吞吐变化需要另行明确受影响合同与验证。

## 2026-10-18：正式mission定义

用户进一步要求“定义成完整详细的mission”。已形成[M003主合同](../../mission/M003_joint_routability_closure/contract.md)、七个子任务和[验收矩阵](../../mission/M003_joint_routability_closure/verification_matrix.md)，集中规定RTL、有效物理约束、测试、新综合和完整实现。当前为planned，仅任务定义；原Q003拥堵缺陷尚未验证解决，不因新mission建立而关闭工程问题。
