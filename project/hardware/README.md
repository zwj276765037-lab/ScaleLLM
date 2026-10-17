# ScaleLLM Hardware Core

Current M002 update (2026-10-15): RTL/Host/build repairs and scoped quick validation are complete. Host CPU regressions, four directed XSim tests, full board RTL elaboration and actual BD validation have run. BD address-alias critical warnings remain documented; no formal synthesis, implementation, bitstream or board acceptance has run. See [M002 report](../../results/missions/M002_summary.md) and [dedicated DDR contract](source/m002_dedicated_ddr.md). The M001 paragraphs below describe the historical migration only.

M001 is a compact copy of the preserved hardware core, not a new qualified
implementation. Only static migration checks were performed. No Vivado, XSim,
GPU, board access, functional test or real experiment was run.

- `rtl/`: format05 attention + MLP production closure and small TB support.
- `host/`, `model/`: runtime, layout, export and numerical reference sources.
- `tb/`, `tests/`, `data/`: focused regressions, ROMs and compact input vectors.
- `vivado/scripts/`, `vivado/manifests/`, `vivado/constraints/`: build inputs.
- [Core specification](source/design.md), [migration record](MIGRATION.md).
- [Hash mapping](migration/source_dest_sha256.json),
  [path adaptations](migration/adaptations.json),
  [static checks](migration/static_checks.json),
  [external evidence/dependencies](migration/external_dependencies.json).

Target: `0x48384605` / ABI `0x00050000`, core100 / DDR UI200/200 MHz,
two distinct cohort16 contexts. Gate/Up uses S37/F24 guards and S44 accumulation
to S24/F16; Down uses S45/F24 guards and S54 accumulation to S32/F16.

The preserved launcher is `vivado/scripts/run_vcu118_board.sh`; it computes its
root from its own location and creates projects/reports only inside this tree.
Normal fresh `create/synth/place/route` source dependencies are complete under
the static manifest/path check, including sourced Tcl helpers, ROMs and XDC.
Vivado2025.2 and its indexed VCU118 board metadata remain external tool inputs.
It is not authorized to run under M001. Its `route` stage resumes `impl_1`,
not native025. No candidate-continuation branch was added.
Route still requires fresh same-root synthesis/place identities and an S3 PASS
screen; no generated project or gate evidence is supplied by this migration.

## Bitgen Not Migrated

Existing entries remain at these read-only source paths:

```text
/home/user/EDA-202/zhuowenjun/ScaleLLM/1_Hardware/vivado/scripts/run_mission0005_bitgen.sh
/home/user/EDA-202/zhuowenjun/ScaleLLM/1_Hardware/vivado/scripts/mission0005_bitgen.tcl
/home/user/EDA-202/zhuowenjun/ScaleLLM/1_Hardware/vivado/scripts/mission0005_post_route_gate.py
```

They require same-root routed/audit reports plus adopted norm, real joint and
full32 status/source identities. Those frozen historical inputs are not migrated;
the gate also binds historical golden-source paths. Copying or rewriting this
acceptance flow is outside M001. Do not execute these old entries to write into
the preserved source tree. Bitgen is not a standalone new-project entry here.

Native025 is failed, unrouted diagnostic evidence, not a deployable baseline.
Only its small receipt/state/timing table are copied into `evidence/native025/`.
Large inputs, old projects, checkpoints and history remain external and read-only.
Current software authority resolves to sibling `../software/0_Software`; its
`v5_fullchain.py` is byte-identical to the approved old source. Frozen evidence
retains its original paths and is not requalified.

Recheck migration only: `python3 -B tools/migration.py verify` from this directory.
This uses AST, manifest, Bash syntax, Tcl completeness and the preserved static
format05 checker; it does not execute test suites or hardware tools.
