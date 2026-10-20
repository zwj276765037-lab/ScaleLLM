# E010：暂停时结果

R002历史终态failed，smoke6/30、pilot/formal0/30；R003未启动，smoke/pilot/formal均0/30，正式完成及独立接受0/39570。原失败组不复用。

GPU0 Llama-3.1-8B-Instruct的BF16、a8w4_fp32各完成4/4训练准备题，原v2门、15完整性阶段及token独立复算通过；均已自然退出。准备结果不计正式ACC。

GPU1原始CUDA三轮自然完成；匹配libcuda仍未消除数据错误，GPU内部读与CPU读均观测到00模式每遍212992字节错误，尚不细分DRAM/控制器/驱动根因。GPU1资格仍关闭。13:42维护attempt因整数PID键序列化错误失败，stop_attempted=false、reset_attempts=0；最新helper26项CPU/mock修复验证通过，实际重置仍未发生。


---
Published: 2026-10-18T05:56:44.899987+00:00
Publication: Pc82a1d6a905d4b58b683ab06fee24e6a
