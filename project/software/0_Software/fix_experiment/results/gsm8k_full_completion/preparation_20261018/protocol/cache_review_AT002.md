# R002 cache 验收修订独立审查

主控已明确决定新 R002 使用 `native_cache_call_parity_v2`。本审查支持把它作为真实生成调用的实现一致性验收；这是一项显式的验证合同修订，不代表 R001 原 cache on/off `.125/.01` 数值门通过。原数值算法和正式 greedy 生成保持，旧 allclose/greedy16 的实际 False 保留为诊断。

本次只读复核了父负责人三类 GPU 诊断的六份原始 JSON，路径、源哈希及统计见 [cache_review_AT002.json](cache_review_AT002.json)：

- 2×2 对照的 step0 全为零差异；统一 lm_head 形状没有消除后续 hidden/logit 漂移，关闭 reduced precision 也未通过旧门。A8W4 两题的超限数在关闭后为 37 / 744。因此，早先提出的“仅 lm_head”解释不足，不能把关闭该 flag 当修复。
- 在完全相同激活行、权重且没有 cache 的单模块 probe 中，full-M 与 single-M 输出不同：BF16 up/down 最大差 0.001953125；A8W4 q/up/down 为 0.0078125 / 0.00390625 / 0.0009765625。同形状重复均精确一致。这直接支持采样模块存在形状相关舍入，不证明全部累计差异都来自这一机制。
- 两种 QDQ、两条固定 prompt 共 68 个 native-generation 对照步骤的最大差均为零；末步同 chunk 重建也为零差异，清零 cache 的反例产生显著差异。这支持采用真实调用路径的独立对照；现有诊断只在末步重建，R002 正式验证仍须补齐每一步的 KV/结构证据。

R002 最小硬门应同时包括：逐步 raw 全词表 logits 与 Transformers `generate(output_logits=True)` 精确且有限；每步从独立 fresh cache 按相同 chunk 重建，核全 logits、逐层 K/V、长度、旧前缀保持和无 alias；cache 清零反例可检出；同进程及固定同一实际 GPU UUID 的独立新进程 32-token 重现；预期 QDQ 投影 prefill/decode 覆盖。只检查 argmax、相同 chunk 重放标志或最终聚合 True 不够。

主控限定的 early-EOS N/A 可接受，但必须独立核验：native 只有一个 logit 步，唯一 token 是解析到的 EOS，step0 的精确、结构及 finite 硬门通过；此时保存 `negative_control_detected=null` 和专用 N/A 状态，`negative_control_qualified=true`。其他路径仍必须真正检测到负对照。

两条同形状路径共享可信的 Transformers 核心，因此其通过证明实现调用一致性，不能声称独立证明全部原生 attention 数学、长上下文正确性或完整 GSM8K 精度。plan 中的验证 ID、worker、冻结合同、matrix 和 finalizer 必须共同版本化；v1/v2 不混用。30 组 smoke/pilot 和完整 formal 的验收继续保留。

本 agent 未运行 GPU 或修改数值算法；这里只读审核父负责人真实证据。R001 原失败证据和 [首轮审查](cache_review_AT001.md) 保留。
