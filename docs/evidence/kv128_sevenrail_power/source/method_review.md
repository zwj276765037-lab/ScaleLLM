# 本轮方法审查与最终验收记录

2026-11-02；最终状态：**PARTIAL_WITH_LIMITS**。main_004完成计划的12/12正式窗口，原始记录与离线数值复核通过。空闲及完整KV128解码步各3次有完整共同时间覆盖；Attention和MLP各3次存在超过预注册G=420 ms的间隔，只接受共同覆盖时段均值，完整窗口均值保持null。原launcher FAIL与sampler原生退出码null均原样保留。

方法依据为[design.md](design.md)的既定合同和[官方来源核查](references/source_facts.md)。没有通过提高缺口阈值、缩短窗口、删除异常命令、补造BUSY或按占空比换算来获得通过。七轨为指定稳压器输出，未测整板输入功率；传感器内部平均/滤波窗口及lag上界未知，严格物理active mean仍未建立。

| 验收项 | 最终状态 | 实际证据与边界 |
|---|---|---|
| 计划窗口采集 | COMPLETE，12/12 | 四类各3次；idle/A/M各>=120 s；full为一次完整32层step |
| 原始采样与数值格式 | PASS | 10116 sweeps、70812轨点、171993次读、零读错误；全量raw独立解码及时戳核查 |
| 采样率依据与实际期限 | 固定D=140 ms；存在迟到 | idle probe先表征；正式5069次起点迟到>2 ms；G=420 ms不变 |
| 恢复、请求身份及输出 | PASS_WITH_LIMITS | 完整256 MiB状态恢复、64命令资格、三次完整step16 token和6个捕获目标匹配；其余27层历史非独立oracle |
| 空闲完整窗口均值 | ESTABLISHED，3/3 | 各窗七轨共同覆盖100% |
| 完整KV128 step完整窗口均值 | ESTABLISHED，3/3 | 各窗七轨共同覆盖100%；包含CPU、DMA与host间隙 |
| A/M完整窗口均值 | NOT_ESTABLISHED，0/6 | 共同覆盖97.0574%–98.5315%，全窗值null；covered mean有效 |
| BUSY观测与保守内窗 | PARTIAL | 9128/9129命令见BUSY；9127条有>=2次观测且可证内窗；2条内窗null |
| BUSY内七轨时间加权均值 | NOT_ESTABLISHED | 没有单条命令满足每轨至少2个完整VI包络与共同覆盖；只报告实际条件点分布 |
| 严格物理active mean | NOT_ESTABLISHED | 内部窗口/lag和绝对校准未知；字段null |
| launcher进程状态 | 原始FAIL保留 | BUSY观测门导致FAIL；workload退出0；sampler原生退出码未知 |
| 资源与收尾 | PASS_WITH_LIMITS | 进程清理/租约释放、只读postcheck通过；不能把postcheck退出0替代sampler未知退出码 |
| RTL/bitstream边界 | 范围遵守；身份有限 | 本轮为host脚本/只读遥测及既有协议工作负载；前后发布bit文件hash一致，不声称FPGA配置读回 |
| 整板功率 | NOT_MEASURED | 七轨标签与范围保留 |

## main_004最终独立核查

直接读取[原始遥测](../DOWNLOADS.md#archive-files)、[逐命令QPC记录](../DOWNLOADS.md#archive-files)、[窗口记录](../native/main_004/workload/windows.jsonl)、[workload回执](../native/main_004/workload/workload.json)及[launcher原始回执](../native/main_004/receipt.json)。[独立审核程序](references/main_004_independent_recompute.py)未调用工程分析器的解码、时间积分或统计函数；[完整独立重算输出](references/main_004_independent_recompute.json)保存每窗每轨均值、缺失区间、BUSY条件点数与原始文件SHA256。

独立遍历全部171993个bus_read（171972次遥测+21次mode/CAL读），核对read_id连续、实际原始字节长度/小端word、API返回、单读QPC起止、跨读非重叠、rail_point与即时bus_read完全一致、逐sweep七轨轮换和所有数值。三轨MAX20751现场模式0x20、VID换算、IOUT指数−1、POUT指数+1均匹配；四轨MAX15301模式0x14、Linear11电流与POUT不支持标记均匹配。全部9611个合法负电流点在VADJ，保留符号；未发现VI读取包络超过G。新的API读取仍不等于新的ADC转换。

正式实际sweep起点周期min/median/p95/max为140.0898/142.007/176.1067/540.9238 ms；sweep持续时间min/median/p95/max为95.5863/112.16935/175.0983/540.1159 ms。较空闲pilot负载下读取变慢，造成真实缺口；没有把目标D=140 ms当成每次实际频率。官方资料中的更新值、主机访问周期和未知内部滤波窗口分别记录。

全部9129条命令ID连续8286..17414，逐descriptor字节hash、generation、layer/opcode、16槽position127/epoch1、80 MHz、输入/输出字节数、DONE cycles、零错误、START→DONE→ACK顺序和无命令重叠均通过。相同(opcode,layer)的输入输出SHA在全部重放中一致。74条命令属于窗外资格（完整64条+5层局部恢复对照各2条），未并入12窗。A三个窗各1175/1160/1165条，五层各235/232/233次；M三个窗各1788/1770/1805条。完整step每窗64条、16 token与六个旧捕获输入输出一致，并有全KV恢复/保持记录。每窗每轨原始点最少456个，均超过200。

现存状态经inspection_002及中止后的连续CSR身份恢复使用，main_004的resume记录匹配上一run末ID8285和live CSR；发新命令前完整256 MiB与快照逐字节一致，快照SHA为`fa610d68fab6045573a355313f78808c93b7273dbf1edc2e8f61bc3ea1ad81c8`。五层position0..126历史有旧捕获逐字节证据，其余27层为生命周期与现场行为证据，保持`independent_full_model_oracle=NOT_ESTABLISHED`。KVRecord本身没有valid/tag/epoch/position字段，没有虚构逐记录tag核验。

### 时间加权结果与覆盖范围

各轨先在全程时间轴构造相邻有效点间隔<=G的线性段，再在窗口边界插值裁剪；七轨在同一共同覆盖集合C积分，均值为总积分/|C|。完整窗口值只在C覆盖全W时填写。这里的100%指合同下的插值支持覆盖，不代表连续物理采样或已知传感器时间窗口。

以下均为七轨V×I遥测之和。每行是三次重复各自时间加权后等权汇总；±为三个重复的样本标准差，不是仪器精度、置信区间或绝对测量误差。

| 工作负载 | 三次均值（W） | 等权均值 ± 样本SD（W） | 三次共同覆盖率 | 可接受的结果口径 |
|---|---|---|---|---|
| 空闲 | 11.108104 / 11.125871 / 11.103386 | 11.112454 ± 0.011856 | 100.0000% / 100.0000% / 100.0000% | 完整窗口均值 |
| Attention五层循环 | 11.360400 / 11.327392 / 11.329244 | 11.339012 ± 0.018545 | 98.5315% / 98.4221% / 97.0574% | 仅共同覆盖时段均值；全窗null |
| MLP L0循环 | 12.114826 / 12.044127 / 12.070719 | 12.076557 ± 0.035709 | 97.4958% / 97.8904% / 97.9212% | 仅共同覆盖时段均值；全窗null |
| 完整KV128解码步 | 11.215846 / 11.193983 / 11.136687 | 11.182172 ± 0.040880 | 100.0000% / 100.0000% / 100.0000% | 完整窗口均值 |

A三窗缺失1.76340815/1.89581090/3.53344445 s，M三窗缺失3.00800510/2.53409175/2.49604475 s。不能把这些covered mean称为完整120 s平均，也不能按总时长或BUSY占比修正。全32层step三次持续65.4053732/65.4006318/65.6950058 s，包含CPU Down、LM head、commit及主机间隙；对应FPGA cycles仅约2.027 s，不据此反推“纯FPGA功率”。

[正式分析JSON](../DOWNLOADS.md#archive-files)、[逐轨逐窗表](../results/main_004_window_rail_v2.csv)、[原始点图](../DOWNLOADS.md#archive-files)与[重复统计图](../DOWNLOADS.md#archive-files)采用上述口径。独立重算与工程最终v2逐12窗coverage/缺口/均值/逐轨/零阶保持敏感性全部吻合（绝对容差1e−10）。图像已检查，原始离散点、POUT、窗口颜色及coverage可见，无平滑替代原始点。zero-order-hold与线性法差异仅作插值敏感性，最大绝对差约0.024948 W，不能作为误差界。

最初工程分析错误地只把完整读取包络包含在W内的点用于全窗积分，丢弃窗口外的边界支撑点；已按原合同修正为全程序列构段再裁剪。原版保存在[原积分输出存档](../DOWNLOADS.md#archive-files)，早期v2状态版本保存在[状态版本存档](../DOWNLOADS.md#archive-files)。原raw未改，最终使用稳定`*_v2`结果；BUSY条件点继续要求VI完整读取包络包含，不把全窗边界规则套到BUSY条件分析。

### BUSY与原始退出异常

9128条命令至少一次读取到BUSY。两条不能建立保守内窗：

- cmd10084，MLP repeat1，只有1次BUSY读取；该事务跨越约77.95 ms，不能由单次API返回夹出有效BUSY内窗，状态为`FEWER_THAN_TWO_BUSY_OBSERVATIONS`。
- cmd14365，Attention repeat2、layer31，0次BUSY读取；START之后首次STATUS开始晚94.5075 ms，直接读到DONE，DONE_CYCLES=3601276对应45.01595 ms。轮询错过BUSY与时序相容，但不能据此补造BUSY观测，状态为`NO_BUSY_OBSERVATION`。

其余9127条有至少2次BUSY观测且内窗正长度；全体DONE/ACK及输出验证成立。两条异常仍保留在所属完整/covered窗口的功率时间轴与cycles中；内窗和内窗条件功率留null。工程与独立程序的每窗BUSY内时长及每轨完整VI包络条件点数全部一致。没有任何单条命令满足七轨各至少2个内窗VI点并获得共同时间覆盖，因此不报告七轨BUSY内时间加权均值。存在的条件点均值/中位数仅是条件样本分布；未知传感器窗口使严格物理active mean继续null。

原launcher将缺少first_busy直接计入completion gate，故[原receipt](../native/main_004/receipt.json)保持`FAIL: QPC command trace identity/completion gate failed`。workload确实exit0且COMPLETE_WITH_LIMITS；sampler自己的回执为COMPLETE/pass=true，但launcher记录`sampler_exit_code=null`。没有把未知原生退出码补成0，也没有用后续postcheck覆盖原FAIL。仅为这两个BUSY观测缺项不重新跑板；已有原始数据足以支撑上述有边界的结果。

### POUT、来源与收尾

三轨MAX20751的POUT按原始2 W档单独保留。VCCINT在空闲为VI=5.525 W、POUT=6 W；正式负载中VI与POUT均出现变化。IOUT编码0.5 A在0.85 V下给出0.425 W电流步长，POUT更粗不能证明VI更准确。MGTAVCC全部为VI=0.45 W/POUT=0 W，MGTAVTT为1.8 W/2 W。正式JSON给出各窗VI/POUT同一支持覆盖的均值差、读取偏移及分辨率；它们为异步读取的一致性比较，不作仪器偏差标定。四轨MAX15301原始POUT及读取时戳明确null，文档未支持而未发未知命令。CAL_GAIN/OFFSET原码已只读保存，没有修改或二次施加到电流读数。

[远端/本地传输清单](../provenance/main_004_transfer.json)为ALL_MATCH，16文件861893152字节；主控已核对全体SHA，本审核另保留主要raw的独立SHA。原回执峰值进程树RSS2693083136字节，最低可用内存9982418944字节，满足8 GiB/2 GiB资源合同；CPU0–7、BLAS单线程。survivors=[]、lease_released=true。

[只读postcheck](../DOWNLOADS.md#archive-files)为COMPLETE/exit0：三次STATUS/ADMISSION_ERROR/DONE_ERROR均0，register_writes=0、handles_closed=true、lease_released=true。前后发布bit文件SHA均为`96df1a5c1bf4174921bc02ccd88df4066dece3d62b491acb3106bb90ac0ffc85`；这是文件身份和现场CSR证据，不是FPGA配置逐位读回。官方PDF直下超时与截图失败保留在references；已读取官方网页文本不等于已保存本地PDF原件。

本次交付的适用范围为上述12窗采集、6窗完整遥测均值和6窗covered mean。后续若要求A/M完整120 s遥测均值、单命令七轨active均值、整板输入功率或绝对精度，必须补充对应观测/仪器证据，不能由本次数据自动推出。

## 历史阶段记录（以下状态为当时状态）

## probe_001独立复核（2026-11-02）

结论：`PILOT_READ_DECODE_CADENCE_REVIEW_PASS_WITH_LIMITS`。只适用于只读短测的读取、解码、时戳和采样周期依据；整个补测阶段仍为BOARD_RESULTS_PENDING，不是四类正式窗口全部PASS。

直接遍历[telemetry.jsonl](../DOWNLOADS.md#archive-files)的全部记录，以独立Python算式从原始字节复算，未调用工程分析器的解码/统计函数；与[工程pilot汇总](../DOWNLOADS.md#archive-files)逐项核对。共594 sweeps、4158 rail points、10098个遥测读和7个mode读；每轮七轨各一次、起始轨按sweep mod 7轮换。全部bytes长度/小端word、mode、VID/Linear11数值及指数、V×I、POUT、VI包络、全体时戳的单调非重叠、raw码频数和所有汇总统计匹配。QPC频率10 MHz及native/Stopwatch夹逼校验通过。

| 独立复算项 | 结果 |
|---|---|
| sweep起点周期 min / median / p95 / max | 91.7795 / 101.6167 / 106.529 / 170.1735 ms |
| sweep duration min / median / p95 / max | 90.6382 / 100.51735 / 104.931 / 164.0938 ms |
| 正式目标周期与缺口阈值 | D=140 ms；G=420 ms |
| MAX20751 VCCINT VI / POUT | 全594点5.525 / 6 W |
| MAX20751 MGTAVCC VI / POUT | 全594点0.45 / 0 W |
| MAX20751 MGTAVTT VI / POUT | 全594点1.80 / 2 W |
| MAX15301 VADJ负电流 | 556/594点；全部电流范围−0.06134033203125..0.01922607421875 A |
| 进程和资源占用收尾 | 原始receipt COMPLETE，child_exit_code=0，lease_released=true，survivors=[] |

[telemetry.json](../DOWNLOADS.md#archive-files)记录只读、无扫描、无写、官方exe哈希及UNKNOWN测量窗；[receipt.json](../DOWNLOADS.md#archive-files)记录bit文件身份和真实退出状态。其SHA256分别为：

- telemetry.jsonl：`939c05ea2eb13df243353fba339744f8483e4a449809f0ab51a8f793de5bdaef`
- telemetry.json：`872550e882c87c9db8a022f6d9fe2815f363455ead3ac212ee1927eaa8953cdc`
- receipt.json：`c5bd360a2f80f724b8a28cf90c383838d1d5206dfb79cb4cab8d8d85179573e9`

短测局限：没有CAL读取；raw单读在完成rail_point后写出，尚非逐read即时日志。工程正在对正式sampler补齐这两项并采用起点调度，最终检查as-run版本。当前恒码不能证明fresh ADC更新、时间窗或精度；VADJ负值不可截零。没有把此约60s空闲短测计为120s正式idle重复，也没有把原始点算术均值提升为正式全窗时间加权值。全模型状态恢复、A/M和完整step各三次、共同覆盖积分、图表及最终退出清理仍待正式证据。

## inspection_002与main_001资格中止的恢复审查

**状态：INCOMPLETE，按同一合同修复和恢复；没有新增审批门。** 原[main_001 launcher回执](../DOWNLOADS.md#archive-files)与[workload回执](../DOWNLOADS.md#archive-files)保留FAIL，workload_exit_code=1、windows=[]；未进入12个正式窗口。sampler自己的[telemetry回执](../DOWNLOADS.md#archive-files)为COMPLETE/pass=true，但launcher记录`sampler_exit_code=null`，因此该进程原生退出码仍未知，不补写0。

本地独立复核[commands.jsonl](../DOWNLOADS.md#archive-files)的43条命令：ID连续8193..8235，layer0..20各A/M以及layer21的A；所有descriptor字节SHA匹配、active_mask=0xffff、16槽position127/epoch1、80 MHz、非零非饱和cycles、错误0、START→BUSY→DONE→ACK时序成立、命令不重叠。最后descriptor SHA为`90ff5b7e11eb61ee70deb524187e565364dd26f9a066d23e91d1a0ae721e84ff`，ACK_ID=8235、Attention/layer21、3599001cycles。XDMA日志尾部ACK之后ADMISSION_ERROR与STATUS均为零值的读取哈希，随后close且quarantined_requests=0，支持在无pending命令的安全边界停止；下一次仍要读live CSR逐项匹配。

main_001采样原始记录包含758 sweeps、5306 rail points、12907 bus_read（12886遥测读+7 VOUT_MODE+7 CAL_GAIN+7 CAL_OFFSET）。独立核对全部bus_read原始字节/word/长度、API returned、无异常、fresh标记、正长度且单调非重叠的QPC包络均通过。相邻总线事务最大空隙0.1706102 s；最后遥测事务晚于最后ACK 0.7197279 s，sampler finished晚0.7850075 s。说明采样在停止附近仍继续进行，不支持真实10 s停写；正式频率仍为D=140 ms、G=420 ms，实际missed_deadlines=401保留，不改称满足所有采样期限。

[冻结workload源码](../DOWNLOADS.md#archive-files)的SHA256与运行回执一致：`0f9854577a8c5e20e86f05f6ed83955800dff4ce0db36ae2cf295f9338cd32eb`。失败条件在check_budget中先求time.time()后stat().st_mtime，并要求0<=age<10；并发追加可产生负age。异常栈和持续采样与这一竞态诊断一致；原日志未保存该次age，不宣称现场直接捕获了负值。修复维持10 s停写门槛，用单调时钟+文件增长或等价先stat后time顺序，普通回归由实施者连续完成。

[inspection_002](../DOWNLOADS.md#archive-files)报告旧末ACK8192、完整末descriptor、DONE_CYCLES1466392一致；5层历史逐字节匹配、其余27层格式/非零核查为PASS_WITH_LIMITS。主控已独立核过5层sealed prefix；本审核读取其报告，并本地重新计算256 MiB快照SHA：`fa610d68fab6045573a355313f78808c93b7273dbf1edc2e8f61bc3ea1ad81c8`，匹配原manifest。[启动连续性依据](../DOWNLOADS.md#archive-files)支持同一OS会话，既不证明FPGA配置读回，也不证明DDR从未被写。

下一次恢复必须在发新命令/写KV前核对live全部CSR与8235末trace一致、全256 MiB当前DDR逐字节等于该snapshot，然后从新ID8236开始重新执行完整64命令资格及原12正式窗。当前审核没有声称恢复前live DDR比较已经执行；该项等待新run原始记录。所有既定数值/输出参考/请求条件/覆盖、七轨非整板以及物理平均窗口UNKNOWN限制保持。43条资格前缀仅作为失败与恢复身份链证据，不并入任何正式均值、三次重复或完整step资格。
