

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# M006 · mlp_linear_only_hardware

[任务合同](contract.md) · [任务总结](../../results/missions/M006_summary.md)

## 执行子任务与主控审核

| 子任务 | 定义 | 完整审核历史 |
| --- | --- | --- |
| SM025 · mlp_linear_interface_and_project_setup | [定义](tasks/SM025.md) | [审核](../../results/reviews/SM025.md) |
| SM026 · mlp_linear_rtl_and_integration | [定义](tasks/SM026.md) | [审核](../../results/reviews/SM026.md) |
| SM027 · mlp_linear_verification_and_build | [定义](tasks/SM027.md) | [审核](../../results/reviews/SM027.md) |

## 关联实验

- [E013 · mlp_linear_only_hardware](../../project/E013_mlp_linear_only_hardware/README.md) — 未登记

## 任务总结原文摘录

# M006：MLP线性投影硬件工程进展

状态：GU-only RTL、限定功能验证、新综合、合法布线和内部时序已经完成；约束与复位告警正在收尾复核，尚未取得完整硬件签核。唯一新工程根为`Workspace/ScaleLLM_MLP_fix`。

当前关键结果：R008/AT001_impl自然退出0，1687352条可路由网络全部完成、0路由错误；正式WNS **+0.002 ns**、WHS **+0.010 ns**，setup/hold/脉宽违例均0。最终网表Down实例0，96条GU lane、3072 MLP DSP和448 GU metadata URAM符合合同；Host Down保留原整数数学。原质量汇总FAIL保留：三个外部复位端口时序覆盖不足、四次辅助报告参数错误，以及待审核的复位/约束告警。当前正完成同routed DCP有界补证，并按design §12修正被clock_groups覆盖的Max-DPO约束；优先同物理网表资格复核，尚未重做implementation。工程验证版bitstream已生成；上板/真实完整模型验证未执行。

已生成文件：[ScaleLLM_MLP_GU_only_ENGINEERING_VALIDATION.bit](../../project/hardware/vivado/reports/m006_gu_AT003_preliminary_bitstream/native_output/ScaleLLM_MLP_GU_only_ENGINEERING_VALIDATION.bit)，80.2 MB。仅工程验证工件，跨时钟绝对延迟和外部reset签核尚未完成，未下载上板。

最新执行方向（2026-10-24）：用户已批准[GU-only新版方案](../../PRO_plan/ScaleLLM_MLP_Gate_Up_Only_Dual_DDR_Design.md)开始实施。FPGA静态移除Down，保留GU双8×12和Attention；Host承担原整数Down。A022已于UTC15:11:32开始独立新RTL图，A021集中冻结新合同；Host工程随后按明确文件所有权并行。当前v6整板R004已自然布线失败（473423未完成信号、545088重叠节点），R005已因新版实施优先收束为PARTIAL（native -15、0survivor、锁释放、116输入无漂移），已保存并核30件工件，SLR1站点99.86%等核心观察有效，剩余新窗/显式路径NOT_COLLECTED；新GU-only代码/验证状态不得与这些旧图证据混用。下文较早进度保留历史，新版G4R已限定通过，硬件物理完成尚待G5。

最新交付优先级（2026-10-25）：用户明确要求先生成bitstream。AT002剩余只读SMC补查已按该优先级收束为partial并核0归属存活，原核心21工件与告警缺口保留。R008/AT003_preliminary_bitstream已于北京时间08:32:18启动、08:45:47自然native0结束，从原cc34…routed DCP成功生成工程验证版.bit；80159259B，SHA256 `66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47`，Root已独立复算并向用户交付链接，0遗留/源无漂移。Max-DPO/外部reset签核未闭合必须随工件说明，仍不下载或上板；约束修正随后继续。

## GU-only 新版实测（2026-10-24，持续更新）

- R006/AT004：新真37位两列lane的512组数值与48次在途clear重放通过，1638周期检查；旧GU路径逐拍

（摘录截断；完整记录见链接。）

## 相关决定、变更与讨论

- [review_queue](../../results/review_queue.md)

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
