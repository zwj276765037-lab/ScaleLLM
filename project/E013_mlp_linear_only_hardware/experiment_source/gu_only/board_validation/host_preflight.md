# M006 GU-only Dell / VCU118 上板准备

后续实际执行已完成，当前结果见 [host_execution.md](host_execution.md)。下文保留本次实际编程前的预检记录与当时 NOT_RUN 边界。

本子任务为工程环境预检与可逆文件准备。实际执行了 Windows 系统/PnP/驱动/工具只读查询、文件暂存和 JTAG 链枚举；未执行 `program_hw_devices`、复位、驱动安装、PCIe 读写或板上计算。Root 负责 M006 测试合同、ABI/CSR/gold 和 bitstream 签核边界，本文件不改变它们。

## 当前结果

| 项目 | 已核实事实 | 原始证据目录（相对 E013） |
| --- | --- | --- |
| 主机 | `hap-dell`，`DESKTOP-D3`，Dell OptiPlex 7000，Windows 10 Pro 19045 x64，PowerShell 5.1 | `experiment_results/board_validation/host_preflight/20261025T005913.159854Z_device/` |
| PCIe | PresentOnly 设备 `PCI\VEN_10EE&DEV_9018&SUBSYS_000710EE&REV_00\4&3533FCBB&0&0008`，Xilinx DMA，Status OK，Problem/ConfigManagerErrorCode 0 | 同上 `data.json` |
| 驱动 | `XDMA` 和 `FTDIBUS` 服务 Running。XDMA provider Xilinx，version `11.38.8.505`，INF `oem113.inf`。注册表有对应 XDMA 设备接口；未用 CreateFile 打开通道 | `experiment_results/board_validation/host_preflight/20261025T005913.160433Z_interfaces/data.json` |
| USB | 首轮未出现候选；开机后复查出现 `USB\VID_0403&PID_6014\210308B76D50`，FTDI USB Serial Converter，PresentOnly OK | `experiment_results/board_validation/host_preflight/20261025T005741.174985Z_device/` 与 `20261025T005913.159854Z_device/` |
| 工具 | `D:\Xilinx\Vivado\2022.2\bin\vivado.bat` / `hw_server.bat`；安装注册表及实际二进制存在。探测前无 hw_server/Vivado 进程、3121 无监听 | `experiment_results/board_validation/host_preflight/20261025T005913.159882Z_tools/data.json` |
| JTAG | 精确 target `localhost:33121/xilinx_tcf/Digilent/210308B76D50`；device `xcvu9p_0`；PART `xcvu9p`；IDCODE_HEX `14B31093`；PROGRAM.IS_SUPPORTED `1` | `experiment_results/board_validation/host_preflight/20261025T010223.461182Z_jtag/devices.stdout.txt` |
| JTAG 执行 | 同主机 Vivado/hw_server 2022.2，列 target 和读 device 两次原生退出码均 0；read-only scope | 同目录 `receipt.json` / `targets.stdout.txt` |
| 清理 | 自有 cmd wrapper PID 54220 / hw_server PID 51420，经身份核对后仅清理该树；即时回执有短暂退出中 PID，后续独立复查确认 hw_server/Vivado/cs_server 及自有 PID 全空，33121 无监听 | 同目录 `cleanup_recheck.json`，UTC `2026-10-25T01:04:44.5392965Z` |
| WSL | `wsl.exe` 存在，但列发行版/运行发行版均 exit 1，返回安装帮助；未确认可用发行版或 PCIe/USB 透传。`usbipd.exe` 未找到 | `20261025T005913.160433Z_interfaces/data.json`；原 WSL 中文输出编码失真，保留原始数据，不据其文本解释更具体状态 |

已有 PCIe 设备和 JTAG 配置寄存器属于探测时板卡上的既有映像，不证明本次 GU-only bit 已在板上运行。注册表还保留历史 DEV_903F 接口，PresentOnly 当前设备为 DEV_9018。

## 已暂存文件

新建且未覆盖既有目录：

`C:\Users\dell\ScaleLLM_board_validation\M006_GU_66a305348d30_20261025`

指定 `ScaleLLM_MLP_GU_only_ENGINEERING_VALIDATION.bit` 实际大小 **80159259 bytes**，Dell 与本地 SHA-256 均为：

`66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47`

初次暂存的 `hw_common.tcl`、`probe_jtag.tcl`、`program_sram.tcl`、`probe_jtag.ps1` 逐件核验大小和 SHA，证据 `experiment_results/board_validation/host_preflight/20261025T010121.373220Z_staging/receipt.json`。

实际 JTAG 运行使用后续新增的 **`probe_jtag_checked.ps1`**，对应本目录当前 `probe_jtag.ps1`（SHA `65694af0eb073a9119d4437cb23dffe110f368b8a1abf739a2678d18b2643c11`），增加了完成标志及精确进程树证据。原暂存 `probe_jtag.ps1` 未覆盖；语法/SHA证据见 `20261025T0103_checked_scripts/powershell_parse.json`。实际远端日志目录为 `jtag_probe_20261025T010222533Z`。

## 可执行入口

- `run_remote_readonly.py device|tools|interfaces|project`：本地 Python 用 subprocess argv 调用 SSH 和 UTF-16LE PowerShell EncodedCommand；只读 probe 以内存 Deflate 载荷规避 Windows 命令行长度。每次保留探测脚本、原始输出 bytes、UTF-8文本、退出码、时间、脚本SHA。
- `stage_dell.py`：仅创建全新目录、SCP、远端 SHA 校验；目标目录存在即拒绝，不自动覆盖重试。
- `run_dell_jtag.py`：只读 JTAG 入口。调用已暂存 `probe_jtag_checked.ps1`，独占临时33121端口，列 targets 后只选择指定串号；运行后收集日志。临时 server 的独占实例在 finally 中按 PID/创建时间清理。
- `probe_jtag.tcl SERVER_URL ?EXACT_TARGET?`：列出下载目标；给定精确目标后只枚举设备/属性。
- `program_sram.tcl SERVER_URL EXACT_TARGET EXACT_DEVICE FULL_BIT_PATH`：**已准备、未执行**。校验 bit 文件名、实际大小及 SHA，精确匹配 target，要求所选 target 中唯一 xcvu9p 且 device 名完全一致。仅调用该设备 `program_hw_devices`，无自动选第一设备、flash 或复位操作。命令完成不等于计算功能通过。

之后若进入编程阶段，在 Dell 启动自己拥有的 2022.2 hw_server 后，可使用以下已确定参数；此示例尚未执行：

```powershell
$stage = 'C:\Users\dell\ScaleLLM_board_validation\M006_GU_66a305348d30_20261025'
# 独立终端运行 server，阶段结束后只清理这个实例：
& 'D:\Xilinx\Vivado\2022.2\bin\hw_server.bat' -s tcp::33121
# 另一个终端，先按实际连接重新核对 target/device：
& 'D:\Xilinx\Vivado\2022.2\bin\vivado.bat' -mode batch -nojournal -source "$stage\program_sram.tcl" -tclargs 'localhost:33121' 'localhost:33121/xilinx_tcf/Digilent/210308B76D50' 'xcvu9p_0' "$stage\ScaleLLM_MLP_GU_only_ENGINEERING_VALIDATION.bit"
```

## 校验、局限和版本

本地 Python AST 解析通过；三个 Tcl 用系统 Tcl 检查脚本完整性通过；`hw_common.tcl` 对真实本地 bit 的字节数/SHA 验证通过，缺失精确 target 被拒绝；实际 Windows PowerShell Parser 对 checked 脚本为 0 errors。原生只读 JTAG 脚本已实际运行通过。`program_sram.tcl` 编程路径 NOT_RUN。

初始 tools/interfaces EncodedCommand 因 Windows 命令行过长失败，原始失败目录保留；内存压缩后重试成功。首个 JTAG 收集器遇 PowerShell 扩展字符串 JSON 对象导致本地 TypeError；远端 probe 已成功完成，原始 `collected.json` 保留并已提取全部文本，采集器现已修复；未因此重复板卡操作。

已有工程仅做定向只读线索调查；初次 listing 发现 `Desktop\hap_check_pcie_link.ps1` 与 `D:\project`，不据文件名声称存在可用 GU 测试。后续 optional detail probe 达180秒传输上限未完成，按Root收束要求对精确命令/创建时间确认的远端 PowerShell PID49760清理，失败/取消证据保留于 `20261025T010238.745101Z_project/`。未安装或实现 Windows DMA transport。

**Windows GU 计算测试 transport / 输入传输 / 读取结果与整数 gold 比对尚 NOT_READY；下载、PCIe 重枚举、本bit只读CSR身份、DDR校准和板上数值正确性均 NOT_RUN。** bit 的 Max-DPO/外部 reset 签核边界见 Root 的当前合同及原交付 manifest。本任务没有改 RTL、冻结输入、三摘要或共享索引。

Hardware Manager 命令依据 [AMD/Xilinx UG908 v2022.2](https://www.xilinx.com/support/documents/sw_manuals/xilinx2022_2/ug908-vivado-programming-debugging.pdf) 和 [UG835 命令参考](https://www.xilinx.com/support/documents/sw_manuals/xilinx2022_1/ug835-vivado-tcl-commands.pdf)，实际 API 可用性以本次原生 2022.2 只读运行补证；编程路径尚未经板上执行。
