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

sys.dont_write_bytecode = True
ROOT = Path(os.environ.get('SLR2_WORKSPACE_ROOT',Path(__file__).resolve().parents[3])).resolve()
SCRIPTS = ROOT/'project/hardware/vivado/scripts'
sys.path.insert(0, str(SCRIPTS))
import m002_physical_evidence as e

SOURCE = ROOT/'project/hardware/vivado/reports/m002_E005_R004_AT003_current_CDC_bound_OPT_place_physopt'
BASE = 'scalellm_vcu118_f05_bd_i/core/inst/u_core/'
FRONT = BASE+'u_compute/u_mlp/u_input_frontend/'
TENSOR = BASE+'u_tensor/'
CHECKPOINT_SHA = '8451b2a86885d5ebb7bcb58dc24c352ac442492425c174269f9a803bb39c202f'


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def rows(path):
    with path.open() as stream:
        yield from csv.DictReader(stream, delimiter='\t')


def selected(name):
    if name.startswith(FRONT):
        return not name[len(FRONT):].startswith(('u_cache0/', 'u_cache1/',
            'bundle_u8_bank_r', 'bundle_meta_bank_r', 'g_bundle_row['))
    return name.startswith(TENSOR) and name[len(TENSOR):].startswith((
        'g_input_beat_bank[', 'input_beat_r', 'input_group_r', 'input_group_valid_r',
        'input_beat_count', 'input_group_count'))


def bindable(ref):
    return ref not in {'GND','VCC'} and not re.match(
        r'^(BUFG|BUFH|BUFR|BUFIO|BUFMR|BUFCE|IBUF|OBUF|IOBUF|MMCME|PLLE)', ref)


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
            'candidate_RAW_pre_place.tsv', 'candidate_S_pre_place.tsv', 'candidate_physical_mapping_pre_place.tsv')}
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
        e.require(name and mapping[r['NAME']] == name, 'Unresolved physical mapping')
        if r['REF_NAME'].startswith('DSP') and r['REF_NAME'] != 'DSP48E2':
            e.require(r['NAME'].startswith(name+'/') and semantic.get(name)=='DSP48E2',
                      'DSP internal does not map to actual semantic DSP48E2 ancestor')
        e.require((r['bindable_P']=='1') == bindable(ref), 'Wrong excluded resource policy')
        if bindable(ref): expected[name] = ref
    e.require(physical == expected and all(selected(n) and bindable(r) for n,r in physical.items()),
              'Placeable P differs from normalized literal selector')
    # Exact pre-place semantic dimensions; never hardcode the physopt set size.
    indices = {}
    patterns = {
        'tensor_48x256':(re.escape(TENSOR)+r'g_input_beat_bank\[(\d+)\]\.input_group_beat_r_reg\[(\d+)\]\[(\d+)\]',48,256),
        'capture_16x768':(re.escape(FRONT)+r'input_buffer_row_r_reg\[(\d+)\]\[(\d+)\]',16,768)}
    for label,(pattern,a,b) in patterns.items():
        actual = set()
        for name,ref in semantic.items():
            m = re.fullmatch(pattern,name)
            if m:
                dims = tuple(map(int,m.groups()))
                if len(dims)==3:
                    e.require(dims[0]==dims[1], 'Tensor bank row identities disagree')
                    dims=dims[1:]
                e.require(ref.startswith(('FD','LD')), 'Input index is not storage')
                actual.add(dims)
        indices[label] = dict(matched=len(actual), expected=a*b, complete=actual=={(i,j) for i in range(a) for j in range(b)})
    quantizers = {q:sum(n.startswith(FRONT+f'g_quant[{q}].u_quantizer/') for n in semantic) for q in range(4)}
    dsp = sum(ref=='DSP48E2' for ref in physical.values())
    if point == 'pre_place':
        e.require(all(r['complete'] for r in indices.values()) and all(quantizers.values()) and dsp==8,
                  'Actual pre-place banks/four quantizers/eight physical DSP not established')
        e.require(any(n.startswith(FRONT+'u_hadamard/') for n in semantic), 'Actual Hadamard missing')
    def fingerprint(values):
        return hashlib.sha256(''.join(f'{n}\t{r}\n' for n,r in sorted(values.items())).encode()).hexdigest()
    value = dict(phase=point, raw_selector_count=len(raw),semantic_S_count=len(semantic), placeable_P_count=len(physical),
        excluded_from_S_REF_counts=dict(collections.Counter(ref for ref in raw.values() if ref in {'GND','VCC'})),
        RAW_NAME_REF_sha256=fingerprint(raw),
        S_NAME_REF_sha256=fingerprint(semantic), P_NAME_REF_sha256=fingerprint(physical),
        S_sorted_NAME_sha256=hashlib.sha256(('\n'.join(sorted(semantic))+'\n').encode()).hexdigest(),
        RAW_sorted_NAME_sha256=hashlib.sha256(('\n'.join(sorted(raw))+'\n').encode()).hexdigest(),
        S_REF_counts=dict(collections.Counter(semantic.values())), P_REF_counts=dict(collections.Counter(physical.values())),
        exact_input_indices=indices, quantizer_primitive_counts=quantizers, physical_DSP=dsp,
        target_SLR='SLR2', actual_membership=e.file_id(report/f'candidate_membership_{point}.tsv'),
        claim='actual stage selector only; pre-place has no assumed placement or physopt count equality')
    save(report/f'candidate_membership_{point}.json',value)
    return value


def compliance(point, report):
    actual = list(rows(report/f'candidate_compliance_{point}.tsv'))
    pb = list(rows(report/f'candidate_pblock_actual_{point}.tsv'))
    bad = [r for r in actual if r['lineage']!='ORIGINAL_MISSING' and r['SLR']!='SLR2']
    pb_bad = [r for r in pb if r['SLR']!='SLR2']
    missing = [r for r in actual if r['lineage']=='ORIGINAL_MISSING']
    original = {r['NAME'] for r in rows(report/'candidate_P_pre_place.tsv')}
    added = [dict(r, verified_original_origin=r['ORIG_CELL_NAME'] if r['ORIG_CELL_NAME'] in original else None,
                  lineage=('NEW_WITH_VERIFIED_ORIG_CELL_NAME' if r['ORIG_CELL_NAME'] in original else 'NEW_OR_UNRESOLVED_ORIGIN'))
             for r in pb if r['NAME'] not in original]
    cut_path = report/f'candidate_cut_{point}_closed.txt'
    e.require(e.key_values(cut_path).get('completed')=='1','Complete candidate cut not closed')
    cut_counts=collections.Counter(); classes=collections.Counter(); resolutions=collections.Counter()
    for r in rows(report/f'candidate_nets_{point}.tsv'):
        cut_counts[r['boundary']]+=1; resolutions[r['resolution']]+=1
    for r in rows(report/f'candidate_endpoints_{point}.tsv'): classes[r['pin_class']]+=1
    sites=collections.defaultdict(set)
    for r in rows(report/f'candidate_site_members_{point}.tsv'):
        sites[(r['SLR'],r['LOC'])].add('candidate' if r['selected_P']=='1' else 'other')
    value=dict(
        phase=point, selected_SLR_counts=dict(collections.Counter(r['SLR'] for r in actual if r['lineage']!='ORIGINAL_MISSING')),
        original_missing=missing, new_pblock_objects=added,
        surviving_or_new_selected_non_SLR2=bad, actual_pblock_non_SLR2=pb_bad,
        actual_pblock_objects=len(pb), candidate_touched_sites=len(sites),
        shared_candidate_sites=sum(len(v)>1 for v in sites.values()),
        complete_candidate_net_classes=dict(cut_counts), endpoint_pin_classes=dict(classes),
        resolution_classes=dict(resolutions),
        compliance_established=not bad and not pb_bad and bool(pb),
        interpretation='Missing objects and new origin evidence are separate; name suffixes do not prove replication. No traffic/SLL/TNS inferred from this complete connectivity cut.')
    save(report/f'candidate_compliance_{point}.json',value)
    e.require(value['compliance_established'], 'Actual surviving/new/Pblock objects violate SLR2 or are unplaced')
    return value


def cut_summary(point, report):
    e.require(e.key_values(report/f'candidate_cut_{point}_closed.txt').get('completed')=='1',
              'Native full candidate cut is not closed')
    nets={r['canonical_net']:r for r in rows(report/f'candidate_nets_{point}.tsv')}
    e.require(bool(nets),'No candidate attached nets')
    endpoint_counts=collections.Counter(); direction=collections.Counter(); classes=collections.Counter()
    net_classes=collections.defaultdict(set); endpoint_names=set()
    for r in rows(report/f'candidate_endpoints_{point}.tsv'):
        key=(r['canonical_net'],r['kind'],r['NAME'])
        e.require(key not in endpoint_names and r['canonical_net'] in nets, 'Duplicate/foreign canonical endpoint')
        endpoint_names.add(key);endpoint_counts[(r['canonical_net'],r['kind'])]+=1
        direction[(r['kind'],r['DIRECTION'])]+=1;classes[r['pin_class']]+=1
        net_classes[r['canonical_net']].add(r['pin_class'])
    segment_names={}; canonical_counts=collections.Counter()
    for r in rows(report/f'candidate_segments_{point}.tsv'):
        e.require(r['segment'] not in segment_names and r['canonical_net'] in nets,'Segment in multiple/missing canonical nets')
        segment_names[r['segment']]=r['canonical_net'];canonical_counts[r['canonical_net']]+=1
    for name,r in nets.items():
        e.require(endpoint_counts[(name,'LEAF_PIN')]==int(r['leaf_pins']) and
                  endpoint_counts[(name,'TOP_PORT')]==int(r['top_ports']) and
                  canonical_counts[name]==int(r['segments']), 'Closed cut native counts disagree')
    exact_leaf_names={name for _,kind,name in endpoint_names if kind=='LEAF_PIN'}
    candidate_pins=0;unmatched=0;candidate_directions=collections.Counter()
    for r in rows(report/f'candidate_pins_{point}.tsv'):
        candidate_pins+=1;candidate_directions[r['DIRECTION']]+=1
        if r['NAME'] not in exact_leaf_names: unmatched+=1
    separated=collections.Counter()
    for name,r in nets.items():
        if r['boundary']!='CUT':continue
        cs=net_classes[name]
        if r['actual_clocks'] or 'CLOCK' in cs:separated['clock_cut_nets']+=1
        elif 'RESET_SET' in cs:separated['reset_set_cut_nets']+=1
        elif 'CONSTANT' in cs:separated['constant_cut_nets']+=1
        elif 'ENABLE_WRITE_CONTROL' in cs:separated['enable_write_control_cut_nets']+=1
        else:separated['data_or_other_control_cut_nets']+=1
    save(report/f'candidate_cut_summary_{point}.json',dict(phase=point,
        canonical_nets=len(nets), segments=len(segment_names), endpoints=len(endpoint_names),
        candidate_pin_records=candidate_pins, candidate_pins_without_exact_leaf_endpoint_match=unmatched,
        candidate_pin_directions=dict(candidate_directions),
        all_endpoint_direction_counts={f'{a}/{b}':v for (a,b),v in direction.items()},
        all_endpoint_pin_classes=dict(classes), exclusive_cut_categories=dict(separated),
        boundary_counts=dict(collections.Counter(r['boundary'] for r in nets.values())),
        resolution_counts=dict(collections.Counter(r['resolution'] for r in nets.values())),
        coverage='All RAW/S/P pins, all attached canonical merged nets, all-direction leaf endpoints and top ports. RAW constants remain visible but are excluded from logical S/P. Candidate pins are exported even if absent from the leaf endpoint set.',
        limits='Unmatched candidate pins can be disconnected or non-leaf physical-parent pins; no disconnection is inferred. Connectivity only; no traffic, activity, SLL use or full-cut timing TNS inferred. Clock/reset categories precede data/control.'))


# Scoped substitution inside this process only; existing gate implementation is reused.
e.recovery_pre_place_parent = successful_pre_place_parent
e.constraint_chain = constraint_chain


def main():
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
    else: raise ValueError('Unsupported isolated evidence action')


if __name__=='__main__': main()
