# MLP ScaleCode DSP 整板候选：设计预算与阶段结果

2026-11-14。权威合同为 [design.md](design.md)。本文件由架构负责人维护；工程在本实验其余目录保存实际结果和运行索引，再同步至此。当前状态（2026-11-14 22:20，Asia/Shanghai最终核查）：本轮全DSP候选已完成完整整板实现、最终物理签核及bitstream生成，交付PASS。原生route成功，setup/hold/pulse失败端点均0，1625124条可路由网络全部完成且路由错误0，DRC零Error/Critical Warning；最终bus-skew94条约束全部满足，9个警告端点均由实际非负约束覆盖。Vivado于22:17:51正常退出0，bit文件80159263字节，主控独立SHA核验与收据一致，详见第5节。raw-only此前因旧8小时限制停止的历史记录保留，不改写为完整route失败。用户后续取消固定墙钟终止已实际生效，资源保护保留；新守护最终收据PASS。Down保持CPU边界，本轮未上板烧写或替换已发布镜像。

**后续板测阶段（2026-11-15 06:50）：** 用户已明确授权“可以去dell进行上板测试”，新增阶段见第6节。构建与bit交付PASS保持；当前已通过`hap-dell`连接到`DESKTOP-D3`，处于板测环境和占用检查，尚未将新候选板测记为PASS。该新授权覆盖本文件及冻结design.md中此前“上板不在构建阶段范围”的限制；旧构建输入、发布文件与历史收据保留。

## 1. 设计预算与比较基线

目标是生产 Decode16/VCU118 `xcvu9p-flga2104-2L-e`，core80MHz、DDR UI200/200MHz。Down保持CPU边界；新候选不改变生产数值/三级恢复接口。两候选可并行完成各自完整板级综合和布局，再比较选择一项完成route与合法bitstream；上板不在范围。

本表保留运行前结构预算；本轮实际综合资源单列于第3节。

| 项目 | 已发布整板背景 | raw-only结构预算 | all-DSP结构预算 |
|---|---:|---:|---:|
| MLP恢复叶数 | 96 | 96 | 96 |
| 恢复乘法DSP/双列叶 | 0 | 2，待整板实测 | 4，待整板实测 |
| 相对原板新增DSP | — | 约192，结构估计 | 约384，结构估计 |
| 全板DSP | 5389，历史placed | 约5581，算术预算 | 约5773，算术预算 |
| 全板LUT | 701775，历史placed | 不从单叶倍乘预测 | 不从bank反推 |
| 全板CLB Registers | 954554，历史placed | 待实测 | 待实测 |
| 全板严格FF | 954552，历史placed | 待实测 | 待实测 |
| BRAM36等效 / URAM | 709 / 304，历史placed | 无架构新增意图，待实测 | 无架构新增意图，待实测 |
| 最终setup WNS / hold WHS | +0.017 / +0.002ns，历史routed | ≥0 / ≥0为签核要求 | ≥0 / ≥0为签核要求 |

背景来源：[生产资源与阶段边界](../../../../docs/PERFORMANCE_AND_RESOURCES.md:223)，223–264行。原生产placed统计与新候选fresh构建上下文不同，历史差额可作描述，不能声称是仅属性变化导致的严格受控因果比较。raw-only与all-DSP之间采用本轮共同输入/策略/工具的实际整板结果比较。以上DSP总数只是5389+192/384的结构预算，不能代替完整网表原语计数；各SLR分布和CLB占用不得按比例外推。

单叶旧结果为 LUT/raw-only/all-DSP placed LUT 733/144/5、DSP0/2/4；all-DSP bank192旧OOC route为601LUT/339CLB FF/384DSP。这些已有结果只支持映射可行性的局部背景，均不是本轮整板数据。来源：[单叶结果](../../mlp_scalecode_dsp_probe/source/results.md:27)和[bank结果](../../mlp_scalecode_dsp_bank192/source/results.md:28)。新整板LUT/CLB/SLR DSP不设未经测量的下降保证。

## 2. 本轮实际状态

| 阶段 | raw-only | all-DSP | 证据入口 |
|---|---|---|---|
| 发布闭包与候选允许差异核验 | PASS，当前阶段输入 | PASS，当前阶段输入 | 两项synth/stage_inputs.json及叶normalized_equal；最终输出仍需再次绑定 |
| 旧叶功能证据身份复核/复用 | PASS，REUSED_PRIOR_RTL_ONLY | PASS，REUSED_PRIOR_RTL_ONLY | 两份functional/result.json保留原manifest/TB身份 |
| 候选完整工程create | PASS | PASS | [raw收据](../runs/dsp_raw_only/create/result.json)、[all收据](../runs/dsp_all/create/result.json) |
| 新叶级post-synth functional验证 | PASS | PASS | [总索引](../functional/results.json)、两份原始日志与独立gold |
| 独立`synth_design -rtl` elaborate | FAIL，OOC IP未载入 | NOT_RUN，同类入口不重复 | raw/elaborate完整失败收据保留 |
| 完整native synth内elaboration/闭包 | PASS，96叶与功能IP已链接 | PASS，96叶与功能IP已链接 | 两份原native日志、当前DCP复核及综合资格收据；调试占位按第4.1节处理 |
| 原始综合后报告门槛 | FAIL_RETAINED，exit1 | FAIL_RETAINED，exit1 | [raw原失败收据](../runs/dsp_raw_only/synth/result.json)、[all原失败收据](../runs/dsp_all/synth/result.json) |
| 完整整板综合资格验收 | PASS，仅synth；精确调试占位已核验 | PASS，仅synth；精确调试占位已核验 | [raw验收收据](../runs/dsp_raw_only/synth_acceptance.json)、[all验收收据](../runs/dsp_all/synth_acceptance.json) |
| 完整整板place/phys_opt | 原生步骤及完整报告复核PASS；原包装FAIL保留 | 原生步骤及完整报告复核PASS；原包装FAIL保留 | 原生impl_1/runme.log；当前[raw恢复进度](../native_resume/checkpoint_001/dsp_raw_only/progress.json)及[all恢复进度](../native_resume/checkpoint_001/dsp_all/progress.json) |
| 完整route | STOPPED_TIME_LIMIT，19:01旧累计时限触发，route未完成 | PASS，已生成routed.dcp，全部可路由网络完成、路由错误0；当前无固定墙钟终止 | [raw停止收据](../native_resume/checkpoint_001/dsp_raw_only/result.json)、[all有效监控进度](../native_resume/backup_all_001/dsp_all/guardian_handoff/progress.json) |
| 必要hold修复 | NOT_RUN | NOT_RUN | 按实际失败类型决定 |
| 最终物理签核 | NOT_RUN | PASS，setup/hold/pulse、route、DRC、身份/时钟/零黑盒及最终bus-skew均核对通过 | route/gate.txt、最终bus-skew原始报告及第3.7节集中复核 |
| bitstream | NOT_RUN | PASS，80159263字节；原生exit0及最终监控收据PASS | 第5节产物、SHA-256与交付证据 |
| 上板烧写/验证 | NOT_RUN | PRECHECK，2026-11-15新授权已开始Dell环境核查；新板测尚未完成 | 第6节与board_test/实际日志 |

**本轮叶级独立核查。** 架构负责人已直接核查[汇总](../functional/results.json)、[raw收据](../functional/dsp_raw_only/result.json)、[all收据](../functional/dsp_all/result.json)、两份sim/console.log及新旧TB差异。两次均由实际候选叶新综合得到functional netlist，实际含2/4个DSP48E2；仿真只加载该网表和TB，日志明确编译`unisims_ver.DSP48E2`，未用行为RTL替代原语模型。两次synth和sim均exit0、stop_reason=null、日志无ERROR/FATAL，最终PASS标记在全部检查和排空之后。

新TB相对旧TB仅三类适配：三个实例的模块名统一为当前候选网表；激励前等待200ns使UNISIM glbl GSR释放；通过标记改名。每次测试中的三个实例是同一个候选网表的三份实例，不是三种不同映射；跨实例一致性不替代独立gold。gold仍从外部dot/code操作数用signed64整数计算完整三因子乘积，不读取DUT中间结果；逐周期弹性模型、队列、3周期握手延迟、背压保持、取消和守恒断言均未删改。

每候选每实例接受135747=输出135741+取消6，结束在途0；567定向、两列各131072个S17编码、4096随机（seed=6d2b79f5）。最长连续II=1为131072，三个实例合计延迟检查394917，输入阻塞1351周期、输出保持1499周期、clear3边沿。GSR等待使总周期从旧137353变为137372、reset边沿从5变为24，事务数与功能覆盖不变。raw新网表SHA-256为`157e2b741ac274993d7844cd3a23b45b15512f662f2a05705e626474eadf54ad`，all为`af72c088604b33be28d4c1bcae0e20898b09a67751db80a2df20a1847cf374c6`。以上PASS严格限于叶级综合网表功能，不能代替整板布局/路由或板测。

**构建进度。** raw/all create分别427.400/437.908s，峰值树RSS3467661312/3467325440B（均约3.23GiB），returncode0、native_pass_marker=true、changed_inputs为空。raw独立elaborate在64.373s后exit1，原始日志为`Synth 8-439 module scalellm_final_decode16_bd_clk_core_0 not found`，没有资源保护触发；此失败完整保留。正确后续路径是native project synthesis完成OOC IP依赖后执行真实顶层elaboration及综合，不关闭黑盒检查，按design.md第4.1节分阶段规则证明真实闭包和96叶映射。

raw/all完整synth实际启动UTC分别为2026-11-14T01:04:18Z及01:05:55Z，各自progress状态RUNNING、6 IP jobs×每进程4线程、各NUMA48逻辑CPU、单树192GiB，阶段timeout10800s。此为启动快照，不表示所有IP或顶层已经完成；实时状态以各自progress/result及原始日志为准。两个叶级新验证已完成后再释放各自候选锁，未并发修改正在综合的源闭包。

**2026-11-14首次raw-only综合后门槛失败与合同限定修订（失败保留）。** 架构负责人独立检查原始[console.log](../runs/dsp_raw_only/synth/console.log:499)、[result.json](../runs/dsp_raw_only/synth/result.json)、当前报告脚本、候选叶源码和下列历史证据。日志明确`synth_design completed successfully`，已链接包括clk_core在内的功能IP并写出本轮`synthesized.dcp`，随后查询到96个恢复叶。退出1发生在`report_candidate_scene`的`Unresolved blackboxes: 1`；[blackboxes.txt](../runs/dsp_raw_only/synth/reports/blackboxes.txt)仅含`dbg_hub`。原收据`native_pass_marker=false`、`changed_inputs=[]`、`stop_reason=null`，elapsed=3950.951s、peak_tree_rss=70316658688B；它仍是FAIL，不能因工具综合已完成而追记为阶段PASS。

历史生产[linked_blackboxes.tsv](../../../../artifacts/verified_80mhz/hardware_agent/evidence/physical/final_decode16_011/reader_001/source_snapshot/project/hardware/vivado/reports/final_decode16_011_synth/linked_blackboxes.tsv:2)记录精确`dbg_hub / dbg_hub_CV / OPEN_DEBUG_PLACEHOLDER`，同次[implementation日志](../../../../artifacts/verified_80mhz/hardware_agent/evidence/physical/final_decode16_011/reader_001/impl/vivado.log:424)在opt_design中生成`xilinx.com:ip:xsdbm:3.0`。据此采用design.md第4.1节：完整综合后只允许这一个精确调试占位身份；优化完成后、place/phys_opt以及最终route/bit检查必须零黑盒。本轮旧blackboxes.txt没有REF_NAME，不能单凭历史分类填PASS；后续独立DCP复核已确认两候选当前精确类型及调试核身份，证据见下文。post-opt零黑盒结果仍是进入实际place_design的必要条件；本次仅验收综合资格，未将核展开、post-opt零黑盒或任何布局结果计为PASS。

同时独立发现[原recovery_mapping.tsv](../runs/dsp_raw_only/synth/reports/recovery_mapping.tsv)的96行`dsp_descendants`全部误报0：脚本把带`gen_row[0]`/`gen_pair[0]`的完整层级名直接传入`string match "$name/*"`，方括号被解释为glob字符集合。使用字面`leaf_name + /`前缀重新统计原[dsp_inventory.tsv](../runs/dsp_raw_only/synth/reports/dsp_inventory.tsv)，得到96叶各2 DSP、恢复层级共192 DSP、全板5581 DSP；原[分层资源报告](../runs/dsp_raw_only/synth/reports/utilization_hierarchical.rpt:597)也有96条恢复叶记录，每条2 DSP。两候选实际叶源码的`use_dsp=yes`分别为2/4处，归一化后与生产叶逐字一致。原0计数表无效并保留，工程已为两候选另存准确映射；后续综合资格复核已通过，仍不能把这些synth计数当作placed结果。

raw-only原始失败证据固定身份如下；已完成的独立复核另存收据并引用这些身份，未覆盖或删除原失败输出：

| 原始文件（均在raw-only/synth） | SHA-256 |
|---|---|
| `result.json` | `24e569748e2f12a24689a5d3c4fc7803322d6613e4c617e6a99ffd38ebf8eb54` |
| `console.log` | `01b7d95bb966a50ae62242064d40c998ba352dd438d8958c32ff3a878a2ec465` |
| `reports/synthesized.dcp`（本次独立重验哈希一致） | `7d64bb23f30a9382cfe01428b9866a26f2478f97cbf50aa674c6a2a91f1db8ff` |
| `reports/blackboxes.txt` | `7d06f1f47bc10036d9c5769fff06d13ce029adde14087fed809c69733b136ace` |
| `reports/recovery_mapping.tsv`（错误计数保留） | `5a5195f361b55b4f49f7ac0d426df59c0074983ec5c06624a4665545f8810905` |
| `reports/dsp_inventory.tsv` | `5b3be5fb2397705fa7f4faa00a050a69d158b211ff6a0aaff9062309d4bc4c50` |
| `reports/utilization_hierarchical.rpt` | `38a876143618298718a7b9351675e2e80da3c022c1b2e2100b430a4059910742` |

**两候选综合资格集中验收。** 架构负责人已独立重验[raw验收收据](../runs/dsp_raw_only/synth_acceptance.json)和[all验收收据](../runs/dsp_all/synth_acceptance.json)、两份原始失败收据/日志、全部原始综合报告与DCP哈希、两份新探针收据及报告、修正映射和[活动运行索引](../runs/campaign_resume_state.json)。所有核验一致。两次原native综合均成功生成本轮DCP，但原报告门槛均因唯一`dbg_hub`退出1；raw/all elapsed分别3950.951/3959.387s，峰值树RSS分别70316658688/69712797696B，stop_reason均null，changed_inputs均为空。原始FAIL继续保留，新`status=PASS`只属于独立综合资格验收。

新[raw探针](../runs/dsp_raw_only/synth_qualified/result.json)与[all探针](../runs/dsp_all/synth_qualified/result.json)均exit0、stop_reason=null，分别611.992/626.516s；实际DCP的唯一blackbox均为`NAME=dbg_hub`、`REF_NAME=dbg_hub_CV`、`IS_BLACKBOX=1`、`IS_PRIMITIVE=0`。两次`get_debug_cores`均成功返回`dbg_hub`及两个DDR4 debug core；cell的`CORE_GENERATION_INFO`/`DEBUG_CORE_INFO`也关联`labtools_xsdbm_v3_00_a`。满足design.md第4.1节的精确综合后占位条件，物理阶段继续要求`ZERO_AFTER_OPT_AND_LATER`。

每份探针日志保留6条已分类ERROR：在3个`debug_core`对象上查询不支持的可选`REF_NAME`/`IPDEF`各3次；另有13条探索性cell属性警告。验收收据绑定日志哈希并记录准确类别/数量，必需cell属性和`get_debug_cores`查询均成功；这不是“日志零ERROR”的运行，也不放宽必需查询失败或最终物理DRC门槛。

原错误映射表仍全部为0。独立字面层级前缀计数、原DSP清单、原分层报告与新[raw修正映射](../runs/dsp_raw_only/synth_acceptance_recovery_mapping.tsv)/[all修正映射](../runs/dsp_all/synth_acceptance_recovery_mapping.tsv)一致：raw为96叶×2=192 DSP，all为96叶×4=384 DSP；全板分别5581/5773 DSP。两项验收绑定身份如下：

| 身份 | raw-only SHA-256 | all-DSP SHA-256 |
|---|---|---|
| `synth_acceptance.json` | `538b939e45c9e9dfb62d0ce94a78dda336ef38c0ee0eff380fb27e994dbcc8ea` | `2eedf59db318d2c72e2ace0259cb6e1017590323e65bddda22382f87969aa79e` |
| 原`synth/result.json`（FAIL保留） | `24e569748e2f12a24689a5d3c4fc7803322d6613e4c617e6a99ffd38ebf8eb54` | `a9587384a29189f10a0cf0beb4c3acaed92f4a7cd453ecc780f40b891cdb23c0` |
| 原`synth/reports/synthesized.dcp` | `7d64bb23f30a9382cfe01428b9866a26f2478f97cbf50aa674c6a2a91f1db8ff` | `48bca619386d39552d019106e2bad7b3a62b9dec516860640869a670fe16ecf4` |

活动索引于UTC 2026-11-14T02:34:42Z启动恢复流程，先登记两项综合资格PASS，随后all/raw place调度分别于02:34:42Z/02:34:43Z进入RUNNING；两份[raw place进度](../runs/dsp_raw_only/place/progress.json)/[all place进度](../runs/dsp_all/place/progress.json)均记录Vivado于02:34:43Z启动。各候选独立48逻辑CPU affinity、native threads32、单树192GiB、implementation累计28800s预算。这里的place阶段包含opt/place/phys_opt流程；RUNNING只表示该阶段已启动，不代表任何物理步骤完成。布局资源、逐SLR分布、拥塞、时序与最终选型等待实际结果；route/bitstream仍NOT_RUN。

## 3. 本轮综合资源与待完成的布局选择

以下数据直接来自本轮[raw综合资源报告](../runs/dsp_raw_only/synth/reports/utilization.rpt:38)和[all综合资源报告](../runs/dsp_all/synth/reports/utilization.rpt:38)，两份报告的Design State均为`Synthesized`；不作为placed/routed资源或闭合证明。

| 综合阶段项目 | raw-only | all-DSP |
|---|---:|---:|
| 全板CLB LUTs | 672923 | 660057 |
| 全板CLB Registers | 952049 | 952049 |
| 全板Register as Flip Flop（严格FF） | 952047 | 952047 |
| 全板DSP48E2 | 5581 | 5773 |
| Block RAM Tile（36Kb等效） | 709 | 709 |
| URAM | 304 | 304 |
| 恢复叶数量 | 96 | 96 |
| 每恢复叶DSP | 2 | 4 |
| 恢复层级DSP合计 | 192 | 384 |

两候选均为695个RAMB36E2及28个RAMB18E2，折合709个Block RAM Tile。综合阶段all-DSP比raw-only减少12866 LUT、增加192 DSP，寄存器与上述存储资源总量相同；该综合差额本身不能决定物理选型。后续occupied CLB、逐SLR利用率、拥塞与post-physopt时序及实际选择见第3.1/3.2节。

资源报告SHA-256：raw为`5bca86040937ced748cfd86c1a1460f0279419a535e2cac325f0f1737f0a137d`，all为`e12b5a8562897717afc8e2e625d741ea2ee8bf26ab49fb35e547f0a17433d3eb`；已与原失败收据内的报告身份逐项核对。


综合、placed、post-physopt、routed资源分别记录，不把较早阶段数字改称最终route数字。每个实际阶段填全板LUT、CLB Registers与严格FF、occupied CLB、DSP48E2、BRAM36/URAM及逐SLR LUT/CLB/DSP；各值附原始报告路径及哈希。分别列恢复96叶的实际原语映射与整板总量，保留层级LUT合并口径。

两候选共同比较表及实际选择已在第3.2节补齐，raw-only按design.md第5节的真实post-physopt结果选中并开始route。该选择不表示最终物理闭合；未选all-DSP的route保持NOT_RUN。

### 3.1 原生布局完成与当前续跑（2026-11-14）

直接核查两份原生 `impl_1/runme.log`：raw的第1417/1468行、all的第1423/1539行分别明确 `place_design completed successfully` / `phys_opt_design completed successfully`。两个原包装收据仍为FAIL；包装把Vivado返回的`Not started route_design`误判成phys_opt未完成，不覆盖原始收据。

以下为原生 **placed** 报告，尚非route后资源：

| placed项目 | raw-only | all-DSP |
|---|---:|---:|
| CLB LUTs | 645270 | 632443 |
| CLB Registers / 严格FF | 935681 / 935679 | 936358 / 936356 |
| occupied CLB / 总147780 | 132516（89.67%） | 136026（92.05%） |
| DSP / 总6840 | 5581（81.59%） | 5773（84.40%） |
| BRAM36等效 / URAM | 709 / 304 | 709 / 304 |
| SLR0/1/2 CLB占用率 | 86.91 / 99.80 / 82.30% | 92.46 / 99.11 / 84.57% |
| SLR0/1/2 DSP占用率 | 72.02 / 82.28 / 90.48% | 91.67 / 85.26 / 76.27% |
| 原生post-physopt估计setup WNS / TNS | +0.498 / 0 ns | +0.028 / 0 ns |

资源来源：[raw placed报告](../runs/dsp_raw_only/create/project/scalellm_final_decode16.runs/impl_1/scalellm_final_decode16_bd_wrapper_utilization_placed.rpt)、[all placed报告](../runs/dsp_all/create/project/scalellm_final_decode16.runs/impl_1/scalellm_final_decode16_bd_wrapper_utilization_placed.rpt)。估计setup来自各自原生runme.log，不能代替完整min/max报告，更不能称为routed timing PASS。all-DSP相比raw-only减少12827 LUT，但occupied CLB增加3510；两者SLR1均接近容量上限，尚须真实route判断拥塞与时序。

当前恢复入口为[run_checkpoint.py](../native_resume/run_checkpoint.py)与[resume_checkpoint.tcl](../native_resume/resume_checkpoint.tcl)，输出在 `native_resume/checkpoint_001/`。先前open_run恢复失败和旧campaign状态保留，不作为当前活动状态。新恢复绑定旧源、manifest、失败收据、DCP和原guard；加载后以真实`TOP`核对顶层、同时校验PART、工具版本与三路原时钟。`NAME`只是checkpoint会话别名，原guard未改写。恢复读取/报告时间计入原implementation累计预算。

14:06核查时两会话实际处于各自post-physopt DCP的open_checkpoint过程，尚无selected.txt或route_go.txt；不将该时点称为已开始route。后续以该目录的phase/progress、selection、route/hold报告及最终result为准。此段是已核查阶段快照，不是最终物理验收。

### 3.2 完整post-physopt比较与真实route启动

2026-11-14 14:24直接核查[自动选择凭据](../native_resume/checkpoint_001/selection.json)、两份`post_physopt/timing_summary.rpt`与raw当前console.log。两候选真实loaded TOP、PART、2025.2工具及80/200/200MHz时钟检查通过，均零blackbox；96个恢复叶实际分别为192/384 DSP，完整层级与原语清单一致。该选择凭据保存全板及逐SLR资源、所有输入报告的路径与SHA-256。

| post-physopt完整报告 | raw-only | all-DSP |
|---|---:|---:|
| LUT | 645270 | 632446 |
| setup WNS / TNS（ns） | +0.498 / 0 | +0.028 / 0 |
| setup失败端点 | 0 | 0 |
| hold WHS / THS（ns） | -0.588 / -2221.805 | -0.641 / -2007.819 |
| hold失败端点 | 36945 | 33542 |
| pulse最差余量 / 失败端点 | 0 ns / 0 | 0 ns / 0 |

all的post-physopt比其placed多3个LUT，两种阶段不混用；其余资源值同第3.1节。两方案setup通过、hold尚未闭合，按合同第5.4条同类别字典序，以更大的setup WNS选定raw-only。未布线hold负值完整保留，选择不是最终时序签核。两份post-physopt DRC均无Error；唯一Critical Warning为未完成布线的RTSTAT-13，最终route签核仍要求零Error/Critical Warning。

补充层级统计（2026-11-14 18:53从上述两份`post_physopt/utilization_hierarchical.rpt`只读汇总）：96个`u_recover`行的LUT归属合计raw为62249（每叶648–650），all为49638（每叶514–518），差12611；FF合计均288，DSP合计分别192/384。全板LUT差为12824，不能用单叶OOC的5 LUT乘以96替代整板结果。报告明确提示跨层级LUT combining可使子层级之和大于父层级；这些数值是完整网表的层级归属统计，不是恢复模块的独立增量资源。当前没有逐LUT归属证据确认每叶绝对值高于OOC的具体成因，不将差异直接归因为边界合并。此汇总未启动新EDA探针或中断route。

现有布局拥塞报告也存在取舍：raw报告18个拥塞窗口，Global/Long/Short最高等级均6；all报告7个窗口，Global/Long/Short最高分别5/6/5。raw的Global/Short等级6区域主要含d1_smc及MLP branch1的u_dot/gate_accum，all对应报告没有这些等级6区域，其Long等级6主要位于attention/projection。来源为两候选`post_physopt/congestion.rpt`。这是布局报告，不能与后续route过程的估计等级混为同阶段比较；若raw最终因相应拥塞未闭合，可据最终路径与这些差异评估合同内备选，当前继续同一次raw route。

all会话于14:23:49正常退出，保存完整候选报告；raw在同一已加载会话执行`route_design -directive Default`，14:24日志已进入`Phase 1 Build RT Design`并确认最大32路由线程，控制器先将进程主线程CPU affinity扩至0–95；14:30工程核查发现65个已有线程仍保留原48CPU集合，随后按既有授权对自有raw树的全部68线程扩至0–95并实测68/68生效，记录见`native_resume/checkpoint_001/dsp_raw_only/route_thread_affinity.json`。此时仅一棵本任务重EDA树，implementation原累计预算继续计时。后续真实route、必要hold修复与bitstream状态见该目录，未完成项不记PASS。

### 3.3 当前route过程记录（未完成，17:05核查）

raw在同一次默认route中完成路由初始化和Global Routing，进入`Phase 5.1 Global Iteration 0`。工具报告至少31个CLB存在高引脚利用率；route过程估计Global/Short拥塞等级5、Timing拥塞等级7。14:31观察到的中间时序为WNS+0.553ns/TNS0，WHS-0.517ns/THS-1069.521ns，均非最终签核。

16:58观察到中间overlap节点序列为882053 → 277392 → 104902 → 49025 → 27244 → 17341 → 12570 → 9790，表明当前路由仍在消除冲突；这些是中间状态，不能填为最终路由错误计数。进程仍RUNNING，RSS约25.7GiB，implementation原累计预算剩余约123分钟，尚无工具错误或资源保护触发，route/hold最终签核及bitstream仍未完成。资源采样曾观察约31.4个CPU实际使用，后续部分算法子阶段降到约3–6个CPU；全线程96CPU affinity及native最大32的配置保持，不能把参数上限表述为每阶段持续满载。

17:03–17:05出现重要新证据：原生日志明确`Route 35-447 Congestion is preventing the router from routing all nets`，路由器开始优先保证连通而非时序优化；该时点中间WNS=-1.383ns、TNS=-1208.901ns，WHS/THS为N/A。负值与警告保留，不当作最终失败或通过。第0轮随后结束，此时本次route_design累计日志elapsed=02:40:34（不是该轮单独耗时），进入`Phase 5.2 Global Iteration 1`，当前route仍在运行。

原route日志另有`Route 35-462`警告：4个command CDC的bus-skew组共9条`dest_hsdata_ff_reg[bit]/D`路径未populate。该警告尚未分类为常量/裁剪，也未忽略约束；工程已预备一次最终固定DCP的只读bus-skew报告及精确端点/全层级net段/leaf driver检查，当前没有因此重载或中断route。检查与当前会话共用原剩余墙钟/RSS预算。

all-DSP的备用直接route入口已预备但NOT_RUN。仅当raw实际失败/停止收据与不同拥塞证据支持备选时启用；届时复用all现有已验证post-physopt报告及自身冻结DCP，不重置它的原place/恢复报告累计时间。全任务hold/bitstream预算同样不因换候选重置。

### 3.4 raw时间保护停止与all-DSP接续（19:04核查）

原raw默认route在Global Iteration 1的节点冲突序列为783820 → 493468 → 257473 → 140697 → 80555。19:01守护触发`cumulative implementation wall time limit`，最终[收据](../native_resume/checkpoint_001/dsp_raw_only/result.json)记录implementation累计28803.433586s、returncode=-15、native_pass_marker=false、hold/bit均0s；峰值树RSS28079042560B，最低MemAvailable453498609664B、最低磁盘324569915392B。触发项只有原实现时间预算，不能把未完成route的中间时序当成最终FAIL/PASS。原raw进程4068319/4068357/4068524均已退出，停止证据保留；本轮raw没有最终route DCP或bitstream。

依据真实Route 35-447拥塞警告和两个候选已有的布局拥塞差异，工程已启动[all-DSP备用运行](../native_resume/backup_all_001/dsp_all/progress.json)。新会话19:02:52启动，19:03–19:04主控与工程分别核实正在open_checkpoint all自身冻结`phys_opt_design.dcp`，owned wrapper PID4149475。加载后的实际TOP/PART/工具/时钟/零黑盒检查继续执行，完整比较报告引用已验证哈希，不再重复生成。原all累计implementation10837.519s被继承；19:04读取为10918.607s/28800s，共享hold/bit已用均0；使用96逻辑CPU affinity和native32线程，其他保护不变。

备用假设仅为改变真实物理拥塞分布：raw/all的SLR1 LUT分别284890（72.29%）/237963（60.38%），all在该SLR少46927 LUT；SLR1 occupied CLB分别49161/48823。46927不是全板LUT差额，全板post-physopt差额为12824。all的Global/Short最高拥塞等级5低于raw的6，相关报告的窗口和模块归属见第3.2节；all的setup裕量更小（+0.028ns），最终是否改善尚待实际route。该备选没有重置实现或hold/bit预算，也没有改变RTL、XDC、时序或DRC通过门槛。

### 3.5 all-DSP布线进展（20:12核查，未完成）

主控直接核对`backup_all_001/dsp_all/console.log`、有效guardian进度和进程状态。同一Vivado PID4149565持续运行，新守护PID4153201有效，旧控制器4149424保持T，固定墙钟终止仍为false、stop_reason=null。当前处于`Phase 5.1 Global Iteration 0`，该轮overlap序列483408 → 71401 → 10958 → 2329 → 703 → 289 → 123 → 60 → 34 → 18；最后日志时间20:12:03。这是当前迭代的中间冲突统计，不能填成最终route错误数或完成百分比。

本次route日志当前最近一条中间时序为WNS+0.171ns/TNS0、WHS-0.626ns/THS-1551.098ns；setup中间值非负但hold未闭合，均不是最终签核。route过程估计Global/Short拥塞等级5、Timing等级7仍保留。采样树RSS26108485632B（约24.3GiB），累计implementation14998.939s仅作统计；hold和bit均尚未执行，目录无bit产物。后续以实际route完成及完整最终报告判断，不由overlap接近0推定通过。

### 3.6 all-DSP原生route完成（21:38核查）

同一all-DSP会话已明确输出`Router Completed Successfully`及`route_design completed successfully`，此次route调用elapsed=02:08:17；随后保存`backup_all_001/dsp_all/route/routed.dcp`。Phase 14.2为路由器内部SLL Register Hold Fix Optimization，实际移动14个既有cell；这属于本次route内部步骤，未另行启动合同中的独立hold修复命令。当前进度类别仍为route，因为签核报告仍在生成，不能因此误报路由算法尚未结束。

主控直接核对新`route/timing_summary.rpt`第142行：setup WNS+0.009ns/TNS0/失败端点0，hold WHS+0.008ns/THS0/失败端点0，pulse WPWS0ns/TPWS0/失败端点0，报告明确`All user specified timing constraints are met`。新`route/drc.rpt`的Design State为Fully Routed，7类共16570条检查均为Warning，零Error/Critical Warning；其中RTSTAT-10为1条No routable loads，最终仍核查独立route状态报告。

`check_timing.rpt`显示no_clock、constant_clock、unconstrained_internal_endpoints、multiple_clock、generated_clocks、loops等内部项目均0；仅pcie_perstn无input delay和两路DDR reset_n无output delay待按冻结来源分类。当前all日志也包含4个bus-skew组共9条未populate路径，必须基于该最终固定DCP完成现行bus-skew核查，不能由setup/hold为正推定这部分通过。

当前routed资源为632446 LUT、936372 CLB Registers（严格FF936370）、136026 occupied CLB（92.05%）、5773 DSP（84.40%）、BRAM36等效709、URAM304；SLR0/1/2 CLB占用92.46/99.11/84.57%。这些为本次routed报告，不能与此前post-physopt寄存器数936358混用。21:37:48有效守护仍RUNNING、stop_reason=null、fixed_wall_time_termination=false，树RSS约28.8GiB；尚无bit文件。完整最终物理签核及bitstream仍未交付。

### 3.7 最终bus-skew复核与完整物理签核（22:06）

原会话21:47产出`route/gate.txt=PASS`并进入route_review；主控独立核对`route_status.rpt`：1625124条可路由网络全部完成，routing errors=0。随后唯一必要只读审计于22:01:20正常退出，[审计收据](../native_resume/backup_all_001/dsp_all/final_bus_skew_audit/result.json)记录CAPTURED、returncode0、stop_reason=null、elapsed812.552s、source_unchanged=true；该CAPTURED本身不代替以下实际审核结论。固定源DCP SHA-256为`3780de3ab72a506a63ee1d59ecea6c7d26e1f2f29ceb7aa5be2ee81acb867259`。

主控独立核对bus_skew.rpt、endpoint_identity.tsv、requested_pins.txt和loaded_identity.txt的SHA与收据一致。最终报告共94条约束、94条数值slack，全部非负且0 VIOLATED，最小slack+3.103ns。实际all日志的9个警告端点均精确匹配一个D pin和一个FDRE cell；其网络TYPE=SIGNAL，由真实FDRE共享扇出驱动，不是常量或已裁剪的目标端点，不能把INIT=0当常量依据。逐字核对最终报告的From/To实际对象集合，9个真实driver与目标cell全部被以下四条约束覆盖：

| 最终约束ID | command CDC | 实际目标bit | 实际共享源bit | slack（ns） |
|---|---|---|---|---:|
| 85 | attention command1 | 14、16 | src_hsdata_ff_reg[16] | +8.580 |
| 86 | attention command0 | 14、16 | src_hsdata_ff_reg[16] | +9.007 |
| 87 | MLP command1 | 15、16、17 | src_hsdata_ff_reg[17] | +8.643 |
| 88 | MLP command0 | 16、17 | src_hsdata_ff_reg[17] | +8.658 |

因此保留路由阶段35-462警告及其共享源寄存器事实，以固定最终DCP的真实约束覆盖和非负bus-skew报告完成审核，未删除/豁免这9条目标路径。当前全局setup/hold/pulse、全部路由、DRC等级、TOP/PART/工具/80与200/200MHz时钟、零黑盒及bus-skew的完整物理签核PASS。

check_timing的1个no_input_delay及2个no_output_delay与同一候选post-physopt记录相同：冻结release_create_board.tcl第395–435行明确pcie_perstn为低有效复位，连接XDMA sys_rst_n及proc_sys_reset；第449–456行将两路DDR4 C0_DDR4接口外引为ddr4_sdram_c1/c2，reset_n为其DDR复位输出，显式管脚在vcu118_ddr4_explicit_pins.xdc第122/237行。内部未约束端点和缺失时钟等仍0，不作为新增同步数据接口放宽。

## 4. 资源保护、失败与复用边界

**当前有效的后续用户授权（19:16:29接管生效）。** 用户在看到raw因8小时停止后明确要求“不要设置强行停止”。该指令覆盖以下旧墙钟上限；本轮当前全DSP实现、后续必要报告/hold修复/bitstream均不再按固定累计时长终止，耗时仅作记录。RSS合计384GiB、MemAvailable下限64GiB、磁盘下限30GiB及实际工具错误/最终物理验收标准继续生效。冻结design.md及旧收据保留其运行当时的预算，不能据旧文档重新启用已撤销的时间终止规则。

已在活跃进程生效，而不只是修改磁盘脚本：[新策略](../native_resume/backup_all_001/dsp_all/guardian_handoff/user_authorization.json)、[有效owner](../native_resume/backup_all_001/dsp_all/guardian_handoff/owner.json)、[输入身份](../native_resume/backup_all_001/dsp_all/guardian_handoff/stage_inputs.json)与[实时进度](../native_resume/backup_all_001/dsp_all/guardian_handoff/progress.json)均已保存。新守护PID4153201持有接管锁；只暂停了原Python控制器PID4149424，核实其starttime/cmdline且实测T状态。同一Vivado独立进程组4149475及其PID4149475/4149494/4149565持续非T，CPU采样与route日志继续推进。新有效状态明确`fixed_wall_time_termination=false`。主控独立复核原stage_inputs、旧controller、新guardian及授权文件SHA-256与接管身份一致，未改写旧manifest。

待执行的最终bus-skew只读检查入口也已移除旧共享墙钟停止分支，保留资源保护。Vivado最终退出后，新守护先固定自身记录，再恢复旧控制器仅收取真实子进程退出码；新`guardian_handoff/final_result.json`将记录准确持续耗时、有效策略及旧结果身份。旧控制器最终累计值只保留暂停前口径，不能替代新守护累计统计。当前该最终收据尚未生成，bitstream仍NOT_RUN。

以下是本次后续用户授权前的历史预算与资源配置：

执行预算见design.md第6节。实测服务器48物理/96逻辑CPU、两个NUMA节点；两候选分别使用0–23,48–71与24–47,72–95。允许2候选重树，单树192GiB、全任务384GiB，系统始终保留MemAvailable64GiB及磁盘30GiB；选择后独占route/hold/bit预先授权单树384GiB、CPU0–95全部96逻辑CPU affinity，runner独占模式不再限48CPU，native maxThreads仍为32。IP综合每进程4线程，jobs初始6/候选，在CPU和内存准入允许时可增至12；物理步骤maxThreads32。最大化有效吞吐不等于保证所有阶段持续占满96逻辑CPU。旧墙钟上限为每候选synth3h、implementation累计8h、选定候选hold累计2h、bit40min；本轮后续物理阶段的时间终止已按上述用户授权撤销。

2026-11-14（工具日志本地时间08:50）空Vivado2025.2探针实测：maxThreads8/16/32均接受且读回相同值；64/96被`[Common 17-154] Value should be >= 1 and <= 32`拒绝，进程退出0。安装手册摘要的1..8与本机参数实现不一致；采用实测上限，具体算法实际线程数仍据日志/CPU观测报告。该查询不构成任何新综合/物理结果。原始工具输出已返回主控及工程，工程可将其作为资源配置记录收录，不能伪造原运行日志文件。

实际运行须登记每次及阶段累计墙钟、峰值单树及全任务RSS、系统最低MemAvailable/剩余磁盘、CPU affinity、线程上限及有效IP jobs。构建基础设施overlay允许修订候选本地create/thread hook/驱动的4线程检查并保存前后哈希；生产RTL仍仅有指定DSP属性差异，XDC/ABI/ROM/物理门槛不变。当前raw-only create按原4线程预算正常完成，不为资源变更中断或改写其manifest；后续阶段使用新配置。所有失败与资源保护触发保持原记录；此处只集中总结新原因、修复与受影响回归。其他项目长期Vivado不属于本任务。

实际候选恢复叶SHA-256：raw-only为`f14295ce66a8d72ebf26fcc96d79bb1a6b53166f5c2772a449cdd15bee7f6210`，all-DSP为`f645dbf2e78f7ea2f1cc372cbe1cfd97c3b7ff3b63ca612a6dec29308786facb`；属性归一化后均回到原生产叶身份。当前没有新候选板测。原发布镜像、既有OOC实验及原始manifest保持不变。候选旧功能证据经身份核验后明确复用；新叶网表验证与新整板物理结果分开标记，不将局部验证扩大为整模型新实测。

## 5. 阶段最终验收：PASS（2026-11-14 22:19）

最终采用`dsp_all`，器件`xcvu9p-flga2104-2L-e`，Vivado2025.2，core80MHz、DDR UI200/200MHz。两候选原生综合/布局及新恢复叶post-synth功能验证已完成；完整整板route与bitstream最终由all-DSP候选通过。raw-only保留STOPPED_TIME_LIMIT，不能据此宣称该候选必然不可布线。

| 最终产物 | 大小（字节） | SHA-256 |
|---|---:|---|
| [ScaleLLM_Final_Decode16_80MHz.bit](../native_resume/backup_all_001/dsp_all/bitstream/ScaleLLM_Final_Decode16_80MHz.bit) | 80159263 | `5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7` |
| [routed.dcp](../native_resume/backup_all_001/dsp_all/route/routed.dcp) | 668816413 | `3780de3ab72a506a63ee1d59ecea6c7d26e1f2f29ceb7aa5be2ee81acb867259` |

[最终物理验收](../native_resume/backup_all_001/dsp_all/final_physical_acceptance.json)、[实际子进程退出收据](../native_resume/backup_all_001/dsp_all/result.json)、[有效新守护最终收据](../native_resume/backup_all_001/dsp_all/guardian_handoff/final_result.json)及[完整原生日志](../native_resume/backup_all_001/dsp_all/console.log)构成交付入口。主控直接重算bit SHA，与原收据`files`一致；新守护引用的旧结果SHA也直接重算一致。DCP在最终只读审计前后SHA相同，bitstream入口`selected_checkpoint.txt`绑定此固定已签核检查点。

最终验收关键值：

| 检查 | 实际结果 |
|---|---|
| setup WNS / TNS / 失败端点 | +0.009ns / 0 / 0 |
| hold WHS / THS / 失败端点 | +0.008ns / 0 / 0 |
| pulse WPWS / TPWS / 失败端点 | 0ns / 0 / 0 |
| 完全路由 / 可路由网络；路由错误 | 1625124 / 1625124；0 |
| DRC Error / Critical Warning | 0 / 0（既有Warning保留） |
| bus-skew | 94条全部满足，最小slack+3.103ns；9个警告目标及真实driver逐字覆盖见第3.7节 |
| TOP / PART / 工具 / 三时钟 / 黑盒 | 全部通过，零黑盒 |
| 原生bit写出 | Bitgen Completed Successfully、write_bitstream completed successfully；0 Error、0 Critical Warning、20 Warning |
| 原生退出及有效守护最终结果 | exit0、NATIVE_RESUME_BITSTREAM_PASS、guardian PASS，stop_reason=null |
| 上板 / 发布镜像替换 | NOT_RUN，不在本轮范围 |

生成前bitstream目录中的timing_acceptance、route_status、drc_acceptance再次通过；主控直接复核其全局时序与最终route一致，DRC仍全为Warning。bit写出调用elapsed=00:02:42；含生成前检查和收尾的完整bit阶段为671.444s。新守护准确累计implementation21870.655s、独立hold0s（router内部hold优化计在route）、bit671.444s。旧控制器终末累计11654.289s仅代表接管前口径，不用它计算最终耗时。

本次恢复会话接管前后监控合并峰值RSS为54474399744B（约50.73GiB，包含单次只读审计），最低MemAvailable444008275968B、最低磁盘320673816576B；这是本次恢复/审计区间，不替代更早两个候选综合/布局并发的资源收据。固定墙钟终止始终false，未触发资源保护。主控和工程核查本次Vivado、旧控制器、新守护及审计进程均已退出，其他工程未受影响。

最终routed资源为LUT632446（53.50%）、CLB Registers936372/严格FF936370、occupied CLB136026（92.05%）、DSP5773（84.40%）、BRAM36等效709、URAM304；SLR0/1/2 CLB占用92.46/99.11/84.57%。96个恢复叶各4 DSP、合计384 DSP，采用第2节新叶综合网表功能验证结果，不重新运行或扩大为新整板功能板测。

本轮共同构建上下文的post-physopt比较显示，全DSP比raw-only少12824 LUT、多192 DSP，并通过实际整板布线与bitstream生成。这证明恢复乘法DSP方案在当前整板中可实现；不能据单叶5 LUT倍乘预测整板占用，也不能将历史生产板与本轮差额全部归因于DSP属性。SLR1的CLB占用仍99.11%，并未建立可直接加入Down矩阵的容量结论；既有架构文档明确Down在CPU，当前证据不足以把它未放入FPGA单独归因于ScaleCodeRecovery LUT用量。

## 6. Dell新候选上板测试：PASS（2026-11-15）

用户明确要求到Dell进行上板测试，授权本轮全DSP候选的实际SRAM下载、设备健康检查及功能回归。此为构建完成后的新阶段，覆盖旧构建合同中的“不上板”范围限制；不改写冻结构建输入或旧发布镜像/manifest，也不进行配置Flash写入。工程继续使用GPT-6.1 Sol / xhigh，复用同一实现负责人；主控维护本节并在阶段结束集中核对，不增加逐步审批。

**镜像身份与目标。** 新bit为第5节80,159,263字节产物，SHA-256 `5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7`，引用[交付索引](../native_resume/backup_all_001/dsp_all/bitstream_receipt.json)。已只读确认SSH别名`hap-dell`可连接到Windows主机`DESKTOP-D3`；使用现有VCU118/XCVU9P、PCIe XDMA和已安装硬件工具。实际JTAG target/device、独占状态、Windows驱动与运行资产仍须从本次现场检查记录确认，不凭历史串号默认选择首个设备。

**阶段范围与通过标准。**

1. 在本实验`board_test/`和Dell独立目录保存新脚本/配置、传输与运行收据，远端新bit大小/SHA必须与本地产物一致。若复用的发布脚本严格绑定旧SHA，只在候选副本中改为本次明确身份，并保留所有检查；不能关闭校验来接受任意镜像。
2. 确认目标板空闲且本任务独占后，通过已有Hardware Manager路径实际program到SRAM，记录具体目标、文件身份、命令、完整日志、退出码和下载后状态。旧发布bit及发布manifest保留；硬件CSR的ABI/build标识不能单独区分属性变化后的新旧bit，必须同时保留本次实际下载链路。
3. 检查PCIe/XDMA接口、最终magic/ABI、80MHz核心、格式/布局、idle/error状态；实际DDR写入/读回成功才记DDR传输通过。健康检查本身不当作数值验证。
4. 计划回放现有封存12条完整算子命令：KV32/KV128各Attention层0、8、16、24、31与Gate/Up层0。参考为既有真实输入/输出及已与其逐字节一致的封存RTL重放，见[选集说明](../../../../docs/evidence/kv32_kv128_cycle_sim/README.md)。新板输出必须全字节比较，保留命令身份、输入/权重/gold/output SHA及首个差异。该选集不等于所有32层均有独立算子gold。
5. 运行原16请求、每请求32新token的真实端到端回归，保持原模型/量化/贪心解码/EOS和退休规则。原请求[requests16.json](../../../../examples/requests16.json) SHA为`9d0db082e3504b2077971f0a3a1370f70c27474dd746dc7309ebca6c818444ed`；封存[outputs.json](../../../../docs/evidence/inference_chat16/outputs.json) SHA为`975c342521ebe538da25cf9d52426c7a65c57632fa256375c2930ce26e04a034`。逐slot比较generated_token_ids、数量、stop_reason及轨迹；按原请求预期512个新token、50个完整round和3200条硬件命令，实际值以本轮日志核对。必须正常完成、硬件最终quiescent、句柄关闭；仅exit0或可读英文文本不够。

端到端与封存输出相同只称本轮候选回归一致性；既有完整模型独立数学oracle仍NOT_ESTABLISHED，不把上述回归扩大成该oracle的数值PASS。Down仍由CPU执行。本阶段不新增功耗采集，也不以旧功耗作为新候选实测。

**执行与资源。** 沿用用户取消固定墙钟强停的要求，本轮测试不按整个任务累计时长强杀；硬件通信的单操作故障超时、真实设备错误、输入身份与数值不一致仍须保留并停止受影响测试。只操作本任务拥有的板会话/进程，保留Dell适用内存与磁盘保护（旧主机运行基线为任务RSS≤8GiB、系统可用RAM≥2GiB，现场核查后记录实际设置）。不终止其他使用者任务，不改驱动、供电/保护配置或自动重启整台Dell。若这些实质操作成为必要条件，先保存现场失败证据并提出具体阻塞；无关准备继续。真实板测完成前不修改旧结果为新PASS。

| 子阶段 | 当前结果 |
|---|---|
| Dell SSH主机连接 | PASS，DESKTOP-D3 |
| 板卡/驱动/工具/独占核查 | PASS，唯一XCVU9P/JTAG目标，现有XDMA驱动，持续公共板锁 |
| 新bit远端传输与身份核验 | PASS，Dell独立目录文件为80159263字节，SHA-256与第5节一致 |
| 新bit SRAM下载 | PASS，2026-11-15 07:19完成；精确目标/bit身份通过、startup HIGH、Vivado exit0 |
| PCIe/ABI/DDR健康 | PASS，严格身份/状态符合；两DDR规范输入缓冲各196608B写入读回逐字节一致 |
| 12条封存算子逐字节回归 | PASS，12/12完整输出逐字节一致，命令身份/ACK/最终空闲与关闭均通过 |
| 原16请求端到端token回归 | PASS，16请求/512 token、50轮/3200命令；最终outputs.json与封存参考整文件相同 |
| 本轮板测集中验收 | PASS，原始证据/全部148文件核验完成；最终空闲、句柄/自有进程关闭、租约释放 |

### 6.1 Dell准备与编程前观测

现场主机为Windows 10 22H2 / DESKTOP-D3，Vivado与hw_server使用`D:/Xilinx/Vivado/2022.2/bin/`；现有XDMA设备状态OK、ConfigManagerErrorCode=0，PCI ID为10EE:9018。默认PATH的Python为3.6.5，本轮使用旧板测已验证的独立Python3.12目录，不改系统环境或驱动。Dell新测试目录为`D:/ScaleLLM_final_model/dsp_all_board_20261115_001/`，其中新bit实际大小与SHA已匹配。原始现场清单与传输记录在`board_test/environment/`。

编程前旧镜像的只读CSR检查因MAGIC不符退出；这是板上既存镜像未知/不符的观测，不属于新候选失败，也未触发CSR写入或DMA。后续独立枚举真实JTAG并确认独占与精确目标后继续已授权的SRAM下载，编程后仍严格检查全部MAGIC/ABI/时钟/布局/状态。初次后台板锁随Windows SSH会话结束退出；该次JTAG脚本因租约owner不存活而中止，实际未下载。工程正在改为持续前台连接持有公共板锁。所有失败日志保留，新bit SRAM下载与功能结果尚为NOT_RUN。

2026-11-15 07:10现场JTAG只读枚举成功：`BOARD_TEST_TARGET_COUNT=1`，完整目标`localhost:3121/xilinx_tcf/Digilent/210308B76D50`，唯一器件`xcvu9p_0` / PART `xcvu9p`，IDCODE `00010100101100110001000010010011`，Vivado退出0；见`board_test/environment/jtag_enum_live_attempt2.stdout.txt`。同次编程前MAGIC/ABI/时钟/布局/状态等11项原始CSR全部为`0xffffffff`，属于无效PCIe读数，不将其解释为有效旧ABI或新候选功能失败。后续guardian的PID数组转换问题已修复并改用前台持续持锁；第一次program准备因自有hw_server随先前会话退出而中止，未执行下载。该脚本问题不改变输入或验收标准。

### 6.2 新候选SRAM下载：PASS（2026-11-15 07:19）

主控核对`board_test/environment/program_candidate_attempt2.stdout.txt`及退出收据，实际下载使用Vivado2022.2与已枚举的完整目标/`xcvu9p_0`，输入bit大小80159263字节、SHA-256 `5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7`。原生PID19088，07:18:35启动、07:19:37收尾，退出0。日志明确`End of startup status: HIGH`、`program_hw_devices`成功，刷新识别2个MIG core，输出`FINAL_SRAM_PROGRAM_COMPLETED; READ_ONLY_FINAL_ABI_PREFLIGHT_REQUIRED`。本任务持锁owner为8248。仅写入易失SRAM，configuration_flash_written=false；未替换发布文件。该结果只证明指定新镜像完成配置，下载后的PCIe/DDR与数值回归继续执行，尚不记功能PASS。

### 6.3 下载后PCIe身份检查与恢复（已恢复）

使用已验证路径的Python3.12.10执行严格只读检查，下载后11项CSR仍全部为`0xffffffff`，MAGIC断言失败、进程退出1；完整输出为`board_test/environment/identity_after.ssh.stdout.txt`。该值与下载前相同，当前定位为尚未解决的主机设备访问/PCIe链路问题，不能据此归因为DSP数值实现失败，也不能跳过身份检查启动DMA。原生program回执及Vivado日志已独立收录到`board_test/program/`。

后续仅对本轮已核实唯一XDMA设备执行设备级恢复/重新枚举，保存前后PnP/CSR及结果；用户已授权的板测范围内无需为这一可恢复操作逐步确认。保留现有驱动与整机运行状态。DDR写入/读回、12条算子回放及16请求回归仍NOT_RUN；若确需整机重启或物理操作，则作为具体外部阻塞单独说明。

07:28设备级恢复完成：`pnputil /restart-device`仅作用于已核对的`PCI\VEN_10EE&DEV_9018&SUBSYS_000710EE&REV_00\4&3533FCBB&0&0008`，原生退出0、明确Device restarted successfully，前后PnP状态均OK/Problem0。驱动SHA-256前后均为`bfc1039ae17cbac465a268a96922d60ebd702dfe2388df8b66d51b2a60fb0932`，whole_host_reboot=false，driver_installed_or_modified=false；见`board_test/environment/pnp_recovery_receipt.json`。

主控独立核对恢复后的`identity_after_restart.stdout.txt`及exitcode0：MAGIC=0x53463136、ABI=0x00010000、CAPABILITIES=0x3f、CORE_HZ=80000000；Attention/MLP布局0x53464101/0x53464102、格式0x48384103/0x48384605，与原合同逐项一致；STATUS/ADMISSION_ERROR/DONE_ERROR均0。PCIe/ABI门槛现已通过，前失败完整保留且已被本次精确设备重启解决。两路DDR实际读写和后续数值回归继续执行。

### 6.4 两路DDR实际传输：PASS

`board_test/health/receipt.json`记录在规范`tensor_spans(5)`输入缓冲中执行DDR0/DDR1各196608字节写入与读回：attention_input局部地址1448083456、mlp_input局部地址310378496。主控直接读取回传的两对`.input.bin`/`.readback.bin`，核对实际长度、逐字节相等及SHA与收据一致；SHA分别为`4d26b8a3af3b47566bdb6d0f35d2458f3f1bd219612cd6850d0c9fe6a04e104c`和`0d6f099031c4abdc6a0e21eb95860a33f8c2617a6e0c311004a36392dc170e83`。传输日志53条，单次transport超时5000ms；操作耗时0.109s。最终STATUS/ADMISSION_ERROR/DONE_ERROR均0、session_closed=true。此结果覆盖该两处实际缓冲的读写通路，模型权重的完整实际传输/回读继续由算子与模型测试验证。

### 6.5 封存算子回放参考复核

KV32 Gate/Up layer0 / command1986的发布仿真引用较早`cycle_decomposition_l0_m_002`，而本轮拟统一从`0_Source/operator_timing_kv32/kv128_compare/board/native/run_002/payloads/`取回放数据。主控直接核对旧`cycle_sim_capture_002/payloads/`与该run_002实际文件：descriptor均256B/SHA `7641b2928d1e5af2cdfb762a79eed7cf056a80c9ed380cbf5c58cc76ae23ce76`，input均196608B/SHA `fbe1eecfcd550d98da30116170f1d61e14aecfe66fd6771698b8112c1d88ff59`，output均917504B/SHA `6fcd577d080d353ff9d111d1afdd838694fe29e408431de50ea7cd3d14f1ed4d`。已封存仿真`cmd_1986_sim_output.bin`实际大小/SHA也与该output一致；原manifest SHA `1b1925535086339bc040ba17617d607dd3fc1cac5841d74dfa5dab59a6f50789`与公开raw_logs_index逐项匹配，两份capture journal分别绑定其实际输入/输出。故本轮统一使用run_002文件不改变这条选集的数值参考或覆盖。原两次板捕获done_cycles为1468365/1468118，属于运行时延差异，不作为输出不等或要求本轮周期精确相同的依据。该复核本身不是本轮新板输出PASS。

### 6.6 新板12条完整算子回放：PASS

主控直接核对`board_test/replay/report.json`、12个新板`cmd_*_output.bin`、参考清单与旧封存仿真实际输出。参考清单SHA为`ceab557efbb65eb6d077b9801365c063e016aec7efc07b853af48410660a5d93`，绑定发布analysis、validation manifest及实际descriptor/input/output/KV/RoPE/权重身份。参考payload已在Dell原目录，只在该主机内复制并核验，不修改gold。

| command | KV | 算子/层 | 新板完整输出字节 | 新板cycles | 逐字节结果 |
|---:|---:|---|---:|---:|---|
| 1986 | 32 | Gate/Up L0 | 917504 | 1468395 | PASS |
| 8130 | 128 | Gate/Up L0 | 917504 | 1468528 | PASS |
| 1985 | 32 | Attention L0 | 196608 | 1616899 | PASS |
| 8129 | 128 | Attention L0 | 196608 | 3601846 | PASS |
| 2001 | 32 | Attention L8 | 196608 | 1614676 | PASS |
| 8145 | 128 | Attention L8 | 196608 | 3599819 | PASS |
| 2017 | 32 | Attention L16 | 196608 | 1614154 | PASS |
| 8161 | 128 | Attention L16 | 196608 | 3599547 | PASS |
| 2033 | 32 | Attention L24 | 196608 | 1613949 | PASS |
| 8177 | 128 | Attention L24 | 196608 | 3600600 | PASS |
| 2047 | 32 | Attention L31 | 196608 | 1614303 | PASS |
| 8191 | 128 | Attention L31 | 196608 | 3599592 | PASS |

12条实际输出均与对应封存sim_output全字节相同，长度与SHA同参考清单一致。每条completion_words==submitted_words，输出比较在ACK之前，ACK后STATUS/ADMISSION_ERROR/DONE_ERROR均0，最终quiescent=true、handles_closed=true。回放总耗时6.688s（含本次权重与KV/RoPE写入/回读），监控峰值RSS125898752B、最低可用内存10209140736B；无固定全任务时间终止。该12条选集PASS不扩大为全部层独立数值gold或完整模型独立oracle。

端到端候选环境先验证Dell旧实测38个文件再复制到独立runtime；主控逐一重算回传文件大小/SHA并与candidate_source_identity.json核对。37个文件与旧版本完全相同，唯一run.py差异是删除wall-seconds参数及两处整轮墙钟终止分支，并记录wall_limit_seconds=null、fixed_wall_time_termination=false。原数值与传输代码未改。首次新launcher在import psutil处退出，未进入模型或打开板；原失败保留，随后用Windows原生ctypes接口替换此非数值包装依赖并继续。

### 6.7 原16请求端到端回归启动与早期进度（07:43历史记录）

候选完整推理于07:40:02启动，Dell Python PID24908（birth `2026-11-14T23:40:02.3722480Z`），前台持锁owner8248。使用原requests16、原模型/资产、完整启动哈希，未使用跳过大文件校验的prepared-config。数值库线程各1；Windows原生CPU亲和性读回复核为0–7。单命令120s、单transport5000ms；fixed_wall_time_termination=false。修复后的launcher使用ctypes，无需新增psutil或修改系统软件。

主控通过SSH只读实际`inference/progress.jsonl`及进程状态确认：完整启动哈希已结束，第一轮32层完成61.985s，第二轮61.703s，07:43已完成2/50轮、当前command170 complete。此时仍在原提示词处理阶段，生成token为0；进程RSS约2.1GiB、系统可用约7.5GiB，guardian为LEASE_HELD、stop_reason=null、stderr为空。首轮估计剩余约51分钟，仅作进度估计，不作为时间终止条件。最终仍须完成50轮/3200命令及512 token逐项回归，当前不将运行中状态写成PASS。

### 6.8 端到端最终结果与板测集中验收：PASS

2026-11-15 08:36:11原推理进程PID24908正常退出0；本轮出生时间与launch/owned-tree/原生退出收据逐项匹配。16个请求均生成32个新token并以length_limit结束，共512 token、50个完整32层round、3200条硬件命令。`execution=COMPLETE`、`final_quiescent=true`、`handles_closed=true`，最终STATUS/ADMISSION_ERROR/DONE_ERROR均0。主控直接比较本轮[outputs.json](../board_test/inference/outputs.json)与原封存参考：不仅token ID、文本、位置、结束原因一致，12126字节整文件完全相同，SHA-256为`975c342521ebe538da25cf9d52426c7a65c57632fa256375c2930ce26e04a034`。

[最终回归审计](../board_test/inference/regression.json)及其原生exit0收据已核对：逐槽每轮token前缀、position、epoch归属、正常退休和原子提交全部通过；实际XDMA日志中3200条完整描述符写入、对应输入、两次完整completion读取、实际输出、匹配ACK及长度/错误/cycle信息全链通过，共934209条实际IO记录。主控另从原始progress直接计数：command_begin/command_complete各3200、position_committed及LM-head各50、host_down_complete及layer_prepared各1600；未用退出0替代覆盖核查。附加核对本次端到端第32轮六条封存选中命令1985/1986/2001/2017/2033/2047，实际active_mask均0xffff，六对input/output SHA全部与既有reference_manifest一致。

完整原生进程墙钟为3368.984946s（56分8.985秒），包含完整启动资产核验；`run.json.seconds=3312.597650528s`从启动哈希完成后的report创建计起，不能混作总耗时。3200条命令实际FPGA周期合计4657997368，亦不替代整模型墙钟。推理进程峰值RSS2510462976B（约2.34GiB），最低可用内存7867686912B；整板测自有进程树峰值RSS2886406144B（约2.69GiB），最低可用内存7509217280B、最低可用磁盘182921015296B。固定整轮时间终止始终false，内存/磁盘保护未触发。

主控重算的最终原始日志身份：

| 文件 | 字节 | SHA-256 |
|---|---:|---|
| [run.json](../board_test/inference/run.json) | 2223653 | `bbaaf73157f395e11bfb5416c3f55394af3ab3eee66db08f88bb5fe5c585161e` |
| [progress.jsonl](../board_test/inference/progress.jsonl) | 4159375 | `0d9805846297298b3a2fd3e5fd3f48dc45a1c1579555906874e652dbf41beb0e` |
| [xdma.jsonl](../board_test/inference/xdma.jsonl) | 227912325 | `b40117ff144e29725281a965c40cbcb6a7d1ee0c7956b78aec039ba397c9bf81` |

08:38:12[收尾收据](../board_test/board_stage_closure.json)为PASS：最终只读身份检查exit0；38个候选运行源文件再次逐项哈希匹配；原program根、该任务hw_server与全部推理进程/子进程均退出，实际Vivado/hw_server/cs_server服务清单为空。guardian最终CLOSED、lease_released=true、active_owned_pids为空、stop_reason=null，原前台守护也已退出0。本次候选`5d78519a…`继续保留在板卡易失SRAM中；未写Flash、未重启整台Dell、未安装或修改驱动。初始PCIe全0xffffffff通过一次精确XDMA设备重启恢复，所有前置失败与修复记录保留。

[远端证据清单](../board_test/evidence_inventory.json)SHA-256为`1e282c9024b11cf05d08bfbac52889842b2c80e841d464ebfd8d00fdda8016d7`，共148文件/241102029字节；[传输回验](../board_test/transfer_verification.json)PASS。主控在本地独立重算这148个实际文件的全部大小/SHA，全部与远端清单一致，并复核最后38文件源码身份与运行前候选manifest完全相同。测试目录为Dell `D:/ScaleLLM_final_model/dsp_all_board_20261115_001/`及本实验`board_test/`；原发布镜像和manifest保持不变。

**本轮已授权板测全部完成。** 结论覆盖新全DSP候选的真实SRAM配置、PCIe/ABI/双DDR、12条选定算子全字节回放及原16请求完整回归。Down仍在CPU；完整模型独立数学oracle仍为NOT_ESTABLISHED，本阶段未新增功耗测量，不将回归一致性扩大为这两项新结论。
