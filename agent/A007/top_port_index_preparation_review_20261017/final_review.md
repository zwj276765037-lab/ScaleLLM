# R006／E008 完整端口索引最终准备包：集中独立审核

准备源码与受影响CPU组合审核通过，**当前没有实质未解决的源码准备缺陷**。适用于R006 manifest `1425da5b04aeba35799efb48a202e438492619d5010aa7554e5511bfdc477de4`（18742 B）和E008 manifest `dcc64a59876e46fa75309cc3bf963cc545e7e4d144caa8c773ce08b27a97a78c`（13466 B）。没有启动新原生运行或物理实现，不预填索引原生资格、加速或布通收益。

execution：本次集中审核完成。verdict：准备包在既定同覆盖协议下可供实际绑定使用。applicability：上述精确双manifest与最终`top_port_evidence.py` SHA `e2aa22376c16e523bb4c32fd79f62dffcdcf48d0d7af0fa67ff099dfbf374de9`。review：源码准备接受；每个实际图的自动资格、真实前置终态和候选选择仍按合同执行，不新增人工审批门。

完成的核验：

- 双manifest分别62／48个身份条目全部重核，实际`verify_preparation`／`verify_manifest`均返回成功。原scope和新acquisition补充强绑定，E008原合同及实际候选/前置终态绑定保持；四个共享collector/validator模块在R006与E008逐字节一致。
- 固定受影响实际collector、原owner/helper及validator在A007快照独立重放：最终16正例、16反例符合预期。新旧采集器在同一有限native图的16情形共112份端点、候选网、local mapping、alias与方向timing scope账本逐字节相等。
- 另对实际collector执行4个独立正例：可选metadata不支持、压缩向量触发真实scalar回退、MIXED/INOUT原样保留和控制情形；cut/timing validator均通过。7个实际native mock错误均自动拒绝且无cut closed：非root、邻接报错、闭包冲突、互查漏/多端口、metadata报错、UNCONNECTED矛盾。仅mock原生与空间/clock查询，未替换实际owner或采集/验证helper。
- 实际E008 common＋hooks＋collector＋adapter在A007目录完成32个pre_place/place组合回放。真实P投影保留，literal P原件不改，后续index身份变化被拒绝。E008 adapter仅`directed_validation_projection`增加3个索引原始证据依赖；parent、成员、祖先约束、origin/copy资格等未变。共享adapter除cut接入外，其余16个函数AST保持，方向timing与cap16沿用原验证。
- 全端口索引与候选网集合分离，完整bus/secondary/断开/多组/unknown库存、每port全部连接、全部alias和每端口网组原生互查均由validator重算；JOIN记录纯计算和真实epoch，未伪造旧ALL_TOP_PORTS原生命令。

本轮发现的唯一实质缺口是INDEX_CLOSED绑定验证可被删减源码清单或换成无关输入文件绕过。两项独立反例先在CT002实际被接受，原反例与快照保留；最终修复强制完整实际collector/validator身份列表和`index.input_path`实际输入身份。最终独立正对照通过，原两反例分别被正确的source/input绑定校验拒绝，见[最终反例结果](final_provenance_mutations.json)。没有用新结果覆盖初轮问题。

R006运行入口要求当前R005真实terminal/status/facts及所有既有PID/start闭合，沿用单EDA与原resource guard。专用停止helper仅作源码审查：正向限定当前attempt、supervisor PID/start、实际新用户decision三字段和具体操作；显式执行旗标前不发信号。**本次审核不是当前R005停止许可，未调用helper或任何信号/锁操作。** 若当前C02先完成，优先其实际结果；R006不因准备完成而成为额外必跑项。原b330/da34保持，E008采用本新包时主控必须绑定上述dcc64精确身份。

新入口的native bus/secondary对象语义、完整索引和性能仍须在实际阶段自动核验；CPU mock不是原生资格。各E008阶段重新建索引，正式setup/hold/PW/合法route、保护和资源验收保持。C01真实cut/timing已另行优先审核并实发主控，C02完整对照与选型待实际证据。

核心证据：[最终双包身份与真实只读verifier](CT006_final_identity_and_verifiers.json)、[最终完整组合](CT004_source_snapshot/CPU_checks/A007_final_provenance_replay/results.json)、[新旧同图112账本比较](same_graph_semantic_comparison.json)、[E008实际32组合](E008_final_actual_phase_replay/results.json)、[独立native分支验证](independent_native_cases_validation.json)。初次快照测试因A007输出父目录尚未创建而失败的记录亦保留；创建测试输出目录后完成重放，该准备失误未归因给工程源码。
