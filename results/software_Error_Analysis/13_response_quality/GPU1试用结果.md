# GPU1试用结果

2026-10-20 16:25（北京时间），按用户“GPU1尝试用一下”的指令实际测试。**GPU1显存写读完整性检查失败，本次没有在GPU1运行模型。**

| 检查项 | 实测结果 |
|---|---|
| 设备 | RTX A6000；UUID `GPU-d87ce710-76bf-872d-9739-f0d7c9b52533` |
| 同时驻留数据 | 16GiB，64块，每块256MiB |
| 已执行模式 | CUDA底层接口写入全零，再读回与CPU已知零值逐字节比较 |
| 首个失败块 | 编号46（从0计数） |
| 该块错误字节数 | 27,082 / 268,435,456；约0.01009% |
| 首个错误示例 | 块内偏移75,500,800；期望字节0，实际255 |
| 原始错误证据 | 完整27,082个坐标及期望/实际值已保存，独立复核一致 |
| 已比较的数据量 | 93次完整256MiB读回，合计24,964,497,408字节；含重复读取，不代表独立显存容量 |
| 后续模式、算术及模型 | 遇首个错误后停止，均未执行 |
| 结束状态 | 约15.55秒自然退出，显存已释放，无本任务残留进程 |

这个比例只是失败块内的错误字节比例，不能换算成模型数值误差或回答质量损失。已知写入值与读回值不同，足以说明该设备当前运行环境不适合产出本次数值精度实验数据；本检查尚不能区分显存、驱动或传输等具体根因。没有执行设备重置、驱动修改或维修。

完整回答质量实验返回GPU0有限后台等待。原有GPU0任务不受干预，GPU1检查失败不计入算法的实验结论。

证据：

- [原始结果](../../../project/E012_multistage_rounding_precision/experiment_results/runs/R012/runtime/AT004_gpu1_memory_probe/probe/result.json)
- [首个失败块记录](../../../project/E012_multistage_rounding_precision/experiment_results/runs/R012/runtime/AT004_gpu1_memory_probe/probe/first_byte_mismatch.json)
- [完整错误坐标](../../../project/E012_multistage_rounding_precision/experiment_results/runs/R012/runtime/AT004_gpu1_memory_probe/probe/first_byte_mismatch.npz)
- [退出回执](../../../project/E012_multistage_rounding_precision/experiment_results/runs/R012/runtime/AT004_gpu1_memory_probe/external_wait_receipt.json)
- [独立复核](independent_review/gpu1_probe_review.json)
