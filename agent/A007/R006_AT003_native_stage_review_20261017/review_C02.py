#!/usr/bin/env python3
"""Offline A007 review. No EDA, DCP read, process signal, or lock operation."""
import sys
sys.dont_write_bytecode = True
import json, hashlib, re
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone

ROOT = Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT = ROOT/'agent/A007/R006_AT003_native_stage_review_20261017'
ATT = ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R006/attempts/AT003_buffered_alias_directed_cut'
REP = ROOT/'project/hardware/vivado/reports/m002_E006_R006_AT003_buffered_alias_directed_cut'
sys.path.insert(0, str(ATT/'sources'))
import directed_evidence as de
import top_port_evidence as tp

def identity(path):
    path=Path(path).resolve()
    assert path.suffix.lower() != '.dcp', 'DCP content read forbidden'
    return de.identity(path)

checked={}
def verify_refs(x):
    if isinstance(x,dict):
        if {'path','bytes','sha256'} <= set(x):
            if Path(x['path']).suffix.lower() == '.dcp': return
            if x['path'] not in checked:
                got=identity(x['path']); assert got == {k:x[k] for k in got}, (x,got)
                checked[x['path']]=got
        else:
            for v in x.values(): verify_refs(v)
    elif isinstance(x,list):
        for v in x: verify_refs(v)

cf=json.loads((ATT/'candidate_C02_directed_cut_closed_facts.json').read_text())
tf=json.loads((ATT/'candidate_C02_bounded_timing_closed_facts.json').read_text())
for obj in [cf,tf]: verify_refs(obj)
bindings=json.loads((ATT/'input_bindings.json').read_text())
replay=OUT/'C02_actual_replay'
replay.mkdir(exist_ok=False)
for p in REP.glob('*C02*'):
    if p.name not in {'candidate_cut_summary_C02.json','candidate_timing_validation_C02.json'}:
        (replay/p.name).symlink_to(p)
original_validate=tp.validate
wrapper_checks=[]
def safe_validate(point,report,require_closed=True):
    result=original_validate(point,report,require_closed=False)
    closed=json.loads((report/f'candidate_top_port_index_closed_{point}.json').read_text())
    assert closed['qualified'] is True and not closed['issues']
    assert closed['point']==point and closed['epoch_id']==result['epoch_id']
    assert closed['sources']==[identity(p) for p in result['source_paths']]+[identity(tp.__file__)]
    assert closed['artifacts']==[identity(result['path']),identity(result['calls_path'])]
    assert closed['input_identity']==bindings['checkpoint']
    assert str(Path(result['input_path']).resolve())==bindings['checkpoint']['path']
    assert str(Path(de.split(result['epoch_id'])[3]).resolve())==bindings['checkpoint']['path']
    wrapper_checks.append(dict(requested_require_closed=require_closed,all_non_DCP_closed_checks=True,DCP_content_check_attributed_to_engineering=True))
    return result
tp.validate=safe_validate
cut=de.cut('C02',replay)
timing=de.timing('C02',replay)
assert cut==cf['native_result'], 'Actual cut replay differs'
assert timing==tf['native_result'], 'Actual timing replay differs'

nets=de.unique(REP/'candidate_nets_C02.tsv','canonical_net')
endpoints=defaultdict(list)
for row in de.rows(REP/'candidate_endpoints_C02.tsv'): endpoints[row['canonical_net']].append(row)
category_direction=Counter(); counts=Counter(); external=defaultdict(lambda:dict(pairs=0,nets=set(),external_cells=set(),pin_classes=Counter(),refs=Counter()))
ordinary_external=defaultdict(lambda:dict(pairs=0,nets=set(),external_cells=set(),pin_classes=Counter(),refs=Counter()))
pair_totals=Counter(); candidate_pairs=0; all_boundary=0
for net,rows in endpoints.items():
    drivers=[r for r in rows if r['role']=='DRIVER'];loads=[r for r in rows if r['role']=='LOAD']
    if len(drivers)!=1:continue
    driver=drivers[0]
    cat,_=de.category(nets[net]['actual_clocks'],{r['pin_class'] for r in rows})
    for load in loads:
        if not (de.inside(driver) or de.inside(load)): continue
        candidate_pairs+=1
        if de.inside(driver)==de.inside(load): continue
        all_boundary+=1
        direction='EGRESS' if de.inside(driver) else 'INGRESS'
        out=load if direction=='EGRESS' else driver
        category_direction[(direction,cat)]+=1
        positioned=driver['SLR'] in de.SLRS and load['SLR'] in de.SLRS
        moved_cross=positioned and (('SLR2' if de.inside(driver) else driver['SLR'])!=('SLR2' if de.inside(load) else load['SLR']))
        pair_totals['all_boundary']+=1
        pair_totals['positioned_boundary']+=positioned
        pair_totals['hypothetical_boundary_cross']+=moved_cross
        ordinary=cat not in {'clock','constant','reset_set'}
        if ordinary:
            pair_totals['ordinary_boundary']+=1
            pair_totals['ordinary_hypothetical_cross']+=moved_cross
            pair_totals[f'ordinary_{direction}']+=1
        cell=out['raw_cell'] or out['NAME']
        parent=cell.rsplit('/',1)[0]
        family=re.sub(r'\[\d+\]','[*]',parent).removeprefix('scalellm_vcu118_f05_bd_i/core/inst/u_core/')
        for table in ([external,ordinary_external] if ordinary else [external]):
            rec=table[(direction,family)]
            rec['pairs']+=1;rec['nets'].add(net);rec['external_cells'].add(cell);rec['pin_classes'][out['pin_class']]+=1;rec['refs'][out['REF_NAME']]+=1
assert candidate_pairs==cut['candidate_involved_driver_load_pairs']
assert all_boundary==cut['candidate_boundary_driver_load_pairs']
assert sum(v for k,v in category_direction.items())==19325
def family_rows(table):
    return [dict(direction=k[0],external_parent_family=k[1],pairs=v['pairs'],unique_nets=len(v['nets']),unique_external_cells=len(v['external_cells']),external_pin_classes=dict(v['pin_classes']),external_REF_NAME=dict(v['refs'])) for k,v in sorted(table.items(),key=lambda kv:(-kv[1]['pairs'],kv[0]))]

timing_rows=list(de.rows(REP/'candidate_scoped_timing_C02.tsv'))
worst=[]
for direction in ['INGRESS','EGRESS']:
    for delay in ['max','min']:
        subset=[r for r in timing_rows if (r['direction'],r['delay_type'])==(direction,delay)]
        row=min(subset,key=lambda r:float(r['SLACK']))
        rpt=REP/f'candidate_cut_timing_C02_{direction}_{delay}.rpt'
        excerpts=[];seen=False
        with rpt.open() as f:
            for line in f:
                stripped=line.strip()
                if stripped.startswith('Slack '):
                    if seen: break
                    seen=True
                if seen and any(stripped.startswith(prefix) for prefix in ['Slack ','Source:','Destination:','Path Type:','Requirement:','Data Path Delay:','Clock Path Skew:']):
                    excerpts.append(line.rstrip()[:1500])
        assert len(excerpts)==7
        worst.append(dict(direction=direction,delay_type=delay,worst=row,report_first_path=excerpts,actual_report=identity(rpt)))

result=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),execution='completed_independent_C02_actual_cut_and_timing_review',verdict='supported_complete_directed_cut_and_bounded_timing_on_original_physopt_graph',applicability='R006 AT003 C02 original E005 physopt; not relocated or postroute',review='accepted_candidate_evidence; selection recorded separately',facts=[identity(ATT/n) for n in ['candidate_C02_directed_cut_closed_facts.json','candidate_C02_bounded_timing_closed_facts.json']],actual_archived_cut_replay_exact_equal=True,actual_archived_timing_replay_exact_equal=True,identity_checks=list(checked.values()),replay_outputs=[identity(replay/n) for n in ['candidate_cut_summary_C02.json','candidate_timing_validation_C02.json']],DCP_safe_replay_adjustment=dict(checks=wrapper_checks,description='Unmodified archived cut/join/timing algorithms. Reviewer-only wrapper uses require_closed=False then independently repeats closed point/epoch/source/artifact/input binding checks. DCP content fingerprint attributed to engineering; reviewer did not read/hash DCP.'),counts={k:cut[k] for k in ['canonical_nets','actual_candidate_native_leaf_pins','retained_endpoint_rows','scope_modes','boundary_directions','candidate_involved_driver_load_pairs','candidate_boundary_driver_load_pairs','timing_scope_rows','unknown_top_or_unplaced_pair_positions']},pair_totals=dict(pair_totals),category_by_direction=[dict(direction=k[0],category=k[1],pairs=v) for k,v in sorted(category_direction.items())],all_boundary_external_families=family_rows(external),ordinary_boundary_external_families=family_rows(ordinary_external),failure_sample_relation=cut['original_failure_sample_alias_relation'],directional_timing_scope={k:len(v) for k,v in timing['query_sets'].items()},worst_paths=worst,timing_interpretation='-through complete boundary LOAD sets. Full path endpoints can both be outside or internal; bounded paths may traverse multiple cut loads. Four max/min cap16 nworst1 sets do not measure full cut TNS.',no_EDA_DCP_signal_or_lock_control=True)
with (OUT/'C02_cut_timing_review.json').open('x') as f:json.dump(result,f,indent=2,ensure_ascii=False);f.write('\n')
print(json.dumps(dict(review=identity(OUT/'C02_cut_timing_review.json'),identities=len(checked),pair_totals=result['pair_totals'],category_by_direction=result['category_by_direction'],ordinary_external_families=result['ordinary_boundary_external_families'][:20],worst_paths=worst),indent=2))
