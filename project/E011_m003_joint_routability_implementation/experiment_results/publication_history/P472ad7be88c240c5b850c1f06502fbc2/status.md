# E011 当前状态

execution_state: failed
verdict: inconclusive
applicability: AT028 native INIT/link_design executed; INIT POST registry guard failed before OPT. Same48source42dafce3; no design/algorithm verdict.

AT028于11:56:29.726006Z自然native1/stop=null/无残留结束；原生link_design成功，init.dcp及INIT时序/DRC/CDC等已保全。194原/归档输入、48源及17个PID/start退出/锁释放已核。旧running摘要已纠正。

A018正在按授权连续修复入口上下文检查：source project overlay为global implementation-only/LATE/TCL；native generated driver创建临时in-memory GateLvl工程并read_xdc -unmanaged，实际INIT registry出现USED_IN_SYNTHESIS1。尚须完整绑定FILE_TYPE等属性及实际read/apply来源，不删除guard或预判无害。优先复用已有真实INIT检查点补跑，不能写成重新执行INIT；不重新综合/不扩大诊断。

G4/place/route未开始。原48源与失败证据先保全，普通修复与受影响回归后新AT真正启动；正常进程无墙钟/静默强停，原单EDA/资源保护与禁区保持，无observer/模型常驻。


---
Published: 2026-10-19T12:41:27.530761+00:00
Publication: Paaf15d0ed61141bda28a05b38f1a83cf
Execution state: failed
Research verdict: inconclusive
Applicability: AT028 natural native1 caused by actual temporary-project registry mismatch; no OPT/G4/place. Sources and original failed run preserved; ordinary repair in progress.
Evidence:
- project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT028_native_init_opt_preplace/evidence/jobs/native_pre_place/status.json
- project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT028_native_init_opt_preplace/evidence/AT028_owner_terminal_and_input_closure.json
- project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT028_native_init_opt_preplace/evidence/AT028_two_warning_classes_one_shot_attribution.json
