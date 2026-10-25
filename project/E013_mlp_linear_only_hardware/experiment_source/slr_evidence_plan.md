# M006 SLR 验证取证计划

状态：R004/AT001_impl 已自然FAIL/0survivor；R005/AT001_physopt_slr 已于UTC13:27:19真实启动，只读physopt DCP，当前原生查询结果待采。用户核心问题是减少 FPGA MLP 操作是否缓解既有 SLR 困扰，不能只用总 LUT/FF 下降回答。

## 范围和身份

优先读取当前实现已生成的日志、hier utilization、route/timing/DRC/CDC 报告。缺少的物理证据只在一个受 board profile 保护的只读会话内从现有 DCP 收集，不重做 opt/place/physopt/route，不改 RTL/约束，不写回原 DCP。32 CPU affinity、192 GiB RSS、maxThreads8、MemAvailable64 GiB/30秒、磁盘30 GiB、唯一重EDA owner继续适用。

每个 DCP 绑定绝对路径/SHA/字节数、原 attempt/result、源 manifest、器件/工具/时钟/约束身份、实际阶段和放置/布线状态。先查同阶段配对：优先旧新 post-place 对比；若只有旧 failed-route 与新 routed，则分别标明实际状态，不能混作同阶段百分比。若当前终态未保存已布局 DCP，只能用现有原报告/日志，不把 optimized 未布局 DCP 当成布局几何实测，也不为取证重跑实现。 当前冻结build在route_design抛错后跳过主线routed.dcp及紧随其后的route_status保存；但外层catch仍会在真实失败设计上继续独立采util/timing/DRC/CDC/route_status，按实际成功产物保留为失败route会话证据。末个physopt/placed DCP只代表对应前序状态，不能当作失败route网表/route overlap的证据，也不为补DCP或报告盲目重跑route。

## 精确历史范围与新映射

历史依据为新根内 `project/E011_m003_joint_routability_implementation/experiment_results/summary.md` 和 `runs/R004/attempts/AT001_failed_route_driver_region_localization/evidence/offline_attribution/actual_driver_module_ranking.tsv`，对应 M003 R003/AT006 失败 route 及 R004/AT001 只读归因。

共同前缀 P=`scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute`。

| 原范围 | 新范围/处理 | 历史含义 |
|---|---|---|
| P/u_mlp/u_serial_command/u_shared_compute/u_branch1 | P/u_mlp/u_shared_compute/u_branch1 | 176163 canonical conflict nets，保留重共享核，不能称已删除 |
| 同上 branch0 | P/u_mlp/u_shared_compute/u_branch0 | 94638，保留 ingress/共享核 |
| P/u_mlp/u_serial_command/u_gate_scheduler/u_swiglu | 实际 netlist 确认不存在 | 19406，仅历史 conflict 归因数，不是新SLL节省预测 |
| 旧 GU projection/repack | P/u_mlp/u_gate_scheduler/u_projection_repack | repack保留，独立查分布/高fanout/跨界 |
| 旧 Down S54 调度/共享核 | P/u_mlp/u_down_scheduler 与共享 branch0/1 | 共享核同时服务GU/Down；物理单元不能按运行opcode静态拆成两份 |
| Attention projection/input/weight_frontend | P/u_attention 对应精确范围 | 保留对照，不能把Attention input热点混称删除 |

固定旧窗口只作空间关联，另外报告新布局实际最拥塞窗口，避免热点迁移后只看旧坐标：

- projection4772→SwiGLU branch1：INT_X57Y687，SLR2/X3Y11；该宽链已删，查新对应区域与新峰值区域。
- parent_head1299：SLR2/X1Y10→branch0 ingress SLR0/X1Y3；跨三SLR结构仍有对应，需要实测。
- paired_weight184：SLR1/X3Y9→Attention weight_frontend SLR1/X3Y6/7。
- d0_smc rdata：SLR2/X3Y10→Attention/input/meta SLR1。

旧canonical冲突/endpoint计数不等于SLL实测，E006更早的SwiGLU SLR1位置也不混入M003放置。

## 一次会话内的有界原生报告

1. `report_utilization -slr`：整板各SLR CLB LUT/FF/BRAM/URAM/DSP与packing；全板正式LUT计数与primitive计数分别保留。
2. 若内置表未给各SLR占用CLB站点，最多按3个SLR做原生批量关系查询：SLR→SLICE sites→placed cells→occupied SLICE sites，记录容量/唯一占用站点。UltraScale+按唯一SLICE站点表示CLB占用，不以LUT数除8估算。可对少数选定层次使用原生filter；不逐个百万cell调用Tcl getter，不混用字符串与原生对象集合。不同层次占用站点可能重叠，不可简单相加。
3. `report_slr_crossing -max_nets 40 -file ...` 一份整板报告；再用一个 `-cells` 精确层次集合（MLP、两branch、Down scheduler、GU repack、Attention相关对照）报告分SLR资源、跨界/SLL、驱动层次和fanout。2025.2命令不使用2026.1新增的 `-hierarchical_depth`。
4. `report_design_analysis -congestion -min_congestion_level 3` 一份报告，保存水平/垂直拥塞窗口、位置、级别与关联模块。此命令的congestion模式是整板范围，即使指定cells也不能宣称仅局部。低于level3没有该报告的信息，不能当作精确零拥塞。
5. `get_timing_paths -inter_slr data_crossing -delay_type max|min -sort_by slack -max_paths 100 -nworst 1`，分别保存跨SLR最差setup/hold；再各取最多100条 `-slack_lesser_than 0` 的跨界违例。显式按slack排序，避免按group排序时max_paths成为逐group上限；原生返回数另核不超过100。用原生 `report_timing -of_objects` 和 `report_design_analysis -of_timing_paths` 输出路径/网延迟/逻辑延迟/SLR_CROSSINGS/起终点。总计最多400条path，不扫描全部net；若返回100条，明确是截断上限，不称总违例数。优先直接复用现有全局WNS/TNS/WHS/THS及route状态，避免重算全套。
6. 对SLL提示与旧热点，只在报告返回的最高fanout/关键跨界路径中关联上述scope/窗口，必要时查询少数精确net。保留当前Place30-1229原文及100条显示上限，不据此认定总数或忽略其实际时序影响。

报告命令失败、无匹配、无已布局数据均显式记PARTIAL/NOT_AVAILABLE，不用 `-quiet` 吞错构造PASS。所有新报告/脚本/配置/原生退出码/资源日志/DCP输入及输出SHA写独立新attempt，原失败和当前冻结证据不改。

## 最终结论尺度

- 分别回答：删除逻辑是否真实不存在；每SLR资源与CLB packing是否下降/更均衡；新峰值及旧热点拥塞是否缓解；实际跨界/SLL/网延迟是否改善；是否合法route、setup/hold及跨界违例是否闭合。
- 全局资源下降不能单独证明SLR改善；shared core/Down/repack的老热点结构仍在，必须正面报告残留。
- 若新配置合法route且原热点/跨界压力有可比改善，可表述本次配置支持缓解。若仍拥塞/违例，必须独立判断局部压力是否下降和是否足够布通；只有局部指标实测支持时才称局部减轻，不能从资源下降直接推出，也不能从仍拥塞直接推出完全无改善。阶段/约束/源版本不等价时标限制，不能宣称单因素因果、全部生产运行或板级通过。

## 离线入口准备（非原生取证结果）

`slr_probe/run_slr_probe.py` 与 `slr_probe/inspect_slr.tcl` 为新只读入口，未加入运行中的104项生产冻结输入。R005/preparation/AT005_cpu 保存25个CPU用例、源码快照、Python编译、系统Tcl8.6.14语法完整性检查及各输入SHA；均通过，未启动Vivado。AT001_cpu另存真实active parent的check-only拒绝日志。AT003已修独立审核发现的routed历史SHA锚、report_timing互斥参数和native退出码准入问题，AT004再加最多4个代表新窗，AT005修正真实终态独立表头/North Dir/空格箭头格式；旧AT001–004记录保留，不扩大为原生命令证明。

原生执行必须在R004父attempt普通native0/1自然终态、stop=null、输入无漂移、所有owned进程退出后；signal/缺失/未知rc拒绝。入口重新核父源快照、原成功qualification、DCP哈希和该stage原生完成/导出证据；所有stage均核当时保存的DCP及log-prefix观察。routed需由`observe_routed_checkpoint.py`在原父root birth活跃、父尚未终态、原生已确认完成导出时记录，不能只读时现算hash充作历史锚。父FAIL与真实阶段保留，只生成诊断COLLECTED/PARTIAL，不产生综合/物理成功凭证。保护沿用32逻辑核、192GiB进程树RSS、可用内存64GiB持续30秒底线、磁盘30GiB，原生线程8，无墙钟或静默强停。

A021已限定静态核AT004增量：最多4个新窗来自父终态日志最后Congestion Report，是代表性采样，不是severity全局Top4。若诊断DCP仅placed/physopt，表中资源仅为该早期保存布局在同一包围clock_region空间内的占用，不能称为该DCP自身route拥塞或精确INT窗内模块归因；父route日志与DCP布局阶段分别标记。8个层次父子资源/站点可重叠，不相加。原生命令尚未执行，CPU与静态接受不替代实际查询结果。

## 官方命令依据（2025.2）

- [UG835 report_utilization](https://docs.amd.com/r/2025.2-English/ug835-vivado-tcl-commands/report_utilization)
- [UG835 report_slr_crossing](https://docs.amd.com/r/2025.2-English/ug835-vivado-tcl-commands/report_slr_crossing)
- [UG835 report_design_analysis](https://docs.amd.com/r/2025.2-English/ug835-vivado-tcl-commands/report_design_analysis)
- [UG835 get_timing_paths](https://docs.amd.com/r/2025.2-English/ug835-vivado-tcl-commands/get_timing_paths)
- [UG835 report_timing](https://docs.amd.com/r/2025.2-English/ug835-vivado-tcl-commands/report_timing)
- [UG912 SLR_CROSSINGS](https://docs.amd.com/r/2025.2-English/ug912-vivado-properties/SLR_CROSSINGS)
- [UG835 get_cells](https://docs.amd.com/r/2025.2-English/ug835-vivado-tcl-commands/get_cells)、[get_sites](https://docs.amd.com/r/2025.2-English/ug835-vivado-tcl-commands/get_sites)

原生R005实际范围补充：report_slr_crossing -max_nets40内部打印get_timing的-max_paths30000（请求上限，实际返回数未报告）。400上限仅指四个显式get_timing_paths导出bucket，不能外推整个vendor会话内部分析最多400路径；原生全局/层次crossing报告另列，未进行Tcl百万对象逐项扫描。当前冻结源码/launch不改，实际观察prefix SHA见本attempt/native_internal_analysis_observation.json。
