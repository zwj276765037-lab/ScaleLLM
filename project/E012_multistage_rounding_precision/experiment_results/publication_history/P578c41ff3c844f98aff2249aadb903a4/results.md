# E012 多级舍入：结果

execution_state: completed（本轮有界实验；M005全链目标未完成）
verdict: supported（仅v2 synthetic与BF16真实局部Linear恢复/确定性界；M005全模型目标未完成）
review: synthetic、真实32与真实128均已独立复算接受

两次真实局部回放均168/168合法，0异常、0饱和、0lane mismatch、四种确定性界违例0。以下「差值」为当前实现−仅输出舍入，单位定点小数16位的输出LSB=2^-16；32/128不合并。

| 输入长度 | 同码 | −1 LSB输出 | 差值signed mean (LSB) | 最大绝对差 (LSB) | 仅输出舍入对oracle RMSE (LSB) | 当前实现对oracle RMSE (LSB) |
|---|---:|---:|---:|---:|---:|---:|
| 32 | 117/168 | 51/168 | −0.3035714286 | 1 | 0.2939525631 | 0.4728670458 |
| 128 | 115/168 | 53/168 | −0.3154761905 | 1 | 0.2872616707 | 0.5109919831 |

对照差值signed mean实数分别−4.632132393973214e−6/−4.813784644717262e−6，最大1.52587890625e−5。相对精确oracle的最大绝对误差分别1.3655118942/1.3518400192 LSB，不能把主对照最大1LSB写成对oracle≤1LSB。各profile低1LSB数：32为Attention17/96、Gate/Up13/48、Down21/24；128为25/96、9/48、19/24。

[32逐行](../experiment_results/runs/R002/attempts/AT003_cpu_replay_bf16_32token/results.jsonl) · [32汇总](../experiment_results/runs/R002/attempts/AT003_cpu_replay_bf16_32token/summary.json) · [128逐行](../experiment_results/runs/R002/attempts/AT005_cpu_replay_bf16_128token/results.jsonl) · [128汇总](../experiment_results/runs/R002/attempts/AT005_cpu_replay_bf16_128token/summary.json)。两次CPU回放native0，1.212/1.259秒，运行期间源码/输入未变。所有source_files校验通过，资格仅bf16_trajectory_local_replay，eligible_current_format_evidence仍false。

两长度各有逐点差值图和相对精确oracle的两组RMSE图，PNG/PDF/SVG齐全，中文、分母、坐标已目视检查。图和逐点CSV/manifest在 [32图目录](../experiment_results/runs/R002/attempts/AT003_cpu_replay_bf16_32token/figures/plot_manifest.json)、[128图目录](../experiment_results/runs/R002/attempts/AT005_cpu_replay_bf16_128token/figures/plot_manifest.json)。没有将零差的输出省略或与synthetic拼接。

真实采集32/128分别native0，45.834/45.343秒，observed RSS1.96/1.92GiB，ownGPU峰14.44GiB；290参数/FP32 RoPE/21模块原权重与实际GPU加载行均验证。两个GPU worker均已退出。原R002/AT001在HF bulk加载时RSS超8GiB受控停止（native−15/监督124）完整保留，无前向/无输出，不构成方法否定。

synthetic v2为303条/264合法：255同码、8个−1和1个−2 LSB，四界0违例；A014独立复算oracle/current/lane/D一致。该−2构造机制不混进真实样本统计。单文本/三层/首末token/4通道的局部结果不能推断总体模型精度、置信区间或非劣效；全32层、全V5、GPU Triton/RTL逐bit、NLL/PPL/ACC均未测。

A014对128数据也完成21个npz、84个原checkpoint行、7,296激活组、14,592权重组、29,184 JSONL lane和168恢复的独立核查，0 mismatch、0界违例。两长度来自同文本且前32 tokens相同，不能称336个独立样本。Root已补齐AT002–AT005集中登记；pending历史已追加解决，原件未删除。图中F16指固定小数16位，非float16。
