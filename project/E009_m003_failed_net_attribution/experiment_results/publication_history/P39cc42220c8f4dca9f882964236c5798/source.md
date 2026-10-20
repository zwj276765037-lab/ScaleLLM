# E009：SM013只读全量归因，AT003单对象属性修复包

M003/SM013，VCU118/Vivado2025.2。基线E008/R001/AT004失败DCP（765705446B/SHA51679d9a…）、144冻结生产输入与原失败证据保持只读。R001固定全部CONFLICTS canonical别名/全端点/唯一主组，consumer与CR关联分表；top20 whole-group与固定补充net union、有界深查/时序按协议执行。

AT003 manifest f0ac0b91…/3774B，query_plan与AT002/AT001字节一致；targets/aggregate/supervise/launch不变。仅修复单对象属性scalar先list包装，保留真实逐元素NAME身份拒绝；增加实际vals/alias CPU正负回归并重新绑定前次终态。A007独立delta审核无实质阻断，回执SHA22941413…已真实绑定。

01:31:02Z实际OPEN_CHECKPOINT_BEGIN，01:40:21Z载图完成，当前固定原生report/schema与库存查询中；input_bindings db010528…/5683B。144输入/DCP/前次PID-start/锁/资源重新核实，单EDA/CPU0–7/nice5/max8、192GiB/48GiB持续30s/disk30GiB，正常无墙钟/静默强停。无生产RTL/XDC修改或物理实现；实际模型未独立核实。


---
Published: 2026-10-18T01:41:19.951583+00:00
Publication: P6c780f2488454bd79f256dc6b70a2eaa
