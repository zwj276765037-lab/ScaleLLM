#!/usr/bin/env python3
"""Launch only M002 diagnostic project implementation; preserve every attempt."""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from m002_physical_evidence import (ROOT, file_id, finalize, input_manifest, parent_place,
                                    require, sha256, synth_lineage, recovery_parent, recovery_opt_parent, recovery_pre_place_parent, cdc_critical_records,
                                    PRIMITIVE_MODEL_ROOT, PRIMITIVE_MODEL_HASHES, BRAM_MODEL_HASHES)


def tcl_literal(value: str) -> str:
    require(not any(c in value for c in "{}\r\n"), "unsupported generated Tcl literal")
    return "{" + value + "}"


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"place", "route"}, "expected place or route")
    stage = sys.argv[1]
    project, report, synth_report, synth_attempt = (Path(os.environ[k]).resolve() for k in (
        "HAP_PROJECT_DIR", "HAP_REPORT_DIR", "HAP_SYNTH_REPORT_DIR", "HAP_SYNTH_ATTEMPT_DIR"))
    require(project.is_relative_to(ROOT / "vivado/project") and
            report.is_relative_to(ROOT / "vivado/reports") and not report.exists(), "invalid/reused output")
    lineage = synth_lineage(project, synth_report, synth_attempt)
    parent = None
    if stage == "route":
        parent_path = Path(os.environ["HAP_PLACE_REPORT_DIR"]).resolve() / "diagnostic_evidence.json"
        parent_value = parent_place(parent_path, project, lineage)
        parent = {"evidence": file_id(parent_path), "checkpoint": parent_value["checkpoint"]}
    report.mkdir(parents=True)
    recovery = bool(os.environ.get("HAP_INIT_REPORT_DIR") or os.environ.get("HAP_OPT_REPORT_DIR") or os.environ.get("HAP_PRE_PLACE_REPORT_DIR")) or bool(parent and parent_value.get("execution_mode") == "checkpoint_restored_commands")
    if recovery:
        os.environ["HAP_EXECUTION_MODE"] = "checkpoint_restored_commands"
        if stage == "place":
            opt_recovery = bool(os.environ.get("HAP_OPT_REPORT_DIR"))
            pre_place_recovery=bool(os.environ.get("HAP_PRE_PLACE_REPORT_DIR"))
            key="HAP_PRE_PLACE_REPORT_DIR" if pre_place_recovery else "HAP_OPT_REPORT_DIR" if opt_recovery else "HAP_INIT_REPORT_DIR"
            inherited_report = Path(os.environ[key]).resolve()
            inherited = (recovery_pre_place_parent if pre_place_recovery else recovery_opt_parent if opt_recovery else recovery_parent)(inherited_report, project, lineage, report)
            os.environ["HAP_RECOVERY_PARENT_REPORT"] = str(inherited_report)
            os.environ["HAP_RECOVERY_CHECKPOINT"] = inherited['checkpoint']['path']
            os.environ["HAP_RECOVERY_PHASE"] = inherited['phase']
            os.environ['HAP_RECOVERY_OPT_EVIDENCE_COMPLETE'] = str(int(inherited.get('opt_evidence_complete',False)))
            if inherited.get('inherited_reset_evidence'):
                os.environ['HAP_INHERITED_RESET_GRAPH']=inherited['inherited_reset_evidence']['graph']['path']
                os.environ['HAP_INHERITED_RESET_FANOUT']=inherited['inherited_reset_evidence']['fanout']['path']
                if inherited['inherited_reset_evidence'].get('bram_port_clocks'):
                    os.environ['HAP_INHERITED_BRAM_PORT_CLOCKS']=inherited['inherited_reset_evidence']['bram_port_clocks']['path']
            if opt_recovery and not inherited.get('opt_evidence_complete'):
                shutil.copy2(inherited_report/'opt_command_result.txt',report/'opt_command_result.txt')
        else:
            os.environ["HAP_RECOVERY_PARENT_REPORT"] = str(parent_path.parent)
            os.environ["HAP_RECOVERY_CHECKPOINT"] = parent_value["checkpoint"]["path"]
    scripts = Path(__file__).parent
    code = sorted([*scripts.glob("m002_diagnostic*.tcl"), scripts / "m002_physical.tcl",
                   scripts / "m002_impl_threads.tcl", scripts / "m002_resume_physical.tcl", scripts / "m002_physical_evidence.py",
                   scripts / "emit_current_board_evidence.py",
                   Path(__file__), scripts / "run_managed_eda.py"])
    archive = report / "stage_sources"
    archive.mkdir()
    for path in code:
        shutil.copy2(path, archive / path.name)
    (report / "archived_sources.sha256").write_text("".join(
        f"{sha256(p)}  {p}\n" for p in sorted(archive.iterdir())))
    identities = [synth_report / n for n in ("inputs.sha256", "build_identity.txt", "fresh_synth_complete.txt")]
    identities += [synth_attempt / n for n in ("synth_checkpoint_bindings.sha256", "synth_checkpoint_bindings.json", "status.json")]
    identities += [synth_attempt / "cdc_critical_rows.json", synth_report / "cdc_post_synth.rpt"]
    identities += [PRIMITIVE_MODEL_ROOT/(ref+'.v') for ref in (*PRIMITIVE_MODEL_HASHES,*BRAM_MODEL_HASHES)]
    identities += [ROOT/'vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/cdc_opt.rpt']
    if recovery and stage == "place":
        inherited = json.loads((report / "recovery_parent.json").read_text())
        identities += [report / "recovery_parent.json", Path(inherited["checkpoint"]["path"])]
        identities += [Path(inherited[k]["path"]) for k in ("status","launcher","child_log","command","stage_inputs","archive","implementation_settings","source_registry") if inherited.get(k)]
        identities += [Path(x["path"]) for x in inherited["inherited_reports"].values()]
        identities += [Path(inherited[k]['path']) for k in ('upstream_recovery','opt_command','parent_constraints','controlled_stop',
            'post_termination','resource_samples','frozen_child_log','completed_report_integrity') if inherited.get(k)]
        if inherited.get('inherited_reset_evidence'):
            reset=inherited['inherited_reset_evidence']
            identities += [Path(reset[k]['path']) for k in ('graph','fanout')]+[Path(row['path']) for row in reset['exports']]
            identities += [Path(row['path']) for row in reset.get('auxiliary_cdc_reports',[])]
            if reset.get('bram_port_clocks'):identities.append(Path(reset['bram_port_clocks']['path']))
        identities += [Path(inherited[k]['path']) for k in ('inherited_pre_place','inherited_integrity','terminal_cost','inherited_post_manifest','post_termination_post_completion') if inherited.get(k)]
        identities += [Path(x['path']) for x in inherited.get('historical_command_receipts',{}).values()]
        identities += [Path(x['path']) for x in inherited.get('inherited_proof_sources',[])]
        if inherited.get('inherited_post_manifest'):identities += list(input_manifest(Path(inherited['inherited_post_manifest']['path'])))
        for kind in ('generated_phy','generated_debug'):
            if kind in inherited:
                generated = inherited[kind]
                identities += [Path(generated[k]['path']) for k in ('evidence','manifest')]
                identities += list(input_manifest(Path(generated['manifest']['path'])))
    if parent:
        identities += [Path(parent["evidence"]["path"]), Path(parent["checkpoint"]["path"])]
    (report / "stage_inputs.sha256").write_text("".join(
        f"{sha256(p)}  {p}\n" for p in sorted(set(code + identities))))
    warnings = project / "scalellm_vcu118_f05.runs/scalellm_vcu118_f05_bd_core_0_synth_1/runme.log"
    registers = sorted(set(re.findall(r"WARNING: \[Synth 8-7137\] Register (.*?) in module", warnings.read_text())))
    critical = json.loads((synth_attempt / "cdc_critical_rows.json").read_text())["rows"]
    targets = [re.split(r"\s{2,}", row["raw"].strip())[-1] for row in critical]
    probe = "set ::m002_warning_registers [list " + " ".join(tcl_literal(x.rsplit(".", 1)[-1]) for x in registers) + "]\n"
    probe += "set ::m002_cdc_targets [list " + " ".join(tcl_literal(x) for x in targets) + "]\n"
    critical_source = (Path(inherited['inherited_reports']['cdc_debug_materialized.rpt']['path'])
        if recovery and stage=='place' and inherited.get('phase')=='post_debug_pre_place' else
        Path(inherited['inherited_reports']['cdc_opt.rpt']['path'])
        if recovery and stage == 'place' and inherited.get('opt_evidence_complete') else
        parent_path.parent/'cdc_physopt.rpt' if stage=='route' else None)
    if critical_source is not None:
        actual_critical = sorted(cdc_critical_records(critical_source))
        probe += "set ::m002_actual_critical_sources [list " + " ".join(tcl_literal(x) for x in sorted({row[3] for row in actual_critical})) + "]\n"
        probe += "set ::m002_actual_critical_targets [list " + " ".join(tcl_literal(x) for x in sorted({row[4] for row in actual_critical})) + "]\n"
        pairs = sorted({(row[1],row[2]) for row in actual_critical})
        probe += "set ::m002_actual_critical_clock_pairs [list " + " ".join(
            "[list " + tcl_literal(a) + " " + tcl_literal(b) + "]" for a,b in pairs) + "]\n"
    (report / "probe_targets.tcl").write_text(probe)
    with (report / "stage_inputs.sha256").open("a") as handle:
        handle.write(f"{sha256(report / 'probe_targets.tcl')}  {report / 'probe_targets.tcl'}\n")
        if critical_source is not None and critical_source not in identities:
            handle.write(f"{sha256(critical_source)}  {critical_source}\n")
    shutil.copy2(report / "probe_targets.tcl", archive / "probe_targets.tcl")
    (report / "archived_sources.sha256").write_text("".join(
        f"{sha256(p)}  {p}\n" for p in sorted(archive.iterdir())))
    vivado = os.environ.get("VIVADO_BIN") or shutil.which("vivado") or "/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado"
    env = {**os.environ, "HAP_STAGE": stage, "HAP_REPORT_DIR": str(report)}
    command = [vivado, "-mode", "batch", "-notrace", "-source", str(scripts / ("m002_resume_physical.tcl" if recovery else "m002_physical.tcl")),
               "-log", str(report / "vivado.log"), "-journal", str(report / "vivado.jou")]
    (report / "command.json").write_text(json.dumps({"argv": command, "stage": stage,
        "environment": {k:v for k,v in env.items() if k.startswith("HAP_")},
        "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "execution_mode": "checkpoint_restored_commands" if recovery else "project_runs", "synthesis": lineage, "managed_attempt": os.environ["HAP_CURRENT_ATTEMPT_DIR"]}, indent=2) + "\n")
    native = subprocess.run(command, cwd=ROOT / "vivado", env=env).returncode
    run_dir = project / "scalellm_vcu118_f05.runs/impl_1"
    # Freeze child evidence even if a POST check deliberately stopped the run.
    if recovery:
        shutil.copy2(report / "vivado.log", report / "implementation_run.log")
    if not recovery and (run_dir / "runme.log").is_file() and not (report / "implementation_run.log").exists():
        shutil.copy2(run_dir / "runme.log", report / "implementation_run.log")
    native_dir = report / "native_run_receipts"
    native_dir.mkdir()
    for path in sorted(run_dir.iterdir()) if run_dir.is_dir() and not recovery else []:
        if path.is_file() and (path.suffix in {".tcl", ".rst", ".dcp"} or path.name.startswith(".")):
            shutil.copy2(path, native_dir / path.name)
    rc = native
    try:
        require(native == 0, f"native physical controller exited {native}")
        input_manifest(report / "stage_inputs.sha256")
        require(synth_lineage(project, synth_report, synth_attempt) == lineage, "synthesis lineage changed during stage")
        finalize(stage, project, report, lineage, parent)
    except Exception as exc:
        (report / "evidence_error.txt").write_text(f"{type(exc).__name__}: {exc}\n")
        print(f"M002_EVIDENCE_ERROR: {exc}", flush=True)
        rc = native or 1
    (report / "launcher_status.txt").write_text(
        f"stage={stage}\nexit_code={rc}\nnative_exit_code={native}\nproject={project}\nreports={report}\n")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
