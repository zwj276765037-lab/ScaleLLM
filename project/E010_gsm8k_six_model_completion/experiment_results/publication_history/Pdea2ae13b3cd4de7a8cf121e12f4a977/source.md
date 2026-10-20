# E010：GPU0推理速度修复已完成有限验证，ACC保持暂停

用户当前授权为停止ACC并修复推理速度，最新资源约束“yqh的不要动，只停止我们的”。当前ACC矩阵没有恢复，两次四题训练诊断已结束。GPU1与M003/EDA未操作。

生产worker按新配置显式选择immutable_cpu_chunks_memcmp_full_content_v1。原checkpoint_static_content_v1、native_cache_call_parity_v2、完整加载/文件SHA/原生全形QDQ重建、每题前后及verification/terminal全部阶段保持。重复阶段改用16MiB pinned暂存与可信不可变CPU字节完整比较，只有覆盖全部字节且metadata/storage/名字一致后才派生原SHA/root；不伪称fresh SHA。所有参数、静态/非持久buffer和Hadamard cache仍覆盖，capture后host保留80GiB。

GPU0固定UUID78b42905…、原flock、单worker串行、CPU16–17。诊断仅Llama3.1-8B的BF16及a8w4_fp32，各四道train/最大64token，当前与yqh23186共享GPU0，不声明独占或完整矩阵资格。数据/5-shot提示/生成/评分9个关键函数AST与R003相同；四题所有输出token逐一相同。

GPU诊断和16源独审完整结束后，仅补强matrix readiness要求canonical worker/run_eval/protocol/双helper来源，缺项/未知mode拒绝；120 CPU回归通过，其他15生产源均为已GPU验证版本。本版完整16源及快照见release_sources.json。待恢复候选配置source/gsm8k_execution_bytewise_integrity_20261018/plan.json明确execution_authorized_this_turn=false；没有R004或新ACC。

---
Published: 2026-10-18T11:43:18.774273+00:00
Publication: Pba1b1c69295b442e9475470cb2173ba7
