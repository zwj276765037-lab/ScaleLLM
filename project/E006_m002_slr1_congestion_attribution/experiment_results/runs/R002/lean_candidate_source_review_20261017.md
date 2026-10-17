# E006：lean R003 查询入口集中审结

execution：本轮有界源码/CPU审核完成；无EDA、信号、进程或锁操作。verdict：精简入口及明确覆盖差异支持提交主控的切换决定；原生API/运行资格尚未验证。applicability：最终prepared manifest与Tcl/runner/launcher精确身份见[审结事实](lean_candidate_source_review_20261017.json)。review：内部审核，不代表用户允许中止原会话或E006验收完成。

最终来源为Tcl `e313e9cd…`、runner `cdf4c9d8…`、launcher `0bac48a2…`；manifest `ce281818…`。10份准备文件与4份原归档均独立重hash匹配。新目的地为E006/R003/AT001，原复用、终态和PID/start来源仍为R001/AT001。显式original_ids退出守卫位于R003遍历之外并绑定input记录，路径改动没有丢失原会话身份核验。

三项修正已逐行核：失败net命中1项仍须NAME严格等原字串；空/多/非真实SLR对象保留未解析；identity/topology失败即终止依赖。唯一report_utilization调用只接受一个非primitive exact hierarchy，移除了全部大leaf-list报告。原targets字节不变。

覆盖顺序为实际region/UNION准备→40失败原名与10节点→真实tile/site/primitive与10NW/UNION→全部UNION附着canonical nets及leaf IN/OUT端点→9个单exact hierarchy报告。原完整primitive归属和global+首4owner资源按同DCP的已闭合身份复用。每个自然query0可独立审核，不把文件暂时稳定当闭合。

保留缺口：不新增热点native LUT/FF、exclusive core_other/interconnect余集native报告、33细层native报告。inclusive core不是core_other；raw LUT/site不冒充native LUT或拥塞。INOUT/top ports未覆盖，DSP.C等需要REF-aware CPU分类；UNION完整附着net不等于候选全cut。固定窗口拥塞仍UNAVAILABLE。

原wrapper第224行的未定义new_peak_sources静态缺陷保留；新runner使用实际external_inputs绑定，既有有界CPUcheck及R003修订桥接保留。原会话真实native退出、stop、wrapper后检错误、独立输入/身份/锁收尾须分别记录，不能把部分查询成功当整个会话成功。

当前原进程未由本审核中止；切换须基于真实用户决定及原真实终态，由A006唯一调度。正常运行无墙钟/静默强停不变。后续在真实事件到来后复用A007审核，不声称文件提供后台监控。
