# 验证与后继接入协议

CPU 命令，在项目根执行；`P` 仅为本 implementation 目录。每次使用新 AT，原始证据不覆盖。

```bash
P=project/software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/integrity_performance_20261018/implementation
taskset -c 18,19 env CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/user/anaconda3/envs/zhouwenjun/bin/python -B "$P/run_cpu_validation.py" --attempt AT003
taskset -c 18,19 env CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/user/anaconda3/envs/zhouwenjun/bin/python -B "$P/benchmark_bytewise_integrity.py" --device cpu --mib 64 --chunk-mib 16 --repeats 5 --output "$P/cpu_benchmark/AT003.json"
```

验收：legacy loader/QDQ positive 与 corruption controls 均通过；原生三种 QDQ fullshape 重建、checkpoint 源绑定、不持久缓冲、H-cache、别名、名称/shape/dtype/storage 必须覆盖；每字节首/末 bit、跨块边界和尾块、NaN payload/负零、空/scalar 必须拒绝损坏。已保存 immutable bytes 的 SHA 必须等于 direct SHA baseline。拷贝或同步异常必须 terminal fail closed。phase 只有 evidence full_coverage_exact 且完整 inventory/storage/bytes 相等才能 derived 原 SHA/root。

benchmark 使用一个合成 uint8 tensor，实际字节数为 MiB+37，覆盖尾块。分别预热，交替记录 legacy descriptor 和候选 compare 的 5 次耗时、中位数、实际字节、ru_maxrss、buffer/base 大小和环境；首字节、chunk 前后与末字节实际损坏，两种方法均必须拒绝。计时不包含基线初建；capture_seconds 另列。没有模型推理或吞吐结论。

仅当父负责人确认 GPU0 独占槽位，才可执行以下未来命令；A013 未执行该命令。GPU1 保持暂停。资源额度须由父核对，flag 本身不能证明独占。

```bash
taskset -c 18,19 env CUDA_VISIBLE_DEVICES=0 PYTHONDONTWRITEBYTECODE=1 /home/user/anaconda3/envs/zhouwenjun/bin/python -B "$P/benchmark_bytewise_integrity.py" --device cuda:0 --exclusive-gpu0-slot --mib 64 --chunk-mib 16 --repeats 5 --output "$P/gpu0_benchmark/AT001.json"
```

后继接入由父在新 R 的新冻结源中完成。可使用 `importlib.util.spec_from_file_location` + `module_from_spec` + `exec_module` 读取候选，不需要插入/替换 `sys.modules`；再调用 `Candidate = candidate.make_integrity_class(original_integrity_module)`，按原构造参数建立 guard。当前 worker 中没有热替换。新 R 的完整性消费者应显式核方法身份/候选与 legacy SHA、immutable capture 每名 SHA 等价、每阶段完整逻辑名称与逐名 byte counts、exact/derived-root 一致；不将这些 phase 误标为重新 SHA。保留 checkpoint_static_content_v1 和 native_cache_call_parity_v2 的原逻辑合同，由父/A010接受新实现证据后冻结。GPU 小合成基准通过仍需新的真实加载/资格/运行证据。
