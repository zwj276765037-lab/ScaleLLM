# A009 最终功能实现交付

execution completed（SM009/E005/R001指定RTL与功能范围）；verdict PASS local functional scope；applicability Attention v1/AT001、MLP v2/AT003；review A007另记。实际模型/effort仍unverified。

3RTL已完成计划48 slot LUT6和32默认row LUT1同拍局部化，输入自首版到功能完成保持冻结。原版/参考、逐项diff、精确输入与失败版本均保留；[R001最终小facts](../../project/E005_m002_optimized_implementation/experiment_results/runs/R001/rtl_functional_final_facts.json)。

Attention：1265488周期冻结差分，1263504槽oracle；192中断/196epochs、4完整图、13591stall，末slot/valid/异步reset/wave127边界命中。MLP Down2477周期/49列FIFO oracle输出、Gate4821/98；replace2/5、stalls1368/2754、reset/clear资格重叠各1、错误16/17场景均通过。AT002 TB声明顺序编译失败已保留，v2仅前移声明；原gold和断言未改。

原日志、身份和限定范围见[Attention结果](../../project/E005_m002_optimized_implementation/experiment_results/runs/R001/attention_functional_results.md)与[MLP结果](../../project/E005_m002_optimized_implementation/experiment_results/runs/R001/mlp_functional_results.md)。功能通过不证明综合网表边界、fanout/拥塞改善、合法route或时序；生产3RTL保持冻结，由A006新综合/物理流程实际核验。A009可通过followup配合后续普通修复或原生结构核查，需先协调活动输入和新尝试，禁止热改源。
