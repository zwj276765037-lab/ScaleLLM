# R001 cache verification 只读诊断

结论：已确认 verifier 与实际 `generate()` 的计算路径存在一个差异，尚未确定数值失败的根因。当前源码未发现明显 cache 长度或位置 off-by-one；BF16 不同计算形状及量化阈值放大误差是可检验假设。原 `.125/.01` 数值门保持，不能凭前 16 token 一致放行正式运行。

原始来源与哈希、精简统计、可证伪条件见 [cache_review_AT001.json](cache_review_AT001.json)。审阅时，三组 AT 的 manifest 所记 worker/QDQ 源哈希均与当前源码一致。

| 3B smoke AT001 | train:0000 最大绝对差 / allclose | train:0001 最大绝对差 / allclose | 已生成 smoke 题数 |
| --- | --- | --- | ---: |
| BF16 | 0.125 / true | 0.125 / true | 4 |
| A8W8 FP32 scale | 0.1875 / true | 0.25 / false | 0 |
| A8W4 FP32 scale | 0.1875 / false | 0.3125 / false | 0 |

六个验证记录均满足 cache on/off 前 16 token 一致、同进程两次 32 token 一致；两组 QDQ 的 196 个投影都有 prefill/decode 覆盖。checkpoint、tokenizer vocab、输入 token 哈希一致。各记录只保存 prompt 位置和生成 16 token 后两次比较的聚合值，未保存逐位置或逐词表超限分布。`allclose` 按 `abs(a-b) <= .125 + .01*abs(b)` 判断，最大差相同不代表判据相同。

最有区分力的发现是 lm_head 路径。安装的 transformers 5.3.0 在 `generation/utils.py:2479–2483` 自动设置 `logits_to_keep=1`；Llama forward 默认 `logits_to_keep=0`，会把所有隐藏位置送给 lm_head。worker verifier 的直接 forward 未传这个参数。因此在生成 16 token 后，verifier 的 cached lm_head 是一行，uncached lm_head 是整个 prefix；实际 `generate()` 两路都只算最后一行。这给数值比较增加了额外的 BF16 GEMM 形状因素。它是已确认的路径差异，是否解释失败仍需 GPU 对照。

QDQ 的 min/max 是每个 token、每 32 元素组独立计算，没有主动跨 token 共享量化 scale。Hadamard 先用输入 BF16 执行 matmul，之后才转 FP32 求 scale/round，再回 BF16 做 `F.linear`。prefill 与单 token decode 的矩阵形状不同，微小变化可能越过量化舍入边界；现有证据没有测出发生在哪一层，也没有证明 reduced-precision reduction 是主因。原运行未记录该实际 backend flag；只读 CPU 进程看到的默认 True 不代表原 GPU 运行的独立回执。

建议父负责人执行以下区分实验，维持模型、提示、固定 token prefix 和原阈值：

1. 做 `reduced_precision=True/False × logits_to_keep=0/1` 的 2×2 对照，同一 case 固定设备、每条件新建 cache，固定使用原 32-token prefix 作 teacher forcing。分别保存 step 0 与 step 16 的 finite、maxabs、RMSE、超限数量/比例、最大归一化超限比、超限 token ID、top1/top2 和 margin。step 16 的 logits 预测第 17 个 token，超出原前 16 token 一致检查，需单独核对。
2. 用真实 `generate(output_logits=True)` 取得 cache on/off 原始 logits，作为独立接口对照；在相同 prefix 上与 `logits_to_keep=1` 的直接 forward 比较。若真实生成通过而 manual loop 失败，优先定位调用、位置和 mask；若真实生成也失败，原数值门仍失败。
3. 将同一最终隐藏行分别放在整矩阵和单行形状中送同一 lm_head，隔离纯 head 形状误差。必要时对固定 QDQ 输入行作全矩阵/单行比较，并保存 Hadamard 输出、scale、zero point 和整数 q 的变化，定位舍入放大。

如果只修正 `logits_to_keep` 即在原阈值下通过，并与真实生成 raw logits 一致，可据证据修复 verifier。若采用新的 backend 设置，应统一冻结实际 math flags 和源/环境身份，重新验证受影响的 smoke/pilot，保留 R001 原失败记录。若对照仍不通过，不把 greedy 一致或更宽阈值当作数值验收。

本审查只读已有证据和源码，CPU affinity 8–9、CUDA 不可见；未运行 GPU、EDA 或修改现有代码。正式 full 尚未由本审查启动或验收。
