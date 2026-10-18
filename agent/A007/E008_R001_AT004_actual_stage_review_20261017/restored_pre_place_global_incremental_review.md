# AT004 恢复 pre-place 与真实布局启动独立审核

execution：独立证据核查完成；verdict：接受恢复后的诊断资格与真实 place 调用；applicability：AT004/C01，本轮有限 live 检查与父完整 POST 分列；review：完成。

144 项生产输入、39 项原归档运行源身份保持。175 个继承约束来源全部核对实际或保留原字节，162 项 metadata 与真实 registry 一致、13 个来源归档保持；本轮 new_actual_reads=[]。候选 overlay 与已审 membership/Pblock/policy/cut/timing 身份一致。

本轮 native restore 回执0，blackbox0、DRC blockers0，6类合计15,914条 Warning 保留。内部 no_clock/constant_clock/pulse_width_clock/unconstrained 均0；三时钟族互不相交；7 async 与4 AUX复位链各4级，6个精确目标存在。外部 reset input1/output2未设delay继续OPEN。debug实际50MHz、2×265端点与父证据一致；声明300MHz差异保留。

完整 reset/CDC/BRAM/原pre-place POST 按同身份旧证据复用，不写成本轮新测。80个保护边界的旧 synth/place/physopt 三表及结果身份与已审 AT003 相同，复用其48/16/16、CE负载及DONT_TOUCH全1结论；当前恢复pre-place没有新80全表，已归档原生POST检查保持，后续当前place/physopt/route各自再核。

两份冻结日志前缀与当前日志前缀一致，先完成恢复检查，再真实调用 `place_design -directive SSI_SpreadSLLs`，实际取得Implementation/xcvu9p许可并进入Starting Placer Task。place完整回执、POST/locality、physopt/route及正式时序仍待实测。正常实现继续；无新增审批门。

机器证据：`restored_pre_place_global_incremental_review.json`。审核未读取或哈希DCP、未执行EDA或控制进程/锁。
