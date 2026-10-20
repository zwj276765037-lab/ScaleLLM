# 旧 literature_2048 表：Qwen2.5 实现与设备身份窄审

执行：A013，CPU18–19、CUDA_VISIBLE_DEVICES 空；只使用 Python 标准库，未导入 torch，未运行模型/GPU/EDA，未操作进程。旧根严格只读，35 项输入的 SHA/大小与审计前后一致性见 [source_manifest.json](source_manifest.json)。表格总复算由父负责，协议/逐题记录由 A010 负责，本审计不重复这两部分。

**结论：现有记录没有证实 case 标签/位宽或替换计数串用；已证实设备分配和运行时间批次与方法混杂，且缺少逐 run 的源码与内容完整性身份。Qwen2.5 的异常差异仍未归因，不能据此声明 GPU1 导致或用“量化噪声”代替调查。**

| Qwen2.5 配置 | worker.created_at（UTC） | CUDA_VISIBLE_DEVICES | runner 对 full job 的记录 | 报告替换 |
| --- | --- | --- | --- | --- |
| BF16 | 2026-09-14 08:29:59 | 0 | cached | 不替换 |
| A8W8 FP32 scale | 2026-09-15 03:58:00 | 1 | complete，新跑 | 196，7 类各 28 |
| A8W4 FP32 scale | 2026-09-15 04:10:55 | 0 | complete，新跑 | 196，7 类各 28 |
| A8W4 FP16 scale | 2026-09-15 04:26:21 | 1 | complete，新跑 | 196，7 类各 28 |
| ScaleCode reference_qdq | 2026-09-14 07:28:06 | 0 | cached | 196，7 类各 28 |

这是记录中的 ordinal，不是物理 UUID。所有 worker 逻辑 device 都为 cuda:0，GPU 名称都为 NVIDIA RTX A6000；同五 case 的 worker/merged/run_state/log 中未发现完整物理 UUID，见 [直接检索记录](physical_uuid_absence_check.json)。因此不能把 9 月的可见设备 1 映射为今日的问题物理卡，也无法做设备与方法的独立因果比较。

同模型五配置记录一致的项目：seed 与四个 evaluator seed 均 20260913；ACC batch=32/PPL batch=1；Python 3.10.19、torch 2.10.0+cu128、transformers 5.3.0、lm_eval 0.4.11；HFLM model_dtype 为 torch.bfloat16；checkpoint 的 14 文件元数据及 fingerprint 均相同（60dced2d…3f81），七个数据源清单一致。本轮没有重哈希实际 checkpoint 权重。BF16 的 method 显式记 eager/use_cache=false；量化 method 只记 native_attention_rope_kv，未单独记录实际 attention backend。各配置实际 attention backend 是否完全一致不能仅靠这些元数据确认。完整原始路径和字段见 [逐 case 身份](qwen_case_runtime_identity.json)。

Qwen2.5 是 28 层，目标为 28×7=196，不能套用 32 层模型的 224。四个量化 case 的 method.module_count、per_op 与各自 model_spec 一致，Attention 权重均 W8，A8W8 的 MLP 为 W8，其余为 W4；scale_code_bits/payload 与各标签一致。FP16 指 scale payload，记录的模型计算 dtype 仍为 BF16。与汇总 hash 相符的量化源码在 setattr 替换后累计 per_op，返回 targets 数；FP16/FP32 两类将 QDQ 权重保存在非 persistent buffer，随后 F.linear 使用。这比仅有表格标签提供更多支持，但 raw 未保存逐模块全名、实际类型/权重内容、独立重建哈希或每阶段检查，因而只能说“报告的 attach 覆盖符合预期”，不能追认全部 196 个有效权重在整次运行中保持正确。HFLM 记录的参数数从 BF16 的 7,615,616,512 降为四种 QDQ 的 1,090,199,040，也与投影权重转为 buffer 相容，不构成全内容证明。

源码身份方面，旧 experiment_manifest 只有汇总时的一套 aggregate code_identity；五个 raw worker 没有各自的完整 code identity。保留路径的十份代码目前有七份与该摘要相符，两份 quantizer 均相符；run_eval_worker.py、protocol.py、merge_eval_shards.py 三份不符。它只说明现在可读的这三份字节不能当作记录中的旧版本，不证明五次运行当时一定用了不同代码。匹配的 run_six_model_eval.py 的 cache 资格检查 case/protocol/full_split/checkpoint fingerprint，没有绑定源码 hash；而 BF16/reference_qdq 实际由缓存复用，故汇总的一套源码 hash 不能向前追认它们的逐次运行版本。详细 SHA 见 [源码身份审计](aggregate_code_identity_review.json)。

旧 artifact 没有当前 checkpoint_static_content_v1 或 native_cache_call_parity_v2 证据；后者也不是该旧 log-likelihood ACC 任务当时的生成验收。这里的缺证意味着无法按当前标准证明 GPU tensor/非持久 QDQ buffer/H-cache 的内容与运行中不变性；不能把“缺证”直接判为旧结果错误。对反常幅度，需要另有控制设备、时间批次、源码和权重内容的对照证据才能归因。本轮遵守 ACC 暂停，没有补跑。

本审计的源码静态检查没有找到已记录 case 与位宽/scale 类型互换的直接证据，也没有证明量化实现整体无缺陷。当前可交付判断是：历史结果可按其旧身份引用，异常原因保持 OPEN。
