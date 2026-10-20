# R003 — SM018固定完整物理实现

Execution state: planned
Verdict: unassessed
Owner: A018（唯一EDA）；A007独立G4/阶段审核，Root集中决定。

沿用M003合同/G2冻结M2+A3+C-P1及原预算、池/80保护/时钟/数值ABI，不重综合、不增候选或sweep。入口是原run_m003_stage.main的implement，外加已双审并冻结的physical_literal_adapter v2（core48+显式3源共51）。

实际输入为R002/AT035原生debug_materialized.dcp（397086017 B，SHA3543a85449d4a988f1eee9f1d7259b6e7ba5e8b55c8ab13d61c6f083a1f24af0）及M003_preplace_package SHA94e3f3350af829d7fd61d4e01988e262b1344697801a062d762a8ca295e98e52。AT035 outer native1仅为已完成POST/preplace后的冗余close_project错误，原失败保留。原pre_place_evidence(create=False)/447源码归档/451输入及当前debug probe已核。真实A007绑定包hash/source_review的G4通过才可原生启动，准备记录不替代此门。

固定执行：restore本版preplace DCP→零apply及原完整restore结构/约束检查→place SSI_SpreadSLLs→phys_opt Default→route Default；原阶段全部reset/CDC/时钟/DRC/资源/接口及失败DCP采集保持。功能/结构、合法route、时序和正式安全分列验收，不承诺一次布通。

单EDA，CPU0–7/max8/nice5，RSS192GiB/MemAvailable48GiB连续30秒/disk30GiB；正常无墙钟或静默强停。无bitstream/板卡/GPU/PPL/ACC，不改保留旧工程及共享其他mission。原始每次AT命令/来源/输入/日志/终态不覆盖；常规修复及受影响验证连续，设计/池/预算/验收变化回Root。

真实A007 G4已通过；完整门后prepare通过且无native副作用。AT001于2026-10-19T18:20:23.378500Z真实启动，实际PID/start与资源/锁/源归档已核。当前进入restore检查，尚无place/route结果。
