# M002 / SM007：完整 implementation

用户于2026-10-15收到E002布局超时报告后明确要求：“进行一次完整的implementation”。本合同落实该新指令为E003，取代E002本轮“不再place”及place/route各两小时的停止边界；E002原失败终态不改写。

## 目标与顺序

从当前已验证的新综合网表和完整debug/pre_place检查点开始，完成实际place_design、独立phys_opt_design、route_design，取得最终DCP、时序、route_status、DRC、资源与拥塞报告。完整implementation指物理流程完成，时序是否达标独立判定；bitstream、板卡、GPU、PPL/ACC仍不在本轮范围。

1. 核验E002/R001/AT002正式综合339输入/45 DCP路径及未变设计身份。复用E002/R003/AT008完整debug_materialized DCP及pre_place/POST、AT012已验证恢复行为，不重复不变的综合、OPT或debug生成。AT009部分布局无检查点，不能继承。
2. 实际恢复后执行必要live sanity、时钟/约束及原生DRC，再完整place；成功即保存完整DCP并取得阶段报告/检查，继续独立physopt及DCP/POST。真实成功父链通过后自动route并保存最终DCP/报告。
3. 一次默认物理策略，不循环换seed或追加策略搜索。常规脚本、查询、解析及入口错误按授权连续修复并做受影响验证，不新增逐项人工批准。报告失败时保全已经完成的DCP，从合法完整点补缺失阶段，不重复已完成命令或伪造原成功。

## 冻结设计与诊断范围

VCU118 / xcvu9p-flga2104-2L-e / Vivado2025.2；core100MHz、DDR UI200/200MHz；Attention→DDR0、MLP→DDR1。Hadamard、ScaleCode、format05、接口/ABI、S24/S32、舍入、golden不变。唯一实现入口project/software及project/hardware；旧目录`/home/user/EDA-202/zhuowenjun/ScaleLLM`只读保留。

沿用[前合同](implementation_contract_2026-10-15.md)已有证据的诊断准入：零未知黑盒、内部时钟与约束覆盖、有效时钟关系、资源合法性和真实工具错误检查。精确8条reset Critical CDC仅作诊断分类，正式reset/CDC/重汇合与事务安全仍OPEN。物理优化后的实际图变化须按本轮证据判断，不假设旧tuple不变，也不自动扩展为无关全系统验证。

允许负setup/hold/PW候选进入诊断route，真实FAIL原样报告，时序收敛不作为route启动前提。USER_SLL_REG、DDR1 BUFCE_ROW上限、高扇出优化跳过等已有告警不自动阻塞，也不自动豁免。不得通过无依据false path、放宽周期、强制LOC/Pblock、删属性或改IP/RTL绕过问题。实质架构/接口/时钟/数值变更交主控集中评判。

## 新预算与停止条件

调整依据：用户新指令明确要求完整implementation；AT009在恢复准备实减31分21秒后已完成全局/细化布局，但约107分31秒剩余窗口仍不足以完成布局后时序优化，停止原因仅为时间上限。预算为成本上限，不保证完成时间。

- place/physopt连同恢复、POST共12小时；route连同恢复、POST共12小时。总物理墙钟24小时，从E003第一条EDA实际启动计时，包含期间修复和间隔。新AT不得重置阶段或总预算，每次取所属阶段余额与总余额较小值。
- 以显式E003授权profile实施，冻结本合同和用户指令身份；E002默认预算与原失败不变。不能靠未核env标志绕过来源、完成父点和fresh guard。旧single_bounded_restart政策仅对E002有效，本轮新授权在实际记录中明确区分。
- 重工具最多1条，A006唯一执行；8 logical CPU/8线程、nice5、进程树RSS192GiB上限。MemAvailable低于48GiB持续30秒或磁盘可用低于30GiB时停止本任务进程组并保存证据，不触碰其他项目。
- 每阶段真实监督和deadline，完成后立即继续依赖阶段。日志暂时无输出或普通warning不自动中止仍在计算的任务。真实fatal、输入身份失效、容量/合法性或资源保护触发则定位，普通修复可在同一剩余预算内继续。
- 无新可检验原因的重复失败不无限重跑，总上限到达保全实际完成范围和缺口，不伪称成功。不安装上轮仅静态审核、尚未验证的missing-physical候选；若确实出现新的完整物理恢复点及补阶段需求，再最小适配和受影响验证。

## 所有权与证据

主控维护goal/mission/results、E003三摘要、共享导航及资源协调。工程A006（内部m002_build_verify，期望gpt-6.1-sol/xhigh）唯一写生产构建/检查/测试，拥有E003协议、R001入口核验、R002 place/physopt、R003 route、硬件实际results及自己的agent台账。A007（内部m002_physical_architecture_review，期望gpt-6-astra/xhigh）只读评判，独占E003/R004/architecture_review.md和自己的台账。实际模型未独立验证，不将期望冒充实测配置；不重绑长期旧会话。

总agent并发最多4含父，禁止再分叉；只读审核与工程可并行，双EDA禁止。保留他人改动，生产输入运行前冻结，运行中不热改。新E003及每次AT保存源/输入/工具/约束、命令、起止/退出、PID身份、资源、日志、DCP/报告及父链。E002原始证据不覆盖。

重要里程碑、异常、资源冲突和终态实际消息通知父，父在用户对话报告；不虚构完成百分比，不声称未配置的后台持续监控。普通修复不逐次制作审批包。

## 验收与交付

执行完成要求place/独立physopt/route真实成功命令、完整阶段DCP与POST及来源链；最终route_status核真实完成率、未布通/冲突网络及DRC，不以文件存在或exit0单独替代完整结果。

时序单列每阶段WNS/TNS/WHS/THS、失败端点、WPWS/TPWS与实际规则类别；分析关键路径、clock skew、逻辑/布线贡献、SLR资源与拥塞。缺失字段标明未取得，过程estimated timing不替代阶段报告；正slack也不关闭未覆盖功能/reset/CDC或板级项目。

主控结合工程原结果和A007阶段审核整合交付，区分执行、技术结论、适用范围及用户全局验收。本次目标是一次完整implementation，不保证一次即达成全部时序及系统验收。
