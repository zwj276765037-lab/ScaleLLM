"""Generate review-only copies. Never edits an active production input."""
from pathlib import Path
import difflib

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT/'project/hardware/vivado/scripts'
DEST = Path(__file__).resolve().parent


def change(name, replacements):
    original = (SOURCE/name).read_text()
    text = original
    for old, new in replacements:
        assert text.count(old) == 1, (name, old[:100], text.count(old))
        text = text.replace(old, new, 1)
    (DEST/name).write_text(text)
    return ''.join(difflib.unified_diff(original.splitlines(True), text.splitlines(True),
                                       fromfile=str(SOURCE/name), tofile=str(DEST/name)))


diff = change('m002_physical_evidence.py', [
    ('import m002_synthesis_recovery as synth_recovery',
     'import m002_synthesis_recovery as synth_recovery\nimport m002_fresh_project_opt_recovery as fresh_opt\nimport sys'),
    ('def generated_phy_parent(attempt: Path) -> dict:',
     'def generated_phy_parent(attempt: Path, *, fresh_project: Path | None = None, create_terminal_observation: bool = False) -> dict:'),
    ('    outputs = {}\n    for d in (0,1):',
     '    disabled_cache = (fresh_opt.qualify_disabled_phy_cache(sys.modules[__name__], attempt, value, records, original, fresh_project, create_observation=create_terminal_observation)\n'
     '                      if fresh_project is not None else None)\n    outputs = {}\n    for d in (0,1):'),
    ("        require(len(cached) == 1 and produced['sha256'] == output['sha256'] == cached[0]['sha256'],\n"
     "                'MIG PHY generated/actual output/post-synthesis cache bytes differ')\n"
     "        outputs[module] = {k:{a:b for a,b in row.items() if a != 'source_path'} for k,row in (\n"
     "            ('produced',produced),('output',output),('cache_written_after_synthesis',cached[0]))}",
     "        if disabled_cache:\n"
     "            require(not cached and produced['sha256'] == output['sha256'], 'fresh disabled-cache produced/result PHY mismatch')\n"
     "            pairs = (('produced',produced),('output',output))\n"
     "        else:\n"
     "            require(len(cached) == 1 and produced['sha256'] == output['sha256'] == cached[0]['sha256'],\n"
     "                    'MIG PHY generated/actual output/post-synthesis cache bytes differ')\n"
     "            pairs = (('produced',produced),('output',output),('cache_written_after_synthesis',cached[0]))\n"
     "        outputs[module] = {k:{a:b for a,b in row.items() if a != 'source_path'} for k,row in pairs}"),
    ("            'cache_miss_count':2,'outputs':outputs,'worker_actual_xdc_reads':worker_reads,",
     "            'cache_miss_count':2,'outputs':outputs,'worker_actual_xdc_reads':worker_reads,\n"
     "            **({'fresh_disabled_cache_qualification':disabled_cache} if disabled_cache else {}),"),
    ("    command = json.loads((source / 'command.json').read_text())\n    status_path = Path(command['managed_attempt']) / 'status.json'",
     "    command = json.loads((source / 'command.json').read_text())\n"
     "    if command.get('execution_mode') == 'project_runs':\n"
     "        return fresh_opt.qualify_native_project(sys.modules[__name__], source, project, lineage, report, write=_write)\n"
     "    if (source/'recovery_parent.json').is_file() and json.loads((source/'recovery_parent.json').read_text()).get('opt_execution_proof_kind') == 'native_project_log_derived':\n"
     "        return fresh_opt.qualify_restored_opt(sys.modules[__name__], source, project, lineage, report, write=_write)\n"
     "    status_path = Path(command['managed_attempt']) / 'status.json'"),
    ("        if archived in archive:\n            require(archive[archived] == digest, \"archived execution code differs from old stage manifest\")",
     "        if archived in archive and source.parent.name != 'stage_sources':\n"
     "            require(archive[archived] == digest, \"archived execution code differs from old stage manifest\")"),
    ("    for point,command in ((('physopt','phys_opt_design'),) if placed else (('place','place_design'),('physopt','phys_opt_design')) if restarted else\n"
     "                           (('opt','opt_design'),('place','place_design'),('physopt','phys_opt_design'))):",
     "    log_derived_opt = value.get('inherited_opt_execution_proof')\n"
     "    if log_derived_opt:\n"
     "        require(auth and auth['profile'] == full_impl.OPTIMIZED_PROFILE, 'log-derived OPT inheritance outside E005')\n"
     "        fresh_opt.verify_inherited_proof(sys.modules[__name__], log_derived_opt, project, lineage, report)\n"
     "        expected_new = {'physopt'} if placed else {'place','physopt'} if restarted else {'debug_materialization','place','physopt'}\n"
     "        require(set(value['command_receipts']) == expected_new, 'fresh OPT inherited/new command scopes changed')\n"
     "    for point,command in ((('physopt','phys_opt_design'),) if placed else (('place','place_design'),('physopt','phys_opt_design')) if restarted or log_derived_opt else\n"
     "                           (('opt','opt_design'),('place','place_design'),('physopt','phys_opt_design'))):"),
    ("receipt.get('command')==command and receipt.get('phase')==point,'recovered parent native phase failed'",
     "receipt.get('command')==fresh_opt.expected_physical_command(point, command, auth) and receipt.get('phase')==point,'recovered parent native phase failed'"),
    ("    restarted_placed=bool(restored_parent and restored_parent.get('phase')=='post_place_pre_physopt')\n",
     "    restarted_placed=bool(restored_parent and restored_parent.get('phase')=='post_place_pre_physopt')\n"
     "    log_derived_opt=bool(restored_parent and restored_parent.get('opt_execution_proof_kind')=='native_project_log_derived')\n"),
    ('(("physopt",) if restarted_placed else ("place","physopt") if restarted_pre_place else ("opt","debug_materialization","place","physopt") if stage == "place" else ("route",))',
     '(("physopt",) if restarted_placed else ("place","physopt") if restarted_pre_place else ("debug_materialization","place","physopt") if log_derived_opt else ("opt","debug_materialization","place","physopt") if stage == "place" else ("route",))'),
    ('        "historical_command_receipts": restored_parent["historical_command_receipts"] if restarted_pre_place or restarted_placed else {},',
     '        "historical_command_receipts": restored_parent["historical_command_receipts"] if restarted_pre_place or restarted_placed else {},\n'
     '        "inherited_opt_execution_proof": restored_parent["inherited_opt_execution_proof"] if log_derived_opt else None,'),
    ('else "original_stage_flow",\n        "physical_resume_admission"',
     'else "new_debug_place_physopt__inherited_native_project_opt" if log_derived_opt else "original_stage_flow",\n        "physical_resume_admission"'),
    ('    auth=full_impl.report_authorization(report)\n    if auth:\n        evidence["execution_authorization"]=auth',
     '    auth=full_impl.report_authorization(report)\n    if auth:\n'
     '        if restored and auth["profile"] == full_impl.OPTIMIZED_PROFILE:\n'
     '            for phase, identity in evidence["command_receipts"].items():\n'
     '                receipt=key_values(Path(identity["path"]))\n'
     '                if phase in {"place","physopt","route"}:\n'
     '                    command={"place":"place_design","physopt":"phys_opt_design","route":"route_design"}[phase]\n'
     '                    require(receipt.get("phase")==phase and receipt.get("native_tcl_code")=="0" and\n'
     '                            receipt.get("command")==fresh_opt.expected_physical_command(phase,command,auth),\n'
     '                            "E005 restored command directive/phase mismatch")\n'
     '        evidence["execution_authorization"]=auth'),
])

diff += change('run_m002_physical_stage.py', [
    ('def main() -> int:\n',
     "def critical_probe_report(stage, recovery, inherited, parent_path):\n"
     "    if recovery and stage == 'place':\n"
     "        if inherited.get('phase') == 'post_place_pre_physopt':\n"
     "            return Path(inherited['source_report'])/'cdc_place.rpt'\n"
     "        if inherited.get('phase') == 'post_debug_pre_place':\n"
     "            return Path(inherited['inherited_reports']['cdc_debug_materialized.rpt']['path'])\n"
     "        if inherited.get('opt_evidence_complete') or (inherited.get('opt_execution_proof_kind') == 'native_project_log_derived' and inherited.get('opt_reports_complete')):\n"
     "            return Path(inherited['inherited_reports']['cdc_opt.rpt']['path'])\n"
     "    return parent_path.parent/'cdc_physopt.rpt' if stage == 'route' else None\n\n\n"
     'def main() -> int:\n'),
    ("            if opt_recovery and not inherited.get('opt_evidence_complete'):\n"
     "                shutil.copy2(inherited_report/'opt_command_result.txt',report/'opt_command_result.txt')",
     "            if inherited.get('opt_execution_proof_kind') == 'native_project_log_derived':\n"
     "                os.environ['HAP_RECOVERY_OPT_LOG_DERIVED'] = '1'\n"
     "                shutil.copy2(Path(inherited['inherited_opt_execution_proof']['path']), report/'inherited_opt_execution_proof.json')\n"
     "            elif opt_recovery and not inherited.get('opt_evidence_complete'):\n"
     "                shutil.copy2(inherited_report/'opt_command_result.txt',report/'opt_command_result.txt')"),
    ('                   scripts / "m002_synthesis_recovery.py",',
     '                   scripts / "m002_synthesis_recovery.py", scripts / "m002_fresh_project_opt_recovery.py",'),
    ("            'post_termination','resource_samples','frozen_child_log','completed_report_integrity') if inherited.get(k)]",
     "            'post_termination','resource_samples','frozen_child_log','completed_report_integrity','inherited_opt_execution_proof') if inherited.get(k)]\n"
     "        if inherited.get('inherited_opt_execution_proof'):\n"
     "            import m002_fresh_project_opt_recovery as fresh_opt\n"
     "            import m002_physical_evidence as evidence\n"
     "            identities += fresh_opt.proof_source_paths(evidence, inherited['inherited_opt_execution_proof'])\n"
     "            identities.append(report/'inherited_opt_execution_proof.json')"),
    ("    critical_source = (Path(inherited['source_report'])/'cdc_place.rpt'\n"
     "        if recovery and stage=='place' and inherited.get('phase')=='post_place_pre_physopt' else Path(inherited['inherited_reports']['cdc_debug_materialized.rpt']['path'])\n"
     "        if recovery and stage=='place' and inherited.get('phase')=='post_debug_pre_place' else\n"
     "        Path(inherited['inherited_reports']['cdc_opt.rpt']['path'])\n"
     "        if recovery and stage == 'place' and inherited.get('opt_evidence_complete') else\n"
     "        parent_path.parent/'cdc_physopt.rpt' if stage=='route' else None)",
     "    critical_source = critical_probe_report(stage, recovery, inherited if recovery and stage == 'place' else {}, parent_path if stage == 'route' else None)"),
])

diff += change('m002_diagnostic_common.tcl', [
    ('    set inherited_opt [expr {[info exists ::env(HAP_RECOVERY_PHASE)] && $::env(HAP_RECOVERY_PHASE) eq "post_opt_pre_debug" && $point eq "opt" && $::env(HAP_RECOVERY_OPT_EVIDENCE_COMPLETE) eq "1"}]',
     '    set log_derived_opt [expr {[info exists ::env(HAP_RECOVERY_OPT_LOG_DERIVED)] && $::env(HAP_RECOVERY_OPT_LOG_DERIVED) eq "1"}]\n'
     '    set inherited_opt [expr {[info exists ::env(HAP_RECOVERY_PHASE)] && $::env(HAP_RECOVERY_PHASE) eq "post_opt_pre_debug" && $point eq "opt" && ($::env(HAP_RECOVERY_OPT_EVIDENCE_COMPLETE) eq "1" || $log_derived_opt)}]'),
    ('        foreach name {opt.dcp opt_command_result.txt timing_opt.rpt utilization_opt.rpt drc_opt.rpt check_timing_opt.rpt clocks_opt.rpt cdc_opt.rpt clock_interaction_opt.rpt exceptions_opt.rpt pulse_width_opt.rpt bus_skew_opt.rpt reset_cdc_and_io_probe_opt.tsv xpm_invalid_endpoint_probe_opt.tsv head_wave_local_opt.tsv} {\n'
     '            file copy [file join $::env(HAP_RECOVERY_PARENT_REPORT) $name] [file join $::m002_report_dir $name]\n'
     '        }',
     '        foreach name {opt.dcp opt_command_result.txt timing_opt.rpt utilization_opt.rpt drc_opt.rpt check_timing_opt.rpt clocks_opt.rpt cdc_opt.rpt clock_interaction_opt.rpt exceptions_opt.rpt pulse_width_opt.rpt bus_skew_opt.rpt reset_cdc_and_io_probe_opt.tsv xpm_invalid_endpoint_probe_opt.tsv head_wave_local_opt.tsv} {\n'
     '            if {$log_derived_opt && $name eq "opt_command_result.txt"} {continue}\n'
     '            file copy [file join $::env(HAP_RECOVERY_PARENT_REPORT) $name] [file join $::m002_report_dir $name]\n'
     '        }'),
])

for name in ['run_m002_optimized.py','m002_resume_physical.tcl']:
    original=(SOURCE/name).read_text();draft=(DEST/name).read_text()
    diff+=''.join(difflib.unified_diff(original.splitlines(True),draft.splitlines(True),
                                     fromfile=str(SOURCE/name),tofile=str(DEST/name)))
for name in ['m002_fresh_project_opt_recovery.py','test_m002_fresh_project_opt_recovery.py']:
    diff+=''.join(difflib.unified_diff([], (DEST/name).read_text().splitlines(True),
                                     fromfile='/dev/null',tofile=str(DEST/name)))
(DEST/'integration_DRAFT.diff').write_text(diff)
