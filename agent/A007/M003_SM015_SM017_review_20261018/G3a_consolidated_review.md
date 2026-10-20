# SM015/G3a 独立合并审核

A007接受当前选定 M2+A3+C-P1 版本的局部RTL实现/集成范围，G3a没有未解决的局部功能阻断。工程继续完成SM016/G3b联合回归与正式约束入口检查；两者齐备且独立无阻断后按Root既有连续授权直接新综合，不需要重新派发或新增用户批准。

G2绑定仍为`4424c426…`；生产MLP `5829f33f…`、resident `55f3e8ef…`、core `672d37c9…`。完整身份和七份独立审核绑定见[G3a机器记录](G3a_consolidated_review.json)。

| 范围 | 已独立核验的实际证据 |
| --- | --- |
| 源码与语义 | 三原件/变更边界、81组/13120bit精确映射、1024组合CE/D方程；核心控制及原算法不变。 |
| A3 helper | 实际UNISIM LUT2/3，131072次进位/回绕、8个S/L/R组合、保持/异步reset。 |
| M2 parent | 旧/新parent逐字抽取，3000随机周期、完整head/tail、push/pop/full/no-credit、双支原子接受；此项明确branch ready stub。 |
| M2真实分支 | 真实完整branch/kernel和独立整数期望；production TILE_W9与兼容default TILE_W2分别native测试，均DT4/DG448；两phase各2048事务，II1/1/1，2304lane、42stall检查及in-flight clear。 |
| A3全容量resident | 实际mode1/default0对原版与独立scoreboard；81920地址外口读写、old-word碰撞、stall/token/计数、S/L/R/abort、非法81920/131071不混叠、legacy X侧带。碰撞日志仅支持≥100，不记推算318为实测。 |
| 实际cohort metadata集成 | 完整core/frontend/resident展开；真实A/双helper/pending/NBA/侧带/标签/存储，302消费、303请求、300stall、4clear组合；跨127/128标签、launch+R后置NBA、abort-only及异步reset通过。86输入/93预归档逐项实核，native/launcher0、无stop/survivor，finish15201ns。 |

最后一项是定向集成：force仅7个environment/state/preload/ready控制，未force原地址、helper、pending或存储状态；不冒充完整板级/DDR端到端。完整81920覆盖由resident独立测试提供。六项已接受native均绑定同三份RTL/G2且真实闭合，无正常进程强停。

失败证据保留：AT001 helper原生PASS后相对入口校验失败；AT002 core原生打印含数值的PASS，但缺launcher要求的独占行marker，整体failed。AT003仅补一行PASS display，原RTL/期望/断言逐字不变；旧原件与失败状态均有归档。工具/入口失败不反驳架构方法。

G3b尚需选定版联合算法回归、正式overlay注册与来源/角色/保护/restore正负例；不能以此G3a替代。SM017/G4再验真实新图、40+40URAM/RDW/cascade、81CE、34FF/自身增量锥、预算、控制集/时钟/硬约束兼容及C01新物理成员。SM018实际setup/hold/合法route另验；TOP01−2.896ns未直接处理、旧差22049 OPEN与拥塞风险均保持。

execution=review_completed；verdict=局部功能实现/集成支持；applicability=上述精确版本与测试范围；review=A007独立建议Root接受G3a，非全局/用户验收。A007未启动EDA、读取DCP或操作进程/锁。
