

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# E011 · m003_joint_routability_implementation

关联：M003 / SM015

## 原始管理记录

- [实验协议](experiment_source/protocol.md)
- [来源摘要](experiment_source/summary.md)
- [结果摘要](experiment_results/summary.md)
- [状态摘要](experiment_status/summary.md)

## 当前结果摘录

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

142实际route代表样本中131完整node集合、11截断；43样本所有节点区域全映射，99含未知region或截断。86个完整LOCAL样本未观察额外SLR，仅限选择样本。最终parent_head12个bit实际sourceSLR2→br

（摘录截断；完整记录见链接。）

## 每个运行批次

| 批次 | 详情 | 具体尝试数量 |
| --- | --- | --- |
| R001 | [本批结果与证据](experiment_results/runs/R001/README.md) | 3 |
| R002 | [本批结果与证据](experiment_results/runs/R002/README.md) | 35 |
| R003 | [本批结果与证据](experiment_results/runs/R003/README.md) | 6 |
| R004 | [本批结果与证据](experiment_results/runs/R004/README.md) | 1 |

## 原工程历史结果


本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
