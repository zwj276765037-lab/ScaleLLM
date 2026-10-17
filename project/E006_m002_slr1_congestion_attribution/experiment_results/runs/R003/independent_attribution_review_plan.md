# R003 实际归因独立审核入口

A007，2026-10-17。本文件是阶段判读准备，结果尚未发生；不执行 EDA、不读取旧 676 MB primitive 表，不修改运行中的 Tcl/runner。

工程 A006 的独立 CPU 提取器 `agent/A006/E006_lean_capture/{capture_stage,capture_graph_stage}.py` 负责闭合 query/stage、原始身份、alias canonical 去重及端点与原生统计逐行一致性，输出至实际 AT001 的 `<stage>_closed_stage_facts.json` / `_summary.json`。A007复用该事实包，独立检查生产器、绑定、关键原始行及候选适用性，不另造一套全量提取器。双方已用真实消息确认分工。

| 实际事件 | 独立判读 |
| --- | --- |
| `failure_samples` stage0 | 核40个字面样本/10个node来源及映射，保留不命中和多命中；同canonical别名去重后，检查 candidate driver/load、组外端点、SLR与unknown，区别真实失败日志节点关系与physopt连接关系。 |
| 任一 `hotspot_NWnnn` query0 | 必要时复用R002 `audit_one_closed_hotspot.py` 的已审逻辑作单区候选交集；先证明实际归档lean Tcl及 `NOT_QUERIED` 声明。单区事件不等于UNION闭合。 |
| `hotspot_ownership` stage0 | 核真实10区的集合并等于UNION，按exclusive owner及candidate交集判读；重叠NW不相加，touched sites不冒称可释放sites。 |
| `hotspot_connections` stage0 | 核UNION附着canonical网、每网driver/load与组内外关系；按单driver有已知实际SLR的网报告跨区，其他保留unknown。工程边界事实与失败样本canonical交集是重点抽查项。 |

候选沿用已绑定R002 `audit_input_frontend_candidate.py` 的 literal `classify/selected`：frontend排除cache/bundle，tensor仅input bank/control。名称命中是RAW；GND/VCC常量单列，logical S排除常量；未知父/REF不默认为组外。当前physopt的split DSP或LOC不能冒称E007新图实际P，E007仍须原生父归一、clone对应与硬约束资格。

端点重新按REF+REF_PIN解释，保留原native terminal-only分类以便追溯。DSP.C是算术数据，FDRE.C是clock，LUT.I0仅知逻辑引脚而不能判定data/control。lean未导出IS_CLOCK/真实clock object，不能声称完整clock识别；未知或混合语义网不合并为data。优先复用已审E007 classifier的有证据规则，未识别REF保持unknown。

lean只导出leaf IN/OUT，不含leaf INOUT和top ports；因此零primitive driver不等于无driver，候选相关端点和UNION连接都不是E007完整cut。net/pin数、RTL位宽均不是SLL使用或流量；占用率不是固定窗拥塞。实际热点相交支持候选针对性，未相交限制“直接缓解该窗”主张，两者均不能预言新implementation布通或时序通过。

[实际启动独立观察](independent_lean_native_start_review.json)仅确认新supervisor/native身份、归档源绑定、CPU0–7/nice5、无墙钟/静默强停及单EDA锁归属。加载结束和上述阶段结果须另由实际回执证明。
