# E013：实验状态摘要

<!-- A022_CURRENT_G5_BEGIN -->
当前G5（2026-10-25T02:01:28.192170+00:00）：G4R LIMITED_PASS、GU-only constructor/综合与AT011同DCP结构资格已完成。真实96lane×148 guard FDRE（37bit×2channel×2entry）、Down0、MLP3072DSP、GUmeta448URAM，Attention/共享核与10/5/5ns时钟身份通过；此范围不等于完整板级签核。

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

- execution_state: running
- verdict: function_pass_route_fail
- applicability: M006新根；有界真实整数核与完整生产层次功能/故障恢复通过，constructor与同完整DCP原生qualification完成；整板实现已自然FAIL并完整收尾；唯一R005只读SLR取证已实际启动，物理未合格。
- 当前R004/AT001_impl：UTC06:19:43启动，消费AT009成功qualification、同104输入freeze3b46f8bc...；32CPU/192GiB、native8线程。opt34m30、place1h48m53、外部physopt11m17均原生成功；已自然终态native1/stopnull/changed[]/0survivor、peak tree RSS29.54045GiB；Route35-2非法路由/545088重叠节点及Route35-162/473423 failed signals，overall/route/setup/hold/DRC/unconstrained均FAIL。
- post-opt/pre-place实际门PASS：0黑盒，原530/554对象全部存续且查到clock，6条reset链24级ASYNC_REG/100MHz/相邻连接符合。A021独立限定审核通过；不外推全部端点约束、最终timing/CDC。
- 原生日志保留Place30-1229 USER_SLL_REG建议未满足（100仅显示上限）、Place46-14高度拥塞、MIG Place30-1995；Route35-447转为优先布通、35-448/35-581估计Global/Short与Timing拥塞均level7（128x128）。实际方向窗口及prefix SHA见AT001_impl/route_initial_congestion_observation.json和route_initial_congestion.txt；不是最终失败/成功或模块归因。
- 已保存optimized/placed/physopt实际阶段DCP及生成时SHA/log-prefix观察；pre-route估计WNS-.219/TNS-11.018ns，非最终时序。终态peak tree RSS31718821888B/29.54045GiB、0survivor；没有资源保护或输入漂移。
- 用户核心验收是减少FPGA MLP操作能否缓解SLR问题。分别判断局部压力是否下降、是否足够合法布通；全局资源下降或仍拥塞均不能替代局部实测。自然终态后按slr_evidence_plan.md打开最佳实际保存阶段只读定位，不重复route补报告。
- R005/preparation/AT005_cpu：新SLR入口25项CPU测试、Python编译、系统Tcl8.6.14语法完整性通过，六源snapshot/hash已存；未执行Vivado。真实父自然native1/stopnull/无漂移/0survivor已核，保留父FAIL与阶段；routed必须有实际生成时历史SHA锚。采metadata/shared双branch等8scope逐SLR资源/实际SLICE、7旧窗+最多4个最后原生拥塞代表新窗、最多400跨界路径样本（非全量）。
- R003/AT003_constructor原生0完成：1323生成文件/规范化XPR+10工件receipt，实际core100MHz/双DDR UI200MHz，peak3139215360B/0survivor；构造完成不等于物理通过。
- AT004原FAIL保留：22OOC+top综合原生成功、完整DCP211877273B/SHA cf11b600...，末身份probe未匹配前缀REF_NAME并误拒pre-opt dbg_hub_CV。native1/stopnull/changed[]/0survivor、peak50.06GiB；原critical不抹除。AT007 close_design与AT008对象集合查询FAIL也保留。
- AT009 qualification原生0/stopnull/changed[]/0survivor、peak20.0415GiB；精确Attention/kernel1/1、禁止MLP非线性0/用户黑盒0、10/5/5ns clocks和24级reset结构PASS。成功receipt f0fee79c...绑定26工件/1433文件及准确4文件修补，同DCP/未变报告有限复用经A021审核。原quality overall FAIL保持。
- 正式综合整板资源LUT766078/FF954137/RAMB36=827+RAMB18=16（835tile）/URAM752/DSP5375；core LUT679798。有效board pins/主钟/三域异步组已在完整DCP核，约束遗漏假设排除。未布局质量的hold/PWS/IO delay及CDC6critical/6198warnings保留；六复位结构限定接受不代表最终CDC通过。
- 功能证据：AT021共享双8x12/S44/S54真实整数核N128/64、完整K128/448，4096GU+1024Down gold PASS；AT028完整真实生产层次235509checks/139012cycles/491520metaB、9compute及坏REC/ABORT/BRESP真实维护/physicalDDR1 framing恢复PASS，Attention idle；AT030首错/同拍/late fatal/timeout/owner及计数单位PASS；AT031真实global fault focused30529checks+GU gold重试PASS。
- 其余已PASS：生产GU调度、当前cache/parser（中段坏组前缀/末写阻塞）、完整生产两opcode DMA、CSR1860checks/mock、Host32CPU tests。AT028到当前RTL的复用边界见reuse_after_priority_revision.md；不以gold不变继承所有控制。
- 尚未通过：生产full-N整数、Attention并发、合法route/最终setup与hold/完整DRC与CDC/SLR闭合/板级。详细历史与原始路径见experiment_results/summary.md。
- 资源保护：small-sim8CPU/96GiB；board32CPU/192GiB、native8线程/IPjobs4；共同MemAvailable64GiB持续30秒、磁盘30GiB，单EDA owner，无墙钟/静默强停，不触其他进程或板卡。

UTC11:31左右route GlobalIteration1原生结束，累计elapsed2h19m15/CPU9h09m33，进入Phase5.3 GlobalIteration2。该迭代中overlap节点1729692→921600，Route35-416中间WNS=-12.148ns/TNS=-1074756.284ns、hold N/A；详见route_iteration1_completion_observation.json。当前有消除冲突进展，但绕线时序代价明显，尚非最终route/时序结果，不与旧最终计数直接相减。实现候选归因见experiment_source/congestion_implementation_evidence.md（11条当轮高扇出原文、宽FIFO/共享主体/metadata672URAM及DDR跨区约束），没有据此热改或新启动EDA。

UTC13:02实态：route Phase9原生验证失败，ERROR Route35-2明确545088 node overlaps、Route35-17确认router errors，route实际13733.3s；当前失败后自动DRC尚在运行，未提前签整attempt终态。失败见证前10节点已直接涉及shared branch0 shift/recover、metadata down_bank1 wr_data_local及d0_mig_slice triple_slr，采样不代表完整排名。原始段及SHA见AT001_impl/route_failure_native_excerpt.txt与route_failure_observation.json。尚无routed.dcp，最后保存阶段physopt；终态/无漂移/0survivor后按既定只读入口采该早期布局的逐SLR资源及旧新空间窗，失败route日志与physopt网表分开，不重复route补报告。物理FAIL不改成功功能证据，也不预判各局部指标完全无改善。

UTC13:23:36 R004/AT001_impl真实自然终态FAIL：native1、stopnull、changed[]、28历史owned PID最终0survivor，peak tree RSS31718821888B/29.54045GiB。终态20native工件SHA见terminal_artifact_hashes.json；失败route实际资源LUT740911/FF944098/BRAM827+16/URAM752/DSP5375。失败route报告WNS-12.141/TNS-1072433.625、WHS-.245/THS-263.314；no_clock0/unconstrained_internal0、IO delay1/2；DRC Critical RTSTAT-13#1及15763warnings，CDC6×10+2×11 critical/5688warnings，均未自动waive。netlist与10/5/5ns clocks实际PASS，不覆盖route FAIL。

UTC13:27:19 R005/AT001_physopt_slr只读原生启动，PID/SID2093416、实际affinity0..31/192GiB/native8；父FAIL/113输入与DCP历史SHA锚已核，不重跑impl。读取physopt.dcp，仅将其逐SLR位置/空间统计关联失败route日志，不能当失败route网表。入口CPU AT005为25tests/Python/Tcl PASS，修正实际终态表格的独立Congestion Report表头/North Dir/空格箭头格式；旧修前来源验证曾windows空，未被原生使用。新attempt input_manifest已冻结真实final E/N/S/W 4窗及7226454e...runner/Tcl aabd5478...；启动时正在open_checkpoint；后续已完成的原生section及当前待采范围见文首当前实态。
