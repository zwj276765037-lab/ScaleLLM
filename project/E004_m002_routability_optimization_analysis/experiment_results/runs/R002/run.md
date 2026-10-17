# R002 — E004

Recorded: 2026-10-15T23:14:52.166539+00:00

Execution state: completed
Verdict: supported (source-structure facts only; candidate physical benefit/equivalence unverified)

- Exact command and working directory: `python3 project/E004_m002_routability_optimization_analysis/experiment_results/runs/R002/recompute_rtl_evidence.py`, cwd `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM`; bounded text/source reads documented in the report.
- Host, tool and platform versions: CPU/Python3 standard library only; no EDA process/license/device use. Baseline platform identity: Vivado2025.2, xcvu9p-flga2104-2L-e, core100MHz/UI200+200MHz.
- Code identity (commit/hash), external constraints and IP identity: 17 current target RTL hashes match the frozen fresh_synth inputs manifest and route effective active build; successful physopt evidence directly binds this same manifest. Full file identities in `rtl_evidence.json`; no new XDC/IP variants.
- Input/data identity and reproducibility inputs: E003 original route vivado.log; successful physopt diagnostic_evidence synthesis binding; fresh_synth inputs.sha256; route effective_build_identity.txt; explicit 17 RTL files and 3 auxiliary TB/design references, all recorded in JSON.
- Start/end times: current NEW_TASK session on 2026-10-15 UTC; exact spawn timestamp not independently captured. First retained evidence creation observed 23:21:51 UTC; final recompute/end time recorded in `rtl_evidence.json` / `analysis_receipt.json`.
- Exit status and infrastructure errors: final recompute exit0; no EDA/infrastructure failure. A multi-file documentation patch initially failed because parent had already updated config.md; parent edits were preserved and the patch was narrowed. No production mutation.
- Independent oracle, expected values and acceptance criteria: SHA256 equality against existing synthesis manifest and successful physopt binding; 24×256/16×384 coverage; all 4096 context addresses enumerated exactly once; original log extraction finds exactly10 nodes/3 signals each. These are arithmetic/identity checks, not RTL functional or physical tests.
- Evidence paths and qualified scope: [RTL report](rtl_routability_analysis.md), [source/math/log evidence](rtl_evidence.json), [recompute command](recompute_rtl_evidence.py), [receipt](analysis_receipt.json). Input/context/postprocess/output/projection structure and 10 printed route nodes only.
- Observations and limitations: 6144b cascaded selections/snapshot; postprocess24576 declared payload bits; projection deliberate local duplication. Static local CE scheme is 24 decoder boundaries per input wave, 48 across both waves, plus64 context=112 explicit boundary instances; not net LUT delta. Singlebank potential12288b source payload reduction requires accepted-phase/visibility contract verification; frontend narrowing/sharedloader require ownership/cycle changes. No full failure-node attribution, candidate implementation, netlist delta, routability/timing or board qualification.

Owner: A008 `/root/m002_rtl_routability_explorer`. Review: pending controller/A007. Production code, constraints and raw E003 evidence remain read-only. Shared three summaries and generated indexes are owned by parent and not edited here.

## Follow-up: existing testbench coverage mapping

On the parent's additional bounded request, appended report §9 after checking the dualwave buffer/local stores/compute scheduler TBs, one source manifest and the existing runner. No simulation or EDA. The original report SHA was verified against `analysis_receipt.json` and preserved under `revisions/rtl_routability_analysis_20261015T233027Z.md`; original receipt/evidence remain unchanged. New follow-up identities and static check-count arithmetic are in `tb_regression_mapping_evidence.json`.

Reusable direct TBs cover production widths, all24 input slots across2×128 groups, short ready stalls, and one16-slot context transfer/drain. They do not pulse clear/reset during operation; context only covers wave0/group5 without read_issue gaps. The compute scheduler TB uses a projection stub and all-zero payload, so it is not a transport/numerical oracle for the slot rewrite. Report §9 gives the smallest new interruption/epoch/stall/drain monitors and identifies the current runner's wall timeout policy that must be adapted before actual execution. Follow-up execution completed, source-analysis-only verdict supported; no new PASS claimed.

A run record alone does not establish PASS or a method verdict.
