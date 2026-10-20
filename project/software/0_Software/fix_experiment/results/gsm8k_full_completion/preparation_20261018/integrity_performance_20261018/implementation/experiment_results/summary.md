# A013 CPU 验证结果

最终候选 `gsm8k_integrity_bytewise.py` SHA256：`fd26590c3b21a3f309042e57c5fb110f33d0d2b8897e4f0e0b5763a864ef9265`。关联 legacy SHA256：`0e11092488523d97acd7ec76776ada669068c70bec1efc190bf5159c43f99121`。本结论只适用于这两个版本；AT001 为此前候选，保持原证据，不与最终源码混合。

CPU AT002：42/42 测试通过，unittest 实测 1.431 秒，进程 exit0。22 项原测试在显式注入候选后继承运行，20 项新增测试覆盖分块比对、SHA 等价、全名/storage/role、immutable baseline、错误终态和派生证据。129 字节的每个位置分别反转 bit0/bit7，共 258 个损坏子例，全部拒绝；scalar/empty 和 12 种 dtype 的 48 个子例通过。三种原生 QDQ 全形重建、不持久缓冲和外部 Hadamard 缓存原测试通过。CPU 未初始化 CUDA。

原始证据：[测试回执](../cpu_validation/AT002/receipt.json)、[原始 unittest 输出](../cpu_validation/AT002/stderr.log)。

CPU 合成 AT002：单 tensor 实际 67,108,901 bytes（64 MiB+37），16 MiB chunk，5 次交替测量。median legacy `tensor_descriptor` 为 0.180306936 秒；candidate full compare 为 0.017537277 秒；该案例实测比值 10.281×。初次 immutable capture 0.186134572 秒，另列、不计入重复检查计时。实际对首、chunk 前后和尾字节的四个损坏反例，两种方法均拒绝；恢复后全覆盖通过。

该案例 immutable baseline 67,108,901 bytes，staging 16,777,216 bytes，CPU buffer 未 pinned；GPU weight replica 为 0。进程 ru_maxrss 从 534,118,400 到 742,891,520 bytes，包含 PyTorch/原 legacy 临时副本/合成输入及完整进程峰值，不能视为候选独占增量。环境 PyTorch 2.10.0+cu128，affinity 18–19，CUDA_VISIBLE_DEVICES 空，cuda_initialized=false。

原始证据：[CPU benchmark AT002](../cpu_benchmark/AT002.json)，含每次耗时、环境、内存、实际覆盖和反例。

判断：CPU 功能/损坏拒绝和该合成性能案例支持候选进一步验证。GPU pinned D2H 路径、全模型内存、真实附着/资格及端到端耗时均未测；没有模型/生成/评分结果，不据此宣称 GPU 或正式补测提速。A010 独立审核与父的新 R/source/consumer 冻结仍为下游责任。
