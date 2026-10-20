**用户最新管理要求：仅每小时有界分析；取消持续观察、agent驻留等待与每阶段唤醒。AT027及原自动资源保护监督不受影响；本轮不启动新EDA/重试。此前观察/自动连续推进描述仅为历史。**

**AT027已于07:49:43Z实际启动：native378139/start8579293，监督377993/start8579054；48源manifest42dafce3、194archive+current匹配、单EDA/原CPU及资源保护核实。修复改为同call51项真实复位来源/INIT/CLR pin极性与NOT独立root函数强证据，候选独审1614ecce接受；95资格实际通过后复用不重跑，33受影响入口修正fixture隔离后实测通过（首失败日志保留），新增DAG深度/异常清cache/常量引脚正负例闭合。未新综合/改RTL；完整修正版全图/预算/G4/物理尚待。**

**AT026于07:28:49Z自然native0/stopnull完成，7原身份退出/锁空、12归档与4额外冻结输入匹配。原生51端点/3 LUT1 INIT1/3 I0/4组已完整采到；双方FDCE/INIT0及pin_IS_INVERTED0实测一致，cell_IS_CLR_INVERTED空值如实保留。原core361/helper1+1 CLR组与AT025相对层次逐项完全一致；root804与全图807中的core相对804完全一致，实际局部函数均NOT(core_rst_n)。AT025原同网比较失败/native1不改写，正在修正入口的复位语义证明口径。**

**AT026已于2026-10-19T07:23:13Z实际启动，仅对AT025同一原生产者的177MB freshcore补取17+34 CLR和≤16组合节点/64输入/深4的复位来源。native356228/start8420188、CPU0–7/nice5/单锁及原资源保护核实；生产48源未改。4CPU函数13定向负例通过。AT025失败不改写，完整复位资格/G4仍未通过。**

**AT025已于2026-10-19T07:13:04Z自然失败，native1/stopnull/无残留；owner14身份退出/锁空/194archive+current匹配。完整snapshot已生成，实际六源NAME列表17/9/3/807/1/3及clock真实12602组/source/K已由独审checker实测PASS。仅34项helper异步CLR alias集合与core原寄存器不相等导致结构资格失败；预算未执行、G4/物理未过。工程正离线核现有全图reset锥，不盲重综合。**

**AT025独立clock源实证：core/core_clk实际源锚已通过同call对象成员检查，绑定到BUFGCE clkout1_buf/O，实际G000000组12602别名；完整snapshot与六源最终NAME/预算/native0/G4仍待。**

**AT025第二次native overlay apply已成功；snapshot采集已开始，六个非clock独立上游锚已全部实际选中，S/L/R/reset/read/write segment_count=17/9/3/807/1/3。完整最终NAME向量与clock source witness/全图结构/预算/native0/G4仍待，不能把早期选择成功当完整资格。**

**AT025实际阶段：REAL_CLOCK_FAMILIES已出，第二次apply入口attempt2/restore_verify_only0已进入，第二成功回执尚未出现。首apply和open_run完成仍为已核阶段，完整snapshot/预算/native0/G4待。**

**AT025阶段更新：原生第一次overlay apply成功，open_run已返回（45分16秒）；PID/start与冻结manifest/overlay均核。第二次apply及新snapshot/预算/native0/G4尚待。**

**AT025已于2026-10-19T05:17:40Z真实启动：监督274416/start7666717，原生Vivado274532/start7666943，48源冻结、194绑定均匹配、原EDA锁持有与资源保护已核。综合后七源采用已有原生证据支持的独立上游actual net锚；受影响7函数检查通过。未新综合/改RTL；完整新图/G4/物理结果仍待。**

**2026-10-19T02:52:17Z AT024已自然失败，native1/stop=null/无归属残留；本次owner核13原身份已退出、锁空、194冻结绑定及当前源均匹配。失败是综合后S层次端口未保留的入口选择器错误，3RTL/G2未变。22依赖读取、两次apply、80×431 memory和288 helper等partial保留；完整snapshot/预算/G4/物理均未通过。02:52终态到约05:06发现期间通知与续接缺口已记录，旧running摘要已纠正。**

# E011来源与当前方法

当前生产入口已合并effective_memory v2、按实际连通组共享clock采集和采集中逐行spool。48 runtime源manifest16f9523c（旧45/7ed/6e2e及全部旧字节保全）；3RTL、G2及原fresh netlist不变。新增shared/stream/decode三个helper均明确列入实际闭包，原AT00342源→当前48的exact6 additions及entry-only delta已验，不固定旧45数目。

全部core17/payload13120/address34/URAM80 CLK与selected boundary按实际direct net证明组成员；同34address FF/C在helper_pins仅复用精确已有见证，禁止宽泛重复。规范化组表可严格展开原字段；requiredrole缺组、raw fallback、断接、错组、源未知/双源、跨调用缓存均拒收。D raw/C与owner/Q/fullcone及431×80 pin/config/mode/chain/decode规则保持已审v2原义，非clock/data查询不扩展重构。

原AT003外层1、AT018/21/22自然失败、AT020用户授权受控停止/原nativeUNKNOWN/历史监督证据缺口全部保留。AT023真实native0完整时钟采集及来源已闭合。当前AT024使用冻结48源恢复完整后报告，未重跑综合生产者。



---
Published: 2026-10-19T08:12:12.202199+00:00
Publication: Pcbc780434f92483c96f008761d4328f1
