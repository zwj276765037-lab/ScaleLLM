# A021：MLP linear接口与架构

角色：M006/SM025架构负责人。当前任务依据 [M006合同](../../mission/M006_mlp_linear_only_hardware/contract.md) 和 [W0合同](../../project/hardware/source/mlp_linear/design.md)。

目标：冻结可实施ABI/schema、cache/parser/compute/DMA/job互连、clear/排空、错误/ACK/epoch及工件兼容，及时交A022实现。当前根为 /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM_MLP_fix。

独占写入：project/hardware/source/mlp_linear/ 与 agent/A021/ 四份Markdown。Root维护共享mission/索引，A022维护RTL/TB/构建和E013证据；不撤销他人修改。无EDA、无后代、无新聊天。

架构接口已实际消息送达Root和 /root/mlp_linear_engineering；后续模块里程碑复用本代理独立审核。普通实现修复无需逐次放行。资源重工具协议由工程持有，A021不启动工具进程。

2026-10-24第十五次任务：集中只读GU-only G1/G4R已完成证据及当前实现。七项RTL模块和Host42 CPU范围限定接受，G4R总整合/CSR/真实metadata fault/完整生产elab待终态；不新增全N×32层仿真门，G5不等待G4H。详细结论见results第十五次、实施映射见design §11。普通实现继续，本代理不重复测试或启动EDA。

第十五次新增终态已闭合：AT019/023/024/026均独立接受，G4R_LIMITED_PASS；AT025测试实例guard遗漏原FAIL保留，AT026仅改guard为1。当前实际源SHA一致，G5入口具备资格，Root/A022连续推进；本回合完成，不等待或预判新构造/物理。

2026-10-25第十六次G5准备：只读新core正式综合资源，与同工具/器件/Design/阶段v6 core比较；整板报告/原生结构和clock终态出齐后集中补审。禁止core对整板、synth对placed混减，不把面积减少当SLR布通，A022连续运行不等待本代理批准。

第十六次终态增量已完成：正式整板资源/clock/netlist及质量原文、DCP/报告SHA、自然FAIL/无残留独立核验。新旧530/554精确集合与6 CDC10路径一致；未布局hold不当最终失败，旧最终两CDC11仍须新物理结果。guard选择器由A022独占修复，同DCP资格待新原生结果；本轮不重复审该修复或空等。限定结论落results/design，既有连续授权不增加批准门。

第十六次AT011新增委派已完成：只补真实同DCP资格/receipt与逐96lane完整37bit存储、clock/约束/24级身份。30工件SHA、102输入精确两driver变化及七件报告字节复用独立核验，结构资格限定接受；原失败和物理未完成范围保留。A022已连续进入R008，本代理不等待后续阶段或新增批准门。

2026-10-25第十七次完成：只读R008真实post-opt debug/24级及两个XPM scope对象/coverage。基本阶段门限定接受，valid/ignored四文件未出保留PENDING，不能按比例误判寄存器漏约束或自动waive。身份/五工件SHA与范围落既有results/design，正常place/route继续；无EDA、重测、生产输入修改或新审批门。

2026-10-25第十八次：只读新Placed原生SLR及四scope、保存DCP来源与当轮控制优化日志，解释面积下降与站点近满并存。实际Attention/GU分布记录，不把旧位置套新图；核旧-packthru和已有slice_sites独立基线，未混阶段计算改善。同批congestion已补核：Level6 Attention与Level5 GU/权重链两类代表窗，不把列项比例当原因份额。后续只补Physopt同阶段结果，不新增EDA或改变当前物理运行。

第十八次Physopt增量已闭合：同阶段站点总减2870/2.0443%、SLR1仅减780而SLR2增1696；Logic+Memory归一化LUT减11.3391%、SLL减15.3362%。新DCP/六报告身份核实，表内congestion仍Placer Final Level、旧min_level3筛选不同，不称route或因果改善。普通物理流程继续，后续仅审新增终态。

2026-10-24首次有界审核：读取A023 Host数值/codec及32项CPU原证据，核验ROM/参考独立性/文件身份；核A022 R001 AT001–004模块范围。已完成，结论见results.md；不扩展到新生产替代图，不等待AT005，不启动测试或EDA。

2026-10-24第二次有界任务已完成：为真实production层次冻结仅输出列缩小的主TB合同，GU128/Down64、K128/448；参数传播/生产guard/错误恢复与证据边界写入design §9。工程由A022继续，Root安排独立TB支撑，本代理不改RTL/TB、不运行EDA、不等待工具。

2026-10-24第三次有界任务完成：只读预检M006新板级create/build/run/输入closure、默认shape保护、生成输入/DCP身份、资源与结果判据。具体WIP缺口已交A022，结论在results末节；不执行EDA，不阻塞独立硬件修复。

2026-10-24第四次有界任务完成：只读复核BRESP可排空恢复、framing/global_freeze边界、首错/快照/ACK/clear与inclusive观测计数；五项缺口交A022下一attempt，最小确定性规则写design revision4。AT028冻结源不热改，不等待终态。

2026-10-24第五次有界任务完成：SM026受影响阶段核AT028完整真实整合、AT030五项错误决策修订与AT031当前全局故障恢复的原始终态/输入身份，独立gold与差异复用；当前生产默认shape/源图支持进入constructor。有限PASS及NOT_RUN边界见results，不等待constructor、不新增架构或逐项批准。

2026-10-24第六次有界审核完成：SM027 AT003构造与AT004当前完整DCP/约束/整板资源、诊断清理继承候选。构造限定PASS，AT004终态/质量未齐，物理资格未签；后续只核新增证据与实际继承差异，不重扫已核constructor。

第六次审核终态补充：AT004在本轮结束前自然FAIL，原因末尾身份查询/占位阶段判据；已核新质量与530/554 DDR debug、六reset CDC。允许新原生DCP qualification及正常opt取证，保留旧FAIL，后续只核新增结果。

2026-10-24第七次有界审核完成：仅当前build/runner的qualification来源、成功凭证/impl依赖、post-opt/pre-place debug/clock/24同步级门。来源字节和精确四文件差异通过独立静态核对；AT004/007/008保持FAIL，AT009仍运行且无成功receipt，未声明原生PASS。原对象clock覆盖与最终全局unconstrained/timing/CDC范围明确分开。不运行EDA、不改工程文件、不等待长终态。

第七次审核收尾终态更新：AT009原生0、无stop/漂移/残留，新receipt/26工件SHA、实际netlist/三clock/24级结构全部核对通过；接受限定qualification，可进入正常opt。继承overall FAIL与最终物理范围保留，原AT004/007/008不改。


2026-10-24第八次有界审核完成：仅新增真实post-opt来源/530与554对象clock覆盖/零黑盒/六链24级结构。原生证据限定PASS，place同进程继续；最终全局时序/CDC/route另判，不重复旧资格、constructor或功能，不执行EDA。


2026-10-24第九次有界核查完成：针对用户资源疑问，读取同阶段整板旧新分层报告并对账、核保留双8×12阵列/metadata和旧前端复用机制。确认LUT/FF/BRAM/DSP实际下降7.58%/7.31%/11.64%/1.39%，URAM保持752；只做归因，不更改工程目标或停止impl。


第九次用户澄清补充：仅阅读E004/E006/M003既有热点记录，核被删SwiGLU与MLP input确曾涉及热点；保留shared/Down S54/repack/Attention/DDR链。给A022准确旧scope与四类同阶段后继指标，不新建选型、不改变当前impl。


2026-10-24第十次有界审核完成：只读新SLR诊断入口/CPU证据，发现并交工程修复routed历史锚、native退出码、report_timing互斥参数三项问题。AT003 22项CPU及源码身份核对通过，限定静态接受；未运行EDA或改当前实现，原生查询仍NOT_RUN。

2026-10-24第十次AT004小增量完成：仅核最后原生拥塞报告最多4代表窗及包围clock_region查询；24项CPU原始证据和对象类型静态接受，明确报告阶段与被读DCP阶段不同只能作候选空间定位。未重复之前范围、运行EDA或改变当前route。

2026-10-24第十一次完成：响应用户“是否调度导致拥塞”，只读当前GU/Down复用与shared广播/归约/累加/重排及当轮physopt高扇出日志。给事实/推断分界与三个可证伪方向；只更新本人文档，不停止或更改当前实现。

2026-10-24第十二次完成：按用户GU-only方向形成下一版方案，Down完整移Host保留数学；核DDR隔离、量化可裁层次、定义ABI/metadata/epoch/Host数值和连续阶段。单独机器草案不热改当前abi/冻结工程；当前R005继续，不新增EDA。

2026-10-24第十三次完成：用户明确要求独立完整新方案，交付PRO_plan/ScaleLLM_MLP_Gate_Up_Only_Dual_DDR_Design.md，GU-only v1.0-draft.2。硬件主线/Host系统验收分开，保留历史方案，修订本人draft/摘要保持一致，不扩大验证范围或修改工程。

2026-10-24第十四次完成：依据用户实施授权，冻结独立完整abi_gu_only.json、统一v1.0状态和metadata-fault owner响应，交A022立即生成使用。当前v6/R005不改；无新审核包，结束释放并行槽。

第二十次AT002追加授权：Root要求实质收敛Max-DPO优先级缺口。本代理负责既有design §12中的最小约束合同/独立验收，A022工程执行；同routed副本精确保留非目标cut，138握手动态D及必要两SMC实际D恢复原10ns预算。原历史102/quality/DCP保持，无额外用户批准门。
