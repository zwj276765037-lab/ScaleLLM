# M001 Hardware Migration

Source: `/home/user/EDA-202/zhuowenjun/ScaleLLM/1_Hardware` (read-only).
Destination: `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/hardware`.
No writes were made to software, shared management records or the source tree.
No additional agents or real experiments were started.

## Included And Excluded

The two production entry manifests close over5 manifests and88 leaves.
Focused TBs add only their small RTL/include/vector dependencies. Host runtime,
current numerical/reference/export helpers, focused Python contract tests,
board create/build/audit scripts and reviewed XDC are retained.

The build actually sources `mission0004_metadata_physical.tcl` and
`mission0005_coordinated_physical.tcl`; their historical names are preserved.
They are code dependencies, not copied mission management. Old diagnostic
checkpoints/fixtures referenced by historical helper procedures are not included.

Excluded: `.Xil`, Python caches, `vivado/project`, `vivado/reports`, large
`data/rebuild_v5_realmodel`, unrelated variants/optimization drivers and
historical goal/mission/result management. Three small native025 terminal files
are instead copied byte-identically into `evidence/native025/`; embedded relative
report/DCP names still refer to the external original report directory.

## Identity And Adaptation

`migration/source_snapshot.json` records the original pre-adaptation copy.
`migration/source_dest_sha256.json` records every source/destination SHA256,
absolute path, byte count and adapted flag. Source files are rehashed on verify.
`migration/adaptations.json` lists the four destination-only software-reference
path changes. RTL, numerical functions, manifests, XDC, build scripts, golden
SHA256 and acceptance assertions are unchanged.

Current runtime/reference sources use sibling `../software/0_Software`, including
`FPtoQ/experiment/v5_fullchain.py`. Its new and old bytes are identical with
approved SHA256 `58a6bb7c769209925bd3bcd9d1a06414b0a25415a46591f70d8efd62db0b9898`.
Frozen reports/artifacts retain their original input paths; they are not rewritten
or requalified. Future builds/reference outputs require fresh provenance.

## Checks And Limits

`migration/static_checks.json` contains exact counts/bytes and check results.
Checks: copied-source/destination hashes, recursive manifest existence/containment,
Python AST, `bash -n`, Tcl `info complete` without executing Tcl inputs, and
the unchanged format05 structural checker (`migration/contract_check.json`).
Tcl completeness and the SV structural checker are not Vivado parsing or RTL
elaboration. Test suites, Vivado, XSim, GPU, board and real experiments were not
run. Literal TB dependencies are copied; runtime plusarg inputs remain external.

New build paths derive from the launcher/script location and constrain generated
projects/reports to this destination. The old `route` dispatch remains `impl_1`;
it does not apply or implement native025. No candidate-continuation logic was added.
Normal fresh `create/synth/place/route` source dependencies are statically complete.
Execution and same-root synthesis/place/S3 route-admission evidence remain untested.

Native025 is failed/unrouted/non-release diagnostic evidence, not a deployable
baseline. Its copied terminal receipt is historical, not a new measurement.
Large weights/captures, old projects/checkpoints, toolchain/board metadata,
legacy reference and board-programming workflows are not standalone here.
The three existing bitgen entries are explicitly listed in README and the
external index, with their frozen routed/audit/joint/norm/full32 evidence binding
as the reason for exclusion; no acceptance flow was rewritten. Paths are listed in
`migration/external_dependencies.json`. Migration is complete only at the
static organization boundary, not at hardware acceptance.
