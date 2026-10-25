# M006 GU-only 工程验证版：有界上板验证计划

日期：2026-10-25。角色：架构与验证策略。项目根：`/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM_MLP_fix`。

本轮交付是准备与合同核查；本作者未配置 FPGA、未写设备、未运行 EDA。用户最新指定工程验证版 `.bit`，说明 Dell 通过 PCIe 接 VCU118 并要求准备上板；该当前指令优先于旧文档中的板卡范围限制。后续按本计划与实际设备依赖推进，不另设逐项用户批准流程。冻结 manifest、RTL、ABI 和原始结果保持原身份。Max-DPO、external reset 签核仍 OPEN；一次板测成功也不将其改成完整物理签核。

| 维度 | 当前记录 |
| --- | --- |
| execution | 本计划已准备；实际编程、DMA 和 GU 数值板测 NOT_RUN |
| verdict | PREPARATION_ONLY；仅证明下列接口/地址/验证方法可定位 |
| applicability | 指定 GU-only v7 工程验证版、生产 N14336/K4096/cohort16 |
| review | 本角色交付父主控集中整合；不冒充用户最终验收 |

## 1. 已核身份与资源

- bit：`project/hardware/vivado/reports/m006_gu_AT003_preliminary_bitstream/native_output/ScaleLLM_MLP_GU_only_ENGINEERING_VALIDATION.bit`。
- 本轮本地实际读取校验：80,159,259 B；SHA256 `66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47`。
- bit 头：`scalellm_vcu118_f05_bd_wrapper`，part `xcvu9p-flga2104-2L-e`，Vivado 2025.2，生成头日期 `2026/10/25 08:44:57`。UserID 为 `FFFFFFFF`，不能当作唯一板上版本证明；用本次实际下载日志、文件 SHA 和 CSR ABI 联合绑定。
- 来源：`project/E013_mlp_linear_only_hardware/experiment_results/runs/R008/attempts/AT003_preliminary_bitstream/bitstream_manifest.json`。其中旧 `NOT_FOR_BOARD_DOWNLOAD` 是生成时范围；保留原文，当前新增授权记录不改写历史 manifest。
- Root 本轮文件预检：`project/E013_mlp_linear_only_hardware/experiment_results/board_validation/bitstream_preflight.json`。Dell 实况以工程本轮原始采集为准；父主控报告已经发现 PCIe/XDMA 及 FTDI USB `0403:6014`、序列号 `210308B76D50`，这些不等于 JTAG 已成功识别 FPGA。
- 轻量 Host 准备/参考生成最多 8 CPU、8 GiB；全项目重 EDA 仍唯一 owner、32 CPU/192 GiB、native 8 threads。本任务不启动第二 EDA，不影响现有资格查询或其他任务。

## 2. 分阶段执行和停止条件

| 阶段 | 有界动作与通过标准 | 失败时停在哪 |
| --- | --- | --- |
| P0 本地/Dell 准备 | 本地与 Dell 文件 SHA/大小一致；保存 OS、工具、驱动、设备实例、路径及传输代码身份；准备每次独立日志目录 | 文件不匹配、目标设备不唯一时停止设备操作，离线准备继续 |
| P1 JTAG 只读发现 | 用 Dell 同版本 Vivado/hw_server 枚举 cable/target/device；记录 cable serial、device IDCODE/part，匹配 VU9P 目标且不能误选链上其他器件 | 发现空链、part 不符或目标不唯一，保存日志并结束本次 probe；不循环等待 |
| P2 实际配置与 PCIe 重发现 | 本阶段执行时才记录 program 操作；指定已核 bit、确认配置结果并采 PCIe 枚举/资源/驱动；重配置前关闭本任务旧设备 handles，之后重新打开 | 下载失败、PCIe 未重新出现、BAR 未分配或驱动异常即停止；重扫/重启需求按实际症状记录，不自动反复重配 |
| P3 只读 CSR 与 readiness | 下表所有身份逐项相等，状态无 busy/未 ACK DONE/fault；DDR 门控链资格按下文记录；连续三份稳定快照，无驱动超时 | ABI 不符不得写任何 CSR/DMA；校准/复位未就绪停止，保留具体读失败与状态 |
| P4 有限 scratch DMA | 独占板卡且 idle；两 DDR 各一页读备份、写不同模式、读回逐字节一致并核另一通道未变，最后恢复原页；记录实际地址/bytes/hash/返回数 | short I/O、超时、别名或 mismatch 保留原始失败；不进入 GU、不硬复位掩盖现场 |
| P5 最小生产 GU | 先一个完整生产尺寸命令，独立 gold 全输出逐字节比较；之后第二 cohort 验证可 ACK/可复用，两个完成都保持独立身份 | 元数据、准入、DONE、数值任一失败停止新提交，保存首错/owner/计数及输出 |

P0/P1 是当前准备阶段；P2–P5 只有实际执行并具备证据后才可标 PASS。常规设备发现单次调用上限 30–60 秒，ready 总等待上限 30 秒；Host CSR/小 DMA 单请求上限 5 秒，GU/metadata 等待默认沿用 backend 的 10 秒。遇实际依赖缺失即结束本次尝试，不以反复延时取代诊断。这些是板卡测试的有界等待，不修改现有正常 EDA 的停止政策。驱动阻塞必须有 transport 层可取消 I/O/超时；仅外层 Python polling deadline 不能中断一个已阻塞的系统调用。

Dell 目前只有 Vivado/hw_server 2022.2（父主控当前采集）；bit 由 2025.2 生成。优先实际只读识别目标及工具读取文件结果，再记录下载兼容性；版本不同本身不构成必须安装新工具的证据。JTAG/PCIe 是两条独立链路，PCIe 已枚举与 FTDI 已出现均不替代 P1。

## 3. PCIe、CSR 和 DDR readiness

构造脚本与生成 XDMA XCI 一致：PCIe `10EE:9018`，Gen3 x8 能力，1 H2C/1 C2H、AXI Memory Mapped；BAR0 1 MiB/64 bit，BAR2 4 GiB/64 bit。记录实际 negotiated link 与 Windows PnP problem code、驱动版本、资源分配；链路降速单列性能限制，不凭此否定基本功能。4 GiB BAR 分配失败是实际前置阻塞。Driver 的 `user`、`control`、`h2c_0`、`c2h_0` 必须按该安装版本映射核实，不能把 XDMA configuration/control 节点当成应用 CSR。

| 应用 CSR offset | 必须读到 |
| --- | --- |
| `0x000` / `0x004` | Attention format `0x48384103` / ABI `0x00020000` |
| `0x100` / `0x104` | MLP format `0x48384605` / GU-only ABI `0x00070000` |
| `0x2b8` | Memory layout `0x4d303032` |
| `0x300` / `0x304` / `0x308` | Linear ABI `0x4d4c0002` / capabilities **exactly `0x1d`** / buffer layout `1` |
| `0x324` | bits[4:0] = `0x08`：idle、quiescent、无 completion/error/reset_required；保留高 phase bits |
| `0x10c`, `0x14c`, `0x178`, `0x260`, `0x2a8`, `0x350`, `0x370` | 保存 owner、metadata、DMA、paired、maintenance、DONE error、admission 原值；无 active/fault/maintenance。owner readiness 见 backend 的 bit5；SHARED mode 尚未写入属于正常准备态 |

`weight_layout=0x57344635` 来自权重文件合同，**不是可读硬件 CSR**；backend 填入该常量不构成板上读回证据。旧 `scalellm_board.py` 的 v5 ABI 常量不可用于本次通过标准。

当前未发现独立 `DDR_CALIB` 应用寄存器。`create_mlp_gu_board.tcl:471` 将两路 `init_calib_complete && !ui_clk_sync_rst` 经 `hap_v5_dual_async_ready_gate_xpm` 独立同步，并共同门控 core reset；因此本版本稳定正确 CSR 响应及 idle/owner-ready 是**基于该绑定设计的 readiness 推断**。如果实际 Hardware Manager 能发现 MIG 调试对象，可额外记录两路原生 calibration status；不能伪造不存在的探针。若 CSR 没响应、全零/全 FF 或状态反复复位，保持 DDR_READY_UNCONFIRMED，禁止先发 DMA“试试看”。一次可读/一次 DMA 成功不证明完整 external reset 协议签核。

## 4. scratch 地址安全依据

Host DMA 映射为 DDR0 `[0,0x80000000)`，DDR1 `[0x80000000,0x100000000)`；engine/descriptor 始终使用 local address。`local_to_host(1, local)` 只在 transport 边界加一次 `0x80000000`。

本次独占诊断临时保留两路 **local `0x7fff0000..0x7fff0fff`（4 KiB）**，对应 Host `0x7fff0000`、`0xffff0000`。依据是构造脚本每通道 2 GiB 的真实映射，以及 `scalellm_memory.py` 的 Attention/MLP 权重、KV/activation/metadata/ROPE 分配和 GU ABI 的六个 tensor slots 均不占该页；GU tensor slots 总区间为 `[0x10000000,0x13000000)`。这不是全应用永久空闲区承诺：运行前必须取得本次板卡独占使用并确认没有另一个 Host/DMA owner。未获得独占时只完成 P3。

首测每通道 4 KiB，256/512-bit 总线对齐，固定地址且不跨 2 GiB 窗口；两路写不同、按地址变化的模式，并读回两路检查别名。先保留原页再恢复；失败时保留备份及失败页，不无界读写或覆盖权重/metadata/tensor 区。Windows 必须使用 64-bit unsigned address 语义，避免 `0xffff0000` 被解释为负 32-bit offset。驱动支持与缓冲区对齐按实际 API 确认，未经证明不任意套用 Linux scatter/gather 假设。

## 5. 最小生产命令、输入与独立 gold

生产图固定 `16 × 4096` 输入、128 groups、Gate/Up 各 14336 列；最小命令仍需 73,728 B REC576 输入、1,376,256 B GU interleaved S24 输出、1792 records。GU 权重两个逻辑 half 各 29,360,128 B，均在物理 DDR1，local base `0` 与 `0x01c00000`；metadata 为 229,376 × 32 B = 7,340,032 B，28 B 有效字段、末 4 B 必须零。metadata bank0/1 装载基址沿用 `0x06800000` / `0x07400000`。不能以 N128 仿真尺寸、零长度或跳过 metadata 降低生产命令尺寸。

复用 `GuOnlyXdmaBackend` 的先后次序：只读 discover → idle 检查 → owner ready 后写 SHARED request `0x108=3` → 验证文件 hash/size/padding → H2C 两份 GU 权重及 inactive bank metadata → LOAD/等待真实 loading 转换与准确 count → COMMIT/generation 校验 → 绑定 layer/epoch → H2C REC576 → 写完整 17-word descriptor → START `0x320=1` → 读 admission `0x370` → 等待 DONE。不能把写返回长度当作命令已接受。

首 descriptor 可用 command/request `1/1`、layer `0`、cohort `0`、buffer `0`、buffer/meta generation 与 epoch 均非零且匹配实际 COMMIT，opcode 为完整 32-bit `1`，Down 地址为零；input local `0x10000000`，output local `0x10100000`。第二 cohort 用独立 command、buffer `3`（input `0x11800000`，output `0x11900000`），保持该 layer/epoch 直到两个结果均 ACK/排空。单命令阶段结束可保留现有 lease；不能强行调用要求两个 cohort 的 `release_gu_layer()`。

数值输入分为三项，全部完整生产形状：

1. 可选全零 smoke：只证明数据通路、尺寸、输出零与 completion；不作为非零算术证据。
2. 主用结构化非零/异号：group0/127、row0/7/8/15、两 matrix、两个 logical half 与尾 block/column14335 均安排不同标记；其余坐标合法零。按 group-major/half-group 的原 exporter 布局写完整文件。用稀疏非零 group 的解析整数公式生成**所有输出**，无需执行完整密集 CPU GEMM；检查左右 shift、负数 arithmetic shift、half-away-from-zero 及饱和边界。
3. S37 guard 补充：合法 total_shift=20 与大 code 产生超过 S36 正负范围、仍在 S37 的中间值；设计大项抵消后保留小非零结果，避免最终 S24 饱和掩盖截位。例如 q−zp=255、activation/weight code=255，8 个 group 的 w=+7 与 7 个 group 的 w=−8 在所有32项相同的情况下严格抵消，再由另一 group 注入可解析小量。逐 group 独立验证 S17 dot、S33 raw、S37 guard/S44 sum，不生成非法 overflow 用例混作通过标准。此为待物化用例，尚无本轮数据文件/PASS。

独立参考公式：`dot=sum32((q-zp)*w_s4)`；`raw=dot*a_code*w_code`；GU `total_shift` 合法 20..44，`guard=raw << (24-shift)` 或 signed `raw >> (shift-24)`；128 groups 精确累加到 S44，最后 half-away-from-zero shift8 并 saturate S24。gold 不读取 DUT 输出反推。完整输出按 `G0,U0,...,G895,U895`、每 record 的 row/16-column/little-endian S24 顺序逐字节比较，并单独输出第一处坐标差异；先复制完整输出再 ID ACK。

DONE 必须逐项匹配 opcode、command/request/cohort/buffer/layer、generation/epoch，`DONE_ERROR=0`、input bytes=73728、output bytes=1376256、records=1792，status completion_valid/quiescent=1 且 busy/job_error/reset_required=0。ACK 后 DONE 清除并恢复 idle；数值 failure 即保留证据，不运行 Host Down/Attention 来掩盖失败。P5 至多支持该 bit 的 GU 板级局部功能；完整 32 层、Host Down 性能、模型精度与 reset 故障恢复另有范围。

## 6. 可复用物料与当前缺口

| 已有物料 | 可复用内容与限制 |
| --- | --- |
| `project/hardware/source/mlp_linear/abi_gu_only.json` | 唯一当前 v7 数值/地址/CSR 合同；不改冻结 schema |
| `project/hardware/host/scalellm_mlp_gu_only_backend.py`、`scalellm_mlp_gu_only_runtime.py` | descriptor、metadata/epoch/ACK 与错误保留；直接 `run_gu` 可独立于 Attention/Host Down pipeline |
| `project/hardware/host/scalellm_mlp_linear.py` | REC576 pack/unpack 与生产 GU output decode；diagnostic payload 仍须满足 canonical zero/padding |
| `project/hardware/model/export_scalellm_llama31_artifacts.py` | 原 `_write_mlp_tile` 权重布局；不能临时更换已有真模型权重语义 |
| `project/hardware/data/mlp_linear_compute/gu128_gold.mem`、`project/hardware/model/generate_mlp_linear_compute_vectors.py` | N128/full-K 独立参考数学与小矩阵；不是本 bit 的完整输入/输出包 |
| `project/E013_mlp_linear_only_hardware/experiment_results/host_reference/integration_gold/` | 独立整数 `scalar()`、固定 literals/manifest；原 generator 含 Linux affinity/resource 操作，不直接在 Windows 运行 |
| `project/hardware/tests/test_scalellm_mlp_gu_only_backend.py` | scripted transport/身份/计数/short-I/O 测试；zero fixture 与 mock DONE 不构成真实板测或生产权重 gold |

本轮尚缺：已识别 FPGA 的 JTAG 回执、实际 program 证据、Windows transport 的真实 driver 绑定与取消/超时证明、完整生产诊断包/独立 gold 及 manifest。`GuOnlyArtifactManifest.load()` 对原 32-layer catalog 做严格 schema/尺寸/身份检查；一个诊断 layer 不应冒充真模型 catalog。工程可使用独立明确标注的诊断 artifact provider/manifest 来接现有 backend，但须保持每个记录的 hash/size/padding 校验，不能放宽生产 loader。当前定向核查只找到已有 N128/Host 测试物料，未证明存在可立即上板的真实完整权重包。

Linux `XdmaSession` 直接依赖 `/dev/xdma*`、`os.pread/pwrite/preadv`、`O_SYNC`；Windows 需要实际已装驱动的 device interface 枚举、CreateFile/ReadFile/WriteFile 或已有可信 utility 桥接，并保持 4-byte little-endian CSR、64-bit offset、精确字节计数、线程串行锁、短读写失败语义及有界 I/O。更换 transport 不改变 ABI；Python/numpy CPU算法可复用，WSL 存在本身不证明 Linux `/dev/xdma*` 可达。

每次实际尝试在 `experiment_results/board_validation/` 下新建身份目录，记录命令/退出码、原始 stdout/stderr、时间、工具/driver/device/cable 身份、bit/脚本/输入/gold SHA、CSR before/after、DMA 数据与比较、首错和各阶段 PASS/FAIL/NOT_RUN。准备报告与实际运行报告分开，保留失败现场且不覆盖旧证据。
