# E006：当前归因结果

热点UNION原语103313条，MLP占79277条（约76.7%）；旧输入前端候选覆盖弱，保留为未实施探索对照。[原热点事实](runs/R003/attempts/AT001_lean_physopt_attribution/hotspot_ownership_closed_stage_facts.json)。

下表复用R004真实成员/资源结果，不是新测；两候选全部P原位于SLR1。

| 候选 | LUT | FF | BRAM36 | DSP | 实际P | 热点原语交集 | CLB触及/共享/独占 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| C01 SwiGLU branch1 | 1890 | 6317 | 6 | 2 | 9491 | 8697 | 1788/1776/12 |
| C02 Down weight repack | 3348 | 3557 | 0 | 0 | 7257 | 2303 | 1347/1339/8 |

[资源独立核查](runs/R004/independent_membership_resources_and_probe_review.json)。共享站点数不等于可释放站点数，SLR2余量不证明打包/布通；祖先与macro资格须在真实新图重验。

R005 AT003两成员资格均原生通过，C01 RAW/S/P=9514/9507/9491，C02=7260/7257/7257。C01完整cut为14307 canonical nets、55605候选leaf pins、58361保留端点、3087 ingress/55 egress、21479 driver-load边界对。[完整cut事实](runs/R005/attempts/AT003_system_python_directed_cut/candidate_C01_directed_cut_closed_facts.json)。其中3072输入data/select网构成6144对，当前已知跨SLR为0；若外部位置不动且全P移SLR2，则为6144跨区对。这不是6144信号或实测SLL使用量。部分驱动位置未知，不能计为零代价。40条原失败样本alias交集为0，不反驳热点关联。

C01四组实际max/min方向查询均返回cap16路径：INGRESS20534候选LOAD的最差setup+1.416ns、hold−0.128ns；EGRESS945外部LOAD为+1.848ns/+0.035ns。双向最差setup涉及相邻SwiGLU分支控制，报告中网络延时占94.13%/94.72%。[时序独立判读](../../../agent/A007/R005_AT003_native_stage_review_20261017/C01_timing_review.md)。这些是原physopt估计结果，不是完整cut TNS、迁移后时序或合法route签核。

R005 AT003按本次明确用户许可于2026-10-17 02:48:19Z受控结束（native−15/supervisor125），C02cut/时序未完成；已得C01结果保持。全部16项输入/进程/资源锁收尾通过，144输入和原DCP未变。[真实终态](runs/R005/attempts/AT003_system_python_directed_cut/terminal_facts.json)。旧R004受控未完成、AT001 owner缺失、AT002工具Python环境失败均保留，不解释为候选失败。

R006同覆盖端口索引包1425及匹配E008包dcc64的[集中准备审核](../../../agent/A007/top_port_index_preparation_review_20261017/final_review.md)已通过；原生资格和加速效果待新运行实测。当前候选未选，implementation未启动。

R006 AT001在原生启动前因重复nice设置自然失败，没有EDA或设计结果；原收据与日志保留。正确调用后的AT002于02:51:03Z真实启动，CPU0–7/nice5、12归档源、144输入和唯一EDA锁已核。[原生启动证据](runs/R006/attempts/AT002_top_port_index_directed_cut/native_start_verified.json)。

R006 AT002的C01完整端口索引已于03:44:45Z真实闭合并由归档validator重验通过：269端口/269完整alias组，2170次原生调用，无断开、多组或未知方向对象，qualified=true/issues=[]。[索引事实](runs/R006/attempts/AT002_top_port_index_directed_cut/candidate_C01_native_port_index_closed_facts.json)。此处只证明该真实图的索引资格，完整C01cut/时序及C02对照仍待完成。

本轮高频alias同步日志造成明显额外工作；已核owner和网络范围未扩大、无新增重复closure证据，具体耗时贡献未隔离。原运行保持。后续缓冲日志23be/3cae入口已集中独立通过；主控已询问本次R006 AT002切换许可，尚无答复，未停止。


---
Published: 2026-10-17T03:45:55.477162+00:00
Publication: P751386c8e2e34162b08d27729031b56d
