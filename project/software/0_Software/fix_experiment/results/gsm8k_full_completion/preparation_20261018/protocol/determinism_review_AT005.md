# AT009/AT010 双卡同脚本生命周期独立审核

A010 仅 CPU8–9、CUDA 不可见。独立验证 34 个完整权重快照的文件与内容 SHA、14 份差异文件的完整坐标及原/新 BF16 words，以及所有逐阶段变化计数，零不符。两次诊断源码、plan、package、runtime flags 相同，实际 GPU UUID 和 CPU 分配正确。详见 [审核数据](determinism_review_AT005.json) 与 [复算脚本](review_weight_lifecycle_AT009_AT010.py)。

| 控制 | AT009 / GPU1 | AT010 / GPU0 |
| --- | --- | --- |
| loader 返回后连续 3 次快照对 checkpoint | 各 16345 元素不同 | 全部 exact |
| 这 3 次之间内容变化 | 35、2 元素 | 0、0 |
| 17 个权重快照 | 原参数始终不同；独立复制的 3 次正确 | 17/17 checkpoint exact |
| 原参数版本 | 始终 0 | 始终 0 |
| 两次 native 输入 | exact | exact |
| 两次 up_proj 完整输出 | exact | exact |
| 两次最终 logits | maxabs 0.125 | exact |

快照在显式 `cuda.synchronize()` 后执行默认 blocking CPU copy，再 `.clone()` 并立即保存独立文件。独立 raw 复算验证了差异；CPU allocator 在旧对象释放后重用地址不等于已保存文件共享可变别名。原 GPU 参数 storage/pointer 保持不变，单靠 `_version` 不能发现这些已保存的字节差异。首次三快照发生在任何 native 调用和本诊断探针安装之前。

登记的 model/model.model/layer25/MLP/up_proj 及全局 forward hooks 均为空、相关模块没有 parametrization；此 inventory 仅覆盖列出的层级，不是全模型所有子模块清单。另分配的正确 checkpoint 张量在同一 GPU1 进程中三次 roundtrip 全等，说明失败与原参数的具体加载/分配/生命周期相关，仍不能确定故障来源。

证据支持暂不再分配 GPU1，并另开 R 在 GPU0 上统一运行全部 30 配置、重新通过 smoke/pilot 与原硬门。这是避开已观察失败资源的操作建议，不是整卡硬件故障或健康认证。GPU0 本次只验证了一个参数和一条提示；新矩阵仍须完整权重身份与静态对象守恒，不能把本局部结果当作 full-model 或 formal 放行。

后继最小实现见 [单卡恢复及完整性建议](single_gpu_integrity_recovery_assessment_AT001.md)：checkpoint/CPU→GPU 复制 exact；原 GPU QDQ 浮点变换保持，可信附加后基线及同 shape 独立重建；覆盖 nonpersistent buffers 和全局 Hadamard cache；完整推理单元前后全静态内容守恒。无生产源修改、无新正式结果、无已验证修复。
