# E007：实验方案

## 真实来源、假设与基线

执行[SM011合同](../../../mission/M002_ddr_separation_and_timing_recovery/slr2_input_locality_candidate_contract_2026-10-17.md)。用户授权定向优化后启动完整implementation。E005失败保持；E006已经核实SLR1资源集中及候选前端组规模，热点/连接仍待实际结果。假设：将输入bank和capture/Hadamard/四量化器成组移至SLR2，可缓解SLR1局部压力而不制造更严重跨区瓶颈。

## 平台与输入身份

VCU118 / xcvu9p-flga2104-2L-e / Vivado2025.2，core100MHz、双DDR UI200MHz。共同父链为E005 R004/AT003的debug_materialized.dcp，SHA8451b2a86885d5ebb7bcb58dc24c352ac442492425c174269f9a803bb39c202f；原144输入和175约束来源保持，实际新运行前后独立核验。完整依据见[父链CPU核查](../../../agent/A006/followon_placement_parent_cpu_preparation_2026-10-16.md)。

## 步骤、控制变量和独立期望

唯一主动变量是候选组的hard SLR2非排他放置约束；同RTL/IP/算法/接口/时钟、同SSI_SpreadSLLs和Default physopt/route、无incremental。实际pre-place重新选择raw/可放置集合，核DSP父归一和常量/clock/cache/bundle排除；导出整个候选完整canonical cut（全方向leaf pins与top ports），核已有LOC/Pblock冲突和所有约束读回。连续完整place/physopt/route并记录真实失败。未变功能测试只按身份和原适用范围引用，不冒充本轮新测。

## 指标、采集与结论规则

报告实际SLR分布/服从率、缺失和复制对象、native资源及原始primitive/site口径、热点和跨SLR连接、原80保护边界、正式POST/DRC及时序/CDC/reset/IO状态。与E005同阶段比较；资源下降不等于路由成功。合法路由须无冲突/未布通信号，所有原时钟setup/hold/PW实际报告，未完成的正式系统安全与板级验收保持OPEN。固定窗原生拥塞不可测时明示UNAVAILABLE。

## 资源、异常与阶段报告

单EDA，CPU0–7/nice5/max8线程；树RSS192GiB、MemAvailable低于48GiB持续30秒、磁盘低于30GiB保持原保护。正常进程无墙钟/静默强停；仅管理自有PID/start。E006未真实结束/锁未释放前不启动第二EDA。原始attempt、输入、DCP、日志与终态不覆盖；普通入口修复使用新attempt连续进行。不运行bitstream/GPU/板卡/PPL/ACC。
