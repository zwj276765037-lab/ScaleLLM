# R004 已闭合成员、资源与 probe 的独立审核

execution：A007 CPU 原始文本复核 completed；R004 全流程仍 running。verdict：两候选的已闭合子集在显式、严格恢复分隔符后相互一致。applicability：当前 AT001 physopt 图的 membership/resources 与九对象 probe；未覆盖未闭合的全 cut、方向时序、UNION 恢复或 terminal。review：独立原始字段、来源身份和闭合回执审核；不是用户验收，也不是候选迁移准入。

机器证据为 [independent_membership_resources_and_probe_review.json](independent_membership_resources_and_probe_review.json)，36523 bytes，SHA256 `0696755244e7f6dc6f7debdd42be799808d2518763329c812dad0c7e34fc4246`。独立脚本在 [A007](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/agent/A007/audit_E006_R004_membership_resources.py)，不导入工程提取器、不读 DCP、不控制进程或锁、不修改工程源。

| 当前图的已测量项 | C01：producer1 | C02：weight_repack |
|---|---:|---:|
| RAW / S / P | 9514 / 9507 / 9491 | 7260 / 7257 / 7257 |
| P 实际 SLR1 / unplaced | 9491 / 0 | 7257 / 0 |
| native CLB / LUT / FF | 1788 / 1890 / 6317 | 1347 / 3348 / 3557 |
| native CARRY8 / F7 / F8 | 25 / 816 / 384 | 12 / 0 / 0 |
| native RAMB36 / DSP / URAM | 6 / 2 / 0 | 0 / 0 / 0 |
| native unique control sets | 36 | 32 |
| touched CLB 与外部 P 共享 / 当前候选独占 | 1776 / 12 | 1339 / 8 |
| P 上实际 DONT_TOUCH=1 | 25 | 24 |

六张表的标题使用 TAB，数据行由源中的未引用字面 TAB 使 Tcl `join` 回落为单 SPACE：membership 为 24 列、physical_members 为 18 列、site_members 为 11 列。独立 Tcl 最小复现已确认。以单 ASCII SPACE 分割并保留所有空字段后，C01 的 9514/9491/33937 行、C02 的 7260/7257/25435 行全部恰好匹配对应列数，无嵌入 TAB。已知生成器恰构造 K 个字段；任何字段内额外 ASCII SPACE 都会增加分割列数，因此此次严格解码可恢复，不需猜测字段。原文件和运行源保持不变；native code 0 本身不能代替这项序列化审核。

独立逐行对照确认：literal root + `/` 选择保持 `[1]` 字面含义；S 只排除 GND/VCC；RAW 名称/REF 与成员表完全双射；P 名称/REF 与物理表完全双射；S→P 的实际 DSP 父映射一致；两候选 RAW/S/P 各自无交集。C01 的两个 DSP48E2 各有八个拆分子单元，site primitive 查询仅返回这些子单元而不返回父名；按实际 physical_parent 覆盖全部 P，不能要求每个 P 父名直接出现在 site primitive 表。

两份 native 资源报告各只有一张 SLR 资源表，实际命令的 exact hierarchy、全部 22 行数值和真实行号与工程 facts 一致。site sharing 按全部 touched-site 原始 primitive 行重新计算；12/8 当前候选独占 CLB 不表示迁移后保证释放，1776/1339 共享 CLB 也不能当作可释放空 CLB。C01 的 6 RAMB36 与 2 DSP site 当前候选独占，同样不证明 SLR2 放置或布线可行。

全部 P 的 IS_LOC_FIXED/IS_BEL_FIXED 为 0；直接 USER_SLR_ASSIGNMENT/RLOC/RLOC_ORIGIN/MACRO_NAME/PBLOCK 值为空。DONT_TOUCH=1 的 25/24 项保留；不能把“工程定义下直接 policy 异常数为 0”说成没有保护属性或完整继承兼容。E008 实际 pre-place 仍需核对祖先、宏、原始/克隆映射和目标几何。

实际 probe 的 NAME、REF_NAME、LOC、BEL、IS_PRIMITIVE 五个 native vector 均长 9，45 条 scalar 与 vector 顺序和值完全一致。LOC/BEL 各有一个空 scalar，仍未发生长度错位。R003 原失败列保持 UNKNOWN，不能将该历史失败归因为 LOC/BEL。

候选支持与选择仍 NOT_ASSESSED。全 cut、正确方向的 cap16 时序、候选相关跨 SLR 端点和实际 terminal 尚未闭合；源端口位宽、整个 attached graph 的跨 SLR loads 或当前 native SLL=0 均不能替代迁移流量及实现结果。

独立审核脚本自身最初两次 CPU 运行失败分别来自“所有 P 父名应直接出现于 site primitive 表”的错误断言，以及 report command 固定行下标；已依据原始 DSP 子映射和带标签的命令行修正。修正前源码和具体失败保留于配套 [harness repair 记录](independent_membership_audit_harness_repairs.json)。没有将审核脚本错误记为工程实验或方法失败。
