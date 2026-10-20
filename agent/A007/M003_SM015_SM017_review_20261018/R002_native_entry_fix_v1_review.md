# A007：正式原生入口修复 v1 与双尝试复用增量无阻断

execution=completed（本子审核）；verdict=supported；applicability=deliverye6feab47 / manifest8c9fb38e；review=source/recovery-entry no blocker，G4 未放行。

45 项冻结源全匹配：原 42 项中 32 不变、10 项入口修复、3 个 helper 新增；13 diff 由原 AT003 归档逐字重建。3 RTL、F4/预算/策略保持。工程201项回归和54源归档已核；A007独立56项定向测试通过（chunk defd78），源码不变；另用原真实 build_identity 做1正5负文本资格测试，确认只允许 implementation-only overlay 的 XDC→TCL 字段变化。

已接受实际query的13120全集/异常拒绝、TCL及绝对helper绑定/成功apply回执、完整INIT脚本保存及严格INIT先于OPT、当前真实日志读取、restore前guard与attempt不增。AT007小图原生机制及完整driver归档绑定已核；正式新图尚未代验。

恢复schema保留 AT003 原生1，复用仅本版23产22用，并要求新尝试原生0、实际重新载入22依赖、selected结构/apply/预算通过；8份旧综合报告明确继承归属。379输入和DCP当前重哈希归因A006，A007核来源记录及消费者代码，不读取DCP。

A006可直接新AT008 recover-synth，按既有授权连续至严格G4；本审核不能启动正式place。TOP01−2.896ns、22049对账和拥塞风险保持。[完整证据](R002_native_entry_fix_v1_review.json)。
