# E010：GSM8K完整性恢复补测与GPU1修复

用户已授权六模型×五配置补测、两张GPU及每小时报告，并追加“修复一下”GPU1。原5-shot raw greedy strict EM、1319 test/格、context8192/new4096、BF16 eager、原生KV和QDQ数值规则保持。

R001/R002失败原始证据保留。新R003暂固定GPU0/CPU16–17，全30组重做smoke/pilot；保留native_cache_call_parity_v2，新增checkpoint_static_content_v1：可信checkpoint输入、全部有效静态tensor/非persistent buffers/Hadamard cache、每生成单元前后内容/storage身份。CPU worker82例和consumer89例通过。

R003 frozen_inputs/plan.json与15份runtime源码已冻结准备，唯一展示路径修订为当前Workspace/project/software/.../results，已独立核请求字节及数值协议不变。ready仍false，尚未启动矩阵。BF16受控验证已独立通过；QDQ受控验证尚待终态。最终39570条必须独立重解码复算与身份验证才填表。

GPU1修复A012仅GPU1/CPU18–19/原flock/有限20GiB原始CUDA测试；AT001系统库、AT002匹配内核580.159.03的私有库、AT003匹配库原生内核观察。NVML项目内工具已恢复查询；无系统驱动替换/重启。M003/EDA/CPU0–7保持。

后续维护授权已收到并保存gpu1_maintenance_authorization_20261018.json。限定管理员helper位于preparation_20261018/gpu1_maintenance_20261018/gpu1_maintenance.py，默认只读；显式execute需root、双卡真实客户端/项目锁/会话/保护进程均合格，最多一次GPU1 reset，finally恢复LightDM。当前内核/局部NVML身份固定，无主机重启/系统驱动/ECC/clock修改范围。


---
Published: 2026-10-18T05:05:53.646966+00:00
Publication: P204770d926c445619f8d935b71eee2d3
