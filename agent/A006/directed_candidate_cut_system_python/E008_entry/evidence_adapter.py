#!/usr/bin/env python3
"""Truthful E005 successful-source adapter; existing diagnostic gates stay active.

No process control or EDA launch. Original production helpers are imported without
editing them. The completed pre-place parent validator is locally replaced because
its production predecessor accepts only a historical timeout source.
"""
from __future__ import annotations
import collections
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import shutil

import directed_evidence as directed

sys.dont_write_bytecode = True
ROOT = Path(os.environ.get('SLR2_WORKSPACE_ROOT',Path(__file__).resolve().parents[4])).resolve()
SCRIPTS = ROOT/'project/hardware/vivado/scripts'
sys.path.insert(0, str(SCRIPTS))
import m002_physical_evidence as e

SOURCE = ROOT/'project/hardware/vivado/reports/m002_E005_R004_AT003_current_CDC_bound_OPT_place_physopt'
BASE = 'scalellm_vcu118_f05_bd_i/core/inst/u_core/'
CANDIDATE_ROOT = os.environ.get('SLR2_CANDIDATE_ROOT', '')
CHECKPOINT_SHA = '8451b2a86885d5ebb7bcb58dc24c352ac442492425c174269f9a803bb39c202f'
DSP_REFS={'DSP48E2','DSP_ALU','DSP_A_B_DATA','DSP_C_DATA','DSP_MULTIPLIER',
          'DSP_M_DATA','DSP_OUTPUT','DSP_PREADD_DATA','DSP_PREADD'}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def rows(path):
    with path.open() as stream:
        reader = csv.DictReader(stream, delimiter='\t', quoting=csv.QUOTE_NONE)
        for row in reader:
            e.require(None not in row and all(v is not None for v in row.values()), 'Malformed native table: '+str(path))
            yield row


def selected(name):
    e.require(bool(CANDIDATE_ROOT), 'No actually selected exact candidate')
    return name.startswith(CANDIDATE_ROOT+'/')



def bindable(ref):
    # Inclusion in P ledger is not native placement/migration qualification.
    return ref not in {'GND', 'VCC'}



def accepted_raw_resource(ref, physical_parent, physical_ref):
    e.require(bool(physical_parent), 'Unresolved native physical parent')
    if ref.startswith('DSP'):
        e.require(physical_ref == 'DSP48E2' and selected(physical_parent), 'DSP actual parent is outside the selected exact root')
        return True
    e.require(ref == physical_ref, 'Non-DSP physical REF unexpectedly changed')
    return bindable(ref)



def successful_pre_place_parent(source, project, lineage, report, *, _write=True):
    source, project, report = map(Path, (source, project, report))
    e.require(source == SOURCE, 'Only the identified successful E005 source is allowed')
    command = json.loads((source/'command.json').read_text())
    e.require(command['synthesis'] == lineage, 'Original synthesis lineage changed')
    closed = e.parent_recovered_place(source/'diagnostic_evidence.json', project, lineage)
    pre = e.pre_place_evidence(source)
    e.require(pre['checkpoint']['sha256'] == CHECKPOINT_SHA and
              pre['checkpoint']['bytes'] == 396068466, 'Wrong qualified pre-place checkpoint')
    constraints = json.loads((source/'constraints_debug_materialized.json').read_text())
    integrity = json.loads((source/'integrity_debug_materialized.json').read_text())
    e.require(constraints['mode'] == 'embedded_checkpoint_inherited' and
              len(constraints['hashes']) == 175 and len(constraints['candidate_metadata']) == 162,
              'Original embedded constraint coverage changed')
    e.require(not integrity['gate_issues'] and integrity['reset_structure']['qualified'] and
              integrity['reset_fanout_observation']['qualified'] and
              integrity['debug_clock_observation']['relationship_qualified'],
              'Original completed pre-place integrity is incomplete')
    for name in constraints['hashes']: e.constraint_source(name, constraints)
    status = Path(command['managed_attempt'])/'status.json'
    value = dict(phase='post_debug_pre_place', source_report=str(source),
        original_execution_state='completed_successful_place_and_physopt',
        original_execution_preserved=True,
        restart_scope='new single-variable SLR2 experiment from saved pre-place; no partial placement inherited',
        checkpoint=pre['checkpoint'], checkpoint_package=e.checkpoint_package(Path(pre['checkpoint']['path'])),
        synthesis=lineage, status=e.file_id(status), command=e.file_id(source/'command.json'),
        child_log=e.file_id(source/'vivado.log'),
        completed_source_diagnostic=e.file_id(source/'diagnostic_evidence.json'),
        completed_source_physopt=closed['checkpoint'],
        stage_inputs=e.file_id(source/'stage_inputs.sha256'), archive=e.file_id(source/'archived_sources.sha256'),
        implementation_settings=e.file_id(source/'implementation_settings.txt'),
        inherited_pre_place=e.file_id(source/'pre_place_evidence.json'),
        inherited_integrity=e.file_id(source/'integrity_debug_materialized.json'),
        historical_command_receipts={'debug_materialization':e.file_id(source/'debug_materialization_command_result.txt')},
        inherited_opt_execution_proof=closed['inherited_opt_execution_proof'],
        historical_OPT_scope='original native project log-derived proof; no fabricated standalone opt command receipt',
        inherited_reports={'cdc_debug_materialized.rpt':e.file_id(source/'cdc_debug_materialized.rpt')},
        source_metadata=constraints['candidate_metadata'], hashes=constraints['hashes'],
        source_archives=constraints.get('source_archives',{}),
        tool_debug_metadata=constraints.get('tool_debug_metadata',{}),
        generated_source_candidates=constraints.get('generated_source_candidates',{}),
        actual_reads=e.file_id(source/'actual_xdc_reads_debug_materialized.json'),
        constraint_mode='embedded_checkpoint_inherited', formal_reset_cdc_safety='OPEN')
    if _write: save(report/'recovery_parent.json', value)
    return value


def constraint_chain(point, report):
    if point == 'route':
        previous_stage=os.environ.get('HAP_STAGE')
        previous_place=os.environ.get('HAP_PLACE_REPORT_DIR')
        os.environ.update(HAP_STAGE='route',HAP_PLACE_REPORT_DIR=str(report))
        try: value=e.recovery_constraints(point,report)
        finally:
            for key,old in [('HAP_STAGE',previous_stage),('HAP_PLACE_REPORT_DIR',previous_place)]:
                if old is None: os.environ.pop(key,None)
                else: os.environ[key]=old
    else: value = e.recovery_constraints(point, report)
    if point != 'project':
        overlay = {name:e.file_id(report/name) for name in (
            'candidate_pblock_readback.txt', 'candidate_actual_SLR2_ranges.tsv',
            'candidate_existing_constraints.tsv', 'candidate_constraint_conflicts.txt',
            'candidate_effective_physical.xdc', 'candidate_P_pre_place.tsv',
            'candidate_RAW_pre_place.tsv', 'candidate_S_pre_place.tsv', 'candidate_physical_mapping_pre_place.tsv',
            'candidate_physical_members_pre_place.tsv', 'candidate_existing_pblocks_pre_place.tcllist',
            'candidate_resource_admissibility.tsv', 'candidate_resource_native_property_support.tsv',
            'candidate_resource_admissibility_conflicts.tcllist',
            'candidate_policy_preservation.txt', 'candidate_policy_conflicts.tcllist')}
        readback = e.key_values(report/'candidate_pblock_readback.txt')
        e.require(all(readback.get(k,'').lower() in {'0','false'} for k in
            ('IS_SOFT','EXCLUDE_PLACEMENT','CONTAIN_ROUTING')), 'Candidate physical policy changed')
        e.require(not (report/'candidate_constraint_conflicts.txt').read_text().strip(),
                  'Existing fixed/physical constraints conflict')
        previous = {'place':'pre_place_restore','physopt':'place','route':'physopt'}.get(point)
        if previous:
            old = json.loads((report/f'constraints_{previous}.json').read_text())
            e.require(old['candidate_physical_overlay']['artifacts'] == overlay,
                      'Candidate physical overlay identity changed during implementation')
        value['candidate_physical_overlay'] = dict(
            mechanism='native create/resize/add_cells_to_pblock and set_property; no read_xdc',
            physical_xdc_scope='export of all effective physical constraints after overlay; not a new read',
            unchanged_embedded_source_count=len(value['hashes']), artifacts=overlay)
        save(report/f'constraints_{point}.json', value)
    return value


def membership(point, report):
    members = list(rows(report/f'candidate_membership_{point}.tsv'))
    raw = {r['NAME']:r['REF_NAME'] for r in rows(report/f'candidate_RAW_{point}.tsv')}
    semantic = {r['NAME']:r['REF_NAME'] for r in rows(report/f'candidate_S_{point}.tsv')}
    physical = {r['NAME']:r['REF_NAME'] for r in rows(report/f'candidate_P_{point}.tsv')}
    e.require(len({r['NAME'] for r in members}) == len(members), 'Duplicate primitive membership')
    e.require(raw == {r['NAME']:r['REF_NAME'] for r in members if selected(r['NAME'])},
              'Native literal selector differs from accepted selector')
    e.require(semantic == {name:ref for name,ref in raw.items() if ref not in {'GND','VCC'}},
              'Logical S must exclude RAW GND/VCC constants')
    mapping = {r['raw_NAME']:r['physical_NAME']
               for r in rows(report/f'candidate_physical_mapping_{point}.tsv')}
    e.require(set(mapping) == set(raw), 'RAW/physical mapping incomplete')
    expected = {}
    for r in members:
        e.require((r['selected_RAW']=='1') == selected(r['NAME']), 'Wrong native selected_RAW flag')
        e.require((r['selected_S']=='1') == (r['NAME'] in semantic), 'Wrong native selected_S flag')
        if r['NAME'] not in raw: continue
        ref, name = r['physical_REF'], r['physical_parent']
        accepted_raw_resource(r['REF_NAME'],name,ref)
        e.require(name and mapping[r['NAME']] == name, 'Unresolved physical mapping')
        if r['REF_NAME'].startswith('DSP') and r['REF_NAME'] != 'DSP48E2':
            e.require(r['NAME'].startswith(name+'/') and physical.get(name)=='DSP48E2',
                      'DSP internal does not map to actual semantic DSP48E2 ancestor')
        e.require((r['selected_P']=='1') == bindable(ref), 'Wrong excluded resource policy')
        if bindable(ref): expected[name] = ref
    e.require(physical == expected and all(selected(n) and bindable(r) for n,r in physical.items()),
              'Placeable P differs from normalized literal selector')
    e.require(raw and semantic and physical, 'Empty exact candidate ledger')
    e.require(all(selected(name) for name in raw), 'Candidate RAW escaped literal root')
    parent_rows = {r['NAME']: r for r in rows(report/f'candidate_physical_members_{point}.tsv')}
    e.require(set(parent_rows) == set(physical), 'Actual P-parent policy coverage incomplete')
    def fingerprint(values):
        return hashlib.sha256(''.join(f'{n}\t{r}\n' for n,r in sorted(values.items())).encode()).hexdigest()
    value = dict(phase=point, raw_selector_count=len(raw),semantic_S_count=len(semantic), placeable_P_count=len(physical),
        excluded_from_S_REF_counts=dict(collections.Counter(ref for ref in raw.values() if ref in {'GND','VCC'})),
        RAW_NAME_REF_sha256=fingerprint(raw),
        S_NAME_REF_sha256=fingerprint(semantic), P_NAME_REF_sha256=fingerprint(physical),
        S_sorted_NAME_sha256=hashlib.sha256(('\n'.join(sorted(semantic))+'\n').encode()).hexdigest(),
        RAW_sorted_NAME_sha256=hashlib.sha256(('\n'.join(sorted(raw))+'\n').encode()).hexdigest(),
        S_REF_counts=dict(collections.Counter(semantic.values())), P_REF_counts=dict(collections.Counter(physical.values())),
        exact_candidate_root=CANDIDATE_ROOT, P_parent_policy=e.file_id(report/f'candidate_physical_members_{point}.tsv'),
        native_exact_hierarchy_resources=e.file_id(report/f'utilization_candidate_{point}_SLR.rpt'),
        target_SLR='SLR2', actual_membership=e.file_id(report/f'candidate_membership_{point}.tsv'),
        claim='actual stage selector only; pre-place has no assumed placement or physopt count equality')
    save(report/f'candidate_membership_{point}.json',value)
    return value


def compliance(point, report):
    actual = list(rows(report/f'candidate_compliance_{point}.tsv'))
    pb = list(rows(report/f'candidate_pblock_actual_{point}.tsv'))
    absent_kinds={'ORIGINAL_MISSING','UNEXPLAINED_MISSING','REPLACED_WITH_NATIVE_ORIGIN'}
    bad = [r for r in actual if r['lineage'] not in absent_kinds and r['SLR']!='SLR2']
    pb_bad = [r for r in pb if r['SLR']!='SLR2']
    missing = [r for r in actual if r['lineage'] in absent_kinds]
    original = {r['NAME'] for r in rows(report/'candidate_P_pre_place.tsv')}
    added = [dict(r, verified_original_origin=r['ORIG_CELL_NAME'] if r['ORIG_CELL_NAME'] in original else None,
                  lineage=('NEW_WITH_VERIFIED_ORIG_CELL_NAME' if r['ORIG_CELL_NAME'] in original else 'NEW_OR_UNRESOLVED_ORIGIN'))
             for r in pb if r['NAME'] not in original]
    cut_path = report/f'candidate_cut_{point}_closed.txt'
    closed = e.key_values(cut_path)
    e.require(closed.get('completed')=='1' and closed.get('coverage_version')==directed.VERSION,
              'Directed candidate cut not closed with actual scope')
    cut_validation = json.loads((report / f'candidate_cut_summary_{point}.json').read_text())
    timing_validation = json.loads((report / f'candidate_timing_validation_{point}.json').read_text())
    e.require(cut_validation['coverage_version']==directed.VERSION and cut_validation['directed_boundary_complete'] is True and
              cut_validation['candidate_leaf_coverage_complete'] is True and timing_validation['complete_directional_query_sets'] is True,
              'Directed boundary or exact timing-set validation unclosed')
    cut_counts=collections.Counter(); classes=collections.Counter(); resolutions=collections.Counter()
    for r in rows(report/f'candidate_nets_{point}.tsv'):
        cut_counts[r['boundary']]+=1; resolutions[r['resolution']]+=1
    for r in rows(report/f'candidate_endpoints_{point}.tsv'): classes[r['pin_class']]+=1
    sites=collections.defaultdict(set)
    for r in rows(report/f'candidate_site_members_{point}.tsv'):
        sites[(r['SLR'],r['LOC'])].add('candidate' if r['selected_P']=='1' else 'other')
    reconciliation=json.loads((report/f'candidate_reconciliation_{point}.json').read_text())
    effective=e.key_values(report/f'candidate_effective_pblock_{point}.txt')
    policy_ok=all(effective.get(k,'').lower() in {'0','false'} for k in
                  ('IS_SOFT','EXCLUDE_PLACEMENT','CONTAIN_ROUTING'))
    resolved={r['NAME'] for r in rows(report/f'candidate_reconciled_P_{point}.tsv')}
    actual_pb={r['physical_NAME'] for r in rows(report/f'candidate_pblock_physical_{point}.tsv')}
    value=dict(
        phase=point, selected_SLR_counts=dict(collections.Counter(r['SLR'] for r in actual if r['lineage'] not in absent_kinds)),
        original_missing=missing, new_pblock_objects=added,
        surviving_or_new_selected_non_SLR2=bad, actual_pblock_non_SLR2=pb_bad,
        actual_pblock_objects=len(pb), candidate_touched_sites=len(sites),
        shared_candidate_sites=sum(len(v)>1 for v in sites.values()),
        coverage_version=directed.VERSION, candidate_directed_boundary_counts=dict(cut_counts), retained_endpoint_pin_classes=dict(classes),
        directed_cut_validation=e.file_id(report/f'candidate_cut_summary_{point}.json'),
        directional_timing_validation=e.file_id(report/f'candidate_timing_validation_{point}.json'),
        full_net_endpoint_coverage='DECLARED_PER_NET_NOT_CLAIMED_FOR_REDUCED_NETS',
        resolution_classes=dict(resolutions),
        reconciliation=e.file_id(report/f'candidate_reconciliation_{point}.json'),
        effective_pblock=e.file_id(report/f'candidate_effective_pblock_{point}.txt'),
        compliance_established=not bad and not pb_bad and bool(pb) and policy_ok and
            reconciliation['qualified'] and actual_pb==resolved and
            not any(r['lineage'] in {'ORIGINAL_MISSING','UNEXPLAINED_MISSING'} for r in missing) and
            not any(r['lineage']=='NEW_OR_UNRESOLVED_ORIGIN' for r in added),
        interpretation='Missing objects and new origin evidence are separate; name suffixes do not prove replication. Scope is candidate_directed_cut_v1; outside peer leaf loads are omitted only on qualified unique-external-driver nets. No traffic/SLL/TNS or whole-net fanout inferred.')
    save(report/f'candidate_compliance_{point}.json',value)
    e.require(value['compliance_established'], 'Actual surviving/new/Pblock objects violate SLR2 or are unplaced')
    return value


def reconcile_objects(original, literal, actual, origin_candidates):
    """Actual native correspondence only; never infer clones from name suffixes."""
    all_objects={r['NAME']:r for r in actual+origin_candidates}
    issues=[];resolved={};lineage=[];replacements=collections.defaultdict(list)
    for name,r in all_objects.items():
        ref=r['REF_NAME']
        try:bindable(ref)
        except Exception as exc:issues.append(f'{name}: {exc}');continue
        origin=r.get('ORIG_CELL_NAME','')
        if name in original and ref==original[name]:
            kind='ORIGINAL_SURVIVING'
        elif origin in original and ref==original[origin]:
            kind='NEW_WITH_VERIFIED_ORIG_CELL_NAME';replacements[origin].append(name)
        else:
            kind='NEW_OR_UNRESOLVED_ORIGIN';issues.append(f'Unexplained current object: {name} origin={origin}')
        if ref=='DSP48E2':
            source=name if name in original else origin
            if not selected(source):
                issues.append(f'DSP correspondence is outside selected exact root: {name}')
        resolved[name]=ref;lineage.append(dict(r,lineage=kind))
    for name,ref in original.items():
        if name not in resolved:
            kind='REPLACED_WITH_NATIVE_ORIGIN' if replacements.get(name) else 'UNEXPLAINED_MISSING'
            lineage.append(dict(NAME=name,REF_NAME=ref,lineage=kind,LOC='',SLR='UNKNOWN',
                                ORIG_CELL_NAME='',ORIG_REF_NAME=''))
            if kind=='UNEXPLAINED_MISSING':issues.append('Unexplained missing original: '+name)
    missing_literal=set(literal)-set(resolved)
    if missing_literal:issues.append('Literal P objects absent from actual reconciled scope: '+repr(sorted(missing_literal)[:10]))
    pb_names={r['NAME'] for r in actual}
    if pb_names!=set(resolved):issues.append('Actual Pblock physical members differ from reconciled P')
    return dict(qualified=not issues,issues=issues,resolved=resolved,lineage=lineage,
                original_count=len(original),literal_count=len(literal),actual_physical_Pblock_count=len(pb_names),
                explained_replacements=dict(replacements))


def require_origin_query(value):
    e.require(value.get('native_tcl_code')=='0' and
              value.get('query_executed')=='1' and
              value.get('required_origin_property_verified')=='1',
              'Global native origin query failed/unsupported; empty origins cannot qualify reconciliation')


def reconcile(point, report):
    require_origin_query(e.key_values(report/f'candidate_native_origin_query_{point}.txt'))
    original={r['NAME']:r['REF_NAME'] for r in rows(report/'candidate_P_pre_place.tsv')}
    literal={r['NAME']:r['REF_NAME'] for r in rows(report/f'candidate_P_{point}.tsv')}
    actual=list(rows(report/f'candidate_pblock_physical_{point}.tsv'))
    for r in actual:r['NAME']=r['physical_NAME']
    origins=list(rows(report/f'candidate_native_origin_objects_{point}.tsv'))
    value=reconcile_objects(original,literal,actual,origins)
    value['native_origin_query']=e.file_id(report/f'candidate_native_origin_query_{point}.txt')
    save(report/f'candidate_reconciliation_{point}.json',value)
    fields=['NAME','REF_NAME','lineage','LOC','SLR','ORIG_CELL_NAME','ORIG_REF_NAME']
    with (report/f'candidate_reconciliation_{point}.tsv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,delimiter='\t',extrasaction='ignore');writer.writeheader();writer.writerows(value['lineage'])
    with (report/f'candidate_reconciled_P_{point}.tsv').open('w') as stream:
        stream.write('NAME\tREF_NAME\n')
        for name,ref in sorted(value['resolved'].items()):stream.write(f'{name}\t{ref}\n')
    # The new names are actual NAME strings. Brace literals avoid []/$ evaluation.
    def literal_tcl(text):
        e.require(not any(c in text for c in '{}\n\r'),'Unsupported native NAME for literal Tcl binding')
        return '{'+text+'}'
    (report/f'candidate_reconciled_P_{point}.tcl').write_text('set ::slr2::P [dict create '+
        ' '.join(literal_tcl(n)+' '+literal_tcl(r) for n,r in sorted(value['resolved'].items()))+']\n')
    e.require(value['qualified'],'Actual stage correspondence unresolved: '+repr(value['issues'][:10]))
    return value


def cut_net_category(actual_clocks, classes):
    known_data={'DATA_ARITHMETIC','DATA_REGISTER','DATA_LOGIC_PRIMITIVE','SELECT_CONTROL'}
    known_controls={'RESET_SET','CONSTANT','ENABLE_WRITE_CONTROL'}
    unknown=not classes or any(c not in known_data|known_controls and not c.startswith('CLOCK') for c in classes)
    if actual_clocks or any(c.startswith('CLOCK') for c in classes):return 'clock_cut_nets',unknown
    if 'RESET_SET' in classes:return 'reset_set_cut_nets',unknown
    if 'CONSTANT' in classes:return 'constant_cut_nets',unknown
    if 'ENABLE_WRITE_CONTROL' in classes:return 'enable_write_control_cut_nets',unknown
    if unknown:
        return ('mixed_known_unknown_cut_nets' if classes & known_data else 'unknown_or_unclassified_cut_nets'),True
    return 'known_data_or_select_control_cut_nets',False


def directed_validation_projection(point, report):
    """Read-only per-phase view binds actual reconciled P without replacing literal P."""
    audit = report / ('candidate_directed_validation_' + point)
    projection = audit / 'projection_identity.json'
    actual_p = report / (f'candidate_P_{point}.tsv' if point == 'pre_place' else f'candidate_reconciled_P_{point}.tsv')
    e.require(actual_p.is_file(), 'Actual phase P ledger missing for directed validator')
    if point != 'pre_place':
        reconciliation = json.loads((report / f'candidate_reconciliation_{point}.json').read_text())
        e.require(reconciliation['qualified'] is True, 'Actual P correspondence unqualified')
        resolved = {row['NAME']: row['REF_NAME'] for row in rows(actual_p)}
        e.require(resolved == reconciliation['resolved'], 'Actual reconciled P JSON/table differs')
    required_tags = ['RAW','S','P','pins','local_owners','segments','local_pin_net','nets','endpoints','boundary_timing_scope']
    input_paths = [report / f'candidate_{tag}_{point}.tsv' for tag in required_tags]
    input_paths += [report / f'candidate_{tag}_{point}.tcllist' for tag in ['directed_class_schema','local_scope','native_role_queries']]
    e.require(all(path.is_file() for path in input_paths), 'Directed phase raw input missing')
    optional_paths = [report / f'candidate_timing_queries_{point}.tcllist', report / f'candidate_scoped_timing_{point}.tsv']
    inputs = {path.name: path.resolve() for path in input_paths + optional_paths if path.is_file()}
    inputs[f'candidate_P_{point}.tsv'] = actual_p.resolve()
    # Pattern above excludes markers whose basename has an extra suffix.
    for basename in [f'candidate_cut_{point}_closed.txt', f'candidate_scoped_timing_{point}_coverage.txt']:
        source = report / basename
        if source.is_file(): inputs[basename] = source.resolve()
    for direction in ['INGRESS', 'EGRESS', 'UNRESOLVED']:
        for kind in ['max', 'min']:
            path = report / f'candidate_cut_timing_{point}_{direction}_{kind}.rpt'
            if path.is_file(): inputs[path.name] = path.resolve()
    if audit.exists():
        e.require(audit.is_dir() and not audit.is_symlink() and projection.is_file(), 'Invalid directed audit view')
        previous = json.loads(projection.read_text())
        for name, bound in previous['inputs'].items():
            e.require(directed.identity(Path(bound['path'])) == bound, 'Directed view input changed: ' + name)
        e.require(directed.identity(previous['literal_P_preserved']['path']) == previous['literal_P_preserved'], 'Literal original P ledger changed during directed view reuse')
    else:
        audit.mkdir()
    for name, source in sorted(inputs.items()):
        target = audit / name
        if target.exists() or target.is_symlink():
            e.require(target.is_symlink() and target.resolve() == source, 'Directed phase view mapping changed: ' + name)
        else: target.symlink_to(source)
    # Each update adds timing artifacts, preserving all prior input identities.
    value = dict(coverage_version=directed.VERSION, phase=point,
                 actual_P=directed.identity(actual_p), literal_P_preserved=directed.identity(report / f'candidate_P_{point}.tsv'),
                 P_source='literal actual pre-place P' if point == 'pre_place' else 'same-phase native-origin reconciled actual P',
                 inputs={name:directed.identity(path) for name,path in sorted(inputs.items())},
                 scope='Read-only projection only; source raw tables are never rewritten')
    if projection.exists():
        # Keep every view revision; no identity-bearing producer record overwritten.
        revision = audit / ('projection_identity_' + str(len(list(audit.glob('projection_identity_*.json'))) + 1) + '.json')
        directed.save(revision, value)
    else: directed.save(projection, value)
    return audit


def cut_summary(point, report):
    audit = directed_validation_projection(point, report)
    value = directed.cut(point, audit)
    value['phase'] = point
    value['actual_phase_membership_projection'] = e.file_id(audit / 'projection_identity.json')
    directed.save(report / f'candidate_cut_summary_{point}.json', value)
    return value


def directed_timing(point, report):
    audit = directed_validation_projection(point, report)
    value = directed.timing(point, audit)
    value['phase'] = point
    directed.save(report / f'candidate_timing_validation_{point}.json', value)
    return value


# Scoped substitution inside this process only; existing gate implementation is reused.
e.recovery_pre_place_parent = successful_pre_place_parent
e.constraint_chain = constraint_chain


def main():
    if sys.argv[1:] == ['runtime-preflight']:
        value = directed.runtime_preflight()
        value['E008_full_adapter_imported'] = True
        value['E008_source_workspace'] = str(ROOT)
        print(json.dumps(value));return
    action, point, directory = sys.argv[1:]
    report=Path(directory).resolve()
    if action=='constraints': constraint_chain(point,report)
    elif action=='hook-batch': e.hook_batch(point,report)
    elif action=='pre-place':
        value=e.restored_pre_place_evidence(report,create=True)
        e.require('candidate_physical_overlay' in json.loads((report/'constraints_pre_place_restore.json').read_text()),
                  'Actual pre-place overlay qualification missing')
        return value
    elif action=='membership': membership(point,report)
    elif action=='compliance': compliance(point,report)
    elif action=='cut': cut_summary(point,report)
    elif action=='directed-timing': directed_timing(point,report)
    elif action=='reconcile': reconcile(point,report)
    else: raise ValueError('Unsupported isolated evidence action')


if __name__=='__main__': main()
