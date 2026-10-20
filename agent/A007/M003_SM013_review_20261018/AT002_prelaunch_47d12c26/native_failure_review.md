# AT002 自然终态与单对象属性适配复核

2026-10-18；A007。execution：AT002 自然 failed，本次有界独立审核 completed。verdict：取数适配缺陷证据支持最小修复；未完成 G1，不反驳优化方法。applicability：47d12c26 固定包与本次封闭原生回执。review：独立接受终态事实和修复依据，AT003 包/原生结果另审。

## 终态

监督器 01:21:12.045955Z 结束，native=1、supervisor=1、stop_reason=null、natural_terminal=true；无 cleanup/survivors/post_integrity_error。独立读取当前 /proc 核实 supervisor、三项 tracked PID 和 observer PID 均不存在，旧 supervisor 无锁记录。完整资源日志复算与 status 一致：树 RSS 峰值 27,605,745,664 B，MemAvailable 最低 502,861,688,832 B，磁盘最低 413,242,417,152 B。未触发资源边界。

144 生产输入及失败 DCP 的运行后身份由 A006 核实，本审核没有重读 DCP；observer 85343 真实 exit0 的工具事实由 A006 报告，PID 消失由本审核独立核实。原证据不覆盖，完整来源身份见 [机器记录](native_failure_review.json)。

## 已关闭原生样本与最小解释

`alias_identity_sample.tsv` 实际 9 条数据：前 8 条 parent handle 与 property NAME 逐元素完全相等，而 list 的字符串表示不相等。AT002 对 AT001 表示比较的修复因此已在这 8 个实际对象上成立，不能外推完整 census。

第 9 条为 XDMA escaped identifier：raw handle 含两个 literal 反斜杠，适配后 NAME 仅一个。独立仅读取 `raw_conflicts.tsv` 最后 8192 B，取最后一行；该行来源是归档源码直接 scalar `get_property NAME`，与 raw handle 字节相等，未进行任何去转义。工程保存的 `escaped_identifier_saved_evidence.json` 与此一致。

归档 `vals` 对单对象返回值先作 `llength`，当前字符串仍被解释为一个元素，因此不会触发 fallback；随后 Tcl list 遍历会解释反斜杠。独立执行原 `vals` 函数并输入上述保存的 scalar NAME，162 字节变为 161 字节，完全复现相应丢字节；`list $scalar` 原样包装可保持字节。[实际 Tcl 反例](scalar_property_counterexample.tcl)及[输出](scalar_property_counterexample.stdout.txt)已保存。

该失败调用在 list 处理之前的原始返回值没有单独记录。这里明确区分：已保存 direct scalar/handle/适配结果的真实差异，以及对归档函数的离线复现。它们支持 count==1 时保留 scalar 的最小适配；新包仍须保留实际逐元素身份、cardinality 与失败回执，在后续原生执行中确认，不可盲目 unescape 或删资格检查。

## 后续边界

同范围 AT003 可按现授权准备、增量审核和续跑；只改 scalar/list 适配及相应回归、来源绑定。canonical/端点全集、分组与 coverage 均未闭合，不记 G1 PASS，不选择候选。无新 EDA/DCP 读取、生产改动、进程信号/锁控制或查询范围扩张。
