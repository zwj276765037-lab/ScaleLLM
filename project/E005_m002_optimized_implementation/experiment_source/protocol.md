# E005：实验方案

## 真实来源、假设与基线

SM009依据[当前合同](../../../mission/M002_ddr_separation_and_timing_recovery/optimized_implementation_contract_2026-10-16.md)连续执行。保持Hadamard/ScaleCode/format05、所有数值位宽/舍入、Host ABI、双DDR职责、core100MHz/UI200+200MHz。基线为E003自然route失败与E004成功physopt定向分析；旧根只读。组合仅input48slot局部译码、MLP32row输出CE、place SSI_SpreadSLLs，physopt/router Default。历史SRL、context、reset及流水不顺带改变。

## 平台与输入身份

Vivado2025.2、xcvu9p-flga2104-2L-e/VCU118、当前主机；真实工具版本、PID/start、argv/cwd、源/TB/reference/manifest/ROM/XDC/IP身份逐AT留存。唯一实现根project/hardware和project/software；A009拥有3个RTL及功能TB，A006拥有构建/监督/物理证据脚本，运行期间不改冻结输入。新的正式create/synth使用E005新工程目录及新manifest，不沿用E003源码hash作新输入。

安装版轻量核验已取得R002/AT004：指定part后native help列SSI_SpreadSLLs，FLOW=Vivado Implementation 2025，实际run属性set/get接受目标directive；不加载大型DCP，不执行综合/布局。AT002空内存工程无run的真实失败及AT003属性核验原记录保留。

## 步骤、控制变量和独立期望

1. 入口CPU/Tcl注入：原route code/result/options保存、单诊断失败不阻止后续、无打开design、已有证据不覆盖、成功路径不变、失败父链拒收及E005授权/资源隔离。每次原日志和测试输入hash落入R002新AT，CPU测试不启动EDA。
2. A009功能交接见R001/functional_execution_list.md、functional_delivery_v1.json和frozen_before/manifest.json。Attention双wave×128group×24slot，非零互补epoch、192个slot中断场景、首尾/valid/wave127边界、随机和长stall；冻结旧模块逐拍比较加独立row-major oracle。MLP Down ROWS16/MATRICES1/S32和Gate ROWS16/MATRICES2/S24，在一个top内各自逐拍对旧模块并用独立列FIFO oracle检查payload/metadata/顺序/错误；reset/clear与fire同拍、尾mask、非法序列、stall稳定等覆盖保持。不能改gold或删断言迎合DUT。
3. 唯一EDA入口run_m002_optimized.py：xsim调用run_xsim_tb.sh并显式HAP_XSIM_TIMEOUT_SECONDS=0；create/synth调用已有板级构建入口，新综合完成后保存实际top/OOC/consumed DCP绑定和新源anchor；place/route走现有完整物理资格并适配真实新图。
4. 新综合必须确认48/32控制边界在网表存活，抓实际index/qual/localCE负载类型、数量与资源，保持SRL映射/数值数据路径，不新增非法锁存、未知黑盒或未分类时钟/未约束类别。已知综合dbg_hub_CV占位与基线同身份的530 no_clock/554 unconstrained明确记缺口，须由新OPT/debug物化及当前实际时钟图资格继续处理，不把综合占位称零黑盒或时钟覆盖完成。对新对象名使用真实driver→consumer与原始时钟/复位/CDC图，不直接复制旧名白名单。普通入口修复连续进行。
5. place SSI_SpreadSLLs→独立默认physopt→完整route，保留各阶段closed DCP/完整POST、固定与新最坏拥塞窗口、SLR/跨界与实际load位置、setup/hold/PW/DRC。资源或结构非法先修复；合法候选时序为负仍可诊断route，风险集中由A007/主控说明，不新增用户逐项批准。

## 指标、采集与结论规则

功能只以真实工具退出0、完整唯一PASS行、无ERROR/FATAL/FAIL及输入hash运行后不变判通过；静态文本检查不是仿真。综合、合法布通、时序、CDC/reset和板级范围分别判定。组合效果不冒充单项消融。

合法route须原生命令成功、closed route DCP/完整POST、routable>0、fully_routed==routable、unrouted/partial/routing_errors均0且无overlaps。时序单列WNS/TNS/WHS/THS/PW；负值不冒称收敛。控制复制/LUT或fanout改善均不能代替合法route。失败捕获写route_failed*，逐项catch取DCP/status/timing/congestion/DRC并保存原始Tcl options，然后重抛原错误；失败产物不可被成功POST/父链接收。

## 资源、异常与阶段报告

A006唯一重工具调度者，Vivado/XSim编译和仿真合计单lane，CPU0–7/max8/nice5、树RSS192GiB、MemAvailable低于48GiB持续30秒、磁盘低于30GiB触发本任务资源保护。没有阶段/总墙钟或无输出强停；有依据的协议周期断言保留。只管理本任务PID/start身份，正常结束独立核退出与锁释放。真fatal、输入身份失效或资源异常按原证据处理，新尝试新AT，不覆盖。

A006在真实启动、阶段结果、异常与终态更新自身状态并实发主控；A009解读其RTL/TB功能证据，A007作集中架构/阶段审核，主控维护三摘要、导航和用户报告。不执行bitstream、板卡、GPU或PPL/ACC，不声称未配置的后台监控。


## 2026-10-16 原监督失联后的有证据恢复

R003/AT001原supervisor失联，原status不存在、原监督/leader wait退出UNKNOWN。原native controller和既存wrapper实际自然完成0、fresh marker和完整报告/80图齐备；同PID/start接管guard保留01:42:20Z至02:17:17Z观测缺口，02:32:00Z无stop/无owned闭合。原原始记录不补造、不覆盖。资源统计只覆盖两个实际采样区间，缺口期间不声称持续达标。

普通clean-status分支保持原要求。额外恢复仅适用E005已完成的新综合，独立synthesis_supervision_recovery.json绑定原started/command/authorization/资源快照、原wrapper真实native与aggregate0、guard政策和终态、新342输入与23生产/22消费45DCP；必须当前无同PID/start活进程，完整图和来源链有效。缺wrapper、native或POST非零、资源停止、残存/活PID、源码/closure/DCP/原资源快照变化均拒收，不用23个end代填原wait0。4入口修改前原字节已归档；AT007包根调用失败保留，AT008在project/hardware执行test_m002*.py实际164项CPU通过、12工程/测试输入未变。原141输入在controller结束时全同，闭合后仅4工程入口改版并新增recovery helper，新的142物理输入独立冻结。

R004物理监督使用现有安装Python subprocess start_new_session与独立stdio分离，真实PID/start/PPID1/内核FLOCK持有者与资源采样另存。此方式减少执行会话关联；原监督失联根因未证明，不声称绝对持久保证。原综合监督缺口和UNKNOWN不因后继物理启动而关闭。

拥塞表按原生报告类型解读。新全局热点表未列出旧固定窗时记未覆盖，不能称旧热点已消失；原生tile坐标与SLICE负载包络不混用，Placer Final Level不改称physopt重新估算的拥塞。
