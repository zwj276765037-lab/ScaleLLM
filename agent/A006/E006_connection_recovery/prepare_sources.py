#!/usr/bin/env python3
"""CPU-only prepare R003/AT002: reuse closed stages and repair connections."""
import ast
import csv
import hashlib
import json
from pathlib import Path
import shutil
import tkinter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LEAN = HERE.parent / 'E006_lean_candidate'
AT = ROOT / 'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R003/attempts/AT001_lean_physopt_attribution'
REPORT = ROOT / 'project/hardware/vivado/reports/m002_E006_R003_AT001_lean_physopt_attribution'


def identity(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest.hexdigest())


def replace(text, old, new):
    assert text.count(old) == 1, old[:100]
    return text.replace(old, new, 1)


def save(path, value):
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')


def main():
    assert not (HERE / 'run_attribution_lean.py').exists(), 'Do not overwrite prepared sources'
    status = json.loads((AT / 'status.json').read_text())
    assert status['native_exit_code'] == 1 and status['native_natural_terminal_observed']
    assert status['stop_reason'] is None and not status['owned_survivors']
    native = (AT / 'sources/attribution_lean.tcl').read_text()
    marker = 'set start [clock seconds];set before [llength $failures]\nquery failure_node_device_mapping'
    prefix = native[:native.index(marker)]
    prefix = replace(prefix, 'source $::env(E006_TARGETS)',
                     'source $::env(E006_TARGETS)\nsource [file join [file dirname [info script]] property_alignment.tcl]')
    prefix = replace(prefix, 'proc ensure_cell_data {objects} {\n    global cellData',
                     'proc ensure_cell_data {objects} {\n    global cellData out')
    for variable, prop, optional in [('names', 'NAME', 0), ('refs', 'REF_NAME', 0),
                                     ('locs', 'LOC', 1), ('bels', 'BEL', 1),
                                     ('primitive', 'IS_PRIMITIVE', 0)]:
        prefix = replace(prefix, f'set {variable} [get_property {prop} $missing]',
                         f'set {variable} [propertyalign::values $missing {prop} {optional} E006_cell_cache [file join $out property_alignment_fallback.tsv]]')
    t = tkinter.Tcl()
    parts = t.splitlist((REPORT / 'error_hotspot_union_connections.txt').read_text())
    error = dict(zip(parts[::2], parts[1::2]))
    parts = t.splitlist(error['options'])
    options = dict(zip(parts[::2], parts[1::2]))
    stack = t.splitlist(options['-errorstack'])
    calls = [t.splitlist(stack[i + 1]) for i, value in enumerate(stack[:-1]) if value == 'CALL']
    names = list(t.splitlist(next(row for row in calls if row[0] == 'ensure_cell_data')[1]))
    assert len(names) == 9 and any(name.endswith('/VCC') for name in names)
    targets = (AT / 'sources/targets.tcl').read_text()
    targets += '\nset failed_alignment_objects [list ' + ' '.join('{' + name + '}' for name in names) + ']\n'
    targets += 'set reused_union_file {' + str(REPORT / 'hotspot_UNION_cells.tsv') + '}\n'
    (HERE / 'targets.tcl').write_text(targets)
    target_manifest = json.loads((AT / 'sources/targets_manifest.json').read_text())
    target_manifest['targets_tcl'] = identity(HERE / 'targets.tcl')
    target_manifest['external_inputs']['failed_alignment_error'] = identity(REPORT / 'error_hotspot_union_connections.txt')
    target_manifest['recovery_failed_alignment_exact_objects'] = names
    save(HERE / 'targets_manifest.json', target_manifest)
    probe = '''query actual_failed_batch_property_diagnostics {
    set objects [list]
    foreach name $failed_alignment_objects {
        set object [get_cells -quiet -hier -filter [format {NAME == "%s"} $name]]
        if {[llength $object] != 1 || [get_property NAME $object] ne $name} {error "Failed-batch diagnostic object missing/nonunique: $name"}
        lappend objects [lindex $object 0]
    }
    set h [open [file join $out failed_batch_actual_property_columns.tsv] {WRONLY CREAT EXCL}]
    puts $h "property\\texpected_objects\\tnative_vector_list_length\\tobject\\tscalar_value\\tscalar_is_empty"
    foreach property {NAME REF_NAME LOC BEL IS_PRIMITIVE} {
        set vector [get_property -quiet $property $objects]
        foreach object $objects {
            set value [get_property -quiet $property $object]
            puts $h "$property\\t[llength $objects]\\t[llength $vector]\\t[list $object]\\t[list $value]\\t[expr {$value eq {}}]"
        }
    }
    close $h
}
if {[query reused_hotspot_union_membership {
    set h [open $reused_union_file r];gets $h header
    if {$header ne "cell\\texclusive_owner\\tdetail_hierarchy\\tREF_NAME\\tLOC\\tBEL\\tSLR"} {error "Reused UNION export header changed"}
    set names [list]
    while {[gets $h line] >= 0} {lappend names [lindex [split $line \\t] 0]}
    close $h
    if {[lsort -unique $names] ne [lsort -unique $preparedHotspotCells]} {error "Current selected-site UNION differs from closed AT001 exact cell names"}
    set h [open [file join $out reused_hotspot_union_actual_membership.txt] {WRONLY CREAT EXCL}]
    puts $h "current_selected_site_primitive_cells=[llength $preparedHotspotCells]\\nreused_union_primitive_cells=[llength $names]\\nexact_sorted_NAME_sets_equal=true"
    close $h
}]} {close $receipt;close $stages;exit 1}
'''
    begin = native.index('set start [clock seconds];set before [llength $failures]\nquery hotspot_union_connections')
    end = native.index('set start [clock seconds];set before [llength $failures]\nset hierarchy_scope', begin)
    tail = '''close $receipt;close $stages
set h [open [file join $out result.txt] {WRONLY CREAT EXCL}]
puts $h "failed_queries=$failures\\nphysical_commands_executed=false\\ncheckpoint_write_executed=false\\nsource_graph=E005_closed_physopt_not_failed_route\\nfixed_congestion=UNAVAILABLE\\nformal_signoff=false\\nreused_closed_stages=failure_samples,hotspot_ownership,exact_hierarchy_resources"
close $h
close_design
if {[llength $failures]} {exit 1}
puts "E006_CONNECTION_RECOVERY_READONLY_COMPLETED"
exit 0
'''
    (HERE / 'attribution_lean.tcl').write_text(prefix + probe + native[begin:end] + tail)
    reuse = json.loads((AT / 'sources/reuse_manifest.json').read_text())
    reusable = [path for pattern in ['failure*.tsv', 'hotspot_*_cells.tsv', 'utilization_total_*_SLR.rpt']
                for path in sorted(REPORT.glob(pattern))]
    reusable += [REPORT / name for name in ['actual_hotspot_site_tile_SLR.tsv', 'hotspot_scope.tsv', 'hotspot_native_resource_limits.txt', 'identity.tsv']]
    reusable += [AT / name for name in ['status.json', 'started.json', 'terminal_facts.json',
                                       'failure_samples_closed_stage_facts.json', 'hotspot_ownership_closed_stage_facts.json',
                                       'exact_hierarchy_resources_closed_stage_facts.json']]
    for path in reusable:
        reuse['artifacts']['R003_AT001_' + path.name] = identity(path)
    queries = list(csv.DictReader((REPORT / 'query_receipts.tsv').open(), delimiter='\t'))
    reuse['closed_lean_attempt'] = dict(attempt=str(AT), report=str(REPORT),
        status=identity(AT / 'status.json'), terminal_facts=identity(AT / 'terminal_facts.json'),
        required_query_receipts=[row for row in queries if row['native_tcl_code'] == '0'])
    save(HERE / 'reuse_manifest.json', reuse)
    runner = (LEAN / 'run_attribution_lean.py').read_text()
    runner = replace(runner, "'allow_readonly_lean_replacement','Wrong replacement decision'", "'repair_failed_lean_connections','Wrong repair decision'")
    anchor = "    batch=ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R003/attempts'"
    admission = '''    require(authorization.get('approval_kind')=='engineering_routine_readonly_repair','Not an engineering repair binding')
    base_row=authorization['original_replacement_authorization']
    require(identity(base_row['path'])==base_row,'Original replacement authorization changed')
    base_authorization=json.loads(Path(base_row['path']).read_text())
    for field in ['prior_lean_terminal_status','prior_lean_terminal_facts']:
        row=authorization[field];require(identity(row['path'])==row,'Prior lean closure evidence changed')
    lean_status=json.loads(Path(authorization['prior_lean_terminal_status']['path']).read_text())
    lean_facts=json.loads(Path(authorization['prior_lean_terminal_facts']['path']).read_text())
    require(lean_status['native_exit_code']==1 and lean_status['exit_code']==1 and lean_status['stop_reason'] is None and lean_status['native_natural_terminal_observed'],'Prior lean not naturally failed')
    require(lean_facts['status']==authorization['prior_lean_terminal_status'],'Prior terminal facts/status differ')
    require(all(value for key,value in lean_facts['checks'].items() if key not in {'native_zero','supervisor_zero','all_stage_codes_zero','all_query_codes_zero'}),'Prior lean closure/integrity not verified')
'''
    runner = replace(runner, anchor, admission + anchor)
    runner = replace(runner, "authorization['prior_terminal_status'] == identity(original/'status.json')", "base_authorization['prior_terminal_status'] == identity(original/'status.json')")
    runner = replace(runner, "authorization.get('approval_kind') == 'user_explicit_controlled_stop'", "base_authorization.get('approval_kind') == 'user_explicit_controlled_stop'")
    anchor = "    reused_inputs=reuse['artifacts']"
    admission = '''    lean_reuse=reuse['closed_lean_attempt']
    require(lean_reuse['status']==authorization['prior_lean_terminal_status'] and lean_reuse['terminal_facts']==authorization['prior_lean_terminal_facts'],'Repair reuse is not the bound failed lean attempt')
    import csv
    with (Path(lean_reuse['report'])/'query_receipts.tsv').open() as stream:
        lean_queries={row['query']:row for row in csv.DictReader(stream,delimiter='\\t')}
    require(all(lean_queries.get(row['query'])==row and row['native_tcl_code']=='0' for row in lean_reuse['required_query_receipts']),'Reused lean closed query changed')
'''
    runner = replace(runner, anchor, admission + anchor)
    runner = replace(runner, "names=['attribution_lean.tcl','targets.tcl','targets_manifest.json','reuse_manifest.json',Path(__file__).name]",
                     "names=['attribution_lean.tcl','property_alignment.tcl','targets.tcl','targets_manifest.json','reuse_manifest.json',Path(__file__).name]")
    runner = runner.replace("stage='readonly_slr1_attribution_lean'", "stage='readonly_slr1_connections_recovery'")
    (HERE / 'run_attribution_lean.py').write_text(runner)
    launcher = (LEAN / 'launch_detached.py').read_text()
    launcher = launcher.replace('AT001_lean_physopt_attribution', 'AT002_connection_recovery')
    launcher = launcher.replace("'allow_readonly_lean_replacement'", "'repair_failed_lean_connections'")
    (HERE / 'launch_detached.py').write_text(launcher)
    ast.parse(runner)
    ast.parse(launcher)
    manifest = dict(status='CPU_PREPARED_NOT_EXECUTED', EDA_executed=False,
        source_files=[identity(HERE / name) for name in ['attribution_lean.tcl', 'property_alignment.tcl', 'run_attribution_lean.py', 'launch_detached.py', 'targets.tcl', 'targets_manifest.json', 'reuse_manifest.json', 'prepare_sources.py']],
        upstream_runtime_archive=identity(AT / 'sources/attribution_lean.tcl'),
        prior_lean_runner=identity(LEAN / 'run_attribution_lean.py'),
        failed_native_error=identity(REPORT / 'error_hotspot_union_connections.txt'),
        actual_errorstack_object_names=names,
        scope='Only failed hotspot UNION connections and exact native property diagnostics; completed failure/ownership/exact hierarchy stages are reused; no normal wall/no-output stop')
    save(HERE / 'prepared_source_manifest.json', manifest)
    print(json.dumps(dict(manifest=identity(HERE / 'prepared_source_manifest.json'), reused_artifacts=len(reuse['artifacts']), EDA_executed=False)))


if __name__ == '__main__':
    main()
