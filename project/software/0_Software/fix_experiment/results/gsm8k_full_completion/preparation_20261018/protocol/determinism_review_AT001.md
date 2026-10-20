# Llama-3.1 BF16 原生重复性只读审查

当前三种设置均未通过逐元素精确的原生生成重复性门，尚无可据此批准的 backend 修复。R002 的失败保持，不能把确定性配置已启用当作确定性已验证。

我在 CPU 8–9 上核对了六份原始 logits 文件的 SHA-256，并独立重算 102 对张量的 exact、finite 和最大差，全部与诊断 JSON 一致。完整证据与版本边界见 [determinism_review_AT001.json](determinism_review_AT001.json)。本 agent 未启动 GPU、EDA 或修改源码。

| AT | 实际设置 | 两题 native 自比 prefill 最大差 | 同 native token 序列 |
| --- | --- | --- | --- |
| AT001 | BF16 reduction=True，原默认 backend | 0.109375 / 0.125 | 两题相同 |
| AT002 | BF16 reduction=False | 0.125 / 0.078125 | 第二题分叉 |
| AT003 | deterministic algorithms=True，workspace=`:4096:8`，BF16 reduction=True | 0.28125 / 0 | 第一题分叉；第二题后续 logits 仍不等 |

AT001–AT003 的 registered buffers 哈希、parameter version 和已记录模型模式均未变。捕获到的 prefill 输入、位置与 mask 都连续；全一 mask 的 position IDs 是零起点的 cumsum/arange，cache 初始为空。安装版 Transformers 每次生成新建 DynamicCache，对 input IDs 作连续 clone。没有证据表明位置偏移或这些布局差异能解释原生自身 step0 不等。

方法有两个需保留的边界。第一，forward pre-hook 只在每题第一次 native 调用执行 kwargs deepcopy 和 CPU 哈希/同步，第二次没有等量仪器操作。第二，第一次输出及 cache 在第二次调用时仍保留，allocator/workspace 条件会改变。因此观测已证明“此诊断调用模式下不重复”，尚不能唯一归因于某个 GEMM。最小追加对照是在捕获完成后，对两次都不再捕获的 native 调用作比较，并对两个完全相同的 fresh-cache manual prefill 作比较；无需更换模型或提示。

两个自由生成序列若已分叉，后面的 logits 对应不同 prefix，其 14–24 级差值不能当作同一输入的纯舍入误差。应优先看 step0 和首次 token 分叉前的共同 prefix，分别记录重复性与生成分叉。单纯 buffer/version 不变也不证明所有未登记的全局状态或任意 `.data` 写入均被排除。

若后继 backend 候选确实通过，修订边界应为：

1. 新建 R，统一应用于六模型五配置，保留 R001/R002 失败与原始诊断，不导入旧六组 smoke 通过记录。
2. 在 Python/CUDA 初始化前通过启动环境固定 cuBLAS workspace；实际 deterministic、warn_only=False、BF16 reduction、TF32、软件/驱动和 GPU UUID 进入冻结协议和运行身份。应用配置之后仍须实测 exact、KV、负对照和新进程同卡重复性。
3. 重做该设置下全部 smoke/pilot，并重新实测时延与生产峰值显存。配置启用不替代 30 组资格核验，不放宽 v2 exact 门。
4. checkpoint/QDQ 算法一致支持“相同方法的新 backend 测量”，不能暗称与旧 backend 数值完全一致。历史五项若缺少对应 math flags，来源清单与表注需明确边界；不能静默放行严格 backend 匹配，也不能自动扩成五项重测。

本审查只覆盖 AT001–AT003 的已完成证据，不为未完成或未来尝试预填成功结论。
