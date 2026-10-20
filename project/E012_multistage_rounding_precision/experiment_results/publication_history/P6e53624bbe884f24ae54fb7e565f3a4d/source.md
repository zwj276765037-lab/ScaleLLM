# E012 R010：原版第32层两输出投影逐数舍入核验

M005/SM021，按用户最新范围只核验原版layer31 Attention o_proj与MLP down_proj，不再优化/加位/跑全模型。固定R006正式数据中预声明的15篇audit文档、1746位置，原样复用CURRENT PreparedActivation01/03，仅加载该层两套checkpoint矩阵，沿用原V5分块权重量化。每出口7151616数值，总14303232；这是15篇逐值普查，不是1024篇逐值普查。

私有原production kernel复制只加observer导出，原算术/有限宽度/half-away/饱和保持；分别保存F24 accumulator、F16当前/独立参考整数码、exact quotient/remainder。原版输出/计数、独立exact参考、旧R006 witness完整依赖与local aggregate为硬一致性检查。全量逐组shift/非零余数/丢弃1比特只流式统计，不保存41亿组项。

[合同](../experiment_results/runs/R010/lastlayer_rounding_audit_contract.json) · [来源/固定15篇](../experiment_results/runs/R010/attempts/AT001_original_two_exit_scalar_audit/manifest.json) · [协议](../experiment_results/runs/R010/attempts/AT001_original_two_exit_scalar_audit/protocol.md)


---
Published: 2026-10-20T02:16:56.874698+00:00
Publication: Pc02186b680df4808ba1f3ff23b45cc37
