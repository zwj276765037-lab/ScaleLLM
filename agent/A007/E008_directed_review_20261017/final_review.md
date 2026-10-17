# E008 有向边界入口独立审核：1d612c65

执行：本次源码与 CPU 审核 completed。判断：入口准备和阶段接线得到支持。适用：最终 manifest `1d612c65a3900669eb6fb73eac8f127e7955f5ef63879035601c486904f16706`（11126 B），原 E008 合同与 directed scope 双绑定。审核：内部独立审核完成；候选未选择，E008 原生实现未运行。

13 自有源、16 复用源、2 CPU 记录、文档及外部绑定均已核验；实际只读 `verify_manifest()` 通过。R005 558c 的 collector/helper 逐字节复用。原 9f267 包 17 项归档、b59 的 11 项自有源均保留。详细身份见 [核验记录](final_package_verification.json)、[静态保护核验](static_protection_verification.json)、[最终机器记录](final_review_1d612c65.json)。

两项常规修复已闭合：合法零字节 timing-query ledger 改用允许空文件的身份函数；复用投影视图时单独复验原 literal P。独立七项测试均符合预期：pre-place 空边界，以及 place/physopt/route 的 DSP 子对象与原生 root 外副本通过；literal P 漂移、实际 reconciled P 漂移、投影链接重定向均拒绝。cut 后新增 timing 输入产生保留旧身份的修订记录，原 literal P 不覆盖。[测试结果](projection_original_9f267/results.json)。

旧命名 `original_9f267_snapshot` 实际在工程修订完成后复制，所存 manifest 与 13 源均为最终 1d612。保留目录及原测试结果，新增[身份说明](snapshot_name_identity_clarification.json)，不能用目录名指认旧源码。CT001 是旧 adapter 的历史 CPU 记录，其相关 membership/selector/resource/IO 逻辑不变；旧身份在归档可复验。CT005 绑定最终 adapter，并记录 14 个 collector mock 的阶段 cut/timing 回放及新增修复测试。均不等同原生验证。

阶段接线核对通过：pre-place 使用实际 literal P；后续先重建并核准 reconciled P，再 cut → scoped timing → 有向时序集合验证 → compliance。DSP children 与 native-origin copies 纳入实际集合，原始 RAW/S/P 保留。父恢复、约束链、membership/origin、资源资格与 Pblock policy 的函数/过程未改；原 `post_phase` 全 POST 及错误保全不变。implementation 只在 pre-place 增加有向时序验证，place=SSI_SpreadSLLs、physopt/route=Default、80 项保护、时钟/CDC/reset/IO、失败捕获和资源监督均保留。[源码差异](b59_to_final_source.diff)。

真实选型、E006 前置终态与 PID/start/锁收尾，以及原合同/新 scope/新 manifest 绑定仍是执行依赖。完整 place→physopt→route、合法布通与 setup/hold/PW 验收保持。获资格的外部 peer IN loads 可不导出；不能据此声称整网 fanout、外部空间分布、全 cut TNS、SLL/带宽或性能收益。

本审核未执行 EDA、读取大 DCP、改动工程源码、发送信号、控制锁或创建后代。后续按真实 R005 阶段证据继续判断，不增加用户逐项批准门。
