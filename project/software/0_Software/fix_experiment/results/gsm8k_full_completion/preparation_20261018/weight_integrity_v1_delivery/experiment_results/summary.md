# 静态内容门受控结果

执行完成，A010独立接受两组终态。CPU专用22项、最终联合82项通过且8源稳定；A010消费者89项及独立源码审通过。原生成5函数/原v2门AST保持。新门不是放松原数值门。

| GPU0/Llama3.1训练smoke | BF16 AT001 | a8w4_fp32 AT001 |
| --- | --- | --- |
| 原生进程 | PID301764，自然exit0 | PID309848，自然exit0 |
| 完成train样本 | 4/4 | 4/4 |
| 原v2详细logits/KV/反例 | PASS | PASS，224 live投影覆盖 |
| 静态完整性阶段 | 15/15 exact | 15/15 exact |
| checkpoint原始keys | 291 | 291 |
| effective静态对象 | 293 | 295 |
| QDQ独立GPU/fullshape重建 | N/A | 224模块 |
| _H_CACHE条目 | N/A | 2 |
| 总耗时 | 985.565s | 1201.818s |
| 纯生成合计 | 7.907s（A010复算） | 26.626s |
| 汇总peak allocated | 16517941248 bytes | 17368237056 bytes |

独立审核包含原始token重解码、installed harness严格评分复算、source/artifact身份、sharedvalidator及完整phase覆盖。两组进程退出与GPU0锁释放均已核验，启动源码保持。实际总耗明显受完整性检查支配，不能用纯生成吞吐估全量。

原始证据位于weight_integrity_v1_gpu_smoke/Llama-3.1-8B-Instruct/{bf16,a8w4_fp32}/AT001，其中manifest/summary/verification/integrity、phase JSONL与postrun_receipt全保留；独立审核位于protocol/integrity_v3_gpu_{bf16,qdq}_terminal_review_AT001.json。完整汇总见本交付根delivery_receipt.json。

范围仅为有界训练资格；正式GSM8K validated仍0/30，30组全新资格及1319题验收未完成。R002冻结11源码与先前记录全字节一致，旧失败不改写。GPU1修复由独立任务处理，此分支不宣称硬件故障或维修成功。
