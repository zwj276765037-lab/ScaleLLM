# 单卡恢复及权重完整性：只读实施建议

身份：A010。此文件是给主控的方案评估，不是源码改动、GPU 放行或硬件诊断。适用前提为 GPU0 生命周期证据完成独立核查；单个 up_proj 通过仍不代表全模型或 30 配置通过。

在原最多两卡预算内暂排除 GPU1，将全部 30 配置、全部阶段和同组重试固定在 GPU0（UUID `78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6`）及 CPU16–17，可保留原科学评估口径。六模型、五配置、checkpoint、QDQ、prompt、greedy、评分及 v2 exact/cache/跨进程门保持。应另开 R，记录资源/实现/完整性合同版本，所有 smoke 与 pilot 重跑；R002 六组 pass 不移入新版本。单卡实际耗时和新增校验开销由新 pilot 测量，不沿用双卡 ETA。GPU1 暂停使用是操作决定，不意味着已证明其硬件损坏。

## 最小可审核实现

1. **可信原生加载。** 将现有 `.from_pretrained(...dtype=BF16...).to(cuda)` 拆开记录两个边界。以已冻结 safetensors key 和正确 dtype 映射为期望，逐 tensor 验证 CPU 加载值与 GPU BF16 值的完整字节、shape、dtype。CPU→GPU 复制没有 QDQ 算法运算，要求 exact。若某个 checkpoint 源 dtype 不同，明确记录原有加载所要求的 dtype 转换；不引入新的转换。原 checkpoint 内容身份与 loader 版本继续验证。失败即保存差异并结束该尝试，不能将错误值登记成基线。

2. **原 QDQ 附加的可信基线。** 保留当前 GPU、全 tensor shape 和浮点实现。每个替换模块记录经核验的原始输入 weight 身份、模块路径、配置与实际输出 buffer 哈希；未替换的 embedding/norm/lm_head 等仍应等于原生 checkpoint 期望。用同一 backend、同一完整 shape、独立正确输入副本逐模块重建 QDQ 输出做资格对照，可以逐个释放以控制峰值；不要求 CPU/GPU QDQ 数学结果逐值相同，也不把正常的 QDQ 变换拿去与原始 checkpoint 哈希比较。重建差异是待解释的资格失败，不能靠容差自动放行或改变算法。

3. **完整静态对象清单。** 对 `named_parameters()` 和 `named_buffers()` 建立完整内容基线，包含 `persistent=False` 的 QDQ weight/bias。`state_dict()` 会遗漏这些 buffer。记录逻辑名称、角色、shape/dtype/stride、字节哈希和别名关系，不能只检查 `_version`。另显式纳入 `scalepath4_method_inference._H_CACHE`；它是全局 dict，既不在 model 参数也不在 buffers 中。其小型 Hadamard 矩阵按原 builder 的符号与归一化值校验，首次创建须有明确登记边界。动态 KV/cache 继续走原 v2 重建资格，不混入静态守恒清单。其他合法惰性对象必须明确列出初始化时点，不设通用忽略规则。

4. **每个完整推理单元前后检查。** 原生 generate、完整 manual decode/rebuild 验证序列、每条正式样本生成前后，同步并检查所有静态对象的内容与清单集合。无需给每个 projection 或每个 decode token 装探针。后校验通过后才能将正式行记为有效完成；任何 mismatch 将当前行/worker 标为不合格并保全证据。即便 logits 或 tokens 自比一致，也不能绕过 checkpoint 身份与静态内容门。正常检查保存 manifest/哈希，失败时再保存涉及 tensor 的 raw 副本及差异。

5. **版本与成本。** 在 worker 身份中加入完整性合同 ID、基线 root hash、真实 GPU UUID 和实现源 SHA，并让 scheduler/resume 明确核对。原 `native_cache_call_parity_v2` 的 exact/finite、cache 重建/长度/前缀/不别名、破坏负例及跨进程 32-token 条件全部保留；完整性作为明确新增门，不能默默更写旧 R。采用同步分块 CPU 字节摘要可限制额外内存，但应测量实际开销并纳入新 pilot。不得以运行较慢为由改成抽样检查后声称完整守恒。

## 最少验证及验收边界

CPU 控制应覆盖：稳定但错误的初始 BF16 值被拒绝、调用后低字节变化被拒绝、nonpersistent QDQ buffer 缺失/变化被拒绝、`_H_CACHE` 变化被拒绝、错误 GPU/旧完整性版本 resume 被拒绝。使用小型独立 tensor 与假 worker 测试，不修改 checkpoint 或实际 GPU 权重制造故障。

随后在 GPU0 用新源版本实测完整加载→QDQ 附加→推理后身份闭环，以及原 30 组 smoke/pilot/独立进程重复门。通过后才具备正式矩阵资格。此方案增加对静态参数身份的证据，不替代算子数值验证，也不能排除两个检查边界之间发生并恢复的瞬时异常；不据此宣称整卡健康认证。具体合同比较和放行仍由主控集中决定。

代码依据：[原生加载及附加入口](../../../../exp/run_eval_worker.py)、[FP16/FP32 QDQ weight/bias](../../../../../experiment/scripts/accuracy_MLP_4bit/mlp4_method_inference.py)、[ScaleCode QDQ 与全局 Hadamard cache](../../../../../experiment/scripts/scale_code_linear/scalepath4_method_inference.py)。历史审核：[AT004–007](determinism_review_AT002.md)、[AT008 单算子](determinism_review_AT003.md)、[AT008 checkpoint](determinism_review_AT004.md)。
