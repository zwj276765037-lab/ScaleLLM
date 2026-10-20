# E011：M003严格原地址入口修复后原生验证

G2 M2+A3+C-P1、3RTL、81CE/13120payloadFF/23CR与A3控制/80URAM、固定预算与策略保持。当前45来源manifest5b307ca7，仅checks083为本次生产delta；旧源保全e717。原地址选择器严格保留17位完整/唯一/type/scope要求，仅排除AT016实际测得的两个精确CARRY8邻居。

源候选A00762d62265与实际应用资格fb6cff77均已通过；62项受影响回归全部通过8.691s。AT017同R002 recover-synth实际11:31:39.167075Z启动，191归档与原23产22用新综合来源绑定。

新快照序列化候选1b448730在独立目录完成：checks10b58b3b/tests63975439，collection_property仅用于集合字段，非空原样读取，required scalar/count/pin_net及Python资格器不改。snapshot wrapper保全errorcode/errorinfo后原options重抛；同包处理源码必空的非ADDR memory startpoints。生产暂未改，原45来源083/5b保持。

v1经A007c308指出payload D/Q等字段原隐含非空不可放宽，未获接受；v1全部字节与CPU结果保留。v2进一步收紧，仅PBLOCKS及memory startpoints，ADDR显式非空，其余原调用全回退，checks6e2e0343/tests907fc7e7。

---
Published: 2026-10-18T13:04:48.671435+00:00
Publication: P26c475149393427c88b6bd0849e19fdc
