

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-20T08:57:35.240611+00:00。来源修订：`cfb9c0cd3fc1`。

# E010 · gsm8k_six_model_completion

关联：M004 / SM020

## 原始管理记录

- [实验协议](experiment_source/protocol.md)
- [来源摘要](experiment_source/summary.md)
- [结果摘要](experiment_results/summary.md)
- [状态摘要](experiment_status/summary.md)

## 当前结果摘录

# E010：导致异常慢的逐题核验开销已修复并实测

旧实现每题前后全权重GPU→CPU复制/转bytes/CPU SHA，8B每题额外105–106秒。修复仍检查完整内容与相同频率，通过不可变可信字节比较消除重复SHA开销。

| Llama3.1-8B配置 | 旧持续间隔中位数 | 新持续间隔中位数 | 观测提速 | 四题旧/新总耗时 |
| --- | ---: | ---: | ---: | ---: |
| BF16 | 107.437s | 9.290s | 11.56× | 979.389s /433.238s |
| a8w4_fp32 | 112.019s | 14.246s | 7.86× | 1148.907s /601.538s |

持续间隔来自3个相邻generate_one completed_at差值中位数，包含前题postcheck/后题precheck+generation/持久化，排除一次性加载及最终复核。短worker整体比仅2.26×/1.91×。两版纯生成BF16为7.724→8.782s，QDQ24.286→24.732s，生成计算路径本身没有提速。当前与yqh共享、旧为同卡较早基线；此为有限共享观测，不是独占受控吞吐资格。

父与A010独立审核均通过：两配置四题请求字节/全部输出token及文本相同；两条32token verification前缀、checkpoint/tokenizer/method/packages、完整staticbaseline/root相同。各15阶段、12个runtime每阶段分别完整16060523008/16060529152字节、原nativev2及负例通过；全部artifact hash/canonical identity/16源前后及快照已核。

CPU worker88/88、consumer初版109/109及最终来源门120/120通过；模型guard独审10/10。GPU0合成64MiB+37B比值14.461×且四处真实翻位均拒绝，仅适用合成。

仅8道训练/每题max64token诊断，未发布ACC，不可外推所有模型/长回答/完整矩阵时长。正式0/39570；原R003停止前smoke10/30、pilot/formal0/30仅历史，新版30组资格尚未开展。完整报告和原始链接见performance_repair_report.md；便捷副本project/software/0_Software/fix_experiment/results/PERFORMANCE_REPAIR_20261018.md。

2026-10-19用户追问历史literature_2048同ACC及量化反超。已完成CPU只读审计：五任务120项同模型比较，量化高18/低96/同6；相同显示值对应整数正确数确实相同。DeepSeek BoolQ四配置恰等于2033/3270多数类基线，但旧记录无逐题预测，不能确认全Yes；Qwen2.5较低两配置与设备ordinal1/批次混杂，缺physicalUUID、逐run代码/有效权重证明，因果待验证，不能归因当前GPU故障或量化噪声。30组协议/身份metadata基本一致、量化attach汇总匹配，未发现直接标签/位宽串用

（摘录截断；完整记录见链接。）

## 每个运行批次

| 批次 | 详情 | 具体尝试数量 |
| --- | --- | --- |
| R001 | [本批结果与证据](experiment_results/runs/R001/README.md) | 1 |
| R002 | [本批结果与证据](experiment_results/runs/R002/README.md) | 1 |
| R003 | [本批结果与证据](experiment_results/runs/R003/README.md) | 1 |

## 原工程历史结果


本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
