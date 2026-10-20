# A014 本轮交付：R004/B001及正式审计入口

execution_state: completed
verdict: inconclusive（整体数值精度；本角色已完成的证据审核范围如下）

B001已完成16/1024篇正式文档。最终独立审计`generic_v2.json`单CPU10.086秒：所有16篇冻结输入、32层hidden统计、384局部位置、384动态事件和final norm公式完成核查；预定audit文档c4:6896的全32层hidden、final及384个局部见证独立复算，两臂逐码0不符。72064个展开见证输出中38376适用理论界且0违例，Softmax33688个causal-mask坐标单列。非audit文档只完成身份、覆盖和聚合公式核查，不宣称原数组逐值复算。

全部16篇末端相对L2记录范围1.1739466238324%–1.7805607257696%；audit文档原数组复算1.5015658007872%。部分结果不构成总体P95/P99置信结论，没有据此制定通过阈值。

通用审计入口`experiment/audit_formal_numerical.py` SHA `1b0eae5f16b2b6b7957d319b570c95c5ab918a2bec94b288a3a240ca8773e421`已冻结；无audit无目录/显式空manifest、薄3层原数组结构通过资格，故意篡改非audit末端公式正确拒绝。无见证时零违例/零不符字段为null，不能冒充已验证。实际结果与fixture资格均保留于[B001 independent_audit](../../project/E012_multistage_rounding_precision/experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical/independent_audit/)。

有限队列最终源SHA `da6c8046ca4ead82907a86e7895e885d363af8c243fbb9ab2d0dcde3e7d3592f`经只读复核，日志游标、SIGTERM收尾及finalize身份竞态已闭合，本冻结计划范围无阻断。Root负责Q001后台执行，A014不监控、不声称剩余1008篇已经完成。后续25份逐attempt审计、完整聚合与最终报告仍由实际终态决定。

适用域：本模型/格式、最长128真实token、32层prefill；不能外推长上下文/decode。局部G/K条件保留，五类见证不代表SwiGLU/Host独立原始见证全覆盖。未重跑ACC/PPL，也不以任务非劣效作为本轮门槛。详见[当前独审正文](../../project/software/0_Software/rounding_precision/source/numerical_fidelity_review_v3.md)与[v3合同](../../project/software/0_Software/rounding_precision/source/numerical_fidelity_contract_v3.md)。

## 历史交付索引

早期E012 protocol/source设计、R001合成以及R002两个长度的BF16局部Linear复算保留于[早期review](../../project/software/0_Software/rounding_precision/source/review.md)。R003开发文档和后续正式计划审核保留于当前v3独审正文对应历史章节。此前仅局部Linear的supported不作为本轮整体结论；历史“全32层未覆盖”也只描述R002当时范围，不能覆盖后来已完成的R003/B001证据。
