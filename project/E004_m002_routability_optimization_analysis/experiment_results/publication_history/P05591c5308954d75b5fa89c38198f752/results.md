# E004：阶段分析结果

新原生top50证明Attention双wave的10根capture_index位扇出6170–6174，activation_wave6163；MLP四控制网8201/6192/6145/4652。首轮候选已收敛为input两wave48个固定slot译码边界与MLP32个output CE副本，同拍/原接口；新增物理收益尚未验证。context64边界和S32-only浅历史替换分别待物理证据，S24深2替换会增加CE端点，宽接口/存储复用另有协议风险。

已有48个布局拥塞窗口Combined LUT最高34%，Level6仅6–16%，全局关闭LUT combining无首选证据。control-set BEL loads1089753已精确复算，不等于FF数；原SRL实例按物理LUT一对一的估算撤回。

详细[优化方案（分析中）](optimization_plan.md)、[RTL与回归映射](runs/R002/rtl_routability_analysis.md)。R001仍在正常生成跨SLR/目标位置报告，最终排序与审核待闭合。


---
Published: 2026-10-15T23:44:12.715601+00:00
Publication: P45fb4c60fdff4b448feda15b24d252b4
