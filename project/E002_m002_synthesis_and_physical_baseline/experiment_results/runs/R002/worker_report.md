# R002 · 物理入口适配与CPU检查

A006唯一写入EDA脚本/测试，父维护共享摘要。原综合create/build/run/emitter及339输入不变；新增独立M002 project implementation入口，不启用旧Pblock/SLR/DSP/1929检查。

- AT001：构建源/ROM staging CPU测试22项通过。
- AT002：受管进程隔离CPU测试4项通过。
- AT003：物理诊断40项加受管隔离4项，共44项；原始终态保留在attempts/AT003_physical_diagnostic_cpu。
- AT004：新增物理诊断测试43项加受管隔离4项，共47项通过；[status](attempts/AT004_physical_diagnostic_final_cpu/status.json)、[tests.log](attempts/AT004_physical_diagnostic_final_cpu/tests.log)、[脚本身份](attempts/AT004_physical_diagnostic_final_cpu/inputs.sha256)。
- AT004实际重新验证原339源、23个native run DCP及22个实际消费DCP，45路径完整集合/各hash一致；[lineage](attempts/AT004_physical_diagnostic_final_cpu/frozen_synthesis_verified.json)。

入口顺序为project INIT保存DCP/有界probe→OPT保存DCP并自动执行全设计准入→place/physopt→同run route。每点独立保存时钟、coverage、CDC、DRC、PW/bus-skew与XDC完整元数据/字节。只有实际唯一工具debug core/cell/port及完整MIG端点扇出可使INIT记为PENDING；OPT要求零黑盒和零内部时钟覆盖缺口，并核对已知6 reset CDC、3 reset IO的真实primitive/INIT/C/CLR/D/CE/AUX极性，未知对象停止在place前。

CPU负例覆盖缺失/重复/串项目/篡改输入及DCP、空/缺失/不可解析/未知debug端点、未知Critical CDC/IO、XDC字节/作用域/USED_IN变化、父launcher/supervisor失败或遗留、native checkpoint/归档篡改、own hook重试与foreign拒绝、负/rounded0/失败端点/NaN时序、真实路由计数。结构正例验证7 async reset链及4 AUX链，负例验证INIT/极性/断链/未知接收者拒绝。route-only helper修复可另存身份，旧parent code使用不可变归档核验。

执行完成与timing verdict分开；负slack只允许作为明确标记的诊断候选。bus-skew未完成解析审核时不能给全局timing PASS。所有physical_signoff=false；没有bitstream/板卡/GPU/PPL/ACC。

资源沿当前合同：8CPU affinity、nice5、单EDA lane、物理general.maxThreads8、RSS192GiB、MemAvailable48GiB/30s、disk30GiB、place/physopt与route各2小时。CPU测试不证明真实Vivado命令语义或目标网表可准入；下一阶段首次真实INIT/OPT用于有界取证及必要普通脚本修复。

AT003原44项记录完整保留。AT004补CDC所有summary类别与detail数量核对、summary内截断拒绝及route空本轮XDC reads继承正例/parent读证据篡改负例；47项通过，源码与测试已归档source_archive。

## AT005 · 真实project-init检查点恢复入口

53项CPU测试及真实恢复preflight通过（attempts/AT005_checkpoint_recovery_cpu）。新增failed POST原状态/归档/phase/DCP、162预link XDC及实际52次读取绑定；拒绝假success父身份、进入OPT后伪称init、原XDC/归档篡改、缺实际read；literal NAME/REF_PIN_NAME查询替代glob。原47项保留，源码/测试与派生recovery_parent完整归档。自管实际命令与receipt和candidate_project_settings分开；原impl_1 FAIL不改为成功。

AT006_recovery_identity_preflight_cpu：55项exit0，新增DCP package part/top/board/tool/XML identity、foreign package拒绝以及display NAME不冒充logical top/完整预检先于判门检查。真实339/45、162XDC与52read再核；源/测试归档完整保留。


## AT007 · 显式debug物化与OPT恢复入口草稿CPU

独立临时草稿完成76项CPU测试、exit0，17项源/测试原样归档于attempts/AT007_debug_materialization_draft_cpu/source_archive，尚未安装live，AT004运行源码不改。新增唯一known hub的OPT PENDING只进debug、实际implement_debug_core条件/receipt、独立debug_materialized/pre_place零BB/完整clock与限定CDC/IO/7+4结构、每后续物理阶段实际局部重验；physopt/route父链绑定真实物化与pre_place证据。后继可核验特定post_opt_pre_debug失败或已有guard请求的125停止父，不重写旧状态、不重跑已完成opt；缺失OPT POST将从同DCP重新采集。

恢复后actual temporary project显式恢复IP cache disable并与candidate XPR设置分记；两MIG PHY本次synth/no-cache-hit证据121文件与debug实际生成23文件分别核验。13份main生成XDC仅为已留字节的来源候选，原INIT52读序、PHY worker2读序和debug worker5读序分开；后者原路径已工具清理，缺原始hash如实保留，不将生成输出自动声称全部main effective。实际source/metadata/bytes继承及debug真实owner限定不放宽未知来源。

极性空cell属性不按0猜测：限定11小block由真实write_verilog -write_all_overrides显式导出并与actual cell/pin properties核对C/D/CLR(R)；未知/冲突阻断。两XPM合法FDRE用同类cell对象取得effective/ignored/scope_override/valid例外与D端timing，不以聚合count推论覆盖。debug probe补hub输入、两output和全部实际fanout C的clock PERIOD/MASTER_CLOCK/SOURCE_PINS，并保留声明300MHz与实际输入50MHz的事实差异；零no_clock不是时钟合同签核。

本AT仅CPU/身份：真实339源/45综合DCP再次核验，PHY/debug新来源身份也核验；实际OPT父终态、工具属性与显式物化/placement/route尚未取得，不提前填写PASS。


## AT008 · 已安装最终OPT续跑入口

84项CPU测试通过（78物理准入/身份、6受管隔离），脚本/测试原样归档在attempts/AT008_opt_recovery_debug_final_cpu/source_archive。安装前逐字节核对live脚本等于AT004运行归档、测试等于AT006归档；安装前取得唯一EDA锁。真实339源/45 DCP再次一致，真实AT004 OPT父preflight通过。

受控125父链限于指定guard原因/五项OPT proof/实际成功opt命令/零BB；原status native−15、125和owned_survivors=[3161784]原样保留。独立post_termination核验原status hash、终态时间、31个原PID/start_ticks及当前均不在、leader唯一旧survivor和冻结子日志；这些receipt/resources/log身份进入新AT输入。缺receipt、status被改、PID范围不全、冻结log被改或实际PID仍存在均拒绝。未来supervisor终态在wait/reap后重查实际survivors，回收前值另记owned_before_reap；真实detached survivor不会被吞掉。

严格clock gate保留实际hub输入/输出/扇出C的周期、master、source、generated/waveform、driver/startpoint及限定有效XDC导出；非空clock不等于真实关系通过，独立错误3.333ns输出拒绝。300MHz参数与50MHz输入差异仍如实保留。AT004缺失OPT POST明确不继承完成，本轮从同OPT DCP补全。


## AT009 · 同OPT报告复用和精确reset CDC诊断入口

93项CPU（87物理+6受管隔离）exit0，已安装/归档source_archive，安装前核live等于AT005/AT008冻结源。真实339源/45 DCP与AT005递归OPT父链PASS：AT005 DCP397273730 bytes/SHA256 b209decf321e4a756f3ded455e0ce162b3404467ec235b5312469f9a89171021，绑定AT004实际opt成功、受控125/reap/archive/工具与约束，以及AT005当前failed POST终态、14完成报告/integrity。恢复相同字节DCP、复用同DCP完整报告，重取缺失/受影响有界探针，不重跑OPT；缺报告/祖先或receipt篡改/伪称重跑均拒绝。

主控已接受限定classified_reset_cdc_diagnostic_only：精确AT005 8条rule/source-clock/dest-clock/source-pin/dest-pin，reference CDC hash7451c566ed781bcc67e2bbc5484378980045df170acb9b2ad884a7d20b94ff67；相对综合4个身份变化逐条保留，未知新项拒绝。当前14块实际override/graph（7 async+4 AUX+3 HostSplit）先于未知CDC判门；FDCE有效CLR极性按实际pin/net alias与truth function算，允许合法反相折叠，不比较LUT字面或强求CLR_INV0。HostSplit3链effective INIT0、4级、CE/R、同UI和stage0与user_reset/Q同相、末Q唯一精确同clock LPF FDRE/D逐项核。

完整sourceQ fanout/UI归属核XDMA→每UI base链4CLR及对应HostSplit首D（UI0一支、UI1两支）；HostSplit末Q只到本psr/U0/EXT_LPF/lpf_asr_reg/D，base末Q跨域只可已证明的本d_smc两AUX首D，其它/无clock阻断。自身域消费者如实全记录。14 primitive字节、raw fanout与本阶段CDC/完整祖先身份均绑定；后续每physical点重取实际reset/fanout，不盲继承pre_place。正式reset/release/事务安全OPEN，不能称豁免或全局签核。

新增CPU覆盖报告复用/祖先错误、合法CLR inversion折叠与真值错误、HostSplit初值/源极性/consumer clock、额外/未知异步consumer、fanout计数缺口及精确8条组合证明缺失与未知source拒绝。CPU不证明实际工具命令或图能通过。

AT009独立审核补充：原4 AUX链16个FDRE未显式assert INIT0（已核REF/ASYNC/级联/CE/R/实际极性且export与cell INIT一致）；AT005同DCP原探针16个INIT0，无实际设计异常。AT006运行源码冻结，不热改/为此重跑；本次由A007核fresh graph/exports补齐16个INIT0证据，下一次合法入口修改补显式INIT0断言。正式安全仍OPEN。


## AT010 · 真实图离线收敛与精确BRAM写口时钟

99项CPU通过（93物理+6隔离，含AT006119909158-byte实际图回归）、真实339/45和AT006同OPT/完整祖先/14报告/图14exports/fanout父链PASS。源/测试已安装、source_archive冻结4份同Vivado原语模型与write_verilog手册；原AT006失败1和原始图不改。7async的INIT1原检查本来正确；新增4AUX显式INIT0。模型参数缺省只从已锚定FDCE/FDRE明文解析，注明model_default/explicit_override并和任何非空逻辑/引脚字段对照，未知表达式、defparam、重复/未知override拒绝。

真实图确认Vivado all_fanin startpoints返回FF launch C，通过同actual FF Q/clock/identity归一化；XDMA rawuserQ高断言加base CLR_INV0与原双反相等价，不以OPT后base_aresetn标签当逻辑真值。14链有效极性、INIT及alias、4级/CE、HostSplit精确LPF consumer离线资格PASS，见actual_reset_structure_requalified.json；正式安全OPEN。

BASE尾Q all_fanout的6362/5282中，原混合clock残余688项全WEBWE（88 RAMB cells），整cell clock并集为core+UI，不能称端口实测。新AT只补实际endpoint→unique actual cell→该cell CLKBWRCLK且IS_CLOCK→get_clocks，保留原混合值；缺失/foreign/多clock/错误UI/A=UI但B=core/未知REF或WEA/越界/重复冲突均拒绝。模型RAMB18/36功能写引擎来源hash固定，非specify多clock条目推论。完整CDC门依然PENDING688实际端口证据，未在CPU状态里伪填通过。

同b209...OPT DCP只copy继承，不伪造新checkpoint生成日志；闭合119MB图、14导出和fanout复用身份与适用阶段明确。debug/physical变换后仍取各阶段自己的实际图和端口时钟，不将OPT静态证据冒作变换后实测。


## AT011 · 辅助CDC精确限制与完整实际OPT入口复核

102项CPU（96物理+6隔离）exit0；新增四精确辅助cap正例、name/clock/count/limit变化和额外UNKNOWN负例、缺失/篡改小报告及full tuple变化拒绝。安装前在唯一EDA锁下核live等于AT007冻结脚本/AT010测试，source_archive与installation.json冻结。早先AT010“仅688待补”的文字遗漏四个辅助对象枚举上限；真实残余1381项为688缺mapping+688旧clock并集拒绝+1缺端口集合+4辅助cap，现按实际证据纠正。

AT007完成688条WEBWE→实际同cell CLKBWRCLK→唯一UI时钟（d0 456、d1 232；88cell），263752B/SHA256 1a4704be88423f55a1825911fce1c57ce24cce83624d78244aeeea386593b69c。其原fanout仅4个TARGETED_CDC_VIOLATIONS_UNKNOWN/m002_changed_reset_opt_0..3；实际get_cdc_violations数668/668/768/769超过64，不能混同report_cdc Critical行数3/3/1/1。

新规则仅匹配四原sentinel及紧邻实际command、clock pair、name、count和LIMIT=64；锚定四小报告原hash，完整解析3/3/1/1、并集exact8与full CDC和注册tuple一致。原UNKNOWN仍保留为auxiliary coverage_limited，仅对象属性枚举覆盖有限；所有其他UNKNOWN、缺失/新增路径、未知consumer继续拒绝。四报告进入输入和proof identities；非OPT阶段不执行该辅助枚举，不扩大规则。

actual_complete_opt_gate在独立目录调用完整hook_batch：原339/45、完整约束链/phase clock/IO、14链结构及exports、完整fanout、688实际port、全量CDC与资源全部检查，gate_issues=[]，classified_reset_cdc_diagnostic_only/new_critical0，formal safety OPEN。不是只运行reset_structure；真实完整gate和actual_parent_preflight均PASS，见actual_combined_status.json。原AT007失败status/log/integrity全部保留。新父链只在OPT字节/工具/约束不变且当前integrity与上游绑定图/exports/fanout吻合时继承，再绑定实际BRAM与四报告，下一AT不重复119MB图或端口取证。

正式debug/pre_place/place/route未由本CPU/离线结果证明，physical_signoff=false。

附加归档复算：replayed_complete_opt_gate_v3以source_archive checker执行全hook，旧stage manifest中的代码定位到AT007原stage_sources，原manifest不改；派生manifest另绑定全部实际输入、当前checker和replay driver。结果仍gate_issues=[]/688实测/完整诊断PASS，见replay_status_v3.log。两次仅复算脚手架路径/目录过滤失败日志原样保留，不涉及EDA或准入规则修改；不改本AT原终态。


## AT012 · 完成pre_place恢复入口

新增13恢复/CLI/终态/新旧命令receipt/route-parent测试和managed隔离6项PASS；96项既有诊断测试身份未变，复用AT011，不声称115项全部重跑。真实AT008完整debug POST在最终checker组合hook gate[]，7+4+3链/14exports/688ports/精确8CDC，恢复父链绑定原timeout/无survivors、e58...DCP/68文件closure；最终19新执行与实际重放/安装来源见AT012 status/actual_replay_status/installation/archived_sources。原AT008及重放v1路径保护失败均保留。无新EDA签核结果，AT009另行真实live restore guard。
