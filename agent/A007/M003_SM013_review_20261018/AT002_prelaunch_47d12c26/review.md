# E009 / R001 / AT002 alias 修复包增量审核

2026-10-18；A007。**该固定修复包可按现有授权直接启动，无实质阻断，无新增用户批准。**

- execution：三处源码 delta、身份/前置及隔离 CPU 重放完成。
- verdict：修复正确区分 Tcl 列表表示与逐元素身份；原生配对资格、canonical census、性能及 G1 待实际证据。
- applicability：AT002 manifest 3773 B / SHA256 `47d12c26baf586e780b104b186df39df22fcdb970bddef4534c66e123ba82402`；同 R001 查询范围。
- review：内部独立增量审核接受；不表示原生已启动或优化有效。

## 核查结果

1. 新包12文件实际 size/SHA 与 manifest 一致，并保存在本目录 source_snapshot。`aggregate.py`、`supervise.py`、`launch.py`、`query_plan.json`、`targets.tcl`及三份合同参考与 AT001 字节相同。top20 排序、16网代表、补充种子、端点/时序边界及资源/无强停规则没有变化。
2. `attribution.tcl` 仅把 NAME/handle 的列表字符串等同检查改为长度及逐元素精确检查；列表表示差异只计数，不影响身份资格。前8个实际配对和所有实际错误配对留回执，真实元素不一致仍失败，错误时 flush。canonical 选取和 segment 闭包互斥检查原逻辑保持。未增加原生查询，也未恢复逐 pin 同步日志。
3. `prepare.py` 定位新 AT002，并新增 AT001 原终态/收尾/观察器来源及旧 PID/start 消失检查。旧 E008、144输入、父DCP、单 EDA 锁和资源检查保留；未覆盖 AT001 运行源和原错误。
4. 从实际修复源提取 alias 函数，在隔离快照运行 `check_cpu.py`：表示不同但同元素正例接受；真实 NAME 错误、数量错误负例均拒绝；原小规模分类/union 对照也通过。实际 exit0，stderr 空，见 `cpu_replay.json`。这是函数实现的 CPU 证据，不是 Vivado 配对结果。
5. AT001 的原生 schema、547548 conflict report 和自然失败终态沿用本轮 `AT001_prelaunch_122178e2/native_failure_review.md`。本次读取工程 terminal_facts、独立保存的 terminal_facts_v2 和 observer_terminal_facts：v2 修正了报告后处理提取，原记录保留；计数与已独立读取的714 B原生 report一致，观察器报告实际工具 exit0。旧失败仍是自然 native1/supervisor1，G1未完成。

## 运行后边界

AT001 未保存失败配对两侧值，因此不把 CPU 反例冒称为该 native pair 的确证。AT002 的首个真实 alias 配对及完整元素资格记录应在实际产出后审核；首次正确运行后再判断 canonical/alias 对账和性能。

AT001 审核中“主组分类覆盖”和“实际代表深查覆盖”分列、原生报告对账、缺失字段/未找种子如实保留、native_completed 不等于 G1 PASS 等边界继续适用。未新增候选、银行或坐标。A006 绑定本固定包/审核证据后可连续执行，无需重做已保持内容的全量准备审核。
