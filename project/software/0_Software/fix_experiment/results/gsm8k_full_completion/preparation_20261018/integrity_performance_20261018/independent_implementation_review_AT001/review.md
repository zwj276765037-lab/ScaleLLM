# A010 候选实现独立审核 AT001

结论：fd26590c3b21a3f309042e57c5fb110f33d0d2b8897e4f0e0b5763a864ef9265 核心在显式连续张量、串行guard及可信host参考范围内得到源码与CPU支持，未发现需修改该核心的算法阻断。尚未接入新R、尚无GPU资格或正式结果提速结论。legacy严格绑定0e110924…91c21。

已核原始42/42日志、回执及delivery各文件身份。独立6项小CPU正负例通过且源前后稳定：非周期字节/跨块与双memcmp方向、非零offset的独立别名对象/不同roles、copy期间storage移动、KeyboardInterrupt终态失败、meta拒绝。审核器首次import路径错误在执行候选测试前失败，原证据保留；修正后新cpu_AT002通过。未初始化CUDA。

CPU合成64MiB+37案例的5次原始耗时中位数和比值均独立重算：legacy0.180306936秒，compare0.017537277秒，比值10.281353×。其capture SHA可由独立合成字节模式复现，4个损坏反例身份齐全。该数据是单CPU tensor、未pinned staging、未含完整guard日志/模型/QDQ与GPU D2H成本，不能外推整模型或完整补测ETA。

源码保障：实际保存的bytes参与capture SHA；tuple/bytes/MappingProxy持有独立不可变参考；每名字/role/元数据/storage检查，所有chunk传输同步后memcmp。NaN/-0按原始字节；空张量保留；非连续与特殊布局明确拒绝，不作静默弱化。CUDA同步次序源码合理，但实际pinned D2H/stream尚未执行，仍须真实GPU证明。

三项放行依赖：

1. 新R消费者必须显式验证method/candidate与legacy SHA、capture逐名SHA/字节/pinning/别名统计、每runtime phase逐名expected=compared=equal和complete/exact/derived-root。当前旧消费者不消费这些新字段，不能直接放行新mode。原checkpoint/nativev2/频率及全量评分门保持。
2. GPU benchmark只能是父独占守护下的payload。当前c9d9e22入口仅接受CVD=0和自声明flag、只记gpu_name；需有限入口适配或等价外部保证，使用完整GPU0 UUID、原锁、真实外部client/资源检查并记录actual UUID，不能把CUDA ordinal当NVML index。当前槽位不独占，禁止启动。
3. 全模型immutable host基线+staging需维持原host/GPU reserve、记录完整内存/时间，并在授权独占GPU0槽实际完成合成CUDA与真实BF16/QDQ资格。CPU数据不能替代。

本轮只写审核目录，未改候选/共享源/摘要，未查询或控制现有GPU任务，未触碰GPU1/M003。新R/切换/consumer接入由父主控负责；完整逐字段清单和证据SHA见review.json。
