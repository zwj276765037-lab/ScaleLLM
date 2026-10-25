# M006 GU-only v7 构建与验证入口

正式新源图为 `vivado/manifests/mlp_gu_only/board.list`，旧 v6 linear 图保留。
有效合同为 `source/mlp_linear/abi_gu_only.json`，仅 GU opcode1；FPGA Down
scheduler、S54 accumulator、Down metadata、repack 和 tensor serializer 已从
新源图裁剪。Host Down 保持原整数格式，Host32层吞吐不是硬件构建依赖。

生产 N14336、K4096=128groups、16行。板级 wrapper 显式生产参数；
`m006_gu_entry.py` 绑定各级默认/传播、1792输出、229376 metadata、真实
37bit源码、128group缓存和44项 Attention 源字节。实际生产层次仿真另核
memory尺寸；综合后原生检查禁止Down对象、96lane逐个两组×两entry×37bit guard数据FF、
MLP3072DSP、GU metadata448URAM。缓存BRAM粒度可能不降低，不预先承诺。

从仓库根执行，每次使用新的 attempt：

```sh
python3 project/hardware/vivado/scripts/m006_gu_entry.py freeze
python3 project/hardware/vivado/scripts/m006_gu_entry.py check
python3 project/hardware/vivado/scripts/run_mlp_gu_board.py create AT006_constructor
python3 project/hardware/vivado/scripts/run_mlp_gu_board.py synth AT007_synth --project project/hardware/vivado/project/m006_gu_AT006_constructor
python3 project/hardware/vivado/scripts/run_mlp_gu_board.py qualify AT011_dcp_qualification --project project/hardware/vivado/project/m006_gu_AT006_constructor --synth-dcp project/hardware/vivado/reports/m006_gu_AT007_synth/synthesized.dcp --qualification-origin project/E013_mlp_linear_only_hardware/experiment_source/gu_only/dcp_qualification/AT007_requalification.json
python3 project/hardware/vivado/scripts/run_mlp_gu_board.py impl AT001_impl --project project/hardware/vivado/project/m006_gu_AT006_constructor --synth-dcp project/hardware/vivado/reports/m006_gu_AT011_dcp_qualification/synthesized.dcp
```

上述为本次来源链的命令标识，重跑使用新的attempt。当前R006功能G4R限定通过，
R007 AT006构造和AT011资格已原生完成，R008 AT001物理于UTC2026-10-24T18:07:59
实际启动。AT007/009因rebuilt端口改名导致查询失败而保留FAIL；AT011先用真实生成
结构网表确认存储名称，再原生逐96lane证明14208个guard FDRE完整。七分析报告及
同DCP保持原字节，资格仅支持该显式AT007来源及精确两驱动patch，不接受任意失败父。
正常新综合若本身资格成功即可直接进入impl。原始状态看E013各attempt；构建消费成功
constructor/source/generated-IP身份及本次成功新DCP，旧v6 DCP不作为本图输入。

板级32逻辑CPU/192GiB进程树、单Vivado8线程/OOCjobs4；单一重EDA owner，
没有墙钟/静默强停。小仿真8CPU/96GiB，light xvlog另用已批准两核4GiB。
MemAvailable64GiB持续30秒和磁盘30GiB保护，只管理自身出生身份/会话进程。

同一原生impl会话在opt后、place前查零黑盒、准确DDR校准端点clock与六条
已审reset同步链，并只针对d0/d1 SMC的两个request-FIFO memory scope保存真实
doutb寄存器/D/clock与exceptions coverage/valid/ignored，覆盖仍需独立审核；
布局和physopt后、route前直接保存全局/Attention/metadata/
两GU branch的SLR资源及原生congestion。没有旧慢窗口或3万跨界路径扫描。
最终route、setup/hold、未约束、DRC和完整CDC独立判断；六链探针不覆盖
XDMA user_reset等其余CDC，原生critical不自动waive。退出码0只证明阶段完成。
