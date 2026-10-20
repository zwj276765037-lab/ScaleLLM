> **当前已由用户暂停（北京时间2026-10-18 13:48）：“先停止所有GPU的实验”。GPU补测、诊断和维护均不再启动；下方管理员命令仅作历史交接说明，收到用户明确恢复指令前请勿执行。**

# GPU1 单卡维护 helper

维护权限已经获用户批准；本 helper 不再请求批准，也不自动提权。需要管理员在本机具有 sudo 权限、且不会随物理 LightDM 停止而退出的终端中执行。先保存桌面工作，等所有 GPU0/GPU1 计算任务自然结束并完成 M003/Codex 安全交接。不要从物理 `:0` 桌面运行；无显示依赖的会话6/SSH，或经运行时核实独立的非零 XRDP 会话可以继续。

管理员执行的单条命令：

```bash
sudo /usr/bin/python3 -B /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/gpu1_maintenance_20261018/gpu1_maintenance.py --execute
```

删除末尾 `--execute` 即仅检查；默认检查绝不会 stop/start/reset，也不调用 sudo。设备占用检查要求管理员权限，以覆盖其他用户；普通用户运行会保守拒绝，不把检查不完整当作安全。父当前环境 `sudo -n true` 已返回需要密码，helper 没有绕过方式。

**占用保护：** 早期核实 GPU0 有其他项目计算进程 PID306724、owner yqh、约16890MiB；该进程在本次管理员 reset 尝试前已退出，此处保留历史背景。即使两个项目锁都空闲，NVML 发现任何计算/未知客户端仍拒绝；必须等待该任务自然退出或由其负责人安排，helper 不停止、不通知该任务。运行时重新识别客户端，不锁死此 PID。两卡原资源锁也必须同时能独占。

运行时核验内核580.159.03、匹配 NVML 与提取的 nvidia-smi 的固定 SHA256、两张精确 UUID。只允许原 LightDM unit 内 root Xorg `:0` 作为预期 GPU 图形客户端；任何计算或未知客户端拒绝。只允许 seat0 的 lightdm greeter，拒绝物理真人桌面、未知会话、其他用户会话重叠，或 M003/Codex/helper及祖先落在 LightDM/greeter影响范围。XRDP例外仅允许明确本机非零 display号且scope匹配；`:0.0` 等别名同样拒绝。

满足条件才执行：持有两卡原锁→停止原 `lightdm.service`→重核原保护进程身份与两卡无客户端→仅一次对 `GPU-d87ce710-76bf-872d-9739-f0d7c9b52533` 的 reset→在 `finally` 中恢复原先 active 的 LightDM。stop 返回非0也会尝试恢复。恢复检查 root LightDM MainPID、active/running及原unit范围；另记录是否已观察到 seat0 greeter，service running不等于已证明桌面完全恢复。失败不重试、不改成双卡reset，不重启主机、不改驱动/ECC/时钟，不停止任何compute/M003或其他用户会话。当前在停止前、取得锁后及停止后，除 NVML 清单外，还以 root 调用只读 fuser 检查 `/dev/nvidia1`、`/dev/nvidia0`、`/dev/nvidiactl`、`/dev/nvidia-uvm`、`/dev/nvidia-modeset`。额外持有者、身份未知、检查报错或清单缺失均拒绝；不会结束这些进程。停止后连原 Xorg 的设备占用也不允许残留。检查与 reset 之间仍存在竞争窗口，驱动仍可能返回 in-use，此时同样恢复 LightDM。

每次默认check/execute都会新建 `runs/<模式_UTC_PID>/`，保留每条管理命令的 stdout、stderr、退出码、真实起止时间，以及前后 GPU客户端、会话/cgroup、必要保护进程身份和最终 result.json。只保存必要身份及显示变量，不保存全环境或完整敏感cmdline。结果 `reset_completed_not_qualified` 仅说明单次reset执行完成；父随后以普通用户、原单worker/资源锁启动新的raw验收AT，helper不加载模型或自动恢复评测。

源码：[gpu1_maintenance.py](gpu1_maintenance.py)，SHA256 `ff4e1b5161330e3c215bfeb05536f496cf8207f8c63eec6489758facc9f100c6`。CPU/mock：[test_helper_mock.py](test_helper_mock.py)，[35/35结果](validation/device_holder_preflight_AT001/mock_results.json)、[原始输出](validation/device_holder_preflight_AT001/mock_stdout.log)。新增9项测试覆盖 NVML 漏报的设备持有者、三个维护阶段的拒绝、缺失身份/清单、root 要求及 fuser 输出和错误处理；原26项保护测试继续通过。mock没有真实系统/GPU/service调用，不能替代管理员实际执行与后续raw验收。

版本边界：2249afac旧版的21项作者测试与25项独立CPU检查已通过；其源码和结果保全在`versions/2249afac/`。真实默认check发现本机loginctl不接受逗号多字段，新版仅改为每字段独立`--property`。该适配版本22项mock全过，[真实非root只读字段回执](validation/loginctl_fields_AT001/receipt.json)取得有效Scope；这不代表真实维护已执行。新版[独立适配复核已通过](../protocol/gpu1_maintenance_loginctl_revision_review_AT001.json)：唯一AST变化、独立argv测试1/1、作者22/22、真实字段回执及后续非root/proc拒绝边界均已核。审核不表示reset或真实恢复已验证。

## 整数进程编号序列化修复（2026-10-18）

管理员真实执行记录 `runs/execute_20261018T054245.505636Z_331396` 在保存预检查进程快照时失败：`public()` 对整数PID字典键调用了 `startswith`。本次 `stop_attempted=false`、`reset_attempts=0`，没有停止图形服务或重置显卡。旧源码、测试和说明已保存在 [versions/3d12ec64](versions/3d12ec64/)。

该修订仅将私有字段过滤限定为字符串键；PID整数键由JSON正常序列化，不修改原始快照。新增4项测试在旧版上全部失败，在新版上全部通过；26项CPU/mock均通过。AST核对证明除 `public()` 外维护源码完全一致，原GPU0计算占用拒绝等保护不变。此次没有重新执行真实管理员维护；重试仍须满足现有占用和会话检查。


## 设备占用预检查修复（2026-10-18 14:00 后）

用户在本窗口提交了管理员执行记录 `runs/execute_20261018T055934.103845Z_335510`：一次 GPU1 reset 返回255，原始原因是 `In use by another client`，并非驱动报告 reset 不支持。LightDM 已恢复 active/running；随后的只读检查也观察到 seat0 greeter 会话 c4。该操作没有完成 reset，不能作为复测起点。

只读检查发现当前用户的 WebKitWebProcess PID11758 属于 Clash Verge 界面 PID11522，持有 GPU1/GPU0/nvidiactl，且未出现在 NVML 进程清单中。非 root 检查无法排除其他用户持有者，因此管理员预检查新增 root 设备占用清单。代理核心 PID11886 属于独立 clash-verge-service.service（MainPID3552）；并未验证退出界面会不会通过应用逻辑改变代理状态。没有结束界面、代理核心或其他程序，没有再次 stop/reset，也未启动 GPU 实验。

旧源码、测试和说明保全于 [versions/2aa9ef1d](versions/2aa9ef1d/)。新检查通过35项 CPU/mock；AST 对比确认维护编排、固定 GPU1 reset、服务操作及资源锁函数未改变。[只读证据](validation/device_holder_preflight_AT001/observations.json)记录真实 fuser 输出、进程归属、LightDM/代理服务状态及原始 reset 错误。

现有完整驱动版本错配仍存在：Xorg 580.178.04 初始化 NVIDIA 内核模块失败；当前服务/greeter 存活并不表示 NVIDIA 图形加速已恢复。这里未修改驱动。先前暂停 GPU 实验的记录保留；本次只完成用户提交失败后的只读诊断和 CPU 维护脚本修复。
