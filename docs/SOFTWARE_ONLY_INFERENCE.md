# 固定 bitstream 的软件推理优化合同与验收

2026-10-25 最终状态：**`SOFTWARE_ONLY_FUNCTIONAL_PASS_WITH_LIMITS`**。修复后的公开 `deferred` 入口已在真实 Llama 权重上完成全部32层、两请求、两生成步；128次 Attention、128次 GU、128次 Host Down、64次 epoch release，原生退出码0。独立核验全部1,032个数值边界、256处残差、4份完整词表 logits/argmax及真实反馈通过，生成 `Hi → It's`、`Hello → Hello!`。最终无 pending/lease、句柄关闭，bit、driver、boot不变。当前程序实现了固定硬件允许的驻留与并行；**GU全层权重直接切地址、持久KV增量decode及Attention双metadata库仍受RTL限制，本轮没有实现这些硬件能力。**

公开运行本身没有读取旧 baseline root/index，也没有在线计算CPU gold：真实FPGA输出经完整copy、持久保存和身份复核后参与后续推理。原始 `run_summary` 保留 `EXECUTION_COMPLETE / NUMERICAL_VERIFICATION_PENDING`；独立[完整数值回执](evidence/software_only_inference/full_numerical_audit.json)与[协议回执](evidence/software_only_inference/full_protocol_review.json)共同支持这里的限定通过，未改写原始证据。第7节保留各阶段历史，历史 pending/失败不是本轮最终状态。

### 首要指标：忽略Host后的板上计算

以下来自本次全部实际 DONE 计数，100MHz，四个真实新token。16个物理行是同一请求的前缀，不能计成16个独立生成token。原始计数和逐命令DONE哈希见[板上核算JSON](evidence/software_only_inference/board_compute_metrics.json)与[逐命令CSV](evidence/software_only_inference/board_compute_commands.csv)。

| 口径 | 时间或吞吐 | 实测与假设 |
|---|---:|---|
| Attention 128命令累计计算窗口 | **1.07629882 s**，平均 **8.408585 ms/命令** | 实际CSR计数；包含compute内部权重供给等待/反压 |
| GU 128命令累计计算窗口 | **0.94089137 s**，平均 **7.350714 ms/命令** | 实际CSR计数；包含compute窗口内等待 |
| 两引擎工作量串行等效 | **0.50429755 s/新token；1.982956 token/s** | `(A累计+GU累计)/4`，不是本次并行时间轴实测 |
| 两cohort逐层调度、Host及外部供给成本为0 | **2.586043 token/s** | `Σ[A0+max(A1,GU0)+GU1]=1.54676484 s`；条件估计，GU LOAD+STORE宽窗代理约2.577066 token/s |
| 足够独立ready任务、供给完全隐藏的服务上界 | **3.716440 token/s** | `4/max(A累计,GU累计)`；理想上界，不能当当前两请求已达到的吞吐 |

Attention `0x038`接compute FSM的非IDLE周期，`0x050..0x06c`八项互斥且每条实测相加等于总数。它不包括board FSM启动前metadata/RoPE/input DMA或末尾output DMA；所以此处是**板上compute窗口**，不是完整START→最终DDR完成时间。GU `0x354`从compute握手计至COMPUTE结束，`0x358`只计LOAD；`0x35c`从store启动贯穿compute至DRAIN，`0x360`计LOAD至DRAIN中的stall。**GU store/stall与compute重叠，不能把四项相加。** LOAD+STORE仅为较宽任务窗代理，仍有未单独导出的控制间隙。上述内部DDR权重供给等待保留在实际compute计数内，Host/PCIe输入准备与在线/离线gold时间均不计入此表。

**为什么有并行仍只有几个token/s：这里的2.586不是DSP算力上限。** 当前bit每个命令重算同一请求16行前缀，完成全32层才产生1个新token；两个引擎重叠只缩短这份工作，不能把历史行变成新的生成结果。若目标硬件实现持久KV、增量decode、独立请求行隔离及供给隐藏，同样16行可以服务16个独立请求的新token。目标报告在上下文S=16、系统并发K=16（两cohort各8请求）时估计连续稳态约33.81 token/s，K=32（两cohort各16请求）时约53.16 token/s；这些是**不同算子映射与硬件能力下的条件设计估计**，不是当前固定bit的软件已达速度，也不能用当前实测功耗直接配算能效。

本次64组顺序CSR读数观察到两引擎任务busy重叠，其中GU处于LOAD21组、COMPUTE43组；Attention状态没有compute phase标记，且两寄存器非同拍读取。当前没有共同计算时间戳或compute重叠累计量，**不能从这些快照恢复实际计算union，也不能称2.586或3.716为实测并行token/s**。当前仍为16行prefix replay；下一未知token须等本请求全模型反馈。需要KV缓存和增量算子映射的目标架构估计另见[性能与资源报告](PERFORMANCE_AND_RESOURCES.md)，不混入本次软件实测。

### 软件实现与完整运行结果

| 项目 | 本次实际结果 |
|---|---|
| 常驻内容 | 32层Attention weights+metadata、32层GU metadata、真实RoPE；129工件，H2C及完整C2H各1,660,952,576 B，逐工件SHA一致 |
| GU weights | 仍每层装入固定56MiB canonical窗口，两cohort共用；没有假称32层GU weights直接驻留执行 |
| 元数据预取 | 64次LOAD/COMMIT全部229,376 records/7,340,032 B；62次跨层LOAD均在旧双GU copy/ACK后，COMMIT均在旧双Down完成后 |
| 实际隐藏范围 | 62次跨层LOAD中61次与至少一个HostDown在途重叠，18次与两个Down重叠；31次可用控制流和下一A0 START给出“首次DMA等待结束早于Down1结束”的上界证明；不宣称全部隐藏 |
| Host数学 | 精确局部FP32整数dot后仍按原int64guard/舍入；128Down中1,344行实际计算，704个旧有效行按真实GU字节身份复用；不是KV缓存 |
| 驻留装载 / 总初始化 | 10.642563 s / 18.356206 s；后者还包含来源及模型身份检查等准备 |
| 完整程序墙钟（次要记录） | 正式213.642901 s生成4 token，即0.01872283 token/s；包含CPU Down/norm/head、PCIe、copy/hash/证据写入，不含后续独立数值审计；不作为上表纯板上速度 |
| 正式传输 | H2C3,792,699,392 B；C2H3,959,422,976 B。输入未单独C2H读回，已保存完整Host输入并核实际H2C长度；weights保持完整读回 |
| 资源与终态 | RSS峰值3,070,611,456 B、最低可用内存9,418,403,840 B；8CPU亲和性、两CPU worker、BLAS1；A0x18/GU0x8、owner0x3b/paired0x23、IRQ/DMA enable0/MSI1、request/pending0 |
| 本次功耗 | **未同步采集**；不能把旧低占空比功耗或目标架构外推当本次测量 |

实际AT为 `AT_20261025T081153.047204Z_resident_full`，run目录 `AT_20261025T081156.983420Z_resident`，summary SHA256 `2309ea2b75f4fda67df1f53f31406fbaf75722f5eef9a23eddf0078eb4600af5`。完整[软件指标](evidence/software_only_inference/full_metrics.json)与[协议审核](evidence/software_only_inference/full_protocol_review.json)绑定同一summary。已核159归档文件、11个实际runtime源、133个冻结vendor文件，256条DONE身份、copy-before-ACK/clear和64个fresh epoch。metadata generation为3..66，最终driver为oem117.inf、boot仍2026-10-25T01:47:48.5000000Z。

**计时适用限制：** `wait_metadata`二次检查覆盖了第一次`dma_complete_observed_s`，故不能据该字段算DMA准确时延或隐藏百分比；本页仅使用实际LOAD、双ACK、HostDown区间和控制流上界。首次full watchdog及一次drain-safe维护/精确旧ID退休仍完整保留，最终版本不再在GU执行时LOAD，不因后续通过删除失败记录。

公开无baseline入口已由本次完整板测覆盖；任意合法短prompt可执行，但新的输入必须另行数值审计，不能沿用本例PASS。独立 `offline-audit` 工具已对[两层真实pilot重新计算](evidence/software_only_inference/two_layer_offline_reference_audit_v2.json)：4A/4GU/4原int64Down及12个Host边界通过，不依赖旧gold、没有设备访问；它不覆盖全32层LMhead。完整本次数值结论来自原已独立审定实板gold的逐字节回归，二者证据范围分开。完整未知prompt的strict FP32头部审计须在原CPU/NumPy/BLAS环境运行。本次覆盖限两真实请求、最多2新token、总长度≤16、量化数学；不扩为长上下文、通用语言质量或Max-DPO/外部reset签核。

工程入口为 `deploy/optimized/`，测试为 `tests/test_optimized_*.py`；旧vendor、bit、数值参考、实测和发布包不覆盖。

固定 bit SHA256：`66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47`。唯一 Dell owner 为 board_host_prepare；本页 owner 为 board_contract_review。只读身份预检通过后按已授权阶段连续工作，不另设逐项批准门；禁止本轮重编 bit、改驱动/电源/启动配置、重启、reset 清故障或重开 backend 掩盖 pending。首个full首错保全后，Root另明确允许下文所述一次可观察的drain-safe maintenance与失败任务退休；不扩展到JTAG/PnP/新START。

## 1. 软件能实现与硬件限制

| 能力 | 固定 bit 的结论 | 本轮实施边界 |
|---|---|---|
| 32 层 Attention weights + metadata 驻留 DDR0 | 支持可编程基址，容量足够 | 首次完整 H2C、C2H SHA 校验后按层切地址，不再逐层从 PCIe 重传 |
| 32 层 GU weights 驻留并直接切层执行 | **不支持**，容量足够不等于接口允许 | RTL 固定 GU 两半地址为 `0/0x01c00000`，每层仍须重装 canonical 56 MiB；两 cohort 共用一次装载 |
| 32 层 GU metadata 驻留 DDR1 | 支持可编程 metadata DMA 源地址 | DDR 镜像一次装载；片上 A/B 库仍逐层加载和提交 |
| GU inactive metadata bank 预取 | 当前实测要求与 GU 执行隔离 | GU1 完整 copy/当前模式要求的核验/身份重核/ACK 后才 LOAD（deferred数值仍待离线）；与 Host Down 或独立 Attention 重叠，完整 DMA、旧 Host lease 释放后 COMMIT |
| Attention metadata 在本引擎计算时预取 | **不支持**，只有单库 | reload 是 START 后 FSM 的前置阶段；可以与另一引擎/Host 工作重叠，不能删掉加载成本 |
| 历史 KV 从 DDR 预取、全层持久 KV decode | **不支持** | board core 的 KV preload 接口绑零；preserve 标志不能恢复被其他层/请求覆盖的 KV |
| 16 行装入 16 个独立 decode 请求 | **不支持** | 固定 query_count=16、一个 query_start/causal context，无每行 request/KV 隔离 |
| Attention 与 GU 并行 | SHARED 模式真实允许 | 两引擎独立 DDR，单软件 IO owner 管理两个 pending；必须实际观测重叠才报告实现 |
| Host Down 与 FPGA 重叠、局部 dot 加速 | 软件可行 | 同一整数结果和数值边界；最多两个 CPU worker，BLAS 单线程，总 affinity ≤8 CPU/8 GiB |
| 真正单 token 增量 decode | 本轮不能实现 | 继续两真实请求、固定 16 行、长度≤16 的 causal prefix replay；生成 token 必须回馈下一完整前向 |

**GU 地址限制是 RTL 判定，不只是 Python 常量。** `hap_mlp_gu_job_control.sv` 同时检查 epoch 和 command 的 canonical bases；非法 epoch 返回 `0x1024`，非法 command 地址返回 `0x1014`。生产 core 直接将 descriptor 基址接到 GU reader，dedicated DDR leaf 不添加 layer offset。现有控制接口没有通用 DDR→DDR memcpy 命令；通过 Host 读再写不构成零传输驻留计算。本轮不向未支持的地址提交 job 来“试探”。

## 2. 地址与不可覆盖范围

所有表内地址均为 **DDR-local 字节地址**，每路有效半开区间 `[0,0x80000000)`（2 GiB）。XDMA Host aperture：DDR0 加 `0`，DDR1 加 `0x80000000`；这不是 PCIe BAR 的映射大小。所有 `base+length` 使用宽整数校验，拒绝溢出、跨路、越界、重叠和短 IO。

令 `L=0..31`、`b=0..5`。地址布局冻结如下；工程生成机器可读表并逐项测试。

| DDR | 工件/缓冲 | local base | 长度/末端 |
|---|---|---|---|
| 0 | Attention L 层 half0 | `L*0x02800000` | `0x01400000`（20 MiB） |
| 0 | Attention L 层 half1 | `L*0x02800000+0x01400000` | 20 MiB；32 层合计到 `0x50000000` |
| 0 | Attention L 层 metadata | `0x50000000+L*0x00280000` | 2.5 MiB；合计到 `0x55000000` |
| 0 | Attention input b | `0x56000000+b*0x00100000` | 196,608 B |
| 0 | Attention output b | input base + `0x00080000` | 196,608 B；六槽保留区到 `0x56600000` |
| 0 | 旧 metadata staging 保留区 | `0x56800000` | 8 MiB，优化模式不使用且不与新镜像重叠 |
| 0 | 真实 RoPE | `0x57000000` | 8,192 B |
| 1 | GU 当前层 half0/half1 | `0` / `0x01c00000` | 各 28 MiB；整体 `[0,0x03800000)` |
| 1 | GU input b | `0x10000000+b*0x00800000` | 73,728 B |
| 1 | GU output b | input base + `0x00100000` | 1,376,256 B；六槽保留区到 `0x13000000` |
| 1 | GU L 层 metadata | `0x20000000+L*0x00700000` | 7 MiB；合计到 `0x2e000000` |

Attention weights 基址须 1,024 B 对齐；Attention input/output/meta/RoPE 和 GU meta 源须 32 B 对齐。GU input/output 必须严格等于上述 descriptor slot，`buffer//3 == cohort`。不得把旧线性模式的 `0x06000000` 激活区误当本 v7 GU canonical slot。

DDR0 常驻 weights+metadata = 1,426,063,360 B（1.328125 GiB）；DDR1 常驻 metadata = 234,881,024 B（224 MiB），另有当前层 weights 56 MiB 与 canonical slots。不能因理论 32 层 GU weights+meta 总 1.96875 GiB 能放入 DDR，就宣称当前 RTL 可直接寻址执行。

首次驻留 manifest 必须绑定 bit/driver、checkpoint、artifact manifest、全部层工件 SHA、布局 SHA、真实 RoPE、加载完整范围及逐工件 C2H SHA。后续 run 只可复用同一 session 中已验证的驻留记录；进程/设备状态变化后不能仅靠旧文件假定 DDR 内容仍有效。GU canonical window 每次换层记录实际层、SHA、H2C/C2H 和新 epoch，不能在旧 lease 未释放时覆盖。

## 3. metadata、epoch 与并发生命周期

### GU inactive bank

`bank_loading` 从 LOAD 开始置位，**完整 229,376 条 metadata DMA 结束后仍保持 1，直到 COMMIT**。job admission 检查任一 bank_loading，因此在 cohort0 后预取下一层会阻止同 epoch 的 cohort1；提前 COMMIT 又会因 active bank/generation 改变而撤销旧 epoch。inactive loading 本身不门控 active bank 读：`gate_read_allowed` 只检查 active valid/address，resident quiescent 只检查响应/写流水是否排空。

**2026-10-25 实板异常后修订：取消“GU1 START 后、GU 执行中 LOAD”的策略。** 原方案在 admission 层面合法，但未覆盖的跨层并发路径在首个 full 运行触发 100 ms watchdog；单层 pilot 没有下一层预取，不能证明该路径安全。保留失败证据，不将其归因成尚无 RTL 支持的 loading→COMMIT 循环。

当前软件执行顺序：

1. 当前层 metadata 已提交，绑定 fresh epoch；依次接受两 cohort，保留既有 Attention/GU overlap。
2. GU1 必须完成全部输出 C2H、持久保存、当前验证模式要求的校验、完整 DONE 身份重核与匹配 ACK；此时 GU pending 为空、job idle/quiescent。**任何 GU 命令仍在途或 DONE 未 ACK 时，拒绝下一层 LOAD。**
3. 保存两份真实 GU 输出后启动/继续 Host Down futures；此窗口可向 inactive bank 发下一层 LOAD（`META_ACTION=1`），并与独立 DDR0 Attention 重叠。保存 LOAD 前后状态、bank/source、DMA count/bytes、开始/完成时刻，异常路径也持久化 loading owner 和时间线。
4. 等完整 229,376 records / 7,340,032 B、metadata DMA 无 busy/error；不能以 bank_loading 仍1判断 DMA未完成，也不能忽略 DMA 错误。若 Host consumer 已结束但 DMA 尚未结束，则在释放检查前有界等待。
5. 两 cohort ACK 完整、两 Host Down consumer lease 均结束、无 job pending 后释放旧软件层 lease。然后装下一层 canonical weights，COMMIT inactive bank 的 fresh generation，再绑定 fresh epoch。不能在旧 lease 未释放时覆盖当前 canonical weights 或提交新 generation。

最后一层不发无用 LOAD；跨 step 从 layer31 到 layer0 仍须完整 pair release。此方案把 metadata 传输移入 Host/独立 Attention 窗口，**不再声称隐藏于 GU 计算**。是否实际隐藏由窗口及等待时间证明。只读轮询超时/短 IO/错误保留首现场，不发下一任务或用 COMMIT/clear 掩盖。

### Attention 与 GU

SHARED 模式分别开放两个 launch，Attention 数据与 weights 走 DDR0，GU 数据/meta/weights 走 DDR1。层号没有强制同步；软件可在依赖已满足时让 Attention 层领先 GU，但每请求 `A(L) → residual/norm → GU(L) → HostDown/residual → A(L+1)` 依赖不可打乱。

新软件应把旧串行 backend 的**另一引擎 idle 假设**改为明确并发状态机，不能整体删掉 guards：

- 全局：ABI/format/capability 不变，`OWNER_STATUS(0x10c)&0x1f == 0x1b`，允许 outstanding 高位变化。`PAIRED_STATUS(0x260)` owner=3，bits2..4（switch/error/maintenance）为0；bit5 全局 quiescent 在任一引擎运行时可为0。全局故障仍立即 poison。
- Attention START：本引擎无 busy/unACK/error，本 pending 为空，地址/metadata/RoPE/layer 身份正确。允许 GU 正常 busy；不能要求 GU status 恒8或 DMA status 恒0。
- GU START/ACK：保留自身 job status、admission、epoch、generation、full DONE 和自身 paths_quiescent 判定。该信号并不要求 Attention idle。两引擎独立 DONE，不得一次 clear 清另一 pending。
- 单 IO owner 串行完成每组寄存器提交；异步 START/collect 可交错，不能两个 session 并发覆写 descriptor。每引擎至多一个 pending，命令号/请求号/buffer generation 全局单调且不复用。
- Attention 清 sticky 使用 legacy `0x008=2`，无硬件 ID-on-ACK；必须软件两次读取同 DONE 身份，完整 C2H/durable/校验后才 clear。GU 用真实 ID ACK；任何可见数值错/身份错不 ACK。
- Host Down 在完整 GU bytes 已拥有后可异步执行；保存其 layer/weights/input 身份并保留 consumer lease。CPU future 的首次异常 poison 全 session，禁止继续提交；已经接受的另一个 job仅允许受控收集、留证，不伪造已取消。

最小可执行调度：先启动 A0(L)，其完成后启动 A1(L) 与 GU0(L)；GU0 输出 copy/ACK 后提交 Down0 future，GU1 在 A1 输入准备完成后启动，同时可启动依赖已满足的下一层 A0。若 Host Down 慢或 IO owner 尚忙，记录真实等待，不人为声称“Host 及时供给”。下一层 GU 必须等旧双 cohort/HostDown 全 release 和新 canonical weights/metadata/epoch 准备。

## 4. 数学与 gold 模式

所有输入、真实 checkpoint/tokenizer、RoPE/permutation、causal padding、S24 格式及 Host norm/residual/LMhead边界沿用已验收完整推理。仍是固定16行、总前缀≤16、两真实请求、两生成步；有效最后位置 `length-1` 的 logits 决定新 token，第一 token 必须真实加入第二次完整前向。EOS/最大新 token 逻辑保持。

### Host Down 局部 FP32 dot 的精确性

仅将每 group32 的局部 `U8-zero_point` 与 W4 dot 用 CPU float32 GEMM 计算，然后立即转 int64。centered 范围 `[-255,255]`，W4 `[-8,7]`，任意部分和绝对值不超过 `32*255*8=65,280 < 2^24`；每乘积及任意加法树/FMA 中间整数都可由 FP32 精确表示。因此此局部替换无舍入损失。运行时保留 shape/range/有限且整数结果检查；禁止以混合低精度 GPU/TF32 或整矩阵浮点缩放替换。

后续仍为原整数顺序：S17 dot → code 乘积 S33 → 每 group 独立对齐 S45/F24 → int64 中的 S54 累加 → 原 half-away 舍入和 S32 饱和。不能把每 group 的右移移到全矩阵求和后。Root 的 CPU probe 已在真实层0/16/31的完整65,536输出、边界/随机/抵消和额外 scalar坐标通过，证据 `results/software_resident_root_validation/exact_dot_feasibility.json`；其 Linux 约1.73×仅为可行性，Dell速度须另测。

Host row memo 只复用同 layer、weights/meta/math SHA 且**实际该行 GU gate/up S24 bytes 完全相同**的 Down 输出；缓存键不能只有 step/行号。新行和未命中的 padding 行仍执行原数学，全部16行完整核验。该优化不改变 FPGA 的 prefix replay，也不构成 KV cache。

### 完整 gold 移出热路径

首轮固定 Hi/Hello baseline 优先采用已验收原 full run 的身份索引：`(engine,layer,inputSHA,weightsSHA,metaSHA,ropeSHA,shape,numeric_format)` → expected full output。不能按层号或旧 command_id 单独命中。在线无需重算 CPU reference，但保存输入、全输出、DONE、计时并比对 expected output SHA，成功后才重新核身份并 ACK；最终离线逐字节比较全输出和原 gold。这保留了可见首数值错不 ACK。

若用户输入没有旧 gold，明确记录 `NUMERICAL_VERIFICATION_PENDING`，可按授权 deferred 模式先完成持久 copy/身份/错误校验后 ACK，随后独立 oracle 全输出核验；正确性结果在核验完毕前不能 PASS。未知数值错误不能声称在硬件运行时已检测。任何已知错误、身份错误、IO错误或离线首次不符立即停止依赖工作，保留首错及实际 pending/已ACK事实。

### 输入传输与公开 deferred 入口

新 Attention 模式显式省略每条输入的 C2H 回读：保留完整 Host 输入及 SHA、H2C 精确长度、固定地址/descriptor、DONE 身份与完整输出核验。原 GU 基类本就只检查输入 H2C 长度，没有输入 C2H 回读。此项不记录“DDR 输入读回 PASS”；128 条 A 的 C2H 字节因此比旧 A 协议少 25,165,824 B。首次所有常驻 weights/metadata/RoPE 和每层 canonical GU weights 仍完整 C2H 校验。输出数值标准不变，deferred 模式的数值正确性仍待独立 oracle。

公开软件必须明确区分两种入口，不能把私有 Hi/Hello gold 回归称为通用程序：

- `audited_baseline`：要求原 baseline_index/model/input 身份全部匹配；查不到即在 START 前拒绝，不能静默退到其他模式。旧结果只是验证依据，推理仍执行实际 FPGA 输出和实际 Host 数学。
- `deferred`：不依赖私有 baseline_root，接收既有范围内的一般两条短 prompt、真实 tokenizer 和1–2新token，长度≤16；保持真实32层 prefix replay、两cohort、EOS/companion和lastrow规则。完整输入、输出、权重/数值来源、DONE/descriptor、copy-before-clear/ACK及首个可见错误保护都保留。运行成功的最终状态是 `EXECUTION_COMPLETE / NUMERICAL_VERIFICATION_PENDING`，不以无报错代替数值通过。
- 独立离线审计入口：复用已独立审查的 `ReferenceLayer`，对实际存盘输入分别重算每条 A/G 完整输出，核实际 Down/Host 边界与生成反馈。绑定原 run_summary SHA、source/model/manifest/真实 RoPE，要求路径/size/SHA/命令身份和完整覆盖一致；缺文件、身份漂移、数值差异均不可 PASS。覆盖数根据实际完整32层和已执行步数计算，合法早停不能硬要求固定256条。产出单独 `audit_receipt`，保留原执行结果和原始证据字节，审计通过后才能给出限定数值 PASS。

本轮先执行已知baseline的pilot，再通过无baseline依赖的公开deferred入口完成Hi/Hello全32层两步板测。独立审计工具另有CPU负向测试及两层真实pilot重算；这不等于任意prompt都已上板通过。

独立离线审计保持**严格字节标准**：FPGA A/G、原 int64 Down 与记录的 Host 边界逐字节匹配，不新增浮点容差。完整 LMhead 的 FP32 归约要求使用与原运行相同的 CPU/NumPy/BLAS 环境；跨 Windows/Linux 的 BLAS 最末位差异已有观察，不能声称跨环境逐 bit 适用。receipt 记录 `host_fp32_policy`、`audit_environment` 及实际参考源。若跨环境头部不符，保留 FAIL 并指出环境适用性；不能忽略头部、只看相同 argmax 就升级数值 PASS。完整审计可以在原 Dell 同环境离线执行，其CPU成本不计入优化推理热路径。


## 5. 分阶段验证和实测口径

| 阶段 | 必须留下的证据 | 通过范围 |
|---|---|---|
| CPU 准备 | 地址布局全覆盖/边界/错地址拒绝；meta仅GU1 ACK后规则及GU busy/DONE拒绝；两个pending的错身份、短IO、timeout、durable失败、future异常测试；Down局部精确回归 | 仅软件准备，不代表板测 |
| 驻留与 pilot | 固定 bit/driver/boot/ABI/idle；首次全部驻留工件读回；2 cohort真实层0，copy/ACK/Down/release；新地址与canonical GU实际绑定 | 有限功能通过 |
| 完整运行 | 32层×2请求×2步；128 A、128 GU、128 Down、64 release，完整输出/输入/ids/raw周期；真实反馈/lastrow/token；首错null、最终idle/pending/lease空 | 本轮限定完整功能 |
| 独立数值核验 | 所有256 FPGA输出逐字节gold、128 Down全量同原结果或独立参考、Host边界和全词表argmax/生成token；权重和source身份统一 | 数值标准未降低 |
| 软件收益 | 一次驻留时间/H2C+C2H字节，与稳态分开；GU每层重装仍计入；CPU/IO/FPGA START-DONE/等待/离线核验分别计时；真实重叠区间 | 仅测得调度与时延，不外推目标架构 |

并行收益至少保存 Attention/GU START、DONE观测、完整copy/ACK、HostDown begin/end 单机 monotonic 时间，及可用 paired counters（仅静止时更新的快照）。同一次快照两引擎 busy 可作为运行重叠证据；软件线程存在或 START 时间接近本身不足以证明硬件计算重叠。预取隐藏须比较其窗口和等待/反压，不能把已发 LOAD 当已隐藏。

吞吐按实际完成的新 token 计算；16 个物理行不是16个独立新token。分别报告首次装载、两步正式时间、离线数值验收时间；与旧约20分钟含在线gold验证wall的对比必须同列各自工作量，不能把删去验证成本写成硬件加速倍数。CPU8/8GiB、唯一设备owner、正常状态与现有 bit/driver 保持，是本轮实际约束。

## 6. 核查来源

以下均为当前源码的定向只读核查；历史物理签核状态不因此改变。

- [GU admission/epoch/canonical地址](../project/hardware/rtl/integration/hap_mlp_gu_job_control.sv)：canonical bases、固定 buffer 地址、meta_loading 拒绝、ACK条件。
- [生产core连接](../project/hardware/rtl/integration/hap_attention_mlp_production_core_gu_only.sv)：descriptor直连、GU自身quiescent、metadata loader/consumer。
- [GU A/B resident metadata](../project/hardware/rtl/mlp/hap_mlp_gu_weight_meta_resident_ab.sv)：bank_loading直到commit、inactive写入及quiescent提交。
- [GU AXI-Lite控制](../project/hardware/rtl/integration/hap_mlp_gu_axil_control.sv)：LOAD/COMMIT真实门控、状态字段。
- [Attention控制](../project/hardware/rtl/attention/hap_attention_cohort16_axil_control.sv)、[board core](../project/hardware/rtl/attention/hap_attention_board_cohort16_core.sv)：可编程地址/对齐、单库reload FSM、KV preload绑0、legacy clear。
- [Attention compute](../project/hardware/rtl/attention/hap_attention_compute_cohort16_top.sv)：固定16行及统一causal上下文。
- [SHARED mode](../project/hardware/rtl/integration/hap_v4_ddr_mode_controller.sv)、[dedicated DDR leaf](../project/hardware/rtl/integration/hap_axi512_dual_engine_dedicated_read.sv)、[data router](../project/hardware/rtl/integration/hap_axi256_dedicated_data_router.sv)：两个独立引擎地址不做layer平移，DDR1 tensor/meta共享arbiter。

## 7. 阶段验收记录

- 2026-10-25 设计核查：`CAPABILITY_REVIEW_COMPLETE / IMPLEMENTATION_PENDING`。Attention weights+meta和GU metadata驻留可实施；GU全层权重直接切base、Attention双bank隐藏、全层KV预取和独立请求row packing受固定RTL限制。工程按上述可行范围继续，实际收益尚未产生。

- 2026-10-25 软件准备集中核查：`down.py` SHA256 `940e0cd4a1a1328620a2a4158ffc66505267fea1323641f4851c65dc710d2a44` 与 Root 的真实全尺寸回归回执一致。层0/cohort0、16/cohort1、31/cohort0各两步，共6份完整输出393,216坐标匹配原实板Down；另36个独立scalar坐标、33行严格memo命中通过，未命中的新行/padding全部计算。证据为 `results/software_resident_root_validation/new_down_real_regression.json`；仅CPU数值准备，未作为Dell速度。初版layout/store/session/verification定向只读审核未见阻断：完整驻留读回与实际输入绑定gold索引已实现。异步backend/runner和本轮实板仍待集中核验。

- 2026-10-25 异步backend首轮审核：持久完整copy→expected SHA→DONE重核→clear/ID ACK次序与独立pending设计符合合同；发现并已通知工程修正一个实际竞态：GU完成可能早于metadata LOAD（START后journal/fsync有耗时），此时LOAD暂时拉低quiescent，父类立即检查DONE会误判失败。修复必须等待metadata DMA与自身路径排空，不能移除quiescent保护；增加DONE早于LOAD负面时序。另要求保留tensor/meta错误位、短IO和Attention fresh-ID检查，以及真实prefetch时刻的job/DMA状态。当前为 `BACKEND_REVIEW_FIXES_PENDING`，尚无优化板测通过结论。

- 2026-10-25 首版完整runtime集中核查：此前metadata DONE竞态、短IO/error bit/fresh A ID保护已修复；另发现的历史Future强引用保留（会累计数十GiB）已删除，weakref回收与first-future-error poison测试通过；最后一层不再无条件预取下一step，避免合法EOS留下loading。A START时间已移到journal/fsync之后。`cpu_tests_v2.stderr.txt`共9项测试通过。实际hidden来源为当前embedding→FPGA A→residual→FPGA GU→整数Down→residual，baseline仅校验，双Host consumer消费后才release旧epoch。状态 `BASELINE_SOFTWARE_PREPARATION_PASS / BOARD_PENDING`；公开deferred和offline审计路径尚待实现验收。

- 2026-10-25 实板 pilot：`PILOT_PROTOCOL_PASS_WITH_LIMITS`。AT `AT_20261025T073216.206498Z_resident_pilot`，原生进程正常exit0；实际run目录 `collected/outputs/AT_20261025T073310.209690Z_resident`，summary SHA256 `0c2b6beea9d4e34d56af29a4ade0ab423fe856c7a9b2ba16138640e92d8b8c42`。独立核归档158文件source SHA/size、129个常驻工件各自地址/尺寸/源工件SHA/C2H SHA和全部4条DONE身份/工作量/copy-before-ACK记录。首次驻留每方向1,660,952,576B、加载10.4381s；总startup73.2508s另含源/模型SHA等准备，不能把驻留加载时间当全部启动时间。实际2A+2GU+2Down、同epoch719175928/meta131，双cohort后release。GU0提交快照A status=0x19、GU status=0x201：证明两引擎任务同时busy，其中GU处于LOAD phase2；该单快照不证明两个compute phase全程重叠。HostDown0在GU1提交时仍在途。pilot仅layer0，**未覆盖跨层inactive metadata预取**；32层镜像读回通过也不等于其他31层计算已测。最终A0x18/GU8、userIRQ0/DMA0/MSI1、无pending/FPGA或Host lease、句柄关闭，driver oem117及boot保持。完整数值/Host边界和transfer核算由Root独立审计另记；本条只给上述实测协议/身份/有限并发结论。

- Root 对同一pilot的独立数值核验已通过：16个完整字节边界和4处残差闭合，见 [pilot数值回执](evidence/software_only_inference/pilot_numerical_audit.json)。当前pilot没有生成完整32层新token，不报告其token/s。


### 首个 full 的异常与恢复边界（2026-10-25）

`AT_20261025T073826.951378Z_resident_full` 原生 exit1，执行结论 **FULL_FAILED_WATCHDOG / NUMERICAL_NOT_COMPLETE**。首错材料位于该 attempt 的 `failure_first/`，后续零写只读状态为 `fault_readonly_forensics.json`。两条 Attention 和 GU0已完成；GU1 command719180037、request719180031、epoch719180032、metadata generation132 的 pending 保留，未复制未校验未ACK，旧 FPGA/Host Down lease 保留。不能把部分输出或正常关闭句柄写成 clean idle。

- GU status `0x324=0x817`：phase FAULT8、busy/completion/error/reset_required=1，quiescent=0；error `0x350=0x2200` 是默认10,000,000 core cycles 的 watchdog（100 MHz 下100 ms），不是 admission 拒绝（0x370=0）。
- 输入全部73,728 B / 2,304 beats / 128 groups；失败DONE仅44/1,792 records、33,024/1,376,256 B。compute9,991,685、store9,991,687、stall9,991,171 cycles。store/compute相互重叠，不能求和。
- 后续只读 meta DMA为229,376 records / 7,340,032 B，inactive bank loading保留（0x14c=0x12），tensor仍busy/armed（0x178=3）。这些是不同时间域的冻结DONE与后续live状态，**不能据最终meta已完成推断watchdog触发前已完成**。
- RTL的DDR1数据arbiter在一个完整metadata命令内锁住client2；GU tensor输出client1需等待。此共享传输路径能产生反压，是需隔离的新路径；当前证据不足以确定具体AXI/DDR前进性停顿原因。已排除“inactive loading直接禁止active metadata读取”的错误解释。既有9项CPU/mock未覆盖真实DDR仲裁前进性，不能用它们覆盖本次实板失败。
- driver仍oem117、固定SYS SHA，boot仍01:47:48.500Z；userIRQ enable0、DMA channel enable0（既有polling模式）、MSI1。pending userIRQ1是故障DONE源仍高，未重新启用IRQ。无主机重启或已观测驱动身份变化。

最小恢复使用已有 `0x110=2` 的单次 drain-safe maintenance 请求。Root在首错完整保全后明确授权唯一设备owner执行独立RECOVERY attempt：仅一次维护、严格保留旧DONE后精确旧ID ACK；超时/错误停止，不JTAG/PnP/boot/driver/新START。此集中决定取代此前对此次恢复的blanket禁止，不构成自动重试流程。该寄存器只请求维护，硬件须等compute/cache/meta响应、tensor transport、paired FIFO/outstanding全部安全排空后才产生 `engine_soft_clear`。`reset_required` 分支允许丢弃后续GU结果并在transport排空后清理未完成的STORE；不强制丢弃仍在途AXI事务。已有小形状integration TB覆盖BRESP fatal的同路径和保留DONE；本次watchdog能否到达安全屏障仍待实际证据。

若执行，须先持久固化原DONE全部字段与源/driver/boot身份。仅发一次维护请求并有界等待；成功条件为GU phase COMPLETE6、busy/reset_required0、quiescent1（当前错误DONE组合应为0x60e），active epoch0、metadata valid/loading与generation清零、metadata/tensor busy/armed/error清零、maintenance pending/busy清零，同时原DONE的opcode/buffer generation/epoch/meta generation/command/request/cohort/layer/error/bytes/records/counters逐项不变。`0x178` 不可要求整字为0：bits[9:7]是job phase，因此维护后COMPLETE6的稳定值为`0x300`，精确ACK后IDLE才为0；bits[12:10]为meta phase，低5位为busy/armed/error，均须0。`0x2a8`须0，`0x260`须回SHARED且paired quiescent的`0x23`。maintenance同时清Attention metadata/RoPE，故此阶段A status预期0、Aerror0；`0x10c`预期`0x3b`，其中bit6是被维护请求清掉的owner_done历史位，bit5 request_ready仍为1，不能误要求旧`0x7b`。control userIRQ enable须保持0，IRQ pending只记录实际值，不写清或凭未知锁存语义要求随源立即下降。之后才可在独立恢复流程以 `0x2a0=719180037` 精确退休这条**失败任务**，检查idle8和无pending；ACK不清旧DONE payload，因此0x350仍为0x2200是合法历史，DONE.error只在completion_valid=1时代表当前完成，busy/error/reset/admission/DMA/maintenance保护仍保留。禁止用正常推理backend把它当成功copy/ACK。旧运行永久FAIL，驻留/epoch/session信任作废，下次完整重新加载和读回。

若安全屏障有界超时或出现新错误，停止，不循环维护、不强清、不切mode、不新backend掩盖。必要时可另由Root协调复用固定同SHA bit的易失SRAM重载：现成 `program_and_probe.ps1` / `program_sram.tcl` 固定80,159,259 B、下载线210308B76D50和xcvu9p_0；随后只读配置/ABI，确需PCIe恢复才复用 `recover_pcie.ps1` 精确9018实例scan/restart。该fallback不修改bit内容、不写Flash、不安装driver、不重启Dell；它尚未在本次执行，不能提前标恢复成功。


- 2026-10-25 公开离线审计准备：Root新增 `deploy/optimized/offline_audit.py` / `tests/test_optimized_offline.py`，定向只读审核未见现有范围的阻断；独立重算实际A/G、原int64 Down和Host输入/残差/反馈，不消费旧baseline输出。路径限制、实际payload SHA重核、执行源快照/vendor/model绑定、覆盖/lease检查和独立新receipt保留原summary均已核。5项CPU测试通过；Root对原layer0真实pilot完成2A+2GU+2原Down+6处Host边界独立审计，35.50s PASS（07:56:30Z）。此pilot无LMhead/生成，不扩写为完整32层或跨平台FP32验证通过；完整头部保持上述同环境严格字节要求。generic运行CLI仍由工程接入，板核心首错状态不被本CPU结果覆盖。


- 单次维护实际阶段：`AT_20261025T075735.238950Z_drain_safe_recovery` 已执行且只执行 `0x110=2` 一次。07:58:27Z回收的before/after及原始event独立复核：GU从0x817到0x60e，meta/generation/epoch全部0，DMA0x300、maintenance0、paired0x23，旧DONE328..364全部16字段保持（包括error2200与原身份/bytes/counters）。硬件安全维护已完成；工程额外沿用A18/owner7b断言误拒合法A0/owner3b，故该脚本native失败但**没有发ACK**，原回执`RECOVERY_FAIL_STOP`保留。RTL确认A的engine_soft_clear清meta/RoPE、0x110清owner_done；Root已协调仅ACK-only续完原授权退休，不重复维护。最终退休尚待实际回执，不能提前写clean idle。


- 失败任务退休实际闭合：同RECOVERY AT的 `single_failed_ack_only.stdout.txt` / `retirement_receipt.json` 记录08:00:04–08:00:07Z仅一次 `0x2a0=719180037`，未再次维护或新START。独立复算 before/after 全16个DONE字段不变，身份/driver/boot完全一致，末态GU8、DMA0、epoch/meta/generation0、A0/error0、owner3b/paired23，userIRQ enable0且pending实际降0，句柄关闭。结论 **RECOVERY_PASS_FAILED_TASK_RETIRED**；原full永久失败，原Host leases随失败batch废弃，不冒充成功消费或数值PASS。首次维护脚本的过严guard失败与其原字节保留。本次无需JTAG、PnP、driver更换或Dell重启。

- 后继验证集中安排：修复版2层pilot使用 `audited_baseline` 覆盖一次真实跨层LOAD/COMMIT；干净完成后，正式32层/two-step使用公开默认 `deferred` 模式，同Hi/Hello但不传、不读取私有baseline root/index。其原summary须保持 `NUMERICAL_VERIFICATION_PENDING`；Root在单独receipt中对实际全部输入/model/weights/RoPE身份、已独立审查gold全字节、Down/Host边界/反馈和最终状态集中核验后，才能对该次运行给出限定数值PASS。旧baseline只在事后审核使用，不能作为运行输入或预测输出。此安排不把已知prompt结果扩大为未知prompt实测；未知合法prompt仍由同环境独立ReferenceLayer审计入口验收。


- 修复版 v2 集中静态审核：`resident_interleaved_post_ack_metadata_v2` 的 `backends.py/run.py/verification.py/device_health.py` 与 `scalellm.py resident/offline-audit` 接线已核，结论 **V2_PREPARATION_PASS_WITH_BOARD_PENDING**。START hook不再触发metadata；仅内部stage首次LOAD，或pending空、双cohort已copy/ACK、GU quiescent的post-pair LOAD。Down1 future先提交，metadata等待期间两Host消费者lease仍保留，新COMMIT/epoch在旧双消费者退休后。恢复后的owner3b及invalid DONE历史error按真实RTL语义判读，其他错误/身份/资源保护未删除。默认deferred不实例化GoldCatalog、不读取baseline root/index或其SHA，实际A/G/Down比较字段与最终summary均明确待数值验证，输入仍来自真实模型与本次FPGA输出。执行源身份包含CLI/device_health和全部optimized源，deployment config另有SHA。工程19项CPU回归通过，Root offline v2/EXECUTION_COMPLETE覆盖6项测试通过；这些是软件准备，通过后按既有授权连续Windows核验、2层pilot及deferred full，不把静态或mock结果写成板测通过。


- v2两层实板pilot集中验收：**TWO_LAYER_POST_ACK_PREFETCH_PASS_WITH_LIMITS**。AT `AT_20261025T080914.081780Z_resident_pilot`，实际run `collected/outputs/AT_20261025T081020.381906Z_resident`，summary SHA256 `4b1cfcc7d4f4adf72f093d1ed1cb76cd82e2c6b34968002bc91c65aef374176a`。独立核实际application.zip中12个运行源/索引身份与133个vendor文件全部SHA/尺寸，原生PID11496自然exit0。4A+4GU+4Down、2epoch release、8完整输出bytegold；Root另核32个完整数值边界、8处残差及身份通过。两层generation1→2、epoch719184136→719184144，全部DONE工作量/command/request/cohort/buffer/layer/epoch/generation一致；4GU均1792 records/1,376,256 B且error0。

  下一层metadata LOAD的monotonic时刻22978.8291669，晚于旧GU0/1 ACK的22978.0434739/22978.8002082；Down0/1分别在22978.0857871/22978.8287766开始，结束于22979.2430710/22979.7902488，故LOAD实际发生在两个Host任务在途时。两份metadata均严格229,376 records、7,340,032 B，第二次COMMIT为22980.3883621，晚于两旧Down结束；新epoch/层1命令与generation2吻合。两次GU0提交快照A busy且GU phaseCOMPUTE4（0x401），证明本次两个引擎任务真实重叠；A状态没有phase细分，仍不把单快照扩写为全程compute重叠。

  **计时局限：** v2的`wait_metadata`在预取与下一stage重复调用，`dma_complete_observed_s`被第二次观测覆盖；不能用它减LOAD时刻作为DMA时延。本次根据冻结控制流，首次DMA等待已在下一层A0 START22979.5245190前结束，该START仍早于Down1结束，因此支持metadata在该Host Down窗口内完成的有界推断；首次完成观测精确值未保存。此缺口不影响完整count/bytes、ACK顺序或数值验收，不为此重复板测。

  运行正式部分6.8649702s，总startup22.6847299s（包含来源/模型核验和驻留等），不是完整模型token吞吐。最终A18/GU8、owner3b/paired23、meta generation2、当前epoch合法保留但无软件lease/pending，userIRQ/DMA enable0、MSI1、request/pending0、句柄关闭，driver/boot不变。首次恢复后的invalid旧DONE error2200被正常新成功DONE覆盖为0；没有为了启动而写清历史。公开deferred full在本次pilot干净完成后按既有授权独立运行，尚不在本条PASS范围。
