# AT018 · snapshot_collection_postreport_recovery

记录目的、实际结果、适用范围、限制及原始证据。登记不代表已执行或通过。

## 实际自然终态

AT018于2026-10-18T15:54:39.852665Z自然native1结束；stop_reason=null、owned_survivors={}，maxRSS63.40GiB。两次实际overlay apply均已独立接受；随后snapshot的memory_startpoint_names在ADDR_A[22]上拒绝空startpoints，实际970B错误栈已保全。栈未包含具体URAM cell，常量/禁用/结构/查询原因仍待本版fresh core原生诊断。

45源/3RTL/G2/core身份未变，tracked PID/start及supervisor已退出，单EDA锁可取得释放；启动runtime_binding保持。observer已poll终态；额外session26467排空请求返回Unknown process id，未冒称另一次成功drain。无完整selected/预算/G4/布局布线结果。

证据：[终态事实](evidence/AT018_terminal_and_address_startpoint_failure_facts.json)。
