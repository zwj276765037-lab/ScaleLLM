# A021：实际配置与身份

期望模型/推理强度：gpt-6-astra / xhigh。

第十五次复用范围：GU-only已完成模块与Host证据集中阶段审核；写入仅既有design/results和A021记录。Root+A022+A021最多3活跃，无后代，A022唯一RTL/EDA owner；本次不运行EDA或测试。

第十六次复用范围：G5同阶段core/整板综合资源与已完成netlist/clock、timing/CDC/DRC/check_timing。已按Root增量委派完成正式整板有限审核；guard选择器及同DCP新qualification由A022独占，本轮不重复审、不等待。既有模型/所有权/资源限制保持，不重扫功能/Host或启动EDA。

第十六次后续Root明确委派补核AT011新增终态：保持原Astra xhigh与文档所有权，只读原生逐cell记录/receipt/哈希及准确输入差异；不运行解析测试或EDA、不更改A022驱动。仅有界验证新增结构资格，不重扫旧报告或constructor全量生成物。

第十七次仍原Astra xhigh与本人文档所有权，Root+A022+A021最多3活跃。只读R008已出原生阶段文件及来源/hash，普通CPU集合/哈希核验；不调用EDA、不补跑缺失probe、不干预冻结运行，后续质量待真实证据。

第十八次保持相同身份与权限，仅现有报告/来源/日志静态核算；为-packthru口径查询AMD官方2025.2 UG835说明，读取旧已生成slice_sites及其既有脚本，没有执行旧诊断。Root持有共享比较JSON，本代理只写既有design/results/A021。

第十八次Physopt增量延续同配置：复用已核旧独立站点和去packthru口径，读取新六工件/保存锚并重算SHA与表格差值；没有EDA、测试重跑、后代或工程输入写入，不重复旧功能/constructor审核。
来源：hardware-agent职责要求、M006合同和Root当前明确委派。

实际角色：架构/接口合同。实际协作身份：/root/mlp_plan_architecture（复用前轮架构代理）；本次由Root followup恢复为A021任务。模型/强度依据本代理原始显式委派参数及Root当前任务声明登记，未重新创建或切换模型。

工具权限：仅本人文档/schema与A021记录可写；源码只读；不运行EDA。最多Root+架构+工程，禁止创建后代。实际配置记录不是用户验收或全局工程完成声明。

当前复用回合角色为独立阶段审核，保持原模型/强度与原写入边界；Root当前活跃安排为Root+A022+A021。此次未新建代理，也未切换模型。

第二次复用保持Astra xhigh架构角色：只读RTL/既有证据，写本人design/results/A021记录。没有创建后代或变更模型/资源执行权限。

第三次复用为板级入口静态独立审核，原Astra xhigh不变。仅本人results/A021记录可写，工具执行限读取/静态核算，不创建子代理。

第四次复用保持原Astra xhigh配置；Root授权仅本人design/results/A021记录补充，相关生产RTL由A022独占且正在冻结运行，无EDA权限使用。

第五次复用保持原Astra xhigh，角色为SM026受影响阶段独立验收；只读证据/源码、执行哈希及入口静态check，写design/results/A021记录。未运行EDA、重跑测试、创建代理或更换模型。

第六次复用仍为原Astra xhigh，SM027有限阶段审核；只读已有DCP ZIP/日志/哈希/候选脚本，未运行Vivado、仿真或测试。文档边界、无后代与A022唯一EDA owner保持。

本次终态前新增质量按Root明确范围补核；查询AMD官方UG908 2025.2确认厂商debug占位/opt阶段规则，未执行EDA或建立一般blackbox/CDC waiver。

第七次复用仍为原Astra xhigh，写入仅现有results/A021记录；对冻结入口和来源工件只读、计算哈希/差异，不调用EDA或测试，不建立后代。AT009为A022独占运行，本代理未更改其冻结输入或共享索引。


第八次复用仍为原Astra xhigh；仅只读R004/AT001_impl新增post-opt证据、核哈希与准确对象集合，写results/A021记录。A022保持唯一EDA owner，本代理不干预运行或设置额外审核停点。


第九次复用保持Astra xhigh；Root明确授权读取指定旧ScaleLLM资源报告用于对比，仅作为历史证据，不恢复旧任务。只读当前/指定历史报告与源码，写本人results/A021记录，无EDA或工程输入修改。


第九次补充SLR判断仍限既有报告/统计静态核查；475行driver归属计数只做算术复核，无工具物理查询。旧物理位置/失败统计不当成本轮改善实测。


第十次复用保持Astra xhigh，无后代。写入仅results/A021；读取新诊断六源、已有CPU日志与安装Vivado2025.2命令手册/AMD官方说明。没有执行CPU回归、原生探针或修改工程冻结输入。

AT004增量仍按同配置仅审AT003→AT004差异、冻结日志/SHA和本机原生命令手册，必要只读当前日志格式；不将活动父日志读取称最终证据冻结，不启动EDA或额外子代理。

第十一次保持Astra xhigh，仅静态读取当前RTL与当轮已有physopt日志；历史注释不当当前placement事实，不按资源比例归因拥塞。写入results/A021，无后代、EDA或运行工程修改。

第十二次仍Astra xhigh；写入本目录design/results、新abi_gu_only_draft.json及A021记录，当前abi.json只读并核写前后SHA不变。A022负责实际工程，Host实现需明确所有权；本代理无后代、无生产写入、无测试/EDA。

第十三次新增授权独占PRO_plan/ScaleLLM_MLP_Gate_Up_Only_Dual_DDR_Design.md；写中文完整方案并同步本人文档/机器草案。仍无后代、EDA或生产代码修改，不维护共享索引。

第十四次保持Astra xhigh，短合同收束；新完整abi_gu_only.json独立于v6，生成器/生产代码归A022。本人仅静态核结构/哈希，无测试/EDA，交付后退出。

第二十次AT002仍原Astra xhigh、无EDA/后代。仅读取关闭原生对象/报告与官方Vivado2025.2约束优先级/reset_timing/all_registers依据，并做SHA及集合核算。写入限既有design/results/A021；A022独占修正和新资格运行。
