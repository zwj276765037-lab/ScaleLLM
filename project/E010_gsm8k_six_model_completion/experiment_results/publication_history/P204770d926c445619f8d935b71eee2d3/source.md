# E010：GSM8K完整性恢复补测与GPU1修复

用户已授权六模型×五配置补测、两张GPU及每小时报告，并追加“修复一下”GPU1。原5-shot raw greedy strict EM、1319 test/格、context8192/new4096、BF16 eager、原生KV和QDQ数值规则保持。

R001/R002失败原始证据保留。新R003暂固定GPU0/CPU16–17，全30组重做smoke/pilot；保留native_cache_call_parity_v2，新增checkpoint_static_content_v1：可信checkpoint输入、全部有效静态tensor/非persistent buffers/Hadamard cache、每生成单元前后内容/storage身份。CPU worker82例和consumer89例通过。

R003 frozen_inputs/plan.json与15份runtime源码已冻结准备，唯一展示路径修订为当前Workspace/project/software/.../results，已独立核请求字节及数值协议不变。ready仍false，尚未启动矩阵。BF16受控验证已独立通过；QDQ受控验证尚待终态。最终39570条必须独立重解码复算与身份验证才填表。

GPU1修复A012仅GPU1/CPU18–19/原flock/有限20GiB原始CUDA测试；AT001系统库、AT002匹配内核580.159.03的私有库、AT003匹配库原生内核观察。NVML项目内工具已恢复查询；无系统驱动替换/重启。M003/EDA/CPU0–7保持。


---
Published: 2026-10-18T04:46:13.580976+00:00
Publication: Pf23b2d9a9348415cbd96a77b257eaf3f
