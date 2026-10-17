# R002 · SM002 / A004 · RTL 专属 DDR 修复报告

负责人：工程实验子 agent `/root/m002_rtl_repair`。本报告为RTL子任务终态；工程范围内修改和四套定向仿真已完成，等待父主控阶段审核。用户授权仅修复、CPU 快速测试、完整 RTL elaboration 和定向仿真；不含正式综合、implementation、bitgen、GPU、板卡、PPL/ACC。

- execution: completed（仅本报告RTL修复与定向功能范围）。
- verdict: PASS for qualified routing/reader/group/AXI/CSR tests；不代表完整数值、时序、板级验收。
- applicability: `data/final_source_identity_check.json` 核对当前6份RTL与full-board elaboration回执、4份最终TB与各PASS回执SHA256全部一致。
- review: submitted to parent；M002全局阶段判断由主控负责。

## 已实现的连接

- Attention 两条逻辑权重流均在 DDR0 UI 域，进入专属 DDR0；MLP 两条逻辑权重流均在 DDR1 UI 域，进入专属 DDR1。保留两半组及六个逻辑 base 字段，地址全部透传为引擎专属 DDR 内 local offsets。
- 新 `hap_axi512_dual_engine_dedicated_read` 为每引擎成对验证描述符，保存第二半流，在各自 DDR 队列按 stream0/stream1 顺序发出；两 DDR 独立推进。复用原 async FIFO、ordered issuer、tag/elastic response、reset manager 和维护排空协议；返回标签表示本引擎 logical stream。
- `resource_top` 只改两引擎内部 reader 的 clock/reset 对应；原命令/payload CDC、Hadamard、ScaleCode、format05 和数值运算模块保持。
- 新 `hap_axi256_dedicated_data_router` 将 Attention data 完整旁路至 DDR0；MLP tensor/meta 的 command-lock 仲裁保留并独立接 DDR1。production 新 `mlp_data_axi_*`，board 新 `m_mlp_axi_*` / `M_AXI_MLP_DATA`，256-bit AXI4 read/write，core100MHz。
- MLP CSR 新只读 `MEMORY_LAYOUT_ID 0x2B8 = 0x4D303032 (M002)`；数值 format/ABI 保持。写该 CSR 返回 SLVERR，避免 Host 将新地址图误用于旧硬件。
- 设计、遥测、CDC、maintenance 与边界详见 `project/hardware/source/m002_dedicated_ddr.md`。Host KV 区域仅保留地址，未增加或验证 off-chip KV 生命周期。

## 文件所有权和修改清单

修改：

1. `project/hardware/rtl/integration/hap_attention_mlp_production_core.sv`
2. `project/hardware/rtl/integration/hap_attention_mlp_board_core.sv`
3. `project/hardware/rtl/integration/hap_attention_mlp_resource_top.sv`
4. `project/hardware/rtl/integration/hap_mlp_axil_control.sv`

新增：

1. `project/hardware/rtl/integration/hap_axi512_dual_engine_dedicated_read.sv`
2. `project/hardware/rtl/integration/hap_axi256_dedicated_data_router.sv`
3. `project/hardware/tb/hap_axi512_dual_engine_dedicated_read_tb.sv`
4. `project/hardware/tb/hap_axi256_dedicated_data_router_tb.sv`
5. `project/hardware/tb/hap_mlp_memory_layout_csr_tb.sv`
6. `project/hardware/tb/hap_m002_dedicated_frontends_tb.sv`
7. `project/hardware/source/m002_dedicated_ddr.md`

保留原 `hap_axi512_paired_2client_read_wrr.sv` 与 `hap_axi256_3to1_arbiter.sv` 字节，分别复用其 helper 和 command-lock 行为。BD/源清单/运行脚本由 build worker 维护；Host 代码由 Host worker 维护。本报告不代替他们的交付和原始证据。

## 已核对的原始运行

工具由 build worker 唯一串行调度。每次尝试的 command/status 位于本 R 的 `attempts`；工具 log、versions、源 SHA256 位于下列实际 report 目录。

| 尝试 | 当前真实结果 | 证据 |
| --- | --- | --- |
| R002 AT001 dedicated_weights | xvlog FAIL，未到 elaboration。新 adapter 的 `global_freeze_core` 在声明前引用；已修复。失败证据保留 | `project/hardware/vivado/reports/m002_R002_AT001_dedicated_weights/xvlog.log` |
| R002 AT002 dedicated_data | XSim PASS，11 项主检查；DDR0 read/write command 12/12，DDR1 24/24；完整写数据1536/3072 bytes；stall517/112；DDR0堵塞时MLP tensor/meta先完成 | `project/hardware/vivado/reports/m002_R002_AT002_dedicated_data/xsim.log` |
| R002 AT003 memory_layout_csr | XSim PASS，10项；ID/format/ABI读取、R背压稳定、AW/W分离握手、full/partial/zero strobe只读写拒绝、reset后ID | `project/hardware/vivado/reports/m002_R002_AT003_memory_layout_csr/xsim.log` |
| R002 AT004 dedicated_weights_full_groups | xvlog/xelab PASS、XSim FAIL。690ns 在更改target后的同一delta读取旧complete而提前检查；仅修TB在时钟边界采样，计数期望未改 | `project/hardware/vivado/reports/m002_R002_AT004_dedicated_weights_full_groups/xsim.log` |
| R002 AT005 dedicated_real_frontends | XSim FAIL，native MLP group0比较不符；保留完整失败并进一步诊断 | `project/hardware/vivado/reports/m002_R002_AT005_dedicated_real_frontends/xsim.log` |
| R002 AT006 dedicated_weights_full_groups | XSim FAIL，逐512位响应检查未报错，首个group比较不符；原生与mock组装oracle存在相同time0触发模式 | `project/hardware/vivado/reports/m002_R002_AT006_dedicated_weights_full_groups/xsim.log` |
| R002 AT007 real_frontends_diagnostic | XSim诊断FAIL：actual payload确定，SV expected全X，meta相等。独立Python逐字地址模型复核实际完整256bytes一致，证明该首组失败是TB oracle未初始化；没有放宽数据/计数/映射 | `project/hardware/vivado/reports/m002_R002_AT007_real_frontends_diagnostic/xsim.log`；`data/AT007_independent_oracle_crosscheck.json` |

AT007 根因：两TB以 `always @*` 生成group期望，group计数在声明时初始化为0，reset持续赋0未产生值变化，首次比较前未触发组合块。只改为 `always_comb` 保证time0执行并增加 `$isunknown(expected)` 硬失败断言，原地址/数值函数/metadata/计数期望保持。复现AT007逐字检查见 `data/check_native_diagnostic.py`。

R003 AT004 full board RTL `-rtl` 原始 `vivado.log` 与 `elaboration_scope.txt` 已核对PASS：88 RTL、1,327,023 elaborated hierarchical cells、0 blackbox、0 error/critical。之后只改TB/文档，当前6份RTL与其hash回执完全一致。证据：`project/hardware/vivado/reports/m002_R003_AT004_final_complete_board_rtl_elaboration/`。这是RTL elaboration，不是正式逻辑综合或资源测量。

最终复测均为新AT，未覆盖失败记录：

| 尝试 | 实际结果与量化覆盖 | 原始证据 |
| --- | --- | --- |
| R002 AT008 final_weight_groups | XSim PASS、exit0、38主检查；Attention/MLP完整组115/184；主good-flow全返回58880/47104bytes，physical AR160/128，对应logical pair80/64；second_pending且egress full实测17cycles；ARstall250/27、Rstall346/220；含维护排空/重启、三个reset、错RRESP/earlyRLAST冻结与hard-reset后good flow | `project/hardware/vivado/reports/m002_R002_AT008_final_weight_groups/xsim.log`；本R `attempts/AT008_final_weight_groups/status.json` |
| R002 AT009 final_real_frontends | XSim PASS、exit0、7主检查；真实reader/命令CDC/深8halfgroup FIFO/assembler/join/MLP telemetry CDC；完整组64/64，physical AR32/16，完整返回32768/16384bytes；输出长期阻塞导致FIFO物理Rstall505/598cycles；活跃maintenance完整排空后softclear | `project/hardware/vivado/reports/m002_R002_AT009_final_real_frontends/xsim.log`；本R `attempts/AT009_final_real_frontends/status.json` |

AT002/003/008/009均在真实工具日志出现对应PASS与`HARDWARE_AGENT_SIM_PASS`；当前源码身份核对10/10通过。无生产RTL为通过TB而调整、无期望数值放宽。

## 独立期望与覆盖

权重 TB 的地址、burst顺序、完整512位响应和每路累计字节由独立测试地址/数据函数计算；没有从 DUT 的 tag、grant、sequence 或返回 payload 反推期望。真实 Attention assembler/MLP join 对接受的两半流再做4096/2048位完整group、metadata、列顺序检查。含1/2/4/16beat、Attention-only/shared、DDR0堵塞下MLP独立进度、伪随机AR/R背压和VALID稳定、维护排空/后续重启、core/DDR0/DDR1 reset和bad RRESP/early RLAST冻结。

原生 frontend smoke 使用真实读器、命令 CDC、深8半组FIFO、组装器和MLP统计快照；64组/引擎、长期阻塞输出造成有限FIFO R背压，在活跃命令中请求维护后放行并核验完整排空。它覆盖 native reader 数据路径，不代表数值矩阵运算端到端验证。

数据 TB 使用三个独立请求 client 与两 DDR 模型，按固定引擎归属检查物理地址、完整256位读/写数据、WSTRB、RLAST、R/B响应和command lock，包含伪随机五通道背压和clear/reset后重启。

## BD地址别名边界

实际BD `validate_bd_design` 返回PASS，但仍有4条 `[BD 41-1354]` 跨主地址映射重叠critical，未屏蔽或删除。build/主控核查实际生成层级：host_split两个2GiB分支、DDR1 S00/S02独立local0 MMU、Host S01 cascaded路径与唯一31位MIG地址边界，支持其刻意跨主别名解释。该证据由build报告负责；本RTL子任务保留原local地址合同，未添加board地址前缀。**本轮未运行真实生成SmartConnect/MIG互连事务仿真，不把BD返回PASS当无critical签核或完整DDR路由板级验证。**

## 未覆盖边界

本轮无正式综合、资源/性能测量、setup/hold/CDC静态签核、implementation、DRC、bitstream或板级闭环。无完整Llama32层/双cohort/ACC/PPL数值验收。未改变数值运算模块，但路由测试不能替代完整数值回归。硬复位测试覆盖空闲各域reset后重启；不声明孤立reset可恢复AXI对端仍在返回的活跃事务。BD连接由脚本/完整RTL入口审核，尚未生成或验证可上板实现。
