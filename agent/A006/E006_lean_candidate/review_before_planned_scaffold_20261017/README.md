# E006 lean_candidate：已准备，尚未执行

当前AT001继续运行。此目录与原4个冻结源分离，没有运行EDA、发信号、改生产或改原归档。入口只做过Python AST、Tcl `info complete`和收尾外部身份分支的有界CPU核查；未试跑任何Vivado API。

## 具体入口

原会话真实终态、独立输入/PID/start/锁/资源收尾，以及用户明确允许替换这一正常只读查询后，由主控保存真实决定记录。实际authorization JSON必须包含`execution_authorized: true`、`decision: allow_readonly_lean_replacement`、真实决定文件的`decision_evidence`身份和原AT001真实`prior_terminal_status`身份；若原尝试受控中止，还必须注明`approval_kind: user_explicit_controlled_stop`。这里没有创建授权回执。

随后使用[独立launcher](launch_detached.py)，传入该实际授权文件：

```text
python3 /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/agent/A006/E006_lean_candidate/launch_detached.py --authorization <实际决定和原终态身份JSON绝对路径>
```

它仅对应新的`R003/AT001_lean_physopt_attribution`和`m002_E006_R003_AT001_lean_physopt_attribution`报告目录；目录均尚未创建。不复用AT001原目录。新wrapper再次检查原所有PID/start已退出、单EDA FLOCK、144输入、同原physopt DCP、原4归档源、14外部目标和17项闭合复用产物；没有相应决定或原终态时拒绝准入。

## 数据覆盖

| 范围 | lean处理与解释 |
| --- | --- |
| 全设计primitive/owner/site分布 | 按同DCP的原676MB闭合导出和已审核source身份复用；不重新枚举2,204,250个primitive。 |
| 原生global及首4owner资源 | 精确复用已关闭报告、回执快照和hash；scope修正与原文件都保留。 |
| 40失败net与10node | 优先做原字串literal exact查询、完整primitive IN/OUT端点；10tile实际GRID/SLR及NW成员关系。缺席/多对象/空SLR明确记录。 |
| 10热点和去重UNION | 实际device tile→site映射和region→sites→primitive选择，完整NAME/REF/LOC/BEL/owner/SLR；保存真实site/tile/SLR表，验证per-region union等于直接union-site选中的primitive集合。 |
| 热点连接 | 保持全部UNION附着完整canonical nets和全部primitive leaf IN/OUT端点、owner×SLR/类别矩阵。仍不是全设计net census或整个SLR2候选cut。 |
| 其余原生资源 | 最后仅9个单exact hierarchy报告（core inclusive；DDR0/1的MIG、SMC、slice各自；PCIe；debug），禁止primitive余集作为utilization输入。 |
| 明确保留缺口 | 不查询exclusive core_other/interconnect remainder或热点大leaf集合的原生LUT/FF资源。CPU primitive/站点/BEL占用单独报告，不伪造native LUT，也不把占用当拥塞。 |

阶段顺序是`failure_samples → hotspot_ownership → hotspot_connections → exact_hierarchy_resources`，每query/stage自然关闭即交付，不等连接全部完成才给热点事实。失败样本前的必要region/union membership准备只查询真实tiles/sites/cells，不做utilization报告。

## 所需动作与收尾

1. 用户未明确允许切换前，原正常会话继续，不根据耗时或静默停进程。
2. 获明确决定后，只能按实际PID/start受控结束本任务supervisor，由其既有guard清理原生树并保存真实终态；不能把部分报告称闭合成功。
3. 原wrapper已知`new_peak_sources`未定义错误保留。原生退出、中止原因、wrapper错误与独立输入一致分别记录；独立复核144、原DCP、14外部输入和4归档源，并核原所有身份退出/锁释放/资源。
4. 再由实际授权文件准入新AT；同CPU0–7/nice5/max8、RSS192GiB、MemAvailable48GiB30秒和disk30GiB保护，正常进程仍无墙钟/静默强停。

新wrapper已使用真实绑定的`external_inputs`执行收尾检查；[有界CPU核查](bounded_post_integrity_CPU_check.json)以实际14项全匹配、内存中错误期待hash被拒绝、144输入和17项复用产物不变核查该分支，没有历史全量回归或EDA。原4归档源保持原身份。

重开同DCP有此前579秒加载成本；这里去掉当前已观测高成本的primitive-list utilization和重复全量primitive导出，但完整canonical连接仍可能较长，没有可靠总ETA。原生热点LUT缺口与未覆盖候选边界不能因切换而隐藏。
