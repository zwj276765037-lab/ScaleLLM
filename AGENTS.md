# ScaleLLM：共享工作约定

三个工作角色：项目主控、工程实验、研究探索。启动时声明本轮角色，读取 research-agent 技能及相应参考文件；用户当前指令优先。

## 当前整理边界

- **2026-10-18最新用户已明确“可以继续了”，解除本次服务器重启暂停，恢复M003。** 授权见`.research-agent/decision_inputs/M003_user_server_restart_resume_20261018T081902Z.json`和`.research-agent/project_pause.json`。从AT013未完成的fresh core命名诊断/选择器问题接续：先核45源/3RTL/G2/本版DCP及资源锁，改进有界属性导出并登记新AT，A007独立无阻断后原生执行；常规修复→G4→完整物理按原合同连续。A006唯一生产/EDA owner，A007只读独立审核，最多3活跃含Root、无后代。下方禁恢复为此前暂停期间状态，本次明确继续已取代；正常无墙钟/静默强停、原资源保护/禁区不变，GPU仍另管。

- **2026-10-18最新最高优先：用户因服务器重启明确要求中断M003。** AT013于07:44:47Z受控停止，监督及归属子进程均已退出，EDA锁已释放、观察器结束、关键输入与部分产物保全；A006唯一进程停止owner，A007只读审核；从此禁止任何新跑/重试/恢复，必须等待用户新的继续指令。当前停止授权仅来源本次用户明确指令，不因慢诊断强停。实态见`.research-agent/project_pause.json`和`mission/M003_joint_routability_closure/server_restart_handoff_2026-10-18.md`；下方连续执行授权均为本次暂停前历史。GPU由用户另行管理，不触碰。

- **2026-10-18 14:12最新M003：E011/R002/AT003自然失败，23项综合子任务完成，后检查误匹配parent_count为payload。** native1/stop=null/survivors空，3RTL不变；另XDC调用Designutils20-1307需实质修复。A006/A007已真实续接常规入口修复/独立审核，不增批准、不改设计/池/预算，G4前核完整覆盖/实际apply与restore。无布局布线结果。下方14:10“后报告运行”为终态前观察。

- **2026-10-18 14:10 M003当前：SM015/SM016限定功能/入口独立通过，SM017 E011/R002/AT003新综合后报告运行。** 23/23综合任务end、0error标记，整次未终态，G4未过、布局未开始。core资源LUT+111/FF+34/CARRY8+4/存储DSP不增。Designutils20-1307新overlay调用告警已交A006/A007，进入place前必须原生闭合，不热改正在消费的冻结源、不强停正常进程。GPU由用户另行管理，本对话回到M003。

- **2026-10-18当前M003：G2已冻结，SM015/SM016 E011/AT001于03:17:41Z实际开工。** 决定见`mission/M003_joint_routability_closure/g2_joint_design_freeze_2026-10-18.md`；M2+A3+C-P1 selected，其他deferred。A006唯一生产/EDA owner，A007独立审核；按G3a/G3b→SM017新综合→G4→SM018连续推进，常规修复不新增批准。TOP01 −2.896ns未直接处理及G1对账差22049保持OPEN。下方G2未过/生产禁改仅为冻结前历史；新运行实态以工程回执为准。M004/E010为共享空间其他工作，保留其改动，不属M003。

- **2026-10-18最新衔接：SM013/E009取数及独立审核已完成，Root限定接受固定查询证据并实际启动SM014设计。** AT003于02:11:43Z自然0/0/null stop结束，无EDA；报告547548与canonical569597差22049保持OPEN，非无条件G1 PASS。主控正式决定`mission/M003_joint_routability_closure/g1_scope_and_sm014_start_2026-10-18.md`；A006已于02:42:57Z实际开始F1–F4离线设计，A007独立审核运行中。候选未选、G2未过、生产未改。C-A3宽度切片仅新增待比较机制；C01 SwiGLU分支与E009 TOP01 shared_compute分支是不同对象。下方准备/诊断运行阶段均为历史，不覆盖当前阶段。

- **2026-10-18最新用户执行授权：“可以开始进行mission”。** M003已正式进入SM013工程准备，A006唯一EDA/新实验负责人、A007独立审核已真实派发。执行补充`mission/M003_joint_routability_closure/execution_start_2026-10-18.md`与`.research-agent/decision_inputs/M003_user_execution_start_20261018.json`。此前“仅定义/planned/不自动启动”是本次授权前状态。按G1–G6技术依赖连续推进普通准备/修复/验证，不新增逐项用户审批；新EDA真实启动以回执为准。主控集中选型，G2前不改生产RTL；正常无墙钟/静默强停、单EDA/资源保护、无后代与禁区保持。

- **2026-10-18当前mission定义：M003联合可布线改造与完整实现验收。** 用户要求“定义成完整详细的mission”；已登记主合同`mission/M003_joint_routability_closure/contract.md`、SM013–SM019及验收矩阵。状态planned，设计尚待归因/四表冻结，本轮没有生产改动、仿真、EDA或新E/R/AT。依赖M002架构及E008已收尾证据，不要求M002先成功；下一技术入口SM013。此前优化/完整实现授权和不变量继续，技术阶段门不增加逐项用户审批；选型集中记录，新RTL必须新综合，不盲目复用旧父图。下方旧合同“唯一C01/RTL不变/不重复综合”仅适用于原E008，不限制M003已明示的联合修改范围，也不自动启动工程。
- **E008终态收尾已完成：** AT004自然route失败，工程14项收尾与A007独立审核均完成，无活动EDA；702396重叠节点/547548冲突网，M002仍未成功。以E008最新三摘要为准，下方“审计进行中”为历史。PDU暂停已解除；原证据、旧冻结包、正常无墙钟/静默强停、单EDA/资源保护和禁区保持。

- **最新最高优先状态：E008/R001/AT004已因布线拥塞自然失败，2026-10-18北京时间05:18:30监督器结束（native1/supervisor1，stop_reason=null，无强停）。最终702396重叠节点/547548拥塞失败信号；完整place/physopt通过阶段核验、9491个C01对象实际全SLR2，仍未合法布通。** 原始status/失败DCP与诊断均保存；此前running摘要因工程代理容量错误未更新，现已恢复A006终态审计/A007独立核验，未启动新AT。PDU暂停已由用户“可以继续了”解除，不重新等待该恢复指令；现有合同内收尾继续，选型/架构/验收变化需主控集中决定，不能按原配置盲目重跑。单EDA/资源保护/正常无墙钟静默强停及禁区保持。

- 2026-10-17 15:14最新实态：E008同C01重试AT002已原生启动，37源/45bbc与144输入核验通过。AT001于13:12在布局前入口属性检查自然失败，修复26例和独立审核通过；旧状态未及时更新及Root续跑衔接现已纠正。主控明确委派同C01常规来源修复的真实登记/连续重试给工程，选型/合同/验收不变；仍正常无强停、单EDA、原保护和禁区保持。

- 2026-10-17最新实态：E006 R006 AT003完整候选比较已自然成功并独立审核，主控选定C01 SwiGLU branch[1]→SLR2。SM012/E008 R001/AT001于04:50:44Z真实启动，执行原单候选合同及有向范围/端口获取补充；3cae入口、35运行源、144生产输入与项目唯一EDA已核。当前尚无新place/route成功结果，最新状态以E008摘要为准；下文较早“未选择/未启动”均为当时历史。正常进程无墙钟/无输出强停，单次停止例外均已使用。

- 本项目根：`/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM`。
- 唯一实现入口：`project/software` 和 `project/hardware`。
- 旧目录 `/home/user/EDA-202/zhuowenjun/ScaleLLM` 是保留源和历史证据，不得删除、移动、改写或清理。
- M001整理和E001快速验证已完成。2026-10-15用户最新授权：先正式综合取得新网表/报告，再适配物理入口并开展布局布线实验。用户随后追加“进行一次完整的implementation”，当前执行合同为mission/M002_ddr_separation_and_timing_recovery/full_implementation_contract_2026-10-15.md（SM007/E003），另有full_implementation_continuation_2026-10-15.md最新补充取消固定墙钟强停，正常推进则持续执行；取代E002停止边界；仍不运行bitstream/GPU/板卡/PPL/ACC，不恢复旧工程任务。
- 2026-10-16最新授权：“开始优化和新的implementation”。当前SM009/E005，执行合同为 `mission/M002_ddr_separation_and_timing_recovery/optimized_implementation_contract_2026-10-16.md`；E003失败与E004分析保持原证据。允许首选两项RTL、功能/入口修复、新综合与完整物理实现；正常进程无墙钟/无输出强停，其他不变量和单EDA资源保护保持。
- 2026-10-16追加授权“火速去查明”：当前SM010/E006，合同 `mission/M002_ddr_separation_and_timing_recovery/slr1_attribution_contract_2026-10-16.md`；只读查询当前DCP的模块×SLR/热点/连接及失败归属，不改生产设计、不重跑implementation。E005已失败结束，原证据保持；仍单EDA且正常无墙钟/静默强停。
- 用户随后授权“查明清楚后进行针对性的优化SLR1 可以让别的SLR区帮忙缓解压力的吗”：E006归因后执行有证据支持的定向卸载与物理验证；后继草案为 `mission/M002_ddr_separation_and_timing_recovery/slr2_input_locality_candidate_contract_2026-10-17.md`，尚未实施。当前正常只读诊断不因查询较慢而强停；此前切换问题现已收到用户明确答复“允许切换这次只读诊断”：仅允许结束E006/R001/AT001并保全证据、真实收尾后切换已审E006/R003轻量入口；后续正常进程仍不强停。
- 用户最新要求“进行针对性优化后开启下一轮implementation 我希望下一次就能成功”：普通适配与完整物理验证已授权，不增设逐项批准门，不承诺一次布通。实测后原SM011/E007输入候选降为探索对照、未实施；E006当前以R004已闭合资源及R005有向边界比较SwiGLU独立分支C01与Down权重重排C02。后继SM012/E008按 `mission/M002_ddr_separation_and_timing_recovery/exact_hotspot_offload_implementation_contract_2026-10-17.md` 准备入口，最多选择一个获实测支持的候选；当前未选择、未启动implementation。真实候选/约束资格和单EDA收尾依赖保持。
- 2026-10-17用户另行明确答复“允许切换本次 R004 诊断（推荐）”：该例外已执行，R004于09:17:59受控结束且数据/144输入/进程/锁收尾已核；其完整cut/时序/UNION未完成保持。R005 AT001于09:19:19启动后因owner辅助函数缺失于09:29:55自然失败；修复包a660已通过完整入口正负对照，AT002于09:34:23启动后因工具内Python缺少_tkinter自然失败；环境修复b330包AT003于09:51:16实际启动并通过原生载图前预检，按 `mission/M002_ddr_separation_and_timing_recovery/directed_candidate_cut_scope_revision_2026-10-17.md` 采完整候选有向边界，明确省略符合资格的外部peer LOAD导出。E008原1d612c65入口已独立核查，同类环境适配同步处理，后继各阶段采用同口径，正式物理验收不变；当前候选未选、implementation未启动。R001及R004的停止例外均已用，不扩展到后续正常进程。
- 保持 Hadamard、ScaleCode 和 format 05 的正确算法；复制完成不等于功能验证、时序收敛或已获得可用 bitstream。
- 四个长期对话是否真实存在，以核验记录为准；模板中的职责说明不代表已创建。

Codex分区名称为「ScaleLLM」，内含「项目主控与架构评判」「工程实现与验证」「研究探索与瓶颈分析」「技术问答」四个独立新对话。用户最新要求已取消此前绑定；不得复制旧会话历史、重新绑定旧代理或自动恢复跨会话通信。当前仅管理分区入口，见agent/work_chats.md和.research-agent/fresh_section_chats.json；旧创建和修复回执仅为历史记录。

- 主控维护 goal、mission、results；工程维护 project、子 agent 记录；研究维护 source；问题由实际负责人维护 question。
- 恢复先从 README.md 首页进入 mission/index.md、project/index.md、communication/index.md、question/index.md，再读当前 goal、合同、实验摘要与审核原记录。首页与各索引由 organize.py 统一生成，不手改生成区；手工维护权威正文后 refresh。详细机制见技能 references/organization.md。
- 每个 SM 可独立审核。重要里程碑、异常、基线失效、全局影响、资源冲突或阻塞及时阶段报告；独立任务继续。任务最终结束后仍提交总报告。
- 写文件不等于通知。活跃子 agent 用实际消息工具通知主控，由主控在用户对话说明重要事项；未配置真实持续运行能力时不声称后台监控。
- 并行有明确依赖、写入边界和资源额度。同一 RTL、摘要或共享索引有单一负责人，脚本锁不保护任意手工编辑。
- 大任务中可独立推进且有并行收益的部分，由当前负责人按 research-agent 自主拆分并实际创建多个子 agent，无需用户逐项分配。每个子 agent 读取同一技能和角色参考，继承当前合同与资源限制，保留他人改动；父 agent 统筹全部层级额度、阶段消息、证据核查及最终整合。agent 并行与重工具调度分别管理。
- agent/model_policy.md 是配置视图；期望配置与实际配置分别记录。用户最新明确设置优先，不默默替换模型。
- execution、verdict、applicability、review 分开。工具失败不反驳方法，功能仿真不代表时序或上板通过。
- 用户指定审核停点必须遵守。合同内的常规修复按已有授权继续，不自动为每一项增设批准。
- 原始运行证据不覆盖；R 是范围明确的批次，AT 是独立具体尝试，改变范围时另开 R。新 mission 合同与子任务放入任务文件夹；历史路径保留。权威规格、代码、工具、约束和数据身份可核查，重要数字链接到真实报告。
- 跨会话消息统一归档为 C 讨论，答复关联原消息；送达、答复、实施、验证分别记录。负责人确认解决范围并附证据后才关闭，不把有回复当作已解决。用户问题另存 Q 记录并引用相关讨论。
- 不自动迁移旧工程、不擅自改变全局接口/验收或扩大预算。工程最终验证与用户审核不能由模板或 bookkeeping 状态代替。
