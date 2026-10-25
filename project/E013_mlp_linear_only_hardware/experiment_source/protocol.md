# E013：MLP线性硬件实验协议

状态：2026-10-24实际执行中，工程owner A022；仅当前新根。

## 范围、来源与基线

M006/SM026–027；设计v1.0与A021 `project/hardware/source/mlp_linear/` 是接口/数值权威。基线0c0d2cdba00ef8e91cc96e678ca4e0b68c4cda60。旧full/serial RTL及旧M003冻结输入保持。新生产路径仅GU/DOWN，共享双8×12/S44/S54；Attention叶子源保持。

## 实际环境与资源合同

96逻辑CPU；MemTotal约503GiB、首次MemAvailable约447GiB，只是共享观测。Vivado/XSim安装 `/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin`；版本以R001工具日志为准。首次共享观测另有旧根Vivado PID1474154及其他项目PID1625454；不操作其进程或锁。

本任务重EDA并发1，A022唯一owner。small-sim profile：CPU affinity最多8核、nice+5、工具threads<=8、进程树RSS96GiB；board profile（Root依当前96CPU/load约8/available约440GiB更新）：CPU affinity最多32核、nice+5、Vivado general.maxThreads<=8、单project独立IP/OOC synth最多4jobs、进程树RSS192GiB。已冻结small-sim尝试不热改。两个profile均采用系统MemAvailable保护底线64GiB持续30秒，磁盘余量底线30GiB。资源保护只管理本任务新进程树，触发后保全输入/日志/退出码并分析，不原样加预算重跑。正常任务无墙钟/静默强停。仿真先模块与小shape pilot，估周期/速率后决定完整shape成本；TB有协议看门狗以使逻辑挂死明确失败。

## 执行与独立期望

R001为环境、cache/parser、数值codec与计算拆分模块验证；R002为DMA/CSR/epoch/生产集成功能；R003为新根工程和综合；R004为物理阶段（按功能与资源资格）。每次AT新目录保留argv、工具版本、全部实际输入哈希、原始stdout/stderr、原生returncode、开始/结束及范围。运行助手不递归hash未消费历史证据。

Cache用独立group/row/lane公式构造scoreboard：GU128、DOWN448、随机重放、响应停顿、未seal/超界/bank错误、job_clear。Parser按独立字节索引期望检查18beat、row10跨beat、reserved/padding/canonical zero、错误后持续drain。计算复用冻结kernel数学oracle逐位比对，分开小shape功能与生产完整计数。DMA用AXI BFM独立检查4KiB与16beat burst、AW/W/B/R背压和响应错误。CSR核AW/W任意次序、strobe、原子快照、旧入口拒绝、完整epoch绑定、错误ACK及稳定completion。最终B、reader/CDC/meta/tag/cache全部排空前不得完成。

## 退出与报告

每个TB独立比较及fatal断言；唯一HARDWARE_AGENT_SIM_PASS且原生0退出、无ERROR/FATAL方为PASS。未跑综合/route/时序/板级写NOT_RUN。功能仿真不替代真实生产层次与物理证据。重要里程碑/异常立即消息Root/A021；普通修复连续推进，更新本E三摘要。禁止GPU/ACC/PPL、bitstream/板卡下载，不启动旧任务。

## GU-only v7 新执行批次（2026-10-24用户授权后）

R006仅新增GU专用RTL/TB/manifest并做受影响功能验证；R007为新constructor和新综合；R008为一次新物理。旧v6冻结源和原失败DCP不覆盖。GU硬件G4R闭合后进入G5，不等待Host32层/吞吐。有效完整schema为abi_gu_only.json，当前ABI-v7/linear0x4d4c0002/caps0x1d。

生产37bit guard/128group cache/229376 GU metadata、真实3072DSP及448URAM由源绑定、完整生产elaboration与新综合网表三者互证；无Down硬件须原生hierarchy验证。metadata每记录32B物理/28B有效，padding失败使inactive目标失效、真实排空；现存active字节和generation不直接改写，epoch撤销/owner/DONE/ACK按新合同验证。故障专项可缩N32但保持完整K128，oracle取原独立Python前32列，不按DUT输出改gold。

R005已按Root新阶段裁量取消可选补充诊断，理由SCOPE_SUPERSEDED_BY_AUTHORIZED_GU_ONLY_IMPLEMENTATION；116冻结输入无漂移/30工件SHA/0survivor/锁释放见原receipt。不是资源、墙钟、静默强停，也不改变R004自然routeFAIL。新板级runner沿32CPU/192GiB、8线程/4jobs/单重进程归属协议；同会话place/physopt后、route前采轻量SLR资源与congestion，无旧慢窗/全局隐藏路径扫描。
