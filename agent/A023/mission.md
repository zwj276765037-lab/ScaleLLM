# A023 Host 整数数值支撑合同

角色：engineering；M006 / SM026 / E013。

权威输入：[M006合同](../../mission/M006_mlp_linear_only_hardware/contract.md)、设计v1.0 §6/7/12/17与[W0 revision2](../../project/hardware/source/mlp_linear/design.md)。实现 S24→H32/S27、S32→H32/S35、MinMax A8/ScaleCode、冻结SiLU ROM及乘Up、REC576与GU/Down codec。独立对照旧fixbit_v2/mlp_fixed整数参考，覆盖全部16行、生产布局与格式拒绝。

唯一工程根 `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM_MLP_fix`。只写 `project/hardware/host/scalellm_mlp_linear.py`、`project/hardware/tests/test_scalellm_mlp_linear.py`、E013 `experiment_results/host_reference/` 与A023四份md。A022并行拥有其余硬件；不撤销其编辑。公共hostops/runtime/schema/manifest/摘要/索引由对应owner管理。

CPU最多8核、RSS96GiB、系统available底线64GiB。只运行小型CPU测试，不运行EDA/GPU/板卡，不创建后代或聊天。普通合同内修复连续执行；数值/接口实质差异先报Root。

退出：实现可用API，独立期望测试通过，保留源码/输入SHA、版本、命令、退出码、日志、覆盖与适用性。无真实模型工件时只声明CPU边界/布局验证，不声称32层或板级通过。

## 后续授权：独立CSR测试支撑

Root于本轮明确派发：新增 `project/hardware/tb/hap_mlp_linear_axil_control_tb.sv` 与 `project/hardware/vivado/manifests/mlp_linear/csr.list`，只编写自检TB/manifest；生产RTL与全部真实仿真由A022唯一owner执行。保留Host已交付源与测试，不无故重跑。参考W0 revision2/94CSR定义，mock job结果而不镜像DUT判定；覆盖AXI-Lite通道顺序/背压/WSTRB、旧入口拒绝、START等待结果和快照、admission、epoch/ACK/abort、DONE别名。无后代，不运行EDA。

## 后续授权：revision3 §9真实生产整合TB

本轮独占新增 `tb/hap_attention_mlp_linear_integration_tb.sv`、`vivado/manifests/mlp_linear/integration.list` 和A023记录。实例真实production_core，N128/64、K128/448固定，四job/两cohort同epoch，真实metadata DMA/REC576/kernel/DDR/ACK，坏REC恢复、末B延迟、BRESP可排空维护恢复、framing global_freeze只reset恢复。所有gold独立标量，BFM只外部端口，不force内部状态。A022拥有生产修改和全部真实EDA；Host/CSR旧交付保持，CSR仿真修复所有权已由Root临时交A022。

## 后续授权：M006新板级Tcl入口加固

A022明确转交 `vivado/scripts/create_mlp_linear_board.tcl` 与 `build_mlp_linear_board.tcl`，A023只修改这两个入口及自身记录；Root临时同时授权修整合TB参考，并授权在既有host_reference保存可复现Python完整gold来源。A022仍独占runner/entry/RTL/manifest/全部EDA。目标是constructor真实配置/可见身份、正式scope拒绝validate-only，以及构建的真实clock/netlist/route/timing/DRC/CDC结构化native证据；不猜不可见property，不用native0替代质量通过，保留Attention ROM固定SHA/staging/Synth8-4445拒绝。小型系统Tcl/Python检查授权内连续执行，无Vivado/xsim。

## GU-only G1/G4H授权

用户批准GU-only实施后Root分派新增 `host/scalellm_mlp_gu_only*.py`（生成 `_abi.py`归A022）、对应tests、E013 `experiment_results/host_gu_only/`。实现原format05 Host完整Down：原W4/32Bmeta decode、bounded输出/full448组纯整数oracle、blocked int64、高效独立向量参考、16x4096合成实测、GU-only runtime任务/层租约与v7拒绝旧ABI/非法Down命令CPU测试。旧linear/runtime/artifacts只读复用；无真实工件不声称真实模型通过。CPU≤8核，子树RSS建议≤8GiB，禁止GPU/板卡/EDA，不用0.94G MAC标量Python做全shape回归。完整Host系统不阻塞硬件G4R/G5。

Root随后授权在同一新Host所有权内完成真实CSR/XDMA backend，复用原session四个方法，保持DDR1 local/Host aperture、hash/padding、fullU32 opcode、epoch/DONE/ACK和失败租约保留。应用Attention回调为明确外部接口且真实身份检查不可省略。42项CPU测试分两attempt交付后，Root转交新增 `tb/hap_mlp_gu_axil_control_tb.sv` 与 `vivado/manifests/mlp_gu_only/csr.list`；只改这两测试文件及自身记录，A022唯一运行EDA。
