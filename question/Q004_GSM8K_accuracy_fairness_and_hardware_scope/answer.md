# Q004回答

本次速度修复保留原算法与评测协议，未发现由修复引入的ACC公平性变化；不能由此推导当前GSM8K算法参考ACC就是硬件ACC。

修复只改变重复静态权重核验方式：可信不可变CPU字节完整比较替代每次重算SHA。加载/checkpoint SHA、原生QDQ重建、逐题/verification/terminal检查频率和完整names/bytes/storage覆盖不变。checkpoint、tokenizer、prompt/5-shot、raw greedy/native cache、上下文与token预算、strict EM不变。正式仍test1319题/组、context8192/max_new4096；速度诊断使用train4题/max_new64，不能混入ACC。BF16与a8w4_fp32两配置各四题原始输出全部token一致，15phase/root保持，父及独审通过。其余28组和正式test尚未完成，新版不能沿用R003资格/行。

五配置为算法比较矩阵：BF16基线、a8w8_fp32、a8w4_fp32、a8w4_fp16对照，reference_qdq才是ScaleCode方案。算法文档/代码一致的核心为Hadamard32、Group32、A8非对称MinMax含零、AttentionW8/MLPW4、ScaleCode code8+shift8，未增加percentile/校准式clipping。FP32/FP16在这些配置名中指scale载荷；实际反量化后线性计算为BF16，不能据名称宣称FP32全矩阵计算。

当前真实manifest明确evaluation_role=algorithm_quality_reference、native_attention_rope_kv=true、hardware_fixed_point_frontend=false、hardware_numeric_contract=not_applicable。QDQ适合算法数值质量比较，保存反量化folded weight并以F.linear计算。不能据它宣称逐位实现了format05的定点Hadamard、有限位宽guard/accumulator、舍入/饱和、SiLU/Softmax LUT、固定RoPE/KV等，也未执行真实FPGA推理。

硬件合同另规定MLP0x48384605、Down S45/S54/S32、Attention独立格式0x48384103及KV12等；当前硬件context限128，而GSM8K算法协议context8192。这些范围不同，不能悄悄截断或直接把算法长上下文分数贴为硬件分数。

后续硬件ACC必须独立使用当前format05整数twin及matched BF16，明确相同数据/提示/上下文或事先约定可复现的长上下文执行方式，核逐组量化metadata/整数、逐层输出和舍入/饱和/格式计数器，取得RTL对应证据；真实硬件ACC还需Host→FPGA→Host闭环。当前尚未完成这些硬件GSM8K验证，未启动新实验。保留现有算法表，同时硬件结果单独命名、逐项注明数值/上下文/验证阶段。

证据：

- [修复报告](../../project/software/0_Software/fix_experiment/results/PERFORMANCE_REPAIR_20261018.md)及其原始/独立核验链接。
- [算法后端明确角色](../../project/software/0_Software/fix_experiment/exp/run_eval_worker.py:240)。
- [五配置定义](../../project/software/0_Software/fix_experiment/exp/six_model_matrix.py:120)。
- [ScaleCode算法权威说明](../../project/software/0_Software/introduction/01_final_scalecode_algorithm.md)。
- [硬件上下文与数值合同](../../project/hardware/source/design.md:10)。
- [候选正式评估配置](../../project/software/0_Software/fix_experiment/source/gsm8k_execution_bytewise_integrity_20261018/plan.json)。
