# ScaleLLM：共享工作约定

三个工作角色：项目主控、工程实验、研究探索。启动时声明本轮角色，读取 research-agent 技能及相应参考文件；用户当前指令优先。

## 当前整理边界

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
