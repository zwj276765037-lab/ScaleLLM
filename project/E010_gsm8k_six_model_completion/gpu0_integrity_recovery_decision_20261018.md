# E010：GPU0恢复补测与权重完整性决定

2026-10-18，本软件任务负责人依据 AT008–AT010 及 A010 独立复核，在用户原“开始补测、两张GPU”资源预算和常规排查授权内作出技术决定。本记录不是新用户批准，也不改 M003。

## 证据与边界

- R002 已自然失败收尾：smoke 6/30、pilot 0/30、formal 0/30，正式完成/独立验证均 0/39570。
- GPU1（`GPU-d87ce710-76bf-872d-9739-f0d7c9b52533`）同一 BF16 模型在加载器返回、尚未生成时，目标层权重即与 checkpoint 有 16345 个元素/字节差异；连续同步快照间仍有变化，参数 version 保持 0。独立另分配的正确权重 roundtrip 可通过，故不将观察扩大成整卡硬件故障结论。
- GPU0（`GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6`）同版 AT010 的 17 个权重快照全部与 checkpoint 精确相同，两次原生调用的输入、目标输出及最终 logits 均相同。仅目标层通过不替代全模型或30配置资格。
- 独立审核重算两卡34个完整快照及14份差异坐标，无记录不符。原始证据保持，不能用稳定但错误的权重通过 logits 自比来替代输入身份检查。

原始证据：[AT008–AT010汇总](../software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/native_input_diagnosis/analysis_AT008_AT010.json)、[独立两卡审核](../software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/protocol/determinism_review_AT005.json)、[恢复评估](../software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/protocol/single_gpu_integrity_recovery_assessment_AT001.md)。

## 执行决定

1. 暂不将 GPU1 分配给补测。新 R003 的全部30模型/配置固定 GPU0，CPU16–17、原单卡独占锁；不变更驱动、不重启主机、不占用 M003 CPU0–7 或EDA资源。
2. 新增运行时权重身份完整性门：可信 CPU 加载基线到 GPU BF16 复制必须精确一致；QDQ 保持原 GPU、原计算形状和算法，核实际有效静态对象及必要的独立重建；调用前后静态内容必须守恒。非持久 buffer 和模块全局 Hadamard 缓存须纳入，不能只查参数 version。正常 KV/合法动态状态须明确区分。
3. 原 v2 的 logits、KV、反例、同卡跨进程重复性门保持；原 checkpoint、数据、prompt、5-shot、greedy、strict EM及长度/显存门保持。CPU/GPU浮点QDQ变换不被强加为逐位同值要求。
4. 原 R001/R002 冻结副本及原始结果不改。新源码/协议/资源版本另冻结到 R003；重做全部 smoke/pilot，不导入旧6组通过记录，不沿用旧时延与显存估计。
5. A011负责完整性模块、worker及loader可选观察接口；A010负责调度/独立汇总接受门、协议及独立审核；父工程负责人负责共享摘要、R003最终冻结与矩阵真实启动。先有CPU正负例、独立代码审核与GPU0受控训练验证，才能启动新矩阵。

当前为实现与准备，R003尚未真实启动。正式结果仅在30组/39570题完整独立复算后发布；仍不填GSM8K ACC/六项平均。
