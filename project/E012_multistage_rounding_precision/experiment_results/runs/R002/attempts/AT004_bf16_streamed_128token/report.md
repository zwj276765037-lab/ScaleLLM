# AT004 bf16_streamed_128token

实际执行：completed，native exit 0，监督 exit 0；45.343秒。

范围：独立128-token真实BF16轨迹局部输入采集；168输出、29184组；不与32-token合并。

原始证据：[capture_manifest.json](capture_manifest.json)、[capture_receipt.json](capture_receipt.json)、[capture_summary.json](capture_summary.json)、[captured_input.jsonl](captured_input.jsonl)。

独立审核见软件rounding_precision/source/review.md；执行完成不代表整个M005精度目标完成。
