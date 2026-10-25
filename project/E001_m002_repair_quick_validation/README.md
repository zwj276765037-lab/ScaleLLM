

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# E001 · m002_repair_quick_validation

关联：M002 / SM004

## 原始管理记录

- [实验协议](experiment_source/protocol.md)
- [来源摘要](experiment_source/summary.md)
- [结果摘要](experiment_results/summary.md)
- [状态摘要](experiment_status/summary.md)

## 当前结果摘录

# E001：修复与快速功能验证结果

本轮完成，结论 supported 仅适用于当前源的限定快速验证；M002 时序恢复及最终部署尚未验收。

| 范围 | 已核实结果 | 证据 |
| --- | --- | --- |
| Host/API/布局/生命周期 | 106 项 CPU 测试 PASS | [R001](experiment_results/runs/R001/worker_report.md) |
| 四套定向 XSim | data 11、CSR 10、权重 38、真实 frontend 7 项主检查 PASS；真实 reader 各64组、背压与维护排空通过 | [R002](experiment_results/runs/R002/worker_report.md) |
| 构建/完整展开 | 49 项 CPU 回归和静态合同 PASS；完整 board 88 RTL、0黑盒 | [R003](experiment_results/runs/R003/worker_report.md) |
| 真实 BD | 构造/validate退出0；保留4条地址别名及1条性能critical，生成译码配置已核查 | [BD原始证据](experiment_results/runs/R003/attempts/AT007_actual_bd_validation/bd_address_decode_evidence.json) |
| 数值合同/源身份 | 9项整数参考PASS，170个数值/软件文件hash保持 | [R004](experiment_results/runs/R004/run.md) |

最终输入hash一致；所有失败尝试保留。首组oracle全X问题只修测试台初始化触发并加非X断言，未改数据/地址期望或golden。完整展开仍有历史reset优先级等普通告警；真实BD译码结构支持跨主地址别名解释，但未执行真实SmartConnect/MIG事务，不作critical豁免。

可进入fresh synthesis取新资源/时钟/告警证据；implementation需当前物理检查、互连事务及告警核查。无正式综合、setup/hold、DRC、bitstream、板卡、完整32层/双cohort数值或性能结论。KV仅保留地址；MLP单层流送开销尚未测量。详见[M002阶段报告](../../results/missions/M002_summary.md)。

## 每个运行批次

| 批次 | 详情 | 具体尝试数量 |
| --- | --- | --- |
| R001 | [本批结果与证据](experiment_results/runs/R001/README.md) | 4 |
| R002 | [本批结果与证据](experiment_results/runs/R002/README.md) | 9 |
| R003 | [本批结果与证据](experiment_results/runs/R003/README.md) | 7 |
| R004 | [本批结果与证据](experiment_results/runs/R004/README.md) | 2 |

## 原工程历史结果


本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
