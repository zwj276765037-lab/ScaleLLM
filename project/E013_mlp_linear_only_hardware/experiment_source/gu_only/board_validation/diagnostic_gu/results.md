# Diagnostic preparation results

Execution: completed CPU preparation. Verdict: `CPU_PREPARATION_PASS`. Board execution by this author: `NOT_RUN`. Source, full artifacts, hashes, independent literals and per-matrix/per-half statistics are recorded in [delivery_report.json](../../../../experiment_results/board_validation/diagnostic_gu/delivery_report.json). Actual device tests are owned by the host engineer and require passing readiness first.

| Case | Independently checked S24 values | Nonzero | Positive | Negative | Tail32 nonzero | Saturation endpoints |
|---|---:|---:|---:|---:|---:|---:|
| structured_v1 | 458752 | 458752 | 269657 | 189095 | 1024/1024 | 64 deliberate |
| s37_cancellation_v1 | 458752 | 457968 | 456112 | 1856 | 1024/1024 | 0 |

Both complete wire oracles passed, including 120 scalar samples each, all padding/canonical checks and inactive-group audits. The primary case covers total shifts20/24/25/44. Every row has 28672 nonzero results; each matrix/half has 114688 nonzero results. Primary tail column14335, rows0/7/8/15: Gate `[-15500,100193,-145349,-237050]`, Up `[26118,-121985,-71540,225327]`. Columns0/1 are exactly +1/-1 for all rows and matrices; columns7/8 are +8388607/-8388608.

The S37 supplement reaches guard min/max `-67917312000/+59427648000`, with 6881280 per-group guards outside S36. Peak exact partial S44 magnitude is475421184000. Its final range is[-48,7160], with no saturation. For Gate,row0,column0 the correct output is1; truncating guard to S36 produces-8388608, so the final small result distinguishes the guard width.

Original exporter byte parity passed on 12 complete matrix/tiles per bundle, each containing all128 groups and both halves. CPU scripted driver checks passed for one/two cohorts, persistence before ACK, failure at the first numerical mismatch with no ACK/second START, and diagnostic provider layer/Down/hash/size rejection. The fixture mismatch is Gate,row0,column0, byte0, expected1/actual0. Injected CPU outputs and DONE do not demonstrate any DUT arithmetic or real board behavior.

Primary file identities:

| Artifact | Bytes | SHA256 |
|---|---:|---|
| weight half0 | 29360128 | `0843d28bd15904b74c566a9f9ebc2b548109fff3698d829b9aa848cd7af878a4` |
| weight half1 | 29360128 | `3e81a6a41c67e391202a19b380eec3fa03133f8f01eaac2432d64ec1b139c093` |
| metadata | 7340032 | `1212290fe1cf515d79c1ebd3e5b922ea36615d3d8a543d40352ae213eed2ee4d` |
| REC576 input | 73728 | `5cd2923cad5f48f0930f511f51a897f5293c8ceaae2e0d468756b168714eea2f` |
| GU S24 gold | 1376256 | `23e993b366a9e90580237ab63474f2813bf0f6009aced7f701ba2bc6893b20bc` |

Full supplement identities and numerical/packing evidence are in its own manifest/verification/coverage reports. Generated binary inputs and gold are frozen; delivery summaries add evidence without rewriting original manifests. Shared indexes and project three-summary files were not edited by this author.
