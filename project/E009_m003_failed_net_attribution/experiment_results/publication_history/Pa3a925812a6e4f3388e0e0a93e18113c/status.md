# E009：SM013原生只读载图中

execution_state: running  
verdict: unassessed

R001/AT001于2026-10-18 00:40:06Z实际进入OPEN_CHECKPOINT_BEGIN；原生Vivado254004/start5572559，监督253912/start5572338，leader253914/start5572545，单EDA锁持有、CPU0–7/nice5已核。当前原生载图中，未取得全量归因；无工具/资源阻断。监督器正常无墙钟/静默强停。

下一步按冻结清单完成原生冲突网canonical/全端点分类和固定深查，核本次native_route_status与基线547548/702396的关系，交A007核口径与G1。未知项据实保留；不热改包、不选型/改生产RTL、不重跑implementation，不运行bitstream/板卡/GPU/PPL/ACC。


---
Published: 2026-10-18T00:40:57.240756+00:00
Publication: P67891491f61a4ad2ac24030cf8acc1a3
Execution state: running
Research verdict: unassessed
Applicability: Native read-only start verified; open_checkpoint in progress; attribution/G1 not yet assessed.
Evidence:
- project/E009_m003_failed_net_attribution/experiment_results/runs/R001/attempts/AT001_failed_route_full_attribution/preflight.json
- project/E009_m003_failed_net_attribution/experiment_results/runs/R001/attempts/AT001_failed_route_full_attribution/cpu_checks.json
- project/E009_m003_failed_net_attribution/experiment_results/runs/R001/attempts/AT001_failed_route_full_attribution/offline_reuse.json
- project/E009_m003_failed_net_attribution/experiment_source/prepared_manifest.json
- project/E009_m003_failed_net_attribution/experiment_results/runs/R001/attempts/AT001_failed_route_full_attribution/native_start_observed.json
- project/E009_m003_failed_net_attribution/experiment_results/runs/R001/attempts/AT001_failed_route_full_attribution/input_bindings.json
- project/E009_m003_failed_net_attribution/experiment_results/runs/R001/attempts/AT001_failed_route_full_attribution/independent_prelaunch_accepted.json
