# M006 linear-only 新根构建入口

唯一硬件根为本仓库的 `project/hardware`。正式源图是
`manifests/mlp_linear/board.list`，选择新的 linear production/resource/board
替代文件，并保留原模块外部接口。旧 M003 源图和冻结检查保持原样。

生产输出 N_GU=14336、N_DOWN=4096，输入 K=4096/14336，16行；128/64
仅供有界集成测试，板级 wrapper 显式锁定生产值及 shape guard。
`m006_entry.py` 同时核输入组128/448、输出与 metadata 派生数量、44个
Attention 基线 SHA、生成器依赖与实际 HDL 选择。测试 gold 不在生产源图。

从仓库根执行（每次使用尚不存在的 attempt 名）：

```sh
python3 project/hardware/vivado/scripts/m006_entry.py freeze
python3 project/hardware/vivado/scripts/m006_entry.py check
python3 project/hardware/vivado/scripts/run_mlp_linear_board.py create AT_create
python3 project/hardware/vivado/scripts/run_mlp_linear_board.py synth AT_synth --project project/hardware/vivado/project/m006_linear_AT_create
python3 project/hardware/vivado/scripts/run_mlp_linear_board.py impl AT_impl --project project/hardware/vivado/project/m006_linear_AT_create --synth-dcp project/hardware/vivado/reports/m006_linear_AT_synth/synthesized.dcp
```

只使用本次成功 constructor 的生成文件和本次成功 synth 的 DCP。runner
验证其来源、输入清单、完整生成文件/源码配置及 SHA；复制其他 DCP 到新根
不能作为实现输入。构建输入改变后须形成新冻结与新工程，不复用旧身份。

板级资源 profile 为最多32逻辑CPU affinity、进程会话总RSS192GiB；
Vivado单进程8线程，单工程独立IP/OOC最多4 jobs。MemAvailable底线64GiB
持续30秒、磁盘底线30GiB。runner只管理自身会话/进程出生身份，等待全部
受管子进程退出再释放锁；没有墙钟或静默终止限。其他人的EDA进程不操作。

真实证据在 E013 的 R003/R004 attempts，原生Vivado报告在
`reports/m006_linear_<attempt>`。`NATIVE_STAGE_COMPLETED`只说明该阶段
原生执行完成；资源、合法布线、setup/hold、未约束路径、DRC、CDC分别看
`stage_quality.json`与原始报告。CDC始终等待实际拓扑审核。此入口不生成
bitstream或下载板卡。

功能证据与当前资格以 E013 三摘要为准，不能从入口存在推断已综合或物理
通过。纯linear计算核、生产规模GU调度、完整K有界整合与物理各有独立范围。
