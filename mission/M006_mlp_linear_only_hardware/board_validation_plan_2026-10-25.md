# M006 GU-only：上板准备与有界验证计划（2026-10-25）

范围：用户指定工程验证版 bit、Dell 通过 PCIe 接 VCU118，要求准备上板。最新指令优先旧板卡禁区；按实际依赖连续推进，不另设逐项批准流程。本轮仅准备/只读发现，实际编程、DMA、GU 数值板测 **NOT_RUN**。Max-DPO、external reset 签核仍 OPEN；冻结 manifest/RTL/ABI/原始结果不改。

状态分开记录：execution=准备完成；verdict=PREPARATION_ONLY；applicability=下述 GU-only v7 bit、生产形状；review=交父主控集中整合，非用户最终验收。详细源证据与接口说明见[有界合同核查](../../project/E013_mlp_linear_only_hardware/experiment_source/gu_only/board_validation/contract_review.md)。

## 文件、设备与资源

- bit：`project/hardware/vivado/reports/m006_gu_AT003_preliminary_bitstream/native_output/ScaleLLM_MLP_GU_only_ENGINEERING_VALIDATION.bit`。
- 本地实核 **80,159,259 B**，SHA256 **`66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47`**；头部 part `xcvu9p-flga2104-2L-e`、Vivado 2025.2。原 manifest 的 `NOT_FOR_BOARD_DOWNLOAD` 保留为生成时范围，不能改写为完整签核。
- 父主控最新回报：已复制 Dell `C:\Users\dell\ScaleLLM_board_validation\M006_GU_66a305348d30_20261025`，远端 SHA/大小匹配；PCIe/XDMA 与 FTDI `0403:6014`、serial `210308B76D50` 已发现。Vivado/hw_server 2022.2 已完成只读 JTAG 探测：target `localhost:33121/xilinx_tcf/Digilent/210308B76D50`，唯一 device `xcvu9p_0`、PART `xcvu9p`、IDCODE `14B31093`；两次原生 exit0，自有服务已清理。原始证据见 [JTAG 回执](../../project/E013_mlp_linear_only_hardware/experiment_results/board_validation/host_preflight/20261025T010223.461182Z_jtag/receipt.json)。
- Host 轻量准备最多 8 CPU/8 GiB；全项目仍单重 EDA、32 CPU/192 GiB/native 8 threads，不占第二 EDA、不影响其他任务。工具 2022.2/生成版本 2025.2 不同本身不证明不兼容；按真实 part/文件读取/下载结果判断，不凭空要求升级工具。

## 阶段与通过标准

| 阶段 | 执行动作与通过标准 | 实际停止边界 |
| --- | --- | --- |
| P0 准备 | 本地/远端 bit SHA一致，保存工具/OS/driver身份和测试入口 | 文件身份不符、目标不唯一 |
| P1 JTAG只读 | 记录 cable serial、FPGA IDCODE/part，唯一正确 VU9P 目标 | 空链、part不符、目标歧义；本轮只读发现 PASS |
| P2 配置/PCIe | 执行时才记录 program；配置成功，关闭旧handles并重发现/重开设备 | 下载失败、设备消失、BAR未分配、driver错误，不反复重配 |
| P3 只读CSR/readiness | 下述身份完全匹配，三份稳定快照，idle、无pending DONE/fault/maintenance | ABI不符或DDR/core未就绪，禁止写CSR/DMA |
| P4 scratch DMA | 独占板卡，两DDR各4KiB备份→不同模式写入→双路逐字节读回/无别名→恢复 | short I/O、timeout、mismatch；保留现场，不进入GU |
| P5 生产GU | 完整尺寸输入、metadata/epoch/descriptor；全输出独立gold一致、DONE身份/计数正确、copy后ACK；第二cohort验证复用 | 首错/owner/输出保留，停止新提交，不硬复位掩盖失败 |

当前 P0/P1 准备与只读发现已完成；P2–P5 未执行。发现/就绪总等待有界30–60秒；CSR/小DMA单请求5秒，metadata/GU沿用backend默认10秒；timeout后结束该尝试并诊断，不无限等待。transport必须支持可取消/超时I/O；外层Python deadline不能中断阻塞系统调用。这些边界不改变既有正常EDA停止政策。

## PCIe、CSR 与 DDR

生成XDMA XCI：**10EE:9018**，Gen3 x8能力，1 H2C/1 C2H，AXI-MM；BAR0=1MiB/64bit，BAR2=4GiB/64bit。记录实际link、PnP problem code、driver、BAR分配；核实安装驱动的user/control/H2C/C2H endpoint映射，不能误把XDMA配置节点当应用CSR。

| CSR offset | 期望值 |
| --- | --- |
| `000/004` | Attention `48384103/00020000` |
| `100/104` | MLP format/GU ABI `48384605/00070000` |
| `2b8` | memory layout `4d303032` |
| `300/304/308` | linear ABI/caps/buffer layout `4d4c0002/0000001d/1` |
| `324` | bits[4:0]=`08`，idle/quiescent，无DONE/error/reset_required |

另保存`10c/14c/178/260/2a8/350/370`的owner/metadata/DMA/paired/maintenance/首错状态。`weight_layout=57344635`是文件合同而非可读硬件CSR。旧v5 `scalellm_board.py` 常量不能用于本次验收。

当前没有已发现的独立DDR_CALIB CSR。构造脚本将两路MIG `calib && !ui_reset`分别同步后共同门控core reset；稳定正确CSR+idle/owner-ready是**绑定该设计的ready推断**。若实际Hardware Manager有MIG调试对象，再采直接calibration状态；无响应/全零/全FF/反复reset时标UNCONFIRMED，不先发DMA。该检查不闭合external reset签核。

scratch临时保留两通道local **`7fff0000..7fff0fff`**，Host为`7fff0000`、`ffff0000`。依据2GiB/channel真实映射及现有权重/KV/activation/metadata/ROPE和GU六槽`[10000000,13000000)`均不占该页。仅在独占且无其他DMA/运行lease时成立；不是永久空闲承诺。Windows须用64bit offset；DDR1 aperture `80000000`只在transport加一次。

## 最小生产GU与gold

生产形状固定16行/K4096/128groups/N14336，输入 **73,728 B**，输出 **1,376,256 B/1792 records**。两GU weight half各29,360,128 B，均DDR1 local `0/01c00000`；metadata **229,376×32 B=7,340,032 B**，每record末4 B为零，bank0/1 base=`06800000/07400000`。N128仿真向量不能直接提交给该bit。

复用`GuOnlyXdmaBackend`：discover/idle→owner-ready后SHARED→验证artifact→H2C→inactive metadata LOAD/count/COMMIT→fresh epoch→REC576→17-word descriptor→START→admission→DONE→C2H完整复制→ID ACK。首命令layer/cohort/buffer=`0/0/0`，input/output=`10000000/10100000`，opcode完整32bit=1，generation/epoch非零、Down地址0。第二cohort用buffer3、独立command，input/output=`11800000/11900000`；两个cohort都ACK后才能调用现有release接口。

gold保持完整形状，可用结构化稀疏/常量数据避免密集CPU成本：全零只作可选传输smoke；主例用非零/异号、group0/127、row0/7/8/15、两matrix/half及尾列14335标记，解析生成全部输出。S37另安排合法大项抵消后小非零输出，避免饱和掩盖截位：例如q−zp=255、a/w code=255、shift20，8个group的w=+7与7个group的w=−8严格抵消，再注入小量。独立检查S17 dot→S33 raw→S37/F24 guard→S44全128组和→half-away shift8→S24饱和；不读DUT反推gold。

输出按G0,U0,…,G895,U895 little-endian S24逐字节比较。DONE全部身份/generation/epoch匹配，error0、input73728/output1376256/records1792，busy/error/reset_required0、completion/quiescent1；ACK后idle。通过只支持该GU板级局部功能，不覆盖32层/Host Down性能/模型精度/故障reset签核。

## 可用物料与 NOT_READY

可复用：`abi_gu_only.json`、`scalellm_mlp_gu_only_backend.py/runtime.py`、`scalellm_mlp_linear.py`的REC576/output codec、原exporter `_write_mlp_tile`布局；`data/mlp_linear_compute/gu128_gold.mem`与`experiment_results/host_reference/integration_gold/`提供N128/full-K独立公式及literals。Host backend测试的scripted transport/mock DONE不构成板测。

**NOT_READY**：Windows真实transport及取消/超时证明、完整生产诊断输入/gold/manifest；实际program仍NOT_RUN。尚未证明可立即使用的真实模型权重包。诊断layer须独立标识，不能伪装成严格32-layer生产catalog或放宽hash/size/padding校验。

Linux `XdmaSession`依赖`/dev/xdma*`与`os.pread/pwrite/preadv`；Windows需实际driver API或可信utility适配，保留4B little-endian CSR、64bit offset、准确计数/short-I/O失败、串行锁与超时。WSL本身不证明PCIe设备可达。每次实际运行新建`experiment_results/board_validation/`尝试目录，保存命令/退出码/原始日志、设备工具身份、所有输入SHA、CSR before/after、DMA/输出比较与分阶段PASS/FAIL/NOT_RUN，保留失败证据。

## 实际执行授权补充

用户后续要求远程操控 Dell 进行测试，本轮进入 P2–P5 实际执行；仅在前置通过后继续下一依赖步骤，普通适配和验证无需逐项批准。板测状态按新实际证据更新，以上“本轮仅准备/只读发现”保留为上一轮记录。指定 bit、既有数值合同、范围与资源保护保持；不自动重启 Dell、装驱动或写 Flash。


## 本轮实际结果

P2加载、P3恢复后只读CSR、P4双DDR页回环、P5结构化和S37两例各两个cohort均已实际PASS。四命令全输出5,505,024B/1,835,008个S24与独立gold逐字节一致，ACK后idle。见[执行总结](../../project/E013_mlp_linear_only_hardware/experiment_results/board_validation/execution_summary.md)。

BAR文字补正：生成XCI保留BAR2=4GiB的声明参数，运行观察为Windows1MiB+64KiB资源；H2C/C2H的4GiB AXI地址空间与PCIe MMIO BAR不是同一对象。按本轮真实CSR/DMA读回验收，不把OS分配4GiB BAR当作额外阻断，也不擅改原XCI。
