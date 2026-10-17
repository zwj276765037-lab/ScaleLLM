# E006/R002：两组 URAM 的真实用途

execution: completed（本条 CPU 源码追踪）；verdict: supported（如下具体用途与容量解释）；applicability: E005 冻结 RTL / 原 physopt 层次利用率；review: 已提交主控，非用户验收。E006 原生模块×SLR、热点及连接审核仍在进行。

`C/u_meta_bank` 的 672 个 URAM 是 **MLP 专用的 Gate/Up 与 Down 权重缩放元数据 A/B 双图**；Attention 的 `u_meta` 另用 80 个 URAM 保存 **Q/K/V/Wo 权重缩放元数据单图**。这些存储不是完整 W4/W8 权重缓存，也不是 Attention 与 MLP 共用一份大权重缓存。这里的用途来自装载位切片与实际消费路径，不仅来自实例名称。

| 原生层次 | 保存内容与逻辑形状 | 逻辑存储量 | 原生 URAM 数 |
| --- | --- | ---: | ---: |
| `C/u_meta_bank/u_gate_bank0`、`u_gate_bank1` | 每图 229376 条 × 224 bit；16 个 code8 与 16 个 shift6，Gate/Up | 每图 6.125 MiB | 各 224 |
| `C/u_meta_bank/u_down_bank0`、`u_down_bank1` | 每图 114688 条 × 224 bit；相同字段，Down | 每图 3.0625 MiB | 各 112 |
| `C/u_compute/u_attention/u_meta` | 81920 条 × 256 bit；每列 code8 + shift6 + 2 个保留位，共 16 列 | 2.5 MiB | 80 |

其中 `C = scalellm_vcu118_f05_bd_i/core/inst/u_core`。MLP 两份完整图共 **18.375 MiB**。以上 MiB 是源码数组承载的位数，不是 DDR 容量或当前有效数据量；复位后有效标志可为零，物理存储仍已配置。

按 URAM 的 4096×72 bit 容量计算，MLP 显式宽度域为 72/72/72/8，每条 224 bit 使用四个宽度域：Gate 每图 `(229376/4096)×4 = 224`，Down 每图 `(114688/4096)×4 = 112`，A/B 合计 `2×(224+112)=672`。其物理容量 23.625 MiB，逻辑载荷占 224/288；这里的宽度余量不能称作另一份权重副本。Attention 的 81920×256 对应 `(81920/4096)×ceil(256/72)=80`，物理容量 2.8125 MiB。**752 = 672+80** 与原生全局计数一致。块数以原生报告为实测，公式只是解释现有形状如何产生该数值，不是本轮重新综合结果。

## 源码证据链

所有下列相对路径在 `project/hardware/rtl/` 下；精确文件 SHA、大小、与 E005 冻结清单的逐项匹配在伴随 `metadata_uram_source_facts.json`。

- MLP 存储形状：`mlp/hap_mlp_weight_meta_resident_ab.sv:23` 声明 ultra 数组；106–119 行生成 72/72/72/8 四域；191–196 行给出生产深度且实际顶层实例无参数覆盖。288–308 行只允许 inactive bank 顺序写入，并要求两类精确写入计数、消费者静止、读写在途清空才 commit；327–378 行是四个物理 bank 实例。A/B 用于保留当前图，同时装载另一图；不是两个 engine 各占一个 bank。现有接口支持该装载/消费安排，不代表本轮测得装载与计算实际重叠性能。
- MLP 装载：`integration/hap_mlp_meta_dma_loader.sv:3` 定义 DDR padded-256 格式，7–8 行固定两类条数，49–51 行仅将 DDR 返回的 `[223:0]` 写入片上，55 行按完整图顺序读。`[255:224]` 的零 padding 是格式约定；本条不声称 loader 逐条检查了这些位（代码没有这种检查）。
- MLP engine 独占链：`integration/hap_attention_mlp_production_core.sv:185` 的 `u_meta_sched` 消费本地 bank 返回；196–212 行 `u_meta_bank` 无参数覆盖；345–348 行输出 `mlp_gate/down_meta`，`integration/hap_attention_mlp_resource_top.sv:153` 的 `u_mlp` 在168–171行接收这两路。`mlp/hap_mlp_serial_ddr_command16_v5_s54.sv:212` 按 Gate/Down 阶段选一路进入 W4 frontend。
- MLP 字段确为计算缩放信息：`mlp/hap_mlp_gate_up_gather_pingpong12.sv:286`、293 行拆出 `[128+column*6 +: 6]` shift 和 `[column*8 +: 8]` code；`mlp/hap_mlp_w4_repack48_to12.sv:212` 的 W4 权重来自独立输入，215–219 行拆元数据同样的 code/shift。`mlp/hap_mlp_gate_up_v5_scheduler16_q4.sv:251` 与 `mlp/hap_mlp_down_v5_scheduler16_s54.sv:188` 分别输出独立 W4、code8、shift6 信号给计算。MLP 的 224-bit 格式为 128-bit code 平面和 96-bit shift 平面，不是 Attention 的逐列 16-bit 交错格式。
- Attention 存储：`attention/hap_weight_meta_resident.sv:7` 默认81920深度，29行256-bit ultra数组；64–67行检查每列 code8/shift6/保留2位；75–78行写入/读出的是这同一256-bit元数据。该文件头部仍写“两外部DDR通道”，这是旧逻辑端口描述，不能覆盖本轮 Attention→DDR0 的合同与当前集成。
- Attention 装载与复用：`attention/hap_attention_board_cohort16_core.sv:277` 实例没有参数覆盖，280行写 DMA 元数据；272–275行仅在 ST_RUN 顺序读本地数组。540–546行依控制位选择是否重载，548–570行完成81920条装载后设置 loaded，随后执行输入和计算；这是显式驻留图，不是按 cache miss 从 DDR 补行的缓存。
- Attention 独立消费：该 board core 的355–358行将 `meta_rsp_data` 与独立 `weight_s8` 合并，416行将元数据送本 engine compute；`attention/hap_attention_compute_cohort16_top.sv:206` 实例化实际 projection，229行传元数据；`attention/hap_projection_core16x16_w8_reuse.sv:323`–326行拆 code/shift，353–354行连到阵列权重缩放口。

## 与专用 DDR、拥塞问题的关系

Attention→DDR0、MLP→DDR1 解决的是两 engine 的外部访问归属。现有 RTL 仍显式保留用于顺序消费、缩放字段对齐和重复使用的片上元数据，以及各自的权重暂存、输入/输出缓冲和计算阵列；DDR 通道独立不会让这些结构自动消失。`u_meta_bank` 放在 `u_core` 层下只是集成层次，不能据此归为两 engine 共享数据。

本条可以解释 **为什么已有大量 URAM**，不能单独解释 **为什么 SLR1 布线失败**。原生报告的672/80是全器件计数；哪个 bank 落在哪个 SLR、热点内比例、端点距离和连接方向仍由 E006/R001 实际原生查询回答。即使热点含 URAM，也须与 LUT/FF、BRAM、控制负载和路由失败样本结合；不可将“元数据很多”直接升级为失败因果。

原生数值来源：`project/hardware/vivado/reports/m002_E005_R006_AT002_closed_place_physopt_readonly/physopt/utilization_hierarchy_depth7.rpt` 第89行 Attention u_meta=80，第99行 u_meta_bank=672，第101/106行 Down 各112，第111/117行 Gate 各224。原报告父子 LUT 数可能因跨层次 LUT 合并不满足直接相加；此处 URAM 数各叶与总计一致。
