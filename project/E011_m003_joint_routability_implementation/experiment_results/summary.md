# E011 当前结果

AT006于2026-10-20T07:07:38.914405Z自然native1/nullstop结束。实际route_design Default因797175最终节点重叠失败；最终route_status有615840资源冲突网。完整place/physopt POST资格通过，route正式POST未进入，未合法布通；时序/安全签核仍OPEN。失败DCP752616705B保全，205源与50身份/锁闭合完成。

R004/AT001于08:28:08.524165Z实际只读启动、09:06:22.648218Z自然native0/nullstop完成；固定scope_exhausted，未执行物理命令或写DCP。205源/归档绑定、7归属身份退出与锁释放均核；额外18项输入含原失败DCP终态字节身份仍匹配。原生峰值owned RSS45.00GiB，未触发资源停止。

全量对账：raw CONFLICTS对象3147231，canonical637893，877互斥主组sum637893。native report615840，差22053保持；actual driver常量22054、非constant615839，仍比report少1，未删常量强凑。旧E009同口径canonical569597/report547548/constant22050，同样非constant残差−1；旧差22049保持。

|当前主要actual-driver/source→load组|canonical冲突网|旧E009同口径|变化|
|---|---:|---:|---:|
|MLP shared branch1 SLR2→2|166422|151527|+14895|
|Attention projection array SLR1→1|92992|84058|+8934|
|MLP shared branch0 SLR0→0|85064|55822|+29242|
|Attention projection frontend SLR1→1|32803|33641|−838|
|SwiGLU SLR2→2|17523|15496|+2027|

不同设计及物理版本；这是同口径对比，不归因于某一单项改动。跨所有source/load组合的模块总数见actual_driver_module_ranking.tsv（含保留常量），不能与上表单组混用。

最低端点跨界需求按canonical637893：本SLR端点603358(94.586%)、相邻7873(1.234%)、两界4588(0.719%)、未知22074(3.460%)。两界=source0/2有opposite负载2665 + source1分别到0与2的1923。sourceSLR总数0:105719、1:238894、2:271223、unknown22057。端点统计不能单独证明实际route没有离开该SLR。

142实际route代表样本中131完整node集合、11截断；43样本所有节点区域全映射，99含未知region或截断。86个完整LOCAL样本未观察额外SLR，仅限选择样本。最终parent_head12个bit实际sourceSLR2→branch0 loadSLR0，全部route节点观察到SLR0/1/2，具体支持此跨中部通路，不能外推全部冲突。

最终十热点原生映射：projection→SwiGLU的INT_X57Y687在SLR2/X3Y11；其余9个长线/quad/local热点在SLR1。具体seed实例：projection4772由SLR2/X2Y10寄存器→SwiGLU branch1 SLR2/X3Y11；parent_head1299由SLR2/X1Y10→branch0 ingress SLR0/X1Y3；paired_weight184由SLR1/X3Y9→Attention weight_frontend SLR1/X3Y6/7；d0_smc rdata由SLR2/X3Y10→Attention/input/meta的SLR1区域。本地、相邻与两界具体争用并存，不能简化为唯一共享SLR1原因。

site.TILE属性不支持，全量endpoint-window交集明确NOT_MEASURED（7213787端点缺site→tile链接）；已选deep有1490条actual site/tile事实，final seed及route节点区域映射仍有效。CR边界breaktile的region UNKNOWN保留。原congestion表仅PlacerFinal/RouterInitial，邻域组成不是最终模块冲突份额；797175全体overlap-node成员映射、全部冲突网实际route/SLL用量仍NOT_MEASURED。结果独立审核待收口。


---
Published: 2026-10-20T09:13:04.148798+00:00
Publication: P56b95df73ae74a4aa8a2da2ff67b3445
