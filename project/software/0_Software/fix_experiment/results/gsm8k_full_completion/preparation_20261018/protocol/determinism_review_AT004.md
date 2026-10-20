# AT008 最终权重与冻结 checkpoint 独立审核

A010 使用 CPU8–9，直接从 safetensors 读取 `model.layers.25.mlp.up_proj.weight`。该 key 的 index 映射为 `model-00003-of-00004.safetensors`；完整 4915916176 字节 shard、index 和 config 的 SHA 均重新核对，匹配 R002 冻结 checkpoint manifest。详见 [审核数据](determinism_review_AT004.json) 和 [独立复算脚本](review_checkpoint_weight_AT008.py)。

加载路径支持逐字节对照：冻结 `run_eval_worker.load_model` 从同一本地目录加载原生 BF16、eager Llama，然后 `.to(cuda)`；AT008 使用 `bf16` 分支，目标是原生 `torch.nn.Linear`，没有 QDQ 变换。checkpoint 与最终保存张量均为 BF16 `[14336,4096]`，无需 dtype 舍入转换。

| 独立核查项目 | 结果 |
| --- | --- |
| checkpoint tensor SHA | `abf3fa9992765e359b6318b5cf94cc559184c37a1a5875b3e249e04f949ee38d` |
| 最终捕获 tensor SHA | `b5462ac771bbf45c17df5f291e3a98b159556b92a1b270996d64b46065efd5b0` |
| 不同 BF16 元素 / 字节 | 16345 / 16345 |
| 影响行数 / 行范围 | 64 / 12800–14251 |
| 每行不同元素数 | 253–256 |
| 高字节变化 | 0 |
| 新低字节为 `0xff` 的位置 | 16282 |
| 存在被清零 bit 的元素 | 12 |
| 最大绝对数值差 | 0.09326171875 |

所有差异坐标、行计数、原始/最终哈希及位模式统计与 A011 的 CPU 对照一致。例如 row12800/col1664 从 BF16 `bc9d`（−0.0191650390625）变为 `bcff`（−0.0311279296875）。低字节包含 BF16 的最低 exponent bit 与 fraction bits；这不是一次普通 GEMM 归约或 allclose 容差的比较。

这证明最终保存的权重不同于原冻结 checkpoint。初始 GPU 哈希也不同于 checkpoint，但当时没有保存 raw 权重，因此其差异分布无法还原。本证据尚不能定位加载、传输、运行时、内存或抓取链路的具体故障来源，不能据此宣称 GPU 硬件故障。

后继最少需要经授权的加载及算子前后立即独立 CPU 权重副本，检查 checkpoint 字节身份、同步边界、参数 storage 别名及变化位置。候选修复应先关闭权重身份异常，再通过受影响/对照提示的无探针 native exact/finite 门；完整矩阵仍需新版本边界下的全部 30 配置、cache 重建/负例、跨进程重复及 pilot 资格。当前无正式 GSM8K 结果或已验证修复。
