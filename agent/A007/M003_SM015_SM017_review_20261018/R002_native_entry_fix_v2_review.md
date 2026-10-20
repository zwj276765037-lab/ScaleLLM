# A007：v2 FILE_TYPE 转换后 policy 恢复无阻断

execution=completed；verdict=supported；applicability=delivery7fde81f7 / manifeste90400dc；review=source-entry无阻断，G4未过。

45源中仅recover Tcl变化、其余44同v1，diff逐字重建。独立读取AT008保存XPR确认TCL的UsedIn包含synthesis/implementation/simulation；原AT003真实身份为XDC:0:1。v2在type后重申原三项policy，记录前/type后/policy后原生属性与synth STATUS/PROGRESS/NEEDS_REFRESH，不清stale或放宽原资格检查。

工程57项回归及49绑定原/副本核验，A007只重放本次新增policy转换Tcl行为测试，exit0；其余56沿用v1已审源码/测试。三RTL/F4/预算/策略保持，可直接AT009继续原生，实际graph/apply/budget和严格G4仍待。[完整证据](R002_native_entry_fix_v2_review.json)。
