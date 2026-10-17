

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-17T08:36:24.995092+00:00。来源修订：`400c5b08f7ef`。

# E004 · m002_routability_optimization_analysis

关联：M002 / SM008

## 原始管理记录

- [实验协议](experiment_source/protocol.md)
- [来源摘要](experiment_source/summary.md)
- [结果摘要](experiment_results/summary.md)
- [状态摘要](experiment_status/summary.md)

## 当前结果摘录

# E004：详细优化分析交付

**分析完成；优化尚未实施，布通效果inconclusive。** 完整交付见[优化方案](experiment_results/optimization_plan.md)，含具体模块/控制资格、基线、首选组合、后备、回归缺口、物理比较及严格route验收。

- Attention双wave的10根capture_index位各6170–6174叶负载，全SLR2；input当前18651LUT/12341FF/56control sets。首改固定24×256bit目的写及每wave24个局部译码边界，保留原快照、复位和周期。不得将全部负载先验称为FF CE。
- MLP Down/Gate输出控制8201/6145负载，分别SLR0/1=4105/4096、3073/3072；按各16row拆为32个同拍局部output CE，保持payload/metadata/资格，不给控制单独加拍。
- 首轮合计80个计划控制边界，不是净新增80LUT保证；新的place选SSI_SpreadSLLs，physopt/router保持Default。安装版帮助缺口列启动前轻量核验，效果须新网表/布局/route测量。
- Down浅历史6144个SRL16E实际占3072个SRL-LUT，Gate4608占2304；当前物理槽数不等于未来净节省。S32-only、保留双bank的postprocess固定pair写列独立后备；S24转FF可能增加CE端点。
- 全局LUT68.93%、FF43.13%但CLB站点99.11%；control sets7.58%。48个拥塞窗口Combined LUT最高34%、Level6仅6–16%，无全局no_lc首选证据。Attention2296DSP超过单SLR推导容量2280，不采用整引擎单SLR硬Pblock。
- 回归须补生产Down MATRICES=1、input任意slot reset/clear/新epoch与长背压；旧TB、stub/全零测试不覆盖全部义务。下一轮失败也保存DCP/route_status，保留原始失败码。

[R001物理报告](experiment_results/runs/R001/physical_routability_analysis.md)、[工程小事实](experiment_results/runs/R001/engineering_delivery_facts_2026-10-16.json)、[R002源码/测试](experiment_results/runs/R002/rtl_routability_analysis.md)、[R003方案](experiment_results/runs/R003/architecture_plan.md)、[独立审核](experiment_results/runs/R003/integration_review.md)。

## 每个运行批次

| 批次 | 详情 | 具体尝试数量 |
| --- | --- | --- |
| R001 | [本批结果与证据](experiment_results/runs/R001/README.md) | 1 |
| R002 | [本批结果与证据](experiment_results/runs/R002/README.md) | 0 |
| R003 | [本批结果与证据](experiment_results/runs/R003/README.md) | 0 |

## 原工程历史结果


本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
