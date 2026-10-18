# E008：AT004运行中，PDU后已实际恢复

execution_state: running
verdict: unassessed

用户新的“可以继续了”已解除PDU暂停。AT004于北京时间17:23:05真实启动，当前初始化/恢复正式父网表。39源/b9dc、144输入/父8451、进程PID/start、CPU0–7/nice5与单EDA锁已核。[启动事实](../experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/native_start_verified.json)。完整pre-place/place/physopt/route待实际完成，不把恢复或启动当物理成功。

AT003原始暂停/14项收尾/无新DCP证据保留；本次新AT从正式preplace父图重做原流程。原同C01常规修复登记与连续重试委派已恢复，不新增用户门；实质选型/架构/验收变化仍归Root。

正常无墙钟/无输出强停，单EDA及RSS192GiB/Mem48GiB30s/disk30GiB保护保持；无bitstream/GPU/板卡/PPL/ACC，旧工程只读。


---
Published: 2026-10-17T09:25:06.578918+00:00
Publication: Pa2056d0d6dfa4db09df418591b2ef659
Execution state: running
Research verdict: unassessed
Applicability: Explicit user resumed after PDU. AT004 true native start/39archives/144production/parent/unique lane verified; full native qualification and complete physical flow pending. AT003 preserved.
Evidence:
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/started.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/input_bindings.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/native_start_verified.json
