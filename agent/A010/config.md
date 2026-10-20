# A010：本轮实际启动配置

任务 M004/SM020/E010；角色 engineering。

期望设置 gpt-6.1-sol / xhigh，来源 agent/model_policy.md。原生 spawn_agent 已显式传入并接受这些参数，实际运行身份 `/root/gsm8k_protocol`；服务端实际模型版本未另行核实。fork_turns=none，无旧会话继承/绑定，无后代。

文件所有权：gsm8k_protocol.py、test_gsm8k_protocol.py、prepare_gsm8k_inputs.py、test_gsm8k_matrix.py；CPU验证独占线程范围见派发。无GPU/EDA启动授权给子agent，GPU由父调度。
