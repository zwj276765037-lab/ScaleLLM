# E010：首轮smoke已执行，正式精度待补

R001 AT001在两张A6000实际启动并于2026-10-18T02:04:05Z自然失败收尾。BF16执行4/4训练smoke样本；a8w8_fp32/a8w4_fp32在生成前的logits allclose门失败；两prompt前16 greedy token一致、同进程32token重现和全部QDQ投影覆盖通过。smoke不是正式精度。

原始日志、模型输入身份、验证记录和冻结源均保留；当前进行受控train-only cache诊断。pilot和test1319均未启动。


---
Published: 2026-10-18T02:11:15.991462+00:00
Publication: Pee0038b7d03442acacbbe07697780a9e
