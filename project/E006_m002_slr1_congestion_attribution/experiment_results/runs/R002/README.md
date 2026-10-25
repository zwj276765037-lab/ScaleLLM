

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# E006 / R002 运行结果

[负责人维护的本批运行记录](run.md)

# R002 — E006

Recorded: 2026-10-16T15:41:11.959037+00:00

Execution state: running
Verdict: supported for source roles and exact target extraction; native attribution pending

- Working directory: `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM`；A007 只执行 CPU 文本分析、hash 与有界源码读取；不启动 EDA/测试，不读大 DCP，不控制进程或锁。
- Targets: [10 route failure nodes / 40 exact net occurrences / 12 separate InstTerms](route_failure_sample_targets.json), 47178 bytes, SHA256 `1f60628af5af11b79fb29f70aebdc8dc3a83e35acb0096f44c693cb6ba1d718f`; parser [source](prepare_failure_sample_targets.py). Original log and audited copy byte-identical; sample is native top10 only, not all failures.
- Hierarchy: [26 exact native hierarchy roots + 13 candidates](hierarchy_attribution_targets.json), 41083 bytes, SHA256 `cf70c5004f753c5ecc0a6b8352c2179499a9b163d9d986ae7d49c0bafe19f4fe`; parser [source](prepare_hierarchy_targets.py). Targets actually delivered to A006/root. Inclusive native LUT totals may overlap across hierarchy; primitive-owner partition and shared-site sets remain separate.
- Source roles: [672 MLP +80 Attention URAM contents/capacity](metadata_uram_roles.md), [15 source identities and exact line evidence](met

（摘录截断；完整记录见链接。）

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |

## 本批问题与交付文件

- [attribution_review.md](attribution_review.md)
- [input_frontend_locality_candidate.md](input_frontend_locality_candidate.md)
- [lean_candidate_source_review_20261017.md](lean_candidate_source_review_20261017.md)
- [metadata_uram_roles.md](metadata_uram_roles.md)

## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
