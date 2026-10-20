# AT003 单对象 scalar 属性最小修复独立审核

execution：增量来源审核与隔离 CPU 重放完成，尚未核实原生启动。verdict：无实质阻断，固定包可在现有 SM013/R001 授权内直接执行。applicability：manifest **3774 B / f0ac0b91d8d91703ba34405bdd5a1154da1ff12f9b892b8ba6209ad119812101**。review：独立启动前接受，不代表 G1 或优化有效。

## 核验结果

- 新 12 项固定源身份全部实际核对；旧 AT002 manifest 和 12 源未变。查询计划、targets、aggregate、supervise、launch 和三合同参考字节不变。归档三执行源 delta 已从真实文件独立重建，与提交的 diff 全等。
- `vals` 仅增加单对象分支：原生 scalar getter 后用 `list $v` 原样包装；required-empty 检查保持，没有 unescape、NAME 宽松比较或新的原生查询。别名逐元素、cardinality 和失败回执保持。
- 新 CPU 测试中的 162 字节/two-backslash 值与本审核从 AT002 保存的真实 scalar 字节完全相同。隔离快照执行实际 `vals`、`alias`，exit0/stderr 空；覆盖转义/空白/列表元字符、空集合、optional/required 空值、正常 vector、scalar fallback、集成真实 NAME 差异拒绝和原 alias 负例。详见 [重放](cpu_replay.json)。
- `prepare.py` 仅重绑新 AT 和 AT002 v2 终态；baseline 仅替换三项 prior status/terminal/observer 身份，144 生产输入及其他 baseline/reference 身份条目不变。新 prior 三文件实际核对；DCP/生产内容检查归于 A006 preflight，本审核未读取 DCP 或取得锁。
- AT002 真实自然终态、旧进程/资源与标量反例已[独立审核](../AT002_prelaunch_47d12c26/native_failure_review.md)，观察器真实 exit0 的工程回执也已封存。原失败证据保持。

## 可执行结论与限界

A006 可按既有授权直接启动此固定包，回传真实 PID/start/来源/锁绑定；不新增用户或逐项批准门。后续真实 scalar/alias 资格、canonical census、端点/分组/coverage 与 G1 仍待原生产物；CPU 正负对照不代替它们。没有选择候选、修改生产 RTL 或启动 implementation。

本次无 EDA、DCP 读取、进程信号/锁操作或后代 agent。[机器结论](review.json)。
