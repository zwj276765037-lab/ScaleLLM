# 完整 top-port 反向索引：R006 独立准备入口

本包保持 `candidate_directed_cut_v1` 的候选完整有向边界与方向时序，仅将 top-port 原生获取方式改为 `NATIVE_PORT_REVERSE_INDEX_V1`。权威补充为 mission/M002_ddr_separation_and_timing_recovery/top_port_reverse_index_acquisition_revision_2026-10-17.md；详细自动资格由 A007 minimal_native_qualification.md 定义。

完整默认 get_ports 库存、每个端口全部直接连接网、完整 aliases、每个端口附着组的完整原生反向互查必须全部通过。BUS/secondary、多组、断开、INOUT/MIXED/UNKNOWN/成功空方向均保留。未知方向沿用原方向回退；身份、邻接或完整性错误直接拒绝当前阶段。可选属性的 VALUE/EMPTY/UNSUPPORTED 单列；失败的实际查询保留原错误，不伪装成功空值。

top_port_index.tcl 保存每次实际原生调用的 BEGIN/END 与完整参数/结果。端口索引与候选 canonical universe 分离。top_port_evidence.py 从原始调用重建全集、邻接、闭包、互查及每网纯 JOIN；INDEX_CLOSED 在所有原始文件关闭后绑定输入、完整源码与原始文件身份。TOP_PORT_INDEX_JOIN 不冒充旧 ALL_TOP_PORTS 原生命令。

新 R006 launcher 需要真实源/旧 scope/获取补充绑定，并且当前 R005 AT003 及全部历史 E006 原始 PID/start、输入和唯一 EDA 锁已经实际收尾。当前 R005 和旧 b330/da34 不改动；本包不是停止许可。若用户另行许可本次切换，controlled_stop_R005.py 仅可通知固定 supervisor1338668/start931443208，由原 handler 完成收尾；默认无 --execute 不发信号，且仍要求真实新用户决定。

CPU 有限图的真实 collector/validator 组合、区分反例、原成员回放、完整入口环境预检和 E008 同阶段 actual P 投影均另存 CPU_checks。它们不证明新原生资格、性能收益、候选有效、时序收敛或合法布通。原流程中的完整 place→physopt→route、80 项保护和正式验收保持。

单 EDA、CPU0–7/nice5/max8，原内存/磁盘保护保持；正常运行无墙钟/静默强停。无 bitstream、GPU、板卡、PPL/ACC，旧工程严格只读。
