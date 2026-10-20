# GPU1维护helper状态

execution_state: completed（helper实现；旧版安全审核与当前3d12版loginctl适配独立复核均通过）。maintenance_execution: not_run。repair_state: unresolved。

当前实际前提：父最新库存有外部GPU0计算PID306724，必须自然退出或由其负责人安排；本环境sudo需要密码。父将仅做默认非root check；管理员后续按README执行。任何未知/活动GPU客户端或不能证明安全的会话身份都会拒绝。维护后的raw新AT仍由父普通用户单worker执行。详见[delivery.json](../delivery.json)。
