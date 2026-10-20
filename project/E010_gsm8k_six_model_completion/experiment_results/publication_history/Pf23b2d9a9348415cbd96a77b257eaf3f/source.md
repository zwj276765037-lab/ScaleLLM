# E010：GSM8K双GPU执行来源

用户已授权在当前exp实现并执行、确认两张GPU。六冻结checkpoint×五配置、原5-shot raw greedy strict EM、test1319/格，max8192/new4096、BF16 eager、原生KV。实际执行plan与14份源码快照在raw R002 frozen_inputs/frozen_sources，数据和权重SHA均绑定。

R001原cache开关allclose门自然失败。R002采用显式native_cache_call_parity_v2：真实生成调用/每步fresh缓存重建/KV结构/负对照/同卡独立进程重复性。原allclose与greedy开关比较保留真实诊断，不宣称数学等价；生产5函数AST与R001相同。详见source/gsm8k_execution_cache_v2_20261018/verification_revision.md。

R003正按gpu0_integrity_recovery_decision_20261018.md准备：暂不分配GPU1，全部30组固定GPU0；增加运行时权重内容身份门，原v2门和评估算法保持。新计划/源码已实现并通过CPU正负例，GPU0 BF16受控验证已通过；QDQ验证进行中，尚待最终审核冻结与真实矩阵启动。

用户后续明确要求修复GPU1；A012 /root/gpu1_repair已真实派发，GPU1/CPU18–19/原锁，原始CUDA有限模式检查。父在项目内下载并仅解包官方580.159.03工具，核归档与SHA；没有系统驱动安装/重启。


---
Published: 2026-10-18T04:34:23.900737+00:00
Publication: Pc9a4af7aeeab4eafa540984873e6ecda
