#!/usr/bin/env python3
"""CPU-only exact NAME subsets of the already-closed E006 primitive export."""
import collections
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
REPORT = ROOT / 'project/hardware/vivado/reports/m002_E006_R001_AT001_physopt_attribution'
BASE = 'scalellm_vcu118_f05_bd_i/core/inst/u_core/'
FRONT = BASE + 'u_compute/u_mlp/u_input_frontend/'
TENSOR = BASE + 'u_tensor/'


def identity(path):
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def classify(name):
    if name.startswith(FRONT):
        tail = name[len(FRONT):]
        for scope in ['u_hadamard', 'u_cache0', 'u_cache1'] + [f'g_quant[{q}].u_quantizer' for q in range(4)]:
            if tail.startswith(scope + '/'):
                return 'frontend/' + scope
        if tail.startswith(('bundle_u8_bank_r', 'bundle_meta_bank_r', 'g_bundle_row[')):
            return 'frontend/bundle_payload_and_local_write'
        if tail.startswith(('input_buffer_row_r', 'g_input_capture[')):
            return 'frontend/S24_capture_and_local_enable'
        return 'frontend/other_control_and_glue'
    if name.startswith(TENSOR):
        tail = name[len(TENSOR):]
        if tail.startswith('g_input_beat_bank['):
            return 'tensor/input_beat_banks'
        if tail.startswith(('input_beat_r', 'input_group_r', 'input_group_valid_r',
                            'input_beat_count', 'input_group_count')):
            return 'tensor/input_control_and_counters'
        return 'tensor/other'
    return None


def selected(group):
    return (group.startswith('frontend/') and group not in {
        'frontend/u_cache0', 'frontend/u_cache1', 'frontend/bundle_payload_and_local_write'
    }) or group in {'tensor/input_beat_banks', 'tensor/input_control_and_counters'}


def main():
    receipts = list(csv.DictReader((REPORT/'query_receipts.tsv').open(), delimiter='\t'))
    closure = [r for r in receipts if r['query'] == 'complete_exclusive_ownership']
    assert len(closure) == 1 and closure[0]['native_tcl_code'] == '0'
    source = REPORT/'all_primitive_locations.tsv'
    prior = json.loads((OUT/'closed_primitive_ownership_review.json').read_text())
    assert source.stat().st_size == prior['source']['bytes']
    metrics = collections.defaultdict(collections.Counter)
    refs = collections.defaultdict(collections.Counter)
    sites = collections.defaultdict(set)
    dsps = collections.defaultdict(set)
    names = collections.defaultdict(list)
    candidate_names = []
    candidate_sites = collections.defaultdict(set)
    all_site_groups = collections.defaultdict(set)
    complete_site_membership = collections.defaultdict(set)
    input_tensor_indices, input_front_indices = set(), set()
    with source.open() as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            name, ref, loc, slr = (row[k] for k in ['cell','REF_NAME','LOC','SLR'])
            group = classify(name)
            if loc.startswith('SLICE_'):
                complete_site_membership[(slr,loc)].add('candidate' if group and selected(group) else 'other')
            if not group:
                continue
            key = (group, slr)
            m = metrics[key]
            m['primitive_count'] += 1
            refs[key][ref] += 1
            names[key].append(name)
            if re.fullmatch(r'LUT[1-6](?:_2)?', ref):
                m['logic_LUT_primitives_not_native_LUT_total'] += 1
            if ref.startswith(('FD','LD')) and loc.startswith('SLICE_'):
                m['CLB_FF_latch_primitives'] += 1
            if ref.startswith(('RAMB36','FIFO36')):
                m['BRAM_36K_equivalent'] += 1
            if ref.startswith(('RAMB18','FIFO18')):
                m['BRAM_36K_equivalent'] += .5
            if ref.startswith('URAM'):
                m['URAM_primitives'] += 1
            if ref.startswith('DSP') and loc:
                dsps[key].add(loc)
            if loc.startswith('SLICE_'):
                sites[key].add(loc)
                all_site_groups[(slr,loc)].add('candidate' if selected(group) else 'retained')
            if selected(group):
                candidate_names.append(name)
                if loc:
                    candidate_sites[slr].add(loc)
            match = re.fullmatch(re.escape(TENSOR) + r'g_input_beat_bank\[(\d+)\]\.input_group_beat_r_reg\[(\d+)\]\[(\d+)\]', name)
            if match:
                a,b,c = map(int, match.groups())
                assert a == b and ref.startswith(('FD','LD')) and slr == 'SLR1'
                input_tensor_indices.add((b,c))
            match = re.fullmatch(re.escape(FRONT) + r'input_buffer_row_r_reg\[(\d+)\]\[(\d+)\]', name)
            if match:
                a,b = map(int, match.groups())
                assert ref.startswith(('FD','LD')) and slr == 'SLR1'
                input_front_indices.add((a,b))
    assert input_tensor_indices == {(a,b) for a in range(48) for b in range(256)}
    assert input_front_indices == {(a,b) for a in range(16) for b in range(768)}
    group_records = []
    candidate_totals = collections.defaultdict(collections.Counter)
    candidate_dsp_sites = collections.defaultdict(set)
    for (g,s),m in sorted(metrics.items()):
        m['unique_DSP_sites'] = len(dsps[(g,s)])
        m['touched_SLICE_sites_nonadditive'] = len(sites[(g,s)])
        group_records.append(dict(group=g,SLR=s,selected=selected(g),metrics=dict(m),
                                  REF_counts=dict(refs[(g,s)]),
                                  exact_sorted_cell_names_sha256=hashlib.sha256(('\n'.join(sorted(names[(g,s)]))+'\n').encode()).hexdigest(),
                                  first_names=sorted(names[(g,s)])[:3]))
        if selected(g):
            candidate_totals[s].update({k:v for k,v in m.items() if k not in {'unique_DSP_sites','touched_SLICE_sites_nonadditive'}})
            candidate_dsp_sites[s].update(dsps[(g,s)])
    for s,m in candidate_totals.items():
        m['unique_DSP_sites'] = len(candidate_dsp_sites[s])
        m['unique_touched_SLICE_sites'] = sum(loc.startswith('SLICE_') for loc in candidate_sites[s])
        m['SLICE_sites_shared_with_retained_frontend_or_tensor'] = sum(a==s and len(gs)>1 for (a,_),gs in all_site_groups.items())
        m['SLICE_sites_with_candidate_and_any_other_primitive'] = sum(a==s and gs=={'candidate','other'} for (a,_),gs in complete_site_membership.items())
        m['SLICE_sites_currently_only_candidate_primitives'] = sum(a==s and gs=={'candidate'} for (a,_),gs in complete_site_membership.items())
    freeze_path = ROOT/'project/E005_m002_optimized_implementation/experiment_source/frozen_inputs_before_current_CDC_recovery.json'
    freeze = json.loads(freeze_path.read_text())
    frozen = {f['path']:f for f in freeze['files']}
    evidence_specs = {
        'rtl/mlp/hap_mlp_input_frontend16_compact_cache.sv': [(3,36),(43,75),(92,140),(180,240),(247,306)],
        'rtl/mlp/hap_mlp_hadamard32_s24_fold4.sv': [(3,40)],
        'rtl/mlp/hap_mlp_full_command16_v5_s54.sv': [(191,240)],
        'rtl/mlp/hap_mlp_serial_ddr_command16_v5_s54.sv': [(322,365),(388,400),(433,453),(492,520)],
        'rtl/mlp/hap_mlp_gate_up_v5_scheduler16_q4.sv': [(242,280)],
        'rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s54.sv': [(93,141),(158,208)],
        'rtl/integration/hap_mlp_tensor_dma_bridge.sv': [(3,39),(49,81),(88,137),(246,264)],
        'rtl/integration/hap_attention_mlp_production_core.sv': [(214,262)],
        'rtl/integration/hap_attention_mlp_resource_top.sv': [(153,162)],
    }
    source_records = []
    for rel,ranges in evidence_specs.items():
        p = ROOT/'project/hardware'/rel
        ident = identity(p)
        f = frozen[str(p)]
        assert ident['bytes'] == f['bytes'] and ident['sha256'] == f['sha256']
        lines = p.read_text().splitlines()
        source_records.append(dict(**ident,freeze_match=True,
          evidence=[dict(start_line=a,end_line=b,lines=[dict(line=i,text=lines[i-1]) for i in range(a,b+1)]) for a,b in ranges]))
    payload = dict(created_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
      execution='CPU subset/source audit completed; native candidate endpoint coverage pending',
      verdict='candidate physical-locality hypothesis only; not implemented or timing/routing-qualified',
      applicability='E005 original physopt NAME export and original 144-input RTL freeze',
      review='prepared for controller; no user acceptance implied',
      closure=closure[0],primitive_source_identity_from_prior_full_audit=prior['source'],
      prior_full_audit=identity(OUT/'closed_primitive_ownership_review.json'),
      freeze=identity(freeze_path),sources=source_records,
      selector=dict(frontend_root=FRONT[:-1],
        frontend_inclusion='all primitive descendants of exact frontend root',
        frontend_exclusions=['u_cache0/ descendants','u_cache1/ descendants',
          'root-relative cell name starts bundle_u8_bank_r, bundle_meta_bank_r, or g_bundle_row['],
        tensor_root=TENSOR[:-1],tensor_inclusion_prefixes=['g_input_beat_bank[','input_beat_r','input_group_r','input_group_valid_r','input_beat_count','input_group_count'],
        rules='literal prefix comparisons implemented in this audit; no wildcard interpretation of brackets',
        matched_primitive_count=len(candidate_names),
        exact_sorted_cell_names_sha256=hashlib.sha256(('\n'.join(sorted(candidate_names))+'\n').encode()).hexdigest()),
      exact_input_payload_indices=dict(tensor_complete_48x256=len(input_tensor_indices),frontend_complete_16x768=len(input_front_indices)),
      groups=group_records,candidate_SLR_metrics=dict(candidate_totals),
      interface_budget_bits=dict(original_frontend_input_S24=12288,original_cache_response_payload=4480,
        proposed_DMA_read_payload_into_group=256,proposed_quantizer_payload_out=4*(32*8+24),
        retained_tensor_output_payload=8192,retained_bundle_to_cache_payload=4480,
        retained_cache_to_gate_payload=4480),
      limits=['LUT primitive counts are not native CLB LUT totals; no summation with inclusive report LUT totals.',
        'Payload bit widths are source interface budgets, not physical nets, active bits, leaf endpoints, SLL usage or traffic.',
        'Current candidate-site occupancy does not predict sites freed or destination packing; other owners can share those sites.',
        'Exact current physopt NAME selectors require native re-resolution and semantic preflight on any earlier OPT checkpoint.',
        'Controller will decide next optimization contract after required E006 hotspot and endpoint evidence closes.'])
    target = OUT/'input_frontend_locality_candidate_facts.json'
    target.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(output=identity(target),selector=payload['selector'],candidate_SLR_metrics=payload['candidate_SLR_metrics'],groups=[dict(group=g['group'],SLR=g['SLR'],selected=g['selected'],metrics=g['metrics']) for g in group_records]),ensure_ascii=False))


if __name__ == '__main__':
    main()
