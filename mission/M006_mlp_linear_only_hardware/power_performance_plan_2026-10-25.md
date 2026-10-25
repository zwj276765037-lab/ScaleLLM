# M006 工程验证版：功耗与速度测量合同（2026-10-25）

**本轮按用户请求实际测量，不另设逐项批准门。** 对象为已通过四次生产GU诊断的bit SHA `66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47`；ABI v7/caps1d、core100MHz、N14336/K4096/16rows/两matrix保持。唯一Dell owner `/root/board_host_prepare`；Host最多8CPU/8GiB，不重配bit、修改RTL/ABI、电源配置、启动GPU/EDA或操作其他任务。Max-DPO/external reset签核仍OPEN。execution、measurement verdict、适用负载与review分开记录；合同冻结不等于测量已完成。

## 1. 速度口径与实际计数器

依据 `project/hardware/rtl/integration/hap_mlp_gu_job_control.sv` 的LOAD/ARM/COMPUTE/DRAIN状态及计数更新、`hap_mlp_gu_axil_control.sv:324`的CSR映射，以及 `project/hardware/source/mlp_linear/abi_gu_only.json`。core100MHz由有效ABI、bit来源构造的clk_core100MHz和已核物理时钟身份共同支持；不是本轮频率计实测。

| CSR | 真实含义 | 报告限制 |
| --- | --- | --- |
| `354` compute | compute command握手起到compute_done，包括末拍；包括权重供给、计算流水和输出背压等待 | `T_compute=cycles/1e8`，称compute窗口延迟，不能称纯DSP计算时间或START→DONE总时间 |
| `358` load | LOAD phase拍数，包含该phase内握手等待，不含VALIDATE | 单列输入装载phase时间 |
| `35c` store | writer arm握手起，持续到终态排空；与COMPUTE大幅重叠 | 单列store/drain窗口，不能再加compute |
| `360` stall | 活跃接口出现valid&&!ready的逐拍OR计数 | 多接口不累加；可能与上述每项重叠，不能称纯额外延迟或简单归因DDR |

计数为32bit饱和，必须在ACK前读取同一DONE快照，值`ffffffff`不能作正常计时。内部`total_cycles`未映射CSR；**禁止将compute/load/store/stall四项相加得到总延迟**。load+store也缺少部分ARM/准入开销，不冒称精确total。

原四次compute 734794/734758/735731/735612约为7.35ms，只作pilot依据，不替代正式样本。单GU数学规模 `2×16×4096×14336 = 1,879,048,192 MAC`；以1MAC=2ops计 **3,758,096,384 ops**。报告 `dense-equivalent GMAC/s = MAC/T/1e9`、`dense-equivalent TOPS = 2MAC/T/1e12`，在compute窗口约0.511TOPS；该计数包含零项，不等于实测非零MAC次数或DSP翻转率。

必须分列：①硬件compute/load/store/stall；②同机Host观测START写入至首次看到DONE的延迟（含MMIO/poll，记录poll间隔）；③输入H2C→DONE→完整输出C2H→gold比较→ACK的每命令端到端时间；④跨SSH/RPC的端到端时间（若仍采用）。装载weights/metadata单独报告，驻留steady-state不能把其成本隐藏成cold-start性能。Host时间用单调时钟；若能记录START调用前/后与最后非DONE/首次DONE，可给出硬件事件时间区间，不能称精确START→DONE周期计数。

正式统计至少**2个成功warmup命令+20个成功有效命令**，按完整pair运行；报告实际N、median/p5/p95（固定使用NumPy linear quantile）、min/max，并保留逐命令原始计数/时间/身份。warmup单列，不删慢样本；错误命令不计入成功吞吐，但单列失败并停止本轮提交，不能重试消除。每个输出完整C2H、逐字节gold通过后才ACK；DONE身份、73728输入B/1376256输出B/1792records及error0继续检查。实际窗口时间/完成数给steady-state吞吐；硬件compute TOPS与Host throughput分开。

## 2. 驻留weights/metadata的合法连续循环

RTL `hap_mlp_gu_job_control.sv:101–106` 允许在IDLE、无unACK DONE、paths_quiescent、admission enabled、无fault/maintenance、active metadata有效且无loading/commit时，将**不同非零epoch**绑定当前active bank/generation、layer和canonical GU bases。无要求重载weights/metadata；ACK/job_clear保留绑定，同active epoch重复commit拒绝。更换meta bank/generation/fatal/reset会使原epoch失效。

合法流程由**同一个测试owner和持续会话**维护：

1. 初次按既有流程核输入hash，stage weights/metadata一次，保存active bank/generation、layer/base、bundle SHA和所属lease；完成warmup。
2. 每个epoch执行cohort0/buffer0、cohort1/buffer3，各有fresh command ID与递增buffer generation；两次均完整copy/compare/ID ACK且排空后release当前Host lease。
3. 显式resident-rebind：核同一驻留身份、meta bank/generation/valid未变、无loading/commit、无active/pending/fault、硬件idle；保持layer、GU bases `0/01c00000`及Down保留字段0，使用run-wide不重用的fresh epoch写`36c`，有序读`370=0`与`368=new_epoch`后建立新Host lease。清admission前先保留既有诊断；非零首错停止，不清错掩盖失败。
4. 同一weights/metadata无需再次DMA或META LOAD/COMMIT，重复下一pair。最末成功pair释放lease并读回idle。

现有 `stage_gu_layer()` 固定重载，不能直接拿它冒称驻留benchmark。工程可在独立measurement adapter中实现上述已核流程并保存来源，保持原生产backend不改；不能靠重建backend丢弃pending/lease来跳过约束。权重/metadata身份变化、generation不符、零/重用epoch、任何首错立即停止新提交并保留现场。native Windows batch需兼容实际Python环境，可复用既有session的只读/写CSR及DMA语义，无需每操作跨SSH。

## 3. 功耗负载、真实遥测与时间窗口

已有structured仅4/128 activegroups，S37仅17/128；零code/权重可能降低数据翻转。可以先报告这些明确命名的负载功耗，**不能称满活跃DSP、满载或真实模型典型功耗**。7.35ms compute/约1.8s RPC命令尤其低占空比，不能当持续负载。

以同机批量循环短pilot确认吞吐/遥测可行，再测**idle15–30s → load15–30s → idle15–30s**，同一只读遥测流不中断，所有阶段保留时间戳与phase边界。pilot最多少量pairs，停止在真实缺失依赖；无有效遥测时继续速度统计并将功耗标NOT_MEASURED，不用估计值填补。窗口长度与样本数不足以支持统计时如实记录，不能无限延长等待。

工程已发现的只读脚本证据为 `experiment_results/board_validation/AT_20261025T013144.475442Z_power_capabilities/existing_read_vcu118_pmbus_telemetry.ps1`：7个固定rail地址70/11/12/15/14/72/73，部分READ_POUT，部分VOUT×IOUT，含raw/单位/量化步长。这不是已测整板12V输入。执行前核工具实际只读调用语义，记录传感器/rail名、地址、V/A/W单位、转换/量化依据、逐rail采样时间与missing/stale/invalid。读事务的寻址选择应按真实API说明，不能静默执行持久电源配置或clearfaults；绝不修改电压、使能或限流。既有日志只能作历史参考，不冒成本轮新测。

分层报告：有真实board-input测点才称整板输入功耗；否则称**已监测rail功耗及所选互不重叠rail之和**，明确未覆盖rail、转换损耗与其它部件。输入rail与下游输出rail不能doublecount；多个rail若是同一供电通路的上下游，只选一个切面，未证明关系就分别列数，不强行求总和。部分rail只有V/I时P=V×I需标推导测量值及其非同时采样误差。

本轮已明确使用固定7路FPGA regulator输出的读取集合，最终总和名称为“7路已监测FPGA稳压器输出功耗和”，不是12V整板输入。benchmark和sampler在同一Dell保存UTC与各自单调时钟原始标记、启动/结束关联点；不直接相减Linux与Windows两台机器的monotonic值。每个rail保留自身读时刻，每个sequential sweep保留start/end。一个sweep跨越idle/load边界时标transition并从稳态统计排除；每个idle/load/idle阶段应取得至少两次完整有效sweep，实际采样不足则标覆盖不足，不伪称稳态统计充分。优先使load窗口起止位于完整pair边界，保存边界命令，避免把跨窗命令全部计入占空比/energy分母；无法精确对齐时给出边界处理与误差范围。

load与前后idle分别给时间加权平均/median/p5/p95、N/有效覆盖时长/采样间隔；波形积分用实测时间戳，缺口不随意插补。增量功耗 `P_load − (P_idle_before+P_idle_after)/2` 使用同样rail集合，附两idle差异；负值或不显著差异如实保留。可计算真实稳态loadwindow总J/成功command数，但必须注明包含I/O、比较、Host等待与实际占空比；增量energy/job另列，不与总energy/job混名。不由低占空比功耗反推出active instantaneous power。

记录 `compute-window duty = sum(354 cycles)/(1e8×window_seconds)`，按实际命令时间边界完整覆盖；它包括compute内部stall，且不包含LOAD/ARM余量，**不是独立精确busy计数**。若采job_busy，另报告采样周期/漏采风险，不与compute duty混名。低采样率无法分辨7.35ms脉冲时，只能给window average。native loop也按实测占空比命名，不预设“满载”。

## 4. 建议新增128-group active-code诊断

由独立vector工程在新bundle生成，不改旧物料。用途为比4/17group稀疏用例更充分的持续数据活动负载，仍不声称worst-case power或真实模型代表性。所有128groups、16rows、两matrix、14336columns均合法非零code；每个activation差值和weight也非零。可用32列周期降低独立gold成本：`c'=c mod32`，g=0..127，r=0..15，k=0..31，m=0/1。

```text
zp = 128
q-zp = (-1)^(k+r+g) * (1 + ((k+3r+g) mod7))
a_code = 17 + ((r+g) mod13)            # 17..29
a_shift = 14 + ((r+g) mod3)
w = (-1)^(k+c'+g+m) * (1 + ((3k+5c'+g+2m) mod7))
w_code = 19 + ((c'+3g+m) mod11)        # 19..29
w_shift = 14 + ((c'+g+m) mod3)
```

因此q∈121..135、w∈±1..±7、total_shift∈28..32；`|dot|≤1568`、`|raw|≤1,318,688`、`|guard|≤82,418`、128组和绝对值≤10,549,504，终值绝对值≤41,209，远小于S24饱和边界。按现行整数算术/原record顺序生成gold，不引入浮点matmul。仅计算两matrix×16rows×32基列的全部128组，然后扩展448个列周期，约4,194,304 MAC的离线参考规模；另直接解码wire并独立scalar抽查边界/尾列，验证全部group code非零、padding/canonical/尺寸/hash、全输出逐字节gold。周期重复是本诊断适用限制，仍覆盖所有物理生产输出位置。

该新case准备未完成时可先跑明确标注的旧case功耗/速度，不将准备依赖扩成全任务阻断。可用后采用相同warmup/N/窗口协议，独立报告case间速度及功耗，不把不同负载混成一个分布。

## 5. 证据与终态审核

每次measurement新建 `project/E013_mlp_linear_only_hardware/experiment_results/board_validation/power_performance/` 子attempt，保存bit/ABI/runner/transport/bundle身份、命令序列/lease、raw telemetry、所有时间/计数、输出hash与逐字节比较结果、原始stdout/stderr/exit、失败和资源边界。瞬时rail读数、window平均、增量、compute窗口速度、Host端到端各有明确字段，不互相替代。

阶段完成或真实失败后集中审核；已有用户授权内普通transport/脚本修复与对应验证连续。任何错误保留首错，不自动硬复位或电源配置写。本合同不要求新增RTL计时器或另行重构硬件；现有无法测到的量明确标不可直接观测。
