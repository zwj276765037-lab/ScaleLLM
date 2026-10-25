

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# E011 / R003 运行结果

[负责人维护的本批运行记录](run.md)

# R003 — SM018固定完整物理实现

Execution state: planned
Verdict: unassessed
Owner: A018（唯一EDA）；A007独立G4/阶段审核，Root集中决定。

沿用M003合同/G2冻结M2+A3+C-P1及原预算、池/80保护/时钟/数值ABI，不重综合、不增候选或sweep。入口是原run_m003_stage.main的implement，外加已双审并冻结的physical_literal_adapter v2（core48+显式3源共51）。

实际输入为R002/AT035原生debug_materialized.dcp（397086017 B，SHA3543a85449d4a988f1eee9f1d7259b6e7ba5e8b55c8ab13d61c6f083a1f24af0）及M003_preplace_package SHA94e3f3350af829d7fd61d4e01988e262b1344697801a062d762a8ca295e98e52。AT035 outer native1仅为已完成POST/preplace后的冗余close_project错误，原失败保留。原pre_place_evidence(create=False)/447源码归档/451输入及当前debug probe已核。真实A007绑定包hash/source_review的G4通过才可原生启动，准备记录不替代此门。

固定执行：restore本版preplace DCP→零apply及原完整restore结构/约束检查→place SSI_SpreadSLLs→phys_opt Default→route Default；原阶段全部reset/CDC/时钟/DRC/资源/接口及失败DCP采集保持。功能/结构、合法route、时序和正式安全分列验收，不承诺一次布通。

单EDA，CPU0–7/max8/nice5，RSS192GiB/MemAvailable48GiB连续30秒/disk30GiB；正常无墙钟或静默强停。无bitstream/板卡/GPU/PPL/ACC，不改保留旧工程及共享其他mission。原始每次AT命令/来源/输入/日志/终态不覆盖；常规修复及受影响验证连续，设计/池/预算/验收变化回Root。

真实A007 G4已通过；完整门后prepare通过且无native副作用。AT001于2026-10-19T18:20:23.378500Z真实启动，实际PID/start与资源/锁/源归档已核。当前进入restore检查，尚无place/route结果。

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_fixed_complete_physical](attempts/AT001_fixed_complete_physical) | failed | SM018 fixed complete physical after actual A007 G4: unchanged frozen physical v2/core48, restore exact AT035 preplace DCP then SSI_SpreadSLLs place and Default physopt/route; all original gates retained, no bitstream. | [执行收据](attempts/AT001_fixed_complete_physical/run.json) · [report.md](attempts/AT001_fixed_complete_physical/report.md) |
| [AT002_place_write_replica_proof](attempts/AT002_place_write_replica_proof) | failed | 12_selected_FDCE_48_state_pins_24_URAM_root_pins_read_only; same actual successful place.dcp; no placement/physopt/route; full raw unsupported properties preserved | [执行收据](attempts/AT002_place_write_replica_proof/run.json) · [report.md](attempts/AT002_place_write_replica_proof/report.md) |
| [AT003_place_write_replica_proof_retry](attempts/AT003_place_write_replica_proof_retry) | failed | 12_selected_FDCE_48_state_pins_24_URAM_root_pins_read_only; same actual successful place.dcp; no placement/physopt/route; full raw unsupported properties preserved; retry empty-collection property decoder only | [执行收据](attempts/AT003_place_write_replica_proof_retry/run.json) · [report.md](attempts/AT003_place_write_replica_proof_retry/report.md) |
| [AT004_cached_place_write_replica_proof](attempts/AT004_cached_place_write_replica_proof) | completed | 12_selected_FDCE_48_state_pins_24_URAM_root_pins_read_only; same actual successful place.dcp; no placement/physopt/route; full raw unsupported properties preserved; retry empty-collection property decoder only; grouped native mem… | [执行收据](attempts/AT004_cached_place_write_replica_proof/run.json) · [report.md](attempts/AT004_cached_place_write_replica_proof/report.md) |
| [AT005_successful_place_POST_physopt_route](attempts/AT005_successful_place_POST_physopt_route) | failed | Actual original G4 -> restore exact successful AT001 place.dcp with zeroapply/full structure -> inherit completed place prefix reports -> all original unfinished place POST -> fixed physopt Default/route Default, with actual fres… | [执行收据](attempts/AT005_successful_place_POST_physopt_route/run.json) · [report.md](attempts/AT005_successful_place_POST_physopt_route/report.md) |
| [AT006_successful_place_POST_physopt_route_cwd_fixed](attempts/AT006_successful_place_POST_physopt_route_cwd_fixed) | failed | Actual original G4 -> restore exact successful AT001 place.dcp with zeroapply/full structure -> inherit completed place prefix reports -> all original unfinished place POST -> fixed physopt Default/route Default, with actual fres… | [执行收据](attempts/AT006_successful_place_POST_physopt_route_cwd_fixed/run.json) · [report.md](attempts/AT006_successful_place_POST_physopt_route_cwd_fixed/report.md) |

## 本批问题与交付文件


## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
