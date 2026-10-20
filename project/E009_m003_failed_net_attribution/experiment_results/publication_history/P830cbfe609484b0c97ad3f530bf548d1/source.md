# E009：SM013全量归因，AT002自然失败已收尾

M003/SM013，E008/R001/AT004失败DCP与144冻结生产输入只读。R001固定范围、完整CONFLICTS别名/全端点/唯一主组、top20 union及有界深查保持。AT002 manifest47d12c26…与AT001 query_plan字节一致，原始包和失败证据不覆盖。

AT002于01:21:12.045955Z自然失败完成；原因是单对象属性getter返回scalar，被vals当Tcl列表解析使转义名称丢一反斜杠。旧逐元素身份检查正确拒绝，不能删除检查或unescape名称。A007已独立接受失败归因与最小singleton list包装修复方向。下一步登记同R001/AT003，追加实际vals函数正负/整合CPU回归并封包审核后连续启动。

正常无墙钟/无输出强停、单EDA与原资源保护保持；144输入及13档案来源均核验、锁空、旧PID/start缺席。无生产RTL/XDC、综合或implementation。实际模型无独立运行回执，不声称已核。


---
Published: 2026-10-18T01:27:38.279152+00:00
Publication: P2c9b0acea67c417f8008592506e67a77
