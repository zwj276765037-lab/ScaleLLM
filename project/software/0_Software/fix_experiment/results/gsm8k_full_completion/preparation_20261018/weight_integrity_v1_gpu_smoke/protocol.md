# 全模型静态内容门的受控训练 smoke

工程范围：M004/SM020/E010；父主控已授权本修复与GPU0训练验证，正式R003矩阵由父负责冻结和启动。GPU1暂不用于补测，不作硬件故障结论。

资源：只用GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6，暴露cuda:0；CPU16,17，各运行2线程；原GPU0 flock贯穿整进程。worker在模型加载前要求MemAvailable≥80GiB、GPU空闲≥24GiB。正常无墙钟/静默强停，无EDA。

源：exp/gsm8k_weight_integrity.py及worker/loader可选只读观察接口；原QDQ实现不改。A010独立维护protocol校验器、matrix和summary。新plan为source/gsm8k_gpu_integrity_v3_20261018/plan.json。冻结R001/R002源、plan与原始结果均只读。

检查：原checkpoint文件完整SHA → CPU加载全部named_parameters/static named_buffers（tied别名、CPU独立RoPE重构） → 全GPU复制内容精确；QDQ使用原GPU/fullshape构造器独立重建，覆盖有效非persistent缓冲及全局_H_CACHE；setup、完整verification单元、每次样本生成前后、阶段结束全部检查内容哈希和tensor/storage身份。未知静态增删、内容/身份变化拒绝；原native_cache_call_parity_v2所有门保持。

CPU证据：专用22项（含三类原QDQ构造器及内容/身份/外部缓存负例），最终联合82项在weight_integrity_v1_cpu/AT004稳定通过；A010消费者89项及源码审核另由A010保存。

GPU顺序：Llama-3.1-8B-Instruct/bf16/AT001先跑4题smoke及原v2门；如无阻断，再同模型a8w4_fp32的独立AT001验证全shape GPU QDQ重建。两组均只读固定train输入。每次真实PID、UUID、路径、原始退出状态通过实际消息报告。

验收：worker自然complete、4题完整、原v2 passed、integrity terminal complete/qualified、shared validator通过、原始张量/phase全覆盖并由A010独立审核；完整性临时重建峰值计入load_attach，KV verifier临时峰值独立计。结束后验证进程退出、原锁可用、启动源码SHA保持。上述局部通过不替代30组重新资格或1319题formal验收，不自动启动matrix。
