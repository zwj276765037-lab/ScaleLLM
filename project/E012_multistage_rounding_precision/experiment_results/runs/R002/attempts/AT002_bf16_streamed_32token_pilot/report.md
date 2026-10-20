# AT002 bf16_streamed_32token_pilot

实际执行：completed，native exit 0，监督 exit 0；45.834秒。

范围：真实BF16 32-token单prompt/三层/七算子/两token/四通道局部输入采集；168输出、29184组；不是V5生产轨迹或任务指标。

原始证据：[capture_manifest.json](capture_manifest.json)、[capture_receipt.json](capture_receipt.json)、[capture_summary.json](capture_summary.json)、[captured_input.jsonl](captured_input.jsonl)。

独立审核见软件rounding_precision/source/review.md；执行完成不代表整个M005精度目标完成。
