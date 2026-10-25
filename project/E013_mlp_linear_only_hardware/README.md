

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# E013 · mlp_linear_only_hardware

关联：M006 / SM026

## 原始管理记录

- [实验协议](experiment_source/protocol.md)
- [来源摘要](experiment_source/summary.md)
- [结果摘要](experiment_results/summary.md)
- [状态摘要](experiment_status/summary.md)

## 当前结果摘录

# E013：实验结果摘要

<!-- A022_CURRENT_G5_BEGIN -->
当前G5（2026-10-25T00:54:01.725589+00:00）：G4R LIMITED_PASS、GU-only constructor/综合与AT011同DCP结构资格已完成。真实96lane×148 guard FDRE（37bit×2channel×2entry）、Down0、MLP3072DSP、GUmeta448URAM，Attention/共享核与10/5/5ns时钟身份通过；此范围不等于完整板级签核。

R008/AT001_impl已自然NATIVE_STAGE_COMPLETED：native0/nullstop/102输入无漂移/0survivor，peak27.379GiB。真实routed DCP665825940B，SHA `cc34f49bef612472367f7d273596d09dede15128d3b72a2708507e4c6d6c7cc4`；正式1687352/1687352全布通、routing errors0。正式STA WNS+.002/TNS0/setup0、WHS+.010/THS0/hold0、WPWS0/pulse0；最差GU控制计数→CSR读数据9.446ns、其中route7.440ns，时序裕量很小。最终no_clock/internal unconstrained0；PERST及双DDRreset缺1input/2output delay。DRC0Error/Critical、15762Warning；CDC6×10+2×11 Critical及5688Warning保留限定结构解释。原`stage_quality` overall FAIL保持，不能用native0冒充全签核。详情见`runs/R008/attempts/AT001_impl/{result,formal_timing_observation,engineering_terminal_summary}.json`及历史时间线。

已确认用户三域clock_groups覆盖4个command handshake的10ns Max-DPO：原10个合并count位路径Slack inf/Asynchronous Clock Groups，coverage不代表active bound；四独立bus-skew均MET，不能替代绝对延迟。AT002补取四scope/十D、两reset8级、两DSP代表及d0SMC后，按用户先取bit优先级于UTC00:30:51受控SIGTERM/-15收束，原因USER_PRIORITIZED_PRELIMINARY_BITSTREAM；30工件及partial/NOT_COLLECTED保全、0survivor/锁释放，原FAIL不改。d1SMC未完成，d0同域+4.076ns不证明异域Max-DPO。

**工程验证版bitstream已交付**：`hardware/vivado/reports/m006_gu_AT003_preliminary_bitstream/native_output/ScaleLLM_MLP_GU_only_ENGINEERING_VALIDATION.bi

（摘录截断；完整记录见链接。）

## 每个运行批次

| 批次 | 详情 | 具体尝试数量 |
| --- | --- | --- |
| R001 | [本批结果与证据](experiment_results/runs/R001/README.md) | 31 |
| R003 | [本批结果与证据](experiment_results/runs/R003/README.md) | 9 |
| R004 | [本批结果与证据](experiment_results/runs/R004/README.md) | 1 |
| R005 | [本批结果与证据](experiment_results/runs/R005/README.md) | 1 |
| R006 | [本批结果与证据](experiment_results/runs/R006/README.md) | 26 |
| R007 | [本批结果与证据](experiment_results/runs/R007/README.md) | 11 |
| R008 | [本批结果与证据](experiment_results/runs/R008/README.md) | 4 |

## 原工程历史结果


本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
