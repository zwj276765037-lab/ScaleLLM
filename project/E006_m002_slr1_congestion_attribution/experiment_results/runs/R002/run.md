# R002 — E006

Recorded: 2026-10-16T15:41:11.959037+00:00

Execution state: running
Verdict: supported for source roles and exact target extraction; native attribution pending

- Working directory: `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM`；A007 只执行 CPU 文本分析、hash 与有界源码读取；不启动 EDA/测试，不读大 DCP，不控制进程或锁。
- Targets: [10 route failure nodes / 40 exact net occurrences / 12 separate InstTerms](route_failure_sample_targets.json), 47178 bytes, SHA256 `1f60628af5af11b79fb29f70aebdc8dc3a83e35acb0096f44c693cb6ba1d718f`; parser [source](prepare_failure_sample_targets.py). Original log and audited copy byte-identical; sample is native top10 only, not all failures.
- Hierarchy: [26 exact native hierarchy roots + 13 candidates](hierarchy_attribution_targets.json), 41083 bytes, SHA256 `cf70c5004f753c5ecc0a6b8352c2179499a9b163d9d986ae7d49c0bafe19f4fe`; parser [source](prepare_hierarchy_targets.py). Targets actually delivered to A006/root. Inclusive native LUT totals may overlap across hierarchy; primitive-owner partition and shared-site sets remain separate.
- Source roles: [672 MLP +80 Attention URAM contents/capacity](metadata_uram_roles.md), [15 source identities and exact line evidence](metadata_uram_source_facts.json). All 15 source hashes match the current E005 144-input freeze. This closes the scoped question of metadata versus coefficient storage, not SLR placement or routing causality.
- A006 actual AT001 launched 2026-10-16T15:51:44.063950Z in `R001/attempts/AT001_physopt_attribution`; single original physopt read. A007 checked the 18 bounded source/external input identities; all matched `input_bindings.json`. Original DCP hash binding comes from the engineering receipt; A007 did not read/hash that binary.
- Static query review: exact owner roots precede core fallback; global primitive partition, actual NW cells and unique UNION, site owner sets, native inclusive detail reports, literal failure net lookup and canonical segment deduplication exist. Runtime coverage and actual report values remain pending until closed stage outputs.
- Endpoint interpretation: query enumerates leaf `IN` and `OUT` pins, omitting INOUT and top ports; NO_PRIMITIVE_DRIVER does not prove no external driver. Primitive terminal classifier intentionally leaves many device-specific controls as OTHER; CPU reclassification can use exported REF_NAME/REF_PIN_NAME without modifying the frozen running query. Both boundaries actually messaged to A006.
- Review status: partial results delivered by real messages, no user acceptance recorded. Parent owns E006 summaries/shared navigation and same-stage old/new aggregate analysis. Do not duplicate its baseline parser; focus current native attribution and independent coverage checks.
- Failure/window CPU cross-check: [exact tile membership](failure_nodes_cpu_tile_intersection.json), 7487 bytes, SHA256 `5cf828c1493bb6f23fab467ab1e10cf2a1c8f547c4c69ed4c2ec84203b720a6d`. Ten closed native NW lists have 20784 unique tiles. Only NODE10/INT_X37Y469 from the route-log top10 is in that union (NW001–007 and009); nine samples are outside. This is an exact-name comparison against actual closed tile lists, with no GRID/SLR inference. It disproves treating those ten selected physopt windows as coverage of all ten failure nodes; it does not prove no congestion outside or no causal relationship. Actually notified parent/A006; native tile/SLR query remains the independent cross-check.

A run record alone does not establish PASS or a method verdict.

- Controlled candidate: [input preprocessing to SLR2](input_frontend_locality_candidate.md), exact current selectors/source/resources in [facts](input_frontend_locality_candidate_facts.json). 40,627 CLB FF /31,709 raw LUT primitives /8 DSP /0 BRAM /0 URAM; source cut incomplete until native endpoints. Candidate not implemented.
- Partial hotspot audit prepared as `audit_one_closed_hotspot.py`, gated by each query native0 and report-scope checks; original full-stage audit preserved.

- Lean replacement source review delivered: [concentrated review](lean_candidate_source_review_20261017.md). New planned scope R003/AT001, original R001 evidence retained. Source/guards reviewed only; no EDA/stop/approval inferred. Actual stage audit requires a real event/followup.
