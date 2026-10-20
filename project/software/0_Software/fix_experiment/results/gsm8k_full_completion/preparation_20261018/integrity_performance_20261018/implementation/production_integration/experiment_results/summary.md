# A013 生产集成 CPU 结果

AT001 联合 CPU 回归 88/88 PASS，unittest 3.062 秒，exit0。包含 56 项新入口/完整性测试及 32 项原 worker/cache v2 回归。GPU metadata 在 worker 控制流测试中显式 mock，未初始化 CUDA；这些控制流测试不构成 GPU 运行或真实 checkpoint 推理证据。测试同时覆盖原生三 QDQ 重建、H-cache、每字节损坏、SHA 等价、精确 80 GiB 边界、内存不足时 snapshot 分配未调用、未知/null id 拒绝、双源绑定、逐 check 计时及 postcheck 失败不提交成功行。

原始证据：[receipt.json](../AT001/receipt.json)、[stderr.log](../AT001/stderr.log)、[stdout.log](../AT001/stdout.log)、[source_dependencies.json](../AT001/source_dependencies.json)。早期开发负例出现 6 个测试 stderr 捕获 fixture 错误（redirect_stderr(None) 令 argparse 无 write 目标），修为 StringIO 后本回执全部通过；未更改生产拒绝逻辑来通过测试。

生产 CPU benchmark：67,108,901 bytes，16 MiB chunk，5 次交替。legacy median 0.179636705 秒；candidate median 0.016745092 秒；该 CPU 单 tensor 实测 10.728×。实际首/chunk 前后/末字节损坏反例两法均拒绝。baseline 67,108,901 bytes，buffer 16,777,216 bytes，无 GPU 权重副本。MemAvailable 实测 523,620,306,944 bytes，扣 baseline+buffer 后 523,536,420,827 bytes，80 GiB guard 通过。详见 [CPU 原始 benchmark](../AT001/cpu_benchmark.json)。

测试版本：helper `17bdabd32e792391622239b32ad81e316fa2ccd688310b4a9fb9bb3f46146542`；worker `80aa1938eed007445f764aa45bfde59d404796278782e7d1d63732dee6f29d4f`；benchmark `6ff9dbf8b1a359d87eb898f689da6c876ba6f6647abd4c14fa4bde5a653cd6de`；legacy `0e11092488523d97acd7ec76776ada669068c70bec1efc190bf5159c43f99121`。A010 shared protocol 的测试时 SHA 另见回执，后续其改动须由父按版本联合验收。

适用性：本子任务只证明该版本 CPU 功能和该合成案例性能。GPU pinned copy、真实静态内存和端到端速度仍由父有限 probe/实际资格验证；不据此恢复 ACC 或承诺全模型提速。
