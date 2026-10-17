# M002 / SM009 / E005：可布性优化与新 implementation

用户在收到E004详细分析后明确要求：“开始优化和新的implementation”。本合同落实该新授权，取代SM008仅分析、不实施的边界；E003失败与E004分析原证据保留。阶段内常规实现、测试、定位、修复、综合及物理入口适配连续执行，不增加逐项用户批准。正常进程不因墙钟或无输出期限强停。

## 冻结方案与不变量

依据[E004优化方案](../../project/E004_m002_routability_optimization_analysis/experiment_results/optimization_plan.md)，冻结SHA256 `9b666f60371b07f67284b0ae402fda28ee3e1ae30db8bac243bd03064a7567f3`，实施首选组合：

1. Attention `hap_tensor24_buffers.sv` 双wave各24个固定256-bit slot目的写，共48个局部译码边界。保持异步payload复位、clear/valid/index控制、BRAM读延迟、6144-bit快照及全部周期/握手语义；标量控制需要时精确保留，不给整个数据bank加DONT_TOUCH。
2. MLP两个 `hap_mlp_projection_repack12_to16_s24_history2.sv` / `hap_mlp_projection_repack12_to16_s32_history2.sv` 各16行输出payload局部CE，共32个组合identity LUT1 driver。精确资格 `rst_n && !clear && input_fire && produces_output_c`；每行Gate384 bit、Down512 bit。保留metadata、valid/order/count/error、stall及同拍优先级，不改SRL历史、不增加周期。
3. 新综合、新布局选 `place_design -directive SSI_SpreadSLLs`；physopt/router保持Default。先核安装版2025.2支持和器件适用性，不静默替换为同名全流程strategy或追加扫参。
4. 安装route失败现场保存：逐项catch保存failed DCP/route_status/诊断，并重抛原route错误；失败产物不能进入成功POST和父链。测试入口支持无外部墙钟强停，保留有依据的协议断言。

VCU118 / xcvu9p-flga2104-2L-e / Vivado2025.2；core100MHz、DDR UI200/200MHz；Attention→DDR0、MLP→DDR1。Hadamard、ScaleCode、format05、数值格式/位宽/舍入、Host ABI及golden不变。唯一实现根project/hardware与project/software，旧 `/home/user/EDA-202/zhuowenjun/ScaleLLM` 严格只读。无bitstream、板卡、GPU、PPL/ACC。

首轮不自动加入SRL→FF、context、postprocess、共享loader、窄frontend、reset移除或新流水。出现实质协议/架构/数值变更由架构负责人集中修订受影响合同；独立任务继续。80个控制边界不是净80LUT增量或收益。

## 执行与验收

先保存受影响原模块和输入身份，再在唯一生产树修改。功能范围：Attention双wave/128group/24slot，非零区分payload、随机及长背压、任意slot reset/clear和新epoch；Down S32生产ROWS16/MATRICES1独立12→16列oracle及原版逐周期比较；Gate S24/MATRICES2自身payload/metadata与周期等价。覆盖同拍消费/补入、尾mask、非法顺序和错误语义，不能删断言或改gold迎合DUT。

失败取证需Tcl/CPU注入检查原错误code/result/options不丢失、单报告失败不阻止后续取证、现有证据不覆盖及失败父链拒收。安装版directive做不加载大型DCP的轻量核验。未变回归可引用原身份，实际本次测试与复用清楚分开。

功能与入口验证完成后冻结源/XDC/IP/工具/配置并正式综合。新综合网表须确认48/32局部边界及负载变化、模块资源、无新增非法锁存/黑盒/未约束路径，按真实连接适配物理检查，不能沿用旧对象名白名单或放松安全判据。已有reset/CDC限定分类仅用于诊断准入，正式安全仍OPEN；新未知项按事实定位。

新place/独立physopt保存完整DCP/POST和同阶段比较：目标索引/CE的driver与负载类型、位置/SLR分布、层次利用率、固定及新最坏拥塞窗口、跨SLR负载、时序和DRC。结构未落实或资源/约束非法时先修复；结构落实但改善不足的合法候选，架构负责人说明风险后按本授权继续一次完整route，不自行增设用户审批。不可用负setup/hold作为诊断route的自动禁入条件，也不可称其已时序收敛。

合法布通须原生命令成功、closed route DCP和完整POST，routable>0、fully_routed==routable、unrouted/partial/errors均0且无节点重叠。时序单列WNS/TNS/WHS/THS/PW；功能、CDC/reset和板级验收独立。失败则保全原错误、失败DCP和诊断，针对新证据定位；不无依据重复相同route或自动无界扫参。

## 分工、并发和资源

- 主控：本合同、SM009、goal/mission/results、E005三摘要、共享导航、阶段事件及最终整合；不维护生产RTL。
- A009（新内部工程agent，期望gpt-6.1-sol/xhigh）：独占上述3个生产RTL、受影响功能TB与模块说明、E005/R001 RTL修改及功能验证证据、agent/A009。不得改构建/物理入口；仿真启动由A006统一调度，必要时获其明确单EDA时段许可后执行。
- A006（现有m002_build_verify，期望gpt-6.1-sol/xhigh）：独占生产构建/监督/物理检查/取证脚本及其CPU测试、E005协议、R002入口适配、R003新综合、R004 place/physopt/route及新AT、agent/A006。唯一EDA调度者；执行A009交付功能测试，失败交A009修DUT/TB，常规脚本自行修。R001原始仿真AT可由A006写入，A009负责解释，二者显式交接不同时写同一文件。
- A007（现有m002_physical_architecture_review，期望gpt-6-astra/xhigh）：只读生产树，独占E005/R005架构与阶段审核、agent/A007；核合同、等价性和物理证据，重要结论及时实发主控/A006，不为普通修复增加审批包。

最多4个活动agent含主控，无后代。所有人读取research-agent与角色参考、hardware-agent及本合同；共享工作区保留他人改动。实际模型未有独立回执则记录unverified；不重绑长期旧会话。

重工具合计最多1条（包括Vivado/XSim及其编译），8 logical CPU/max8线程、nice5；沿用树RSS192GiB、MemAvailable低于48GiB持续30秒、磁盘低于30GiB的资源保护，只控制本任务进程。无固定阶段/总墙钟和无输出强停；新启动不得沿用默认300秒或12小时timeout。真实fatal、身份失效、资源异常按证据处理，不触碰其他项目进程。

每次实际尝试用新AT记录命令、输入hash、工具版本、PID/start、起止退出、资源、原日志、DCP/报告和父链；运行中不热改冻结输入。阶段成功、异常、基线失效、资源冲突、终态实际消息通知主控；主控及时向用户报告。执行状态、技术结论、适用范围和用户审核分开，不以后台启动或文件写入冒充完成。
