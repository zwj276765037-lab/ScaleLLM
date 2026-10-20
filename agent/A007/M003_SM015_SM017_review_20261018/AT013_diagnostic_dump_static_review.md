# AT013 dump_rows / prop 静态审核

未发现脚本级全图循环或自身递归；每对象的 7 个字段分别调用 list_property，存在每行 7 次属性枚举的可避免开销。parents 的 NAME 条件是固定后缀，无尾部通配符；真实对象数尚未输出。

全局 ::prop 没有 namespace/冲突保护，但有界检查当前 Vivado scripts 和实际注入 MCP Tcl 未找到同名定义/调用。不能据此认定碰撞，也不能排除其他已加载/编译部分；原生内部开销没有实测。0 B 缓冲文件只能说明 dump 尚未 flush，不能定位具体字段或判定卡死。

按工程“仅静态”请求，未运行额外 mock、EDA 或查询。当前进程与源保持。仅对后继新冻结尝试建议私有 namespace、每对象一次 list_property，并为少量代表对象增加 flush 与字段计时；这些建议不授权中断当前正常诊断。

[证据与范围](AT013_diagnostic_dump_static_review.json)。
