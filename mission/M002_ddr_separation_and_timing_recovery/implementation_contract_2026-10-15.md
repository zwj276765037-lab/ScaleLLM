# M002：正式综合及布局布线实验合同

用户最新授权（2026-10-15）：“我支持先正式综合取得新网表和报告，再适配物理入口，开展布局布线实验”。它取代此前本轮不得综合/implementation的阶段限制；E001快速验证仍作为已完成历史证据，不覆盖原报告。

## 目标、顺序和范围

1. SM005：使用E001最终修复源，新的项目/报告目录，完成正常create（含IP outputs）和fresh synth；取得实际网表/DCP、资源、时钟、CDC、DRC、setup/hold估计和全部告警报告。
2. SM006：依据新综合网表和报告，适配当前M002物理入口及检查，然后完成一次可解释的place/phys_opt及route基线实验。预先只读梳理可并行；物理实现须依赖真实完成的新综合。不恢复native025及旧工程任务。
3. 可以做维持合同的常规构建/约束/RTL实现错误修复和受影响回归；不逐次要求用户批准。禁止通过删功能断言、改golden、松数值或无依据时序例外凑PASS。新架构/接口/数值/时钟语义改变由Astra主控集中评判，不静默扩大设计。
4. 不运行bitstream生成、板卡、GPU、PPL/ACC。完整32层数值验收未包含于此次物理基线，告警及未覆盖项不能因implementation完成而关闭。

## 冻结规格与物理判断

器件xcvu9p-flga2104-2L-e，Vivado2025.2，VCU118。core100MHz、DDR UI200/200MHz；Attention→DDR0，MLP→DDR1；双逻辑权重流、256bit独立数据口、六CSR local offsets和layout ID不变。Hadamard、ScaleCode、format05/ABI、S24/S32、舍入、golden不变。权威来源goal/goal.md、project/hardware/source/design.md、m002_dedicated_ddr.md和E001各AT源身份。

不能把旧Pblock/SLR固定归属、DSP分区数和1929 terminal计数当作新架构验收。先用新综合网表核对实际层级、资源/时钟/CDC/DRC；物理入口保留真实输入身份、时钟覆盖、资源适配、合法连线和工具错误检查。首个实验优先工具自主布局，不新增未经证据支持的硬LOC/Pblock，不更改100MHz目标。

允许负slack候选进入有明确标记的诊断性布局/布线以取得真实瓶颈，负值必须原样报告。工具运行完成、诊断候选可继续、最终时序收敛分别记录；不伪造S3 PASS或绕过真实DRC错误。容量不可实现、缺时钟/约束、未解析黑盒、工具致命错误等必须先定位。若现有检查对诊断入口不相容，显式建立诊断语义，不冒充生产签核。

2026-10-15 实际入口修复选择：R003/AT002已完成真实project link并保存init.dcp，后置CDC对象查询失败，原impl_1和AT002失败状态保持。允许新AT从该project-init DCP自管恢复→补未完成探针→OPT→调试模块生成→place/phys_opt，以避免重做无变化的完整link；这属于原授权内常规修复，不是新增用户批准。新execution_mode须绑定原失败终态、归档源码、DCP生成阶段/hash、完整综合339输入/45 DCP及身份anchors、原child log的实际XDC顺序/scope及162项约束bytes/metadata。恢复后验证真实design/时钟/debug/有效例外，约束标记为检查点内继承，不能伪称本轮重新读取。补齐6CDC/3reset IO、head-wave局部控制cone及XPM端点证据，并执行真实place前检查。新自管执行的实际exit/完成记录/DCP定义后续route父链；不为失败的project run补造成功receipt。重复告警取证可按阶段裁剪并明确复用范围，不能以有限样本代替全量安全结论；资源和时间上限不变。

2026-10-15 原生流程核查纠正：实际impl_1生成Tcl的223行调用opt_design，287–290行在place_design前另行调用implement_debug_core，当前自管入口遗漏后者。随后AT004真实OPT已进入Generate And Synthesize Debug Cores并生成xsdbm:3.0；本机原生命令手册也明确OPT自动实现debug。因此不能将额外显式调用的遗漏说成OPT缺少实现能力；保留该调用是沿用原生顺序，并设置独立检查点。保留真实OPT DCP/报告及实际生成阶段，在新AT显式执行implement_debug_core，保存独立debug_materialized/pre_place检查点，再要求零黑盒、完整实际时钟覆盖、DRC及限定CDC/IO等准入。只有已核实的工具debug链可带PENDING进入该处理，未知黑盒或其他覆盖缺口不得放行；不改冻结源码或放宽最终检查。

AT004已核实恢复临时project实际IP cache为read/write，原XPR禁用策略未继承。两PHY worker日志均为no cache hit后实际综合；已归档121文件/65,898,981 bytes。debug另存23文件/867,221 bytes及实际xsdbm参数、工具/生成成功与DCP身份，可作诊断派生产物；5份被工具清理的worker OOC XDC原字节/hash缺口保留，不仅因此重跑。生成out XDC字节不等于主设计实际加载证据，OOC 3.333ns不等于主设计频率。后继从同OPT DCP恢复时应核hub输入/两输出/相关530扇出C的实际clock period/master/source及checkpoint有效约束/scope，并在实际恢复project上关闭并记录cache。新post-OPT父链绑定真实OPT成功命令、DCP生成/hash、原终态/受控停止、生成IP/约束身份；原project impl_1失败状态不改。

2026-10-15 OPT复位CDC诊断范围澄清：AT005新增CDC-11两条，原6条CDC-10中两条core ready的代表source变为calDone_gated；精确源/目标/rule的增量为4项。只允许当前已列明8条Critical在实际图命中时标为classified_reset_cdc_diagnostic_only：原4条CDC10不变、2条ready源变化、2条XDMA至DDR base CDC11，clock/source/dest任意新增或变化仍拒绝。门前核7条四FF链及相关AUX链的实际clock、ASYNC_REG、CE、级联、INIT与有效极性，显式primitive导出与图一致；两ready变化须落在原有calib/!ui_reset逻辑锥（允许已证实的极性折叠，不按LUT字面/原代表source判断等价）；XDMA源Q在同一UI中的多同步分支及消费者须精确归属base gate与HostSplit并保存完整相关fanout。

上述结构及既有黑盒/时钟/DRC等检查通过后可自动继续诊断place/route，最终reset/CDC safety仍OPEN；同域独立释放、事务中复位/重汇合仍需后续功能验证，不称安全豁免或修改时序例外。只有出现链断、错clock/极性、具体异步直达消费等反例才按实际缺陷先修。该界限服务用户已授权的首个可解释物理基线，不自动扩大为全局复位架构重设计或新增人工审批。A007阶段判据及A004实际源锥证据见E002/R005原审核。

BD41-1354四条别名critical已有生成配置解释，继续保留；实际SmartConnect事务可与物理诊断并行安排，未验证不作正式豁免。历史29条reset优先级warning需按实际综合网表/控制优先级分析，源未改不等于告警安全。逐文件add_files性能提示不作为功能阻塞。

## 所有权和资源

- 父/root：goal/mission/results、E002三摘要、任务/agent记录、资源协调和最终整合。
- A006 / 复用/root/m002_build_verify：唯一EDA执行者；唯一写入Vivado构建/约束/检查与测试；E002 R001–R004原始运行及工程报告；project/hardware/source/results.md的实际指标。不能与他人同时改冻结的构建输入。
- A007 / 新Astra xhigh reviewer：只读审查物理策略、综合结果、阶段验收；写E002/R005评判记录，可修订本合同物理判断段但先通知父；不执行EDA、不改脚本/RTL。
- A004 / 复用RTL工程：只读核查reset告警与现有RTL，写R005下独立warning说明；当前不改生产RTL。若需要修复，由父协调冻结边界后单一负责人落实。
- 总并发4含父，禁止子agent再分叉。工程模型沿用项目gpt-6.1-sol/xhigh；阶段设计/验收gpt-6-astra/xhigh。请求配置和实际核实分开记录；不绑定长期旧会话。
- 本任务重工具最多1条流程。总CPU占用限定8个logical CPU（进程树继承affinity）；HAP_JOBS及child synth并发合计控制在该上限。nice=5；整个受管进程树RSS上限192GiB，MemAvailable低于48GiB持续30秒或磁盘可用低于30GiB时停止本任务进程组并保存证据。只管理本任务进程，其他已有Vivado不触碰。
- 单次create上限30分钟、synth上限3小时、place/phys_opt上限2小时、route上限2小时。每阶段真实监测；异常/超时先定位，不原样无限扩时或循环换seed。本轮目标是首个真实物理基线及必要常规修复，不无界追求时序收敛。没有进展且无新可检验原因则停止该无效尝试，提交具体阻塞及替代证据。

AT008原截止2026-10-15 09:08:25 UTC保持，不热改冻结入口。若终止时确已取得新的完整关闭place/physopt DCP及对应命令native0事实，待原进程树结束并核无存活后，可按既有常规修复授权适配仅恢复缺失POST/physopt的入口；先核DCP完整性/hash、同工具/源/约束及原终态，明确新AT范围和成本依据，不重复已完成物理命令。命令成功、DCP完整、POST完成、route父链资格分别判断；不能以孤立DCP伪造原运行整体成功或直接绕过route检查。若无新有效恢复点或可检验原因，不原样重跑续额度。此条是原授权内的恢复实施边界，不新增用户审核停点，也不证明当前已取得上述产物。

AT008实际于09:08:31 UTC因原wall timeout结束，124/native−15、无survivors；没有完整place/physopt DCP。已测得debug后完整POST约33分钟、布局前总准备约44分钟，且实际布局已过全局阶段到细化Phase3.3，因此可检验的成本改进是从已完整关闭并通过pre_place的debug DCP恢复，继承同身份完整POST。按既有常规修复授权实施一次明确post-debug/pre-place恢复模式，通过受影响CPU正负例及真实组合身份核验后可自动启动，单次仍2小时/8CPU/单EDA及原内存磁盘保护。恢复仍须有限live sanity和原生DRC，区分继承与本轮新证据；不能把原部分布局进度当可恢复，不能预称净省33或44分钟或保证完成。若此一次布局尝试仍无新完整物理恢复点，不再重复place；若有新的完整place/physopt DCP，则仅按上段恢复实际缺失阶段。原AT008终态保留，原授权范围、接口、时钟和最终验收不变。

2026-10-15 终态执行：AT009于11:41:11.046467 UTC按原7200秒上限受控结束，managed124/native−15、stage_wall_timeout；7个已记录PID/start_ticks均退出，峰值树RSS32.28GiB。实际完成全局/细化布局及Phase4.1.1.2 BUFG Replication，终止时仍在Phase4.1.1.3 Post Placement Timing Optimization；无place/physopt成功命令回执或完整DCP。按上述一次恢复边界，本轮停止重复place；仅补缺失物理阶段的候选未测试、未安装、未执行，独立physopt和route未运行。原综合网表、OPT/debug/pre_place证据保留，完整物理基线未完成；中间WNS−1.884ns/TNS−1349.388ns不是完成布局或布线报告。本条记录实际结束，不新增用户暂停决定，也不授权扩大资源或下一次place实验。后续实验须基于本次耗时和真实瓶颈另界定范围。

## 证据、验收与报告

E002 R001=create/synth；R002=物理入口适配及CPU验证；R003=place/phys_opt；R004=route；R005=独立策略/告警/阶段审核。每次运行新AT，保存源码/约束/工具/IP/数据身份、命令、起止/退出码、受管PID/资源采样及完整日志/DCP；同一次尝试的终态不覆盖。已通过且依赖未变的E001回归复用并明确身份，不伪称本次重跑。

综合交付实际LUT/FF/DSP/BRAM/URAM、时钟/CDC/DRC、估计setup/hold及告警；布局/布线交付每阶段WNS/TNS/WHS/THS、违例端点、关键路径及逻辑/布线贡献、拥塞/资源、route完成率及DRC。未产出的字段标NOT_RUN/未得到。首次诊断不预设正slack结果。

发生综合完成、资源不可适配、基线改变、物理阶段终态或资源冲突即报告父主控，用户对话说明实质进展；本授权内按依赖连续推进，不增加用户审核停点。阶段Astra核查是工程内部整合，不伪写用户批准。最终报告区分执行、结论、适用范围和用户验收；不声称后台持续运行能力。
