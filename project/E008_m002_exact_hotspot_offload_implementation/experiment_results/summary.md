# E008：AT004自然布线失败，收尾已核

execution_state: failed  
verdict: inconclusive

**未合法布通。** 原生route于2026-10-17 19:09:25Z（北京时间10月18日03:09:25）失败；Phase9核验报告702396个重叠节点、547548个拥塞失败信号。native route报告耗时3h51m12s。五项失败诊断随后全部成功保存，19:28:37Z结束；失败图locality采集完成后保留原错误重抛。监督器于21:18:30.695127Z（北京时间05:18:30）自然结束，native1/supervisor1、stop_reason=null、无需清理；status的completed仅表示监督结束。

| 当前失败图诊断 | 实测 |
| --- | ---: |
| 可路由网络 / 完全路由 | 2031733 / 1484185 |
| 有路由错误 / 资源冲突 | 547548 / 547548 |
| 全局WNS / TNS | −12.413 / −915419.312 ns |
| setup违例端点 | 418798 |
| 全局WHS / THS | −0.125 / −41.550 ns |
| hold违例端点 | 3264 |
| WPWS / TPWS | −0.664 / −2.171 ns |

失败DCP765705446B（工程独立核SHA51679d9a…）及route status/timing/congestion/DRC已保存。timing页眉Routed不等于合法布通；DRC实际Partially Routed，RTSTAT-13/CW1+15917 Warning，不是DRC签核。失败图through-LOAD四组各16：入setup/hold−6.093/−0.055ns、出−6.093/+0.026ns，均不是全局时序或full-cutTNS。

完整place与physopt已独立接受；失败图候选9491个原始P仍全SLR2、无缺失/替换，cut14307网/58361保留端点/21479边界逻辑对。定向落区成立，但本次合法布通失败；不能将全局重排、热点变化或失败归因全部算给C01。局部SLL超额、高拥塞、6个warned bus-skew目的pin与shared source覆盖缺口、正式reset/CDC/IO OPEN保留。未取得成功route全局POST或正式routed签核。

[14项终态核验](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/terminal_summary.json)全true：144输入/绑定源未变、原PID/start消失、EDA锁释放；8499资源样本，峰RSS33.301GiB，最低MemAvailable457.264GiB/disk383.524GiB，无强停。[两个观察器](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/observer_terminal_facts.json)均真实exit0且无活动进程。[A007终态失败及14项收尾独立审核已完成并接受](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/terminal_engineering_delivery_facts.json)，不重复place/physopt；当前无新AT。

[详细失败工程包](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/failed_route_terminal_summary.json)。证据集中入口：[监督终态](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/status.json) · [工程收尾facts](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/terminal_facts.json) · [原生失败及检查点身份](../../../project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation/E008_physical_evidence.json) · [失败route status](../../../project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation/route_failed_status.rpt)。


---
Published: 2026-10-17T22:58:24.632449+00:00
Publication: P9e290ff193074fdb81e0b9242f3f822d
