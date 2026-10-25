# M006：MLP线性投影硬件工程进展

状态：GU-only RTL、限定功能验证、新综合、合法布线和内部时序已经完成；约束与复位告警正在收尾复核，尚未取得完整硬件签核。唯一新工程根为`Workspace/ScaleLLM_MLP_fix`。

当前关键结果：R008/AT001_impl自然退出0，1687352条可路由网络全部完成、0路由错误；正式WNS **+0.002 ns**、WHS **+0.010 ns**，setup/hold/脉宽违例均0。最终网表Down实例0，96条GU lane、3072 MLP DSP和448 GU metadata URAM符合合同；Host Down保留原整数数学。原质量汇总FAIL保留：三个外部复位端口时序覆盖不足、四次辅助报告参数错误，以及待审核的复位/约束告警。当前正完成同routed DCP有界补证，并按design §12修正被clock_groups覆盖的Max-DPO约束；优先同物理网表资格复核，尚未重做implementation。工程验证版bitstream已生成；上板/真实完整模型验证未执行。

已生成文件：[ScaleLLM_MLP_GU_only_ENGINEERING_VALIDATION.bit](../../project/hardware/vivado/reports/m006_gu_AT003_preliminary_bitstream/native_output/ScaleLLM_MLP_GU_only_ENGINEERING_VALIDATION.bit)，80.2 MB。仅工程验证工件，跨时钟绝对延迟和外部reset签核尚未完成，未下载上板。

最新执行方向（2026-10-24）：用户已批准[GU-only新版方案](../../PRO_plan/ScaleLLM_MLP_Gate_Up_Only_Dual_DDR_Design.md)开始实施。FPGA静态移除Down，保留GU双8×12和Attention；Host承担原整数Down。A022已于UTC15:11:32开始独立新RTL图，A021集中冻结新合同；Host工程随后按明确文件所有权并行。当前v6整板R004已自然布线失败（473423未完成信号、545088重叠节点），R005已因新版实施优先收束为PARTIAL（native -15、0survivor、锁释放、116输入无漂移），已保存并核30件工件，SLR1站点99.86%等核心观察有效，剩余新窗/显式路径NOT_COLLECTED；新GU-only代码/验证状态不得与这些旧图证据混用。下文较早进度保留历史，新版G4R已限定通过，硬件物理完成尚待G5。

最新交付优先级（2026-10-25）：用户明确要求先生成bitstream。AT002剩余只读SMC补查已按该优先级收束为partial并核0归属存活，原核心21工件与告警缺口保留。R008/AT003_preliminary_bitstream已于北京时间08:32:18启动、08:45:47自然native0结束，从原cc34…routed DCP成功生成工程验证版.bit；80159259B，SHA256 `66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47`，Root已独立复算并向用户交付链接，0遗留/源无漂移。Max-DPO/外部reset签核未闭合必须随工件说明，仍不下载或上板；约束修正随后继续。

## GU-only 新版实测（2026-10-24，持续更新）

- R006/AT004：新真37位两列lane的512组数值与48次在途clear重放通过，1638周期检查；旧GU路径逐拍比较及独立整数gold均一致。原生编译、elab、xsim均0，无强停或遗留进程。该结果只覆盖lane，尚不代表完整双8×12或生产集成。
- R006/AT012：真实双8×12 GU计算核PASS，N128/fullK128/16行共4096个输出与独立gold一致，含row/column scale/shift变化；非fullN14336整链结论。AT013 job完整opcode/保留字段拒绝与fault/ACK/owner回归PASS。AT014生产图语法PASS，elab/功能分别验证。
- R006/AT016 tensor：生产1792条GU输出和完整73728B输入、4KiB/16beat/反压/最终B屏障、非法Down/长度错误无AXI及错误响应回归PASS。AT018 metadata：loader+resident+scheduler有界32条记录、padding错误完整排空/有效前缀、active bank保持与禁止commit、64条读回PASS；不是full229376记录实跑。
- R006/AT006、AT007：工程已报告128组cache与REC576 parser实际仿真PASS；完整地址、高位越界不别名、乱序/提前seal、非法opcode、错误drain及末record反压。job/meta等语法通过不当成功能通过。
- A023最终合并CPU测试26项通过，原生0、输入未漂移、峰值约942MiB。完整16×4096 Down输出与独立448组整数参考逐位一致，并加入原exporter真实pack工件解码测试。32层两cohort的128硬件命令/64 CPU Down为mock依赖/租约验证；真实板卡、模型传输未测；随后新增真实CSR/XDMA adapter的16项fake transport/系统调用转发测试PASS，合计42项分两次运行，新adapter尚未上板。证据：[Host运行清单](../../project/E013_mlp_linear_only_hardware/experiment_results/host_gu_only/AT_20261024T153221518972Z/manifest.json)。
- 当前A022继续GU-only硬件集成/故障回归/新综合物理流程；A023已交付Host backend及CSR TB并结束本子阶段，A021已恢复集中阶段审核。G5依赖G4R，不等待完整Host模型系统。
- R006/AT019真实production集成PASS：222035项检查、112509周期、262144B元数据；同epoch4GU、非法Down/0x101无AXI、REC错误重试、ABORT真实排空、BRESP维护保DONE及物理早RLAST/core-reset重试。xsim1413.486s。AT023 CSR PASS：4155检查/594writes，保留零字段WSTRB矩阵、Down RO0及任务快照/ACK。A021已独立核原生终态与当前源身份；AT024 metadata真实全局故障PASS；AT025因TB enforce误设0触发断言FAIL并保留，修正实例为1后的AT026完整生产elab PASS。A021已按既定覆盖限定接受G4R；不外推完整模型/并发Attention/板卡。
- R007/AT006_constructor已原生0完成（无漂移/无强停/无遗留进程，1323生成文件与10工件绑定），新工程`project/hardware/vivado/project/m006_gu_AT006_constructor`；102项输入冻结。R007/AT007_synth已于UTC16:29:36实际启动；新综合资源/物理尚无成功结论。
- 新GU-only core综合已完成并生成DCP，原生report实测LUT593717、FF756043、BRAM542tile、URAM528、DSP5368；A021已核同阶段旧core对照，分别减少86081 LUT、61662 FF、192 BRAMtile、224 URAM、1 DSP。这是计算核心口径，整板资格核查与资源报告尚待完成。SLR分布、拥塞、合法布线与时序仍未取得，不能把core资源下降替代物理结果。

- AT007正式整板Synthesized报告已生成：LUT679997（较v6减少86081，11.24%）、FF892475（减少61662，6.46%）、BRAM643tile（减少192）、URAM528（减少224）、DSP5374（减少1）。[同阶段比较](../reviews/M006_gu_only_synthesis_comparison.json)绑定两报告SHA。新synthesized.dcp已保存；AT007整次native1/无强停/无输入漂移/零遗留进程，失败点为96lane的guard pin查询全部返回0。Down0/3072MLP DSP/448GU元数据URAM/96lane与10/5/5ns时钟实际核实；A022按普通查询修复对同一新DCP资格复验，不重复综合、不降低37bit断言。pre-opt no_clock530/internal554及CDC待后续复核；物理尚未运行，不以综合资源改善代替SLR改善。

- AT009同DCP资格仍native1：真实rebuilt hierarchy已将lane边界端口重命名，原RTL guard名称查询不成立。AT010已先解析实际Vivado结构Verilog，确认96lane各148个guard FDRE，共14208，覆盖两组×两entry×37bit；下一原生资格改核这些真实存储对象，不改RTL/数值合同，不重综合。原失败/18.81GiB峰值/无输入漂移/零遗留证据保留。

- AT011同一新DCP原生资格native0完成：全部96lane各148个FDRE完整覆盖两组×两entry×37bit，guard0/1各7104，缺位/未知0；Down0、3072MLP DSP、448GU元数据URAM、10/5/5ns时钟、6链24同步级身份均PASS。无漂移/无强停/零遗留，峰值19.04GiB。原AT007/009 FAIL及pre-opt质量状态保留；R008/AT001_impl已于UTC18:07:59真实启动，消费同新DCP与资格receipt、同102冻结输入；32核/192GiB/8线程，当前载图。后续连续opt/place/physopt/route，布局和物理优化后采SLR/拥塞；尚不代表合法route/时序/CDC完成。

- R008新opt_design原生成功（34m49、0error/0critical），optimized.dcp已写出，place_design已实际启动。post-opt 0黑盒，原530/554目标全部存续且有时钟，24同步级核验通过；两个SMC实际FDRE/D端点各有10ns Max Delay Datapath Only/Endpoints1覆盖证据，四份valid/ignored辅助报告未生成、保持待核。A021有限审核未发现阻断布局项；最终CDC/时序/route未验收，SLR结果尚待。

- R008 place_design原生成功（1h37m19、0error/0critical），placed.dcp SHA `cc92d8dcbc90d23b358627ccc7e2ea201b864cfb3092cbc58ddb1850459fa0cb`。当前Fully Placed报告SLR0/1/2 CLB占用83.75%/98.28%/97.14%，LUT179085/243557/234256，URAM168/168/192，DSP1571/1840/1963；估计WNS+0.501ns但工具仍报高度拥塞。SLR1/2仍近满载，不能以总LUT下降判定拥塞解决；新Physopt报告出来前不与旧Physopt直接相减。当前scope/拥塞报告继续生成，后续物理优化/route尚待。

- Placed五份SLR报告和congestion已齐：GU branch1主体SLR0、branch0主体SLR1、Attention主体SLR2（触及44815站点；scope站点不可相加），GU元数据URAM168/168/112。最高Level6窗口涉及Attention postprocess_store/right2/KV量化，GU branch0相关代表窗Level5；窗口单元占比不是因果贡献。phys_opt_design已实际开始，等待同阶段新结果后再与旧Physopt比较。

- 新phys_opt_design原生5m01完成，估计WNS+0.465/TNS0；因无setup违例，工具明确未修改网表。新Physopt站点与Placed相同，同阶段旧→新CLB为45040/49193/46155→41254/48413/47851：SLR1仅释放780站点、SLR2新增1696、SLR0释放3786，全板减少2870（2.04%）。旧站点口径有独立原生slice_sites去重计数支撑；旧LUT比较须排除-packthru额外路由穿越LUT。SLR1/2近满载仍在，route尚待。

- R008 route_design已实际进入Phase1 Build RT Design。Physopt DCP SHA `5c8922a05f8ec15ad30fbc2453d2cc163b3c56b20ac52a99b67900f60b70be72`，六报告绑定已存。A021同阶段核Logic+Memory LUT740911→656898（-11.34%）、SLL13817→11698（-15.34%），站点仅-2.04%。新拥塞报告仍自报Fully Placed/Placer Final Level；新旧报告参数不同不能以行数比较热点减少，Level6仍在。合法布线/最终时序仍待原生结果。

- 首轮route估计已可同类别比较：旧Global/Short Level7(128×128)→新Level5(32×32)，Timing类别仍均Level7。Root已核两原生日志Route35-448/35-581准确行；这支持首轮普通布线压力有所缓解，不证明合法route或时序收敛。当前进入Rip-up And Reroute Global Iteration0，最终结果尚待。

- R008同一Global Iteration0原生overlap计数504525→79281→13837（UTC21:52观察），冲突下降但尚未清零/终态。10条Route35-462路径静态身份均为固定任务group_count的同轨迹冗余位（reset0后命令接受置1），实际是否合并及约束覆盖待最终DCP核，不直接豁免。

- R008 Global Iteration0重叠节点实际清零，但中间时序WNS−1.798/TNS−83.044、最新WHS−0.240/THS−71.412，尚不合格且非终态。工具自然进入Global Iteration1，重新调整路径后临时overlap1049→241→95→59；继续原冻结流程，无重启。最终route/时序/CDC仍待。

- R008五轮全局重布线均消解到0overlap，Phase8原生汇总failed/unrouted/partial/overlap均0，Phase9 routed-net verification成功；最新router估计WNS−0.325/TNS−3.377、WHS+0.006/THS0，setup仍负值。当前进入Phase14路由内物理优化，route命令尚未返回、正式timing_summary未出，不提前判整体物理PASS。

- R008 route_design原生成功（2h02m23，0error/0critical），实际routed.dcp已保存SHA `cc34f49bef612472367f7d273596d09dede15128d3b72a2708507e4c6d6c7cc4`。正式route_status确认1687352/1687352全部fully routed、0routing errors，A021独立核DCP/日志/102输入一致，限定ROUTE_LEGALITY_PASS。路由内Phase14物理优化后WNS+0.002/TNS0/WHS+0.010/THS0；正式时序/DRC/CDC/结构及约束告警收尾尚待，整体未提前PASS。

- R008整次于UTC23:27:20自然native0结束，无强停/102输入无漂移/0遗留，峰值27.38GiB。正式Routed时序WNS+0.002/TNS0（setup0/2848130）、WHS+0.010/THS0（hold0/2846686）、WPWS0/TPWS0（pulse0/949552）；最差GU状态计数→CSR读数据，2ps余量。末图96lane/14208guardFF/3072MLP DSP/448GU URAM/Down0与时钟身份全PASS。DRC0Error/Critical；原quality仍FAIL，包含reset IO delay1/2和四XPM查询参数错误，CDC8严重项及bus-skew补证待集中复核；只对保存的routed DCP做有界补查，不重复物理、不改原回执。

- AT002已取得四scope bus-skew MET（实际1.072/0.652/1.364/1.084ns，对10ns），10条告警D实为每half共源FDRE合并；两新增reset4级链与两DSP代表结构核验符合既有合同。但逐D timing明确Asynchronous Clock Groups/Slack inf，10ns Max-DPO被高优先级clock_groups覆盖，属于实际绝对延迟约束缺口；scope coverage列出该约束不能证明生效。Root已交A021制定最小约束修正及同routed副本受影响资格，A022待当前冻结查询自然终态后连续执行；不虚构IO时序或重写历史PASS/FAIL。

## GU+Down 旧版阶段历史（不代表当前运行状态）

- 已完成仓库克隆、独立工作分支、设计阅读和[实现计划](../../PRO_plan/ScaleLLM_MLP_Linear_Only_Dual_DDR_Implementation_Plan.md)。
- A021交付[W0硬件接口合同](../../project/hardware/source/mlp_linear/design.md)与revision 2机器可读schema；Root静态核查94个CSR、39个错误码与544-bit descriptor映射通过。此结论仅限结构一致性。
- A023交付Host整数参考与REC576/GU/Down codec，[32项CPU测试通过](../../project/E013_mlp_linear_only_hardware/experiment_results/host_reference/README.md)。范围为合成输入、完整16行数值和字节布局，不代表完整模型或RTL结果。
- A022已交付cache/parser/GU scheduler、compute/DMA/job/CSR及生产集成源码与新根构建入口，持续联编和仿真。旧版本cache/parser局部PASS与当前修订需区分；AT004 GU scheduler pilot通过，完整生产形状AT005通过（229376源记录、305920内部pass、1792输出），生产源图AT009联编通过；上述结果不代表完整共享核数值或整板功能通过。

## 旧版执行记录

A022为唯一重EDA owner。A023已交付Host、CSR、真实生产整合自检测试、独立Python gold及板级Tcl加固；A021已完成design revision4错误处理规则及SM026阶段验收；五项实现缺口已由A022修复并通过受影响回归。A021/A023当前空闲；最多Root加两名活跃子智能体，无后代。

资源：小型仿真8核/96 GiB RSS；后续整板32核/192 GiB RSS，Vivado单流程8线程，独立IP/OOC最多4个并行任务。正常任务不因运行时间长或日志静默停止；保留系统可用内存和磁盘保护。[资源决定](../../.research-agent/decision_inputs/M006_resource_profile_revision_20261024.json)。

## 旧版验证与物理阶段记录

当前cache/parser、生产长度DMA、CSR及小shape完整K共享核已取得模块PASS，详见[SM026进展](../reviews/SM026.md)。AT028有界真实生产整合通过235509项检查，五项控制边界修补的AT030/031回归通过；A021已独立接受这一有限功能阶段。新Vivado工程R003/AT003_constructor已真实生成，AT004已生成整板综合网表，但收尾身份查询错误导致整次FAIL，正在修复并以同一DCP重新验证；完整综合验收、布局布线、时序/DRC/CDC尚无通过结论；板卡与完整模型未验证。

最新执行状态与原始尝试见[E013工程摘要](../../project/E013_mlp_linear_only_hardware/experiment_status/summary.md)，独立审核见[A021模块结果](../../project/hardware/source/mlp_linear/results.md)。

最新SM027里程碑：R003/AT009同一综合网表原生资格核验完成（native0，输入无漂移，20.04GiB峰值）；Attention/共享kernel/三工作时钟/24同步级均PASS。原AT004 FAIL及未布局质量结果不改写。按既定32逻辑CPU/192GiB资源配置继续唯一implementation；最终route/timing/DRC/CDC尚未验收。

当前物理里程碑：R004/AT001已完成opt及限定post-opt独立验收，place原生命令成功并保存网表，正在phys_opt。工具已报高度拥塞，布局估计WNS-.645ns，最终布线/SLR/时序未过；正在按用户关注补充同阶段SLR热点与拥塞对照，不能用整板LUT下降7.58%代替SLR改善证据。
