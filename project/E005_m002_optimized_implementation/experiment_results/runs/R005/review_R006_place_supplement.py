"""Independent aggregate/native evidence review, with no EDA or DCP reads."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter,defaultdict
import csv,hashlib,json,re
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT=Path(__file__).parent
AT=ROOT/'project/E005_m002_optimized_implementation/experiment_results/runs/R006/attempts/AT002_closed_place_physopt_readonly'
MASTER=ROOT/'project/hardware/vivado/reports/m002_E005_R006_AT002_closed_place_physopt_readonly'
P=MASTER/'place'
checks=[]
def ident(path,expected=None):
    assert path.suffix!='.dcp'
    data=path.read_bytes();r={'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    if expected:
        assert r['bytes']==expected['bytes'] and r['sha256']==expected['sha256'],path
        r['matched']=True
    checks.append(r);return r
def rows(path):
    with path.open() as f:return list(csv.DictReader(f,delimiter='\t'))
def hist(value):
    words=value.split();assert len(words)%2==0
    result={words[i]:int(words[i+1]) for i in range(0,len(words),2)}
    assert len(result)*2==len(words)
    return result
def single(value):
    if value.startswith('{') and value.endswith('}'):value=value[1:-1]
    assert ' ' not in value
    return value
summary_path=AT/'place_readonly_closed_phase_summary.json'
ident(summary_path,{'bytes':4250,'sha256':'ff04992de5c21e578068ccdb5e829689c5ab5ee59dc439af7eb241755ddf8d7e'})
summary=json.loads(summary_path.read_text());fp=Path(summary['full_facts']['path']);ident(fp,summary['full_facts']);facts=json.loads(fp.read_text())
for key in ('producer','input_bindings','result_and_options'):ident(Path(facts[key]['path']),facts[key])
for r in facts['actual_archived_query_sources_unchanged']+facts['artifacts']:ident(Path(r['path']),r)
original_dcp=facts['original_checkpoint_rehashed_unchanged']
assert original_dcp['sha256']=='32b4af05f2ba43c8f63ec8ee44f7fcd40dbc1d6f5012638d404bb0cb6678bdf2'
assert Path(original_dcp['path']).stat().st_size==original_dcp['bytes']==579966904
phase_rows=rows(MASTER/'phase_receipts.tsv');place_phase=next(r for r in phase_rows if r['phase']=='place')
assert place_phase==facts['phase_receipt'] and place_phase['native_tcl_code']=='0'
assert (MASTER/'place_result_and_options.txt').read_text()=='result {} options {-code 0 -level 0}\n'
queries=rows(P/'query_receipts.tsv');assert len(queries)==60 and all(r['native_tcl_code']=='0' for r in queries)
assert {r['query'] for r in queries if re.fullmatch(r'fixed_native_window_\d+',r['query'])}=={f'fixed_native_window_{i}' for i in range(48)}
rawloads=rows(P/'target_net_loads.tsv');boundaries=rows(P/'boundary_drivers.tsv');positions=rows(P/'target_net_position_envelopes.tsv');mapping=rows(P/'placed_reference_site_SLR_mapping.tsv')
assert len(rawloads)==94 and len(boundaries)==80 and len(positions)==97 and len(mapping)==56
raw_by_net={r['net']:r for r in rawloads};assert len(raw_by_net)==94
pos_by_net=defaultdict(list)
for pos in positions:pos_by_net[pos['net']].append(pos)
group_totals={};normalized=[]
for raw in rawloads:
    roles=raw['roles'];matches=[g for g in ('input','gate','down') if f'boundary:{g}:' in roles]
    group=matches[0] if matches else 'upstream';assert len(matches)<=1
    if not matches:assert roles=='upstream'
    driver=single(raw['driver_cells']);dloc=single(raw['driver_LOCs']);dslr=single(raw['driver_SLRs']);dref=single(raw['driver_REF_NAMEs'])
    assert raw['source_resolution']=='SINGLE_PLACED_DRIVER' and dslr in {'SLR0','SLR1','SLR2'}
    pins,unique=int(raw['leaf_load_pin_count']),int(raw['unique_load_cell_count'])
    loadslr=hist(raw['load_SLR_pin_counts']);refs=hist(raw['load_REF_pin_counts']);urefs=hist(raw['load_REF_unique_cell_counts']);terms=hist(raw['load_terminal_counts'])
    assert sum(loadslr.values())==sum(refs.values())==sum(terms.values())==pins
    assert sum(urefs.values())==unique==pins
    assert set(loadslr)<= {'SLR0','SLR1','SLR2'}
    cross=pins-loadslr.get(dslr,0);assert cross==int(raw['source_relative_cross_SLR_pin_count'])
    if group!='upstream':
        count,ref=(256,'FDCE') if group=='input' else ((384,'FDRE') if group=='gate' else (512,'FDRE'))
        assert pins==count and refs=={ref:count} and terms=={'CE':count}
    pp=pos_by_net[raw['net']];assert len(pp)==len(loadslr)
    for p in pp:
        assert int(p['leaf_load_pins'])==loadslr[p['SLR']]
        assert int(p['nonSLICE_or_unplaced_pins'])==0 and int(p['SLICE_pins'])==int(p['leaf_load_pins'])
        assert int(p['SLICE_Xmin'])<=int(p['SLICE_Xmax']) and int(p['SLICE_Ymin'])<=int(p['SLICE_Ymax'])
    row={'net':raw['net'],'group':group,'driver_cells':[driver],'driver_REF':dref,'driver_LOCs':[dloc],'driver_SLR':dslr,
         'leaf_load_pins':pins,'unique_load_cells':unique,'cross_SLR_leaf_load_pins':cross,'load_SLR_pin_counts':loadslr,
         'load_REF_pin_counts':refs,'load_terminal_counts':terms,'position_envelopes':pp}
    normalized.append(row)
    total=group_totals.setdefault(group,{'nets':0,'leaf_load_pins':0,'unique_load_cells_summed_per_net':0,
        'cross_SLR_leaf_load_pins':0,'load_SLR_pin_counts':Counter(),'driver_SLR_counts':Counter(),'driver_REF_counts':Counter()})
    total['nets']+=1;total['leaf_load_pins']+=pins;total['unique_load_cells_summed_per_net']+=unique;total['cross_SLR_leaf_load_pins']+=cross
    total['load_SLR_pin_counts'].update(loadslr);total['driver_SLR_counts'][dslr]+=1;total['driver_REF_counts'][dref]+=1
assert normalized==facts['per_net_loads']
assert group_totals==facts['load_groups']==summary['load_groups']
assert Counter(r['REF_NAME'] for r in boundaries)==facts['boundary_REF_counts']

prior=ROOT/'project/hardware/vivado/reports/m002_E005_R004_AT003_current_CDC_bound_OPT_place_physopt'
old_boundaries=rows(prior/'optimized_boundaries_place.tsv');old_by_cell={r['cell']:r for r in old_boundaries}
ident(prior/'optimized_boundaries_place.tsv');ident(prior/'optimized_control_sources_place.tsv')
for r in boundaries:
    old=old_by_cell[r['cell']]
    for newkey,oldkey in [('scope','scope'),('REF_NAME','REF_NAME'),('INIT','INIT'),('DONT_TOUCH','DONT_TOUCH'),('LOC','driver_LOC'),('BEL','driver_BEL')]:assert r[newkey]==old[oldkey]
    targets=[n for n in normalized if n['driver_cells']==[r['cell']] and n['group']==r['scope']];assert len(targets)==1
    n=targets[0];assert n['driver_SLR']==r['SLR'] and n['leaf_load_pins']==int(old['leaf_input_pins'])
    assert n['load_REF_pin_counts']==hist(old['load_REF_counts']) and n['load_terminal_counts']==hist(old['load_pin_counts']) and n['load_SLR_pin_counts']==hist(old['load_SLR_counts'])
    allp=n['position_envelopes'];bounds=[min(int(p['SLICE_Xmin']) for p in allp),min(int(p['SLICE_Ymin']) for p in allp),max(int(p['SLICE_Xmax']) for p in allp),max(int(p['SLICE_Ymax']) for p in allp)]
    assert bounds==[int(v) for v in old['load_slice_XY_bounds'].split()]
for old in rows(prior/'optimized_control_sources_place.tsv'):
    new=raw_by_net[old['net']];assert new['roles']=='upstream'
    assert int(old['leaf_input_pins'])==int(new['leaf_load_pin_count']) and hist(old['load_REF_counts'])==hist(new['load_REF_pin_counts']) and hist(old['load_pin_counts'])==hist(new['load_terminal_counts'])
    assert single(old['drivers'])==single(new['driver_pins']) and single(old['driver_LOCs'])==single(new['driver_LOCs'])
placed_ref_path=OUT/'AT003_placed_driver_sites_for_device_mapping.json';ident(placed_ref_path);placedref=json.loads(placed_ref_path.read_text())
map_by_loc={r['placed_reference_LOC']:r for r in mapping};assert set(map_by_loc)==set(placedref['unique_sites'])
for r in mapping:
    assert r['placed_reference_LOC']==r['actual_site_NAME'] and r['device_SLR'] in {'SLR0','SLR1','SLR2'} and r['phase_context']=='place'
    assert r['scope']=='device_mapping_of_original_placed_LOC_not_replaced_by_current_driver_LOC'
for n in normalized:assert map_by_loc[n['driver_LOCs'][0]]['device_SLR']==n['driver_SLR']

oldwindows_path=OUT/'old_congestion_windows_reference.json';ident(oldwindows_path);oldwindows=json.loads(oldwindows_path.read_text())
windows=rows(P/'fixed_window_occupancy.tsv');connections=rows(P/'fixed_window_attached_connections.tsv')
assert len(windows)==len(connections)==48
priority=[]
for i,r in enumerate(windows):
    old=oldwindows['reference_rows'][i];assert int(r['reference_row'])==i
    assert (r['direction'],r['type'],r['old_level'])==(old['direction'],old['type'],old['level'])
    assert '('+r['native_endpoint_1']+','+r['native_endpoint_2']+')'==old['native_window']
    tile_names=(P/f'fixed_window_{i}_actual_tiles.txt').read_text().splitlines();assert len(tile_names)==len(set(tile_names))==int(r['tile_count'])
    assert r['native_endpoint_1'] in tile_names and r['native_endpoint_2'] in tile_names
    cap=hist(r['site_TYPE_capacity']);used=hist(r['occupied_site_TYPE_counts']);ref=hist(r['primitive_REF_counts']);slrs=hist(r['SLR_site_counts'])
    assert sum(cap.values())==sum(slrs.values())==int(r['site_count']) and sum(ref.values())==int(r['primitive_count'])
    assert all(v<=cap[k] for k,v in used.items()) and set(slrs)<= {'SLR0','SLR1','SLR2'}
    assert r['current_fixed_congestion_metric']=='UNAVAILABLE_NO_VALIDATED_FIXED_WINDOW_CONGESTION_API'
    conn=connections[i];assert int(conn['reference_row'])==i and conn['scope']=='attached_segments_only_not_boundary_crossings_or_congestion'
    for key in ('primitive_input_leaf_pins','primitive_output_leaf_pins','attached_hierarchical_net_segments'):assert int(conn[key])>=0
    if any(old['native_window']==p['native_window'] and old['direction']==p['direction'] and old['type']==p['type'] for p in oldwindows['priority_reference_windows']):
        priority.append({'reference_row':i,'direction':r['direction'],'type':r['type'],'native_window':old['native_window'],'old_level':old['level'],
            'grid_bounds':[int(r[k]) for k in ('actual_GRID_POINT_Xmin','actual_GRID_POINT_Ymin','actual_GRID_POINT_Xmax','actual_GRID_POINT_Ymax')],
            'tile_count':int(r['tile_count']),'site_count':int(r['site_count']),'primitive_count':int(r['primitive_count']),
            'occupied_SLICE_sites':used.get('SLICEL',0)+used.get('SLICEM',0),'available_SLICE_sites':cap.get('SLICEL',0)+cap.get('SLICEM',0),
            'URAM288_sites_used_capacity':[used.get('URAM288',0),cap.get('URAM288',0)],'DSP48E2_sites_used_capacity':[used.get('DSP48E2',0),cap.get('DSP48E2',0)],
            'SLR_site_counts':slrs,'attached_connections':conn,'current_fixed_congestion':r['current_fixed_congestion_metric']})
assert len(priority)==4

hier={}
for group in ('input','gate','down'):
    lines=(P/f'utilization_hierarchy_{group}.rpt').read_text().splitlines();header=None;table=[]
    for i,line in enumerate(lines):
        values=[v.strip() for v in line.split('|')[1:-1]]
        if values and values[0]=='Instance':header=values
        elif header and len(values)==len(header) and values[2].isdigit():
            table.append({'line':i+1,**{k:(int(v) if j>=2 else v) for j,(k,v) in enumerate(zip(header,values))}})
    assert table and table[0]['Instance']==table[1]['Instance']
    assert all(table[0][k]==table[1][k] for k in header)
    hier[group]={'summary':{k:table[0][k] for k in header},'rows':table,
        'scope':'Exact selected hierarchy, root summary repeats once; do not sum duplicated parent/child rows.'}
gate_cross=[{'row':int(r['net'].rsplit('_',1)[1]),'driver_LOC':r['driver_LOCs'][0],'driver_SLR':r['driver_SLR'],
    'load_SLR_pin_counts':r['load_SLR_pin_counts'],'cross_SLR_leaf_pins':r['cross_SLR_leaf_load_pins'],'positions':r['position_envelopes']}
    for r in normalized if r['group']=='gate' and r['cross_SLR_leaf_load_pins']]
gate_cross.sort(key=lambda r:r['row'])
spans={}
for group in ('input','gate','down'):
    ns=[r for r in normalized if r['group']==group];ps=[p for n in ns for p in n['position_envelopes']]
    spans[group]={'single_load_SLR_net_count':sum(len(n['load_SLR_pin_counts'])==1 for n in ns),
        'zero_source_relative_cross_SLR_net_count':sum(n['cross_SLR_leaf_load_pins']==0 for n in ns),
        'SLICE_coordinate_X_span_min_max':[min(int(p['SLICE_Xmax'])-int(p['SLICE_Xmin']) for p in ps),max(int(p['SLICE_Xmax'])-int(p['SLICE_Xmin']) for p in ps)],
        'SLICE_coordinate_Y_span_min_max':[min(int(p['SLICE_Ymax'])-int(p['SLICE_Ymin']) for p in ps),max(int(p['SLICE_Ymax'])-int(p['SLICE_Ymin']) for p in ps)]}
native=[];second_open=False
with (MASTER/'vivado.log').open() as handle:
    for line in handle:
        native.append(line)
        if line.startswith('Command: open_checkpoint ') and line.rstrip().endswith('/physopt.dcp'):
            second_open=True;break
assert second_open
assert any('E005_READONLY_PHASE_COMPLETED place native_tcl_code=0' in line for line in native)
snapshot=OUT/'R006_AT002_place_closed_then_physopt_open_native_prefix.txt'
with snapshot.open('x') as handle:handle.writelines(native)
record={'reviewed_at':datetime.now(timezone.utc).isoformat(),'identity_checks':checks,'native_phase_receipt':place_phase,'query_count':len(queries),
    'all_query_codes_zero':True,'native_phase_seconds':int(place_phase['ended_epoch'])-int(place_phase['started_epoch']),
    'phase_identity':facts['phase_identity'],'place_DCP_stat_and_engineering_rehash_binding_only':original_dcp,
    'all94_per_net_aggregate_rows_and97_position_rows_equal_engineering_facts':True,'load_groups_independently_recomputed':group_totals,
    'all80_boundary_fields_and14_upstream_prior_place_rows_match':True,'source_relative_cross_units':'unique leaf input pins per canonical connected net; not unique global cells, SLL wires or boundary crossings',
    'gate_crossing_rows':gate_cross,'upstream_crossing_rows':[r for r in normalized if r['group']=='upstream' and r['cross_SLR_leaf_load_pins']],
    'position_spans':spans,'placed_reference_LOC_mapping_count':56,'mapping_limit':'56 original E005 placed LOCs through same-part topology; not old E003 leaf/crossing baseline',
    'fixed48_original_windows_exactly_match':True,'fixed48_tile_lists_count_unique_endpoints_match':True,'fixed48_cap_used_ref_SLR_hist_consistent':True,
    'priority_fixed_windows':priority,'fixed_window_limits':['All48 current congestion fields UNAVAILABLE, never0 or old level reused.','Site counts and used distinct sites are not LUT utilization; BRAM alternative site types not additive BRAM blocks.','Primitive REF counts contain DSP subprimitives, not DSP block counts.','Attached hierarchical net segments are not global unique logical nets or region-crossing nets.','Windows overlap; no whole-device sum or unmeasured old resource delta.'],
    'hierarchical_utilization':hier,'native_prefix':ident(snapshot),'execution':'place readonly phase complete; native session and physopt phase continuing',
    'verdict':'Target structure retained and new source-relative locality/window-resource/hierarchy evidence supported; no timing/routability/signoff inference',
    'review':'A007 bounded read-only aggregate crosschecks and source inspection; no EDA/test/DCP read; session terminal/freezes/locks reviewed separately'}
target=OUT/'R006_AT002_place_supplement_review_evidence.json'
with target.open('x') as handle:json.dump(record,handle,ensure_ascii=False,indent=2);handle.write('\n')
print(json.dumps({'evidence':str(target.relative_to(ROOT)),'identity_checks':len(checks),'gate_crossing_rows':gate_cross,'position_spans':spans,'priority_windows':priority,'hierarchy':{k:v['summary'] for k,v in hier.items()}},indent=2))
