# SM003 / A005 Host 修复与 CPU 快速验证

负责人：工程实验；2026-10-15 Asia/Shanghai。execution=completed；verdict=PASS（下述 CPU 范围）；review=待主控；applicability=AT104/sources.sha256 对应 Host 源。Host 源已冻结供联合验证。

本轮采用 research-agent SKILL.md、references/engineering.md、references/hardware.md。用户授权由父任务传递为“开始修复与快速功能验证”，未运行 Vivado/XSim/GPU/板卡/PPL/ACC，未改旧目录、RTL、构建脚本、golden、数值格式、舍入或算法。

## 修复交付

- 恢复旧 Host 消费者需要的 metadata/activation/artifact 常量、六字段 LayerAddresses、matrix_regions、mlp_meta_bases 与 activation_base_for_buffer。六个 CSR 权重字段均为各引擎专属物理 DDR 的 local offset，c0/c1 保留完整逻辑半组。
- Attention：20 MiB × 2 × 32 = 1280 MiB，常驻 DDR0；MLP：28+28+14+14 = 84 MiB，仅一个 DDR1 层 slot。32 层 MLP 2688 MiB 大于 2 GiB，不声明全层常驻。
- artifact manifest schema2 与 format05/ABI 保持内容合同；iter_matrix_loads/preload_all_matrices 仅装载常驻 Attention；iter_mlp_loads 和 XdmaLayerStager.mlp_weights 按层加载四份 MLP artifact。resident samples 明确 scope=resident_attention_only，channels=[0]。
- MLP 后端执行锁覆盖权重 lease、metadata、tensor DMA、命令、completion 与 ack。lease 前及 staging 后均检查 flags/ACK、busy/status、DMA、abort/maintenance；未退役状态不进行权重写入。异常保守置 RESET-REQUIRED，stager lease 永久 poison，防止后续覆写在飞权重。硬件 TIMEOUT/MAINTENANCE_ABORT 仅在已有维护排空检查和 ack 完成后安全退出。
- Hostops 根据 Attention/MLP 选择 DDR0/DDR1；输入、输出在每个 cohort/slot 分区；残差/RMSNorm 和下一层输入迁移按原顺序运行。传输记录新增 channel。
- 新只读物理布局标记：CSR 0x2B8，MEMORY_LAYOUT_ID=0x4D303032。initialize 强制读取；run_board 在初始化成功后才 preload。旧/未知布局在首个寄存器写入或 DDR 写入前被拒绝；未改 format05 数值 ABI。
- run_board 的预加载字节期望由旧混合布局 3968 MiB 改为 resident Attention 1280 MiB。

## 物理布局（半开区间，均 local）

| DDR | 分配 | 范围 / 大小 |
|---|---|---|
| 0 | 32 层 Attention c0/c1 | [0x00000000,0x50000000)，1280 MiB |
| 0 | KV 保留区 | [0x50000000,0x56000000)，96 MiB；保留地址不等于已实现 DDR KV 生命周期 |
| 0 | 6 个 activation slot | [0x56000000,0x56600000)，各 1 MiB |
| 0 | Attention metadata 双 bank | [0x56800000,0x57000000)，各 4 MiB |
| 0 | RoPE 保留区 | [0x57000000,0x57010000)，payload 8 KiB |
| 1 | 单层 MLP 四 artifact | [0x00000000,0x05400000)，84 MiB |
| 1 | 6 个 activation slot | [0x06000000,0x06600000)，各 1 MiB |
| 1 | MLP metadata 双 bank | [0x06800000,0x08000000)，各 12 MiB |

每个 activation slot：input 位于 slot+0，payload 192 KiB；output 位于 slot+0x80000，Attention payload 192 KiB / MLP payload 256 KiB。matrix_regions + RUNTIME_REGIONS 按通道检查整个区间交集和 DDR 跨界。旧 compatibility 常量 MATRIX_BYTES_PER_CHANNEL/RUNTIME_LOCAL_BASE 现表示 DDR0 resident extent，不能继续按旧混合布局乘二使用。

MLP CSR local offsets：gate c0=0，gate c1=0x01c00000，down c0=0x03800000，down c1=0x04600000。Attention 层 l：c0=l×40 MiB，c1=c0+20 MiB。

## 原始验证证据

所有尝试均独立保存 command.json、output.log、sources.sha256，未覆盖失败记录；时间为 UTC（本地 UTC+8）。

| AT | 命令 / 范围 | 退出码与结果 |
|---|---|---|
| [AT101](attempts/AT101/command.json) | /usr/bin/python3 -m pytest -q，原 7 个 Host 测试文件 | 1；系统缺 pytest，未安装依赖，改用 unittest |
| [AT102](attempts/AT102/output.log) | /usr/bin/python3 -m unittest -v，7 个文件 | 1；89 tests，8 fixture errors；4 缺省寄存器 KeyError，3 缺 current fixture 父目录，1 legacy 脚本依赖未迁移 |
| [AT103](attempts/AT103/output.log) | unittest 扩至 export/reference 与 lease 测试 | 1；105 tests，3 current bitgen fixture 缺历史脚本错误 |
| [AT104](attempts/AT104/output.log) | unittest 9 个文件，完整命令见相邻 command.json | **0；106 tests，3.648s，OK** |

AT104：2026-10-14T23:49:02.745645+00:00 至 23:49:06.680660+00:00；Python 3.12.3、NumPy 1.26.4、Linux x86_64。包含 tests/test_scalellm_memory.py、artifacts、hardware、hostops、board、runtime、export、reference 及 host/test_scalellm_memory.py。

独立期望覆盖：真实 Host 模块导入与六 CSR、32 层 Attention 全半组尺寸/地址、MLP 四 artifact 84 MiB、区域包含/部分相交/接界与 DDR 跨界、manifest 格式/hash/大小拒绝、metadata DMA 正确物理通道、输入/输出实际传输通道/地址、层 slot 复用和跨线程所有权、short DMA/超时后的 poison、11 种未退役硬件状态 0 staging/0寄存器写入、旧 layout 的 run_board 路径 0 preload/0 DDR 读写。原双 cohort 32 层三次执行 fixture 继续覆盖 384 命令身份与依赖；没有代替真实 RTL/模型运行。

legacy/current board evidence tests 现在均在 TemporaryDirectory 内构造完整脚本/报告/identity fixture，并局部 mock 模块路径；完整保留生产哈希、路径、数值报告和拒绝条件。它们仅验证证据解析器，不验证真实 bitstream、脚本执行或物理签核；未复制任何旧脚本。

## 源身份与边界

权威只读旧 memory 来源：/home/user/EDA-202/zhuowenjun/ScaleLLM/1_Hardware/host/scalellm_memory.py，SHA256=602b2dff8f12bcb7e5c35e4256eaa5f4007b53c8a6d35926c7d6c4bfaa58b0a7。该源定义 Attention 半组20 MiB、Gate/Up 半组28 MiB、Down 半组14 MiB和metadata精确字节数。

当前所有权改动：host/scalellm_memory.py、scalellm_hardware.py、scalellm_artifacts.py、scalellm_hostops.py、scalellm_board.py、host/test_scalellm_memory.py，以及 tests/test_scalellm_memory.py、hardware、artifacts、hostops、board。逐文件身份见 [AT104/sources.sha256](attempts/AT104/sources.sha256)。runtime/export/reference 仅运行原 CPU 用例，未改生产算法。

未覆盖：真实 artifact 全量导出/读回、真实 DDR/PCIe、RTL elaboration/仿真、重工具、综合/实现/时序/bitstream/板卡、真实32层模型/PPL/ACC、吞吐/功耗。host/test_ddr_separation_full.py 的历史 synthetic 性能估计未用作当前 M002 证据。Host lease 假设一个排他 XDMA 会话配一个 stager/backend；不提供跨进程设备仲裁。布局标记须由本轮 RTL 实现后联检。
