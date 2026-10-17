# E002：执行状态

execution_state: running
verdict: unassessed
applicability: 当前新工程fresh create/synth阶段，未获得综合终态。

A006唯一执行EDA，AT001_fresh_create正在受管运行；新项目m002_E002_R001_AT001_fresh。A007策略和A004源码告警只读子阶段已交付，代理空闲，待新综合网表时复用集中核查。源/综合构建输入保持冻结。

资源合同：总8logicalCPU、单路EDA、nice5、RSS192GiB及系统可用内存/磁盘保护；create30min、synth3h上限。create正常完成后自动synth；获得新网表后再适配物理入口并place/route。未授权bitstream/板卡/GPU/PPL/ACC。
