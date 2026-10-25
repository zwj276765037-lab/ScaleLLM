# E013：实验结果摘要

<!-- A022_CURRENT_G5_BEGIN -->
当前G5（2026-10-25T02:01:28.191844+00:00）：G4R LIMITED_PASS、GU-only constructor/综合与AT011同DCP结构资格已完成。真实96lane×148 guard FDRE（37bit×2channel×2entry）、Down0、MLP3072DSP、GUmeta448URAM，Attention/共享核与10/5/5ns时钟身份通过；此范围不等于完整板级签核。

R008/AT001_impl已自然NATIVE_STAGE_COMPLETED：native0/nullstop/102输入无漂移/0survivor，peak27.379GiB。真实routed DCP665825940B，SHA `cc34f49bef612472367f7d273596d09dede15128d3b72a2708507e4c6d6c7cc4`；正式1687352/1687352全布通、routing errors0。正式STA WNS+.002/TNS0/setup0、WHS+.010/THS0/hold0、WPWS0/pulse0；最差GU控制计数→CSR读数据9.446ns、其中route7.440ns，时序裕量很小。最终no_clock/internal unconstrained0；PERST及双DDRreset缺1input/2output delay。DRC0Error/Critical、15762Warning；CDC6×10+2×11 Critical及5688Warning保留限定结构解释。原`stage_quality` overall FAIL保持，不能用native0冒充全签核。详情见`runs/R008/attempts/AT001_impl/{result,formal_timing_observation,engineering_terminal_summary}.json`及历史时间线。

已确认用户三域clock_groups覆盖4个command handshake的10ns Max-DPO：原10个合并count位路径Slack inf/Asynchronous Clock Groups，coverage不代表active bound；四独立bus-skew均MET，不能替代绝对延迟。AT002补取四scope/十D、两reset8级、两DSP代表及d0SMC后，按用户先取bit优先级于UTC00:30:51受控SIGTERM/-15收束，原因USER_PRIORITIZED_PRELIMINARY_BITSTREAM；30工件及partial/NOT_COLLECTED保全、0survivor/锁释放，原FAIL不改。d1SMC未完成，d0同域+4.076ns不证明异域Max-DPO。

**工程验证版bitstream已交付**：`hardware/vivado/reports/m006_gu_AT003_preliminary_bitstream/native_output/ScaleLLM_MLP_GU_only_ENGINEERING_VALIDATION.bit`，80159259B，SHA `66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47`。AT003结束UTC00:45:47，native0/nullstop/无漂移/0survivor/锁释放，peak23.564GiB；write_bitstream原生4m00、0Critical/0Error。`AT003_preliminary_bitstream/bitstream_manifest.json`绑定原DCP/102输入/工具/脚本/native结果，`delivery_receipt.json` SHA `b5e4c427d278214d773aed8dcb854ac3b70d4f3be432043c19cbca85899b9443`。Max-DPO/外部reset签核开放；AT003生成交付阶段未访问板卡/GPU。后续Dell板测由Root另授权及专属owner独立登记，A022本轮仍只负责EDA/约束资格。

AT004已于UTC01:18:30.927485自然FAIL：native1/nullstop/changed[]/0survivor/锁释放，peak23432990720B；取消前身份检查发现它已退出，未发送任何信号。真实首次拒绝是ddr0 data集合148074中148042落入原谓词、32未覆盖；名字在旧探针中未导出，不能猜类别，也尚未reset/read任何时序。原生已确认4scope34/34/35/35直连及原50clock/100同域极值；14,386,032基础through集合差68。导出XDC页眉含输出文件名是另一个已识别的比较器问题，尚未执行到该比较，不能把它写为AT004原生失败原因。

AT005已自然FAIL（native1/nullstop/无漂移/0survivor，peak20317671424B）：fresh50clock及原STA100行复用身份通过，随后Vivado filter拒绝复合一元!，raw role文件仍空，任何时序未改；不作为32角色证据。

AT006已于UTC01:57:50.403258自然FAIL：native1/nullstop/changed[]/0survivor，peak20200513536B。原生已关闭全部64角色工件：ddr0/1各16个BITSLICE_CONTROL/PLL_CLK及16个RIU_CLK，IN/IS_CLOCK1，library input/clock1/data0，具有实际clock；系统Python继承Vivado PYTHONHOME/PYTHONPATH后stdlib版本不符，helper在角色决策前失败，任何时序未改。不是UNKNOWN真实角色被猜测排除，原FAIL保留。

**当前运行**：R008/AT007_routed_constraint_qualification已UTC02:00:57.300347启动（PID/SID2700936），唯一EDA，32CPU/192GiB/8线程。新v2入口38项CPU检查原生0（含实际64角色分类、绑定BITSLICE_CONTROL厂商时钟模型、矛盾角色UNKNOWN及污染Python环境下-I隔离），仅CPU/语法。系统Python调用统一-I，库方向input/output显式规范化；每次新原生流程仍先双域≤512完整取证，工件关闭后按预冻三分支处理，不动态source。严格绑定同原cc34 DCP及AT004已关闭原STA100行，fresh50clock须一致；零差异重放核有效scope/有序可执行约束、clock/12指标/同域极值，再执行精确138直连补集。zero replay保存独立DCP及六成员原始SHA；全同是充分证据，不同不盲认物理改变或放宽。首轮SMC保持原cut；不改原DCP/102源/已交bit，不重综合或物理。未取得终态前不称修正通过。

完整物理签核尚未闭合。旧AT007/009查询FAIL、AT025测试guard配置FAIL、旧v6布线FAIL与所有原始quality均保留；不以新阶段覆盖历史。
<!-- A022_CURRENT_G5_END -->

以下保留此前阶段过程记录，当前状态以上述受限结论及各attempt原始终态为准。

G4R已于2026-10-24T16:23:11.000913+00:00获得A021独立LIMITED_PASS，按授权连续G5；不等待Host32层/吞吐。R006 AT024真实production metadata padding专项PASS：N32/fullK128，idle无虚假DONE、heldDONE快照不改、active GU真实owner2120、active bank0/7/511代表字节及generation保持/epoch撤销、ACK拒绝、三次实际安全维护及GU62逐byte gold重试；xelab101.871s/xsim137.703s。代表点不外推全bank逐字节。AT025因TB保留enforce0却断言1而FAIL，生产RTL/断言未改；改测试配置1后AT026完整N14336/K128生产elaboration实际PASS，cache16x128x280、GU metadata AB229376x224、guard37、1792输出派生及guard1均实测。

R007 AT006_constructor已UTC16:21:53.818803实际启动，PID/SID2283139/affinity0..31/192GiB；新工程hardware/vivado/project/m006_gu_AT006_constructor，报告reports/m006_gu_AT006_constructor；102输入freeze SHA87a98e40d56c3a767085d2865c52f582ea681e754092fc80967265732b008ae4。AT006已自然NATIVE_STAGE_COMPLETED（native0/nullstop/changed[]/0survivor，peak3124072448B=2.910GiB），1323生成文件/10native工件及receipt SHA5181319015f3c28662bf843c21f7b9be0c40bf87d608cd9caf84de707eeee52c绑定成功。AT007_synth已UTC16:29:36.403855实际启动（PID/SID2294216、32CPU/192GiB/8线程/4jobs），消费该新工程和同102输入身份；23项native综合均完成，主会话正在合并完整网表并做后报告。正式core OOC资源为CLB LUT593717/FF756043/BRAM542tile（535RAMB36+14RAMB18）/URAM528/DSP5368，原文及SHA已保存到AT007_synth/core_utilization_synth.rpt与core_utilization_observation.json；这不是整板/SLR/终态结论。物理尚未开始，新native96lane/Down缺席/DSP3072/GU meta448URAM仍须完整新DCP取证。

以下为此前阶段过程记录；当前状态以上文及具体attempt终态为准。

当前GU-only执行状态（2026-10-24T16:12:54.069429+00:00）：已授权G0–G5，A022唯一RTL/EDA owner；v7完整schema SHA318cf64064354aed52943fd21909aa8b67f11ca8fb565a37c65441d522d4938a，旧v6图/ABI/证据保留。新GU compute/resource/production/board已真实接通，G4R尚待metadata-owner专项与完整生产尺寸elaboration；新综合/物理未启动。

R006 AT019新真实production整合PASS：N128/fullK128、222035checks/112509cycles/262144metadataB、四同epoch两cohortGU、完整独立Python整数gold、旧Down/32bit0x101无AXI/owner拒绝、REC7前缀排空/重试、真实ABORT完整排空、BRESP安全维护保DONE/首诊断、物理DDR1早RLAST globalfreeze拒软清/core-reset/末GU数值重试；2次真实维护/23jobclear。xsim1413.486s、xelab106.091s，峰值1533251584B/1.428GiB，native0/nullstop/0survivor。AT023 v7 CSR实际PASS：4155checks/594writes/5submit/3epoch/2ACK/2abort，134/138/170全部16WSTRB against-zero矩阵、Down RO恒0、AW/W/B/R背压与诊断/快照；job结果mock不替代整合。

先前实际模块PASS：AT004两列37bit对旧GU512向量/在途clear/1638cycle；AT006 cache128及非法128/256无alias；AT007 parser坏组17前缀/末commit背压；AT012真实双8×12 GU N128/K128、4096 S24、2048meta/2816事务；AT013 full32bit准入/首错/ABORT/timeout/late-fatal/ACK/owner；AT016 GU生产1792记录tensor与R/B故障；AT018真metadata loader/resident/scheduler（32物理32B/有效28B、padding7全drain/7前缀、active字节代数保持/禁commit/64读）。AT012 scale/shift在row/col变化，activation/W4在group/k变化；lane极值由AT004覆盖。

当前串行AT024 metadata fault运行中：N32/fullK128、4输出/3072B、512meta/16384B、768事务，真production idle/heldDONE/active-owner、epoch/字节/代数/ACK/维护/重试。随后AT025完整生产N14336/K128，实际cache$size128/metadata229376/guard$bits37/派生1792等elaboration。串行队列遇失败即停，不并发第二重EDA。

R007新入口已准备：m006_gu_entry/create/build/run及新board/production清单，102闭合输入/80HDL/95模块无重名/44Attention字节匹配；AT002隔离schema重生成CSR+Host ABI逐byte相同，AT004_all_lane_probe_cpu为14项源码负例/Python/系统Tcl完整性PASS（含完整快照），原生Vivadoquery尚NOT_RUN。计划新综合网表原生逐96lane查37bit、DSP3072/GU meta448URAM与Down对象缺席；cache128由源码绑定+完整elab+actualcache实例互证，不预承诺BRAM下降。G5同会话place/physopt后采轻量SLR/congestion，无旧慢窗/路径扫描；完整CDC独立保留，不以六链探针覆盖其余critical。

失败历史保留：R006 AT002/011编译普通修复；AT009/015准备转换失败无EDA；AT017 TB commit等待错过真实握手导致watchdog，修TB后018PASS。旧R005按Root新版阶段裁量取消可选诊断（SCOPE_SUPERSEDED_BY_AUTHORIZED_GU_ONLY_IMPLEMENTATION），116输入无漂移/30工件SHA/0survivor/锁释放；R004自然routeFAIL545088overlap不变。小仿真8CPU/96GiB；board32CPU/192GiB、native8线程/OOC4jobs，无正常墙钟/静默停止。G5不等待Host32层/吞吐。

下方保留旧v6/阶段历史，当前状态以上述段落及具体attempt原始终态为准。

最新执行状态（2026-10-24 UTC15:22）：用户已批准GU-only实施，A021完整abi_gu_only.json（318cf640...4938a）为有效v7合同；UTC15:11:32已开始新文件G0/G2/G3，旧v6源保持。R006/AT001首5新RTL/7模块语法PASS，AT002 compute声明顺序FAIL已修，AT003新GU compute/CSR语法PASS；目前仅语法，不是数值/elaboration。新Host ABI已生成并交A023。

R005已按Root新版阶段裁量受控取消可选新窗口/显式路径采样，原因SCOPE_SUPERSEDED_BY_AUTHORIZED_GU_ONLY_IMPLEMENTATION；不是用户直接kill、超时、静默或资源失败。native SIGTERM -15、原runner FAIL未改；116输入无漂移、0survivor、共享EDA锁已释放。已COLLECTED核心/8scope/SLICE/congestion/7旧窗报告及partial文件保留并逐件SHA；未完成字段NOT_COLLECTED。详情R005/AT001_physopt_slr/scope_cancellation_receipt.json。R004原自然route FAIL不变。现在继续GU-only实现和受影响单重仿真/新综合物理，不等Host32层。

当前实态（2026-10-24，R005诊断仍运行）：R004/AT001_impl已自然FAIL（native1/stopnull/changed[]/0survivor，545088重叠节点），不重复旧implementation。唯一R005/AT001_physopt_slr已完成open_checkpoint、全局/8scope资源与跨界、真实SLICE、congestion及7旧窗；4新窗与显式路径采样尚待完成，未签诊断终态。保存Physopt布局原生SLR1占49193/49260 SLICE（99.86%，余67），Down repack/input_fire跨SLR fanout6185，GU repack4650/GU tags6149仍在；详见experiment_source/gu_only/native_pressure_support.json，不能外推失败route网表或删后改善比例。

下一版方向为GU-only，Down完整移Host且保持原format05整数数值与原权重。A021 design §10和abi_gu_only_draft.json仅planned；A022 engineering_scope.md/ddr_binding.json列可执行裁剪/测试依赖及实际DDR0 Attention、DDR1 MLP接线证明。当前生产源、v6 ABI和R005冻结输入均未变，尚无GU-only RTL/新综合/物理结果；等待Root集中确认下一版实施范围，不增加逐项审批。

| 尝试 | 实际结果与边界 |
|---|---|
| AT001/AT003 | 首版cache/parser PASS，后续受影响回归为AT011/012 |
| AT002/AT014 | DUT断言及PASS marker完成，但正常统计字符串触发runner关键字FAIL；原失败保留，未改gold/断言 |
| AT004 | GU scheduler N128/K128：2048源、2816内部、16输出，6412周期；投影BFM不证明MAC |
| AT005 | GU scheduler完整N14336/K128：229376源、305920内部、1792输出，612620周期；XSim842.32s。仅调度/重排/背压 |
| AT006–008/AT009 | 联编普通语法修复；AT009 xvlog原生0；不等于层次elaboration |
| AT010 | job控制PASS：同epoch4job、descriptor原子快照、ACK/延迟完成/abort/hardclear保留DONE；路径状态为mock |
| AT011 | 当前cache PASS，576组/全部row/lane及错误生命周期 |
| AT012 | 当前REC576 parser PASS：704合法、640坏记录，坏组17保留17×576已提交前缀并排空；末合法record被阻塞23周期不提前计数/done |
| AT013/AT015 | AT013 TB保留标识符编译FAIL；修复后AT015 tensor DMA PASS：input73728/258048B、GU1376256/Down262144B，4KiB/16beat、背压/末B延迟/response fault；此后transport安全出口新增待整合 |
| AT016/017/019 | 真实kernel用例失败保留。根因均在TB物理输入：metadata错误按14bit交错（实际低128code+高96shift）；随后always@*未在time0初始化首组metadata，独立去g0贡献精确解释DUT -144 |
| AT018 | CSR PASS：1860check/332write、17descriptor RW、64RO保护、49telemetry、AW/W/B/R背压、START/mock结果延迟及DONE别名错误分类；不替代job/DMA |
| AT020 | 首组metadata修正后DUT -125与独立Python一致，但SV gold函数返回3导致FAIL；冻结源码快照和逐group参考保留。公式/舍入不变，替换为独立Python全量gold |
| AT021 | 真实double8x12共享kernel、GU S44与Down S54 PASS：N128/64、K128/448，4096GU S24+1024Down S32逐值匹配独立Python整数。group/k相关activation/W4、行列不同codes/shifts、尾12/4、异步DDR、出口背压。xsim143.415s/5504事务，peak0.89GiB；xelab67.857s/peak1.44GiB |
| AT022 | 当前生产源图xvlog语法分析原生0；没有层次elaboration结论 |
| AT023 | 未带生产Attention选择宏，xelab缺模块FAIL；未DUT功能 |
| AT024 | 完整真实生产层次xelab原生0/92.67s，time0原SV gold selfcheck失败；未DUT命令 |
| AT025 | 当前DMA transport回归PASS：两opcode完整生产字节数、R/B响应错误在完整burst后安全停留且禁止新请求 |
| AT026 | Python10240值gold六literal自检通过，首GU输出W逐byte通过；末B屏障因TB admission job_clear基线少算一次FAIL，修补保留全部屏障 |
| AT027 | job公共fire/done独立边沿计数PASS，compute/store首fire inclusive、stall按周期并集；同时保留4job/ACK/abort既有控制回归 |
| AT028 | 完整真实生产层次PASS：235509 checks/139012 cycles/491520 metadataB、2次真实维护、9完整compute；四个同epoch两cohort、REC7失败ACK重试、真实ABORT drain/维护、BRESP安全维护保DONE/首诊断+重试、早RLAST global_freeze拒软清/core reset新session重试。xsim14m51 |
| AT029 | 后续控制边界候选RTL+短timeout TB xvlog语法原生0，不是行为 |
| AT030 | 最新job控制单位PASS：80cycle watchdog、同拍ABORT/path/DRAIN与late fatal/ACK、先错保持、idle/active owner clear、fatal+START响应、原4job及inclusive counters |
| AT031 | 最新global fault wiring真实focused PASS：30529 checks/23820cycles/245760 metadataB，global_freeze拒软清/core reset/完整GU gold重试，soft_clear0；xsim2m11 |

Host独立32项CPU测试PASS见host_reference/AT_20261024T030431628513Z，冻结SiLU8193词逐项相同，H32/A8/SwiGLU与REC576 codec；仅Host支持证据。每AT输入SHA/命令/原生退出码/日志保留，当前源相对旧PASS变化见状态摘要。新工程constructor及原生综合命令/完整DCP已完成；AT004身份probe FAIL保留，AT007/008查询入口FAIL已修，AT009 DCP资格原生完成，R004/AT001实现已自然FAIL，R005只读诊断运行中。合法route、最终时序/DRC/CDC资格、板级均未通过。

入口CPU证据：R003/AT001_entry_helpers 18项shape负例/XPR配置绑定/快速父退出后的SID子进程发现PASS（仅辅助函数）；R003/AT002_csr_repro隔离目录重生成CSR与当前RTL逐byte一致PASS。旧CSR头部作为generator依赖纳入M006输入，未选入生产RTL源图。R003/AT006_qualification_helpers通过真实AT004来源和4个精确diff/hash负例；不是EDA资格。旧AT005诊断继承13case针对未应用候选，未扩成接受FAIL父。

R003/AT003_constructor真实原生0/NATIVE_STAGE_COMPLETED：peak RSS3139215360B、无stop/无输入变化、owned8 PID最终0残留；1323生成文件与规范化XPR/10native工件绑定成功receipt。实际BD core100MHz/双DDR UI200MHz，完整wrapper/IP生成。

R003/AT004_synth终态FAIL：22 OOC及top全部synth_design原生成功，完整DCP 211877273B/SHA cf11b600c30b4cf0756693e3e4c76dd8b04ac09e79eaf644a05ba9d988bc5a4b已写出。末尾身份probe未匹配Vivado OOC模块REF_NAME前缀，真实Attention/shared kernel/wrapper在正式hier报告中明确存在；唯一黑盒为pre-opt dbg_hub_CV。native1、stopnull、changed[]、survivors[]、peak53746458624B（50.06GiB）；不签成功回执，不称零critical。原native日志的20-1307诊断puts警告保留。

AT004正式整板资源：LUT766078、FF954137、RAMB36=827/RAMB18=16（835tile）、URAM752、DSP5375；core正式LUT679798，不与primitive总数混用。4个内嵌XDC确认board pin/主钟/三域异步组有效，遗漏假设排除。未布局WNS+.904/TNS0、WHS-.814/THS-46941.938/936065 hold端点、WPWS-.012/5端点；no_clock530、unconstrained554均DDR校准debug，另PERST输入/双DDR reset输出缺delay。DRC0error/critical、15769warnings；CDC3 info434、CDC9 info19、CDC10 critical6、CDC15 warning6198。没有物理时序/CDC通过结论。

AT007资格入口native1/stopnull/changed[]/0survivor FAIL：fresh open_project尚无design时close_design报Common17-53，未进入DCP检查，peak1293619200B。删除qualify/impl两处该调用后，AT008已实际确认Attention1/kernel1/禁止非线性0/用户黑盒0/24同步级，后clock对象集合类型错误FAIL（peak21510115328B）并已修；后续AT009已原生0完成。严格绑定AT004原FAIL/23成功synth日志/1433 post-generated文件/同SHA DCP，仍仅4文件准确patch，104依赖/83HDL及RTL/IP/ROM/有效约束/shape保持；freeze3b46f8bcd155d6de51bdae45956212625b4c1759ee56acf07d581aafd33479d5。复用旧timing/CDC/DRC，只原生重查身份/clock/约束/6复位结构，AT009成功回执见下。6条reset经A021限定结构接受，原CDC critical保留，post-opt必须0黑盒且530/554端点clock/6同步链实查后才place。

AT009资格实际原生0/stopnull/changed[]/0survivor、peak21519392768B（20.0415GiB），精确模块1/1/禁止非线性0/用户黑盒0、实际10/5/5ns clocks、6×4级结构全部PASS。新成功receipt SHA f0fee79c00fa8247e208df86e8edb8556b7a3a227eca9c4015ce82fde8716ee5，26工件SHA及1433生成文件被绑定，A021已独立核验；overall原质量FAIL及历史FAIL保持。R004/AT001_impl已UTC06:19:43实际启动，PID/SID1810584/affinity0..31/RSS192GiB，消费该成功回执及同DCP；opt后原生debug/clock/24级门通过才place/route，当前物理未通过。

R004/AT001_impl已原生完成opt_design（34m30，0 Critical/0 Error）和post-opt/pre-place门：全部黑盒0，原530/554对象全部存续且全部查到时钟（removed0/missing0）；6条reset链24级寄存器的ASYNC_REG/100MHz/相邻D连接全部PASS。两native报告及SHA见attempt内post_opt_observation.json（当前tree RSS28.3648GiB，最终runner峰值待终态）。门仅证明原精确对象clock非空及六条限定reset结构，不能替代最终完整unconstrained/setup/hold/DRC/CDC资格。optimized.dcp已完整保存（376424082B，SHA9939ad8c...），place_design已实际启动，precondition DRC0错误，继续physopt/route，物理仍未合格。

实现过程记录：AT001_impl经place Phase2.5 Global Place Phase1；此前Place30-1229在d0_mig_slice发出USER_SLL_REG建议未满足警告，原生日志显示100条后抑制，100不是总数。当前不改约束或waive，最终依据route/时序及跨SLR路径评估；不是当前原生ERROR，也不据此提前判物理合格。

用户当前核心验收是删减FPGA MLP操作是否缓解既有SLR问题。全局资源下降不替代per-SLR packing/拥塞/实际跨界/SLL/关键网延迟和合法route证据；自然终态后按experiment_source/slr_evidence_plan.md做一次有界只读现存DCP取证，不为补报告重复implementation，准确保留失败route前最后DCP的阶段范围。

R004/AT001_impl最新：place_design已原生成功（1h48m53，404info/240warning/0critical/0error），placed.dcp已完整保存并在place_completion_observation.json记录SHA与资源；外部phys_opt_design已同进程实际启动，route尚未开始。Place46-14高度拥塞、Place30-1229 USER_SLL_REG提示及4条MIG Place30-1995保留；post-placement估计WNS=-.645ns，尚非最终时序/SLR通过。自然终态后按SLR取证计划对实际保存阶段只读定位。

AT001_impl最新阶段：外部phys_opt_design原生成功11m17，完成行0critical/0error；pre-route估计WNS=-.219ns/TNS=-11.018ns，仍未闭合。physopt.dcp已完整保存（SHA与route实际启动见physopt_completion_route_launch.json），route_design已在同一冻结进程实际启动/maxThreads8。高度拥塞警告保留；route/最终时序/SLR改善未判定，未新增并发EDA。

route实测风险：AT001_impl首轮数据布线后的Route35-447指出拥塞正阻碍所有网络完成路由，工具转为优先完成路由而非时序优化；当前进入第二轮Initial Net Routing Pass，尚未终态，不能宣称SLR改善或合法route。该实际警告与Place46-14均保留，终态后按SLR计划定位。

截至2026-10-24 10:04 UTC，R004/AT001_impl进入route Phase5 Rip-up And Reroute。原生Route35-448/581估计Global/Short与Timing拥塞level7（128x128）；方向窗口原字节和native log-prefix SHA见attempt/route_initial_congestion.txt及observation.json。尚无route终态，局部SLR压力变化与能否布通分别待证。新只读SLR入口CPU准备AT004_cpu为24tests/Python编译/系统Tcl完整性PASS（六源snapshot），不是Vivado查询证明；只允许自然终态/无漂移/0survivor后执行。保留父FAIL/实际阶段，routed必须历史SHA锚，重点保留metadata/shared核、7旧窗+最多4个最后原生代表新窗（native tile→SLR、资源范围明确包围clock regions）、最多400跨界路径样本非全量。

UTC11:31左右route GlobalIteration1原生结束，累计elapsed2h19m15/CPU9h09m33，进入Phase5.3 GlobalIteration2。该迭代中overlap节点1729692→921600，Route35-416中间WNS=-12.148ns/TNS=-1074756.284ns、hold N/A；详见route_iteration1_completion_observation.json。当前有消除冲突进展，但绕线时序代价明显，尚非最终route/时序结果，不与旧最终计数直接相减。实现候选归因见experiment_source/congestion_implementation_evidence.md（11条当轮高扇出原文、宽FIFO/共享主体/metadata672URAM及DDR跨区约束），没有据此热改或新启动EDA。

UTC13:02实态：route Phase9原生验证失败，ERROR Route35-2明确545088 node overlaps、Route35-17确认router errors，route实际13733.3s；当前失败后自动DRC尚在运行，未提前签整attempt终态。失败见证前10节点已直接涉及shared branch0 shift/recover、metadata down_bank1 wr_data_local及d0_mig_slice triple_slr，采样不代表完整排名。原始段及SHA见AT001_impl/route_failure_native_excerpt.txt与route_failure_observation.json。尚无routed.dcp，最后保存阶段physopt；终态/无漂移/0survivor后按既定只读入口采该早期布局的逐SLR资源及旧新空间窗，失败route日志与physopt网表分开，不重复route补报告。物理FAIL不改成功功能证据，也不预判各局部指标完全无改善。

UTC13:23:36 R004/AT001_impl真实自然终态FAIL：native1、stopnull、changed[]、28历史owned PID最终0survivor，peak tree RSS31718821888B/29.54045GiB。终态20native工件SHA见terminal_artifact_hashes.json；失败route实际资源LUT740911/FF944098/BRAM827+16/URAM752/DSP5375。失败route报告WNS-12.141/TNS-1072433.625、WHS-.245/THS-263.314；no_clock0/unconstrained_internal0、IO delay1/2；DRC Critical RTSTAT-13#1及15763warnings，CDC6×10+2×11 critical/5688warnings，均未自动waive。netlist与10/5/5ns clocks实际PASS，不覆盖route FAIL。

UTC13:27:19 R005/AT001_physopt_slr只读原生启动，PID/SID2093416、实际affinity0..31/192GiB/native8；父FAIL/113输入与DCP历史SHA锚已核，不重跑impl。读取physopt.dcp，仅将其逐SLR位置/空间统计关联失败route日志，不能当失败route网表。入口CPU AT005为25tests/Python/Tcl PASS，修正实际终态表格的独立Congestion Report表头/North Dir/空格箭头格式；旧修前来源验证曾windows空，未被原生使用。新attempt input_manifest已冻结真实final E/N/S/W 4窗及7226454e...runner/Tcl aabd5478...；启动时正在open_checkpoint；后续已完成的原生section及当前待采范围见文首当前实态。
