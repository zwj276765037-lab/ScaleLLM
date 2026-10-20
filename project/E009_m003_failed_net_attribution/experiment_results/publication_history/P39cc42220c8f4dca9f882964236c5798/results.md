# E009：AT003载图完成，固定原生查询中

AT003于01:31:02Z（北京时间09:31:02）实际OPEN_CHECKPOINT_BEGIN；native261951/start5879131，supervisor261857/start5878910，leader261861/start5879118。实际nice5/CPU0–7、唯一FLOCK由监督器261857持有，13来源档案和144生产输入已绑定。独立新观察器60460/PID261974仅读阶段，不控制原生进程。

单对象属性修复CPU回归：保存162字节/2反斜杠NAME、空值/optional、vector/fallback、实际vals+alias整合与真实差异拒绝全部通过；这些是离线脚本验证。新AT的完整原生alias资格、canonical清单、端点、唯一分组、union覆盖和G1仍未实测。

AT001/AT002自然失败的原包与证据全部保留；AT002 native1/supervisor1/stop_reason=null，终态/144来源/进程/锁/观察器收尾均闭合，不判断优化方法无效。547548冲突网与702396重叠节点保持独立指标。

[真实启动核验](runs/R001/attempts/AT003_failed_route_full_attribution_scalar_fix/native_start_observed.json) · [来源绑定](runs/R001/attempts/AT003_failed_route_full_attribution_scalar_fix/input_bindings.json) · [修复与CPU回归](runs/R001/attempts/AT003_failed_route_full_attribution_scalar_fix/delta_and_cpu_checks.json)。

01:40:21Z OPEN_CHECKPOINT_COMPLETE已由真实native marker与独立只读观察器60460记录；当前原生report/schema查询，无终态。载图完成不代表全量alias/census或G1完成。


---
Published: 2026-10-18T01:41:19.951583+00:00
Publication: P6c780f2488454bd79f256dc6b70a2eaa
