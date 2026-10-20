# E012 多级舍入：来源与方法

M005 / SM021 / SM022。用户主对照为「仅输出舍入」「当前实现」，精确oracle单列参考。唯一实现根 `project/software/0_Software/rounding_precision/`；[数值协议](protocol.md) 和 [BF16资源合同](../../../mission/M005_multistage_rounding_precision/real_capture_gpu0_contract.md) 定义范围。

当前实验在固定同一qa/zp/qw、ScaleCode code/shift及全组次序下，比较任意精度有理数参考、仅末端half-away，以及生产V5表达式提取的CPU恢复。生产算法/硬件/数值规则不变。三profile分别为Attention、Gate/Up、Down-S32/shift12/S45/S54；CPU模型不等于GPU Triton/RTL逐bit验证。

旧真实归档仅float32[32768,32]+op标签，缺点积、整数码、scales及逐组位置：[有界inventory](../experiment_results/runs/R001/attempts/AT001_cpu_local_rounding_pilot/data_inventory.json)。现有真实数据为新采集单校准文本的BF16模型轨迹，分别固定32与128tokens，取层0/15/31×7 Linear×首末token×4通道，每个长度168输出/29,184完整Group32。Down的BF16输入适配S32，不声称生产SwiGLU轨迹。

采用LlamaModel+accelerate meta构造，每参数独立safe_open→blocking GPU copy→删除CPU张量/关闭映射；避免失败的HF5.3整批句柄驻留。GPU0固定UUID，2线程、RSS8GiB、ownGPU24GiB、共享free8GiB、300秒；没有扩大预算。环境Python3.10.19/torch2.10.0/transformers5.3.0/accelerate1.13.0/numpy2.2.6/safetensors0.7.0，CPU回放Python3.12。逐运行manifest保存具体代码/命令/输入SHA。

全部290base参数消费15,009,849,344B，逐tensor body SHA聚合 `e192e33a74c51f7ad3e53b14bd32e3d0c3308a325d7f2b5d013bc1dc018547c6`；仅省略未执行的lm_head，仍不宣称完整checkpoint文件hash。21模块原始权重行及q/code/shift跨32/128完全一致：[冻结权重核对](../experiment_results/runs/R002/attempts/AT005_cpu_replay_bf16_128token/frozen_weight_crosscheck.json)。保存实际BF16激活/加载权重行、原checkpoint切片、整数lane，所有引用文件SHA实核。source_format_id=null、trajectory=bf16，adapter目标格式另列，永不冒充当前V5生产证据。

v1/v2及捕获版本有独立manifest；原始结果不回写。32capture后runner只补来源核验注释，当前/128使用新runner，算术模块未变；A014已收到此边界。合成pilot、真实32、真实128独立分母，图仅来自真实回放。没有全32层/全V5传播/非线性/PPL/ACC结论。

A014已分别独审32/128的真实源链、生产前端/权重量化、点积和精确恢复，均0 mismatch；没有独立重哈希全部15GB参数body，实际采集hash与84行独立读取的证据范围分别陈述。两个长度共享文本和前32tokens，不作独立样本或模型总体推断。
