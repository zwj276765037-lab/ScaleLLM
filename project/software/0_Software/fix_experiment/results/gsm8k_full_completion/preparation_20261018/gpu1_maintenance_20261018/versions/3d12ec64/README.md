# GPU1 单卡维护 helper

维护权限已经获用户批准；本 helper 不再请求批准，也不自动提权。需要管理员在本机具有 sudo 权限、且不会随物理 LightDM 停止而退出的终端中执行。先保存桌面工作，等所有 GPU0/GPU1 计算任务自然结束并完成 M003/Codex 安全交接。不要从物理 `:0` 桌面运行；无显示依赖的会话6/SSH，或经运行时核实独立的非零 XRDP 会话可以继续。

管理员执行的单条命令：

```bash
sudo /usr/bin/python3 -B /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/gpu1_maintenance_20261018/gpu1_maintenance.py --execute
```

删除末尾 `--execute` 即仅检查；默认检查绝不会 stop/start/reset，也不调用 sudo。普通用户若不能读取必要的进程身份/环境，会保守拒绝，不把检查不完整当作安全。父当前环境 `sudo -n true` 已返回需要密码，helper 没有绕过方式。

**现在应拒绝的条件：** 最近父核实 GPU0 仍有其他项目计算进程 PID306724、owner yqh、约16890MiB。即使两个项目锁都空闲，NVML 发现任何计算/未知客户端仍拒绝；必须等待该任务自然退出或由其负责人安排，helper 不停止、不通知该任务。运行时重新识别客户端，不锁死此 PID。两卡原资源锁也必须同时能独占。

运行时核验内核580.159.03、匹配 NVML 与提取的 nvidia-smi 的固定 SHA256、两张精确 UUID。只允许原 LightDM unit 内 root Xorg `:0` 作为预期 GPU 图形客户端；任何计算或未知客户端拒绝。只允许 seat0 的 lightdm greeter，拒绝物理真人桌面、未知会话、其他用户会话重叠，或 M003/Codex/helper及祖先落在 LightDM/greeter影响范围。XRDP例外仅允许明确本机非零 display号且scope匹配；`:0.0` 等别名同样拒绝。

满足条件才执行：持有两卡原锁→停止原 `lightdm.service`→重核原保护进程身份与两卡无客户端→仅一次对 `GPU-d87ce710-76bf-872d-9739-f0d7c9b52533` 的 reset→在 `finally` 中恢复原先 active 的 LightDM。stop 返回非0也会尝试恢复。恢复检查 root LightDM MainPID、active/running及原unit范围；另记录是否已观察到 seat0 greeter，service running不等于已证明桌面完全恢复。失败不重试、不改成双卡reset，不重启主机、不改驱动/ECC/时钟，不停止任何compute/M003或其他用户会话。NVML清单未必包含所有仅监控客户端；reset仍可能由驱动以in-use自然拒绝，此时同样恢复LightDM。

每次默认check/execute都会新建 `runs/<模式_UTC_PID>/`，保留每条管理命令的 stdout、stderr、退出码、真实起止时间，以及前后 GPU客户端、会话/cgroup、必要保护进程身份和最终 result.json。只保存必要身份及显示变量，不保存全环境或完整敏感cmdline。结果 `reset_completed_not_qualified` 仅说明单次reset执行完成；父随后以普通用户、原单worker/资源锁启动新的raw验收AT，helper不加载模型或自动恢复评测。

源码：[gpu1_maintenance.py](gpu1_maintenance.py)，SHA256 `3d12ec648dd587bc1dc160c04f102abe49b1a679e3fcbcb81c456a48b21f23fa`。CPU/mock：[test_helper_mock.py](test_helper_mock.py)，[22/22结果](mock_results.json)、[原始输出](mock_stdout.log)。已覆盖默认零动作、外部GPU0计算、双锁拒绝、seat0/显示别名/保护范围、stop部分失败与后续失败的恢复、仅一次GPU1 reset。mock没有真实系统/GPU/service调用，不能替代管理员实际执行与后续raw验收。

版本边界：2249afac旧版的21项作者测试与25项独立CPU检查已通过；其源码和结果保全在`versions/2249afac/`。真实默认check发现本机loginctl不接受逗号多字段，新版仅改为每字段独立`--property`。当前22项mock全过，[真实非root只读字段回执](validation/loginctl_fields_AT001/receipt.json)取得有效Scope；这不代表真实维护已执行。新版[独立适配复核已通过](../protocol/gpu1_maintenance_loginctl_revision_review_AT001.json)：唯一AST变化、独立argv测试1/1、作者22/22、真实字段回执及后续非root/proc拒绝边界均已核。审核不表示reset或真实恢复已验证。
