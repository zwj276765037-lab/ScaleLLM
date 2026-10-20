# A013 完整字节完整性检查性能候选

范围：M004 / SM020 / E010 软件补测的独立候选准备；父负责人拥有新 R、共享摘要、冻结和切换。A013 只写本 implementation 子目录；不改现有 15 份冻结运行源，不操作任何进程、GPU1、M003 或 CPU0–7。执行 CPU18–19，`CUDA_VISIBLE_DEVICES=''`。未启动后代。期望模型/强度 gpt-6.1-sol / xhigh；实际以父 spawn 证据为准，子任务不从请求值推断实际配置。

问题：legacy `tensor_descriptor` 每次读取全部静态 tensor，D2H、`numpy().tobytes()` 和 CPU SHA 重复发生。候选 `gsm8k_integrity_bytewise.py` 显式 factory 接收原模块，不替换 `sys.modules`，只覆写 attached 后的重复内容检查。原 checkpoint 文件身份、CPU/GPU direct SHA、原生全形 QDQ 重建、Hadamard 重建、stage_complete 文件复核和 native_cache_call_parity_v2 保留。

attached 完成后，逐 tensor 捕获私有不可变 `bytes` 分块，对实际保存的块增量 SHA；每项必须等于已验证 baseline_manifest，才能建立 runtime 比较基线。原数学、生成、评分、检查频率、名称和 storage_identity 覆盖均保留。每个 runtime phase 完整枚举全部逻辑名称，元数据/存储相等后逐块拷入一个复用 CPU buffer，拷贝完成后调用 libc memcmp；全部字节相等后才复用原 SHA/root。每阶段记录方法、每名/整阶段 expected/compared/equal byte 数，明确 SHA 是派生复用。failed phase 不提供 derived root。

平台与内存：PyTorch CPU 回归；未来 CUDA 使用单 bounded pinned CPU buffer。CUDA 每阶段每 device 一次起始 barrier，逐块完成同步后比较/复用 buffer，无整套 GPU 权重副本。默认 chunk 16 MiB；immutable host baseline 为实际 distinct contiguous 存储区字节总数，完整模型的约 16–19 GiB 是父任务估计，未在本子任务实测。相同地址/大小的别名可共享 immutable 块，但所有逻辑名称逐次比较。CPU 模式用普通 staging buffer。

兼容边界：仅 native byte order、contiguous strided、非量化 CPU/CUDA tensor；非 contiguous、conj/negative view bits、稀疏/其他设备显式拒绝。scalar/zero-size/NaN payload/负零按 raw bytes 处理。未来若真实模型触及拒绝边界，需新修订和审核，不能静默弱化。

入口与协议见 [protocol.md](protocol.md)。CPU 验证和合成计时按 AT 分开保留原始回执；本候选不能为现有运行追加资格。
