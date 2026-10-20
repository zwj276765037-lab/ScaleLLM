# E010：BF16真实速度修复已验证，QDQ诊断运行中

共享GPU0合成五轮中位数旧0.220956秒、新0.015279秒（14.461倍），四处翻位负例均拒绝。CPU worker88/88、consumer109/109和模型guard独审10/10通过。

8B BF16四题训练诊断完整终态exit0：逐题持续完成间隔中位数107.437156→9.290226秒，观测11.5645倍；短worker总耗时979.388900→433.238190秒，观测2.2606倍。总耗时包括未减的加载/核验一次性成本，逐题提升与短worker整体提升不可混说。当前GPU0有yqh23186运行，旧基线为同GPU/驱动较早结果，故上述为共享诊断观测值，非独占受控性能资格。

四题prompt字节/输入token/原始全部生成token与文本逐一相同，两个verification的32token前缀相同，原静态baseline manifest/root相同，15阶段顺序与完整exact保持，原nativev2/变异负例门通过。父额外核old/new所有声明artifact hash/canonical identity/请求4ids和逐行身份；详见bf16/parent_independent_comparison_AT002.json。

QDQ a8w4_fp32正串行四题train诊断，未恢复矩阵。正式仍0/39570；所有诊断不作为正式ACC。yqh始终未控制，GPU1/M003不动。

---
Published: 2026-10-18T11:29:53.701797+00:00
Publication: P8d013f2c9106490d83488e28f80592fe
