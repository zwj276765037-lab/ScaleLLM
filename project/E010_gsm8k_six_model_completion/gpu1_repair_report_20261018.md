# GPU1 修复记录（诊断完成，维护已授权）

本轮用户授权“修复一下”；角色为工程实现与验证。原 GSM8K 补测继续，硬件 M003 的任务和 CPU0–7 保持。此记录只描述已观察到的行为，GPU1 尚未恢复评估资格。

| 项目 | 实测发现 | 当前结果 |
| --- | --- | --- |
| 显卡监控 | 内核驱动580.159.03，系统NVML580.178.04，默认查询失败 | 已使用官方匹配版本在项目内恢复查询；系统库未改 |
| 模型权重 | GPU1的Llama3.1目标权重在推理前已与checkpoint不符；GPU0同层17次快照一致 | GPU1退出补测队列，新增全模型静态内容检查 |
| 原始CUDA显存检查AT001 | 无Torch/Transformers，20GiB/9种模式；7种模式失败，包括设备自行填零；本次分配46–50出现错误 | 失败已复现，完整差异和自然收尾保留 |
| 匹配CUDA库AT002 | 已核实际加载580.159.03；相同原始程序再次出现字节错误 | 仅匹配用户态库不足以修复；9种模式已自然完成 |
| GPU内部观察AT003 | 00/ff共320次GPU内部与CPU读回对照全部一致；00每遍212992字节错误、ff为0 | 自然完成并独立复核，GPU内部可见错误 |
| GPU0恢复验证 | BF16准备组4/4训练题、293静态对象和15次完整性阶段、原v2门均通过，独立复算一致 | QDQ也已4/4、295对象/224投影/15阶段全部通过并独立审核；R003维护hold，正式0/39570 |

项目内监控工具：[nvidia_smi_local.sh](../software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/nvml_local_recovery_20261018/nvidia_smi_local.sh)。只为该次调用提供匹配库，不能据此声称系统驱动已修复。

字节错误可能涉及显存、显存控制器或其他设备路径；CUDA虚拟地址不能当作物理坏页。匹配库复测不能排除全部内核驱动/平台原因。ECC当前Disabled，ECC错误显示N/A，不能按零错误解释。

## 维护边界与后继

实际Xorg图形进程PID2653使用两张卡，其中GPU1占38MiB。官方随包nvidia-smi手册规定：重置需要root，且目标GPU不得仍被CUDA、X server或监控程序使用。拓扑实测两卡通过SYS连接，没有NVLink；仍须在维护当时重新检查单卡重置资格。ECC开关按该版本文档需要重启生效。

因此当前未重置GPU、未退出桌面、未重启主机，也未安装或替换系统驱动。AT003已自然完成且独立审核通过，确认设备内部读取可见错误。用户已明确允许安排维护窗口，仅限安全交接后释放图形客户端、重置GPU1并复测；涉及全局驱动重载或主机重启时，须同时安排GPU0/M003正常交接。复位或重启本身不等于修好：需重新通过原始显存测试、完整模型输入身份、调用前后完整性和原v2验证后，才能恢复GPU1补测。

[原始检查与对照](../software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/gpu1_repair_20261018/experiment_results/summary.md) · [维护步骤草案](../software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/gpu1_repair_20261018/maintenance_candidate.md) · [实际维护影响清单](../software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/nvml_local_recovery_20261018/maintenance_impact_inventory_20261018T0435.json)

记录时间（UTC）：2026-10-18T04:39:24.490607+00:00

## 最新执行边界

用户已回复“允许安排上述GPU1维护窗口”，见[gpu1_maintenance_authorization_20261018.json](gpu1_maintenance_authorization_20261018.json)，不再等待重复授权。维护仍未真实执行，有两个实际前置：

1. 当前账号的非交互sudo返回“a password is required”。管理员需在本机终端输入密码执行经过审核的有限维护脚本，不能在对话提供密码；不会更换系统驱动或重启主机。
2. 本项目GPU0两组受控验证均已自然退出，但NVML又核实GPU0存在另一用户的PID306724，占16890MiB，属于另一项目。保持它正常运行，维护和新矩阵启动均须重新检查真实客户端，不能只凭本项目flock可获得就判全卡空闲。

实际占用GPU的Xorg2653属于lightdm.service的物理:0登录界面，seat0当前只有lightdm-greeter；本对话/M003批处理运行于独立session-6.scope且无DISPLAY，另外两用户XRDP:10/:11也独立。维护脚本需运行时再次确认这些隔离条件，只操作lightdm，若出现未预期会话或进程则拒绝。

[GPU0外部客户端证据](experiment_results/hourly_reports/20261018_external_gpu0_client_observed.json) · [维护前置与会话证据](experiment_results/hourly_reports/20261018_gpu1_maintenance_preconditions.json) · [GPU内部观察独立复核](../software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/protocol/gpu1_internal_observer_review_AT001.json)

更新（UTC）：2026-10-18T04:56:27.862489+00:00

## 管理员入口与执行证据

维护程序及完整命令：[维护README](../software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/gpu1_maintenance_20261018/README.md)。目前仅默认只读check有真实执行记录：首次CLI不兼容已修复并保留失败，第二次触及非root进程读取权限，均没有stop/reset。实际维护后读取该目录runs/execute_*/result.json；只有单卡reset完成并不代表数据修复成功，需接续新AT字节/模型验证。R003维护hold保持，每小时报告继续。
