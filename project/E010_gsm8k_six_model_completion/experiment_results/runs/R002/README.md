

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# E010 / R002 运行结果

[负责人维护的本批运行记录](run.md)

# R002：原生缓存调用验证v2与GSM8K全矩阵

范围：六模型×五配置，smoke→pilot→formal1319题/格→独立复算/表格更新。缓存资格修订与输入字节等价证据见当前source/gsm8k_execution_cache_v2_20261018；原R001 failed保留。本批code/plan新冻结，不复用旧样本。当前准备新AT，实际状态以attempt记录和raw current_state.json为准。

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_dual_gpu_native_cache_v2](attempts/AT001_dual_gpu_native_cache_v2) | failed | 6/30 smoke groups completed; Llama-3.1-8B-Instruct BF16 train0000 native-generate/raw-forward bitwise mismatch; rebuilt KV and repeatability passed, train0001 passed. Queue naturally drained; 0 pilot/formal. Controlled GPU1 diagn… | [执行收据](attempts/AT001_dual_gpu_native_cache_v2/run.json) · [report.md](attempts/AT001_dual_gpu_native_cache_v2/report.md) |

## 本批问题与交付文件


## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
