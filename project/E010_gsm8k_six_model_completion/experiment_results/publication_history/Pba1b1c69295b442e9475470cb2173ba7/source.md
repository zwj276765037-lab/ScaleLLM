# E010：ACC暂停期间的GPU0推理速度修复

用户已要求停止ACC并修复速度，最新明确“yqh的不要动，只停止我们的”。R003及原始失败/中断证据保留，不自动恢复矩阵。GPU1、M003/EDA及CPU0–7不触碰。

生产worker显式接入 immutable_cpu_chunks_memcmp_full_content_v1：加载/checkpoint/原生全形QDQ SHA来源核验不变，逐题前后/verification/terminal完整检查频率不变；重复检查改为有界pinned D2H与不可变可信CPU字节逐一精确比较，完整相等后才派生旧root，清楚标记非fresh SHA。全names/metadata/storage/buffers/Hadamard cache覆盖保持；capture后host保留80GiB。

本版数据、5-shot raw greedy/strict EM、BF16 eager/native KV及native_cache_call_parity_v2不变。九个关键生成/提示/评分函数AST与R003相同。新mode及双helper来源、capture SHA和每phase逐字节覆盖由consumer显式核查；新旧模式不能混用。16源诊断快照和独立plan存shared_model_diag_AT001。

当前仅固定GPU0四题train/64token共享速度诊断，非矩阵/ACC恢复。原flock、实际UUID、已知外部客户端、旧三个scope最大peak×1.2+8GiB free与host120GiB守护；外部yqh23186不控制、不要求退出。

---
Published: 2026-10-18T11:29:53.701797+00:00
Publication: P8d013f2c9106490d83488e28f80592fe
