# A011：gsm8k_worker

M004/SM020/E010工程子任务。文件：run_gsm8k_worker.py、test_gsm8k_worker.py、summarize_gsm8k.py、test_summarize_gsm8k.py、render_accuracy_table.py。读取research-agent/engineering及项目约定；共享工作区中保留其他人改动，按已确认接口集成；父agent维护全局记录与GPU调度。

2026-10-18后续父派发：拥有run_gsm8k_worker.py、run_eval_worker.py默认None只读observer、新gsm8k_weight_integrity.py/专用测试及独立诊断/preparation交付；matrix/protocol/summarizer现归A010，保留其改动。仅GPU0/CPU16,17有界训练smoke，原锁/80GiB与24GiB门，结束保持GPU空闲供维护；不启动matrix/formal。已完成并由A010独立接受。
