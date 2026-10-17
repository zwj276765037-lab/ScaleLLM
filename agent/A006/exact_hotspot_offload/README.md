# E008 exact-hotspot offload entry — prepared, native not run

Owner A006. This is a new isolated entry for SM012/E008. R004 running source and E007 exploratory source remain unchanged. No candidate is selected by this directory, and this preparation does not start, queue or stop EDA.

The input is E005/R004/AT003 debug_materialized.dcp (396068466 bytes, SHA256 8451b2a86885d5ebb7bcb58dc24c352ac442492425c174269f9a803bb39c202f), its actually successful place/physopt parent, 144 frozen production inputs and 175 inherited constraint sources. E007 contributes reviewed source only. Native execution remains NOT_RUN.

The successor contract is mission/M002_ddr_separation_and_timing_recovery/exact_hotspot_offload_implementation_contract_2026-10-17.md (6420 bytes, SHA256 1a9253d3d5acd9988f497410bbd132383dcddaad36f02456bccc293a55457e8f). R004 evidence selects exactly C01 or C02. Actual E008 pre-place RAW/S/P membership and physical policy must be qualified again; no physopt count equality, old input banks, quantizers, Hadamard ancestry, 8-DSP or no-BRAM assertion is retained.

The implementation controller retains the prior E005-derived restore and 80 boundary/clock/reset/CDC/IO gates and full place(SSI_SpreadSLLs) → physopt(Default) → route(Default), with no incremental checkpoint read. One hard SLR2 Pblock preserves all prior constraints. Unknown or dedicated clock/IO resources are retained in the ledger and cannot pass migration qualification without an explicit actual explanation. DSP internals use actual DSP48E2 parents; RAMB18/36 and URAM remain separate resource classes. The resource ledger records native IS_PRIMITIVE and supported PRIMITIVE_* attributes rather than inventing support for absent properties. Every actual object still has native list_property checked; identical full support lists are exported once in candidate_resource_native_property_support.tsv and referenced by support_id, without REF-level sampling.

Literal-root site snapshots use candidate_literal_site_members_<phase>.tsv; reconciled actual-P site snapshots use candidate_site_members_<phase>.tsv. Both are exclusive new files, independently retained. The actual two Tcl open commands are exercised across place/physopt/route to reject filename collisions.

R004's actual unquoted-literal-TAB join defect is fixed in the new writers. The necessary CPU admission checks execute the new Tcl writer against brackets, empty fields and multiword values, then parse it; they also replay both actual closed R004 ledgers through the new generic membership checker. This is CPU source validation, not E008 native qualification. Original source derivation and subsequent narrow source repairs are recorded through current file identities; prepare_initial_sources.py must not be rerun after admission.

Actual execution binding is supplied by Root only when the R004 dependency has closed. The runner requires this JSON schema in --e006-closeout:

```json
{
  "phase": "E006_attribution_closed",
  "successor": "SM012/E008",
  "engineering_execution_verified": true,
  "candidate_scope_supported": true,
  "selected_candidate": {"id": "one actual C01 or C02", "root": "the exact matching authority root"},
  "successor_contract": {"path": "absolute contract path", "bytes": 0, "sha256": "actual identity"},
  "preparation_manifest": {"path": "absolute prepared_manifest.json path", "bytes": 0, "sha256": "actual identity"},
  "terminal_status": {"path": "absolute actual E006 terminal status path", "bytes": 0, "sha256": "actual identity"},
  "evidence": [{"path": "absolute actual closure/independent review evidence path", "bytes": 0, "sha256": "actual identity"}]
}
```

The schema above is documentation only, not an executable support receipt. Empty/unsupported selection or false/missing support is rejected. All evidence identities and real PID/start closure are checked. Root owns experiment/attempt registration; the entry accepts a fresh attempt or the untouched organizer scaffold in E008/R001. Runtime directories and detached receipts are never overwritten.

After actual selection and single-EDA-lane closure, the prepared launcher is:

```text
python3 agent/A006/exact_hotspot_offload/launch_detached.py --attempt <new absolute E008/R001/attempts/AT...> --report <new absolute reports/m002_E008_R001_...> --e006-closeout <actual absolute Root closure binding>
```

No normal wall-clock or silence stop. CPU0–7/nice5/max8 and tree RSS192GiB / MemAvailable48GiB for30s / disk30GiB protections are unchanged. No bitstream, GPU, board, PPL/ACC, algorithm, ABI or clock changes. No old workspace mutation. A006 remains the only EDA executor; Root/A007 receive actual stage evidence and independently judge support and results.
