# M002 修复与快速功能验证合同

日期：2026-10-15（Asia/Shanghai）。用户最新指令：“开始修复与快速功能验证”。本合同限定本轮执行范围；旧合同/报告中的性能预测与验收勾选不构成已验证事实。

## 目标和边界

修复 [主控审核](../../results/reviews/M002_readiness_2026-10-15.md) 的 B1–B4，完成当前源的 Host 回归、完整 RTL elaboration 和关键 DDR 事务功能仿真，判断后续综合是否具备条件。实现入口仍为 project/hardware 与 project/software，旧 ScaleLLM 目录只读。

允许：RTL/Host/构建修复、CPU 单测与整数数值回归、xvlog/xelab/xsim、必要的 Vivado synth_design -rtl elaboration。正式 synthesis、implementation、route、bitstream、GPU、PPL/ACC、板卡均不在本轮范围。不得修改 Hadamard、ScaleCode、format05 权重字节含义、数值位宽、舍入和审计要求。

## 确定的接口方案

- Attention 的两个逻辑权重流都必须完整读取，其物理目标统一 DDR0；MLP 两逻辑流目标统一 DDR1。c0/c1 表示逻辑半组，不再表示两个物理 DDR。保留六个 CSR 权重基址，值为各引擎专属 DDR 的通道本地偏移。
- 新 dedicated read 模块保留成对描述符校验，将两逻辑流依次发往该引擎的物理 DDR，并正确分流返回；两引擎独立运行。须保留背压、错误响应、排空、复位与维护语义。
- production 新增 mlp_data_axi_*，256-bit AXI4 R/W；board 新增 m_mlp_axi_*，接口名 M_AXI_MLP_DATA。该口 core100，经 DDR1 SmartConnect 转宽与跨域后到 DDR1；现有 M_AXI_DATA 仅 Attention→DDR0。WEIGHT_C0/C1 仍分别连 DDR0/DDR1。
- Attention 两逻辑 reader 使用 DDR0 时钟/复位，MLP 两 reader 使用 DDR1 时钟/复位；核查所有关联控制 CDC。core100、DDR UI200/200 不变。
- Host：Attention 32层完整矩阵（40MiB/层）常驻 DDR0 [0,0x50000000)，KV保留 [0x50000000,0x56000000)；activation 从0x56000000起6个1MiB槽、输入输出不重叠；Attention metadata双4MiB从0x56800000起，RoPE从0x57000000起。
- DDR1：MLP四权重artifact为28+28+14+14MiB，单层slot [0,0x05400000)；activation从0x06000000起，metadata双12MiB从0x06800000起。具体有效大小按原artifact合同核实；全部物理区域必须不相交、不跨2GiB。
- MLP加载、命令与完成受同一生命周期保护；双cohort不可覆盖在飞权重。错误/超时不能在硬件未静止时释放可重用slot。Host地址与CSR本地偏移分开，数值输出保持S32/F16。
- 在任何MLP权重staging之前先核验硬件idle、completion/ack、DMA及abort状态，避免先覆盖在飞数据再拒绝命令。新增只读布局寄存器0x2B8 MEMORY_LAYOUT_ID=0x4D303032（M002），Host在任何DDR写入前校验；数值format05和ABI不变，旧权重artifact字节可复用，旧布局bitstream必须拒绝。
- 新XDC去除无依据的时序例外、derate及猜测位置；只保留可证明的当前约束。根vivado/scripts/m002*仅作兼容入口，权威实现位于project/hardware。
- 旧mission0004/0005物理XDC与native025相关固定分区检查不代表新专属DDR布局有效；原文件保留，撤下M002默认构建输入。place/route前需要当前设计相容的物理检查，不能复用过期partition/terminal计数宣称通过。本轮不执行这些阶段。

## 分工与额度

| 任务 | 负责人/实际子任务 | 唯一写入范围 | 证据批次 |
| --- | --- | --- | --- |
| SM002 | A004 / /root/m002_rtl_repair | 必要RTL与对应TB、R002 worker_report | E001/R002 |
| SM003 | A005 / /root/m002_host_repair | Host、Hostops及相关CPU测试、R001 | E001/R001 |
| SM004 | A006 / /root/m002_build_verify | 构建脚本、清单、约束、构建测试、R003和R002原始EDA尝试 | E001/R003 |
| 主控 | 当前 /root | goal/mission/results、共享索引与E001三摘要、最终整合审核 | 汇总各批次 |

总agent并发4（含主控），子agent不得再分叉。工程启动期望gpt-6.1-sol/xhigh，实际运行模型未另核实。只有A006可运行EDA，同一时刻1个工具流程、最多8线程；CPU轻量测试可并行。快速工具单次超时先报告并定位，不自动升级正式综合或长跑。

BD快速校验限定补充：首次300秒内已观察到真实DDR构造和时钟检查进展；若该次超时，保留失败回执，先完成权重/frontend复测，再允许一次新的600秒validate-only尝试（与完整RTL展开同级上限）。仍在generate_target之前退出；若再超时则如实报告未完成，不继续扩时。该调整由主控依据实际构造进展作出，不扩大到正式综合或implementation。最终AT007在原300秒内完成，600秒重试预案未启用。

## 验证与报告

1. Host import/API、artifact身份/大小、区域交集与边界、物理通道/CSR本地偏移、activation slot生命周期、MLP在飞保护及错误状态。
2. 完整RTL层级elaboration（标明production/board/BD实际覆盖范围），新适配器与集成路径的权重完整性、返回归属、独立/并行引擎、背压、reset/maintenance和协议错误。
3. 与改动相关的整数数值回归保持独立期望；不能修改golden来消除失败。快速验证不冒充32层真实完整模型或板级验证。
4. 每个具体尝试使用新AT目录，保存真实命令、源/输入hash、工具版本、起止时间、退出码和日志，不覆盖失败证据。范围变化新开R。
5. 关键里程碑或全局问题即时消息主控；独立工作继续。最后提交总报告，明确已修复、已验证、尚未覆盖与综合启动判断。
