# M006 MLP linear：预算与验证结果

日期：2026-10-24；合同：[design.md](design.md) revision 4；生产[abi.json](abi.json) revision 2。
本文件由A021维护架构预算及集中审核；实际命令/日志/尝试由A022的E013三摘要引用。**已限定接受Host CPU、模块与SM026有界真实整合：AT028完整序列、AT030错误优先级、AT031当前全局故障恢复均PASS；数值/正常路径按明确差异复用。新板级constructor已限定验收；AT004已导出完整整板综合DCP，末尾身份probe失败使attempt终态FAIL；新原生DCP qualification及物理资格待闭合。**

## 平台与运行资格

| 项目 | 目标/已知事实 | 证据类型 |
| --- | --- | --- |
| 工程根 | /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM_MLP_fix | 当前M006合同 |
| FPGA | VCU118 xcvu9p-flga2104-2L-e | 设计目标及基线构建配置 |
| 时钟 | core100 MHz；DDR0/DDR1 UI各200 MHz | 设计目标；新时序尚未测 |
| 工具 | Vivado/XSim 2025.2已由工程定位，实际命令/版本日志由E013登记 | 工程回传；A021未启动EDA |
| 资源合同 | 小仿真维持已启动profile：8 CPU核/RSS96 GiB；后续整板profile：32可用CPU/RSS192 GiB，Vivado单进程maxThreads8、独立OOC/IP最多4jobs | Root最新转达；以[A022 E013协议](../../../E013_mlp_linear_only_hardware/experiment_source/protocol.md)及runner实际配置为准，不热改当前仿真 |
| 共享资源保护 | 单重EDA owner；available低于64 GiB持续30秒保护，磁盘余量30 GiB保护 | 非独占资源承诺，实际使用由工程证据记录 |
| 权重/模型 | 原format05 W4权重不重新量化；完整32层工件本地manifest待工程登记 | 目标/待取证 |
| 实际执行范围 | 模块实现、CPU参考、编译仿真及合格后的新工程/综合/物理；无bitstream下载/板卡/GPU授权 | M006合同 |

## 可复算容量与流量

| 项目 | 数值与公式 | 类型/限制 |
| --- | --- | --- |
| A8 cache逻辑payload | 16×448×280 bit = 2,007,040 bit = 245 KiB | 结构需求；实际BRAM碎片/输出FIFO额外 |
| 原两cache合计 | 140+245=385 KiB；逻辑减少140 KiB | 基线结构推导；不是综合资源节省 |
| cache row bank | 448×280 bit，每行独立读写，16行 | 推导；不承诺具体RAMB36数量 |
| parser记录 | 16×32 U8 + 16×3 metadata + 16 pad = 576 B | ABI；18 AXI256 beat |
| GU输入/输出 | 128×576=73,728 B；1792×768=1,376,256 B | 固定payload |
| Down输入/输出 | 448×576=258,048 B；256×1024=262,144 B | 固定payload |
| 每层/cohort MLP激活 | H2C331,776 B + C2H1,638,400 B = 1,970,176 B | payload；不含权重/metadata/协议 |
| 每pair 32层激活 | 1,970,176×32×2=126,091,264 B=120.25 MiB | 固定形状推导 |
| 每层权重/metadata staging | 84+10.5=94.5 MiB；同层pair复用一次 | Host epoch条件；硬件权重DDR读仍每cohort各84 MiB |
| 保留计算核 | 双8×12，结构估算3072 DSP48E2 | 仅核结构，不等于全部MLP DSP |
| 有用MAC | GU1,879,048,192；Down939,524,096；合计2,818,572,288 | 每层/cohort16；尾lane内部事务另算 |
| 理想AXI256带宽 | 32 B×100 MHz=3.2 GB/s | 单beat接口峰值；串行读写/16beat burst/DDR仲裁及Host影响实际利用率 |

cache与kernel请求/响应可局部流水，GU/Down同命令只激活一种读adapter。GU和Down不并行共享核；load先于compute，输出store可与compute重叠。额外DDR流量和Host计算不可从端到端指标中删去。

## 验证状态

| 阶段 | 当前状态 | 证据/下一步 |
| --- | --- | --- |
| 原设计/当前源静态阅读 | 已完成 | 前轮实现计划与本轮contract引用 |
| schema结构检查 | Root独立检查通过 | 94 CSR唯一/对齐/位于MLP窗口；39 error唯一；544-bit descriptor完整映射。仅静态结构通过 |
| cache/parser RTL | AT011/AT012新回归PASS，当前输入SHA一致 | 已补中段错误/最终commit背压；见第二次有界任务快照 |
| Host数值/codec | 32项CPU测试证据限定接受 | 当前源与AT_20261024T030431628513Z一致；仅合成输入，不含应用集成 |
| GU/Down计算及生产集成 | 有限PASS：AT028真实N128/64、K128/448；AT030/031覆盖当前控制修订 | 见第五次阶段审核；不扩展到生产全N或Attention并发，AT016/024/026历史FAIL保留 |
| 新板级constructor | R003/AT003原生完成，限定PASS | 第六次审核：1323生成文件+规范化XPR/10native工件与AT004启动链一致；非综合/物理结论 |
| 新综合资源 | AT004完整整板DCP及资源已取得；attempt因末尾身份probe失败为FAIL | 22 OOC+top完成；LUT766078/FF954137/BRAM835 tile/URAM752/DSP5375；新qualification待执行，不等同时序或可布线 |
| place/physopt/route/时序/DRC/CDC | NOT_RUN | 目标100/200 MHz不代表实现达成 |
| bitstream/上板/性能 | NOT_RUN，当前合同未授权下载/运行 | 后续单独按真实授权与硬件资格处理 |

## 阶段审核规则

每条结果同时标注execution、verdict和applicability。E013三摘要提供当前源、输入、工具、命令与日志；A021仅在里程碑集中核验受影响合同，不逐次批准普通修复。首次模块阶段重点为cache/parser封装与错误排空，后续独立审核计算、控制、SHARED与新构建。

历史route失败和原全板资源只作同配置可比较基线，不为新候选填写实测值。完整模型工件缺失不阻塞独立模块工程，但相应端到端数值与板级项保持未验证。

## 首次有界阶段审核：2026-10-24 03:12 UTC

审查者A021；execution=completed，verdict=limited_acceptance，applicability如下表。源码只读、读取原始证据并复算SHA256；没有重跑CPU测试、仿真或EDA。范围止于A023 Host交付和A022 AT001–004，不审查新生产替代图；AT005仅核输入身份，不等待或预判结果。

| 对象 | 原始执行/裁决 | 本轮适用范围 |
| --- | --- | --- |
| [Host AT](../../../E013_mlp_linear_only_hardware/experiment_results/host_reference/AT_20261024T030431628513Z/manifest.json) | 原始unittest日志32项/5.832 s/OK，进程exit0、stop=null | 当前Host模块和测试与冻结输入一致；允许作为数值oracle/codec支撑 |
| [AT001 cache](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R001/attempts/AT001_cache/result.json) | xvlog/xelab/xsim均原生0；576次全行全lane地址重放，SIM_PASS | 仅其inputs.json所列历史cache/TB；当前两文件已变化 |
| [AT002 parser](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R001/attempts/AT002_parser/result.json) | xsim原生0且SIM_PASS，但runner verdict=FAIL | 保持原FAIL；日志正常统计字符串含error造成误判，不冒称该AT已通过 |
| [AT003 parser](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R001/attempts/AT003_parser/result.json) | 原生0且PASS；576合法组、512错误后排空组 | 仅其历史parser；当前已改提交计数时点，尚需复验 |
| [AT004 GU pilot](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R001/attempts/AT004_gu_pilot/result.json) | 原生0且PASS；128列、2048 source、2816 compute、16 output、6412 cycles | 9个输入SHA均与当前文件匹配；仅scheduler/gather/repack与cache/projection BFM，非共享kernel数值 |
| AT005生产形状GU | 审核时尚无result.json | 不授予PASS；完成后由后续里程碑审查 |

### Host数值、ABI与参考独立性

已阅读[实现](../../host/scalellm_mlp_linear.py)、[测试](../../tests/test_scalellm_mlp_linear.py)、原fixbit_v2/mlp_fixed整数参考及[运行说明](../../../E013_mlp_linear_only_hardware/experiment_results/host_reference/README.md)。独立复算11个当前来源、5个NPZ/HEX/BIN工件、4份冻结源码、runner和原始日志SHA全部匹配manifest；无需因本次审查重跑相同测试。

- H32的5级蝶形、11585归一化、负数/半值舍入及S27/S35边界以旧标量整数函数逐组对照；新实现为独立NumPy数组运算。16×4096及16×14336全形状包括后8行，不受旧参考ROWS=8常量限制。
- MinMax采用含0区间、RNE零点/编码、affine端点钳位；S35 D超过4,269,834,239必须拒绝。测试明确区分旧helper可能clip与新合同reject，且验证失败前未调用pack，不用更改参考掩盖差异。
- GU接口直接接收已RMSNorm的S24；独立FP32 adapter保持float32操作、半值远离0、S24饱和。极端有限FP32先clip再转整数，避免旧路径int64溢出；该定义及覆盖明确，不重复RMSNorm。
- REC576有独立标量字节地址reference，覆盖128/448组、row10跨beat、reserved/padding/canonical-zero、code=1合法；GU覆盖全部896×2记录及尾tile，Down覆盖256记录、小端与符号扩展。
- SiLU读实际8192词ROM并补隐含顶端词，完整表与旧独立构表函数一致；覆盖所有LUT地址中点±1、±16端点、乘积半值及S32极值。ROM SHA为`8263e8981b637b00143c6dfd6674f2397a73c85c6ed8934f0ee839f76db6ea67`。
- Host源SHA为`227e457e4d0464115241d2de6a8521496413b0a071344d776ab9c3a861a3c716`；测试源SHA为`cd0b6e269214d736f8fcfb0ecc481f91dc4f4e3babcc768f2e324a8a796c2bb1`。这是合成输入数值/codec验收，不覆盖真实权重、32层模型、runtime迁移、CSR操作、板级或性能。

### 硬件协议结论与剩余覆盖

源码阅读确认当前cache以owned/sealed/pending/rsp_valid约束访问，begin在error后关闭；读响应保持至握手，payload RAM不复位。parser完整18beat后校验再提交，首次格式错误后禁止后续写并继续固定输入排空；当前accepted_input_bytes已移至cache写握手。GU请求FIFO将权重与cache响应配对，投影tag只在最后K组接受时进入，输出保持G/U交错；done条件含准确事务数及request/tag/output排空。未发现本轮范围内阻断性实现错误。

当前cache SHA为`be9a02392173d66ae6bdb1796ca5209a301cf21f2f5719f163da76e130dff6c5`；parser SHA为`f5895b7f141c4f327a9dcc61f723bc2b1b569710e19dfcac7c1dfa321a6eaec2`。它们与历史PASS不同：cache错误码/错误后begin锁与TB有修订，parser计数从组装时移至wr握手。A022已说明计划AT006+复验；本次静态核查不替代该运行。

| 尚待验证项 | 发现性质与责任 |
| --- | --- |
| 在中段REC注入格式错，最终INPUT_BYTES只计此前合法cache提交；剩余流持续排空且不再写 | 当前parser TB四类错都在第0组；属覆盖缺口，已实际消息交A022补入既定回归 |
| 最后一条合法REC已组装但wr_ready长阻塞时，INPUT_BYTES不提前增长，done不提前 | 当前TB仅末态检查计数；针对新修订的必要回归，已交A022 |
| 当前cache/parser新哈希重新编译/仿真，错误码及owner锁对应schema | 工程普通修复/回归连续执行，不增加逐次架构批准 |
| 真实共享kernel数值、Down、DMA跨4KiB/最终B、错误恢复、ACK/epoch、SHARED及生产图 | 不在本轮覆盖；后续集中里程碑按真实证据验收 |

W0 revision2合同无需因本次审核修改。未运行综合/物理/bitstream/板级；未将CPU合成输入或BFM调度结果当作完整硬件工程完成证据。

## 第二次有界任务：仅输出N缩小的整合合同

2026-10-24，execution=completed；verdict=contract_ready_for_implementation；本轮只读RTL、原始终态及哈希，未启动EDA或等待后续运行。Root/A022实际消息协商定主整合GU N128、Down N64，K组固定128/448；[design.md §9](design.md#9-真实生产层次的有界整合测试合同)已落盘。生产ABI/schema未改，文档revision3不扩展Host合法payload。

已核实际传播点：production_core/resource_top、compute/GU/Down scheduler、job/tensor DMA、metadata loader/resident/scheduler。修正项是compute原`DOWN_GROUPS=INTERMEDIATE_COLUMNS/32`及同名非生产断言；它会把N_GU128错误传成Down K4。现在固定Down448，metadata1792和2688内部事务对应N_DOWN64，生产同余尾12/4覆盖。形状与计数统一传播、默认guard及生产manifest禁止误关要求见合同；A022独占实现。

| 本轮读取的后续证据快照 | 原始结果/身份 | 本轮结论 |
| --- | --- | --- |
| [AT005](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R001/attempts/AT005_gu_production/result.json) | 六步骤原生0、PASS；229376 source/305920 compute/1792 output/612620 cycles；输入SHA无变化 | 补全首次审核当时未终态的全形状GU scheduler/BFM证据；不含真实kernel数值 |
| [AT011](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R001/attempts/AT011_cache_current/result.json)、[AT012](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R001/attempts/AT012_parser_current/result.json) | 六步骤均原生0、PASS；输入SHA无变化 | A022报告并已落盘覆盖第17组padding错后17×576前缀、最终record阻塞23周期；旧两项覆盖要求已有新运行回应，不再以旧AT冒充当前源 |
| [AT010 job](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R001/attempts/AT010_job_control/result.json)、[AT015 tensor DMA](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R001/attempts/AT015_tensor_dma/result.json) | 原始PASS，读取时job/tensor源码已变化 | 仅接受历史attempt事实；参数化新源需新证据，job mock不证明真实维护排空 |
| [AT016 compute](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R001/attempts/AT016_compute/result.json) | runner FAIL，日志`Fatal: compute error numeric00000004`；工具原生0不改变断言失败；TB随后已变 | 尚无可用于成本估计的合格真实kernel测量；工程继续修复，不重标为新128/64合同通过 |

这些是已有证据的有限终态/哈希确认，不是本轮新执行，也不是对所有新增TB逐行重审。前轮Host源/测试/ROM保持验收范围；design文档本轮变化不能改写其历史manifest身份。

实际故障恢复仍OPEN：当前core的clear-safe依赖busy/active，job FAULT busy依赖paths_quiescent，tensor或compute又可能等待clear退出。尚无本轮动态结论；合同明确真实framing完整BRESP错误应验证可排空维护恢复，framing损坏/global_freeze则只允许core reset路径。不能用AT010 mock或强制quiescent关闭该项。已向Root/A022报告，交下一真实整合TB。

当前没有新综合、物理、板级或整板端到端通过。本回合交付后结束，后续阶段由Root按真实里程碑复用审核，不占槽轮询。

## 第三次有界任务：新板级入口与生产图预检

2026-10-24 03:43 UTC快照；execution=completed，verdict=entry_gaps_identified，applicability=当前可读WIP脚本/源码图。仅静态阅读、manifest闭合/模块声明扫描、Attention基线SHA核对及Python AST语法检查；未运行constructor、综合、实现或仿真。没有等待AT021/023等运行，也未把主整合静态24832 group事务预算当作实测性能。

已读[m006_entry.py](../../vivado/scripts/m006_entry.py)、[create](../../vivado/scripts/create_mlp_linear_board.tcl)、[build](../../vivado/scripts/build_mlp_linear_board.tcl)、[runner](../../vivado/scripts/run_mlp_linear_board.py)、board/production/compute与Attention lists、board wrapper及linear core/resource、实际ROM/相关Tcl/XDC和E013资源协议。

核验所得：读入生产closure为107文件、83 RTL、100个模块声明，未发现重复模块定义；production/resource/metadata resident各仅选择linear替代源。Attention baseline文件哈希全部匹配，constructor宏实际选择`hap_attention_board_cohort16_core`，真实Attention H32/量化/softmax叶子均保留。MLP H32/量化/SwiGLU/full/serial叶子不在该图；这只是源码选择证据，仍需综合后的实际层次确认。所选RTL无文本include，唯一`$readmemh`为Attention `data/softmax_exp_u17.mem`；ABI `.svh`虽纳入身份清单，当前所选RTL未实际include它。

新根路径由脚本自身定位，递归list拒绝外根/缺失输入，旧M003冻结manifest未被引用或改写。constructor记录三个工具安装内VCU118 board XML输入并在结束复核；build已有Attention ROM逐run复制、固定SHA及Synth8-4445拒绝检查。末次检查尚无新`input_manifest.json`，是未冻结/尚未执行状态；不能把入口存在当作已创建Vivado工程。

| 项目 | 本轮具体缺口与影响 | 已交工程的可执行处理 |
| --- | --- | --- |
| 入口-01：生产shape | m006_entry只核文件身份/Attention基线及禁止文件名；board wrapper虽当前无override，入口尚未实际核14336/4096/128/448/enforce1和派生counts。RTL initial不能独立提供构建保护 | 静态核默认/传参图及wrapper，加constructor实际elaborated参数/层次report对账；正式manifest保留结果，错误值失败。A022已确认修复 |
| 入口-02：构造回执资格 | runner终态已要求stop=None，但当时receipt写入条件仍仅rc==0；资源停止或输入变更的attempt可能留下可被synth信任的回执 | receipt仅在原生成功、无stop、无输入漂移、无存活归属进程且必要产物完整时生成，并绑定终态证据。A022已确认修复 |
| 入口-03：DCP来源 | `--synth-dcp`当时只核新根reports内文件与本次SHA；旧DCP复制进新根也可满足，未证实来自成功M006 synth | synth输出专用receipt绑定项目/constructor/输入manifest/有效stage结果/DCP SHA；impl逐项验证。A022已确认修复 |
| 入口-04：生成输入身份 | inventory仅xpr/bd/xci/xdc/wrapper，漏普通生成HDL/ROM/Tcl/IP DCP；xpr复核显式跳过，可丢失实际source/define/top设置身份 | 记录实际生成及消费输入全图；XPR易变字段采用规范化配置身份，不能跳过top/源/defines/约束/IP运行配置。A022已确认修复 |
| 入口-05：validate-only混用 | create继承`HAP_BD_VALIDATE_ONLY=1`可原生0结束于BD验证、未生成wrapper/IP；runner当时未区别此scope | board正式constructor强制0，或独立scope回执禁止被synth使用；记录实际环境/模式。已消息通知A022 |
| 入口-06：阶段质量 | build会生成route/timing/DRC/CDC报告，但没有各自验收字段；当前`NATIVE_STAGE_COMPLETED`名称诚实，不能再据此推断全通过。旧clock XDC注释依赖旧build审查，新build尚缺实际clock身份/period核验 | 分开记录综合/route合法性、100/200MHz实际clock及未约束路径、WNS/WHS/TNS/THS、DRC/CDC逐项结论；未读/未闭合保持待审核。新网表核真实Attention/共享核、MLP非线性消失和无未解析black box。已通知A022 |
| 入口-07：进程归属完整性 | owned起始为空，仅按轮询时PPid tree追踪；launcher快速退出前产生的子进程可能被重挂后漏记；TERM宽限期不持续发现新子进程。出生时间核对保护已跟踪PID，但不能证明未跟踪者不存在 | 按新会话SID/PGID结合出生身份或subreaper补全归属；只有原root出生身份仍匹配才遍历该root；停止期间继续发现/收尾，survivors清单覆盖全部owned。已通知A022 |

当时compute.list末尾混入两个TB gold ROM、oracle JSON和生成Python，constructor会把它们加入sources_1；A022已明确正在拆到compute_test.list。该项按已声明WIP处理，不误称为已执行板级错误。以上均为普通工程修复，不新设逐项用户或架构审批；功能关键路径独立继续，修复后的真实入口/综合里程碑再集中取证。

资源配置静态符合32 CPU affinity上限、RSS192 GiB、MemAvailable64 GiB持续30秒、磁盘30 GiB、maxThreads8、单project IP/OOC最多4jobs；board与sim共用同一EDA锁，无固定墙钟/静默强停。其实际运行、峰值、全部子进程退出和物理结果本轮均未测。runner结果已排除stop!=None为成功，入口-02指出的是独立receipt条件仍不一致。

末次脚本身份：m006_entry `65f0ef5c6601b54ae267f7b512e190da1391863cdb04d026543939bb13ac8e53`；runner `1b61875b64153b21b81b6d01abd5b8a4ff290dc3238cc1602721eea520086d56`；create `71752b275b83be11cac913edb33f2350af31b3466171a9bd24e2b875b7cfa55c`；build `298dcd51d3e33e26b0edacbde666277d84fa8f8739e5ff2bfb53c2c823a80162`。工程继续修改后这些是历史快照；本轮不等待修复或声明复验通过。

工程追问的elaborated参数读取方案：本轮没有核实Vivado公开的参数property名，不提供猜测字段。可先将board wrapper的生产常量显式传参、严格静态关系与source SHA绑定，再由constructor核实际top/defines/generic/compile-order、真实层次/可见端口和数组维度。若工具未公开参数值，报告必须分别标`parameter_values_source=static_bound_source`与`actual_elaboration_parameters=unavailable`，不得把空property当实测。该组合是独立于initial error的入口保护；后续真实综合结构再补证，普通实施不等待本代理逐项放行。此建议已实际发Root/A022。

## 第四次有界任务：故障恢复与观测计数静态复核

2026-10-24；execution=completed，verdict=fixes_required，applicability=AT028冻结期间当前可读production/job/tensor/compute及其清理连线。无生产改动、EDA、新测试或等待AT028终态。A022确认本轮相关源冻结运行；普通修复在后继attempt，不热改已消费输入。Root提供AT021真实共享核完整5120值gold通过、AT025 transport回归及AT027计数回归信息；本轮不重复其运行或代替阶段终审。AT026仍为原FAIL，不因TB clear基线修复改写历史。

BRESP恢复主链静态读通：私有AXI256 DMA在失败B握手后进入ST_FAULT，不再发AW；framing完整时transport_quiescent为真。job_reset_required选择discard sink，让已启动compute继续消耗权重/metadata/cache并退役无效输出，tensor本地未提交buffer留待安全clear。新增mlp_fault_clear_safe等待真实compute/cache/metadata/resident/weight与tensor transport退役，不要求失败tensor恢复IDLE；最终仍通过原paired跨域维护屏障才engine_soft_clear。未发现此路径重新引入原job busy→tensor busy→hard_clear的直接闭环；动态恢复是否完成仍由真实整合证据回答。

framing错误的DMA ST_FAULT保留framing_error，transport_quiescent持续假；paired global_freeze也使共享leaf自身非quiet，禁止soft-clear恢复。正常job_clear只接MLP cache/compute/parser/tensor/metadata scheduler；Attention和resident只接engine_soft_clear，因此正常START/ACK本地clear不直接清Attention。CSR ADMISSION_ERROR只由core reset或明确0x374清除，安全hard_clear不清诊断；job hard_clear保持已有未ACK DONE并撤销epoch，resident只在全局clear撤销metadata。

| 待修项 | 具体静态触发与影响 | 最小修复/有界验证 |
| --- | --- | --- |
| 恢复-01：同拍ABORT与成功 | job DRAIN读取旧abort_pending/live_error；本拍合法ABORT或维护请求与成功终态同拍可snapshot(0)，随后却执行维护并保留成功DONE | 用本拍握手/请求参与统一terminal_error；ABORT/维护胜成功。单位用例同时触发DRAIN完成与ABORT |
| 恢复-02：首错被LOAD覆盖 | LOAD&&load_done&&paths_error无条件写live_error；较早拍ABORT/维护首错会被后来的输入格式错误替换 | 首错锁统一仲裁；已有码保留，无旧码时本拍输入错误高于新ABORT。分别验证先ABORT后LOAD错及二者同拍 |
| 恢复-03：全局故障未进入MLP诊断 | paired_error/data_conflict_error只进integration_error，未进job_paths_error/fatal/quiescent；MLP Idle/DONE时局部quiet可能为真并容许新准入 | 明确全局错误门阻准入/非quiet并设置严重性；健康SHARED不能无条件等待全A+M paired_core_quiescent。idle fault及其hard_clear不得用旧descriptor制造任务DONE |
| 恢复-04：Complete时late fatal/ACK | 当前fatal处理仅phase<=VALIDATE和LOAD..DRAIN；未ACK Complete时新fatal不升级reset_required，同拍ACK未检查新fatal | 跨phase严重性升级，fatal同拍ACK拒绝；已有DONE内容不重写。单位用例保持旧DONE，注入late fatal与ACK同时到达 |
| 恢复-05：recoverable后deadline失效 | watchdog条件含!paths_error；先padding错误后R流停止可永久LOAD且不升级fatal；先ABORT后超时直接snapshot2200又会丢首错 | 活动未终态一直计时；旧首错保留，超时只升级严重性。单元短timeout+已有padding且无load_done，另核已有ABORT超时 |

上述五项已即时消息通知Root/A022；Root确认同一次普通修复，A022接受统一优先级及global fault/健康SHARED区分，后继attempt追加边沿case。本轮将最小规则写入design §5 revision4，生产ABI/schema仍revision2；没有新逐项批准门。尤其hard_clear补MAINTENANCE_ABORTED必须依据真实accepted-job owner，不能单靠fault态busy推断有任务。

观测计数静态核验：compute/store cycles采用首fire与已有started的并集，分别包括compute_done与最终drain边沿；32bit饱和、终态后停止。compute/tensor flow_stall仅输出核心域valid&&!ready事件，production OR成每周期并集，再进入job计数自增；未见其反馈ready/valid、状态转移或恢复控制。fatal快照冻结后，后台discard排空不继续改DONE计数。此结论不修正上表终态错误仲裁缺陷，也不声称AT028通过。

当前源码身份：hap_attention_mlp_production_core_linear.sv `1f6b304e3411da03c1ec76e92d17c71ea4b6ddc7c0a009e6184d1cbe44a45a11`；hap_mlp_linear_job_control.sv `e45db0110c994619b892648b7d87922567acc9c59b4a425b2ebbb89be7b28769`；hap_mlp_linear_tensor_dma.sv `7687da4ac6ea4922e335f757115502558b301dacb9fa88f29d44be211a3ba02f`；hap_mlp_linear_axi256_dma.sv `ce379a1959364de5bb7b127505ed93d77829e4d8ed3e9195589d625ec559d2a9`；hap_mlp_linear_compute16_s54.sv `37b439054272f6de73e9eb0dbe59840b8fd7c63fcea6581f2f7f38f1242d57a4`。后续修复改hash即为新审核对象；本回合完成后退出，真实整合终审再由Root复用。


## 第五次有界阶段审核：SM026受影响范围验收

2026-10-24，A021；execution=completed，verdict=LIMITED_PASS，applicability=下列冻结输入及差异复用范围。只读源码/原始结果、比较snapshot与SHA、执行当前入口只读check和静态shape/模块声明核查；未启动EDA、重跑测试、重新生成gold或修改生产文件。design revision4与生产ABI revision2保持。

### 原始终态与当前身份

| 证据 | 独立核到的原始结果 | 适用版本与范围 |
| --- | --- | --- |
| [AT028 integration](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R001/attempts/AT028_integration/result.json) | PASS；六步骤native0/stop=null；xsim.log唯一PASS；235509 checks、139012 core周期、491520 B metadata、2次soft-clear；XSim run14m51，监督xsim步骤896.629 s | 冻结snapshot逐文件与inputs.json一致。完整§9序列已运行；当前只有production core、job control和TB focused宏三文件变化，不能把AT028称为当前全部源重跑 |
| [AT030 job priority](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R001/attempts/AT030_job_fault_priority/result.json) | PASS；六步骤native0/stop=null；唯一PASS；5810 ns终止 | snapshot及当前全部输入SHA一致。控制公共接口/同拍事件/owner/快照/计数单位验证，paths由TB驱动，不能单独证明真实transport排空 |
| [AT031 global fault](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R001/attempts/AT031_global_fault_current/result.json) | PASS；六步骤native0/stop=null；唯一PASS；30529 checks、23820 core周期、245760 B metadata、soft-clear0；XSim run2m11，监督xsim步骤137.623 s | snapshot及当前全部输入SHA一致。实际编译宏M006_GLOBAL_FAULT_ONLY，只运行physical DDR1 framing→拒绝soft-clear→真实core reset→GU gold重试；没有重跑AT028全部序列 |

上述checks是TB检查调用计数，不等同独立数值样本数或覆盖百分比。XSim墙钟是仿真成本，不是板卡吞吐。历史失败AT024（SV参考time0不符literal）、AT026（START合法job_clear基线断言错误）均保留；未通过修改gold数值或放宽DUT输出检查改判。

### 真实整合与独立gold

AT028使用真实CSR/router/job、metadata DMA/resident/scheduler、完整REC576/cache、共享双8×12核、weight/CDC与专属DDR路由、tensor DMA。外部BFM施加非同时100/200 MHz域、AXI各通道背压/末B延迟；无force内部quiescent、无算术stub、无直写resident绕过LOAD/COMMIT。真实Attention实例处于idle，测试观察其正常launch允许与无被误清脉冲；这不等同Attention并发。

同epoch两cohort的GU/Down四任务、全部16行逐输出W字节gold、tail12/12/8与12/4、输入/metadata/weight/cache/输出计数、末B阻塞无DONE或clear、坏REC前缀7×576及剩余输入排空/ACK/同epoch重试均覆盖。Down ABORT继续计算/传输退役后通过实际共享维护撤销epoch/metadata，DONE保留。GU首BRESP错误只接受一个AW/B、无新AW，compute discard及真实transport屏障最终触发维护；reset_required阻ACK，hard_clear保留DONE身份/首错/计数与ADMISSION_ERROR，再ACK、重载metadata/epoch并Down重试。故障排空闭环因此在受测形状获得动态回应，第四次预检的该风险不再保持未验证。

独立参考为[Python生成器](../../../E013_mlp_linear_only_hardware/experiment_results/host_reference/integration_gold/generate_integration_gold.py)及[生成manifest](../../../E013_mlp_linear_only_hardware/experiment_results/host_reference/integration_gold/manifest.json)。生成器直接用任意精度整数计算每组32项dot、code乘积、按组shift恢复、完整K求和和half-away舍入/饱和；不读取DUT结果计算gold，不导入RTL调度或失败SV算术。q/W4随group/lane、code/shift随row/column变化，两cohort/两投影不同。10240值（8192 GU S24、2048 Down S32）共32768 B，96条packed-row常量；六个预先固定literal覆盖正负和小幅舍入。

本轮核六件gold输入在AT028 snapshot与当前逐字节一致，96条常量同时完整嵌入AT028与当前TB；生成器SHA `b1c5e6ca08a3e590f66804a6664938233c391e0ff876bd94d8cbf135c4597121`，gold_words.bin SHA `9f53ded7be5164d82f3957b5429cf6d527173c398fb7f33fdefcc9c05dd9c39e`，gold_rows.svtext SHA `453b89e46487899b1260bf99f134a786329cbef400399eec3711ad6839545e2d`，all_values.json SHA `8ef295bbff2f37cc935d02ef12ea08fd743c2303cb72b4e86bfe224ce3163885`。生成manifest的TB SHA早于后续控制断言修复；这里以冻结inputs及实际嵌入内容匹配建立绑定，没有把旧TB SHA当当前身份。该组是合成数值证据，未宣称真实模型权重或SwiGLU整层链。

### 五项修复与复用依据

| 前轮问题 | 当前实现及本轮断言核查 | 限定结论 |
| --- | --- | --- |
| 恢复-01，同拍ABORT成功码 | 组合selected_error包含本拍合法abort_fire；AT030 id40令合法ABORT与DRAIN退役同拍，公开DONE必须2201且身份40；原四个正常任务仍成功 | 受测ABORT边沿PASS；维护同拍采用同一组合规则，未声称所有同拍组合穷举 |
| 恢复-02，LOAD覆盖首错 | live_error只由无旧码时的统一选择锁存，LOAD错误只改phase；AT030 id41先ABORT后padding仍2201/4032 B，id44同拍新padding与ABORT取2001 | 首错及确定优先级PASS |
| 恢复-03，全局fault/无owner | core将paired_error/data_conflict纳入error/fatal并强制非quiet，健康SHARED不等待全Attention+MLP的global quiet；job active_owned只标真正accepted任务。AT030 idle/旧descriptor/clear不造DONE、fatal+START回1007、有owner clear补2202；AT031物理DDR1早RLAST保持global_freeze/reset_required/paired非quiet，软清理请求不生效，真正reset后GU逐byte恢复 | 当前全局framing恢复PASS；data_conflict连线静态确认，未注入所有global故障来源 |
| 恢复-04，late fatal与ACK | fatal跨phase升级；ACK显式拒绝fatal_now；已有DONE不重新snapshot。AT030 id43原成功DONE后fatal与匹配ACK同拍，ACK拒绝、reset_required升高、DONE身份/码0/计数保留且无job_clear | 公开边沿行为PASS；严重性与既有首码分离 |
| 恢复-05，recoverable关闭deadline | timeout_now不再依赖!paths_error，旧首码参与超时快照；AT030 id42用80周期timeout，padding2001且不发load_done，最终reset_required/busy及4032 B前缀保留；后改live输入不改DONE | 活动recoverable不关闭deadline及首错快照PASS；生产10M周期未跑，ABORT后timeout等交叉组合由同一选择逻辑静态覆盖，未称动态穷举 |

独立diff确认AT028之后仅两处生产RTL控制修改：core新增全局故障诊断/非quiet；job统一首错、owner、超时及同拍行为。kernel/cache/parser、metadata、DMA、数值恢复、调度、数据及ready/valid源未变。当前core SHA `9f01889b274f6b2d2fd715d3760d4663617af5ef6246bfb8596d63a69d05b0f4`；job SHA `dabfcb656da836830de7fc4a4dc8f74ff0c0ed280a93b84c2138eaa97a49b359`；当前整合TB SHA `9e9d4d3e4296a97eef7d053c38780b74a5b0aef8f87c2fedcab83c09e35349e8`。TB差异仅新增focused编译分支/范围打印，默认仍执行完整序列，gold及全部原断言保留。

健康路径fatal/selected_error为0且owner在admission置1，正常phase/arm/fire/store_seen/数量核验保持；原mid-compute ABORT及BRESP在非同时事件下选择相同首码。AT030保留四job及公开fire/done的inclusive计数断言，observer只输出并进入计数，不反馈控制。因此接受AT028未改变数值/正常/已受测BRESP排空证据的限定复用，结合AT030新控制和AT031真实全局故障补验；不是“当前整合全套又跑了一次”。工程的[复用说明](../../../E013_mlp_linear_only_hardware/experiment_source/reuse_after_priority_revision.md)与本轮独立diff一致。

### 生产入口资格与未验证边界

当前m006_entry实际只读check返回M006_INPUT_CHECK_PASS 104；递归闭合104个冻结依赖、83个selected_hdl、100个模块且无重名，44个Attention基线源SHA全部一致。旧CSR头部仅用于generator可复现依赖，未选入生产HDL；MLP非线性/旧full/serial未选入。board wrapper显式14336/4096/enforce1；production/resource/compute三层default与传播、K128/448、1792/256输出记录、229376/114688 metadata和四payload均由入口静态执行核验，独立于initial error。正式input_manifest SHA为`97d7b3403fe0549499204e02c5f140d4296fe3881648906506c05971bda6c64c`。

[R003/AT001](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R003/attempts/AT001_entry_helpers/result.json)的18项CPU入口测试只适用于其当时helper：包括形状负向变异拒绝、XPR规范化和session子进程归属；后续artifact绑定变动未借该旧PASS声称全入口动态复验。[R003/AT002](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R003/attempts/AT002_csr_repro/result.json)记录隔离CSR逐byte重生成一致。当前create静态可见正式模式拒validate-only、记录实际TOP/defines/compile-order/BD公开属性，并明确参数值来自static_bound_source、actual_elaboration_parameters=unavailable；真实constructor仍必须产出并核这些报告，空属性不能当动态参数证明。

本轮未发现阻止按已授权依赖进入constructor的具体问题。A022已启动新根R003/AT003，A021不等待/预判其终态；普通工具修复继续新attempt取证，不增加逐次批准门。**NOT_RUN或未验收：生产全N整数整合、metadata全容量/高地址、Attention并发SHARED、32层真实模型/完整Host调度/真实XDMA拒绝传播、生产watchdog裕量、constructor终态、新综合资源与实际层次、合法route、100/200 MHz时序/未约束路径、DRC/CDC、bitstream与上板。** 此次有限功能PASS和静态输入资格不替代上述任何一项。


## 第六次有界阶段审核：SM027构造、当前综合网表与诊断清理继承

2026-10-24，A021；execution=completed（本次有限审核），verdict=CONSTRUCTOR_LIMITED_PASS_REQUALIFICATION_REQUIRED。适用R003/AT003构造终态、AT004完整DCP/资源/约束及本轮到齐的终态质量。无EDA、无测试重跑、无生产改动；未重审SM026功能/Host。AT004于05:43:10Z自然终态FAIL，native1/stop=null/changed_inputs=[]，峰值RSS53,746,458,624 B；末尾身份probe未正确匹配Vivado前缀后的模块并拒绝debug占位，成功synth receipt未签发。**普通入口修复及新原生DCP qualification可连续推进；物理最终资格尚未签定。**

### 构造与当前综合输入链

[AT003原始result](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R003/attempts/AT003_constructor/result.json)为native0、stop=null、changed_inputs=[]、NATIVE_STAGE_COMPLETED；8个记录owned PID最终survivors=[]，峰值RSS3,139,215,360 B。launch实际affinity为32 CPU、192 GiB RSS上限、maxThreads8/IP jobs4、validate_only0，符合既定profile。

constructor receipt SHA `ae7554f94f05808ec1c5954da8010c1ad7a6b479b6d90d0ea907be468025e72f`；其1323生成文件+规范化XPR inventory与AT004启动project_inputs逐项相同。10个native工件现存SHA均匹配；AT003/AT004两份冻结manifest和全部source_snapshot同SHA `97d7b3403fe0549499204e02c5f140d4296fe3881648906506c05971bda6c64c`，本次读取时104个生产依赖仍无漂移。AT004保存的constructor_identity与真实receipt完全相同；没有借旧M003工程或DCP路径提供来源。

[constructor_summary](../../vivado/reports/m006_linear_AT003_constructor/constructor_summary.txt)记录真实wrapper top、2025.2、xcvu9p-flga2104-2L-e、VCU118 2.0、真实Attention宏和BD core100 MHz/双DDR UI200 MHz；production_shape、compile-order和BD可见属性的SHA有绑定，actual_elaboration_parameters明确unavailable，没有把静态参数当动态读取。

综合推进后，原constructor inventory中22个生成IP的.xml及规范化XPR身份已变化；这是本轮观察到的阶段间产物变化，不能声称当前工程仍逐byte等于constructor。AT004开始时inventory相同已独立核实，后续应由成功synth的post-inventory签定当前生成物，impl再对该inventory复核；当前runner正采用此分阶段链，不能回写constructor历史或跳过变更检查。具体生成XML变化内容未在本轮逐项反推。

### 已导出的完整整板DCP、约束与资源

[AT004 DCP约束证据](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R003/attempts/AT004_synth/dcp_constraint_members.json)与实际ZIP成员逐项核对一致：完整DCP为211,877,273 B，SHA `cf11b600c30b4cf0756693e3e4c76dd8b04ac09e79eaf644a05ba9d988bc5a4b`。dcp.xml为wrapper top/正确part、OutOfContext=0，包含完整EDIF、数据库及四个序列化XDC成员；这是已链接全板checkpoint，不是单个core OOC网表。23份原生run日志（22 OOC+top）均有成功综合终态；23份Attention softmax ROM staging哈希全匹配，未见Synth8-4445。

四个实际XDC成员哈希、大小与证据JSON一致；主XDC含237个PACKAGE_PIN和235个IOSTANDARD属性设置。early XDC保存两个DDR板级参考钟4 ns，主XDC保存PCIe参考钟10 ns，late XDC保存PCIe与双DDR参考域三组asynchronous且include_generated_clocks。实际XPR中四份有效board/DDR/clock约束均用于synthesis+implementation；唯一impl-only M006 XDC仅注释和诊断打印。因此本轮没有证实有效约束遗漏，不能因文件标记或一个诊断critical就推断DCP无约束。这里核到的是DCP序列化约束；100/200 MHz实际派生clock对象、路径覆盖与CDC正确性仍待native identity/质量报告，不能用主参考钟代替UI时钟验收。

[真实hierarchical utilization](../../vivado/reports/m006_linear_AT004_synth/utilization_hierarchical.rpt)标明Synthesized、完整wrapper与正确器件：整板Total LUT766078（Logic722967/LUTRAM28560/SRL14551）、FF954137、RAMB36 827+RAMB18 16即835个36Kb tile当量、URAM752、DSP5375。真实层次含Attention cohort16、MLP linear cache/compute及共享核；共享核DSP3072，MLP compute总DSP3073，cache使用RAMB36 64。受查层次未见旧MLP full/SwiGLU/H32 frontend；随后native身份report误用hap_*开头匹配，Attention/kernel及board pin均为空；实际唯一blackbox是dbg_hub/ref=dbg_hub_CV。须修正包括禁止叶子在内的精确模块尾名/层次匹配后原生复核，不能用当前0计数证明未解析RTL或禁止叶子为零。

这些是当前综合网表的实测资源，不能称为物理资源最终值、拥塞改善、可合法布通或时序收敛。没有与不同父图的旧M003资源作无条件差值比较；功能形状保护依然沿用前轮已验收的默认14336/4096/128/448/enforce1输入链。

### 诊断清理与DCP继承的限定判断

top synth_1及open_run日志唯一critical类别为Designutils20-1307，指向ddr_timing_recovery.xdc:9不支持的puts。该文件除注释只有一条braced literal puts；mlp_linear_physical.xdc同样仅注释加一条literal puts。本次候选只删两条打印，其他字节保留，诊断移入driver_diagnostics.json；没有删除有效timing exception、引脚、clock、placement或RTL/IP/ROM内容。原AT004日志和critical事实保留，不能事后改写为零critical。

已读[候选runner](../../../E013_mlp_linear_only_hardware/experiment_source/diagnostic_cleanup/staged_run_mlp_linear_board.py)全部继承函数与相对冻结runner的diff，SHA `bfeb44d46cf2f3ae2ffa226d8a3ef63fae9db39e709b06cd4dfc1a8de7da0dde`。仅允许impl显式继承；manifest除files外必须完全一致，dependency membership不变，精确变更集合只能是runner和两份指定XDC。每份XDC核父snapshot SHA，当前字节必须恰好删除唯一literal puts；父DCP/receipt/constructor/current+parent manifest/driver exact patch都绑定SHA，父result必须native0/null stop/无漂移且owned survivors空。外围入口仍核真实DCP、全部native artifacts、post-synth generated inventory/XPR；不是仅凭一个继承JSON绕过父链。

[R003/AT005候选13case](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R003/attempts/AT005_diagnostic_helpers/staged_result_v2.json)原始PASS，driver/test源码SHA均匹配；包括有效候选、RTL/membership/shape/有效约束变更、父snapshot/manifest、故障终态、owned残留、DCP身份、patch、record身份及外范围拒绝。该测试使用隔离synthetic fixtures，本轮未重跑；它证明受测守卫，尚不证明真实AT004父链已生成或实际继承成功。

结论：**精确的纯诊断清理无需重跑未受影响综合**，但AT004现已FAIL，无成功父receipt，不能直接使用上述仅接受成功父的候选继承路线。若身份probe修复加入build脚本，实际集合也超过原三文件；13case仅保留其旧候选适用范围。Root/A022已实际确认新原生DCP qualification路线：保留AT004 FAIL及其原DCP，以正确查询重新核同一DCP/实际clock/完整质量，并签独立成功qualification回执后承接impl。该回执须显式绑定失败父、准确失败原因、原生22+top成功证据、constructor/输入图/生成IP/DCP SHA及新查询脚本差异；不得泛化接受任意FAIL父，不得伪装成已通过旧allowlist。普通修复无需逐项批准。

### 本轮新增终态质量的有限分类

[stage_quality](../../vivado/reports/m006_linear_AT004_synth/stage_quality.json)与原始报告到齐，原生synth process完成，attempt因最后required netlist/clock身份检查失败而native1。hierarchical report已有实际前缀`scalellm_vcu118_f05_bd_core_0_hap_*`模块；查询只认`hap_*`开头导致Attention/shared核计数0和三个board clock pin空。该查询错误不证明硬件模块或时钟真实缺失；同时不能据此直接签成功。新qualification必须实际读取正确对象，查询精确匹配并拒绝缺失/多义对象，不能只把预期计数写进结果。

[timing_summary](../../vivado/reports/m006_linear_AT004_synth/timing_summary.rpt) SHA `5f22e162a5d9e085f2fa00e09769e3253da36da2d5801bcea7f11f7cec366c47`：未布局WNS+0.904 ns/TNS0、setup失败0；WHS−0.814 ns/THS−46941.938 ns、hold失败936065；另WPWS−0.012 ns/TPWS−0.037 ns、pulse-width失败5。前两类分别是当前综合估计，setup非负不证明最终时序，未布局hold负值也不直接判不可实现；均保留，允许正常opt/后继实现取得实际证据。Clock Summary可见core `clk_out1_scalellm_vcu118_f05_bd_clk_core_0`为10 ns/100 MHz，双DDR派生clock有5 ns/200 MHz；对应board pin的唯一clock身份仍须修正probe后实际核。

逐条分类完整check_timing列表：no_clock530全部为双DDR校准debug，每DDR含U_XSDB_SLAVE 213+u_xsdb_arbiter52，根分别dbg_hub/sl_iport0_o[1]与sl_iport1_o[1]；unconstrained_internal554全部在同一校准域，每DDR233+44。没有MLP/Attention对象。另no_input_delay唯一pcie_perstn，no_output_delay为ddr4_sdram_c1_reset_n/c2_reset_n，必须单列reset接口语义，不以“DDR debug”一并豁免。

实际唯一占位cell=dbg_hub/ref=dbg_hub_CV与上述两个clock根相连。AMD [UG908 2025.2 Debug Hub](https://docs.amd.com/r/2025.2-English/ug908-vivado-programming-debugging/Debug-Hub)说明UltraScale/Memory IP调试hub在opt_design插入；[同版实现章节](https://docs.amd.com/r/2025.2-English/ug908-vivado-programming-debugging/Implementing-the-Design-Containing-the-Debug-Cores?contentId=VJJXx7_BBA1ReATTMJl0vw)明确其最初为blackbox，place/route前须完成实现。据此允许正常opt取证，只限定这一个已识别厂商占位，不允许任意dbg*或未知RTL黑盒。post-opt须实际确认该占位已实现、无其他未解析blackbox，并回查530/554对象的clock/约束及计数变化；不能从文档推定本工程一定自动消失，不加无来源false-path或waiver。

[cdc.rpt](../../vivado/reports/m006_linear_AT004_synth/cdc.rpt) SHA `a16a76a6c40ec581135761cd6910be550387451d4250a0ebee2cca44fe97aa0f`：CDC3 Info434、CDC9 Info19、CDC10 Critical6、CDC15 Warning6198。仅六条critical做本轮实际路径分类：两个DDR `div_clk_rst_r1_reg/C`经ready组合逻辑到core_gate/u_ready0或1_cdc/arststages_ff_reg[0]/CLR；其余四条为d0/d1_gate的u_ready_cdc末级到各Smartconnect psr0和psr_aclk1的ACTIVE_LOW_AUX同步器首级D。读取源代码确认ready=calib_done AND NOT ui_reset；board gate使用四级XPM异步assert/同步release，输出再与base reset合并。报告指向真实reset控制路径而非MLP数据，但组合逻辑/多源reset解除的可靠性不能仅凭XPM命名、基线身份或asynchronous clock groups认定通过。六项均保持PENDING_REVIEW，后续核实际fanin/同步级/解除时序与post-opt拓扑，不能扩大为CDC整体waiver；6198条warning未在本轮逐路径审核。

本轮按Root限定要求补读六项必要源结构后，**结构层面限定接受，可继续正常opt，当前没有据此要求RTL修改的实质证据**；原CDC-10报告仍保留Critical，最终CDC未签。两个core_gate接收端实际是`xpm_cdc_async_rst` active-low、四级、ASYNC_REG，vendor实现明确异步置reset、目的clk逐拍释放；MIG的ui_clk_sync_rst由同一c0_div_clk寄存驱动。四个Smartconnect接收端不是async_rst原语：生成proc_sys_reset 5.0.17 wrapper均为C_AUX_RESET_HIGH=0、C_AUX_RST_WIDTH=1、目的100 MHz；其LPF的ACTIVE_LOW_AUX先反相reset电平，经`xpm_cdc_single`四级/SRC_INPUT_REG=0重新同步，再LPF和同步reset sequencer，不能声称该整条链零延迟异步断言。生成bd_ea2b/bd_2a3b的psr0/psr_aclk1明确aux_reset_in接aresetn；d*_gate的base和ready分别同DDR域同步释放后AND，任一异步reset断言只使低有效reset拉低。该判断基于稳定复位电平、reset期间不承诺业务数据保持的既有板级reset用途，不适用于任意短脉冲、数据重汇合或正常job_clear。

读取依据含[board双ready门](../../rtl/board/hap_v5_dual_async_ready_gate_xpm.sv)、[board reset门](../../rtl/board/hap_v5_reset_gate_xpm.sv)、实际生成d0/d1_smc各psr0与psr_aclk1 wrapper/clock map，以及本机Vivado2025.2 vendor源`data/ip/xilinx/proc_sys_reset_v5_0/hdl/proc_sys_reset_v5_0_vh_rfs.vhd:1010`（SHA `df892cc9994a5a02f7089876a26e2129d449d8221c4e6cbf45f46e28e4a32696`）与`data/ip/xpm/xpm_cdc/hdl/xpm_cdc.sv:1227`（SHA `27592359d8363d7e6575298f9d0faa7c9f9258ea77f19c9a38946fbaf3783f09`）。接受的是这六个准确实例的复位架构解释，未用set_false_path/waiver消除报告；post-opt回查这些结构/极性/同步级不退化，最终映射后的reset时序与整体CDC另判。

DRC native对象计数error/critical0、warning15769、unknown0，按现有规则为PENDING_REVIEW；这与top日志Designutils诊断critical不是同一个计数。原stage_quality总体FAIL、hold/unconstrained FAIL和CDC/DRC PENDING均保留，不以native查询修复篡改历史。

本轮已就新增终态/实际六条CDC完成有限分类，不等待新的qualification/opt结果。可连续执行修正后的原生DCP qualification及正常opt取证，未签place/route最终质量或CDC豁免。后续仅核新qualification回执、实际应用差异/post-inventory和post-opt必须回查对象，复用已核constructor/DCP/1323起点/约束成员；**PENDING：修正后的实际netlist/clock身份、有效父链、debug占位与未约束列表post-opt结果、六CDC结构的post-opt一致性/reset接口判断、最终hold/pulse-width/DRC/CDC。NOT_RUN：本次新opt/place/physopt/route、bitstream/上板。**

## 第七次有界审核：SM027 qualification来源与实现前置检查

日期2026-10-24。仅复核当前[build入口](../../vivado/scripts/build_mlp_linear_board.tcl)、[runner](../../vivado/scripts/run_mlp_linear_board.py)、AT004→AT009来源记录及impl前置依赖；不重扫constructor、Host、数值或功能回归，不运行EDA或测试。结论为 **AT009原生qualification限定接受，可进入正常opt取证**；本轮未发现能使当前qualification虚假签发成功凭证的具体阻断缺陷。此结论不等于post-opt或最终物理质量PASS。

冻结对象：AT009 manifest SHA `3b46f8bcd155d6de51bdae45956212625b4c1759ee56acf07d581aafd33479d5`；build SHA `ea4c162d0e9a5920c4eda02e91c740e8cbdc0b8b7d8f5874c6a75169b7c11780`，runner SHA `43819703f5fa9660660e575212c8a7cd6a623b067a41c9fa147aaaffac51a73c`。两份当前入口与AT009 source_snapshot逐字节一致，未热改。

来源验证的限定范围已核：validator只接受准确R003/AT004_synth的已记录失败，要求native1、null stop、无漂移/残留、23份实际synth成功日志、原manifest/source snapshot、1433项post-failure inventory与规范化XPR、原constructor SHA、同DCP与原报告SHA；旧13case草案不用于接受FAIL父。独立重算[AT004_origin](../../../E013_mlp_linear_only_hardware/experiment_source/dcp_qualification/AT004_origin.json)所列5份来源证据和23份日志SHA均一致；未重复遍历已审constructor的1323项文件。

对父manifest与AT009 manifest进行结构比较，非files字段和文件成员集相同，变化准确限定为build、runner及两XDC。两XDC均逐字节等于父快照删除唯一literal `puts {...}`行，无有效约束变化；两个driver当前内容与记录的完整unified diff及patch SHA一致。[AT004_requalification](../../../E013_mlp_linear_only_hardware/experiment_source/dcp_qualification/AT004_requalification.json)准确绑定该四文件差异和本次freeze。AT009复制DCP的SHA仍为 `cf11b600c30b4cf0756693e3e4c76dd8b04ac09e79eaf644a05ba9d988bc5a4b`；七份复用utilization/timing/clock_interaction/CDC/DRC/check_timing/native DRC报告及inherited_stage_quality与AT004原字节一致，origin副本内容一致。原FAIL/PENDING质量含义未改变。

凭证门和impl依赖：仅native0、无resource stop/输入变化/owned survivor且必须工件齐备才签新`qualified_existing_synthesis_dcp` receipt；原生netlist/clock身份不通过会返回失败，24级reset核验异常也不会签凭证。impl要求该成功receipt与其实际成功result、当前manifest、原constructor身份、准确DCP路径/SHA、已绑定工件及生成输入一致，再使用receipt绑定的debug目标来源；constructor旧freeze只由成功qualification scope连接。原生阶段完成与overall质量仍分开，原timing/unconstrained FAIL及CDC/DRC PENDING不会被新身份PASS覆盖。

原生对象使用已做限定静态检查：board pin和post-opt clock查询直接传递`get_pins`集合到`get_clocks -of_objects`，不再以`lappend/concat`字符串列表替代该集合；当前源未发现同类确定性类型缺陷。AT009新增原生终态已确认该qualification范围的实际对象可读且身份通过；post-opt分支尚未执行。AT007的fresh `close_design`失败、AT008的clock集合类型失败均有native1/null stop/changed[]/0survivor原result，均无成功synth receipt；不重标历史失败为PASS。

post-opt检查实际位于`opt_design`之后、`place_design`之前：禁止任何剩余blackbox，对原530/554目标记录存续与接收寄存器clock，核六条准确同步链共24级的存在、FD原语、ASYNC_REG、目的10ns clock及相邻D驱动，失败立即阻止place。这里只有准确`dbg_hub/dbg_hub_CV`可在pre-opt阶段作为厂商占位，未扩大成通用debug黑盒豁免；六条CDC-10报告保留。

**覆盖边界必须保留**：post-opt的`removed`只表示原精确对象名未命中，不能断言其功能逻辑已删除；`clocked`只表示接收寄存器能查询到clock，不能断言该endpoint的全部时序约束充分。因此该gate的PASS仅限零黑盒、原目标存续/clock覆盖及24级结构，不能替代实现后全局`check_timing`、unconstrained、setup/hold/pulse-width、DRC、CDC与route判据。未新增无来源false-path或waiver。此界限已明确发Root/A022，工程确认在E013与后续里程碑保留。

收尾自检时AT009实际终态到齐，已只补核新增证据：[result](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R003/attempts/AT009_dcp_qualification/result.json)于2026-10-24T06:18:01.543576Z完成，native0、null stop、changed[]、4个owned进程/0survivor，peak20.04 GiB。新receipt SHA `f0fee79c00fa8247e208df86e8edb8556b7a3a227eca9c4015ce82fde8716ee5`，其report/evidence副本一致；26个绑定工件SHA全部核对一致，manifest/constructor/debug来源身份一致，1433项receipt inventory与本次project_outputs内容一致。原生txt实际确认Attention1、共享核1、禁止MLP非线性0、用户未解黑盒0、唯一pre-opt dbg_hub_CV；board core/ddr0/ddr1 pin分别对应10/5/5 ns唯一clock，六条链共24级的原语/ASYNC_REG/目的clock/相邻D连接全部PASS。原overall仍为FAIL，继承timing/unconstrained/CDC/DRC含义未抹除。

因此接受当前成功资格凭证，允许由A022继续正常opt并执行已有pre-place门；不因纯查询修复重综合，也不把历史AT004/007/008改成成功。**PENDING：实际post-opt黑盒/原对象clock覆盖/24级结构及最终全局质量。NOT_RUN（本轮）：EDA、测试、post-opt/pre-place实际检查、place/route及最终物理验收。** 后续仅核新增实现证据，不重做本次来源字节与历史constructor审核；普通修复仍由A022连续执行。


## 第八次有界审核：真实post-opt对象与同步结构门

日期2026-10-24。仅核R004/AT001_impl新增post-opt证据，结论为 **POST_OPT_GATE_LIMITED_PASS**；没有新增布局/布线停点，也不替代整轮物理验收。未重复qualification、constructor或功能审核，未启动EDA或修改工程输入。

来源：本次[observation](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R004/attempts/AT001_impl/post_opt_observation.json)、impl launch及复制的成功资格receipt相互一致：manifest SHA仍`3b46f8bcd155d6de51bdae45956212625b4c1759ee56acf07d581aafd33479d5`，receipt SHA与launch绑定一致，DCP路径/SHA与receipt一致，debug目标来源SHA一致。只核本次来源连接，未重遍历旧构造工件。

[post_opt_debug_identity](../../vivado/reports/m006_linear_AT001_impl/post_opt_debug_identity.txt)实际310647 B、SHA `742078fbbf976a07d99bf9fa4f56f8f758415bb14059463ed751c1bb86367dea`，与observation一致。原530个no_clock目标和554个unconstrained目标逐名、顺序与绑定来源完全一致，各集合内无重复；全部存续，owner为该pin的准确所属cell，全部实际查询到clock `mmcm_clkout5_1`，各自removed=0、missing_clock=0。原生blackbox列表为空。该结果确认本工程实际opt后占位消除与既定目标clock覆盖，不再仅依赖厂商流程预期；当前报告没有提供该新debug clock的完整时序质量，不从clock名称推导频率或收敛。

[post_opt_reset_cdc_identity](../../vivado/reports/m006_linear_AT001_impl/post_opt_reset_cdc_identity.txt)实际8552 B、SHA `191832b032e033ad50f2764ad223310953f7292dc45dd322e6d1c0f25d71543f`，与observation一致。准确六链24级原生输出与已资格确认对象逐行一致：两个core_gate链共8个FDCE，四个Smartconnect AUX链共16个FDRE；ASYNC_REG=1、目的core clock、逐级相邻D驱动及每级pass=1完整。接受这六条稳定复位电平路径的post-opt结构保持，不豁免原CDC-10或整个设计CDC。

[console](../../vivado/reports/m006_linear_AT001_impl/console.log)确认`opt_design completed successfully`，原生elapsed34m30、CPU1h42m46；该opt段77 Infos/113 Warnings/0 Critical Warnings/0 Errors。0error/critical仅是该命令阶段记录，未声称113条warning已逐项接受。优化后checkpoint写出，随后同进程已进入`place_design`；本轮观察时route尚未开始、整轮result尚不存在，资源采样不是最终runner peak。

**限定接受范围**：准确原目标存续及clock覆盖、零黑盒、六链24级同步结构。本次全部目标实际存续，未使用“旧名字消失”作为通过依据；clock可查询仍不等于endpoint全部约束充分。**PENDING：完整place/physopt/route终态、最终全局check_timing/unconstrained、setup/hold/pulse-width、DRC/CDC与资源保护终态。** Root/A022已收到结论，按既有合同连续实现；本代理完成本轮并退出，不等待长运行。


## 第九次有界核查：移除MLP非线性后的资源归因

日期2026-10-24，回应资源为何没有随算子数大幅下降。**实测资源确实下降，但保留的矩阵阵列与metadata存储占主体。** 本轮仅只读报告/RTL和静态算术，impl继续，无EDA或工程输入改动。

比较对象：[旧M003 E011/R002/AT003整板报告](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/hardware/vivado/reports/m003_E011_R002_AT003_fresh_synth/utilization_hierarchical_post_synth.rpt)与[新M006 AT004整板报告](../../vivado/reports/m006_linear_AT004_synth/utilization_hierarchical.rpt)，均为Vivado2025.2 Build6299465、xcvu9p-flga2104-2L-e、scalellm_vcu118_f05_bd_wrapper、Synthesized；使用同一`Total LUTs`栏和BRAM36等效tile（RAMB36+RAMB18/2）。未拿raw LUT primitive、core OOC或physopt/place结果直接与整板综合相减。Root另核旧source_archive 95份RTL与新根保留基线SHA一致；本代理核下述默认shape链和分层统计。

| 同阶段整板资源 | 旧 | 新 | 减少 | 降幅 |
|---|---:|---:|---:|---:|
| Total LUTs | 828874 | 766078 | 62796 | 7.58% |
| FF | 1029350 | 954137 | 75213 | 7.31% |
| BRAM36等效tile | 945 | 835 | 110 | 11.64% |
| URAM | 752 | 752 | 0 | 0% |
| DSP | 5451 | 5375 | 76 | 1.39% |

生产形状可比：保留旧[resource top](../../rtl/integration/hap_attention_mlp_resource_top.sv:153)无参数override实例`hap_mlp_full_command16_s54`；[V5 manifest](../../vivado/manifests/attention_mlp_resource_top_v5_sources.list:36)选择宏重命名的[full command](../../rtl/mlp/hap_mlp_full_command16_v5_s54.sv:17)。其默认14336列、128组、Down448组/256条16列输出，并将参数传入[serial](../../rtl/mlp/hap_mlp_serial_ddr_command16_v5_s54.sv:7)，后者明确HIDDEN_COLUMNS4096、默认ENFORCE=1；full:360也断言14336/128/448/256。新生产默认同14336/4096/128/448，缩小shape只存在于已注明的TB实例。

当前资源主体与实际保留内容：

| 当前实际层次（父子行不可相加） | Total LUTs | FF | BRAM36等效tile | URAM | DSP |
|---|---:|---:|---:|---:|---:|
| MLP linear compute `u_mlp` | 424521 | 509711 | 317 | 0 | 3073 |
| 其中共享双8×12核 `u_shared_compute` | 392384 | 479315 | 192 | 0 | 3072 |
| 新共享activation cache `u_cache` | 4270 | 55 | 64 | 0 | 0 |
| MLP metadata AB banks | 3583 | 4454 | 0 | 672 | 0 |
| Attention整体 | 233907 | 272649 | 353 | 80 | 2296 |
| board core以外全部IP | 86280 | 136432 | 101 | 0 | 6 |

双8×12核仍承担Gate/Up/Down矩阵运算，[linear compute](../../rtl/mlp/hap_mlp_linear_compute16_s54.sv:517)继续实例化[共享核](../../rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s54.sv:147)的两个branch。共享核占当前MLP compute LUT约92.4%、全板LUT约51.2%，3072 DSP保留；删掉SiLU/H32/量化并未缩减这些矩阵运算所需的并行阵列。W4双DDR reader/frontend、Gate/Down调度、repack/累加/队列仍存在。metadata的Gate AB各224 URAM、Down AB各112 URAM合计672，占全板752的89.4%；[新production metadata实例](../../rtl/integration/hap_attention_mlp_production_core_linear.sv:197)仍按完整权重形状与AB驻留协议配置，另80 URAM是Attention，因此URAM不降。

旧被移除的操作本来已复用硬件，不能按“删掉几种操作”估计为删除几套大阵列：旧[compact input](../../rtl/mlp/hap_mlp_input_frontend16_compact_cache.sv:3)是一套H32和四个A8量化器分时服务16行；[fold4 H32](../../rtl/mlp/hap_mlp_hadamard32_s24_fold4.sv:3)每拍只做4个归一化乘法，正式旧报告只占8 DSP。旧整个input frontend（含两半缓存）35118 LUT/42301 FF/66 BRAMtile/8 DSP；并非16套H32与16套量化器。

旧[SwiGLU frontend](../../rtl/mlp/hap_mlp_swiglu_product_frontend16_q4.sv:3)只有两个row-local SiLU producer、一套中央H32、四个量化器，逐行/逐元素复用；整个层次为30914 LUT/31477 FF/44 BRAM36/68 DSP。两[SiLU leaf](../../rtl/mlp/hap_mlp_silu_mul.sv:37)各为8192×24 block ROM和单元素流水乘法，实测每个1866 LUT/105 FF/6 BRAM36/2 DSP；其余64 DSP来自中央S32 H32。量化器采用多状态、复用除法通路，并未各铺开32个独立除法器。故整板DSP净降76恰为输入H32的8 + 中间H32的64 + 两SiLU的4；主核3072 DSP与Attention2296 DSP未删。

BRAM也能具体对账：旧输入双8row缓存66 tile、旧Down activation cache64、旧SwiGLU frontend44，替换成新统一linear cache64，净降110；共享核192、GU gather96、W4 frontend29、Attention353与板级IP101等主要BRAM仍保留。此为对实际层次归并后核算，不把父层次及子ROM重复相加。

LUT/FF总差不能简单相加“被删层次”：新tensor DMA/job/CSR控制和cache替代有自己的成本；共享核旧389143 LUT→新392384（+3241），其FF479315/BRAM192/DSP3072完全一致。该LUT差发生在不同外围连接/调度综合上下文，本轮未做primitive级逐cell归因，不将其武断归为某一优化或异常。Attention旧234090 LUT/272661 FF→新233907/272649，少183 LUT/12 FF，其BRAM/URAM/DSP不变；board core外各顶层IP及合计全部一致。新旧core的净差正好等于整板净差。最终可确认的是7.58% LUT、7.31% FF、11.64% BRAM和1.39% DSP实测下降；URAM因驻留metadata保留而不变，不能称“资源完全没少”，也不能承诺删算子就按操作数同比减少面积。

本轮没有修改设计目标或资源优化方案，未停止正在进行的impl。以上为同阶段综合资源归因，不能代替最终布局布线资源、频率、功耗或吞吐结论。


### 用户澄清：删操作能否缓解长期SLR问题

**有明确的局部减压机制，但目前只能确认综合资源释放，尚未实测本轮SLR拥塞改善，更不能承诺布通。** [E006既有归因](../../../E006_m002_slr1_congestion_attribution/experiment_results/summary.md)曾将SwiGLU `g_row_branch[1].u_branch_leaf`作为SLR1热点候选：8697是热点S成员交集，3072是入口data/select网，均不是“预计可省的SLL”。该候选后续物理版本位置已变化，不能把早期SLR1位置套到M003。

更近的[M003 E011失败route定位](../../../E011_m003_joint_routability_implementation/experiment_results/summary.md)明确存在projection→SwiGLU的INT_X57Y687（SLR2/X3Y11）；旧MLP input frontend/cache也进入实际冲突driver层次榜。这次完整删除SwiGLU/H32/量化前端，确实移除了这些宽选择、乘法/ROM/row-ring及控制汇聚链，并释放LUT/FF/BRAM，为相邻逻辑重新布局提供空间。因此并非只删除了与旧问题无关的小功能。

但仍保留旧问题的大块结构：共享双branch及其Down S54累加器、Gate/Down宽repack/弹性队列、parent payload选择/ready控制、weight/meta与DDR互连、Attention前端和计算阵列。E011实际样本中parent_head1299从SLR2/X1Y10到branch0 ingress的SLR0/X1Y3，路由实际经过三SLR；paired_weight184及d0_smc rdata→Attention/input/meta也有跨区域或跨SLR连接。新实现保留对应功能/数据边界，但本轮未证明它们会落在相同SLR或走相同路径。尤其[E004的大input热点](../../../E004_m002_routability_optimization_analysis/experiment_results/runs/R001/physical_routability_analysis.md)是**Attention input**的capture_index高扇出，不是本次删除的MLP input；不能把所有旧input热点都称已移除。早期E004曾同时出现全板LUT68.93%与CLB站点99.11%，说明可布线性还取决于站点打包、局部pin密度和连线跨度，资源比例下降不等价于拥塞同比下降；这些是旧阶段数据，不是本轮当前占用。

[E011 actual-driver表](../../../E011_m003_joint_routability_implementation/experiment_results/runs/R004/attempts/AT001_failed_route_driver_region_localization/evidence/offline_attribution/actual_driver_module_ranking.tsv)第2/4/6行分别为shared branch1 176163、branch0 94638、SwiGLU19406。单位是旧失败route去alias后的**canonical冲突网按实际driver所属层次归组数量**，跨所有source/load组合汇总；475行独立求和为637893，保留常量及与native report615840的既有口径残差。19406/637893=3.0422%仅该旧网集合中的driver归属比例，不是拥塞面积、driver cell数、样本交集、实际SLL用量或本次预期改善率；各模块互相争用，删掉其中之一也可能改善组外网络，不能按比例预测route结果。

当前终态后按Root既有授权只需对照四类具体证据，不变更当前运行输入或新增候选：

1. **同阶段每SLR站点/打包与局部拥塞**：CLB sites及LUT/FF/存储/控制集合分别统计，聚焦保留shared branch0/1、原projection→SwiGLU附近与旧SLR1热点窗，观察新cache/tensor DMA是否形成替代热点；不将触及site数当可释放site数。
2. **真实跨SLR连线**：检查parent ingress→branch0/1、paired_weight以及d0_smc→Attention/meta对应边界的实际source/load SLR、SLL/跨界需求和可读路由，不把endpoint对数直接当SLL消耗，不只看全板平均值。
3. **保留宽通路的局部代价**：Down S54输出/累加、Gate/Down repack和parent ready/CE的真实fanout、setup/hold关键路径及net-delay比例；确认删掉SwiGLU后瓶颈是否仍由shared/Attention控制或宽选择主导。
4. **最终合法布通与时序**：ROUTED_FULLY、unrouted/resource-conflict/overlap各自口径，WNS/TNS与WHS/THS及pulse-width；既有DRC/CDC和未约束路径合同保持。place/opt成功或总LUT下降均不能代替这些终态。

上述准确旧scope/文件已发A022，用于当前自然终态后的有界补证，不扫描新全设计或提前修改架构。结论仍是“减少了一部分真实历史热点及周边占用，方向上有望减压；是否缓解保留的跨SLR与局部拥塞，等待本轮实际物理证据”。


## 第十次有界审核：SLR只读诊断入口

日期2026-10-24。范围仅E013/experiment_source/slr_probe的runner、Tcl及CPU检查，后补与本次问题直接相关的routed观察器；未运行EDA、重跑CPU测试、修改104冻结输入，未重审历史功能/constructor/资源账。最终结论：**修订后有限静态接受，原生诊断NOT_RUN**，当前实现按原流程继续，无新增用户停点。

初始AT001/AT002的15项CPU证据只说明入口合成案例与Tcl source completeness通过。AT002已正确补`-sort_by slack`及每桶返回不超过100的断言，但本次查出三项实际缺口并立即交Root/A022连续修复：

| 缺口 | 影响 | AT003当前修复 |
|---|---|---|
| routed仅诊断时现算SHA，未对父阶段历史DCP hash | 父终态后替换同名文件无法由原导出日志识别 | 与placed/physopt一样强制历史observation；routed另绑生成时父root birth/输入manifest/终态前标记 |
| terminal gate未检查native退出码 | 外部signal或未知退出可能被null stop/0survivor误当自然终态 | 要求严格整数0/1，并校验execution/verdict与成功rc一致；保留自然FAIL用于诊断、不升级为成功 |
| report_timing同时用-of_objects与-delay_type | 2025.2原生命令参数互斥，四桶报告会ERROR/PARTIAL | 删除report_timing上的-delay_type，max/min只由已返回timing_path对象决定 |

第三项依据本机2025.2 `doc/eng/man/report_timing:184–193`及AMD [UG835 report_timing](https://docs.amd.com/r/2025.2-English/ug835-vivado-tcl-commands/report_timing)：path对象已有DELAY_TYPE，不能同时指定-delay_type/-setup/-hold。CPU Tcl `info complete`不会执行Vivado命令，因此旧CPU PASS不能覆盖此原生兼容性问题；未将旧证据重标为原生通过。

已补核[AT003_cpu](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R005/preparation/AT003_cpu/result.json)：22项unittest及Python编译/Tcl completeness三条命令真实rc0，三日志SHA匹配，六份当前源均与记录SHA及source_snapshot一致。当前runner SHA `f06f6f1a2bcc182ca95e5b31af9f1f3ece969b24acf41b782763cf600f5856b4`，Tcl SHA `97ac9b28eb898eb09b54bdeb4ec7170ca142f2e45eaee5da4af7adadc030d058`。新增用例覆盖routed无锚、替换DCP、错误父身份/终态后观察、observer不覆盖/死root/未导出，以及异常退出码。另读取AT001 active-parent --check-only实测rc1拒绝，未创建EDA或诊断attempt；本代理没有再次执行。

来源门：仅新根M006 R004 impl父记录，必须有terminal result/launch/ownership/manifest，null stop、changed[]、survivors[]，并对原owned PID+birth查活性。来源还绑定父source_snapshot、原成功qualification receipt、同DCP/project/input identity、原生指定阶段完成及随后checkpoint导出日志。placed/physopt/routed分别要求自己的历史DCP SHA和日志prefix，source_stage不由文件名以外的推测补齐；失败route可读取已成功保存的physopt阶段，但不能称routed或成功实现。父来源与诊断脚本在实际诊断结束时再次验hash，资源停止、输入漂移、残留或native非零均FAIL。

新[observe_routed_checkpoint.py](../../../E013_mlp_linear_only_hardware/experiment_source/slr_probe/observe_routed_checkpoint.py)只读取当前运行的文件/进程：新根R004、父impl、原PID/birth/session仍活跃、父result未存在、输入manifest一致，原生日志必须先route成功再DCP导出，hash前后文件大小/mtime稳定，写观察前再拒父终态，并用exclusive create禁止覆盖。它不启动工具或生成/改写DCP；缺少真实生成期观察则routed诊断继续拒绝，不能终态后凭现算hash补造历史锚。

Tcl实际只有open_checkpoint和查询/报告，没有opt/place/physopt/route、约束更改、write_checkpoint或bitstream。几何查询必须native PLACED_FULLY为true；route状态只是记录，不因此签physical PASS。scope准确匹配为1才查，缺失记UNAVAILABLE；收集错误保留ERROR文件并标DIAGNOSTICS_PARTIAL，原生收集完成标记/工件缺失则FAIL。结果始终`physical_acceptance=NOT_ASSIGNED`，不会把DIAGNOSTICS_COLLECTED或PARTIAL伪装成物理通过。

对象与统计范围静态核查：selected_names先重新get_cells成原生集合；get_sites/get_cells、timing_path集合直接传给原生查询，未见前期将对象转普通字符串列表后传-of_objects的确定性问题。SLICE容量来自每SLR实际sites，occupied为mapped primitive关联的去重SLICE sites；不采用LUT/8估算，不包含纯routing占用的保证，父子scope/site可共享而不能相加。该SLR→sites查询形式在既有E004原生成功脚本中有先例；当前新查询仍须实际Vivado执行取证，CPU测试不证明其返回值。

跨SLR路径为max/min × worst/negative四桶；每桶sort_by slack、max_paths100、nworst1并检查返回<=100，总计最多400个**返回样本**，桶间可能重叠，不是400条不同路径或全量违例。每行full_population=NO，NO_MATCH仅表示本查询无返回；report_slr_crossing的最多40条网明细不能用作全体跨界网总数。congestion最低level3报告及旧clock-region占用均保留原生范围，不把低于阈值/无窗口等同零拥塞。

三项本轮问题当前源码已修，未发现新增阻断；无需再经逐项批准才能按既有授权执行后续只读取证。**NOT_RUN：本代理测试/EDA、实际SLR诊断、routed生成期观察及最终物理验收。** 当前route状态或拥塞不在本次审核内；后继仅依据实际来源锚与原生结果作有限判断，不因CPU PASS提前宣称SLR改善。

### AT004代表拥塞窗口小增量复核

2026-10-24，仅复核相对AT003新增的最后Congestion Report解析、窗口TSV冻结与原生区域查询，不重复已验来源门/400路径样本范围。[AT004_cpu](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R005/preparation/AT004_cpu/result.json)原始24项unittest、Python编译及Tcl completeness均rc0；三份日志SHA、六份当前源及source_snapshot SHA逐项一致。本代理未重跑测试。当前runner SHA `6b63d2d6bd3409979f774a7754855730f013d26e9336af4fb58c942280c67238`，Tcl SHA `aabd5478b9cd28a58436d381f5460f42517826e105370000e99c99a9c99404a5`。

解析从父原生日志最后一次`Congestion Report`开始，保留报告字节偏移/长度/SHA，按既定类别方向顺序选每类首窗，去重且最多4窗；这只是代表样本，不是全量热点或按严重性计算的全局Top4。只读对照当前正在运行的原生日志，标题/方向/INT角点格式符合解析；这次阅读不构成最终窗口冻结，实际诊断仍须先满足父自然终态门。选中TSV纳入诊断输入hash，父完整日志也受原来源hash保护；CPU不推断tile到SLR的几何关系。

新增原生链为`get_tiles`→`get_slrs/get_clock_regions`→按原生clock_region坐标的包围矩形重新`get_clock_regions`→`get_cells/get_slrs`。安装Vivado2025.2手册`get_slrs:67–73`、`get_clock_regions:69–77`及`get_cells:98–105`明确支持这些对象类型；传入-of_objects的是get_*返回集合，名称列表只用于重新查询原生对象，未见前期普通字符串列表冒充对象的问题。无法解析角点记UNAVAILABLE，查询异常记ERROR/PARTIAL；当前仍未实际执行Vivado查询，CPU PASS不证明原生返回值。

资源和8个scope计数覆盖**代表INT窗口所包围的clock_region矩形**，包括该范围内全部可返回的已布局单元；不是精确INT矩形内资源，不是拥塞网/失败网数量，也不是单元导致拥塞的因果证据。原INT角点、原生SLR、实际clock_region集合均输出，父子scope及重叠区域不可求和。无窗口/零匹配不解释为零拥塞。

**阶段边界：**窗口来自父终态日志最后的拥塞报告，空间占用来自被选中DCP的实际`source_stage`。若失败route后只保存了physopt（或placed）DCP，二者结合仅用于候选空间定位；不能称该早期DCP自产生了失败route热点，不能推出失败route网的driver归属、资源冲突原因或本次改善量。需要具体driver结论时另依实际可用网/路由证据，不由包围区域的单元数量反推。

本增量**有限静态接受，未见新增阻断；原生诊断与物理验收仍NOT_RUN**。只更新本人文档，无EDA、冻结工程改动或新增审批停点，当前route继续。

## 第十一次有界分析：仍拥塞是否来自调度

2026-10-24，响应用户追问，只读当前RTL和本轮已有physopt日志，不启动EDA或改变冻结输入。**结论需分层：任务执行顺序尚无证据是根因；调度器内部宽FIFO的指针/写使能、共享核广播/归约与宽结果汇聚则是真实物理连接，其中部分本轮已有高扇出证据。** 不能将二者笼统称为“调度问题”，也不能由资源占比推算拥塞贡献。

**当轮实测证据。** [当前impl console](../../vivado/reports/m006_linear_AT001_impl/console.log:686)的686–696行，Physopt32-1132报告GU `request_wr_ptr_r[0/1]`、gather控制，以及双branch的ingress指针/down/weight控制，原扇出1968–2076。日志中124–136是受timing constraint或macro primitive限制后可参与该优化的loads，不是这些网实际已降至该扇出。后面6候选/141新instance也不能证明所有上述网络已本地化。这是本轮真实控制网络压力，尚未证明它们占全局拥塞的多少。新GU [request FIFO](../../rtl/mlp/hap_mlp_linear_gate_up_scheduler16_s24.sv:211)在419–430行用同一write pointer寻址1536bit权重、168bit metadata及事务tag；双branch [ingress](../../rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s54.sv:962)也用共同write pointer维护2304bit S9 activation、1536bit weight及metadata/tag。此处branch activation是8×32×9=2304bit，不是外部U8格式的2048bit。

**时间复用没有删除保留的空间连接。** [linear compute](../../rtl/mlp/hap_mlp_linear_compute16_s54.sv:508)以P_GATE_RUN/P_DOWN_RUN选择同一核；526–539行对activation、weight、code/shift和mask作宽mux。它已经避免另建GU与Down两套乘法阵列，但两个8×12 branch仍同时接收同一事务，见[shared parent](../../rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s54.sv:118)及147/183两个实例。生产parent payload为6560bit，包括4608bit S9 activation、1536bit weight和metadata/tag；activation按8行拆到两侧，1536bit权重及其metadata同时送两侧。GU返回16×12×24=4608bit，Down返回16×12×32=6144bit。插空拍或改任务先后不使这些静态连线、mux、FIFO与寄存器消失；若要靠时分减少它们，必须改变物理并行度/缓存组织/边界宽度，而非只延迟START。

**空间核内仍有广播和LUT归约。** [8×12 slice](../../rtl/mlp/hap_a8w4_slice8x12_group_s37.sv:108)生成8行×6个双列lane；同一行activation及其code/shift进入6lane，某列对weight及其code/shift进入8行。每lane同时处理32个K元素，单branch1536 DSP、双branch3072 DSP；[pack2 reduction](../../rtl/mlp/hap_a8w4_group32_pack2_s17.sv:3)明确将归约加法放在LUT/carry中，98–170行仍是32叶→16→8→4→2→1流水树。ScaleCode恢复与shift对齐也保留于线性计算内部，不能把删SwiGLU等同于删掉乘法后的全部LUT通路。共享核当前392384 LUT的实测占用说明规模，不能拿它的占比当拥塞占比。

**累加、metadata与结果汇聚仍存在。** 每branch [Gate S44与Down S54累加器](../../rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s54.sv:1085)同时实例化，按mode选择接收；Down是96lane、342tile、448group，每lane独立S54 BRAM bank及读改写/舍入饱和，见[Down accumulator](../../rtl/mlp/hap_mlp_down_group_major_accum_s54.sv:161)和214–233行。只让GU/Down交替并不会让两个累加器自动合并。Down中央[12→16重排](../../rtl/mlp/hap_mlp_projection_repack12_to16_s32_history2.sv:105)从6144bit到8192bit，每输入bit保留SRL history；当前input_fire仍到各history CE，输出已逐row分组，179–200行的pass选择/汇聚仍要布线。MLP metadata AB银行仍按完整矩阵配置，见[production](../../rtl/integration/hap_attention_mlp_production_core_linear.sv:186)和197行；672 URAM是实际占用，不等价于672份跨SLR广播。Attention与双DDR连接仍在，不能把整板所有热点归给MLP。

**控制已有缓解，不能一概归罪于START/ready。** START/command_fire主要在[compute FSM](../../rtl/mlp/hap_mlp_linear_compute16_s54.sv:584)锁存命令并切换状态，不是直接给3072 DSP发一根启动线。parent credit由两项FIFO occupancy决定；branch ingress、Gate slot、Down两项队列和lane guard FIFO已隔断多级组合ready，见[shared](../../rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s54.sv:82)、1017–1058行。clear已在947–960行分为每branch十二个本地域；[slice](../../rtl/mlp/hap_a8w4_slice8x12_group_s37.sv:80)以lane0拥有输入credit、逐row拥有输出capture。因此可以确认还有宽capture/control广播，不能未经网表查询称存在一条从DMA直达全部乘法叶的未断开ready链，或将clear/start直接列为当前最高扇出网。

**布局适配候选。** 当前[mlp_linear_physical.xdc](../../vivado/constraints/mlp_linear_physical.xdc:1)只有三行注释，没有给新branch/locality设手工pblock；shared中“outer SLR”是继承注释，不是当前实际位置证据。与此同时，[旧M003 CE分组](../../rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s54.sv:822)仍按旧native-CR bit grouping生成42个head和39个tail DONT_TOUCH LUT1，在新图中是否依然局部、是否限制本可有益的重整，值得核查。它们也可能仍有益；仅看到旧分组或没有pblock不能断言主因，更不能直接删保护或照搬旧分区。

按现有证据优先做以下可证伪区分，均复用当前终态后既定有限取证，不增加本轮运行输入或审批门：

1. **已知宽控制的物理扩散。** 先看本轮已报1968–2076 fanout的GU FIFO/双branch ingress：实际load的SLR/clock_region分布、网延迟、是否落在最终热点、复制后的真实分组。如果它们已局部且不进入冲突/长路径集合，则降低其优先级；仅一条高扇出日志还不足以证明全局根因。
2. **保留数据网络和硬资源邻近性。** 对同一scope区分parent→branch宽payload、branch内归约/Down bank、6144→8192重排及Attention/DDR/meta。若当前实际crossing/冲突集中在Attention或DDR，而MLP边界已局部，则不能继续沿“MLP调度”单线归因。失败route日志热点加physopt包围区域人数只能筛选候选，不能代替失败网driver证据。
3. **新布局与继承控制分组是否相容。** 看42/39组CE的实际driver/load区域与保留约束/宏限制，区分“打包和硬资源分布挤压”与“控制分组失配”；只有实际位置/连线支持时，下一轮才考虑局部buffer组织/控制banking或单变量分区实验。单纯降低任务并发应主要改变运行活动/吞吐，不能作为静态route减压的充分方案。

本轮事实支持优先怀疑**宽FIFO控制与保留并行核的物理组织**，而非认定数值/命令调度逻辑错误。当前严重拥塞的主导网、跨SLR贡献与最终改善量仍待实际物理证据；没有将旧E011 driver排名、当前LUT占比或中间overlap计数当成本轮根因证明。

## 第十二次有界设计：GU-only下一版，Down移Host

2026-10-24，Root转达用户方向后形成[design §10](design.md#10-下一版gu-onlyplanned方案down移host)及[abi_gu_only_draft.json](abi_gu_only_draft.json)。状态为**PLANNED_NOT_IMPLEMENTED_NOT_FROZEN**；本轮只读归因和文档/机器草案，不实现RTL/Host、不跑测试/EDA。当前abi.json写前后SHA均`6fc3662574ef951c30883bb2415292fe4d49de812bcb83947a91691080eb7633`，新草案不被当前104输入或R005选中，历史FAIL及已有阶段证据不变。

DDR问题已沿当前constructor:576–589、production dedicated-reader实例:434及其源头:3核对：Attention两逻辑half和tensor到物理DDR0；MLP两half、tensor/metadata到DDR1。另读A022的[实际生成BD边CPU记录](../../../E013_mlp_linear_only_hardware/experiment_source/gu_only/ddr_binding.json)，六条接口边与源码一致；该记录是CPU解析，不是新上板证明。`ddr0/1`出现在MLP旧权重基址名中是half编号，不改变专属物理DDR选择。FPGA内部INT/SLL、站点与硬资源连接仍共享，静态route overlap不是运行时DDR地址/仲裁冲突。

当前正式AT004分层报告的不重叠Down对象：scheduler13947 LUT/16880 FF/1DSP（含8290 LUT的S32 repack）；两S54 accum合计41830/16038/192RAMB36；两输出队列3230/12356；两Down metadata bank1461/2124/224URAM。合计**60468 LUT、47398 FF、192 RAMB36、224 URAM、1 DSP**。这是可裁对象的当前占用，不能称新综合净差；共享3072DSP保留。cache448→128确定逻辑bit少71.43%，但280bit宽端口与primitive粒度使64BRAM36未必减少。S45/Down模式的进一步裁剪待GU37bit专化和逐位回归，额外资源收益未知。

有限读取正在收集的R005原生[crossing_global.rpt](../../vivado/reports/m006_slr_AT001_physopt_slr/crossing_global.rpt:118)：Down repack input_fire6185 fanout分布SLR1/2=3113/3072，tensor output_error118_out8196=4100/4096；保留GU tag6149/6148和GU repack input_fire4650亦跨SLR1/2。该已出报告能证明当前保存Physopt的宽控制范围，为静态删除Down数据通路提供具体动机；不是整个R005终态验收、最终失败route归因或成功预测。未为方案等待剩余查询，也没有新增EDA。

下一版计划保留Attention、GU双8×12、全部32层及原权重/format05模型数学。Host完成原SiLU/H32/A8后，用原Down W4/ScaleCode执行S17 dot→S33 raw→S45 guard→448组S54→末端舍入饱和S32；独立Python整数oracle与blocked int64实现对照，禁止FP32替代或重新量化。每cohort约0.94G整数MAC，CPU延迟/吞吐未测；每cohort省Down上传+下载520192 B不能直接换算端到端加速。

机器草案明确v7/linear0x4D4C0002/caps0x1D，仅GU opcode1；DOWN准入BAD_OPCODE零副作用。544bit布局保留而Down基址字保留0；metadata只GU A/B每bank229376条、7340032 B；epoch只绑定GU，FPGA层租约与Host Down不可变权重/中间buffer租约分开。计划顺序为新图/G0、Host数值G1并行Down静态裁剪G2、GU37bit专化G3、真实系统整合G4、全新物理证据G5；普通修复不逐项审批。细节及责任在design §10，已交Root/A022。**NOT_RUN：GU-only RTL、Host Down实现/数值回归、性能、综合及route。**

## 第十三次交付：独立GU-only完整方案

用户明确要求删除FPGA Down并重新规划。已完成[ScaleLLM_MLP_Gate_Up_Only_Dual_DDR_Design.md](../../../../PRO_plan/ScaleLLM_MLP_Gate_Up_Only_Dual_DDR_Design.md)，版本GU-only v1.0-draft.2、PLANNED，读者无需旧方案即可理解DDR分工、全模型Host Down、精确数值、静态裁剪、数据/ABI/epoch/租约、资源/吞吐、SLR和验收。原GU+Down方案不动，当前abi.json身份未变；本次没有生产实现或EDA。

相对第十二次，明确G4R硬件与G4H Host系统分开，G5依赖G4R，不等Host32层/吞吐；首次删Down/GU专化A版与后续locality B版分开取证。SLR按新GU-only综合轻量预算，不固定迁区或照搬旧CE分组。标量oracle只跑有界输出/fullK/边界，完整生产shape采用高效独立整数参考，避免每次回归安排0.94G MAC纯Python全量运算。

机器草案revision2同步新增完整32bit opcode及原优先级、cache128计数/先验址后截位、weight metadata末4 B硬件验证与故障边界、实际GU37bit裁剪要求。正文GU input+output总量已核为**1,449,984 B**；Down每cohort MAC、metadata字节与不重叠资源小计复算一致。已有测试只按依赖复用，新控制/cache/metadata/37bit核仍须实际回归；Attention源/BD身份不当并发功能证明。所有实现、性能、GU-only综合/route仍NOT_RUN。Root/A022已获完整方案路径，后续按明确所有权连续实施。

## 第十四次收束：授权实施与完整schema冻结

2026-10-24，用户明确“可以开始进行”。独立方案更新为GU-only v1.0，状态**AUTHORIZED_FOR_IMPLEMENTATION**；冻结完整[abi_gu_only.json](abi_gu_only.json)，SHA256 `318cf64064354aed52943fd21909aa8b67f11ca8fb565a37c65441d522d4938a`。该文件展开94个CSR、39个错误码和17word/544bit descriptor，包含有效v7覆盖及GU-only通道/模块/metadata/epoch规则，可以供新生成器直接消费。draft只保留历史并标superseded；当前v6 abi.json SHA未变，不修改R005输入。本次静态核schema计数、地址唯一/对齐、descriptor位覆盖及v7身份；没有执行RTL/Host回归或EDA。

padding故障按保守既有全局MLP fatal语义明确：目标加载bank失效且禁止commit，active bank字节/generation/选择不因inactive加载失败直接改变；但阻新准入、撤销epoch资格、升级reset_required。没有accepted GU不得由配置或陈旧descriptor伪造DONE；真实active GU保留首错并冻结其失败DONE；已有未ACK DONE保持身份/首错/计数，仅升级reset_required，同拍fatal拒绝ACK。已接受AXI仍真实排空，受控恢复后重新加载/commit及新epoch。此澄清不取消owner失败响应。

A版允许删除mode/tile后按原字段bit位置重映射旧CE分组，保留FIFO和atomic fork/join协议，并核完整payload位覆盖；不将其视为旧SLR位置保证，不要求同时做B版locality重构。PRO方案/design§10引用已统一；完整schema路径/SHA及关键故障规则已交Root/A022。**实施已授权，GU-only功能/Host数值/新综合/物理/性能验收仍NOT_RUN。** 本代理完成合同交付并释放活跃槽，阶段结果再复用审核。

## 第十五次审核：GU-only G1与G4R已完成部分

2026-10-24 UTC，A021按当前授权只读核查新GU-only实现及原始证据，未运行测试/EDA、未改生产文件或冻结ABI。本次最终结论为 **G1_SYNTHETIC_LIMITED_PASS / G2_G3_MODULE_LIMITED_PASS / G4R_LIMITED_PASS**，依据下方AT019/023/024/026的新增终态闭合。具备既定G5入口资格，可连续推进新constructor/综合/物理，不等待G4H真实模型32层；不是G5完成或物理PASS。主方案和完整v7 schema保持不变；R004旧图FAIL、R005范围收束PARTIAL不作为新图成功证据，也不恢复旧诊断。

**已完成RTL证据。** 逐项读取R006下`result.json`/`inputs.json`/原生`xsim.log`及有关TB；AT004、006、007、012、013、016、018各六步骤均native0、stop=null、owned_survivors=[]，原生日志含SIM_PASS。独立重算全部输入SHA与当前文件一致，数量分别16/8/8/29/8/10/11；没有将旧版PASS直接迁移到新代码。

| R006 attempt | 本次限定接受范围 | 不外推范围 |
| --- | --- | --- |
| [AT004_lane_equivalence](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R006/attempts/AT004_lane_equivalence/result.json) | 新旧GU lane每拍ready/valid/计数/错误及保持输出相等，512向量与独立Python整数gold，另48次在途输入后clear；code1/127/128/255/zero、总shift边界与126、不舍入算术右移 | 非全数值穷举或物理收窄证明 |
| [AT006_cache](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R006/attempts/AT006_cache/result.json)、[AT007_parser](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R006/attempts/AT007_parser/result.json) | 完整128组/256次重放、group128/256拒绝无地址别名；坏记录5类、已提交prefix、末记录背压和全discard | 不声称cache BRAM按逻辑容量同比下降 |
| [AT012_compute](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R006/attempts/AT012_compute/result.json) | 真实双8×12、N128/fullK128、16row、4096 S24值；16输出/2048 metadata/2816内部事务，真实异步权重reader与输出停顿 | 不是N14336性能或完整模型；ingress逐k辅助检查仅前128次row0/col0，完整输出比较另覆盖全部4096值 |
| [AT013_job_control](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R006/attempts/AT013_job_control/result.json) | U32 opcode2/0x101拒绝无副作用、四GU同epoch、保留零base、ABORT/首错/timeout/late fatal/ACK/owner和inclusive计数 | quiescent为单位输入，不替代真实自然排空 |
| [AT016_tensor_dma](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R006/attempts/AT016_tensor_dma/result.json) | 完整73728B输入和1792记录输出，4KiB分界、背压、最后B屏障、R/B错误、非法Down/长度不发AXI | 不替代全production故障或真实PCIe |
| [AT018_metadata](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R006/attempts/AT018_metadata/result.json) | loader/resident/scheduler真实32条；padding第7条错只提交7条，后续整命令drain；active bank身份/字节保留、64条有序读及安全clear | 不替代active GU owner失败DONE、held DONE保持及全局恢复整合 |

AT012的gold由`model/generate_mlp_linear_compute_vectors.py`独立Python整数公式生成，读取所有128×32乘加，row/column code与shift、group/k的activation/W4均变化，不读取DUT输出或counter生成预期；与TB的4096坐标映射相符。AT004另有独立generator/manifest/hash，其oracle不导入RTL或实现助手。新lane实际`guard*_mem[36:0]`、U7 shift相加及37bit符号扩展后移位已核；shared/slice仅GU S44路径，旧Down源保留作历史但不在新生产选择图中。

**G1及Host运行支撑。** 独立核[Host README](../../../E013_mlp_linear_only_hardware/experiment_results/host_gu_only/README.md)所指两次原始manifest、unittest日志和所有输出SHA：`AT_20261024T153221518972Z`为26项/8.697s，`AT_20261024T154353319434Z`为16项/7.390s，均native0/无stop/运行输入未变。前者所有当前输入SHA一致；后者仅backend模块顶端地址说明docstring修改，独立AST去顶端docstring后完全一致，原测试快照保留。42是两次证据合计，不声称一轮42测试或重复执行。

`scalellm_mlp_gu_only.py`按S17 dot→S33 raw→逐组S45对齐→K448 S54累加→一次half-away右移8/饱和S32实现；int64最坏中间界低于2^53，无FP32 GEMM或提前投影舍入。生产16×4096合成输出65536值与不同遍历/einsum/floor-div参考一致，224坐标另对Python大整数fullK oracle；负数右移、code/shift、溢出与饱和边界独立覆盖。原exporter `_write_mlp_tile`实际生成fullK448/32列record后解码验证，避免仅自造packer与decoder互相印证。SiLU ROM SHA `8263e8981b637b00143c6dfd6674f2397a73c85c6ed8934f0ee839f76db6ea67`、既有Host预处理及原exporter身份绑定；没有第二次RMSNorm。实测1.735678s是一次冷的合成全shape Down运算，解码0.303939s另列，不含SiLU/H32/A8/I/O，不能称真实模型吞吐。

strict schema2/v5或schema3/W4F5工件身份与运行v7分离，exact fields/size/path/order/hash保留；`verify_hashes=False`只用于catalog读取，实际Down取字节仍重新验SHA。Down数组为bytes-backed不可写并绑定layer。pipeline先复制GU输出，匹配ACK并检查backend quiescent后释放FPGA层租约，Host权重/中间buffer直到CPU Down和residual消费者结束才释放；下一层有明确依赖。实际adapter调用既有XdmaSession方法，DDR1 aperture只加一次，START后有ordered ADMISSION_ERROR读取，故障保留pending/lease不擅自ACK或clear。16项adapter测试使用fake transport，不能证明真实BAR SLVERR传播、PCIe/AXI或Attention并发。

**首次读取时的待补状态（已由下方增量闭合）。** 当时AT019的93个冻结输入仍与当前一致、已有四个正常GU逐值通过日志，但无总result/SIM_PASS；没有据中间输出判整合通过。独立CSR、真实production metadata fault（idle/held DONE/active GU、实际drain/维护重试）及完整生产shape TB当时均待原生终态。AT014仍仅全生产xvlog，不改标为elaboration通过。G4R按合同以有界真实N128/fullK128、完整生产elaboration及已有生产全长度模块证据闭合，不新增FullN×32层仿真门。

**同次审核终态增量一（AT019/023）。** 随后[AT019_production_integration](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R006/attempts/AT019_production_integration/result.json)已自然PASS：222035 checks、112509 core cycles、262144 metadata B、2次维护、23次job_clear，XSim1413.486s；六步骤均native0/stop=null/0 survivor，93项当前输入SHA无变化。实际新production N128/K128完成两cohort四GU复用epoch、坏REC第7组prefix及全输入drain后重试、ABORT完成真实计算/传输后维护、首BRESP失败停止新AW并discard剩余计算/排空/维护/保留DONE与ADMISSION_ERROR再ACK重载，以及物理DDR1 RLAST错误保持global_freeze且soft-clear无效、core reset后重试。共八个完整GU（含ABORT任务）逐W字节与gold对照；64行/8192个唯一GU预期值与冻结Python生成物逐行完全一致，gold生成来源与六件工件SHA仍绑定。Attention实际存在且保持idle，只接受正常MLP不误清/不向Attention发流量，不扩为Attention并发功能。

[AT023_csr](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R006/attempts/AT023_csr/result.json)亦自然PASS：4155 checks/594 writes/5 submit/3 epoch/2 ACK/2 abort；六步骤0/null/无残留，8项当前输入SHA一致。实测真实v7 CSR，16种WSTRB×每字节非零的独立真值表核0x134/0x138/0x170 merge后保留零；Down RO恒零、RO/未知/非对齐拒绝、AW/W独立握手与B/R保持、完整544bit/U32 opcode传递、等待job结果再回B、首ADMISSION_ERROR及DONE投影均覆盖。job结果/DONE输入为显式mock，因此该测试不替代AT019/024的owner/排空。保留AT014 syntax-only边界；当前只余AT024真实metadata fault与AT025完整生产elaboration终态待补。原生产GU scheduler在R001/AT005完整shape PASS中的源码SHA `cddead1e7c28980999bdab64fc1ed29f55eabbb0aa8828c0282127ab80ce9faf`与当前一致，仅在其既有模块范围复用，不把旧集成PASS迁移至新图。

**同次审核终态增量二（AT024）。** [AT024_metadata_fault](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R006/attempts/AT024_metadata_fault/result.json)六步骤均native0/stop=null/0 survivor、93项当前SHA一致，原生SIM_PASS；N32/fullK128真实production，共22409 cycles，XSim137.703s。合法inactive加载512×32B后，对新的inactive加载第7条注入非零padding：实际读完16384B，只提交7条prefix；active bank身份/generation及第0/7/511条代表字节保持（不是全bank逐字节穷举）。三个独立状态均通过：idle不造DONE/job_clear并阻准入；held成功DONE内容不改、只升级reset_required且拒ACK；active GU保留真实owner61、失败码0x2120、撤epoch、拒ACK。三次恢复均经现有真实compute/weight/metadata/tensor transport安全条件触发维护，再保留快照/ACK并重载；最终新epoch12的GU62按独立gold逐W字节通过，无force或内部状态注入。该证据闭合§10的metadata padding owner语义；只剩AT025完整生产elaboration终态，不扩展故障种类或全N长仿真。

**生产形状尝试失败保留（AT025）。** AT025虽xvlog/xelab/xsim各native0，但XSim time0实际Fatal `actual production compute parameters`，无SIM_PASS，runner正确记FAIL。独立核TB第105行已设N14336/HIDDEN4096，却残留`ENFORCE_PRODUCTION_SHAPE(0)`；第501行要求实际值1，故断言正确暴露测试实例配置遗漏。生产board wrapper/三层默认1未因此改变，不是新的小shape生产图。已交A022仅修测试开关为1后新attempt，保留原FAIL及所有断言，不重新执行未受影响的模块/Host/整合测试；G4R在补测终态前保持PENDING。

**同次审核最终闭合（AT026）。** [AT026_production_shape](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R006/attempts/AT026_production_shape/result.json)于2026-10-24T16:20:29.984241Z自然PASS，六步骤native0/stop=null/0 survivor，87项当前输入SHA一致；原生日志有`GU_PRODUCTION_ELAB`、唯一SIM_PASS、960ns正常结束。与AT025冻结快照逐行比较，仅TB实例`ENFORCE_PRODUCTION_SHAPE(0)`改为1，生产RTL及全部断言未变。实际展开验证N14336/K128/enforce1、16个cache row均128×280bit、两个GU metadata bank的229376深度及72/8bit代表宽域、两branch代表lane的37bit guard存储、job/tensor1792及loader/scheduler229376派生计数，以及复位后v7/linear ID/caps和无任务健康状态。它验证完整生产图的展开/参数/存储及复位，不宣称全N计算或吞吐实测；全部96lane的原生综合网表宽度及硬资源数继续由G5检查。AT025原FAIL不改标。

AT019真实N128/K128完整输出/故障恢复、AT023实际CSR、AT024真实metadata owner三状态恢复、AT026完整生产展开，加上本次先前已接受的GU37bit/输入/生产全长度DMA及按精确源码复用的全shape GU scheduler，共同满足主方案G4R约定。**G4R_LIMITED_PASS，无当前阶段实质阻断。** G5可沿原授权连续运行，Host真实模型工件/完整应用链及性能仍按G1/G4H未完成范围推进；新综合结构与净资源、placed/route/时序/DRC/完整CDC仍需各自真实证据。该结论已实际通知Root/A022，不新增逐次审批门。本轮完成，后续只审新增G5工件，不重复已闭合模块/Host/功能范围。

新版入口静态绑定默认14336/4096/K128/enforce1、1792输出/229376 metadata、cache128；生产选择图有95个唯一模块、44 Attention源保持，新schema隔离生成CSR/Host ABI。R007入口CPU检查和独立重生成仅属于CPU资格，不冒称Vivado构造已通过。实际新综合必须输出Down专属层次缺席、GU3072 DSP/metadata448 URAM/96lane guard37结构及新资源报告；本次指出原探针只采一lane，A022已在未运行入口改逐lane检查并提交`AT004_all_lane_probe_cpu`，原生对象查询仍NOT_RUN。

G5不等待完整Host32层链或CPU吞吐，但必须消费本版G4R及新生产源身份，不能继承v6语义变化前DCP。旧R004六CDC-10与另两条XDMA user_reset→d0/d1 gate arststage CLR的CDC-11仍需新版实际报告/结构及复位合同分类；六链24级探针不自动覆盖后两条，不无来源waive。pre-opt/未布局报告与最终route/setup/hold/unconstrained/DRC/CDC各自判据分开。**NOT_RUN/未接受：真实32层模型工件与应用链、Attention并发、真实PCIe/板卡、GU-only constructor/综合/物理、净资源/SLR改善、端到端性能。** 已交Root/A022现阶段结论，普通修复和已授权运行连续，无逐项批准门。

## 第十六次审核准备：GU-only与v6同阶段资源比较

本节已在下方补入正式整板终态、质量审核及AT011同DCP资格增量；起始记录保留当时状态。最新结论为 **SYNTH_STRUCTURE_QUALIFICATION_LIMITED_PASS / AT007_AND_AT009_FAIL_PRESERVED**，不是G5物理通过。

2026-10-25本地，G4R已闭合，A022正执行R007/AT007新综合。本轮先只读核已完成core OOC，**CORE_SYNTH_RESOURCE_OBSERVED / TOP_SYNTH_PENDING**；整板/native identity/clock/质量终态未齐，不签新整板综合或物理PASS。当前AT007 `input_manifest.json` SHA256 `87a98e40d56c3a767085d2865c52f582ea681e754092fc80967265732b008ae4`，102项冻结依赖、80个selected HDL与当前输入无变化；这只是本次观察时一致，最终仍以run收尾的输入/进程/receipt为准。

已读两个正式`*_core_0_utilization_synth.rpt`：同Vivado2025.2 Build6299465、器件xcvu9p-flga2104-2L-e、Design=`scalellm_vcu118_f05_bd_core_0`、Design State=`Synthesized`。LUT采用report的CLB LUTs（含LUTRAM/SRL且按工具合并口径），BRAM采用Block RAM Tile，不把raw primitive LUT、OOC core和整板、synth和placed混减。

| core OOC同阶段 | v6 GU+Down | GU-only v7 | 减少 | 相对v6 |
| --- | ---: | ---: | ---: | ---: |
| CLB LUT | 679798 | 593717 | 86081 | 12.6627% |
| FF | 817705 | 756043 | 61662 | 7.5409% |
| BRAM tile | 734 | 542 | 192 | 26.1580% |
| URAM | 752 | 528 | 224 | 29.7872% |
| DSP | 5369 | 5368 | 1 | 0.0186% |

来源：[v6 core原报告](../../vivado/project/m006_linear_AT003_constructor/scalellm_vcu118_f05.runs/scalellm_vcu118_f05_bd_core_0_synth_1/scalellm_vcu118_f05_bd_core_0_utilization_synth.rpt)（SHA `6466d081d5f28a161f4b5b5c4e08707fdaa96466ebc214a29e3e0dcc86c794c3`）；[新GU-only core原报告](../../vivado/project/m006_gu_AT006_constructor/scalellm_vcu118_f05.runs/scalellm_vcu118_f05_bd_core_0_synth_1/scalellm_vcu118_f05_bd_core_0_utilization_synth.rpt)（SHA `a8bdf93f4235de95a1a018e9869fdbb1bbe4134fe6615e450fdfbf4b0d87ba57`）。新core原生日志最终总计为890 Infos/314 Warnings/0 Critical/0 Errors；568 warnings属于较早“Synthesis finished”阶段行，不当最终warning总数。已生成core DCP147880832 B，SHA `4075c5cc6ad53ed374e1f97deb9b59fffd936c0f528775a36fc98673c9c60a4c`；它不是最终整板DCP。

BRAM192、URAM224、DSP1的变化与删Down专属S54 accumulator/metadata/scheduler的计划口径吻合；GU共享乘法阵列继续保留，因此不预期共享3072 DSP按Down比例减少。LUT/FF净差包含GU37bit收窄、控制/数据路径移除及重新映射，不能把全部额外差值单独归因于某一模块。core的Unique Control Sets18524→18180、CARRY8 50182→44119也是综合统计，不代表SLR站点/拥塞改善。cache128的实际BRAM收益仍不能由逻辑深度比例推定。

正式整板比较基线固定为[旧v6 AT004 Synthesized层次报告](../../vivado/reports/m006_linear_AT004_synth/utilization_hierarchical.rpt)：766078 LUT/954137 FF/835 BRAM tile/752 URAM/5375 DSP。等新整板同阶段报告到齐后再填新数与层次对账，不以core差值外推整板，也不拿旧R004 Physopt/failed-route数据作同阶段面积基线。

后续一次集中审核消费AT007真实终态与成功身份链、实际GU96lane逐lane guard37/3072 DSP/448 GU metadata URAM/Down层次缺席、Attention与clock身份，并区分综合中间时序/DRC/CDC与最终物理资格。当前此类新整板原生检查尚未出齐，**G5仍进行中，SLR/route改善未测得**。A022按合同连续运行，A021无EDA/生产输入修改/后代，不设置逐次批准停点。

**同次正式整板终态增量。** [AT007原result](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R007/attempts/AT007_synth/result.json)为自然FAIL：native1、stop=null、changed_inputs=[]、owned survivors=[]、peak50.096 GiB；不是资源停止。完整整板[synthesized.dcp](../../vivado/reports/m006_gu_AT007_synth/synthesized.dcp)实测194407960 B，SHA256 `783eb0faf3baf062ec72f27572a2be9a119be967e070165be79aa1486314d398`。23个综合run完成及原生报告存在，不等于整个attempt成功：末尾逐96lane guard接口查询全部返回0，使结构项及overall FAIL；该结果只说明当前查询未取得位宽，不能据此称真实guard为0bit，也不能先签37bit检查通过。A022独占修复选择器并对同一DCP做新qualification；本轮不重复调查该实现、不重综合、不等待新尝试。

原始[stage_quality.json](../../vivado/reports/m006_gu_AT007_synth/stage_quality.json)中六份报告的SHA与实际文件全部一致；其中process的NATIVE_STAGE_COMPLETED只是已完成的原生子阶段，不能覆盖原result和overall FAIL。资源比较采用同工具、器件、整板top及Synthesized状态的[新正式层次报告](../../vivado/reports/m006_gu_AT007_synth/utilization_hierarchical.rpt)（SHA `90a3e5fa11f861d59af2d521e9f263ee7b22f5f7cbe2e00ba0d969678e5bf69e`）和[旧正式报告](../../vivado/reports/m006_linear_AT004_synth/utilization_hierarchical.rpt)（SHA `69ba7cd5b8cc9f13b7131fb0e5b90872332ea4d32064eb324f19f070be125286`）；与Root维护的[整板比较JSON](../../../../results/reviews/M006_gu_only_synthesis_comparison.json)数值一致。

| 整板Synthesized | v6 GU+Down | GU-only v7 | 减少 | 相对v6 |
| --- | ---: | ---: | ---: | ---: |
| Total LUT | 766078 | 679997 | 86081 | 11.2366% |
| FF | 954137 | 892475 | 61662 | 6.4626% |
| BRAM tile | 835 | 643 | 192 | 22.9940% |
| URAM | 752 | 528 | 224 | 29.7872% |
| DSP | 5375 | 5374 | 1 | 0.0186% |

BRAM为RAMB36+RAMB18/2：827+16/2→635+16/2。整板与core净差恰相等，但表格来自两份实际整板报告，不是core外推。层次对账：shared核392384→325458 LUT、479315→446559 FF、192→0 RAMB36，DSP始终3072；metadata672→448 URAM；MLP cache4270→5737 LUT、55→48 FF、64→64 RAMB36。因primitive深度粒度，cache128没有带来BRAM净减，且自身LUT增加1467。Attention为233907→233939 LUT、272649→272660 FF，BRAM/URAM/DSP不变，属本次映射小差异；不把nested层次相加或将整板全部LUT下降归于单一裁剪。上述是同阶段实测面积变化，尚无GU-only实际SLR站点、拥塞或route改善结论。

**实际层次与clock。** [netlist_identity](../../vivado/reports/m006_gu_AT007_synth/netlist_identity.txt)原生确认真实Attention实例1、GU共享核1、禁止MLP层次0；[gu_structure](../../vivado/reports/m006_gu_AT007_synth/gu_structure_identity.txt)确认禁止Down0、MLP3072 DSP、GU metadata448 URAM及96lane数量，guard宽度仍未获有效查询。唯一黑盒为精确`dbg_hub/dbg_hub_CV`，未解析用户黑盒0，只适用pre-opt厂商debug占位。实际wrapper及[clock_identity](../../vivado/reports/m006_gu_AT007_synth/clock_identity.txt)分别核core10 ns、DDR0/DDR1各5 ns，均有真实generated clock。新旧[clock_interaction](../../vivado/reports/m006_gu_AT007_synth/clock_interaction.rpt)均显示core↔双DDR及双DDR相互关系为Asynchronous Groups；core↔XDMA是Max Delay Datapath Only，不把所有跨域一律描述为异步组，更不把例外存在等同CDC实现正确。

| 原生质量项目 | v6 AT004 synth | GU-only AT007 synth | 本次判断 |
| --- | --- | --- | --- |
| setup WNS/TNS | +0.904/0 ns | +0.904/0 ns | 当前未布局模型下无setup违例，非最终时序PASS |
| hold WHS/THS、失败端点 | −0.814/−46941.938 ns、936065 | −0.814/−44254.328 ns、877173 | 未布局hold尚需正常实现处理，不直接判最终失败或宣称改善 |
| pulse WPWS/TPWS、失败端点 | −0.012/−0.037 ns、5 | 相同 | 最终物理需复核 |
| no_clock / internal unconstrained | 530/554 | 530/554 | 精确端点集合逐名一致，均DDR校准debug |
| CDC | 6 Critical / 6198 Warning | 相同 | 6条CDC10准确路径一致，原critical保留 |
| DRC | 0 Error/Critical、15769 Warning | 0 Error/Critical、15767 Warning | 少2条对应已删Down scheduler同一DSP，非全部warning获豁免 |

**debug/时序阶段边界。** [timing_summary](../../vivado/reports/m006_gu_AT007_synth/timing_summary.rpt)中530个无clock对象全部位于双DDR校准`u_ddr_cal_top/u_ddr_cal`，各265；554个未约束内部端点同属校准，各277，均与旧版精确集合一致，clock根为`dbg_hub/sl_iport{0,1}_o[1] (HIGH)`。另外缺input delay1项为`pcie_perstn`，缺output delay2项为两DDR reset_n，不能混入debug554。既定新post-opt/pre-place门必须实际检查零黑盒、这些当前目标存续/clock及六链24级结构；旧v6 post-opt已通过不能代替新DCP结果。旧名不再存在不证明逻辑已删，clock存在也不等于完整端点约束充分；最终全局check_timing/unconstrained、setup/hold/pulse、CDC/DRC与route仍分别验收。

**CDC限定分类。** [cdc.rpt](../../vivado/reports/m006_gu_AT007_synth/cdc.rpt)的CDC3 Info434、CDC9 Info19、CDC10 Critical6、CDC15 Warning6198均与旧同阶段相同。六条Critical的准确source/destination逐行一致：双DDR`div_clk_rst_r1_reg`至`core_gate/u_ready{0,1}_cdc/arststages_ff_reg[0]/CLR`两条；d0/d1 gate末同步级至各Smartconnect`clk_map/{psr0,psr_aclk1}/.../ACT_LO_AUX/syncstages_ff_reg[0]/D`四条。前两条按既有四级XPM异步置位/同步释放复位结构理解；后四条为proc_sys_reset AUX稳定电平四级同步器及LPF/sequencer，不混称全是async reset。沿已核源结构作有限分类，不新增waiver；post-opt24级探针与最终原生CDC仍需独立证据。旧R004最终又出现的两条XDMA user_reset→d0/d1 gate CLR的CDC11未被本次综合六条或24级探针覆盖，新报告暂未列它们不能视为已修复。

**DRC与vendor诊断。** [drc.rpt](../../vivado/reports/m006_gu_AT007_synth/drc.rpt)的DPOP3为5154→5153、DPOP4为249→248；准确减少对象是旧`u_mlp/u_down_scheduler/sticky_error_r3` DSP的PREG/MREG建议。DPIP2 7263、DPREG7 3072、REQP1858 22、REQP1877 9保持。两条Constraints18-401的完整消息亦与旧相同，来自安装XPM memory Tcl条件块59行中的`*doutb*reg*`广匹配，选中两Smartconnect request FIFO的`doutb_reg[0]_i_1`组合对象，不能据此断言真实寄存器max_delay均成功或均丢失。已向A022建议把这两个精确XPM scope的合法doutb端点、对象类型/clock及有效例外覆盖核查合入既定post-opt范围；保留原警告，只有实际遗漏才修约束，不改vendor库或泛化waiver，不另建重EDA扫描。

本轮结论为**正式资源与已完成层次/clock观察有限接受；AT007 FAIL保留，DCP qualification及G5物理尚待**。没有发现需要重跑未受影响综合的证据；A022可按既有授权对同SHA DCP修复查询/新建准确来源资格，再连续执行正常opt/物理取证。本代理不重复guard选择器审核、不等待新qualification、不改活动输入或Root比较JSON；没有EDA、测试重跑、后代或新审批停点。

**同次资格增量：AT011真实37bit存储与来源闭合。** 2026-10-25本地，按Root新增委派只核[AT011_dcp_qualification](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R007/attempts/AT011_dcp_qualification/result.json)及新增身份，不重审此前资源/功能。实际native0、stop=null、changed_inputs=[]、survivors=[]、peak19.041 GiB，原生日志唯一`M006_NATIVE_STAGE_COMPLETE qualify`并自然退出。[成功资格receipt](../../vivado/reports/m006_gu_AT011_dcp_qualification/m006_gu_synth_identity.json)SHA256 `228a95690c179ef57c0dfb2bd91a7c20b466c2c1b27b865a2f28812ac2b3b712`；其30个绑定工件均独立重算SHA一致，evidence副本逐字节相同。回执包含1433项生成物身份，与本次`project_outputs.json`完全一致；本轮不重复constructor全量扫描。

本次完整DCP仍为`783eb0faf3baf062ec72f27572a2be9a119be967e070165be79aa1486314d398`，独立重算一致；六份旧分析报告和`drc_native_objects.txt`共七件均与AT007逐字节一致。当前manifest SHA `b03f1da1e352cecf634233f46122749c3ca011108ca77daa90eade6853f37d71`，102项相对AT007只有`build_mlp_gu_board.tcl`和`run_mlp_gu_board.py`两driver变化，全部当前输入SHA一致；selected HDL、默认生产shape、source membership与Attention身份相同。明确来源记录、两文件patch和收尾验证绑定原AT007失败及constructor；无RTL/IP/ROM/有效约束变更、无重新综合。原AT007、AT009 FAIL保留；新`stage_quality.overall=FAIL`仍保留未完成物理质量范围，不能改为全工程PASS。

原guard端口在rebuilt网表已改名，单纯按RTL端口名或REF_PIN_NAME查询无法测位宽。替代证据是[AT010真实core funcsim解析](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R007/attempts/AT010_guard_storage_cpu/guard_storage_netlist.json)：514556094 B原生结构Verilog，实测SHA `5ef7b4ef385d99cb6a2e6b544b48f2654016c232b7bb29ee8516c25ef8e52fe0`，与AT007生成inventory记录一致；96个lane模块定义与96个实例一一绑定，各148个FDRE，完整两组×两entry×37位。CPU解析只确定真实命名，最终由AT011对同整板DCP查询，不用CPU文本代替原生网表证据。

独立解析[guard_storage_objects.txt](../../vivado/reports/m006_gu_AT011_dcp_qualification/guard_storage_objects.txt)的全部14208条原生记录，准确集合为`branch[0..1] × row[0..7] × pair[0..5] × guard[0..1] × entry[0..1] × bit[0..36]`：96lane各148个FDRE，无重复、缺位、额外位或未知owner，guard0/1各7104。这证明真实GU guard存储已收窄到37bit，不声称被优化重建的旧端口名仍存在，也不把总FF计数当数值正确性证明；原有lane等价/完整K计算功能证据另按已审范围复用。原生[结构身份](../../vivado/reports/m006_gu_AT011_dcp_qualification/gu_structure_identity.txt)同时满足Down禁止层次0、MLP3072 DSP、metadata448 URAM、96lane/mismatches0；原阻断已闭合。

新[netlist](../../vivado/reports/m006_gu_AT011_dcp_qualification/netlist_identity.txt)和[clock](../../vivado/reports/m006_gu_AT011_dcp_qualification/clock_identity.txt)重新核真实Attention1/GU核1、用户黑盒0、仅精确pre-opt dbg_hub占位及core/DDR0/DDR1=10/5/5 ns。[constraint_identity](../../vivado/reports/m006_gu_AT011_dcp_qualification/constraint_identity.txt)与[有效XDC](../../vivado/reports/m006_gu_AT011_dcp_qualification/effective_constraints.xdc)记录两4 ns DDR主输入、10 ns PCIe主输入及include_generated_clocks三组异步关系；实际269个port均有PACKAGE_PIN，235个非空IOSTANDARD，另34个GT terminal不套普通IOSTANDARD。此为实际对象属性口径，不与此前序列化XDC中显式PACKAGE_PIN命令计数混减，也不据此宣称所有路径约束充分。

[六链24级原生记录](../../vivado/reports/m006_gu_AT011_dcp_qualification/qualification_reset_cdc_identity.txt)已逐项核：8 FDCE、16 FDRE，全部ASYNC_REG=1且有目标clock，每链索引0..3完整，18条相邻级D驱动均等于前级，24项pass=1。仅闭合既定六条复位/稳定电平路径的结构探针；不豁免原六CDC10、不覆盖旧最终额外两CDC11、不替代post-opt复查或全局CDC。pre-opt530/554、两XPM诊断/有效例外覆盖、最终setup/hold/pulse/DRC/route与SLR指标仍按前述阶段边界处理。

结论：**SYNTH_STRUCTURE_QUALIFICATION_LIMITED_PASS**，具备既定正常opt/后续物理入口资格，无本次范围新增实质阻断；不等Host32层或重跑未改功能。已通知Root/A022，A022按连续授权启动R008/AT001_impl；启动消息不算物理结果。本代理仅写已有results/design/A021，无EDA、重测、生产修改、后代或新批准门，本轮完成。

## 第十七次有界审核：GU-only真实post-opt及两XPM scope

2026-10-25本地，只读R008/AT001_impl已完成的阶段工件，未等待整轮终态或运行EDA。结论为 **POST_OPT_DEBUG_RESET_LIMITED_PASS / XPM_ENDPOINT_AND_COVERAGE_OBSERVED / XPM_REMAINDER_PENDING**。当前正在保存optimized DCP并继续既定place/route；该运行尚无最终result/stage_quality，不能签整轮物理PASS。本节文件SHA是本次读取的已出工件身份，最终仍须纳入工程收尾证据。

**来源与实际阶段。** [launch](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R008/attempts/AT001_impl/launch.json)实际绑定AT011资格receipt `228a95690c179ef57c0dfb2bd91a7c20b466c2c1b27b865a2f28812ac2b3b712`、同DCP `783eb0faf3baf062ec72f27572a2be9a119be967e070165be79aa1486314d398`和manifest `b03f1da1e352cecf634233f46122749c3ca011108ca77daa90eade6853f37d71`；本次receipt/manifest副本SHA吻合，102项当前输入均无变化。[vivado.log](../../vivado/reports/m006_gu_AT001_impl/vivado.log:331)原生明确opt_design成功，elapsed34m49s，77 Infos/113 Warnings/0 Critical/0 Errors；不把正在写出的DCP或后继阶段当作已完成结果。

**debug实际对象闭合。** [post_opt_debug_identity](../../vivado/reports/m006_gu_AT001_impl/post_opt_debug_identity.txt)黑盒0；530个原no_clock pin与554个原unconstrained endpoint均与AT011冻结reference逐名及顺序完全相同、没有重复。全部1084条记录的owner与pin所属cell一致，均有`mmcm_clkout5_1`，surviving/clocked分别530/554、removed/missing均0。本次证明这些准确旧目标已有时钟及占位黑盒消除，不宣称全部debug逻辑删除、全部端点例外充分或最终全局unconstrained为0。

**六链复位结构闭合。** [post_opt_reset_cdc_identity](../../vivado/reports/m006_gu_AT001_impl/post_opt_reset_cdc_identity.txt)与AT011原24行逐字节一致：8 FDCE、16 FDRE，六链各索引0..3、ASYNC_REG/目标clock/18条相邻D连接正确，24项pass=1。仅接受既定六条复位/稳定电平路径的post-opt结构；原六CDC10以及旧最终额外两CDC11均不因这个探针而被豁免，最终新原生CDC另判。

**两XPM request-FIFO的已出证据。** [post_opt_xpm_endpoint_identity](../../vivado/reports/m006_gu_AT001_impl/post_opt_xpm_endpoint_identity.txt)严格限定d0/d1 Smartconnect的`s00_nodes/s00_w_node/.../gen_fifo_req/.../xpm_memory_base_inst`，每个scope实际仅有1个`doutb_reg_reg[0]` FDRE和对应D endpoint，clock分别为`mmcm_clkout0`/`mmcm_clkout0_1`，missing_register_clock=0。原18-401命中的`doutb_reg[0]_i_1`仍存在且类型明确为LUT4，支持此前“过宽名字集合混入组合对象”的定位，未发现真实寄存器被误认成该LUT的证据。

[d0 coverage](../../vivado/reports/m006_gu_AT001_impl/post_opt_d0_smc_doutb_coverage_exceptions.rpt)及[d1 coverage](../../vivado/reports/m006_gu_AT001_impl/post_opt_d1_smc_doutb_coverage_exceptions.rpt)均为本次Optimized原生报告，查询`-to`准确真实FDRE；分别position662/686列出`Max Delay Datapath Only max_dpo=10`、Endpoints1、From2 pins/To2 cells、From50%/To33.33%。报告自身说明分母是例外隐式或显式指定的pin集合，故不能将50%/33.33%解释为当前各1个真实doutb寄存器有半数/三分之二漏约束。现证据支持真实目标存在并被该coverage行计入，不支持宣称全部例外冲突/忽略情况已排除或端到端时序已经通过。

本次读取时两scope的valid/ignored共四份预期报告均不存在，最终stage_quality亦未产生；因此不把调用已经返回写成COLLECTED、不把文件缺失解释为“0 ignored”，也不撤销原vendor警告。必要后续仅保全这四次调用的实际catch/状态到既定最终质量记录，按缺失保留PARTIAL/PENDING，再结合既定全局时序/CDC决定残余项；若确需补证，只限这两个既定scope，不能用笼统waiver代替。已有证据未显示必须中断正常place/route的实际缺约束错误，不新增大范围诊断或逐项批准门。

| 已读取阶段工件 | SHA256 |
| --- | --- |
| post_opt_debug_identity.txt | `742078fbbf976a07d99bf9fa4f56f8f758415bb14059463ed751c1bb86367dea` |
| post_opt_reset_cdc_identity.txt | `191832b032e033ad50f2764ad223310953f7292dc45dd322e6d1c0f25d71543f` |
| post_opt_xpm_endpoint_identity.txt | `ff1419a6454fe7bc85e43bed3a9bb3ba8020308fbd78986f0eb85abdb16dec52` |
| d0 coverage | `7578279d4472b8a19bd7d08f371143ab4cb3e99d6a1e2dc08e9bf5120485aedc` |
| d1 coverage | `8a506577334b1cf67d3475edcb246a02ced6fdc54b8a44f906be089a2b2a9779` |

Root/A022已收到有限接受和缺失项边界。SLR站点/拥塞、最终route、setup/hold/pulse、全局check_timing、DRC/CDC、两XPM残余报告和整轮收尾身份仍待后继实际证据；本轮不重读旧综合/功能、不改冻结输入、不运行EDA/测试或等待整轮结束。

## 第十八次有界归因：GU-only Placed站点压力与实际模块分布

2026-10-25本地，当前只接受 **PLACED_RESOURCE_SCOPE_AND_CONGESTION_OBSERVED**，不预判Physopt、route或拥塞改善。原生place_design成功1h37m19s、0 Error/Critical，估计WNS=+0.501 ns；同一日志仍有Place46-14 highly congested警告。保存[placed DCP来源锚](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R008/attempts/AT001_impl/placed_checkpoint_observation.json)绑定511010742 B、SHA `cc92d8dcbc90d23b358627ccc7e2ea201b864cfb3092cbc58ddb1850459fa0cb`、导出marker/日志prefix、102输入及AT011 receipt；本次独立重算DCP与prefix SHA均一致。估计WNS不是route后真实时序签收。

[当前整板report_utilization -slr](../../vivado/reports/m006_gu_AT001_impl/placed_utilization_slr.rpt)明确为Fully Placed、未加-packthru，SHA `8374b4c72c4a1071b6bb514cd7df55b09892927e543b5a4ac92adda5da011274`。以下均是本次实际站点/资源，不能把综合LUT净降11.24%直接当作同量CLB空间释放：

| 当前Placed | SLR0 | SLR1 | SLR2 |
| --- | ---: | ---: | ---: |
| 已占CLB / 49260 | 41254 / 83.75% | 48413 / 98.28% | 47851 / 97.14% |
| 剩余CLB站点 | 8006 | 847 | 1409 |
| CLB LUTs / 容量比例 | 179085 / 45.44% | 243557 / 61.80% | 234256 / 59.44% |
| CLB Registers / 容量比例 | 247397 / 31.39% | 347289 / 44.06% | 288181 / 36.56% |
| Unique Control Sets | 7568 | 9519 | 4326 |
| DSP | 1571 | 1840 | 1963 |
| URAM | 168 | 168 | 192 |
| BRAM tile | 61.5 | 203 | 378.5 |

**逻辑资源少了，站点仍可能接近满占。** SLR1/2各只使用约62%/59%的LUT槽、44%/37%的FF槽，却已触及98%/97%的CLB站点；按已占站点算平均约5.03/4.90个LUT。这直接支持“删逻辑未自动把保留网络紧密装回更少站点”，但尚不能把闲余槽全部归因于控制集。不同clock/reset/CE、carry/宏结构、LUTRAM/SRL站点类型、时序与连线局部性均可能限制合并或促使布局展开；本报告没有分解各因素贡献。SLR2的4326个control sets明显少于SLR1的9519，却同样接近满站点，进一步说明单看control set总数不能确定根因，也不能直接判任务scheduler逻辑错误。

**真实模块位置已经改变。** 四份本次同会话`-slr -cells`报告给出以下实际分布，不能沿用旧“branch1在SLR2”的位置：

| scope | LUT：SLR0 / 1 / 2 | DSP：SLR0 / 1 / 2 | 触及CLB：SLR0 / 1 / 2 |
| --- | --- | --- | --- |
| [GU branch0](../../vivado/reports/m006_gu_AT001_impl/placed_branch0_utilization_slr.rpt) | 2967 / 153954 / 0 | 32 / 1504 / 0 | 706 / 34565 / 0 |
| [GU branch1](../../vivado/reports/m006_gu_AT001_impl/placed_branch1_utilization_slr.rpt) | 157301 / 3 / 0 | 1536 / 0 / 0 | 37626 / 3 / 0 |
| [Attention](../../vivado/reports/m006_gu_AT001_impl/placed_attention_utilization_slr.rpt) | 0 / 15969 / 212532 | 0 / 336 / 1960 | 0 / 4267 / 44815 |
| [GU metadata](../../vivado/reports/m006_gu_AT001_impl/placed_metadata_utilization_slr.rpt) | 679 / 711 / 594 | 0 / 0 / 0 | 353 / 512 / 217 |

scope站点可共享，表格不能相加成互斥占用，更不能把某scope的站点占比称作拥塞贡献。可确认的是：branch1几乎全在SLR0，branch0主要在SLR1，SLR2的47851个已用站点中44815个触及Attention。故SLR2接近满载并不证明Down残留或GU控制主导；Attention与周边布线仍占很大范围。GU metadata448 URAM实际168/168/112跨三SLR，Attention另外80 URAM全在SLR2；连接仍需考虑跨域与硬资源邻近，不能把物理DDR专属解释为SLR独占。当前全局SLL为SLR0↔1的6554/37.93%、SLR1↔2的5144/29.77%，总11698；这种全局比例未满也不能排除局部INT/clock region热点。

**已有控制网络证据，尚非最终热点因果。** 本次[日志692–702行](../../vivado/reports/m006_gu_AT001_impl/vivado.log:692)实报GU request write pointer约2019–2020、branch activation CE2052、weight CE1968、branch1 ingress write pointer2057 fanout；timing/macro限制使本次VHFN可考虑loads只剩124–134左右，工具因此未将这些网纳入该轮复制。这个较小数字不是实际fanout已降到百余。另[1089–1111行](../../vivado/reports/m006_gu_AT001_impl/vivado.log:1089)22个BUFG插入候选因placement/routing conflicts全跳过，包括GU repack/branch clear及部分Attention控制；这只限本轮place候选，不能误称整个设计没有BUFG优化或所有宽网均未处理。这些直接日志支持保留GU宽FIFO/capture控制仍是B版局部性候选，不证明它们占全部拥塞或数值/命令调度错误。

**比较口径先冻结。** 旧R005 [utilization_slr](../../vivado/reports/m006_slr_AT001_physopt_slr/utilization_slr.rpt)是Physopt postPlace且带-packthru，当前为Placed且未带；两种差异均须保留。[AMD UG835 2025.2](https://docs.amd.com/r/2025.2-English/ug835-vivado-tcl-commands/report_utilization)说明-packthru加报专作route-through的LUT。旧三SLR Total LUT分别额外含12268/19182/15212，因此后续同阶段逻辑LUT采用Logic+Memory=224847/298317/217747，不直接用237115/317499/232959相减。官方这一选项说明本身不证明所有其他行完全不受口径影响。

已有无需重启EDA的旧站点证据：[slice_sites.tsv](../../vivado/reports/m006_slr_AT001_physopt_slr/slice_sites.tsv)通过原生`get_sites→get_cells→去重get_sites`直接计primitive占用，board为45040/49193/46155，恰与旧CLB行一致；这保留了独立于report flag的旧站点基线。旧R004不带flag的hierarchical报告是Routed，不能用它替换Physopt基线。当前仍不计算旧99.86%与新98.28%的“改善量”；待新Physopt真实报告后，只对明确同阶段/同定义字段比较，CLB站点口径有疑义则保留未定，不默认由面积下降推导改善。

**同批Placed局部热点已到齐。** 后续同会话[placed_congestion.rpt](../../vivado/reports/m006_gu_AT001_impl/placed_congestion.rpt)完整10924 B，SHA `bebeeed40825246d811f1cab255637ce00c7680d6c06f6815b5611436afb6bbf`，明确Fully Placed。14条代表窗中3条最高Level6的Cell Names前三项均来自Attention postprocess_store、projection right2 shard与KV quantizer：

| 当前原生代表窗 | 类型/level | 窗内已报资源 | 实际列出的主要层次 |
| --- | --- | --- | --- |
| CLEL_R_X30Y738 → DSP_X59Y800 | South Global / 6 | LUT57%、URAM100%、DSP92% | Attention postprocess_store、right2 shard、KV worker3 |
| CLEL_R_X8Y774 → BRAM_X38Y835 | North Long / 6 | LUT68%、URAM50%、DSP98% | Attention postprocess_store、right2 shard、KV worker1 |
| CLEL_R_X30Y735 → DSP_X59Y795 | South Long / 6 | LUT56%、URAM100%、DSP90% | Attention postprocess_store、right2 shard、KV worker3 |
| CLEL_R_X36Y376 → DSP_X51Y405 | East Global/Short / 5 | LUT53%、RAMB/URAM/DSP均100% | GU branch0 row1/pair2 dot、paired_weight、W4 frontend |
| CLEL_R_X31Y391 → CLEM_X46Y422 | South Global / 5 | LUT62%、RAMB/URAM均100%、DSP62% | GU branch0 row7/pair2 dot、gather、W4 frontend |

这是本轮真实布局拥塞代表区域，已能定位Attention和保留GU/权重链两类压力；与scope分布共同支持“局部硬资源邻近和保留连接仍紧”的判断。报告Cell Names中的43%等只按原生列项保留，不转成拥塞原因份额；代表窗可能重叠，也不是全部热点或失败route网driver排名。原生全SLR DSP/URAM尚有余量而具体窗达100%，说明全局资源富余不能直接解决局部区域供给；仍不足以仅凭该表区分布线需求、打包约束和控制网络的定量贡献。

B版据此只记录两个可证伪方向：保留GU宽FIFO/capture/clear控制是否需要按实际物理bank局部复制，以及Attention/GU/meta跨SLR接口与局部站点/硬资源预算是否匹配。两类实际热点均应进入预算，不能只因名为scheduler就将全局原因归给任务调度，也不能盲套旧CE组或固定迁区。本轮冻结输入不改；Root/A022已收到六份当前报告范围、位置及口径结论。phys_opt_design已按既定流程开始，后继只补新Physopt同阶段可比字段，当前不计算旧新改善量；无新EDA、重测、诊断包或批准门。

**同次Physopt增量：同阶段资源比较已闭合，route仍待。** 原生standalone phys_opt_design成功5m01s、0 Error/Critical，估计WNS=+0.465 ns/TNS0，并明确`No setup violation found. The netlist was not modified.`。[保存锚](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R008/attempts/AT001_impl/physopt_checkpoint_observation.json)绑定511009344 B DCP、SHA `5c8922a05f8ec15ad30fbc2453d2cc163b3c56b20ac52a99b67900f60b70be72`；本次独立核DCP及导出日志prefix均吻合。[六份报告观察记录](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R008/attempts/AT001_impl/physopt_pressure_reports_observation.json)绑定同manifest/DCP，各报告实际SHA均一致。五份utilization表的资源/分布数据行与Placed全部相同，原布局关系仍适用；不由此推断所有物理对象逐位置完全相同。

现在双方utilization阶段均为**Physopt postPlace**。站点采用此前已核旧独立去重`slice_sites.tsv`基线（与旧CLB行一致）对本次[原生CLB行](../../vivado/reports/m006_gu_AT001_impl/physopt_utilization_slr.rpt)，不将带-packthru的旧Total LUT直接相减：

| 已占站点 | 旧v6独立SLICE计数 | 新GU-only CLB | 新减旧 | 新剩余 / 49260 |
| --- | ---: | ---: | ---: | ---: |
| SLR0 | 45040 | 41254 | −3786 | 8006 |
| SLR1 | 49193 | 48413 | −780 | 847 |
| SLR2 | 46155 | 47851 | +1696 | 1409 |
| 全板合计 | 140388 | 137518 | −2870（−2.0443%） | 10262 |

**全板逻辑减少，站点只释放约2%，且不是各SLR均下降。** SLR1从剩67个站点变成847个，只释放780；SLR2已占站点反而增加1696。实际模块重新分布及scope站点共享见前表，不能把各SLR差值全部归给某个删除模块。按严格Logic+Memory归一化，同阶段三SLR LUT旧224847/298317/217747→新179085/243557/234256，总740911→656898、减少84013（11.3391%）。这是Physopt逻辑LUT口径，区别于正式综合Total LUT的11.2366%；两种阶段均显示逻辑数下降远大于已占站点下降，但并未分解packing/时序/连线/硬资源邻近各自贡献。

同阶段全局SLL旧SLR0↔1为8324、新6554（−1770），SLR1↔2为5493→5144（−349），合计13817→11698（−2119，−15.3362%）。这是全局跨SLR资源统计的减少，不能称局部拥塞或路由冲突同比减少；当前SLR1/2仍有很小站点余量，代表窗口仍存在局部硬资源满占。URAM从旧220/280/252变为168/168/192，反映删除Down银行并重新布局；资源释放不自动消除保留Attention/GU连接的压力。

**拥塞报告的内部阶段必须保留。** 新[physopt_congestion](../../vivado/reports/m006_gu_AT001_impl/physopt_congestion.rpt)虽在phys_opt_design之后生成，自身仍标`Fully Placed / Placer Final Level`，SHA `f6b87aaa3e91c81d1e42b909071a7cfac6b60c4dfcdc8d769b22cd6c6b62f902`；14行内容与本轮Placed表完全一致。它不是route拥塞，也不是重新计算的最终route结论。旧R005同样报告保存DCP中的Placer Final Level，但命令另带`-min_congestion_level 3`；因此旧48行→新14行不能作为热点减少比例。两边都仍出现Level6；旧最高代表窗包含Down accum/共享核及Attention，新最高代表窗主要列Attention，保留GU/权重链为Level5。只能据此说明所列代表区域和成员发生变化，不能以Cell Names百分比、级别或行数给最终因果份额。

本次结论为 **PHYSOPT_RESOURCE_COMPARISON_OBSERVED**：删Down/GU专化确有逻辑、URAM和全局SLL释放，现有布局站点压力只小幅下降且重新分配；本轮phys_opt没有提供进一步消除这些布局热点的证据。route已按既有流程开始，尚不判断成功/失败、实际overlap或最终时序/CDC。Root/A022已获具体同口径数字，本代理仅补本节/design/A021，后续只读新增route/质量结果，不新增EDA、修改冻结图或设置批准门。

## 第十九次有界预审：Route35-462字段与可选XPM报告

本次只读当前R008/AT001_impl的四组十条bus-skew告警与两个既定XPM scope的报告收集逻辑；未运行EDA、未改102项冻结输入，不提前接受route/CDC。[告警观察记录](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R008/attempts/AT001_impl/route_bus_skew_warning_observation.json)所绑定162057 B原生日志prefix的SHA `919735064e3d1de9e344754013b351452f1bdea6b6adb10c0d4c0ba01f7af500`独立复核一致；1321/1325/1329/1334行与十个完整D端点逐一吻合。以下四份RTL和build脚本当前SHA均与运行manifest `b03f1da1e352cecf634233f46122749c3ca011108ca77daa90eade6853f37d71`一致。

| 原生warning scope（每个均在`u_compute`下） | dest_hsdata位 | 实际字段与冻结生产值 | 静态来源 |
| --- | --- | --- | --- |
| `u_attention/u_weight_frontend/u_command{0,1}_cdc`，grp_84/85 | 每scope的14、16，共4条 | payload低17位`group_count`；81920=`0x14000`，恰14/16位为1 | [Attention core:337](../../rtl/attention/hap_attention_board_cohort16_core.sv#L337)、[frontend:202](../../rtl/attention/hap_dual_ddr_weight_frontend.sv#L202) |
| `u_mlp/u_w4_frontend/u_command{0,1}_cdc`，grp_86/87 | 每scope的15、16、17，共6条 | payload低20位`group_count`；1792×128=229376=`0x38000`，恰15/16/17位为1 | [GU compute:9/105/125](../../rtl/mlp/hap_mlp_gu_compute16_s44.sv#L105)、[W4 frontend:299](../../rtl/mlp/hap_mlp_w4_dual_ddr_frontend.sv#L299) |

这些路径属于记录数，不是base address或数据字段。两frontend分别在reset将payload置0，在接受命令后拼接`{base,group_count}`；普通`core_clear`不重新赋payload（Attention:175–176/194–203，W4:259–260/288–300）。因此表中位在同一源payload内具有相同的0→1/复位轨迹，可作为冗余位合并的解释候选，**不能称为全时恒1或已证实工具常量化**。安装版XPM handshake源码`xpm_cdc.sv:588–592`按相同向量index由`src_hsdata_ff`传至`dest_hsdata_ff`，支持以上RTL字段映射；实际综合/优化是否共享launch FF、复制或改变端点仍须原生网表证据。

[AT011有效约束:4241–4281](../../vivado/reports/m006_gu_AT011_dcp_qualification/effective_constraints.xdc#L4241)对这四个精确scope均保存10 ns Max Delay Datapath Only及10 ns bus_skew；不能将告警解释为源约束完全缺失。相邻vendor CDC-15 waiver仅陈述XPM handshake模式的CDC范围，并不自动豁免Route35-462或证明十条物理路径覆盖充分。

若终态现有报告不足，最小后续仅在同一保存DCP查这十个完整D名：逐端点保留存在性、owner primitive/clock、直接net及全部driver对象，追到真实launch FF/Q或常量源；若合并则记录共享driver及源位对应，不能假设同index源FF仍存在。对四个scope记录实际src/dest集合、关联10 ns约束和未形成timing path的原生结果；不做全图fan-in、不重做物理、不依据静态推断新增waiver。该清单已交Root/A022，本轮结论为 **BUS_SKEW_FIELD_IDENTITY_OBSERVED / NATIVE_PATH_CLASSIFICATION_PENDING**。

**四份可选XPM报告仍缺，等待最终catch原文。** 本次检查时stage_quality尚未落盘，`post_opt_{d0_smc,d1_smc}_doutb_{valid,ignored}_exceptions.rpt`四文件均不存在。冻结[build:32–44](../../vivado/scripts/build_mlp_gu_board.tcl#L32)的`m006_report`在命令catch时写`native_status=FAIL`及原始`native_error`，命令返回但文件缺失/空时写`missing_or_empty_report`；只有非空报告才登记COMPLETE、路径和SHA。[build:284–286](../../vivado/scripts/build_mlp_gu_board.tcl#L284)针对两个既定真实register集合分别调用valid/ignored。

最终须核`xpm_exception.{d0_smc,d1_smc}.{valid,ignored}.native_status/native_error`四组记录：区分命令参数/对象错误、正常返回但无工件及真实完整报告；有报告时核准确scope/对象、实际有效或ignored条目及SHA。缺文件或catch不能写成COLLECTED、ignored=0或完整约束通过。现有两coverage的10 ns/Endpoints1仍是已见的有限覆盖证据，From50%/To33.33%是原集合口径，既不等于寄存器漏约束率，也不替代缺失valid/ignored分析。若确需修collector，只在当前自然终态后由A022按原scope普通修复；本轮不猜测未输出报告的具体工具原因、不增加运行停点。

build:508–514会将任何`*.native_status=FAIL`计入最终`overall.status=FAIL`；故即使route原生成功，缺失可选报告也可能留下质量汇总FAIL。必须分辨“收集失败”与“已证物理违例”，同时保留原始FAIL，不将正常native退出等同于全部质量通过。四组bus-skew与两XPM scope保持各自范围，最终全局check_timing、timing、route、DRC、CDC依旧单独验收。活动route的中间overlap下降不作为本次预审的最终物理结论。

## 第二十次集中验收：R008路由合法性与最终质量分项

**首批已成型证据：ROUTE_LEGALITY_PASS；完整物理验收尚待。** 原生`route_design`完成2h02m23s，最终0 Errors/0 Critical Warnings/243 Warnings；保存routed.dcp为665825940 B，SHA `cc34f49bef612472367f7d273596d09dede15128d3b72a2708507e4c6d6c7cc4`。本次独立读取全DCP重算SHA，核[生成锚](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R008/attempts/AT001_impl/routed_checkpoint_observation.json)的203479 B日志prefix、实际导出行1891、原AT011成功receipt及当前102项输入均吻合、无漂移。该限定通过不表示wrapper已自然终态或全部后报告已收齐。

[正式route_status](../../vivado/reports/m006_gu_AT001_impl/route_status.rpt) SHA `1c83314491f1781859c15f6cfa6008b43852203e3e908287720795302af0c0b7`：1687352条routable nets全部fully routed，routing errors为0。另4925160条无需路由（4160271内部连接、764889无load）不混入fully-routed分母。原生日志1632–1636为failed/unrouted/partially routed/node overlaps全0，1689完成routing verification；最终1872–1879为Router Completed Successfully及route_design成功。因此本轮实际完成合法布线，与旧v6 R004自然route失败的状态有别，不再仅根据中间overlap推断结果。

Phase14路由内物理优化对包括`u_mlp_ctrl/mlpc_rdata`的路径继续处理，日志1853–1860最终摘要WNS=+0.002 ns/TNS0、WHS=+0.010 ns/THS0。它是真实原生阶段摘要，**仍不替代尚待的完整setup/hold/pulse-width、check_timing/unconstrained及例外覆盖报告**，也不将2 ps setup余量描述为宽裕。仅本轮A版成功不能分离删除Down、GU收窄及布局变化各自的因果份额。

| 验收项 | 当前独立结论 | 后续只核新增证据 |
| --- | --- | --- |
| DCP来源/冻结输入/合法布线 | 上述限定PASS | 最终wrapper自然终态、0survivor、最终route boolean/receipt与同DCP身份 |
| setup、hold、pulse-width、check_timing | 路由内setup/hold摘要已见；正式分项PENDING | 最终timing_summary的全部表项、无clock/内部未约束及IO边界，不以旧post-opt目标全部clocked替代全局检查 |
| DRC与CDC | PENDING | 原生最终DRC；完整无waiver CDC中的六CDC10及可能两XDMA reset CDC11逐准确对象，不能沿用六链24级证明覆盖全部CDC |
| GU结构、netlist、clock | 综合资格/post-opt限定证据已通过；最终图PENDING | Phase14后的真实96lane双channel双entry37位、Down缺席/3072DSP/448metadataURAM及clock身份 |
| 四组十条bus-skew路径 | 字段身份已证；实际路径分类PENDING | 第十九次的十准确D端点/driver/约束最小范围，现有报告不足时同DCP只读补证，无静态waiver |
| 两SMC四份valid/ignored报告 | 既有coverage限定证据；缺失原因PENDING | 最终stage_quality四组catch原文与工件，将收集错误和真实时序/约束违例分开，原quality状态保留 |

当前后报告仍由A022同原生会话连续收集；本代理不重复物理、不修改冻结输入、不增加批准门。后续在本节增量记录实际报告/终态，不重审已闭合的功能、constructor或旧资源账。bitstream、上板、真实模型/32层Host应用与性能仍不属于本次路由合法性结论。

最终CDC的精确预定位仅复用旧R004两条CDC-11：`xdma_0/inst/pcie4_ip_i/inst/user_reset_reg/C`分别至`d0_gate/inst/u_base_reset_cdc/arststages_ff_reg[0]/CLR`及d1对应端点；同源还扇至host_split各目标域的vendor reset同步器。当前冻结`hap_v5_reset_gate_xpm.sv:15–22`指定4级、active-low、异步assert/同步release，constructor:494–496/598将xrstn接两gate base和host_split reset。这两条base-reset链不属于现有六链24级探针，不能套用其PASS。若新最终CDC仍报相同项，需在准确两链核原生clock/ASYNC_REG/D连接与launch实际fanout/reconvergence，再按复位合同判断；目前不将静态结构意图当最终网表证明，也不预设必须改RTL或可直接waive。已与A022协调只在必要时合并到同一次终态DCP查询，不额外重复load。

### 正式时序、CDC/DRC及wrapper终态增量

[timing_summary.rpt](../../vivado/reports/m006_gu_AT001_impl/timing_summary.rpt)实际2385885 B、SHA `02e46e2962f3a7d3c1f002cd5de74e31d3d2391078d7a4f40fbbf1bd5cb3e0ff`独立复核一致，状态Routed，min/max、Slow/Fast corners及Conservative Inter-SLR compensation均启用。正式分项为：

| 检查 | 最差余量 ns | 总负余量 ns | 失败端点 / 总端点 | 限定结论 |
| --- | ---: | ---: | ---: | --- |
| Setup | +0.002 | 0 | 0 / 2848130 | 已施加约束下PASS |
| Hold | +0.010 | 0 | 0 / 2846686 | 已施加约束下PASS |
| Pulse width | 0.000 | 0 | 0 / 949552 | 已报告检查下PASS |

报告明确All user specified timing constraints are met。no_clock、constant_clock、内部unconstrained、multiple_clock、generated clock缺源、组合/锁存环及partial IO delay均0；这已比旧pre-opt目标clock查询更进一步，覆盖本次正式全局内部检查。最差setup是GU branch1 row0/pair4的`total_shift_format_count_reg[2]`至MLP CSR `rdata_reg[31]`，core10 ns、22逻辑级、数据延迟9.446 ns，其中route7.440 ns（78.764%）；2 ps是本次已收敛余量，不夸为宽裕。最差hold +0.010 ns在多个clock组并列，Attention half1 staging[250]→BRAM DIN[2]仅为其中一例。

**三个外部reset IO是准确覆盖边界。** `pcie_perstn`仍列no_input_delay，两个`ddr4_sdram_c{1,2}_reset_n`列no_output_delay，均保留HIGH。不能把这三项当未布通或内部同步数据失败，也不能填任意0 delay消除计数。check_timing汇总中的port级false-path数为0，但详细报告的7个PERST源路径均明确有False Path：至rst_core/rst_ddr0/rst_ddr1首D以及XDMA sys_reset首CLR，属于厂商reset接收端例外；不等于PERST全无时序例外。两DDR reset输出实际由各MIG `cal_RESET_n_reg[0]`经OBUF驱动，报告max delay2.520/2.329 ns、Slack inf、无output requirement。当前有结构依据将三项分类为外部reset协议边界；本次内部STA不证明板外PERST脉宽/上电顺序、DDR reset引脚协议或板延迟符合要求。已有合同曾保留这些known-open，未添加新waiver或宣称已完成板级验证，原check_timing FAIL保持。

[最终CDC](../../vivado/reports/m006_gu_AT001_impl/cdc.rpt)为Routed、`-details -no_waiver`，3940967 B、SHA `2065f9a730323dd8a74bcf2e430398b57a7a1568c9cbb15c0ec15140c69a768a`。逐行计数与summary一致：519 CDC-3 Info、19 CDC-9 Info、6 CDC-10 Critical、2 CDC-11 Critical、5688 CDC-15 Warning。

- 六CDC-10接收范围仍为两个core ready的首级CLR及四个Smartconnect AUX reset首级D；深度分别4/5，与已核post-opt六链24级及稳定复位电平合同吻合，可限定接受这六个准确接收结构的架构解释，未发现必须改RTL的证据。四SMC的reset链是vendor同步/LPF/sequencer，不冒称整条链零延迟异步断言。d1两个launch在本报告为`u_ready_cdc[3]`，旧R004为`u_base_reset_cdc[3]`，二者为reset AND的不同真实输入，不能写成源对象逐字相同。原Critical保留，未扩大成整个设计CDC通过。
- 两CDC-11准确命中前述XDMA→d0/d1 base-reset链；保持待同routed DCP两链8级及launch扇出证据，不能套用六链24级。
- 全部5688 CDC-15已按实际source/destination分类：5540条在同一个XPM memory实例内从写clock至读侧register（host_split2570、d0/d1_smc各1301、paired_weight六FIFO368）；144条为XDMA八个GT CPLL频率计数器各18位；4条为debug FIFO，无未归类项。5540使用Asynch Clock Groups，余148为False Path。没有一条落在`dest_hsdata`，因此不能用十条group_count冗余位解释这些warning。
- paired六FIFO的冻结wrapper为标准`xpm_fifo_async`，fwft、RELATED_CLOCKS=0、CDC_SYNC_STAGES=2，读写均有empty/full和reset_busy门控；同报告可见其pointer同步对象。GT vendor源`gtwizard_ultrascale_v1_7_gtye4_cal_freqcnt.v:179–188`先离开测量状态、等待HOLD后再锁存计数，属于受控计数采样。上述证据支持按FIFO/vendor受控跨域结构族分类，区别于裸多位逐bit同步；**范围分类不是将全部warning自动豁免，也不替代总线偏斜/有效例外覆盖**。

[最终DRC](../../vivado/reports/m006_gu_AT001_impl/drc.rpt)为Fully Routed，9927686 B、SHA `4362d1a601ef9f871cead87c0beba4f008490435d257a8f8e2105292d6b27fc0`，0 Error/0 Critical、15762 Warning：DPIP-2 7263、DPOP-3 5153、DPOP-4 248、DPREG-7 3072、PDCN-1569 3、REQP-1858 22、RTSTAT-10 1。前三类是DSP流水线建议；3 PDCN在debug hub inferred LUT；22 REQP为PCIe BRAM collision advisory；RTSTAT列804个无routable loads网络，不是routing errors。

**DPREG-7的条件单独核实，不能与性能建议混写。** 原文警告动态OPMODE可能选择内部P反馈且PREG=0。冻结`hap_a8w4_pack2_dsp.sv`只有带停顿的乘法寄存，但本次没有仅凭RTL意图排除条件：流式读取已绑定SHA `5ef7b4ef385d99cb6a2e6b544b48f2654016c232b7bb29ee8516c25ef8e52fe0`的真实core funcsim，全部3072个`s1_dsp_product_s25_r0`定义、3072 parent module types均PREG=0，OPMODE从bit8至0严格为`{0,0,0,t,t,0,v,0,v}`，0例外。安装版原生`DSP48E2.v:1224–1264`显示W=00、X/Y各00或01、Z[6:4]仅000或011（零/C），内部P反馈选择不可达。该相关位模式为条件性warning提供实证解释；OOC全定义证据与route末图不能混称同一阶段，已交A022合入同次DCP两branch各一leaf的9位driver/PREG/OPMODEREG确认，不进行3072对象的大查询或重综合。

[R008原result](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R008/attempts/AT001_impl/result.json)已自然终态：2026-10-24T23:27:20.753971Z，native0、stop=null、changed[]、40个owned记录/0survivor、peak27.379 GiB。最终netlist为Attention1/shared GU1/Down0/blackbox0，core/DDR clock10/5/5 ns；真实96唯一lane各148个guard FDRE、两channel各7104、无缺位/额外位、3072 DSP/448metadata URAM，末图结构限定PASS。quality绑定的21份实际带SHA报告逐份一致；原stage_quality SHA `c3874d9bd7e1c827fd8181af735ea9fed8ebbebfee4110b427550446ac81c5f2`保持`overall=FAIL`。

原FAIL原因现已可精确区分：三个reset IO的缺省外部delay，以及四次可选报告调用的`Vivado 12-2785`（`-write_valid_exceptions`/`-ignored_objects`分别不能与`-to`组合）。四项是收集命令错误，不是报告发现四个ignored异常；既有coverage仍是已收集的指定集合证据，不等于约束优先级/实际生效性通过，原调用失败不得改写。A022按原授权在同一routed DCP开启唯一有界查询，合并十bus-skew端点、两reset链、两个DSP代表及两SMC合法scope报告，不改约束、不重物理。**截至本增量：GU-only实现、合法route及已施加内部STA已完成；完整CDC/剩余约束归类等待此次必要补证，外部reset协议/板级覆盖仍独立未完成。**

### AT002新增实际对象：有限结构接受，Max-DPO覆盖存在实质缺口

本次读取[core_objects_observation](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R008/attempts/AT002_terminal_bus_skew_query/core_objects_observation.json)绑定的21个已关闭工件，逐文件字节/SHA全部一致；parent identity、source hash文件及15502 B原生console prefix SHA一致，当前六项query输入无漂移，DCP仍为同一`cc34f49b…c7cc4`。这只是查询中已关闭工件的独立审核，不提前声称AT002自然终态或0survivor。

**十个告警端点的网表解释已证实。** [原生对象](../../vivado/reports/m006_gu_AT002_terminal_bus_skew_query/native_objects/native_bus_skew_objects.txt)显示Attention每half的dest14/16实际都由同scope `src_hsdata_ff_reg[16]/Q`驱动，GU dest15/16/17都由同scope `src_hsdata_ff_reg[17]/Q`驱动，全部为真实FDRE源。它们是同轨迹位合并，不是全时常量；静态payload字段解释与原生网表闭合。十个逐D实际路径的data delay为0.247–0.911 ns，但均明确`Timing Exception: Asynchronous Clock Groups`、`Slack: inf`，不得记作10 ns绝对延迟通过。

| 准确scope（位于u_compute） | 动态数据端点 | 原生bus-skew requirement / actual / slack ns |
| --- | ---: | --- |
| Attention weight_frontend command0 | 34 | 10 / 1.072 / +8.928 |
| Attention weight_frontend command1 | 34 | 10 / 0.652 / +9.348 |
| GU w4_frontend command0 | 35 | 10 / 1.364 / +8.636 |
| GU w4_frontend command1 | 35 | 10 / 1.084 / +8.916 |

四[scope报告](../../vivado/reports/m006_gu_AT002_terminal_bus_skew_query/native_objects/scope1_bus_skew.rpt)的constraint summary均MET，详细路径输出各限32；动态endpoint总数138，不能将128条已打印skew路径当完整逐D绝对延迟表。偏斜有限接受与绝对延迟缺口同时成立：coverage列出10 ns Max-DPO，仅表明指定对象/预算存在；用户三域clock group优先级将它覆盖。官方[2025.2 UG903](https://docs.amd.com/r/2025.2-English/ug903-vivado-using-constraints/Exceptions-Priority)明确clock groups优先且bus-skew独立，`-reset_path`无法越过clock groups。[异步信号约束说明](https://docs.amd.com/r/2025.2-English/ug903-vivado-using-constraints/Constraining-Asynchronous-Signals)要求偏斜之外仍需控制绝对延迟。

厂商安装版`xpm_cdc_handshake.tcl`按目标5 ns×两级同步产生10 ns两种约束，XPM HDL在发送请求时保持源数据、两级请求同步后capture。因此原预算有来源；仅十条短count路径与四组skew不足以证明含32位base在内的整个握手总线符合采样预算。本次不能把该缺口仅归档成warning后称G5全部完成。**这是已证约束覆盖问题，不是已证数据延迟超限，也不推翻合法route或已施加同步域STA。** Root已授权在同物理图独立副本修正，最小实施/验证合同写入[design §12](design.md#12-r008同物理图的cdc约束收敛合同)；修正后finite Max-DPO资格尚NOT_RUN。

**两新增reset链结构限定接受。** [native_xdma_reset_objects](../../vivado/reports/m006_gu_AT002_terminal_bus_skew_query/native_objects/native_xdma_reset_objects.txt) SHA `9e31b7bb57b866555a34c4c098219e6619d937fe89766b4092ccf9ddc47a4761`：两scope共8级FDCE，ASYNC_REG=1、INIT=1，分别正确DDR clock；stage0 D=VCC，其后严格前级Q→D，所有CLR由XDMA `user_reset_reg/Q`驱动。共同源73个load完整列出，含两gate共8个CLR、host_split四个AUX同步入口及XDMA内部reset/enable；不是只有两个负载，也不能把73个load都当已经独立签核的同步器。每条末级Q仅送各自aresetn LUT2的I0，与既有base/ready组合相符。按稳定全局复位、各目标域同步release、复位期间不保留事务的既定合同，可限定接受这两条准确base-reset结构；未见应因CDC-11就修改RTL的证据。原两Critical保留，这不覆盖板外PERST协议或全部73负载的功能验证。

**两个末图DSP代表与先前全3072模式证明相符。** [native_representative_dsp_objects](../../vivado/reports/m006_gu_AT002_terminal_bus_skew_query/native_objects/native_representative_dsp_objects.txt) SHA `d6f089513f90ba124b0b516b418619f500b26ccf912205004908ebde885d4b79`：两branch各一leaf均DSP48E2/PREG0/OPMODEREG0；ALUMODE全GND，OPMODE8/7/6/3/1为GND，5/4/2/0四位同一真实`s0_valid_r_reg/Q`，26个pin追踪均闭合。与已核全部3072个绑定funcsim模式共同排除逻辑可达的内部P反馈条件，DPREG-7无需为消除计数而改乘法RTL；不把两代表查询说成route末图全部3072逐一查询。原DRC警告保持。

**SMC仍按实际端点区分。** 本次已关闭的[d0 scoped例外](../../vivado/reports/m006_gu_AT002_terminal_bus_skew_query/native_objects/d0_smc_scoped_exceptions.rpt)在10 ns条目显示Invalid endpoint；vendor原selector含`*doutb*reg*`的非法LUT对象，这不自动等于唯一真实FDRE/D没有生效约束。随后[d0 coverage](../../vivado/reports/m006_gu_AT002_terminal_bus_skew_query/native_objects/d0_smc_coverage_exceptions.rpt)明确列出唯一真实FDRE及Max-DPO10 ns/Endpoints1，仍不能替代生效优先级；50%/33.33%继续是原pin集合口径。ignored/timing及d1尚待同次查询完成，不能预填ignored=0、将Invalid endpoint解释为整个DPO有效或全部失效，也不热改活动输入。后续只核新增真实D的优先级、约束和时序；若也被group覆盖，按§12同一有界修正加入各1真实D。原四项命令互斥FAIL与新查询结果分开保存。

本批结论：**BUS_SKEW_LIMITED_PASS / RESET_STRUCTURE_LIMITED_ACCEPT / DSP_MODE_LIMITED_ACCEPT；CDC_MAX_DPO_COVERAGE_OPEN。** 合法route、同步域STA和GU结构已完成；硬件全约束资格尚需上述精确修正，外部reset/上板独立未验。本代理没有EDA、重测、生产/102输入修改或新审核包，普通修正由A022按既有授权连续执行。

### 最新交付授权：先生成工程验证版.bit

用户最新“不能先生成bitstream吗”已由Root转为执行优先级：A022先从原`cc34f49bef612472367f7d273596d09dede15128d3b72a2708507e4c6d6c7cc4`合法routed DCP生成工程验证版`.bit`，再继续design §12的约束修正；不再要求修正后资格作为文件生成前置。正在运行的AT002辅助只读查询如需收束，原始/PARTIAL证据必须保全，不能算已完成SMC审核。

**本条仅记录AUTHORIZED，尚无bitstream生成成功证据。** 文件交付须绑定实际DCP/源/工具/日志、原生退出结果及`.bit`大小/SHA，并明确“工程验证版：Max-DPO覆盖未闭合、必要SMC结论尚待、外部reset协议及板级未验证”。原quality FAIL、已有route/同步STA限定PASS及开放项均保持；不捏造IO delay、不新增waiver、不降级原生生成检查，也不把生成文件视为约束全部通过。仅文件生成已授权，下载/配置板卡、上板/GPU仍不在范围。本代理只更新既有design/results，没有启动EDA或修改冻结输入。

### 后续交付与§12补集语义明确

工程验证版已由A022实际生成、Root交付；本次读取[AT003 delivery_receipt](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R008/attempts/AT003_preliminary_bitstream/delivery_receipt.json)并核其result SHA一致：native0/stop=null/changed[]，状态`PRELIMINARY_BITSTREAM_GENERATED_SIGNOFF_OPEN`，工件80159259 B、SHA `66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47`。这是先前授权后的真实增量，不将前述授权时尚未生成的记录倒改为当时已完成，也不由文件生成推出约束签核或板级验证通过。

本次只读评估A022提出的全部primitive非clock输入through补集，**有条件接受为固定138条直连路径专用构造**，已写入design §12第3项。其等价性来自三点：原有向clock clamp限制所有新cut都属于原cut；任一非目标原cut路径仍包含捕获输入或外部输出边界；每个目标被证明为直接FF Q→FDRE D，减去D后不再经过任何through点。全部primitive输入包括组合输入，作为遍历点可用，不能称作timing endpoint全集；直接连接证据必须覆盖138条，不复用十条样本替代。

额外top output/inout driver集合也必须与目标路径零交集，特别不能含目标launch Q，否则会重新切掉已排除的D。CE/clock-gating/异步控制/RAM/DSP/有效入向INOUT等类别须实核集合包含，不能仅以`all_registers`或类别计数假定完备。保留真实-from/-to clock方向以免双时钟宏误切同域；修正后的逐138 finite Max-DPO及全局cut差异仍是实际退出条件。本次是集合语义及约束合同结论，工程CPU准备/新原生验证不因此记PASS。

[AT002保全的d0实际D路径](../../vivado/reports/m006_gu_AT002_terminal_bus_skew_query/native_objects/d0_smc_doutb_one_timing_path.rpt)确为同域`fifo_empty_r`→真FDRE D、5 ns Setup、slack +4.076 ns/data0.865 ns；只取`-to`最差一条，不能证明跨域Max-DPO生效。d1未采，保持NOT_COLLECTED。SMC若存在组合数据路径，减D后的中间primitive输入仍在through集合，故不得直接套138直连证明；首次修正保持其原cut。必要时仅在同副本按准确异域-from查其D，再对完整目标路径和共享节点另作精确分区，不能悄悄扩成140目标或粗删组合cone。已将具体条件发Root/A022，无新用户审批、EDA或工程输入修改。

**AT004包含门失败的窄核。** 已读取[native_capture_complement_proof](../../vivado/reports/m006_gu_AT004_routed_constraint_qualification/native_output/native_capture_complement_proof.txt)：ddr0实际data集合148074，其中148042被谓词覆盖；32个遗漏未输出名字。此前primitive全集1877027、through基础14386032、准确减68，138条目标直连/目标与through无交集已有该次原生记录；但这些局部结果不能覆盖遗漏类别。工程报告AT004自然native1/0survivor且未修改约束，本次原始proof证明实际终止在包含门，不把另行发现的导出页眉问题误写成该次失败原因。

当前只确认“native类别集合与当前谓词不完全一致”，没有证据判32项都是clock、output或无害。已在design §12加入启动前冻结的三分支分类规则：先完整保全有界差集及实际pin/library/clock角色；真实capture精确加入、纯非capture有证排除、未知则在时序修改前失败。相同session可按预冻规则适配已知分类并重新核完整补集/138路径交集，无需逐selector人工放行，也不允许活跃源热改。官方命令说明未保证data/clock/output集合互斥；因此既不能机械要求所有data查询返回项都作为输入cut，也不能仅因在clock/output集合中就删除。v2尚未原生证明这32项身份，本轮未运行EDA或修改工程实现。
