# M002 / E006 R006 / E008：完整 top-port 反向索引获取补充

用户针对性优化及下一轮完整 implementation 的授权继续有效。本补充是同一候选完整有向边界覆盖下的原生获取协议变更，准备完成不等于新运行启动。当前 R005 AT003 正常运行，原 b330/da34 及全部合同和证据保持。

## 唯一变更与权威规格

保持[有向候选范围修订](directed_candidate_cut_scope_revision_2026-10-17.md)的 candidate_directed_cut_v1 逻辑覆盖、C01/C02精确范围和全部时钟/复位/常量/unknown/INOUT/top端口及方向时序。仅替代原详细审核要求的每候选网 get_ports -of_objects 全segments 原生调用和 ALL_TOP_PORTS 收据获取方式，采用完整原生端口全集、逐端口全部附着网及完整segments、端口实际附着网组的全量原生反向互查，再对候选完整segments精确投影。

权威细则为[A007最小原生资格](../../agent/A007/top_port_projection_semantics_20261017/minimal_native_qualification.md)，12224 B / SHA256 `11e2aad030dd98a04d1fafd8fe98cc99fb01e1b1a6568cb0bc3aa8f702de67c0`。其第0节明确旧条款替代范围，第1–7节全部适用。不同设计阶段/point分别建立和验证索引；只读 current_instance . 必须实际为top，不在collector中默改上下文。

acquisition_mode=NATIVE_PORT_REVERSE_INDEX_V1 与 schema_version=top_port_reverse_index_v1 单列。TOP_PORT_INDEX_JOIN 是真实纯计算，不伪造旧原生 get_ports 调用；validator从全集/每端口连接/完整闭包/原生互查和实际参数重算。字面端口名、bus/secondary和未知方向保留，不能按名字或位宽猜测补全。无端口候选网的空投影必须建立在完整原生库存与互查资格上；缺文件或查询失败不是零。索引网不得扩入原候选网络或时序范围。

任何完整性错误自动拒绝该阶段，保留完整错误；原包可用于明确的新尝试回退。常规适配与受影响回归沿用授权，不新增人工批准门。旧逐网查询覆盖的原始证据和失败状态均不改写。此前“成本小”只是设计估计，当前具体慢API仍未定位，性能改善尚未实测。

## 批次、依赖及后继实现

新R006单独登记获取协议；仍使用同一E005 physopt DCP、144冻结生产输入、C01/C02及既有闭合资源/热点/失败样本。已有成员证据按原身份引用，实际新图的资格仍自动核验。R005正常完成则优先其真实结果，不为替代准备拖延选型或既有da34实现入口。

R006仅在R005真实终态并完成输入/PID/start/唯一EDA锁收尾后启动。若R005仍正常，任何受控停止都需要用户对此次R005 AT003的明确许可及具体已核准备包；原R001/R004停止例外已使用，本补充不授权停止。没有许可时当前运行持续。

E008若采用新获取入口，实际绑定同时包含[原E008合同](exact_hotspot_offload_implementation_contract_2026-10-17.md)、原有向scope、本补充、新manifest及真实选型/前置终态证据。pre-place、place、physopt、route每阶段独立重建索引；父恢复、80保护、真实RAW/S/P、物理父/宏/祖先约束、hard/nonexclusive/non-routing-contained SLR2 Pblock、全部实际P落区、完整place→physopt→route、正式setup/hold/PW/DRC/CDC/reset/IO和合法布通验收全部保持。至多选一个实测支持的候选，不预填支持或承诺布通。

## 责任与资源

A006唯一EDA及源码/运行证据负责人；A007集中核验受影响语义与实际结果；主控负责协议、真实绑定、登记和摘要。最多三个活跃agent、无后代，保留他人改动。当前运行与替代准备分离，不热改冻结源。

单EDA、CPU0–7/nice5/max8、树RSS192GiB、MemAvailable低于48GiB持续30秒和磁盘低于30GiB的原保护保持。正常进程无墙钟/无输出强停。旧工程严格只读，RTL/IP/ABI/数值/时钟不变，无bitstream/GPU/板卡/PPL/ACC。
