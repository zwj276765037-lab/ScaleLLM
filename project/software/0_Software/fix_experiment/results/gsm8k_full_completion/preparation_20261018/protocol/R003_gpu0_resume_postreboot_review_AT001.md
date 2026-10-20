# R003 GPU0 重启后入口审核 AT001

结论：限定入口适配通过，无源码或既有资格证据阻断。仅适用于 launcher `fe3eab2a45232d39c90ae0aa08da4e6f88c8d3822241c683caac7b2b5240d478`。

与旧版 `68ddfa8e…c036` 的 AST 对照确认仅三处变化：监控程序改为 `/usr/bin/nvidia-smi`，两条查询 argv 移除 `bash`。GPU0 独占、资源、双 hold、冻结源和资格检查均未削弱。

冻结 plan `2e77661b…1426`、15 个运行源及其 15 个快照全部哈希一致。已有 BF16/QDQ 终态审核与原始产物身份匹配，均为 4 题、15 项守恒检查合格；未重跑模型或全权重核验。

主控 dryrun 回执 exit0、全部启动前检查通过，记录新内核驱动 580.178.04；审核时 maintenance hold 仍 active，R003 无 launch/current_state。由主控按用户“先只用GPU0完成补测实验吧”处理 hold，并在真实启动时核资源。worker CPU16–17，supervisor CPU14–15，单 GPU0。

本审核只执行 CPU8–9 的读取、AST 对照和哈希核验；未调用 GPU、控制实验进程或触及 M003/EDA。GPU1 继续排除。既有训练证据早于重启，后续仍须全部30组 fresh smoke/pilot 和独立进程重复性门；正式 ACC 接受数为0。
