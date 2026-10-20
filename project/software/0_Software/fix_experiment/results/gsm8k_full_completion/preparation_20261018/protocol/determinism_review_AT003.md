# AT008 单算子与权重捕获独立审核

A010 仅使用 CPU8–9；未启动 GPU、改动生产源或放宽验证门。详见 [完整审核](determinism_review_AT003.json) 与 [复算脚本](review_isolated_up_proj_AT008.py)。

原始 `.pt` 文件 SHA 通过；独立重算全部保存输入/完整输出/最终权重哈希、28 份 descriptor，以及 51 对已登记张量比较，零不符。四次 native 输入完全相同；权重的 shape、stride、dtype、storage offset、data/storage pointer 与 117440512 字节大小一致，但调用前权重 SHA 变化，初始与最终 SHA 也不同。

抓取代码使用默认同步 `.cpu()` 后立即消费字节；持久化输入/输出/最终权重另做 CPU `.clone()`，加载后各份 raw tensor 使用独立 storage。未见把异步未完成数据、GPU 指针或可变 CPU 别名直接当哈希证据的实现。最终 raw 权重及转置字节哈希可独立复现；此前权重仅有日志哈希，无法重新逐值核查。

固定最后输入/权重后，`F.linear`、重复使用已填入 0/1/NaN/−1 的输出 buffer、保持存活的六份独立新 buffer，共 18 次完整输出全部 exact/finite，并等于最后一次 native 输出。这里没有复现固定操作数下的算子或输出分配差异。原记录 `all_isolated_operands_identical=false` 是将 18 次最终权重与初始 `weight_before` 比较所致；这 18 次内部的权重 SHA 实际相同。

另外独立比较发现 native1 与 native2 的调用前输入和权重 SHA 相同，输出仍不同，最大差值 `0.00390625`。因此不能仅凭跨调用权重变化就完整解释所有输出差异；还缺每次算子前后权重 raw 副本与同步时间边界。

本次接受“捕获到权重字节身份异常；固定最后权重的局部算子可重复”。未接受 backend、allocator 或 GPU 硬件根因，也没有已验证修复。磁盘 checkpoint 对照另见 [后继独立审核](determinism_review_AT004.md)。
