# A013 生产完整性性能修复集成

本阶段受父新任务授权：用户明确停止本项目 ACC 并要求修好推理速度；ACC 矩阵保持停止，不创建 R004、不自动恢复。本子任务仍 CPU18–19、CUDA_VISIBLE_DEVICES 空，不运行 GPU、不控制进程、不触碰 yqh/GPU1/M003，无后代。父负责实际 probe/flock/资源核验，A010 负责 protocol/消费者；A013 只改新 helper、worker、新 benchmark、新测试及本 implementation 证据目录。

生产改动：`exp/gsm8k_integrity_bytewise.py` 从 fd26590 候选复制，保留原候选证据。附加分配前资源审计：按实际 contiguous tensor 的 (device,data_ptr,nbytes) 去重，MemAvailable 减 immutable baseline 和 bounded buffer 后仍须至少 80 GiB；审核记录先保存，再决定是否分配。加载 direct SHA、全形 native QDQ、完整字节/逻辑名/元数据/storage/H-cache 和检查频率保留。

worker 明确按 `plan.protocol.integrity_implementation_id=immutable_cpu_chunks_memcmp_full_content_v1` 启用 factory。缺字段为 legacy；显式 null 或未知值拒绝。identity/data identity/manifest 显式记录 fast id，code_identity 同时绑定 fast helper 与 legacy。逐题成功行仍在 postcheck 通过后提交。新增 `performance_timings.jsonl` 记录每次观察/检查/finish 的真实耗时和成功/失败；manifest/summary 汇总，row 拆分 precheck/postcheck、原生生成耗时和 worker 调用总耗时。原 `elapsed_seconds` 和数值/生成/评分代码不改。

benchmark 默认 CPU，不初始化 CUDA。CUDA 必须 `--gpu-uuid` 完整 UUID、相同 CUDA_VISIBLE_DEVICES 和 Torch actual UUID；共享诊断与 exclusive flag 互斥。共享模式限 <=64 MiB+37 bytes、16 MiB chunk、3–5 repeats、自有 CUDA allocation <=1 GiB，并声明 shared_diagnostic_only=true、exclusive_verified=false、model_or_ACC_qualified=false。flag 不证明实际独占；父外部 runner 拿原锁、留 NVML 外部 client/资源证据并决定执行。

准确测试源和版本：[AT001 回执](../AT001/receipt.json)、[依赖源哈希](../AT001/source_dependencies.json)。旧 implementation/AT002 的 fd26590 CPU 证据与此生产 17bdabd3 版本分别保存。
