# AT018 自然终态与 ADDR 合同独立审核

A007 已接受 AT018 自然失败的收尾证据。失败定位为 `memory_startpoint_names` 拒收 `ADDR_A[22]` 的空 startpoints；具体 URAM cell 和该 pin 的实际连接仍未知，因此当前不接受按位号放宽断言。

- execution：本次有界审核完成；AT018 于 2026-10-18 15:54:39.852665Z 自然 native 1，stop=null，无 owned survivors。
- verdict：终态和冻结输入身份接受；地址空起点原因 OPEN，架构可行性 inconclusive，G4=false。
- applicability：E011/R002/AT018，checks `6e2e0343…` / manifest `7ed07e8c…` / G2 `4424c426…`。
- review：实际报告、闭合副本、源码与只读进程状态独立核查；本审核不代表用户最终验收。

## 终态与原始证据

20 项小证据身份记录均匹配工程包，包括 5 组终态原件/副本、两次实际 apply 成功回执和未被覆盖的启动 runtime binding。45 项当前源共 3614272 B 全部匹配 manifest，三个 RTL 和 G2 保持。七个 tracked PID/start 及 supervisor 共八个身份当前都不在；只读 `/proc/locks` 未见精确锁 `103:02:169247080` 的 owner。A007 未获取锁、发送信号或操作会话。

原生 970 B 错误栈 SHA `b049a742…` 明确指向 snapshot 的 memory input-pin 循环，但没有 cell 名。报告目录没有 selected snapshot、qualification、budget 或 URAM 属性导出；两次 apply 成功不能替代这些证据。AT003 原始 outer native 1 保留。不得将 AT018 精确错误反推为缺少错误栈的 AT017 原因。

监督器记录的峰值 68076539904 B（63.4012 GiB）按终态原值引用，本轮未重扫完整资源采样流。fresh core 177165461 B 仅由 A007 stat；`e51adf50…` 内容身份引用 A006 回执，A007 未读/hash DCP。

会话事实仅承接 A006 回执：observer326 已轮询 session26467 至终态；随后额外 drain 返回 Unknown process id26467。本审核未另做 drain，不写成第二次成功回收。

## 17 位逻辑地址和 23 位物理端口

冻结 resident RTL 第 77–92 行生产分支为两个 81920×128 数组，各自读取 17 位 helper 地址；core 第 277 行明确启用该分支。G2 第 36–49 行保留 34 helper FF、40+40 URAM、实际 ADDR 消费者与级联/读写/响应映射核验义务。冻结合同没有规定物理 ADDR 高六位必定为常量。

当前 Python qualifier 第 125–140 行将 direct drivers 和 startpoints 合并，每片要求自己的 17 个 Q 均被 ADDR_A 消费，排除原 core 和跨片地址。它是按 slice 聚合的覆盖检查，不是每个物理位到逻辑位的完整映射，也没有要求全部物理 ADDR 输入必须出现时序起点。第 194–202 行另检查 A 读/B 写控制常量和 80 项 URAM 配置清单。这些实现事实不直接授权删掉 Tcl 的非空检查。

本机 Vivado 2025.2 的 `data/verilog/src/unisims/URAM288.v`（203045 B，SHA `83e1c721…`）提供下列器件模型依据：

| 模型位置 | 已确认语义 | 当前设计仍需原生确认 |
| --- | --- | --- |
| 95–100 | ADDR_A/B 与 CAS_IN_ADDR_A/B 均为 23 位 | 实际 full cell/pin 和净表 |
| 3300/3312 | 内部阵列索引取有效地址 `[11:0]` | 哪些 local Q 实际驱动这些位 |
| 3184/3200、3217/3233 | 有效地址 `[22:12]` 经 SELF_ADDR/SELF_MASK 参与译码 | 当前 MASK/ADDR 值、动态/常量驱动、容量覆盖 |
| 2250–2264 | MIDDLE/LAST 在 REG_CAS=FALSE 时取 CAS_IN；其他情况由 IREG_PRE/REG_CAS 选择寄存或直接地址 | 当前级联属性、实际选中入口、同片级联连通性 |

因此器件允许部分地址译码位为常量或被 mask 忽略，也允许级联节点选用 CAS_IN 而非直接 ADDR。但这些是有条件的机制，不能据参数默认值或 17→23 宽度差认定本次 `ADDR_A[22]` 合法。未连接、驱动未解析、查询错误与合法常量必须区别。

## 后继窄诊断的必要证据

1. 绑定 fresh core / 当前冻结来源，核完整 80 URAM 名单；导出精确 full cell/pin，不能从旧栈猜测出错 cell。
2. 对 ADDR_A/B 导出 pin 对象数量、net/segment 完整身份、全部直接 driver pin/ref/常量值、all_fanin 原始结果及返回状态。空集合与工具错误分别保留。
3. 导出实际 CASCADE_ORDER、IREG_PRE、REG_CAS、SELF_ADDR/MASK、RDB_WR 与相关 enable；按实际选中入口追踪 CAS_IN_ADDR 的同片连接。
4. 将各片全部 17 个 own local Q 映射到实际被消费的物理位和级联路径，保持写地址语义，排除 core/cross-slice 读地址。未解析的有效输入继续失败；仅对实际常量/未选入口证据充分者考虑限定处理。

A006 可按既有授权准备有限 fresh-core 诊断，不需原样重复整个长入口。实际诊断或修复候选由 A006 直接 followup 本 A007 续审。TOP01 −2.896 ns、G1 差 22049 与完整 G4/物理验收均保持 OPEN。本轮无 EDA、生产修改、DCP 内容读取、进程控制、GPU、后代或新测试。

机器结论：[review JSON](AT018_terminal_and_address_contract_review.json)。逐项核验和原厂源码摘录：[verification JSON](AT018_terminal_and_address_contract_verification.json)。
