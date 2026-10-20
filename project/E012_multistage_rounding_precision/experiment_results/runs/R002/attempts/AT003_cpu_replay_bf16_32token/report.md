# AT003 cpu_replay_bf16_32token

实际执行：completed，native exit 0，监督 exit 0；1.212秒。

范围：32-token真实BF16轨迹局部同码Linear恢复；168条合法/无理论界违例；117同码/51低1LSB。

原始证据：[manifest.json](manifest.json)、[execution_receipt.json](execution_receipt.json)、[summary.json](summary.json)、[results.jsonl](results.jsonl)。

独立审核见软件rounding_precision/source/review.md；执行完成不代表整个M005精度目标完成。
