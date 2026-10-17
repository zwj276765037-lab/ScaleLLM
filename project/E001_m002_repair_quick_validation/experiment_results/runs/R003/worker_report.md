# R003 · M002 构建修复与快速验证终态

负责人：SM004 / A006 工程实验（m002_build_verify）。日期：2026-10-15 Asia/Shanghai。

- execution：completed；本轮所有受管工具进程已结束。
- verdict：所选源静态审计、完整board RTL展开、定向功能仿真及真实BD构造/校验已获得相应范围证据；保留BD地址别名critical与既存RTL告警，不构成implementation签核。
- applicability：当前唯一硬件实现入口及各attempt的源/工具/约束hash；最终输入复核见`final_input_recheck.json`，数据/CSR所选依赖复核见`applicability_recheck.json`。
- review：提交主控审核，非用户最终验收。

## 实现交付

- 新MLP DATA口`M_AXI_MLP_DATA`经DDR1 SmartConnect S00；DDR1增至3SI/2clock，core100 MHz→UI200 MHz；Host S01、WEIGHT_C1 S02。Attention DATA/WEIGHT_C0仅到DDR0。构造和build复查实际连线、单目标地址空间与CDC时钟，静态审计检查新口256bit宽度和clock ASSOCIATED_BUSIF。
- 完整清单加入dedicated weight/data router并保留原helper依赖；根`vivado/scripts/m002_*`仅兼容转发，真实工具入口位于`project/hardware/vivado/scripts`。
- `ddr_timing_recovery.xdc`去除无依据multicycle、derate、LOC/Pblock。默认M002构建不加载legacy mission0004/0005物理XDC；旧文件不改，mission0005与M001/只读旧源hash一致。place/route明确报缺少当前设计相容物理检查的技术错误，未新增用户批准流程。
- 快速入口保持8线程、独立新报告目录、超时进程组清理、版本/命令/起止/退出码/hash、错误扫描和唯一PASS marker。新增真实BD validate-only入口在显式`generate_target all`前退出；Vivado传播会自行建立SmartConnect内部BD配置，本轮未显式生成完整IP outputs、未正常综合或实现。

## 结果与证据

| 验证范围 | 结果 | 证据 |
| --- | --- | --- |
| 联合CPU回归 | 49/49 PASS | `attempts/AT006_final_cpu_and_static_contract/command_0.log` |
| 完整选源静态审计 | PASS，87 leaves/104模块，core100/UI200及新增256bit DATA口 | 同AT006 `command_1.log` |
| 完整board RTL `synth_design -rtl` | PASS，88 RTL、1,327,023层级RTL对象、0黑盒；工具阶段3m34s | `project/hardware/vivado/reports/m002_R003_AT004_final_complete_board_rtl_elaboration` |
| 真实板级BD | `validate_bd_design`退出0；288s含启动，未进入显式IP output生成/正常综合 | `project/hardware/vivado/reports/m002_R003_AT007_actual_bd_validation` |
| DATA router实际XSim | 11组检查PASS，selected依赖当前不变 | R002/AT002及对应hardware/vivado/reports |
| M002布局CSR实际XSim | 10组检查PASS，selected依赖当前不变 | R002/AT003及对应hardware/vivado/reports |
| 权重+真实assembler/join XSim | 38组检查PASS，17个second-pending且egress-full周期，完整字节/组/元数据/顺序比对 | R002/AT008 `m002_R002_AT008_final_weight_groups` |
| 真实Attention/MLP双reader/CDC/halfgroup前端XSim | 7组场景PASS，每引擎64完整组，真实有限FIFO/背压/排空/重启 | R002/AT009 `m002_R002_AT009_final_real_frontends` |

RTL对象数不是综合资源统计；有限事务/整数向量不代表完整32层端到端数值回归。R002权威功能报告由RTL负责人维护，本文件仅引用实际运行终态。

## 告警与BD地址解释

完整RTL日志：0错误、0严重警告、296普通警告。29条Synth8-7137来自`hap_activation_cache_8row.sv`4条、`hap_linear_tile_accum_dual_s42.sv`16条、`hap_mlp_silu_mul.sv`9条；三文件当前hash与M001目标及原源hash完全相同。逐条身份和位置见AT004 `reset_priority_warning_provenance.json`，仍需后续数值/综合复位语义审核。

真实BD保留5条critical：1条12-3645逐个add_files性能提示，4条41-1354跨master的DDR0/DDR1本地地址别名提示；另14条普通warning，完整内容见AT007 `warnings.json`。未降低severity、未消警、未作critical waiver。

AT007 `bd_address_decode_evidence.json`保存顶层及三份真实SmartConnect内部BD的原始参数摘录/路径/hash：Host split MMU两段为base0/size31→route0，base0x80000000/size31→route1；d0/d1核心SI各有base0/size31的唯一M00路由，d1 Host SI为IS_CASCADED=1，接收上级路由标签；d1 M00 sc2axi的AXI_ADDR_WIDTH=31、内部SC宽64，MIG AxiAddressWidth=31。顶层连线证明每个核心master只有专属DDR出口，Host才可到双DDR。saved addressing未序列化显式excluded segment，核心每空间只指派一个slave segment。

因此core DDR1 local地址与Host的0x80000000+local在各自入口译码后，进入同一DDR1 31bit出口时落到相同local低31位。基于真实参数的边界复算见`address_boundary_recomputation.json`。这解释本次已保存配置中的别名及截断，没有新错路由的静态证据；不等同SmartConnect全事务仿真、综合网表或板卡通信验证，critical日志继续保留。

## 失败尝试与证据保留

R003/AT001保留旧物理测试20/21失败；旧XDC字节未改，测试改为验证M002不加载历史分区。AT002在新CSR改变源身份后主动终止exit143，不算PASS。AT005保留旧MLP channel0期望的2项失败及漏传HAP_BOARD_BUILD入口参数失败；按明确DDR1合同修正后AT006通过。

R002保留AT001声明前引用编译失败、AT004 delta-cycle旧完成标志race、AT005/006/007首组oracle未初始化为全X的失败。最终只修测试台触发/采样并加期望非X硬断言；数据/地址/字节/元数据/数量期望不放宽，生产RTL在最终完整elaboration后未变。独立Python对AT007实际MLP payload逐字复算见R002/data。所有原始attempt独立保留。

## 后续fresh synth入口（仅静态核对，未执行）

真实入口`project/hardware/vivado/scripts/run_vcu118_board.sh`：先`create`，设置HAP_JOBS=8、新HAP_PROJECT_DIR及新HAP_REPORT_DIR；正常create生成完整IP/wrapper；再同一project配另一新report目录运行`synth`。本轮validate-only工程不能直接作为synth输入，因为缺完整IP输出/wrapper/create回执。

build技术阻断只在place/route；fresh synth可达launch_runs synth_1，保留输入/BD/ROM/clock/DRC检查并在post_synth报告及fresh_synth_complete.txt停止，不进入implementation。可以据fresh synthesis获取资源与告警证据，不代表critical waiver或实现签核。本轮未运行正常综合、place/route、bitgen、板卡、GPU、PPL或ACC；后续物理检查适配、完整32层数值和板级闭环仍待工程验证。

以下为后续独立新鲜综合的可执行参数示例，**本轮未执行**；目录必须未使用：

```sh
HAP_JOBS=8 HAP_PROJECT_DIR=/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/hardware/vivado/project/m002_fresh_synth_candidate HAP_REPORT_DIR=/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/hardware/vivado/reports/m002_fresh_create_candidate /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/hardware/vivado/scripts/run_vcu118_board.sh create
HAP_JOBS=8 HAP_PROJECT_DIR=/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/hardware/vivado/project/m002_fresh_synth_candidate HAP_REPORT_DIR=/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/hardware/vivado/reports/m002_fresh_synth_candidate /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/hardware/vivado/scripts/run_vcu118_board.sh synth
```
