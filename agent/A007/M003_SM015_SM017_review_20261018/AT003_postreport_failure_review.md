# AT003后报告自然失败：两个新M003入口缺口

A007独立核原件：AT003于06:12:18.758871Z自然native1，stop=null、survivors空、三RTL不变；23个实际synth目录均有end且无error。已记录的进程身份均不再存活；不读取或哈希DCP，不把外层失败改记为成功。

正式M003 XDC两次解析各报6条Designutils20-1307：file/info/source及`::m003::apply`不受该XDC上下文支持；实际日志没有apply成功marker。随后`m003::snapshot`的宽`parent_*_r_reg*`查询误收入`parent_count_r_reg[0]`并自然失败。两项均属新M003 native资格缺口，与旧constructor27条告警独立；G3b CPU/Tcl注册不构成实际生效证据。

最窄修复限定在collector和约束执行入口：head/tail家族精确全集13120bit、重复/漏项/replica/count负例保持；正式加载采用原生支持的Tcl或纯XDC边界，并实核成员/池/属性/成功回执。恢复检查必须在任何reapply前核checkpoint已有约束。3RTL、G2、区域/预算/策略保持。

Root已明确允许按实际消费语义复用本次同源23产物。须工程原生23产22用身份和未变综合消费源/参数/工具作依据，后继新AT资格/预算独立成功；旧status1、原log及379输入保全，不能伪造原AT通过，也不复用旧E005父图。新图/G4/物理仍未接受。[逐项审核](AT003_postreport_failure_review.json)。
