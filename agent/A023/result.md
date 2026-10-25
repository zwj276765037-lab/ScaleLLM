# A023 结果交付

M006 / SM026 / E013 Host支撑完成，研究判断：supported（仅CPU合成输入整数边界和ABI布局）。

- 实现：[scalellm_mlp_linear.py](../../project/hardware/host/scalellm_mlp_linear.py)。S24/S32双H32、MinMax A8/ScaleCode、冻结SiLU与乘Up、GU/Down输出解包、严格REC576 pack/unpack，以及两个生产prepare入口。FP32适配显式接收现有RMSNorm结果，不重复归一化。
- 测试：[test_scalellm_mlp_linear.py](../../project/hardware/tests/test_scalellm_mlp_linear.py)。32 tests PASS，5.832s，退出0；独立原数学参考及标量字节索引，全16行生产形状、极值/ties/尾列/跨beat/错误拒绝。
- 证据：[README与API说明](../../project/E013_mlp_linear_only_hardware/experiment_results/host_reference/README.md)、[manifest](../../project/E013_mlp_linear_only_hardware/experiment_results/host_reference/AT_20261024T030431628513Z/manifest.json)、[原始日志](../../project/E013_mlp_linear_only_hardware/experiment_results/host_reference/AT_20261024T030431628513Z/unittest.log)。源码/ROM/input SHA、工具版本、命令与资源已记录；Python3.12.3/NumPy1.26.4，maxrss约76.6MiB。
- A022已确认API，并收到独立16行REC576 .bin/.hex与预期q/meta。公共hostops/runtime/schema/三摘要/索引未修改。

限制：未加载真实32层模型工件；未执行全层权重矩阵、RTL/EDA/GPU/板卡，不声明整模型或硬件验收。无本子任务剩余阻塞。

## 续接交付：CSR自检TB（2026-10-24）

已新增 [hap_mlp_linear_axil_control_tb.sv](../../project/hardware/tb/hap_mlp_linear_axil_control_tb.sv) 与 [csr.list](../../project/hardware/vivado/manifests/mlp_linear/csr.list)。执行状态：源码交付completed；CSR仿真：**NOT_RUN（由A022唯一owner执行）**。

静态核对通过：DUT全部139端口精确连接；schema全部64个RO/LEGACY_RO/COMPAT_RO/RESERVED地址及17个descriptor字段地址顺序精确一致；唯一 `HARDWARE_AGENT_SIM_PASS`。这些静态核对不代替编译或真实仿真。

自检范围：AW先/W先与同时送入；W/B/R背压及稳定性；17个descriptor RW的full/partial/zero WSTRB；64个只读地址三种strobe拒绝、49个legacy telemetry读零/zero-strobe写拒绝；unknown/unaligned访问；0x110旧START与maintenance组合原子拒绝、0x174全部strobe拒绝；START在submit握手及外部mock结果期间延迟B，544-bit快照稳定及随后配置独立；admission首错/clear；epoch/ACK/abort外部结果映射和无重复脉冲；DONE新旧别名、计数与legacy错误类别。mock job显式提供错误码/延迟，不复制DUT准入算法，也不声称验证真实job/DMA排空或DONE冻结。断言保持合同语义，失败用fatal，唯一PASS仅在全部完成后输出。

生产问题回传：0x298 legacy类别统一映射1的问题已通知A022，A022回复已修映射与ACK后error gating；A023未修改生产RTL。

真实运行入口（A022）：

`python3 project/hardware/vivado/scripts/run_mlp_linear_sim.py hap_mlp_linear_axil_control_tb tb/hap_mlp_linear_axil_control_tb.sv vivado/manifests/mlp_linear/csr.list <新的attempt标识>`

SHA256：TB `11930d3d60c82aa009cb6f4559f32b1d3a69477c0389066708384be8ae6a4056`；manifest `a8a6593c90db504ac30c12f2d9d3b339af35f8f720a2252427d76eb8b524f9fb`。已向Root/A022交付并退出释放槽；此前Host实现和32项CPU证据未改动、未重跑。

## 续接交付：revision3 §9真实生产整合TB

新增 [hap_attention_mlp_linear_integration_tb.sv](../../project/hardware/tb/hap_attention_mlp_linear_integration_tb.sv) 与 [integration.list](../../project/hardware/vivado/manifests/mlp_linear/integration.list)。A023执行状态：源码交付completed；真实编译/仿真 **NOT_RUN（A022唯一owner）**。不将以下静态/参考值自检写成RTL PASS。

TB实例真实 `hap_attention_mlp_production_core`，N_GU128/N_DOWN64/enforce0仅在TB实例选择，K128/448、16行、真实Attention/CSR/router/job/metadata DMA/resident/scheduler/cache/sharedkernel/weight CDC/tensor DMA/paired DDR全部在生产源图。BFM仅替代外部AXI-Lite主机、AXI256 MLP数据DDR、AXI512物理DDR1和时钟/复位。Attention是真实实例但闲置，不能据此宣称并发SHARED验证。无stub、force、DUT层次写或伪造quiescent。

数据源按原exporter的W4半流（每source记录每half128B）、GU tile/matrix/group顺序、Down group/tile顺序、metadata低128位code与高96位shift/32B padding布局。q/W4随group/lane变化；row/col/group尺度变化，覆盖F24算术右移和左移。纯automatic标量oracle逐全K/32lane计算，再有符号64位guard/accumulate/half-away/saturation；每个输出byte按独立gold比较，包括16行、GU G/U交错、GU尾32和Down尾16。

实际运行了小型Python任意精度独立复算：当前公式六坐标 `(op,cohort,matrix,row,col): acc -> output` 为 `(1,0,0,0,0):44916→175`、`(1,1,1,15,127):-576→-2`、`(1,0,1,10,125):-58→0`、`(2,0,0,0,0):-26638336→-104056`、`(2,1,0,15,63):1247232→4872`、`(2,1,0,10,62):-161→-1`。这六个常量已写入SV time0参考函数自检；**SV自检尚未执行**。另独立复算旧compute公式g0 dot307、128组dot_sum−1994、guard_sum−31904→−125，未改旧gold。

执行顺序：

1. epoch9：job10 GU/cohort0→ACK、11 Down/cohort0→ACK、12 GU/cohort1→ACK、13 Down/cohort1→ACK，正常job_clear保持epoch/meta且不触发维护、Attention launch permission保持。每正常job末B主动延迟64core周期，禁止提前DONE/job_clear。
2. job20 GU中段record7坏padding，全部73,728B排空、仅前7条提交，禁止seal/compute/AW；错误DONE→身份ACK→同epoch job21 GU成功重试。
3. job22 Down在真实compute接受后ABORT，已接受任务持续推进，全部输出/B排空后保留ABORTED DONE、真实自动维护使epoch/meta失效；ACK后重载metadata/epoch10。
4. job30 GU首个tensor BRESP=SLVERR且framing完整，ACK须拒绝；真实0x110维护等待compute/cache/meta/transport安全，hard_clear保留DONE/首admission诊断并撤销epoch/meta，匹配ACK后重载epoch11，job31 Down/cohort1重试。
5. job40 GU物理DDR1早RLAST，真实paired global_freeze保留reset_required/非quiescent；core_clear请求不得伪恢复；真实core/DDR reset开启新session，重载epoch12并job41 GU重试。

所有故障预期断言保持合同；生产安全屏障由A022实现。TB统计外部AR/W/OKAY-B字节、metadata issue/delivery、cache全K请求、writer接收records和权重物理beat数。GU每job期望2816cache请求/2048meta/8192weight beats/16records，Down448cache请求/1792meta/7168weight beats/4records。

静态检查已实际执行并通过：99个真实外部端口声明覆盖、function/task结束配对、嵌套manifest文件存在、无force/DUT写、唯一PASS marker。这不是SV语法联编或功能仿真。最终SHA256：TB `57736114ec599c34af99ddbfe04042c0d17759ce8ba1dbbe2cc5abc4b5f04bb9`；manifest `141f502c9282ee27d8a1b1dac014b3ea47425972b1c4d6246c03fff1a702fd53`。

入口（已直接交A022）：`python3 project/hardware/vivado/scripts/run_mlp_linear_sim.py hap_attention_mlp_linear_integration_tb tb/hap_attention_mlp_linear_integration_tb.sv vivado/manifests/mlp_linear/integration.list <新attempt>`。结构成本：9个完整compute共24,832内部group事务，另framing部分；4次metadata load共491,520B；time0预计算gold包含1,966,080group/62,914,560lane乘法。JOB_BOUND=2M、global18M core周期是失效保护，不是吞吐或实测墙钟估算。A023没有运行EDA/修改生产RTL/重复Host或CSR测试。

未覆盖：默认14336/4096输出完整整板、真实模型/Host SwiGLU整层链、Attention并发、吞吐/时序/CDC/板级。真实编译及所有动态覆盖待A022新attempt；如失败按原gold/断言修复，不改期待值迎合DUT。

## AT024参考自检失败后的修复

AT024真实层次xelab完成，但原SV数学oracle在time0独立GU175 literal检查失败，未向DUT发命令；保留该失败证据。采用Python任意精度完整数学gold，直接物化在同一TB的96条packed-row常量中（8192 GU S24与2048 Down S32值，共32768B，列0在LSB），SV只切片及显式符号扩展，弃用该失败SV算术函数；原数据公式、六literal和所有DUT断言不变。完整gold原始word bytes SHA256 `9f53ded7be5164d82f3957b5429cf6d527173c398fb7f33fdefcc9c05dd9c39e`；新TB SHA `1330a6e7da2a67b794f563d9a5f64afc1702fd65146775e9c9b442a108cb0772`。实际CPU生成1,966,080group/62,914,560lane乘法，单进程且affinity最多8核，Python 3.12.3，耗时23.066s。真实复跑仍由A022执行，修复交付不代表RTL PASS。

## 新板级Tcl入口加固交付

[create_mlp_linear_board.tcl](../../project/hardware/vivado/scripts/create_mlp_linear_board.tcl)更新：模块引用改显式production `board_core_linear.sv`，正式constructor拒绝validate-only=1；调用A022的shape静态绑定检查输出 `production_shape.json`；记录实际fileset TOP/VERILOG_DEFINE/可读GENERIC与compile order；`elaboration_identity.txt`记录真实BD层次、公开可见pin/interface属性和宽度，并明确 `parameter_values_source=static_bound_source` / `actual_elaboration_parameters=unavailable`。不把BD构造身份误写成已运行elaboration或综合网表。

[build_mlp_linear_board.tcl](../../project/hardware/vivado/scripts/build_mlp_linear_board.tcl)更新：综合/实现过程即使失败也尽量收集各项native报告并写 `stage_quality.json`；process完成、netlist、clocks、route、setup/hold、unconstrained、DRC、CDC分别记录，整体不会因native0自动PASS。实际综合网表检查真实Attention/sharedkernel、禁止MLP非线性/旧full模块与blackbox；公开属性不可读则待审核/失败，不猜值。按实际board wrapper clock pins读取连接clock的名字/period，严格核core10ns及DDR各5ns。实现route用本地手册确认的PLACED_FULLY/ROUTED_FULLY/ERRORS_IN_ROUTES native查询；timing独立WNS/WHS路径与native summary的WNS/TNS/WHS/THS/endpoints；unconstrained四类native检查，格式不可解析保留待审核。DRC错误/critical判FAIL，warning待审核；CDC保留详细未忽略waiver的native report，明确PENDING_REVIEW，等待规则/豁免审核。Attention ROM逐run staging、固定SHA与Synth8-4445拒绝完整保留。

产物接口已直接交A022：constructor的 `production_shape.json`、`elaboration_identity.txt`、`compile_order_sources.rpt`、`compile_order_constraints.rpt`；build的 `stage_quality.json`、`netlist_identity.txt`、`clock_identity.txt`、`check_timing.rpt`、`drc_native_objects.txt`及原生route/timing/DRC/CDC报告。runner/receipt由A022绑定，A023没有修改其文件。

实际静态/系统检查：两个Tcl的`info complete`通过；系统Tcl8.6.14/Python JSON嵌套字段/数值往返通过；用固定文本和查询stub对setup负slack→FAIL、hold正slack→PASS、unconstrained count3→FAIL和native WNS/TNS/WHS/THS解析做纯parser检查通过；入口所需字段/保留ROM代码静态检查通过，git diff whitespace检查无问题。这些仅是小工具/解析器检查，**Vivado constructor/synth/impl均NOT_RUN（A023未执行）**，不能证明实际clock/property/质量动态成立。具体公开命令/flags按本地安装Vivado2025.2手册核查，无猜测elaboration参数property。

最终SHA256：create `30bfae14cf41ba3bcea0c61f5b7c95eb6d18d603e43c1a04e5fb0895c110e15a`；build `debaf4f8aedebf46dcf29d3088b7effba013e1fe77ebe0778257e7b13d124fae`。整合参考修复TB SHA `1330a6e7da2a67b794f563d9a5f64afc1702fd65146775e9c9b442a108cb0772`已单独交A022重跑。独立Python完整gold来源已在host_reference/integration_gold保存；原SV算术参考失败根因尚未解释，不声称已定位XSim问题。

## GU-only Host Down及真实CSR/XDMA适配交付

新增`scalellm_mlp_gu_only.py`、`_artifacts.py`、`_runtime.py`、`_backend.py`和五份对应test，生成`_abi.py`由A022维护只读。数值实现原W4F5/32Bmeta decode、独立bounded fullK scalar和blocked int64，16×4096/full448组全部65,536输出与独立einsum参考一致，224坐标纯Python fullK一致；实际原exporter producer→decode独立覆盖half/group/column顺序。旧v5权重manifest与v7 runtime身份分离且保留大小/hash/路径/布局验证，未改变原工件字节。runtime完成两cohort/32层任务、Host与FPGA独立租约，不提交硬件Down。

真实新backend直接绑定原XdmaSession四个CSR/DMA方法，实际身份/Attention ABI/SHARED→GU-only三工件stage/hash/padding→LOAD/COMMIT→epoch→17word/544bit descriptor→fullU32 START→ordered admission→DONE身份/计数→C2H owned copy→ID ACK→双cohort释放。保留DDR1 local和Host aperture区分；失败保留owner/pending/诊断，不自动维护或伪成功。Attention/残差/RMSNorm为明确应用回调，缺失拒绝；应用仍需真实Attention权重/KV/输入配置，本交付不声称完整应用已接通。

实际证据：[Host README](../../project/E013_mlp_linear_only_hardware/experiment_results/host_gu_only/README.md)。AT_20261024T153221518972Z 26 tests PASS/8.697s/native0，fullshape blocked1.735678s（不含decode0.303939s/其他I/O），峰值RSS964664KiB；AT_20261024T154353319434Z adapter新增16 tests PASS/7.390s/native0，峰值113248KiB，含原XdmaSession系统调用mock证明4B/U32写与aperture恰加一次，真实新adapter+pipeline组合和错误租约保留。合计42项，分两次运行，未伪称同次整跑。命令/工具/输入源SHA/日志/snapshots/fake trace均保存，全部inputs_unchanged、stop=null。完整输出SHA `eb985d6fa74a10fb7623034cbde4c1798bb80d26f048aff18e2b77b4dcfb4514`；最终源身份`host_gu_only/delivery_sources.json`。

限制：仅合成工件；bounded默认export路径/已知artifact目录未发现真实32层W4F5导出，`artifact_discovery.json`明确搜索范围。32层任务图测试是显式mock调度，不证明整模型数值/吞吐；fake transport不证明RTL/真实XDMA/AXI/板级。没有执行EDA/GPU/板卡，也未修改旧Host/runtime/artifacts或R005冻结输入。Host子阶段已向Root/A022交付，不阻塞G5；续接两份v7 CSR测试文件。

## GU-only v7 CSR测试台交付

新增[tb/hap_mlp_gu_axil_control_tb.sv](../../project/hardware/tb/hap_mlp_gu_axil_control_tb.sv)及[mlp_gu_only/csr.list](../../project/hardware/vivado/manifests/mlp_gu_only/csr.list)，原linear TB只读复用，新DUT为`hap_mlp_gu_axil_control`。静态核对实际PASS：全部139端口精确一一连接、17word顺序与冻结生成ABI一致、64个RO地址与完整schema分类一致、task/module配对、manifest源存在、无force/层次写、唯一HARDWARE_AGENT_SIM_PASS。**SV compile/XSim NOT_RUN，A023未运行任何EDA。**

新增v7覆盖：`0x134/0x138/0x170`每地址全部16种WSTRB×四个独立单byte非零向量，按enabled byte是否非零分别预期SLVERR/OKAY；另每strobe写全零和zero-strobe写全1，读取/输出/descriptor reserved始终零，拒绝不得改变其他word或凭空生成admission error。`0x164/168/254/2ac`对应外部旧Down输入故意非零但读恒零，并保留全部RO full/partial/zero-strobe拒绝。IDs固定numeric48384605/control00070000/linear4d4c0002/caps1d/buffer1/memory4d303032。15普通word full/partial/zero写、两个reservedword零，以及独立合法GU绑定73728→1376256B/1792records。

START覆盖full32bit opcode1与reserved0快照、AW先/W先、submit/B/R/W背压及后续写不改变已接受快照。额外opcode2/0x101外部job返回BAD_OPCODE0x1010；对0x101仅WSTRB1写1仍保留高byte、继续显式拒绝，最终fullU32写1恢复。CSR层只负责opaque descriptor传递，**这些mock结果不声称独立验证真实job准入**，真实job测试由A022另执行。复用旧test的admission首错/clear、旧START+maintenance原子拒绝、0x174拒绝、epoch/ACK/ABORT结果等待、DONE/legacy alias、legacy错误类别和无重复脉冲。最终预期5次submit/3epoch/2ACK/2ABORT。

运行入口交A022：`python3 project/hardware/vivado/scripts/run_mlp_linear_sim.py hap_mlp_gu_axil_control_tb tb/hap_mlp_gu_axil_control_tb.sv vivado/manifests/mlp_gu_only/csr.list <新attempt>`。TB watchdog50000core周期，约数百次单CSR读写，独立小型仿真，无完整矩阵或真实DMA。源码SHA256 TB `673e55c605daa61a45d6404934307024a1e169005d3e2c96bcd67cbb0d46364d`，manifest `1b1ce4e2c1b40fcbb547dcf6b8c75175fbef5b6e736458822e7aa769efbda725`。

Root指出backend地址文案后，已仅修docstring/README明确CSR是控制BAR寄存器偏移，DMA/descriptor数据地址为DDR1 local；代码功能未改、不重跑旧测试。新的delivery_sources身份附post_test_changes说明，原16项attempt快照保持。所有本轮授权实现/静态交付完成，无剩余A023进程或EDA；已通知Root/A022后退出释放槽。
