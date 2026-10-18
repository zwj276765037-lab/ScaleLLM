# AT004 完整place阶段独立审核

execution：实际place命令、全局POST与候选locality全部闭合成功。verdict：接受完整place诊断阶段及C01实际SLR2符合性；全局hold时序FAIL、正式reset/CDC/IO安全OPEN保持。applicability：AT004/C01当前place图与外层physopt实际启动。review：独立组合审核完成，不新增停点。

原生post_code/locality_code均0，13:23:46Z闭合；复用8份已审子步骤，补核当前compliance纯函数重放与工程完整facts逐字段一致。C01原始9491个P全部SLR2、无缺失/替换；完整有向cut与4组有界时序均有当前图真实证据。原生日志169756行为phys_opt_design -directive Default，169758行真实许可成功，169761行Starting Initial Update Timing Task，确认进入外层physopt；不声称physopt完成。

INGRESS setup/hold最差+0.603/−0.221ns，EGRESS+0.603/+0.057ns；两方向setup的16条起终点/时钟签名全部重合，不能算独立32条setup路径或每条跨cut。8,014个未知位置pair全由7个S/P排除的GND/VCC驱动；127个已知跨SLR只是逻辑pair，不是全SLL。979个touched sites中801个shared是当前占用，不是释放容量。

全局setup WNS+0.147ns，但hold WHS−0.562ns、THS−1879.853ns、34,042违例endpoint，时序仍FAIL。SLR1同place LUT336,107→282,659、register435,367→352,889；其他SLR发生大规模重排，不能将全局delta归因C01。SLR数字只使用独立验证的唯一顶层LUT/register/BRAM/URAM/DSP行；重复using-O5/O6子行字典覆盖限制保留。

高拥塞、自适应窗口不可直接比、固定原热点改善未证、RTSTAT-13及exception覆盖限制、正式安全OPEN均保持。未证明route成功、full-cut TNS、拥塞因果改善或物理签核；最终输入/进程/资源收尾待真实terminal。审核未运行EDA、读取/hash DCP、控制进程/锁或改工程消费包。
