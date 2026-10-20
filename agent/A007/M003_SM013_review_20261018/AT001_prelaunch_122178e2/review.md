# E009 / R001 / AT001：固定诊断包启动前独立审核

2026-10-18；A007。**结论：该固定包在当前 M003 / SM013 合同内可执行，无需新增用户批准；未发现实质启动阻断项。** A006 绑定本审核与固定包身份后可直接启动。此结论不代表已经启动、原生 API 已通过、G1 完成或候选有效。

- execution：静态源码/范围/保护核查及隔离 CPU 对照重放完成。
- verdict：准备包可执行；原生数据完整性、547548 网对账及性能待运行证据。
- applicability：`prepared_manifest.json` 为 3451 B，SHA256 `122178e2627308307b859e8baba6334b639fc257b6c457d9afe5bd8a69f17f6d`；仅此固定范围和来源。
- review：内部独立启动前审核通过；用户结果审核及 G1/G2 技术验收未被代替。

## 已核内容

1. 清单中 12 个源/计划/参考文件逐项 size/SHA 与实际文件一致，已保存在本目录 `source_snapshot/`。准备 preflight 文件的 size/SHA 与清单一致；CPU 重放实际 exit0、stderr 空，见 `cpu_replay.json` 和原输出。没有读取或重新 hash DCP。
2. `attribution.tcl` 只打开已保存失败图和取数，未见综合/opt/place/physopt/route、写 DCP、read_xdc、set_property 或生产修改。真实 `ROUTE_STATUS` schema/enum、`CONFLICTS` 对象、原生 route report 和 raw conflict 名单均保存。canonical 基于每网原生 segment 闭包、NAME 字典序和缓存；发现闭包冲突或必需属性错配即失败。
3. census 与固定补充网导出全量 leaf pin 和顶层 port；同网 leaf pin 和 port 分别去重，port 方向反转到驱动/负载语义。缺驱动、多驱动、INOUT、unknown endpoint、未知位置及不可得字段保留。driver 归一最多到 u_compute 下四层且保留 generate 索引，主组唯一；consumer/clock-region 辅表不相加为全量网。
4. 真实叶端点属性按 16384 pin 批量，cell 属性分块读取，alias 和 endpoint 输出大缓冲；4096 网才打一次进度。无逐 pin puts+flush、无全设计 source×sink 笛卡尔积；原生 alias 查询仍按不同闭包逐网执行，实际耗时尚未测得，不预称已加速。
5. top20 主组确定排序，深属性取每组最多 16 个字典序代表网；补充 parent head/tail、meta 地址、80 保护、top10 literal 和原 C01 已测跨 SLR 字典序前 16 网固定。deep endpoint 仅这些网，无递归 fanin/fanout；每 timing tag 最多 16 网、16 load pins、max/min 各 2 paths。query plan 中 candidate roots 为候选框架，不暗含全 root 递归查询。
6. `aggregate.py` 按唯一 canonical ID 分组和 union；小规模重放覆盖 raw/canonical 计数差、多驱动、未知、INOUT、补充交集去重和源/负载 SLR。此 CPU 对照仅核计算/实现，不能证明 Vivado 返回的 segment/方向/属性集合完整。
7. supervisor 对 12 源、review 与 manifest 绑定；持唯一锁后重核 baseline、144 生产输入、旧 PID/start 消失和 EDA 空闲；归档源再进入原生命令。CPU0–7、max8、nice5、RSS192GiB、MemAvailable48GiB 持续30s、disk30GiB 及按原 PID/start 身份清理逻辑保留。无墙钟/无输出超时条件；正常 route 失败图只用于只读取数。
8. launcher 回执明确只证明监督器请求，真实 native `started.json`、命令/进程及锁仍需单独核验。自然 exit、监督 exit、stop_reason、残留清理及最终身份重核分开，旧 raw 产物不覆盖。

## 原始来源归因

A006 preflight 于 `2026-10-18T00:35:44.231483+00:00` 报告：144 输入匹配、旧 PID/start 消失、无活动 EDA/编译、锁获取并释放；MemAvailable 529587396608 B，disk free 415677931520 B。该记录与冻结清单绑定；实际启动前 supervisor 再查，本审核没有将过去的空闲探针当成未来锁保证。

失败 DCP 为 765705446 B / SHA256 `51679d9a4f8dc35c5e5b167ebbecd72260b0862f85ad8168782646f0fc16da21`，是 **A006 工程核验归因**，A007 未读 DCP。既有 E008 收尾审核沿用；本次未重跑原收尾。

## 运行后必须如实区分的证据

- `top20_unique_conflict_nets` / `coverage_fraction` 是前 20 主组与补充集合的**网级分类覆盖**；deep properties 每组仅 16 个代表网。必须同时据 `deep_selected.tsv` 报实际深查网数/交集，不能把全组覆盖率表述成每个组内网都深查、或“根因已解释比例”。全量 endpoint 分类本身仍覆盖 census。
- 聚合器的 `native_report_conflict_nets=547548` 和 overlap=702396 是固定 E008 基线数字；G1 应关联本次真实 `native_route_status.rpt` / enum / raw conflicts 复核。raw 数、canonical 数、原生 report 数差异不强行配平；`DIFFERENT_COUNTS_RETAINED_REQUIRES_REVIEW` 不是全量资格 PASS。
- literal seed 未找到、schema 属性不可得、无 load timing 或 timing 原生错误都必须保留缺口。`--final` / `native_completed.txt` 仅表示预定采集流程结束，不表示关键候选事实或 G1 自动关闭。
- segment 语义、leaf/port 完整性、DCP 载入与 native `CONFLICTS` 口径要由本次实际数据核实。准备对照不替代原生资格，不用旧样本代替全量。
- G1 未关闭时保持候选未选。用于 G2 的特定候选仍须完整 F1/F2/F3/F4 证据；CPU 分类成功或某热点落区不证明下一轮能布通。

以上为数据解释和后续验收边界，不要求热改已封包或新增用户批准。发生普通适配失败时按原授权保留失败证据、同范围新 AT，并仅审核实际变化和受影响语义。
