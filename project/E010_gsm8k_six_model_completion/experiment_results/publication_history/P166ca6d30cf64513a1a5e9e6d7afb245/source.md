# E010：GSM8K双GPU执行来源

用户已授权在当前exp实现并执行、确认两张GPU。六冻结checkpoint×五配置、原5-shot raw greedy strict EM、test1319/格，max8192/new4096、BF16 eager、原生KV。实际执行plan与14份源码快照在raw R002 frozen_inputs/frozen_sources，数据和权重SHA均绑定。

R001原cache开关allclose门自然失败。R002采用显式native_cache_call_parity_v2：真实生成调用/每步fresh缓存重建/KV结构/负对照/同卡独立进程重复性。原allclose与greedy开关比较保留真实诊断，不宣称数学等价；生产5函数AST与R001相同。详见source/gsm8k_execution_cache_v2_20261018/verification_revision.md。


---
Published: 2026-10-18T02:25:51.020491+00:00
Publication: P4dee1f4819774fcb9fe4154753e10dd5
