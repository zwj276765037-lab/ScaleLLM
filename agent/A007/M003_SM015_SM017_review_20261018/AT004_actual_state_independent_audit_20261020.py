"""A007 bounded, read-only reconstruction. No owner proof code or EDA execution."""
from pathlib import Path
import collections
import datetime
import hashlib
import json
import re

ROOT = Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
SRC = ROOT / 'project/E011_m003_joint_routability_implementation/experiment_source/place_write_replica_proof'
REPORT = ROOT / 'project/hardware/vivado/reports/m003_E011_R003_AT004_cached_place_write_replica_proof'
ATT = ROOT / 'project/E011_m003_joint_routability_implementation/experiment_results/runs/R003/attempts/AT004_cached_place_write_replica_proof/evidence'
OUT = ROOT / 'agent/A007/M003_SM015_SM017_review_20261018'
identities = {}
def read(path):
    path = Path(path)
    data = path.read_bytes()
    identities[str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)] = dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    return data

def doc(path):
    return json.loads(read(path))

def lines(path):
    return [json.loads(line) for line in read(path).splitlines()]

def names(value):
    assert isinstance(value, str)
    result=[]
    for value in value.split():
        if value.startswith('{'):
            assert value.endswith('}')
            value=value[1:-1]
        assert '{' not in value and '}' not in value
        result.append(value)
    return result

def signal(row):
    return {key: sorted(names(row[key])) for key in ['nets','drivers','driver_cells','driver_refs','primary_ports','primary_port_directions']}

package = doc(SRC / 'query_package_AT004_cached.json')
rows = lines(REPORT / 'selected_state_and_root_pins.jsonl')
groups_l = lines(REPORT / 'grouped_native_sources.jsonl')
bindings_l = lines(REPORT / 'grouped_native_pin_bindings.jsonl')
trace = lines(REPORT / 'grouped_API_trace.jsonl')
api_text = read(REPORT / 'grouped_API_counts.tcldict').decode()
counts = dict(collections.Counter(row['kind'] for row in rows))
assert len(rows)==108 and counts=={'cell':12,'parent':12,'state_pin':48,'state_clock':12,'memory_root_pin':24}
cells = {r['NAME']:r for r in rows if r['kind']=='cell'}
parents = {r['cell']:r for r in rows if r['kind']=='parent'}
clocks = {r['cell']:r for r in rows if r['kind']=='state_clock'}
pins = {(r['cell'],r['terminal']):r for r in rows if r['kind']=='state_pin'}
roots = {(r['cell'],r['terminal']):r for r in rows if r['kind']=='memory_root_pin'}
selected = set(package['selection_cells'])
assert len(selected)==12 and set(cells)==set(parents)==set(clocks)==selected
assert set(pins)=={(c,p) for c in selected for p in ['D','C','CE','CLR']}
assert len(roots)==24 and set(roots)=={tuple(p) for p in package['selection_root_pins']}
assert len(cells)==len(parents)==len(clocks)==12 and len(pins)==48
endpoints={r['pin']:r for r in [*pins.values(),*roots.values()]}
groups={r['id']:r for r in groups_l}
bindings={r['pin']:r for r in bindings_l}
assert len(groups_l)==len(groups)==15 and len(bindings_l)==len(bindings)==72
assert set(endpoints)==set(bindings)
net_union=set()
group_facts=[]
for group in groups.values():
    nets=group['nets']
    assert len(nets)==len(set(nets)) and nets
    assert group['canonical_top_net'] in nets
    assert not net_union.intersection(nets)
    net_union.update(nets)
    assert len(group['leaf_drivers'])==len(group['driver_cells'])==len(group['driver_refs'])==1
    assert group['leaf_drivers'][0].rsplit('/',1)[0]==group['driver_cells'][0]
    assert group['primary_ports']==group['primary_port_directions']==[]
    use=[b for b in bindings.values() if b['group']==group['id']]
    assert use
    group_facts.append(dict(id=group['id'],native_net_count=len(nets),endpoint_count=len(use),canonical_top_net=group['canonical_top_net'],leaf_drivers=group['leaf_drivers'],driver_refs=group['driver_refs']))
for endpoint,b in bindings.items():
    group=groups[b['group']]
    assert b['direct_nets'] and len(b['direct_nets'])==len(set(b['direct_nets']))
    assert set(b['direct_nets']).issubset(group['nets'])
    row=endpoints[endpoint]
    assert row['pin']==row['cell']+'/'+row['terminal'] and row['REF_PIN_NAME']==row['terminal'] and row['DIRECTION']=='IN'
    actual=signal(row)
    for key in ['nets','driver_cells','driver_refs','primary_ports','primary_port_directions']:
        assert actual[key]==sorted(group[key]), (endpoint,key)
    assert actual['drivers']==group['leaf_drivers']
    assert len(names(row['nets']))==len(set(names(row['nets'])))
assert trace[0]['event']=='call_begin' and trace[-1]['event']=='call_complete'
assert trace[0]['phase']=='placed_write_replica_proof' and trace[0]['design']=='checkpoint_place' and trace[0]['token']=='1'
assert int(trace[-1]['endpoints'])==72 and int(trace[-1]['groups'])==15
starts=[r for r in trace if r['event']=='api_begin']; ends=[r for r in trace if r['event']=='api_end']
assert len(starts)==len(ends)==90 and all(r['return_code']=='0' for r in ends)
assert [(r['api'],r['input_objects']) for r in starts]==[(r['api'],r['input_objects']) for r in ends]
members=[r for r in trace if r['event']=='segment_membership']
assert len(members)==15
member_groups=set()
for r in members:
    b=bindings[r['pin']];g=groups[b['group']];member_groups.add(g['id'])
    assert r['actual_direct_member']=='1' and r['direct_name_match_count']=='1' and r['direct_class']=='net'
    assert r['direct_name']==r['direct_object'] and r['direct_name'] in b['direct_nets']
    assert int(r['segment_count'])==int(r['object_unique_count'])==len(g['nets'])
assert member_groups==set(groups)
complete=[r for r in trace if r['event']=='group_source_complete']
assert len(complete)==15 and {r['group'] for r in complete}==set(groups)
for r in complete:
    g=groups[r['group']]
    assert int(r['net_count'])==len(g['nets']) and r['driver_count']=='1' and r['port_count']=='0'

originals={int(re.fullmatch(r'.*/artifact_index_r_reg\[(10|11|12)\]',c)[1]):c for c in selected if '_replica_' not in c}
assert set(originals)=={10,11,12}
pairs=[]
state_summaries=[]
all_locations=[]
for cell in sorted(selected):
    c=cells[cell];parent=parents[cell];clock=clocks[cell]
    assert c['REF_NAME']=='FDCE' and c['IS_PRIMITIVE']==c['IS_SEQUENTIAL']=='1' and c['INIT']=="1'b0"
    assert c['IS_C_INVERTED']==c['IS_D_INVERTED']==c['DONT_TOUCH']==''
    assert c['IS_CLR_INVERTED']=="1'b1" and c['IS_CE_INVERTED']=='NOT_SUPPORTED'
    assert parent['NAME']==cell.rsplit('/',1)[0] and parent['DONT_TOUCH']=='' and parent['REF_NAME'] not in ['', 'NOT_SUPPORTED']
    assert clock['NAME']==clock['clock']=='clk_out1_scalellm_vcu118_f05_bd_clk_core_0'
    assert float(clock['PERIOD'])==10 and [float(x) for x in names(clock['WAVEFORM'])]==[0,5]
    assert clock['IS_GENERATED']=='1' and clock['MASTER_CLOCK']=='xdma_0_axi_aclk'
    assert clock['SOURCE_PINS']=='scalellm_vcu118_f05_bd_i/clk_core/inst/mmcme4_adv_inst/CLKOUT0'
    by_pin={terminal:bindings[pins[cell,terminal]['pin']]['group'] for terminal in ['D','C','CE','CLR']}
    for terminal,polarity in [('D','0'),('C','0'),('CE','0'),('CLR','1')]:
        assert pins[cell,terminal]['IS_INVERTED']==polarity
    all_locations.append((c['LOC'],c['BEL']))
    state_summaries.append(dict(cell=cell,primitive='FDCE',INIT=c['INIT'],actual_pin_polarities={t:pins[cell,t]['IS_INVERTED'] for t in ['D','C','CE','CLR']},native_groups=by_pin,LOC=c['LOC'],BEL=c['BEL']))
    if cell in originals.values():continue
    match=re.fullmatch(r'(.*/artifact_index_r_reg\[(10|11|12)\])_replica_([1-9][0-9]*)',cell)
    assert match and match[1]==originals[int(match[2])]
    original=match[1]
    # Names select a pair only; all acceptance conditions below use actual native facts.
    assert {k:v for k,v in clock.items() if k!='cell'}=={k:v for k,v in clocks[original].items() if k!='cell'}
    assert {k:v for k,v in parent.items() if k!='cell'}=={k:v for k,v in parents[original].items() if k!='cell'}
    for prop in ['REF_NAME','INIT','IS_C_INVERTED','IS_CLR_INVERTED','IS_D_INVERTED','IS_CE_INVERTED']:
        assert c[prop]==cells[original][prop]
    for terminal in ['D','C','CE','CLR']:
        assert signal(pins[cell,terminal])==signal(pins[original,terminal])
        assert pins[cell,terminal]['IS_INVERTED']==pins[original,terminal]['IS_INVERTED']
        assert by_pin[terminal]==bindings[pins[original,terminal]['pin']]['group']
    pairs.append(dict(original=original,replica=cell,bit=int(match[2]),native_groups=by_pin,all_input_sets_and_sources_equal=True,INIT_and_effective_polarity_equal=True,clock_object_and_edges_equal=True))
assert len(pairs)==9 and len(set(all_locations))==12
assert {p['replica'].rsplit('_replica_',1)[1] for p in pairs if p['bit']==10}=={'1','3','4'}
assert all({p['replica'].rsplit('_replica_',1)[1] for p in pairs if p['bit']==b}=={'1','2','4'} for b in [11,12])
previous_path=OUT/'R003_AT001_write_address_delta_independent_review_20261020.json'
previous=doc(previous_path)
assert identities[str(previous_path.relative_to(ROOT))]['sha256']=='e7cba51b8279932077baedc4920b66a5323a4514b70e5d528b8aeb333cc3defa'
prior_changed={(r['cell'],r['pin']):r for r in previous['review']['changed_rows']}
assert set(prior_changed)==set(roots)
root_facts=[]
pairmap={p['replica']:p['original'] for p in pairs}
for key,row in roots.items():
    prior=prior_changed[key]
    assert signal(row)==signal(prior['actual'])
    assert row['IS_INVERTED']=='0'
    driver=names(row['drivers'])[0];replica=driver.rsplit('/',1)[0]
    assert names(row['driver_refs'])==['FDCE'] and driver==replica+'/Q' and replica in pairmap
    bit=int(re.fullmatch(r'ADDR_B\[(10|11|12)\]',row['terminal'])[1])
    assert pairmap[replica]==originals[bit]
    assert names(prior['prior']['drivers'])==[originals[bit]+'/Q']
    assert names(prior['actual']['startpoints'])==[replica+'/C']
    root_facts.append(dict(cell=key[0],pin=key[1],bit=bit,actual_driver=driver,original_state=originals[bit]+'/Q',native_group=bindings[row['pin']]['group'],actual_pin_inverted=0))
assert collections.Counter(r['bit'] for r in root_facts)=={10:8,11:8,12:8}

proof=doc(ATT/'actual_same_state_equivalence.json')
requal=doc(ATT/'actual_complete_place_structure_requalified.json')
assert proof==requal['physical_state_equivalence'] and proof['passed'] is True
assert proof['raw_native_source']['sha256']==identities[str((REPORT/'selected_state_and_root_pins.jsonl').relative_to(ROOT))]['sha256']
assert {(r['original'],r['replica']) for r in proof['state_pairs']}=={(r['original'],r['replica']) for r in pairs}
assert {(r['cell'],r['pin'],r['bit'],r['actual_driver'],r['original_state']) for r in proof['affected_root_bindings']}=={(r['cell'],r['pin'],r['bit'],r['actual_driver'],r['original_state']) for r in root_facts}
assert requal['passed'] is True and requal['errors']==[] and requal['fixture'] is False and requal['phase']=='place'
assert requal['original_full_function_evaluation_retained'] is True and requal['raw_snapshot_unchanged'] is True
assert [requal[k] for k in ['exact_new_M2_LUT1','exact_new_address_FF','exact_helper_LUT','exact_helper_CARRY8','protected_added_LUT']]==[81,34,40,4,85]
assert requal['URAM_per_slice']=={'0':40,'1':40} and requal['actual_address_root_counts']=={'0':6,'1':6}
assert requal['normalized_cell_literals']==17 and len(requal['raw_reset_endpoint_observations'])==51
assert proof['identity_bindings_verified'] is True
large_not_reread=[]
for binding in package['bindings']:
    p=Path(binding['path'])
    if p.name in ['place.dcp','m003_native_place.json']:
        assert p.stat().st_size==binding['bytes']
        key='checkpoint' if p.name=='place.dcp' else 'actual_snapshot'
        assert proof[key]['bytes']==binding['bytes'] and proof[key]['sha256']==binding['sha256'] and Path(proof[key]['path']).resolve()==p
        large_not_reread.append(dict(**binding,method='Owner native launcher/full CLI identity verification; previous A007 frozen identity and current stat, no A007 reread/hash.'))
    else:
        read(p);assert identities[str(p.relative_to(ROOT))]==binding
assert proof['checkpoint']==package['checkpoint']
assert proof['query_package']['sha256']==identities[str((SRC/'query_package_AT004_cached.json').relative_to(ROOT))]['sha256']
assert requal['snapshot_sha256']==proof['actual_snapshot']['sha256']=='6eb90ed584d1a0b8a0e4db0e5e40c3cf79f130a2fe503d0c3f5b2b70ea02ed8f'
assert proof['checkpoint']['sha256']=='b9e2f6dbf4fc6e013c6e4cf6078218983529f799e7ce2ecf9d0f905892f242e5'
launcher=doc(REPORT/'launcher_status.json');complete=doc(REPORT/'read_only_complete.json');boundary=doc(REPORT/'cached_query_native_boundary.json');closure=doc(ATT/'owner_terminal_and_source_closure.json')
assert launcher['native_exit_code']==0 and launcher['read_only'] is True and launcher['place_reexecuted'] is False
assert launcher['checkpoint']==package['checkpoint'] and launcher['package']==identities[str((SRC/'query_package_AT004_cached.json').relative_to(ROOT))]
assert launcher['command']==boundary['adapted_command'] and launcher['command'][5]==str(SRC/'query_cached.tcl')
assert complete['completed']=='true' and complete['actual_selected_cells']=='12' and complete['actual_selected_root_pins']=='24'
assert complete['before_apply']==complete['after_apply']=='0'
assert complete['new_place']==complete['physopt']==complete['route']=='false'
status=doc(closure['status']['path'])
assert identities[str(Path(closure['status']['path']).relative_to(ROOT))]==closure['status']
assert status==closure['terminal'] and status['execution_state']=='completed' and status['native_exit_code']==0 and status['stop_reason'] is None and status['owned_survivors']=={}
assert status['core_RTL_unchanged_during_job'] is True and status['no_wall_or_quiet_stop'] is True
assert closure['lock_free'] is True and len(closure['processes'])==6
assert all(r['expected_alive'] is False and r['actual_start'] is None for r in closure['processes'])
assert closure['archive_bindings']==len(closure['source_checks'])==200 and all(r['current_matches'] and r['archive_matches'] for r in closure['source_checks'])

neg=doc(ATT/'actual_full_CLI_negative_receipt.json')
assert neg['passed'] is True and neg['CPU_actual_data_mutations'] is True and neg['native_executed'] is False and len(neg['cases'])==8
expected_errors={
'wrong_replica_D':'actual state input group differs',
'wrong_replica_CE':'actual state input group differs',
'unknown_effective_clock_polarity':'unknown boolean/one-bit literal',
'wrong_replica_INIT':"assert flag(row['INIT']) == 0",
'wrong_actual_clock_edge':'actual clock/period/edge differs',
'original_full_guard_read_Q':'URAM root unloaded/missing bit or cross-slice own read-Q mapping',
'original_full_guard_URAM_mask':'URAM actual high-address mask changed',
'original_full_guard_80_boundary_coverage':'original 80-boundary role count changed: down'}
negative_facts=[]
assert {c['case'] for c in neg['cases']}==set(expected_errors)
for case in neg['cases']:
    assert case['rejected'] is True and case['exit_code']==1 and case['native_executed'] is False
    log_path=Path(case['log']);log=read(log_path).decode();assert expected_errors[case['case']] in log
    origin=doc(log_path.parent/'CPU_origin.json');assert origin['CPU_mutation_only'] is True and origin['native_executed'] is False and origin['mutation']==case['case']
    full=case['case'].startswith('original_full_guard_')
    assert case['full_original_validator_reached'] is full
    if full:
        q=doc(log_path.parent/'CPU_qualification_result.json');assert q['passed'] is False and expected_errors[case['case']] in q['errors'] and q['physical_state_equivalence']['passed'] is True
        errors=q['errors']
    else:
        assert 'AssertionError' in log and not (log_path.parent/'CPU_qualification_result.json').exists()
        errors=[expected_errors[case['case']]]
    negative_facts.append(dict(case=case['case'],exit_code=1,expected_semantic_rejection_verified=True,original_full_validator_reached=full,errors=errors))
for name in ['state_equivalence.py','qualify_placed_sources.py','test_state_equivalence.py','test_actual_place_cli.py']:
    read(SRC/name)
for name in ['state_equivalence_CPU_actual_empty_metadata.log','state_equivalence_CPU_regression_complete.log']:
    fixture=doc(SRC/name)
    assert fixture['passed'] is True and fixture['CPU_fixture_only'] is True and fixture['native_observation'] is False and fixture['complete_schema_rows']==108
    assert len(fixture['negatives'])==22 and all(r['rejected'] for r in fixture['negatives'])
for path in [requal['original_frozen_validator']['path'],requal['prior_literal_adapter']['path']]:
    read(path)
for key in ['explicit_adapter','prior_literal_adapter','original_frozen_validator']:
    assert identities[str(Path(requal[key]['path']).relative_to(ROOT))]==requal[key]
fdce_path=Path('/home/user/EDA-202/vivado/vivado_2025.2/2025.2/data/verilog/src/unisims/FDCE.v')
read(fdce_path)
assert identities[str(fdce_path)]['sha256']=='74d30d7c788e7db47f12b92d5b4b57b707974a0962708b309e4cc081d5f98b04'
read(ATT/'actual_complete_place_structure_requalification_CLI.log')
oldq=doc(ROOT/'project/hardware/vivado/reports/m003_E011_R003_AT001_fixed_complete_physical/m003_qualification_place.json')
assert oldq['passed'] is False and len(oldq['errors'])==24 and set(oldq['errors'])=={'URAM root write-address bit source changed'}

result=dict(schema=1,observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),execution='completed_read_only_independent_actual_evidence_reconstruction',
    evidence_only=True,owner_proof_module_imported=False,new_EDA=False,process_control=False,process_polling=False,old_whole_suites_rerun=False,
    coverage=counts,groups=group_facts,total_distinct_native_net_names=len(net_union),native_endpoint_count=72,native_trace=dict(api_calls=90,all_return_code_zero=True,all_15_actual_direct_memberships_verified=True,context=trace[0],raw_counts=api_text),
    state_facts=state_summaries,pairs=pairs,root_bindings=root_facts,
    native_terminal=dict(status=status,launcher=launcher,owner_closure_processes=closure['processes'],owner_lock_free=closure['lock_free'],owner_checked_bindings=200,independent_live_process_polling=False),
    raw_cell_empty_properties_preserved=True,root_pin_polarity_independently_checked='all 24 actual IS_INVERTED=0; exact current evidence only',
    proof_and_full_result_agree_with_independent_reconstruction=True,actual_full_CLI_negative_checks=negative_facts,owner_fixture_negatives_reused=22,
    structure_counts={k:requal[k] for k in ['phase','fixture','exact_new_M2_LUT1','exact_new_address_FF','exact_helper_LUT','exact_helper_CARRY8','protected_added_LUT','URAM_per_slice','actual_address_root_counts','normalized_cell_literals']},
    original_AT001_24_error_report_preserved=True,previous_delta_review=str(previous_path.relative_to(ROOT)),large_evidence_reused_without_reread=large_not_reread,
    evidence_identities=identities)
out=OUT/'AT004_actual_state_independent_reconstruction_20261020.json'
with out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(dict(passed=True,evidence=str(out.relative_to(ROOT)),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),rows=len(rows),groups=len(groups),endpoints=len(bindings),state_pairs=len(pairs),root_bindings=len(root_facts),actual_full_CLI_negatives=len(negative_facts))))
