# AT004 完整 physopt 阶段独立审核

execution：实际 physopt 命令、全局 POST 与候选 locality 全部闭合成功。verdict：接受完整 physopt 诊断阶段及 C01 实际 SLR2 符合性；全局 hold 时序 FAIL、正式 reset/CDC/IO 安全 OPEN 保持。applicability：AT004/C01 当前 physopt 图及实际 route 启动。review：独立组合审核完成，不新增停点。

原生 post_code/locality_code 均 0，2026-10-17 15:18:14Z 闭合，POST/locality 共 6,719 秒。复用 7 份当前 physopt 子审核及已审旧基线数值，补核当前 compliance 纯函数重放与工程完整 facts 逐字段一致。C01 原始 9,491 个 P 全部位于 SLR2，无缺失/替换；完整有向 cut 与 4 组有界时序均有当前图真实证据。原生日志 254173 行为 route_design -directive Default，254175 行许可成功，254178 行 Starting Routing Task。工程 route 启动交接中的闭合事实绑定、回执、符合性、时序及原生日志片段已独立核对；其中实时资源/进程观察仍归属于工程。

INGRESS setup/hold 最差 +0.603/−0.221 ns，EGRESS +0.603/+0.057 ns；两方向 setup 的 16 条起终点/时钟签名全部重合，不能算独立 32 条 setup 路径或保证每条跨 cut。8,014 个未知位置 pair 全由 7 个 S/P 排除的 GND/VCC 驱动；127 个已知跨 SLR 只是逻辑 pair，不是全 SLL。979 个 touched sites 中 801 个 shared 表示当前占用，不能换算为释放容量。

全局 setup WNS +0.147 ns，但 hold WHS −0.562 ns、THS −1879.853 ns、34,042 个违例 endpoint，时序仍 FAIL。原生 physopt 因 WNS 非负跳过 setup 优化并报告网表未修改；当前时序与 place 相同，不能据此声称优化收益。SLR1 同 physopt LUT 336,107→282,659、register 435,367→352,889；其他 SLR 发生大规模重排，不能将全局 delta 归因 C01。SLR 数字只使用独立验证的唯一顶层 LUT/register/BRAM/URAM/DSP 行；重复 using-O5/O6 子行字典覆盖限制保留。

高拥塞、自适应窗口不可直接比、固定原热点改善未证、RTSTAT-13 及 exception 覆盖限制、正式安全 OPEN 均保持。没有 route 完成、full-cut TNS、拥塞因果改善或物理签核结论；最终输入/进程/资源收尾待真实 terminal。审核未运行 EDA、读取/hash DCP、控制进程/锁或改工程消费包。

详细证据、身份与限制见 [JSON 审核记录](physopt_combined_stage_review.json)。
