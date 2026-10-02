# ScaleCode 模块化对比实验

本目录用于比较 ScaleLLM 当前 ScaleCode/整数数据通路与“计算核输出先反量化为 FP16/FP32，再进入后续算子”的浮点基线。

- [`goal/README.md`](goal/README.md)：实验问题、比较口径、指标、工作负载与验收规则。
- [`experiment/README.md`](experiment/README.md)：模块目录索引和统一目录约定。
- `result/<module>/`：每个模块独立保存 `SUMMARY.md`、机器可读指标和 `raw/<variant>/{xsim,ooc}` 原始证据。
- `result/REPORT.md`：仅汇总通过功能、同吞吐、post-route 时序与 DRC 门禁的正式结果。

实验已进入执行阶段。未满足全部门禁的中间结果统一标为 `DIAGNOSTIC`，不提前宣称实验结论。
