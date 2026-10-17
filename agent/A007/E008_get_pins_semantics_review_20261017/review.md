# 完整 leaf 查询的本地 API 语义核查

结论：**无法凭现有本地文档证成以单个 canonical/top/parent 网段代替全部 segments 的等价性。保持 E008 固定 b59 源码与当前 R004 运行。** 本次只读源码和安装目录文档，没有启动 EDA、执行 native 查询、额外扫描图或控制进程/锁。

execution：有界核查 completed。verdict：替代查询的完整性 UNKNOWN，性能收益 NOT_MEASURED。applicability：Vivado 2025.2 本地 API 文档和当前冻结 R004 inspector。review：A007 独立核查，机器证据见 [review.json](review.json)，9270 bytes，SHA256 `2a6e82ca21850ed18405543f41f83d39bc52c0d797d034c96132d9bab17c8a45`；七份小文档原文和完整身份一并保留。

| 选项 | 可证事实与限制 |
|---|---|
| 当前 `get_pins -leaf -of_objects $segments` | [get_nets 文档](man_get_nets.txt:113)明确 `-segments` 取得跨全部层次的所有网段；[get_pins 文档](man_get_pins.txt:67)定义 leaf 为 primitive 或 black-box pins。 |
| 单个当前 canonical alias | 当前源码的 canonical 是排序后第一个 alias，只作标签；不是 native 最高层或 driver 网段。[get_pins 文档](man_get_pins.txt:99)没有保证从任意一个网段能跨父层和兄弟层获得与全 segments 一样的完整 leaf 集合。 |
| native top/parent 网段 | [get_nets 文档](man_get_nets.txt:98)分别定义 driver leaf 所在段和最高层段，却没有给出其 leaf 查询与所有网段查询等价的承诺。不能借 parent 假设忽略无 driver、多 driver 或 INOUT 情形。 |
| 全 segments 直接取 pins，再过滤 `IS_LEAF` | [pin 属性文档](class_pin.txt:43)列出 IS_LEAF；此法在通常连接模型下是合理候选，但本地文档不足以证明所有黑盒、层次、复制或未知对象情形与 `-leaf` 精确等价，也没有证明更快。仅为条件假设，不修改源码。 |
| fanin/fanout、clock 或 register 域替代 | [all_fanout](man_all_fanout.txt:4)是网络遍历，timing endpoints 选项另有语义；寄存器时钟域也不是同一电气 net 的全部连接对象。不能替代完整 driver/load/INOUT/top/unknown 端点导出。 |

当前实现已经用 visited 在同一候选内跳过处理过的 aliases；尚无证据说明一次 `get_pins` 内部是否对每个 alias 重复展开。因此不能从 12550 个 alias 或 `all_registers` 返回的 967038 个寄存器对象推导重复次数、canonical leaf 数量或复杂度。native `FLAT_PIN_COUNT` 的单个计数同样不能证明端点 NAME/kind/direction 集合相同。

冻结 inspector 的 157–160 行在 segment 导出后、首条端点输出前依次执行 `get_pins`、`get_ports`、`get_cells`/ensure_cells 和四列 pin 属性查询。文件暂不增长不能判定具体慢 API。主控随后实发 A006 的 00:34 观察：C01 端点表已从 5799936 bytes 增至 69103616 bytes，已越过该区间；本次审核没有独立测量这些运行数字，完整 cut 仍未闭合，性能归因仍 UNKNOWN。

现阶段不引入替代查询、不减少端点或 top-port 范围、不按推测添加查询或重跑。若未来实际提出更换，需要在相同固定图上以完整对象及属性集合确认等价，再实测成本；这只是证据要求，本记录不启动或要求额外实验。
