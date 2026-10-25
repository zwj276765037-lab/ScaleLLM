# A022：MLP linear硬件工程

角色engineering；实际内部身份`/root/mlp_linear_engineering`；GPT-6.1 Sol xhigh。
执行[SM026](../../mission/M006_mlp_linear_only_hardware/tasks/SM026.md)与
[SM027](../../mission/M006_mlp_linear_only_hardware/tasks/SM027.md)，对应
[M006合同](../../mission/M006_mlp_linear_only_hardware/contract.md)、
[goal](../../goal/goal.md)、[AGENTS](../../AGENTS.md)及
[E013协议](../../project/E013_mlp_linear_only_hardware/experiment_source/protocol.md)。

唯一根为`/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM_MLP_fix`。
交付真实RTL/Host必要codec与oracle/可复现功能仿真/新Vivado工程，再按
功能资格连续完成综合与实现。最新用户已批准GU-only实施：FPGA仅GU，
Down完整移Host保留原整数format05；保留double8x12/3072DSP、GU37/S44
与S24 repack，静态裁S54/Down metadata/repack/tensor。Attention DDR0、
GU DDR1职责不变，旧v6图/ABI保留。验收按模块功能、
真实集成、构建/综合、route与timing/DRC/CDC分开，未做不得记PASS。

所有权为本任务新/修改硬件RTL、TB、构建脚本/清单及E013协议/三摘要/原始
证据。Root独占共享goal/mission/index；A021独占source/mlp_linear设计/
schema；A023独占新scalellm_mlp_gu_only*.py（生成ABI例外归A022）、
其测试与host_gu_only证据。A023新CSR TB已交回A022唯一EDA执行。不能撤销其他工作者改动或改旧根/旧任务。

A022是唯一重EDA owner。small-sim8CPU/RSS96GiB；board32CPU/RSS192GiB，
单Vivado8线程、独立IP/OOC最多4jobs；MemAvailable64GiB持续30秒/磁盘
30GiB保护，只管自身进程会话。正常工具无静默/墙钟终止限。不启动GPU、
ACC、PPL、bitstream或板卡下载。普通实现/编译/修复连续，合同实质变化
集中交架构负责人；里程碑/实质阻塞用真实消息回传Root。

用户最新验收重点：减少MLP FPGA操作能否缓解旧SLR拥塞/跨界问题。新GU构建在同一place/physopt原生会话采SLR资源和congestion，不再运行旧慢窗口诊断；资源表、功能PASS、合法route与SLR改善分别下结论。R006功能、R007新constructor/synth、R008一次新物理连续，G5不等待Host32层/吞吐。

R008/AT001已于UTC2026-10-24T23:27:20.753971自然NATIVE_STAGE_COMPLETED，0输入漂移/0survivor；实际route零错误、受约束setup/hold/pulse失败端点均0。当前只读同routed DCP补十命令bus-skew、两复位链、两代表DSP及两SMC例外对象，形成分项物理结论；原IO delay1/2与四可选报告参数错误、CDC/DRC限定复核均显式保留。
