# M003 / SM013 独立审核入口

日期：2026-10-18。负责人：A007 `/root/m002_physical_architecture_review`。主控已通过真实消息转达用户“可以开始进行mission”，并派发本轮审核；该最新授权优先于任务定义时的 planned 文本。实际 E/R/AT、原生启动与完成由 A006 证据另记。

- execution：AT001/AT002 自然终态、AT003 固定修复包/真实启动/自然终态和最终独立审核均完成。
- verdict：AT003 固定查询去重/分类/deep及代表时序证据支持；547548报告精确对账差+22049保持OPEN，优化效果inconclusive。
- applicability：[AT003 固定包](AT003_prelaunch_f0ac0b91/review.md)、[真实启动](AT003_prelaunch_f0ac0b91/native_start_review.json)与 M003/SM013 已审合同。原 AT001/AT002 审核各保留其阶段适用性。
- review：内部独立审核。无 EDA、DCP 读取、生产改动或后代 agent；不新增逐项用户审批。

当前阶段：[G1最终独立审核](G1_consolidated_review/review.md)完成；建议主控限定接受并推进SM014四表与集中候选判断，正式G1范围由Root记录。固定查询569597清单可复算，但547548报告映射/差22049未解释，不作无条件G1 PASS。未选候选、G2未通过。

A007实际代表时序回放session40815 exit0，104 DATA路径和104 launch C/CLK负例通过，4无路径报告单列；原生argv/Command头限制保留。[最终绑定](G1_consolidated_review/final_binding_checks.json)另核审计来源/回执、manifest保留身份及22个非constant未知与deep20534交集0。未重扫3.66GB全端点、未读DCP；真实工程raw audit v3采用已审算法/fixture及实际exit0回执。依赖未知的候选单独闭合，其余设计继续。下文AT001/AT002/AT003准备文字均为历史阶段记录。

历史阶段：AT001 已于 00:53:21.909734Z 自然失败，原生计数/schema 已核，canonical census 未完成；[终态与修复依据](AT001_prelaunch_122178e2/native_failure_review.md)。已实发 Root/A006。AT002 47d12c26… [最小修复包](AT002_prelaunch_47d12c26/review.md)已增量接受，可按原授权直接启动；其[真实启动](AT002_prelaunch_47d12c26/native_start_review.json)已独立核实；原生alias/census及G1结果待测。原准备/启动结论仅保留各阶段适用性。

AT002 最新终态：01:21:12.045955Z 自然失败；前 8 条真实配对相等，第 9 条 XDMA escaped NAME 存在 scalar/list 适配差异。原终态/进程/资源及离线反例已[独立审核](AT002_prelaunch_47d12c26/native_failure_review.md)。G1 未完成，AT003 同范围最小修复准备中，未启动。

AT003 f0ac0b91… [固定修复包](AT003_prelaunch_f0ac0b91/review.md)已独立接受：真实 12 源、三执行源 delta、旧证据/来源保持与实际函数 CPU 正负回归通过。可按既有授权直接启动；真实原生资格/G1 另核。

## 责任和读写边界

A007 只写本目录及 `agent/A007/status.md`、`state.json`；主控独占 mission/results/共享导航，A006 独占新实验/三摘要/诊断脚本。已有历史审核和证据保持。文件变动后的审核以变化内容及受影响语义为界，不重复全量旧日志。

普通同范围修复自然失败后使用新 AT；实质范围变化按合同另 R。当前审核没有停止当前或未来正常原生进程的授权。正常进程无墙钟/静默强停，单重工具和既有资源保护保持。

## 包审核要点

| 项 | 检查及可接受条件 |
| --- | --- |
| 真实来源 | 入口、模块、配置、冻结对象集合、父图和原始报告都有实际身份；DCP 身份由 A006 读取核验，A007 不重读 DCP。运行消费归档源与已审包一致。 |
| 原生失败网集合 | 说明所用真实原生命令/属性和状态值，保存状态分布及返回数量；明确 conflict/resource-congestion 集合与 unrouted/partial/total 的关系，不拿笼统非 FULLY_ROUTED 集合直接冒充 547548。差异保留映射和原因。 |
| canonical/alias | 记录 segment alias 的实际归并依据和一对多关系；不只截短网名或以 driver 名猜 canonical。层次段重复、顶层 port、双向端点、多 driver、未知均有显式去向，不能静默丢网。 |
| 驱动与消费归属 | 先区分 leaf pin/层次 pin/top port，方向定义明确；模块归一规则固定。未知位置与未知 owner 独立保留，不变成 SLR0 或零扇出。源、负载、端点和连接对不混用。 |
| 唯一主组 | 主键为 driver 模块、source SLR、排序去重 load SLR 集合；每 canonical 网仅一个主组，多 driver/unknown 显式桶；按唯一网数降序和键字典序定前 20。consumer/clock-region 辅表可重叠但不累加为全量网。 |
| 全量守恒与覆盖 | canonical 总数、各桶、唯一主组、unknown 数量可对账；前 20 及补充集合覆盖为 canonical ID union，分母为同一已对账集合。覆盖率不是因果解释率。 |
| 有界深查 | 固定 literal roots、80 保护匹配、已知跨 SLR 边界、允许方向/查询终点、字段和代表时序条数；不在循环中递归扩大，新热点另记缺口。全量分类可以完成全部网级记录。 |
| 批量性能 | 属性批取或同图缓存有身份/顺序保证；alias/端点账本缓冲写盘，最终成功和异常路径均有 flush/close；不逐 pin puts+flush，不构造全设计 source×sink 笛卡尔积，不反复全芯片扫描。 |
| 可失败性 | 必须数据不可取得时原错误/缺口有记录；无法确认关键集合不能输出全量 PASS。小规模正负对照覆盖重复 alias、未知、多 driver、分组并列和 union；对照不冒充原生资格。 |
| 运行保护 | 单 EDA/lane、CPU0–7/max8/nice5、RSS192GiB、MemAvailable48GiB/30s、disk30GiB 和 PID/start 身份控制真实接入；无继承的墙钟/静默终止器。 |
| 连续性 | 原生命令、监督器、阶段记录和最终 exit 分开；终态时更新三摘要/审核，不因旧文档 running 重启；原始证据和失败诊断不覆盖。 |

包无实质缺陷时，A007 向 A006 和 Root 明确发送“该固定包在当前合同内可执行”，不要求追加用户确认。原生能力、性能和 G1 完成仍等真实产物。

## G1 到达后的审核

绑定原生来源、运行身份及真实输出；核全量网清单与分组/覆盖守恒，抽查代表 alias/owner/SLR 归属及未知类别。对被用于 SM014 的候选要求关键源、负载、状态和落区证据完整；关键未知只阻塞依赖该未知的候选。仅数据采集成功不得判优化有效、唯一根因已证明或下一轮必布通。

需要核验全部表的守恒时采用有界、单次线性 CPU 复算并先确认工程资源安排；不占 EDA，不扩大原生查询。阶段、异常或终态结论用真实消息交主控/A006；此文件不是后台监控。
