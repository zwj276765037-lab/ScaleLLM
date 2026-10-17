#!/usr/bin/env python3
"""Prepare, never execute, an independent read-only lean E006 alternative."""
import ast
import json
from pathlib import Path
import shutil
import sys
import tkinter

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
OLD = ROOT / 'agent/A006/E006_slr1_attribution'
sys.path.insert(0, str(OLD))
from capture_stage import identity

source = (OLD / 'attribution.tcl').read_text()
prefix = source[:source.index('set start [clock seconds];set before [llength $failures]')]
opening = source[source.index('set start [clock seconds];set before [llength $failures]'):source.index('query complete_exclusive_ownership')]
identity_start = opening.index('query identity {')
topology_start = opening.index('query topology {')
opening = (opening[:identity_start] + 'if {[' + opening[identity_start:topology_start].rstrip()
    + ']} {close $receipt;close $stages;exit 1}\nif {[' + opening[topology_start:].rstrip()
    + ']} {close $receipt;close $stages;exit 1}\n')
old_pins = source[source.index('proc pin_cell_data'):source.index('proc pin_class')]
new_pins = r'''set cellData [dict create]
proc ensure_cell_data {objects} {
    global cellData
    set missing [list]
    foreach object $objects {if {![dict exists $cellData $object]} {lappend missing $object}}
    if {![llength $missing]} {return}
    set names [get_property NAME $missing]
    set refs [get_property REF_NAME $missing]
    set locs [get_property LOC $missing]
    set bels [get_property BEL $missing]
    set primitive [get_property IS_PRIMITIVE $missing]
    set count [llength $missing]
    foreach values [list $names $refs $locs $bels $primitive] {if {[llength $values] != $count} {error "Selected cell property alignment differs"}}
    foreach cell $names ref $refs loc $locs bel $bels leaf $primitive {
        if {!$leaf} {error "Nonprimitive selected from leaf endpoints/sites: $cell"}
        set owner [owner_of $cell]
        dict set cellData $cell [list $owner [detail_of $cell $owner] $ref $loc $bel [slr_for $loc]]
    }
}
proc pin_cell_data {pin} {
    global cellData
    set cell [string range $pin 0 [expr {[string last / $pin]-1}]]
    if {[dict exists $cellData $cell]} {return [linsert [dict get $cellData $cell] 0 $cell]}
    set cells [get_cells -quiet -of_objects $pin]
    if {[llength $cells] == 1} {
        ensure_cell_data $cells
        set cell [get_property NAME $cells]
        if {[dict exists $cellData $cell]} {return [linsert [dict get $cellData $cell] 0 $cell]}
    }
    return [list UNRESOLVED_PARENT_FROM_PIN:$cell UNKNOWN UNKNOWN UNKNOWN UNKNOWN UNKNOWN UNKNOWN]
}
'''
net_procs = source[source.index('proc pin_class'):source.index('set start [clock seconds];set before [llength $failures]\nquery failure_node_device_mapping')]
needle = '    set resolution [expr {[llength $dp] == 1 ?'
net_procs = net_procs.replace(needle, '    set endpoints_for_cache [concat $dp $lp]\n    if {[llength $endpoints_for_cache]} {ensure_cell_data [get_cells -quiet -of_objects $endpoints_for_cache]}\n' + needle)
prepare = r'''if {[query prepare_regions_and_union_membership {
    set regionTileSets [dict create];set preparedUnionTiles [dict create]
    foreach region $regions {
        lassign $region name tiles_file
        set h [open $tiles_file r];set requested [split [string trim [read $h]] \n];close $h
        set tiles [get_tiles -quiet $requested]
        if {[lsort -unique [get_property NAME $tiles]] ne [lsort -unique $requested]} {error "Actual region tile names differ: $name"}
        foreach tile $requested {dict set regionTileSets $name $tile 1;dict set preparedUnionTiles $tile 1}
    }
    set preparedHotspotSites [get_sites -quiet -of_objects [get_tiles -quiet [dict keys $preparedUnionTiles]]]
    set preparedHotspotCells [get_cells -quiet -of_objects $preparedHotspotSites -filter {IS_PRIMITIVE == 1}]
    set hotspotUnion [dict create]
    foreach cell $preparedHotspotCells {dict set hotspotUnion $cell 1}
}]} {close $receipt;close $stages;exit 1}
'''
prepare = prepare.replace('\\\\n', '\\n')
failure = source[source.index('set start [clock seconds];set before [llength $failures]\nquery failure_node_device_mapping'):source.index('set start [clock seconds];set before [llength $failures]\nquery hotspot_union_connections')]
failure = failure.replace('        set count [llength $matches];set status',
    '        set count [llength $matches]\n        if {$count == 1 && [get_property NAME $matches] ne $name} {error "Exact failure net name differs from requested literal: $name"}\n        set status')
failure = failure.replace('        set status [expr {$code ? {UNAVAILABLE_NATIVE_SLR_QUERY} : {ACTUAL_NATIVE_DEVICE_QUERY}}]',
    '''        if {$code} {set status UNAVAILABLE_NATIVE_SLR_QUERY} elseif {[llength $slrs] == 0} {
            set status UNAVAILABLE_EMPTY_NATIVE_SLR_QUERY
        } elseif {[llength $slrs] != 1 || [lsearch -exact [get_slrs] [lindex $slrs 0]] < 0} {
            set status AMBIGUOUS_NATIVE_SLR_QUERY
        } else {set status ACTUAL_NATIVE_DEVICE_QUERY}''')
hotspot = source[source.index('set start [clock seconds];set before [llength $failures]\nset hotspotUnion'):source.index('proc pin_cell_data')]
hotspot = '\n'.join(line for line in hotspot.splitlines() if 'report_utilization -cells' not in line) + '\n'
hotspot = hotspot.replace('        dict set regionCells $name $cells', '        ensure_cell_data $cells\n        dict set regionCells $name $cells')
site_mapping = r'''query actual_tile_site_mapping {
    set h [open [file join $out actual_hotspot_site_tile_SLR.tsv] {WRONLY CREAT EXCL}]
    puts $h "site\tSITE_TYPE\tactual_device_SLR\texact_tile\tactual_GRID_POINT_X\tactual_GRID_POINT_Y"
    foreach site $preparedHotspotSites {
        set tile [get_tiles -quiet -of_objects $site]
        if {[llength $tile] != 1 || ![dict exists $preparedUnionTiles [get_property NAME $tile]]} {error "Site has no unique tile in the selected union: $site"}
        puts $h "$site\t[site_type_for $site]\t[slr_for $site]\t[get_property NAME $tile]\t[get_property GRID_POINT_X $tile]\t[get_property GRID_POINT_Y $tile]"
    };close $h
}
'''
site_mapping = site_mapping.replace('\\\\t', '\\t')
hotspot = hotspot.replace('foreach region $regions {', site_mapping + 'foreach region $regions {', 1)
hotspot = hotspot.replace('stage_done hotspot_ownership $start $before', '''query hotspot_primitive_union_coverage {
    if {[lsort -unique [dict keys $hotspotUnion]] ne [lsort -unique $preparedHotspotCells]} {error "Per-region exact union differs from direct selected-site primitive union"}
    set h [open [file join $out hotspot_native_resource_limits.txt] {WRONLY CREAT EXCL}]
    puts $h "native_hotspot_resource_utilization=NOT_QUERIED\nreason=avoid_large_primitive_list_report_utilization\nprimitive_site_BEL_occupation_is_not_native_LUT_resource_or_congestion\nfixed_congestion=UNAVAILABLE";close $h
}
stage_done hotspot_ownership $start $before''')
connections = source[source.index('set start [clock seconds];set before [llength $failures]\nquery hotspot_union_connections'):source.index('close $receipt;close $stages\nset h [open [file join $out result.txt]')]
hierarchies = r'''set start [clock seconds];set before [llength $failures]
set hierarchy_scope [open [file join $out lean_exact_hierarchy_scope.tsv] {WRONLY CREAT EXCL}]
puts $hierarchy_scope "owner_context\texact_hierarchy\treport_name\tscope"
foreach spec $owner_roots {
    lassign $spec owner roots
    if {$owner ni {core_other ddr0 ddr1 pcie debug}} {continue}
    set index 0
    foreach root $roots {
        incr index
        set tag ${owner}_${index}
        query native_exact_hierarchy_$tag {
            set cells [exact_cell $root]
            if {[llength $cells] != 1 || [get_property IS_PRIMITIVE $cells]} {error "Expected exactly one hierarchy object: $root"}
            puts $hierarchy_scope "$owner\t$root\tutilization_total_${tag}_SLR.rpt\tinclusive_exact_hierarchy_not_exclusive_primitive_remainder";flush $hierarchy_scope
            report_utilization -cells $cells -slr -file [file join $out utilization_total_${tag}_SLR.rpt]
        }
    }
}
close $hierarchy_scope
stage_done exact_hierarchy_resources $start $before
'''
hierarchies = hierarchies.replace('\\\\t', '\\t')
ending = source[source.index('close $receipt;close $stages\nset h [open [file join $out result.txt]'):]
ending = ending.replace('E006_ATTRIBUTION_READONLY_COMPLETED', 'E006_LEAN_ATTRIBUTION_READONLY_COMPLETED')
lean = '# Independent PREPARED lean candidate; never hot-edits AT001.\n' + prefix + opening + new_pins + net_procs + prepare + failure + hotspot + connections + hierarchies + ending
assert lean.count('report_utilization -cells') == 1
(OUT / 'attribution_lean.tcl').write_text(lean)
shutil.copy2(OLD / 'targets.tcl', OUT / 'targets.tcl')
targets = json.loads((OLD / 'targets_manifest.json').read_text())
targets['targets_tcl'] = identity(OUT / 'targets.tcl')
targets['lean_preparation_parent_manifest'] = identity(OLD / 'targets_manifest.json')
(OUT / 'targets_manifest.json').write_text(json.dumps(targets, indent=2) + '\n')

old_attempt = ROOT / 'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R001/attempts/AT001_physopt_attribution'
old_report = ROOT / 'project/hardware/vivado/reports/m002_E006_R001_AT001_physopt_attribution'
closed = json.loads((old_attempt / 'closed_owner_batch001_facts.json').read_text())
artifacts = {Path(row['path']).name: row for row in closed['artifacts']}
for name in ['all_primitive_locations.tsv', 'site_owner_sets.tsv', 'exclusive_owner_SLR_REF_counts.tsv', 'ownership_coverage.tsv']:
    artifacts[name] = identity(old_report / name)
for name in ['closed_owner_batch001_facts.json', 'closed_owner_batch001_summary.json', 'closed_owner_batch001_resource_scope_correction.json', 'input_bindings.json']:
    artifacts[name] = identity(old_attempt / name)
bindings = json.loads((old_attempt / 'input_bindings.json').read_text())
for row in bindings['sources']:
    artifacts['original_source_' + Path(row['path']).name] = row
reuse = dict(original_attempt=str(old_attempt), original_report=str(old_report),
    required_closed_query_receipts=closed['closed_query_receipts_snapshot'],
    artifacts=artifacts, original_archived_sources=bindings['sources'],
    checkpoint=bindings['checkpoint'],
    semantics='Complete primitive/site ownership and global+first4 owner native resource tables are reused by exact artifact identity from the same DCP. Active AT001 query/stage receipt files are not frozen or modified.',
    gaps=['No native utilization of exclusive core_other/interconnect primitive remainders.',
          'No new native hotspot LUT/FF resource table; CPU site/BEL/primitive occupancy is separate.',
          'Selected hotspot complete nets are not an entire-design or entire-candidate cut census.'])
(OUT / 'reuse_manifest.json').write_text(json.dumps(reuse, indent=2) + '\n')

runner = (OLD / 'run_attribution.py').read_text()
runner = runner.replace('One supervised E006 attribution session; opens only own closed physopt once.',
    'Prepared lean E006 read-only alternative; never controls or edits original AT001.')
runner = runner.replace('    args=parser.parse_args();attempt=args.attempt.resolve();report=args.report.resolve()', '''    parser.add_argument('--authorization',type=Path,required=True)
    args=parser.parse_args();attempt=args.attempt.resolve();report=args.report.resolve()
    authorization_path=args.authorization.resolve()
    authorization=json.loads(authorization_path.read_text())
    require(authorization.get('execution_authorized') is True,'No actual replacement execution authorization')
    require(authorization.get('decision') == 'allow_readonly_lean_replacement','Wrong replacement decision')
    approval_evidence=authorization['decision_evidence']
    require(identity(approval_evidence['path']) == approval_evidence,'Replacement decision evidence identity changed')''')
start = runner.index("    for p in sorted(batch.glob('AT*/started.json')):")
end = runner.index("    checkpoint=identity(PARENT/'physopt.dcp')", start)
runner = runner[:start] + '''    source_dir=Path(__file__).resolve().parent
    reuse=json.loads((source_dir/'reuse_manifest.json').read_text())
    original=Path(reuse['original_attempt'])
    original_status=json.loads((original/'status.json').read_text())
    require(authorization['prior_terminal_status'] == identity(original/'status.json'),'Original terminal is not the authorized closed status')
    require(original_status['execution_state']=='completed' and not original_status['owned_survivors'],'Original attempt not closed')
    original_ids=prior_registered_identities(original_status,json.loads((original/'started.json').read_text()))
    require_registered_closed(original_ids)
    if original_status['stop_reason'] is not None:
        require(authorization.get('approval_kind') == 'user_explicit_controlled_stop','Original non-natural stop lacks explicit user decision')
    else:
        require(original_status['native_natural_terminal_observed'],'Original terminal not naturally observed')
    for p in sorted(batch.glob('AT*/started.json')):
        ended=p.parent/'status.json';require(ended.exists(),'prior E006 attempt unclosed')
        status=json.loads(ended.read_text())
        require(status['execution_state']=='completed' and not status['owned_survivors'],'prior E006 owner not closed')
        require(status['stop_reason'] is None or p.parent==original,'Unrelated prior E006 stop is not authorized')
        require_registered_closed(prior_registered_identities(status,json.loads(p.read_text())))
    reused_inputs=reuse['artifacts']
    require(all(identity(row['path'])==row for row in reused_inputs.values()),'Reused closed input changed')
    import csv
    with (Path(reuse['original_report'])/'query_receipts.tsv').open() as stream:
        observed={row['query']:row for row in csv.DictReader(stream,delimiter='\\t')}
    require(all(observed.get(row['query'])==row and row['native_tcl_code']=='0' for row in reuse['required_closed_query_receipts']),'Reused query did not close unchanged')
''' + runner[end:]
runner = runner.replace("names=['attribution.tcl','targets.tcl','targets_manifest.json',Path(__file__).name]",
    "names=['attribution_lean.tcl','targets.tcl','targets_manifest.json','reuse_manifest.json',Path(__file__).name]")
runner = runner.replace("prior_registered_identities=prior_ids,external_inputs=external_inputs,",
    "prior_registered_identities=prior_ids,external_inputs=external_inputs,reused_closed_inputs=reused_inputs,replacement_authorization=identity(authorization_path),original_attempt_terminal=identity(original/'status.json'),original_started=identity(original/'started.json'),original_registered_identities=original_ids,")
runner = runner.replace("batch=ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R001/attempts'", "batch=ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R003/attempts'")
runner = runner.replace("report.name.startswith('m002_E006_R001_')", "report.name.startswith('m002_E006_R003_')")
runner = runner.replace("str(archive/'attribution.tcl')", "str(archive/'attribution_lean.tcl')")
runner = runner.replace("stage='readonly_slr1_attribution'", "stage='readonly_slr1_attribution_lean'")
runner = runner.replace("    external_inputs=target_manifest['external_inputs']", "    external_inputs=target_manifest['external_inputs']")
runner = runner.replace("            require({p:identity(row['path']) for p,row in external_inputs.items()} == new_peak_sources,'external source/target changed')", "            verify_external_inputs(external_inputs)\n            require({p:identity(row['path']) for p,row in reused_inputs.items()} == reused_inputs,'reused closed input changed')\n            require(identity(authorization_path)==inputs['replacement_authorization'],'replacement authorization changed')")
marker = '\ndef interrupted(signum, frame):'
runner = runner.replace(marker, '''\ndef verify_external_inputs(expected):
    actual={key:identity(row['path']) for key,row in expected.items()}
    require(actual == expected,'external source/target changed')
    return actual

''' + marker)
assert 'new_peak_sources' not in runner
ast.parse(runner)
(OUT / 'run_attribution_lean.py').write_text(runner)

launcher = (OLD / 'launch_detached.py').read_text()
launcher = launcher.replace('from pathlib import Path', 'from pathlib import Path\nimport argparse')
launcher = launcher.replace("ROOT = Path(__file__).resolve().parents[3]", "parser=argparse.ArgumentParser(description='Prepared independent lean launcher; run only after actual authorization and closed original lane')\nparser.add_argument('--authorization',type=Path,required=True)\nargs=parser.parse_args()\nROOT = Path(__file__).resolve().parents[3]")
launcher = launcher.replace('AT001_physopt_attribution', 'AT001_lean_physopt_attribution')
launcher = launcher.replace('experiment_results/runs/R001/attempts/AT001_lean_physopt_attribution', 'experiment_results/runs/R003/attempts/AT001_lean_physopt_attribution')
launcher = launcher.replace('E006_R001_AT001_lean_physopt_attribution', 'E006_R003_AT001_lean_physopt_attribution')
launcher = launcher.replace("str(SOURCE / 'run_attribution.py')", "str(SOURCE / 'run_attribution_lean.py')")
launcher = launcher.replace("'--report', str(report)]", "'--report', str(report), '--authorization', str(args.authorization.resolve())]")
launcher = launcher.replace("SOURCE = Path(__file__).resolve().parent", "SOURCE = Path(__file__).resolve().parent\nauthorization=json.loads(args.authorization.resolve().read_text())\nassert authorization.get('execution_authorized') is True and authorization.get('decision')=='allow_readonly_lean_replacement', 'No actual lean execution authorization'")
ast.parse(launcher)
(OUT / 'launch_detached.py').write_text(launcher)

for path in OUT.glob('*.py'):
    ast.parse(path.read_text(), filename=str(path))
assert tkinter.Tcl().call('info', 'complete', lean) == 1
assert tkinter.Tcl().call('info', 'complete', (OUT / 'targets.tcl').read_text()) == 1
assert [identity(row['path']) for row in bindings['sources']] == bindings['sources']
manifest = dict(preparation_only=True, native_started=False, original_archived_sources_unchanged=bindings['sources'],
    AST='complete; no launcher executed', Tcl_info_complete='1; Tcl source not evaluated',
    files=[identity(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='prepared_source_manifest.json'])
(OUT / 'prepared_source_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(dict(prepared_manifest=identity(OUT / 'prepared_source_manifest.json'),
    prepared_files=len(manifest['files']), original_sources_unchanged=True, native_started=False)))
