# R004 · route未运行说明

route NOT_RUN；command/start/end/exit均为null，没有虚构route失败。依赖R003完整physopt DCP及其实际成功POST/终态链；AT009按原2h截止停止，无place/physopt成功receipt或DCP、无survivors。见not_run_reason.json与AT009/terminal_facts.json。

遵守单次恢复边界，不再重复place；私有续接候选仅持久保留、未安装/未执行，不能充当route parent。物理目标未完成，算法/数值与时钟合同未改。
