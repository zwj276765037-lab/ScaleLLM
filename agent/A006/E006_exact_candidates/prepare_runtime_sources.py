#!/usr/bin/env python3
"""CPU-only R004 controller/guard preparation from the unexecuted repair entry."""
import ast
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPAIR = HERE.parent / 'E006_connection_recovery'
TARGETS = ROOT / 'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R004/independent_candidate_targets.json'
CONTRACT = ROOT / 'mission/M002_ddr_separation_and_timing_recovery/exact_hotspot_candidate_comparison_contract_2026-10-17.md'


def identity(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(data)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest.hexdigest())


def replace(text, old, new):
    assert text.count(old) == 1, old[:100]
    return text.replace(old, new, 1)


def save(path, value):
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')


def main():
    assert not (HERE / 'run_attribution_lean.py').exists(), 'Do not overwrite prepared runtime sources'
    targets = json.loads(TARGETS.read_text())
    require_targets = targets['candidates']
    assert [row['id'] for row in require_targets] == ['C01', 'C02']
    assert all(re.fullmatch(r'C[0-9]+', row['id']) and row['primitive_literal_prefix'] == row['root'] + '/' for row in require_targets)
    target_text = (REPAIR / 'targets.tcl').read_text()
    target_text += 'set exact_candidate_targets [list ' + ' '.join('[list {' + row['id'] + '} {' + row['root'] + '}]' for row in require_targets) + ']\n'
    (HERE / 'targets.tcl').write_text(target_text)
    manifest = json.loads((REPAIR / 'targets_manifest.json').read_text())
    manifest['targets_tcl'] = identity(HERE / 'targets.tcl')
    manifest['external_inputs']['candidate_targets'] = identity(TARGETS)
    manifest['external_inputs']['R004_scope_contract'] = identity(CONTRACT)
    save(HERE / 'targets_manifest.json', manifest)
    # Reuse closed full-design/failure/hotspot/resource evidence, never rereport it.
    reuse = json.loads((REPAIR / 'reuse_manifest.json').read_text())
    for row in targets['prior_closed_evidence'] + targets['frozen_RTL_evidence']:
        source = ROOT / row['path']
        actual = identity(source)
        assert actual['bytes'] == row['bytes'] and actual['sha256'] == row['sha256']
        reuse['artifacts']['R004_authority_' + source.name] = actual
    save(HERE / 'reuse_manifest.json', reuse)
    text = (REPAIR / 'attribution_lean.tcl').read_text()
    marker = 'set start [clock seconds];set before [llength $failures]\nquery hotspot_union_connections'
    source = '''source [file join [file dirname [info script]] candidate_inspector.tcl]
set ::m002_report_dir $out
set ::slr2::siteSLR $siteSLR
set memberStatus [dict create]
foreach spec $exact_candidate_targets {
    lassign $spec point root
    set start [clock seconds];set before [llength $failures]
    set code [query candidate_${point}_membership {slr2::readonly_resolve $point $root}]
    dict set memberStatus $point $code
    query candidate_${point}_exact_native_resources {
        set object [exact_cell $root]
        if {[get_property IS_PRIMITIVE $object]} {error "Exact candidate root is primitive: $root"}
        report_utilization -cells $object -slr -file [file join $out utilization_candidate_${point}_SLR.rpt]
    }
    stage_done candidate_${point}_membership_resources $start $before
}
query candidate_disjointness {
    set prior [dict create];set priorP [dict create];set overlaps [list]
    foreach spec $exact_candidate_targets {
        lassign $spec point root
        if {[dict get $memberStatus $point]} {error "Candidate membership did not close: $point"}
        set sets [dict get $::slr2::candidateSets $point]
        foreach name [dict keys [dict get $sets RAW]] {
            if {[dict exists $prior $name]} {lappend overlaps [list RAW $name [dict get $prior $name] $point]}
            dict set prior $name $point
        }
        foreach name [dict keys [dict get $sets P]] {
            if {[dict exists $priorP $name]} {lappend overlaps [list P $name [dict get $priorP $name] $point]}
            dict set priorP $name $point
        }
    }
    m002_put [file join $out candidate_disjointness.tcllist] [list actual_overlaps $overlaps separate_scopes true combined_migration_candidate false]
    if {[llength $overlaps]} {error "Exact candidate RAW/P scopes overlap"}
}
foreach spec $exact_candidate_targets {
    lassign $spec point root
    set start [clock seconds];set before [llength $failures]
    set cutCode [query candidate_${point}_complete_cut {
        if {[dict get $memberStatus $point]} {error "Full cut not executed: exact candidate membership failed"}
        set sets [dict get $::slr2::candidateSets $point]
        foreach setname {RAW S P} {set ::slr2::$setname [dict get $sets $setname]}
        slr2::cut $point
    }]
    stage_done candidate_${point}_complete_cut $start $before
    set start [clock seconds];set before [llength $failures]
    query candidate_${point}_bounded_boundary_timing {
        if {$cutCode} {error "Bounded timing not executed: full cut did not close"}
        slr2::scoped_timing $point
    }
    stage_done candidate_${point}_bounded_timing $start $before
}
'''
    text = replace(text, marker, source + marker)
    text = replace(text, 'proc net_record {net summary endpoints edges track_edges} {\n    global hotspotUnion cellData', 'proc net_record {net summary endpoints edges track_edges} {\n    global hotspotUnion cellData segmentExport')
    text = replace(text, '    set canonical [lindex $segments 0]\n    set dp', '    set canonical [lindex $segments 0]\n    foreach segment $segments {puts $segmentExport "$canonical\\t$segment"}\n    set dp')
    text = replace(text, 'query hotspot_union_connections {\n    set pins', 'query hotspot_union_connections {\n    set segmentExport [open [file join $out hotspot_union_canonical_segments.tsv] {WRONLY CREAT EXCL}]\n    puts $segmentExport "canonical_net\\tsegment"\n    set pins')
    text = replace(text, '    };close $summary;close $endpoints\n    set h', '    };close $summary;close $endpoints;close $segmentExport\n    set h')
    text = replace(text, '    foreach property {NAME REF_NAME LOC BEL IS_PRIMITIVE} {\n        set vector', '    set vectors [open [file join $out failed_batch_actual_property_vectors.tsv] {WRONLY CREAT EXCL}]\n    puts $vectors "property\\texpected_objects\\tnative_vector_list_length\\tactual_native_vector_Tcl_list"\n    foreach property {NAME REF_NAME LOC BEL IS_PRIMITIVE} {\n        set vector')
    text = replace(text, '        set vector [get_property -quiet $property $objects]\n        foreach object $objects {', '        set vector [get_property -quiet $property $objects]\n        puts $vectors "$property\\t[llength $objects]\\t[llength $vector]\\t[list $vector]";flush $vectors\n        foreach object $objects {')
    text = replace(text, '    close $h\n}\nif {[query reused_hotspot_union_membership', '    close $h;close $vectors\n}\nif {[query reused_hotspot_union_membership')
    text = text.replace('E006_CONNECTION_RECOVERY_READONLY_COMPLETED', 'E006_EXACT_CANDIDATE_COMPARISON_READONLY_COMPLETED')
    (HERE / 'attribution_lean.tcl').write_text(text)
    runner = (REPAIR / 'run_attribution_lean.py').read_text()
    runner = runner.replace("'repair_failed_lean_connections'", "'readonly_two_exact_candidate_comparison'")
    runner = runner.replace("'engineering_routine_readonly_repair'", "'engineering_targeted_readonly_attribution'")
    runner = replace(runner, "    batch=ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R003/attempts'",
                     "    batch=ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R004/attempts'")
    runner = runner.replace("startswith('m002_E006_R003_')", "startswith('m002_E006_R004_')")
    anchor = "    base_authorization=json.loads(Path(base_row['path']).read_text())"
    admission = '''
    require(base_authorization['decision_evidence']==approval_evidence,'Historical original decision differs')
    for field in ['contract','candidate_targets']:
        row=authorization[field];require(identity(row['path'])==row,'R004 scope/targets identity changed')
    require(authorization['contract']['path']==str(ROOT/'mission/M002_ddr_separation_and_timing_recovery/exact_hotspot_candidate_comparison_contract_2026-10-17.md'),'Wrong R004 contract')
    require(authorization['candidate_targets']['path']==str(ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R004/independent_candidate_targets.json'),'Wrong exact candidate authority')
'''
    runner = replace(runner, anchor, anchor + admission)
    anchor = "    require(lean_facts['status']==authorization['prior_lean_terminal_status'],'Prior terminal facts/status differ')"
    admission = '''
    lean_started=json.loads((Path(authorization['prior_lean_terminal_status']['path']).parent/'started.json').read_text())
    require_registered_closed(prior_registered_identities(lean_status,lean_started))
'''
    runner = replace(runner, anchor, anchor + admission)
    anchor = "    external_inputs=target_manifest['external_inputs']"
    admission = '''
    require(external_inputs['candidate_targets']==authorization['candidate_targets'] and external_inputs['R004_scope_contract']==authorization['contract'],'Compiled exact scope differs from execution binding')
'''
    runner = replace(runner, anchor, anchor + admission)
    runner = replace(runner, "names=['attribution_lean.tcl','property_alignment.tcl','targets.tcl','targets_manifest.json','reuse_manifest.json',Path(__file__).name]",
                     "names=['attribution_lean.tcl','property_alignment.tcl','candidate_inspector.tcl','candidate_evidence.py','targets.tcl','targets_manifest.json','reuse_manifest.json',Path(__file__).name]")
    runner = replace(runner, "E006_TARGETS=str(archive/'targets.tcl'),", "E006_TARGETS=str(archive/'targets.tcl'),E006_CANDIDATE_ADAPTER=str(archive/'candidate_evidence.py'),")
    runner = runner.replace("stage='readonly_slr1_connections_recovery'", "stage='readonly_exact_candidate_comparison'")
    runner = replace(runner, "    external_inputs=target_manifest['external_inputs']", "    external_inputs=dict(target_manifest['external_inputs'])\n    for field,row in authorization.items():\n        if isinstance(row,dict) and {'path','bytes','sha256'}.issubset(row):\n            require(identity(row['path'])==row,f'Execution evidence changed: {field}')\n            external_inputs['execution_binding_'+field]=row")
    (HERE / 'run_attribution_lean.py').write_text(runner)
    launcher = (REPAIR / 'launch_detached.py').read_text()
    launcher = launcher.replace('R003_AT002_connection_recovery', 'R004_AT001_exact_candidate_comparison')
    launcher = launcher.replace('R003/attempts/AT002_connection_recovery', 'R004/attempts/AT001_exact_candidate_comparison')
    launcher = launcher.replace("'repair_failed_lean_connections'", "'readonly_two_exact_candidate_comparison'")
    (HERE / 'launch_detached.py').write_text(launcher)
    for path in [HERE / 'run_attribution_lean.py', HERE / 'launch_detached.py', HERE / 'candidate_evidence.py']:
        ast.parse(path.read_text())
    marker = '    proc=None;tracked={};stop=None;peak=0;low_since=None'
    assert runner.split(marker, 1)[1] == (REPAIR / 'run_attribution_lean.py').read_text().split(marker, 1)[1]
    sources = [HERE / name for name in ['attribution_lean.tcl', 'property_alignment.tcl', 'candidate_inspector.tcl', 'candidate_evidence.py', 'run_attribution_lean.py', 'launch_detached.py', 'targets.tcl', 'targets_manifest.json', 'reuse_manifest.json', 'prepare_runtime_sources.py', 'prepare_candidate_inspector.py']]
    save(HERE / 'prepared_source_manifest.json', dict(status='CPU_PREPARED_NOT_EXECUTED', EDA_executed=False,
        source_files=[identity(path) for path in sources], scope_contract=identity(CONTRACT), candidate_targets=identity(TARGETS),
        reuse_count=len(reuse['artifacts']), upstream_repair_source_manifest=identity(REPAIR / 'prepared_source_manifest.json'),
        supervision_and_post_integrity_tail_identical=True,
        scope='Original UNION legacy IN/OUT repair plus independent exact C01/C02 RAW-S-P/native-resource/full-leaf-INOUT-top/cap16 timing scopes. No physical policy change.'))
    print(json.dumps(dict(manifest=identity(HERE / 'prepared_source_manifest.json'), EDA_executed=False)))


if __name__ == '__main__':
    main()
