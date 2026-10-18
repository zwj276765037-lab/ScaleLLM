# AT004 自然失败后的收尾独立审核

execution：终态输入、原进程、资源与观察器证据审核完成。verdict：接受 14 项收尾检查；合法布线仍 FAIL、正式安全仍 OPEN。applicability：仅 AT004 已结束尝试的闭合，不是实现成功或新的运行授权。

独立重新核对 144 个生产输入、39 个原来源绑定、39 个实际 stage_sources 归档、准备包/CPU 检查/文档、合同/范围补充和候选归因证据，身份一致。stage_inputs 的所有非 DCP 文件重新 hash；父 DCP 与失败 DCP 只由 A007 检查元数据大小和绑定。两份 DCP 的完整内容 hash 已由 A006 独立终态 collector 复算，分别吻合 396,068,466 字节/8451b2a8… 和 765,705,446 字节/51679d9a…；不会表述为 A007 读过或 hash 过 DCP。

8,499 条完整 resources.jsonl 样本独立复算与 status/terminal facts 一致：峰值 RSS 35,757,166,592 字节，最低 MemAvailable 490,982,973,440 字节，最低磁盘余量 411,805,528,064 字节；最大采样间隔 11.721124 秒。全程样本符合既有资源保护阈值。19 个原 PID-start 身份通过只读 /proc 再核均不存活；工程独占非阻塞锁探测显示 lane 已释放，审核另以 /proc/locks 核对该 inode 无持锁条目，未申请/释放锁或发送信号。

两个观察器 session 42865、73883 的工程归档真实工具回执均 exit0，未返回 running session；终态字段与监督 status 相符，自动捕获器最后于 21:18:34.992595Z 观察到 supervisor_terminal=true。历史缓冲输出截断不影响完整资源样本复算，也不当作完整资源历史。资源观察器最后一条 utc 是资源采样时间，不冒充观察器退出时间。

工程失败详细包 cf03a19d… 的最终失败计数、全局时序、当前 C01 compliance、五项采证回执和原生日志片段均与 A007 已完成的终态审核一致；64 条有界时序 TSV 的组数和最差 slack 也已复算，仅作为失败图有界诊断。native 日志显示 route elapsed 13,872 秒；整数边界 epoch 差 13,871 秒，1 秒舍入/取点差异保留，两者均不同于包含后续采证和 locality 的监督总时长。

engineering_execution_verified=false 正确表示原生/监督非零且没有完整成功 route 阶段，并非未核实这次自然失败。没有成功 route POST、最终 bus-skew 全覆盖或正式 reset/CDC/IO 安全结论；收尾通过不能替代这些验收。未启动 EDA、新 AT 或 implementation。

证据、完整身份和核查边界见 [JSON 审核记录](route_failed_terminal_closure_review.json)；物理失败结论见 [终态审核](route_failed_native_terminal_review.md)。
