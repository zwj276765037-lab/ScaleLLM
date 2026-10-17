#!/usr/bin/env python3
"""One-time CPU source derivation for E008. Never launches or controls EDA."""
import ast
import hashlib
import json
from pathlib import Path
import re
import shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OLD=HERE.parent/'slr2_input_locality'
READONLY=HERE.parent/'E006_exact_candidates'


def proc(text,name):
    start=text.index('proc '+name+' ')
    end=text.find('\nproc ',start+1)
    if end<0: end=len(text)
    return text[start:end]


def replace_proc(text,name,new):
    old=proc(text,name)
    return text.replace(old,new,1)


def pyfunc(text,name,new):
    tree=ast.parse(text)
    node=next(n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
    lines=text.splitlines(keepends=True)
    return ''.join(lines[:node.lineno-1])+new+'\n\n'+''.join(lines[node.end_lineno:])


def main():
    # This entry is source generation only and is never invoked by the runner.
    assert not (HERE/'prepared_manifest.json').exists(), 'Do not regenerate an admitted source'
    old_manifest=json.loads((OLD/'prepared_manifest.json').read_text())
    for row in old_manifest['own_sources']:
        p=Path(row['path']);assert len(p.read_bytes())==row['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
    for name in ['property_alignment.tcl','implementation.tcl']:
        shutil.copy2(OLD/name,HERE/name)
    controller=(HERE/'implementation.tcl').read_text().replace('E007','E008')
    controller=controller.replace('slr2::cut pre_place\n','slr2::cut pre_place\nslr2::scoped_timing pre_place\n')
    (HERE/'implementation.tcl').write_text(controller)
    hooks=(OLD/'candidate_hooks.tcl').read_text().replace('E007','E008')
    hooks=hooks.replace('# Agent-owned SLR2 input-locality hooks.', '# Agent-owned exact-hotspot SLR2 hooks.')
    hooks=hooks.replace('    variable front ${base}u_compute/u_mlp/u_input_frontend/\n    variable tensor ${base}u_tensor/',
                        '    variable root $::env(SLR2_CANDIDATE_ROOT)\n    variable candidateID $::env(SLR2_CANDIDATE_ID)')
    hooks=hooks.replace('variable pblock m002_input_locality_SLR2','variable pblock m002_exact_hotspot_SLR2')
    hooks=replace_proc(hooks,'slr2::group', '''proc slr2::group {name} {
    variable root
    return [expr {[prefix $name ${root}/] ? "EXACT_HOTSPOT_SELECTED" : "OUTSIDE_SELECTOR"}]
}''')
    hooks=replace_proc(hooks,'slr2::selected', '''proc slr2::selected {name} {expr {[group $name] eq "EXACT_HOTSPOT_SELECTED"}}''')
    hooks=replace_proc(hooks,'slr2::bindable', '''proc slr2::bindable {ref} {
    # Ledger inclusion only. Actual migration admissibility is a separate gate.
    return [expr {$ref ni {GND VCC}}]
}''')
    readonly=(READONLY/'candidate_inspector.tcl').read_text()
    resolve=proc(readonly,'slr2::readonly_resolve')
    resolve=resolve.replace('proc slr2::readonly_resolve {point root}', 'proc slr2::resolve {point}')
    resolve=resolve.replace('variable candidateSets','variable cellPblocks;variable root')
    resolve=resolve.replace('    set RAW [dict create];set S [dict create];set P [dict create];set mapping [dict create]',
        '    set RAW [dict create];set S [dict create];set P [dict create];set mapping [dict create]\n    set handles [dict create];set physicalCache [dict create];set cellInfo [dict create];set cellPblocks [dict create]')
    # Fix the real native export bug: separator must be an explicit Tcl word.
    resolve=resolve.replace('[join $row \t]', '[join $row "\\t"]')
    resolve=resolve.replace('] \t]', '] "\\t"]')
    resolve=resolve.replace('    dict set candidateSets $point [list RAW $RAW S $S P $P]', '''    set cellPblocks $memberPblocks
    set h [open [file join $::m002_report_dir candidate_physical_mapping_${point}.tsv] {WRONLY CREAT EXCL}]
    puts $h "raw_NAME\\tphysical_NAME"
    dict for {name parent} $mapping {puts $h "$name\\t$parent"};close $h''')
    resolve=resolve.replace('    return $root_object', '''    report_utilization -cells $root_object -slr -file [file join $::m002_report_dir utilization_candidate_${point}_SLR.rpt]
    exec python3 $::env(SLR2_ADAPTER) membership $point $::m002_report_dir
    return $root_object''')
    hooks=replace_proc(hooks,'slr2::resolve',resolve)
    # Adopt already reviewed alias deduplication and all-direction cut procedure.
    for name in ['slr2::cut','slr2::timing_boundary_selection']:
        replacement=proc(readonly,name).replace('E006_QUERY_COMPLETED','E008_QUERY_COMPLETED')
        hooks=replace_proc(hooks,name,replacement)
    # Existing post/runtime procedures remain in place. Runtime overrides phase.
    (HERE/'candidate_hooks.tcl').write_text(hooks)
    runtime=(OLD/'runtime_hooks.tcl').read_text().replace('E007','E008')
    runtime=runtime.replace('variable P;variable front;variable tensor','variable P;variable root')
    runtime=runtime.replace('variable P;variable originalP;variable front;variable tensor','variable P;variable originalP;variable root')
    start=runtime.index('    # Also preserve retained frontend/tensor objects and their hierarchy policies.')
    end=runtime.index('    set before [placement_policy before $scope]',start)
    runtime=runtime[:start]+'''    # Check all selected physical parents, literal descendants and every real ancestor.
    set scope $objects
    set broad $root;set bracket [string first {[} $root]
    if {$bracket >= 0} {set broad [string range $root 0 [expr {$bracket-1}]]}
    foreach object [get_cells -quiet -hier -filter [format {NAME =~ "%s*"} $broad]] {
        set name [get_property NAME $object]
        if {$name eq $root || [prefix $name ${root}/]} {lappend scope $object}
    }
    set path $root
    while {$path ne "." && $path ne "/"} {
        set parent [m002_exact get_cells $path]
        if {[llength $parent] != 1} {error "Required actual ancestor unavailable: $path"}
        lappend scope $parent;set path [file dirname $path]
    }
    set scope [lsort -unique $scope]
    resource_admissibility $objects
'''+runtime[end:]
    runtime=runtime.replace('scope=all_original_pblocks_and_frontend_tensor_ancestors_cells','scope=all_original_pblocks_and_exact_candidate_ancestors_cells')
    runtime=runtime.replace('set query [format {IS_PRIMITIVE == 1 && (ORIG_CELL_NAME =~ "%s*" || ORIG_CELL_NAME =~ "%s*")} $front $tensor]',
        'set query {IS_PRIMITIVE == 1 && ORIG_CELL_NAME != ""}')
    # Timing uses the same reviewed procedure, including exact native query commands.
    runtime=replace_proc(runtime,'slr2::scoped_timing',proc(readonly,'slr2::scoped_timing'))
    (HERE/'runtime_hooks.tcl').write_text(runtime)
    adapter=(OLD/'evidence_adapter.py').read_text()
    adapter=adapter.replace("FRONT = BASE+'u_compute/u_mlp/u_input_frontend/'\nTENSOR = BASE+'u_tensor/'", "CANDIDATE_ROOT = os.environ.get('SLR2_CANDIDATE_ROOT', '')")
    adapter=pyfunc(adapter,'selected', '''def selected(name):
    e.require(bool(CANDIDATE_ROOT), 'No actually selected exact candidate')
    return name.startswith(CANDIDATE_ROOT+'/')''')
    adapter=pyfunc(adapter,'bindable', '''def bindable(ref):
    # Inclusion in P ledger is not native placement/migration qualification.
    return ref not in {'GND', 'VCC'}''')
    adapter=pyfunc(adapter,'accepted_raw_resource', '''def accepted_raw_resource(ref, physical_parent, physical_ref):
    e.require(bool(physical_parent), 'Unresolved native physical parent')
    if ref.startswith('DSP'):
        e.require(physical_ref == 'DSP48E2' and selected(physical_parent), 'DSP actual parent is outside the selected exact root')
        return True
    e.require(ref == physical_ref, 'Non-DSP physical REF unexpectedly changed')
    return bindable(ref)''')
    adapter=adapter.replace("r['bindable_P']", "r['selected_P']")
    adapter=adapter.replace("r['NAME'].startswith(name+'/') and semantic.get(name)=='DSP48E2'", "r['NAME'].startswith(name+'/') and physical.get(name)=='DSP48E2'")
    start=adapter.index('    # Exact pre-place semantic dimensions; never hardcode the physopt set size.')
    end=adapter.index('    def fingerprint(values):',start)
    adapter=adapter[:start]+'''    e.require(raw and semantic and physical, 'Empty exact candidate ledger')
    e.require(all(selected(name) for name in raw), 'Candidate RAW escaped literal root')
    parent_rows = {r['NAME']: r for r in rows(report/f'candidate_physical_members_{point}.tsv')}
    e.require(set(parent_rows) == set(physical), 'Actual P-parent policy coverage incomplete')
'''+adapter[end:]
    adapter=adapter.replace('        exact_input_indices=indices, quantizer_primitive_counts=quantizers, physical_DSP=dsp,',
        "        exact_candidate_root=CANDIDATE_ROOT, P_parent_policy=e.file_id(report/f'candidate_physical_members_{point}.tsv'),\n        native_exact_hierarchy_resources=e.file_id(report/f'utilization_candidate_{point}_SLR.rpt'),")
    adapter=adapter.replace("            if not source.startswith(FRONT+'u_hadamard/'):\n                issues.append(f'DSP correspondence is outside intended Hadamard: {name}')", "            if not selected(source):\n                issues.append(f'DSP correspondence is outside selected exact root: {name}')")
    (HERE/'evidence_adapter.py').write_text(adapter)
    runner=(OLD/'run_candidate.py').read_text().replace('E007','E008').replace('SM011','SM012')
    runner=runner.replace('m002_slr2_input_locality_implementation','m002_exact_hotspot_offload_implementation')
    runner=runner.replace('slr2_input_locality_candidate_contract_2026-10-17.md','exact_hotspot_offload_implementation_contract_2026-10-17.md')
    runner=runner.replace('experiment_results/runs/R002/attempts','experiment_results/runs/R001/attempts').replace('m002_E008_R002_','m002_E008_R001_')
    runner=runner.replace("for key in ['contract','selector_reference','architecture_boundary_plan']:", "for key in ['contract','selector_reference','source_reuse_manifest']:")
    anchor="    require(bool(closeout.get('evidence')),'No actual attribution review evidence')"
    runner=runner.replace(anchor,anchor+'''
    selected = closeout.get('selected_candidate', {})
    targets = json.loads((HERE/'target_authority.json').read_text())['candidates']
    require(any(selected == dict(id=t['id'], root=t['exact_root']) for t in targets),
            'Empty or unsupported exact candidate selection')
    require(closeout.get('successor_contract') == identity(CONTRACT), 'Wrong E008 selected contract binding')
    require(closeout.get('preparation_manifest') == identity(HERE/'prepared_manifest.json'), 'Wrong E008 selected source binding')''')
    runner=runner.replace("return dict(closeout=identity(closeout_path),terminal_statuses=closed,closed_registered_identities=registered)",
        "return dict(closeout=identity(closeout_path),terminal_statuses=closed,closed_registered_identities=registered, selected_candidate=selected)")
    runner=runner.replace("env['SLR2_WORKSPACE_ROOT']=str(ROOT)", "env['SLR2_WORKSPACE_ROOT']=str(ROOT)\n    env['SLR2_CANDIDATE_ID']=dependency['selected_candidate']['id']\n    env['SLR2_CANDIDATE_ROOT']=dependency['selected_candidate']['root']")
    runner=runner.replace("files.update(p for p in archive.iterdir() if p.is_file())", "files.update(p for p in archive.iterdir() if p.is_file())\n    files.add(Path(dependency['closeout']['path']))")
    runner=runner.replace("scope='new E008 complete place/physopt/route; original impl_1 status preserved'", "scope='new E008 exact-hotspot complete place/physopt/route; original impl_1 status preserved', selected_candidate=dependency['selected_candidate']")
    (HERE/'run_candidate.py').write_text(runner)
    authority=ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R004/independent_candidate_targets.json'
    shutil.copy2(authority,HERE/'target_authority.json')
    print('E008 thin sources derived; no admission manifest and no EDA launch')


if __name__=='__main__':main()
