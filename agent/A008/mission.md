# m002_rtl_routability_explorer

内部记录ID：A008。

角色：engineering；小 mission：SM008；实验：E004。

## 当前合同

依据 [SM008合同](../../mission/M002_ddr_separation_and_timing_recovery/routability_analysis_contract_2026-10-16.md)、根 AGENTS.md、research-agent 的 engineering/hardware/models-and-launch 参考。只读核查当前构建实际 Attention input/output/context/postprocess/projection 结构，将 E003 route 的10个冲突节点样本映射到源码，给出源码规模估算、协议风险和可区分候选，不做最终架构决定。

## 依赖、写入范围与资源

拥有 `project/E004_m002_routability_optimization_analysis/experiment_results/runs/R002` 与 `agent/A008`。生产 RTL/XDC/脚本/既有证据只读；不读旧根，不运行 EDA/GPU/板卡，不开后代。A006负责物理实测，A007负责方案独立判断，主控唯一维护共享三摘要/索引。共享目录保留他人修改。仅小型CPU计数、哈希、有限地址覆盖和现存日志解析。

数值、Hadamard、ScaleCode、format05/Attention格式、舍入、Host ABI、双DDR及core100MHz/UI200+200MHz保持。内部周期候选必须列出数据寿命、握手和数值回归义务。

## 阶段回传

重要里程碑/异常/全局影响及时通过实际消息工具发给主控；详细证据留在实验目录。
