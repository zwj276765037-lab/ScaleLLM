# R002：缓存调用验证修订

本轮软件任务负责人依据训练样本诊断和 A010 独立审查作出此技术修订；不是新增的用户批准，也不改变硬件 M003。原 R001 终态 failed 保留，不能标记为通过。

## 证据与被排除的解释

所有诊断只用固定 train:0000/0001，未查询正式 test 答案调整协议。

| 对照 | A8W8 FP32 scale | A8W4 FP32 scale | 判断 |
| --- | --- | --- | --- |
| 首次完整提示 cache on/off | 两提示误差均 0 | 两提示误差均 0 | 未见初始调用错位 |
| 第16步，原缓存开关容差 | 1提示失败，max .25 | 2提示失败，max .3125 | 原门未通过 |
| 双方 logits_to_keep=1 | 原失败保留 | 原失败保留 | 排除仅输出层计算形状造成失败 |
| 禁用 BF16 reduced precision | 仍有超限 | 仍有超限 | 不采用此设置作为修复 |
| 手工增量调用 vs 原生 generate，第0–16步 | 全部 raw logits 逐值相同 | 全部 raw logits 逐值相同 | 受控调用路径一致 |
| 末步从空缓存按相同分块重建 | 误差 0 | 误差 0 | 初步状态重建对照通过 |
| 故意清零缓存 K/V | max误差12.75–13.6875 | max误差11.9375–18 | 反例检出 |

独立单层 probe 保持输入行/权重相同且不使用缓存：BF16 up/down 最大差 .001953125；A8W4 q/up/down 分别 .0078125/.00390625/.0009765625。重复相同形状输出逐值相同。此证据表明计算形状会产生 BF16/QDQ 舍入差异，但不宣称已穷尽整个模型累计漂移的来源。

原始 JSON、脚本与冻结激活：`../../results/gsm8k_full_completion/preparation_20261018/{cache_diagnosis_AT001,native_cache_diagnosis_AT001,projection_shape_diagnosis_AT001}/`。审核：`../../results/gsm8k_full_completion/preparation_20261018/protocol/cache_review_AT002.md`。

## 新资格版本 native_cache_call_parity_v2

新 R002 使用新 plan SHA 与 verification_contract_id，旧 R001 结果不复用。每模型/配置固定同一 GPU，smoke 与 pilot 是独立新进程。

- 每个固定提示第0–16步（或原生 EOS 提前结束）：手工增量调用与原生 generate 的全词表 raw logits 必须逐值相同且有限。
- 每步从空缓存按同一完整提示加逐 token 分块独立重建；全 logits、各层 K/V 必须逐值相同，并检查长度、前缀保持和无存储别名。
- 最后一个可用 decode 步故意清零副本 K/V，须检出输出变化。仅首 token 为真实 EOS、无前置缓存时允许明确 N/A，不能伪写 detected=true。
- 两次同进程及两个独立进程前32 token 必须一致，检查固定 GPU UUID 与全部 QDQ 投影预填充/解码覆盖。
- 原 cache on/off 全词表 allclose（atol=.125、rtol=.01）和前16 greedy 一致性继续保存真实结果，角色改为诊断，不扩大容差、不改写失败。

这一修订验证调用与缓存状态管理，两个对照共享 Transformers/QDQ 核心，因此不构成 native cache 数学正确性的独立证明，也不证明 cache on/off 数学等价。正式报告注明原生缓存语义和这一限制。

## 保持的评估口径

六模型×五配置；GSM8K main/test 每组1319题；原5-shot schedule/seed；raw prompt；greedy；BF16 eager；未量化原生 KV；总8192、新增4096；strict-match 主指标；其余五任务原始分数；无 PPL。生产生成、QDQ算法、权重、数据和评分均不修改。pilot长度/显存门继续执行。
