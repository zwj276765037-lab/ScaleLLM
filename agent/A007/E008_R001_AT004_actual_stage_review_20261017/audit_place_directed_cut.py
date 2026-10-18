"""Replay only the closed AT004 cut from archived text; never open DCP."""
import sys
sys.dont_write_bytecode = True
def deny_dcp_content(event, args):
    if event == 'open' and args and isinstance(args[0], (str, bytes)):
        path = args[0].decode() if isinstance(args[0], bytes) else args[0]
        if path.lower().endswith('.dcp'):
            raise RuntimeError('A007 DCP content access forbidden')
sys.addaudithook(deny_dcp_content)
import os, json, hashlib
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict

ROOT = Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
REPORT = ROOT / 'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
ATTEMPT = ROOT / 'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation'
OUT = Path(__file__).resolve().parent
SOURCES = REPORT / 'stage_sources'
REPLAY = OUT / 'directed_cut_place_replay'
REPLAY.mkdir(exist_ok=False)
checked = {}

def identity(path):
    path = Path(path).resolve()
    assert path.suffix.lower() != '.dcp'
    before = path.stat()
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    row = dict(path=str(path), bytes=after.st_size, sha256=h.hexdigest())
    checked[str(path)] = row
    return row

def read_json(path):
    return json.loads(Path(path).read_text())

bindings = read_json(ATTEMPT / 'input_bindings.json')
assert identity(bindings['parent']['path']) == bindings['parent']
checkpoint = read_json(bindings['parent']['path'])['checkpoint']
actual_path = REPORT / 'candidate_cut_summary_place.json'
actual_id = identity(actual_path)
assert actual_id['sha256'] == '73e0074025f4a5629de8ccab6f5861c2ee6b2a3750fe95ca0061d5fc8fc36fa1'
actual = read_json(actual_path)
assert actual['phase'] == 'place'
projection_path = REPORT / 'candidate_directed_validation_place/projection_identity.json'
projection = read_json(projection_path)
assert identity(projection_path) == actual['actual_phase_membership_projection']
assert projection['phase'] == 'place' and projection['P_source'] == 'same-phase native-origin reconciled actual P'
assert projection['actual_P'] == identity(REPORT / 'candidate_reconciled_P_place.tsv')
assert projection['literal_P_preserved'] == identity(REPORT / 'candidate_P_place.tsv')
assert all(projection['actual_P'][k] == projection['literal_P_preserved'][k] for k in ['bytes','sha256'])
assert len(projection['inputs']) == 17
for name, row in projection['inputs'].items():
    assert identity(row['path']) == row
    target = projection_path.parent / name
    assert target.is_symlink() and target.resolve() == Path(row['path'])
    (REPLAY / name).symlink_to(row['path'])

sys.path.insert(0, str(SOURCES))
import directed_evidence as directed
import top_port_evidence as top
directed.identity = identity
top.identity = identity
original_validate = top.validate
safe_checks = []
def safe_validate(point, report, require_closed=True):
    value = original_validate(point, report, require_closed=False)
    closed = read_json(Path(report) / f'candidate_top_port_index_closed_{point}.json')
    assert closed['qualified'] is True and closed['issues'] == []
    assert closed['point'] == point and closed['epoch_id'] == value['epoch_id']
    assert closed['input_identity'] == checkpoint
    assert value['input_path'] == checkpoint['path'] and top.split(value['epoch_id'])[3] == checkpoint['path']
    assert closed['sources'] == [identity(SOURCES / 'top_port_index.tcl'), identity(SOURCES / 'top_port_evidence.py')]
    assert closed['artifacts'] == [identity(value['path']), identity(value['calls_path'])]
    safe_checks.append(dict(closed_marker=identity(REPORT / f'candidate_top_port_index_closed_{point}.json'), engineering_checkpoint_metadata=checkpoint, reviewer_DCP_access=False, full_native_reciprocal_replay=True))
    return value
top.validate = safe_validate
os.environ['DIRECTED_REUSE'] = str(OUT / 'NO_REUSE_MANIFEST')
cut = directed.cut('place', REPLAY)
assert cut == {key:value for key,value in actual.items() if key not in {'phase', 'actual_phase_membership_projection'}}
assert cut['directed_boundary_complete'] is True and cut['candidate_leaf_coverage_complete'] is True
assert sum(row['pairs'] for row in cut['unknown_top_or_unplaced_pair_positions']) == 8014
assert cut['candidate_involved_driver_load_pairs'] == 44054
assert all(row['driver_SLR']=='UNPLACED' and row['load_SLR']=='SLR2' for row in cut['unknown_top_or_unplaced_pair_positions'])
assert sum(row['current_known_cross_SLR_pairs'] for row in cut['pair_scope'])==127
assert all(row['current_known_cross_SLR_pairs'] == row['hypothetical_all_P_to_SLR2_outside_fixed_known_cross_SLR_pairs'] for row in cut['pair_scope'])
scope = list(directed.rows(REPORT / 'candidate_boundary_timing_scope_place.tsv'))
scope_counts = dict(Counter(row['cut_direction'] for row in scope))
assert scope_counts == {'INGRESS':20534, 'EGRESS':945}
assert all(row['role'] == 'LOAD' for row in scope)

# Reuse accepted topology, separately examine the actual newly placed endpoints.
prior_path=OUT/'pre_place_directed_cut_incremental_review.json'
assert identity(prior_path)['sha256']=='3f0e023284b2bef333fa605d07a9b2db9edea232a64d548362e59378a43e325c'
prior=read_json(prior_path);prior_cut=read_json(prior['actual_summary']['path'])
invariant_keys=['coverage_version','directed_boundary_complete','candidate_leaf_coverage_complete','native_pin_class_schema_qualified','native_role_qualified_nets','canonical_nets','actual_candidate_native_leaf_pins','actual_local_raw_pin_records','disconnected_candidate_leaf_pins','retained_endpoint_rows','retained_class_counts','scope_modes','boundary_directions','retained_net_categories','candidate_involved_driver_load_pairs','candidate_boundary_driver_load_pairs','timing_scope_rows']
assert all(cut[k]==prior_cut[k] for k in invariant_keys)
assert identity(SOURCES/'directed_evidence.py')==prior['validator']
assert identity(SOURCES/'evidence_adapter.py')==prior['adapter']
grouped=defaultdict(list)
for row in directed.rows(REPORT/'candidate_endpoints_place.tsv'):grouped[row['canonical_net']].append(row)
nets={row['canonical_net']:row for row in directed.rows(REPORT/'candidate_nets_place.tsv')}
unknown=Counter();unknown_drivers=defaultdict(set);known_cross=Counter();allpairs=0
for name,records in grouped.items():
    assert nets[name]['resolution']=='SINGLE_DRIVER'
    drivers=[r for r in records if r['role']=='DRIVER'];loads=[r for r in records if r['role']=='LOAD'];assert len(drivers)==1
    driver=drivers[0];category,_=directed.category(nets[name]['actual_clocks'],{r['pin_class'] for r in records})
    for load in loads:
        if not (directed.inside(driver) or directed.inside(load)):continue
        allpairs+=1
        if driver['SLR'] not in directed.SLRS or load['SLR'] not in directed.SLRS:
            assert not directed.inside(driver) and directed.inside(load) and load['SLR']=='SLR2'
            assert driver['SLR']=='UNPLACED' and driver['inside_P']=='0' and driver['inside_S']=='0'
            unknown[category]+=1
            unknown_drivers[category].add((driver['NAME'],driver['REF_NAME'],driver['pin_class'],driver['kind'],driver['inside_RAW'],driver['inside_S'],driver['inside_P']))
        elif driver['SLR']!=load['SLR']:
            known_cross[category]+=1
assert allpairs==44054 and dict(unknown)=={'reset_set':6156,'constant':429,'clock':1429}
assert dict(known_cross)=={'clock':6,'known_data_or_select_control':38,'mixed_known_unknown':53,'unknown_or_unclassified':30}
unknown_detail=[dict(category=k,pairs=unknown[k],drivers=[dict(zip(['NAME','REF_NAME','pin_class','kind','inside_RAW','inside_S','inside_P'],r)) for r in sorted(v)]) for k,v in sorted(unknown_drivers.items())]
membership_review=identity(OUT/'place_membership_reconciliation_review.json')
assert membership_review['sha256']=='cfbb3047dac1dda52562d17ac38da8245d4299ce06f7eab223e76afb1bdc59c2'
index_review=identity(OUT/'place_native_index_alias_review.json')
assert index_review['sha256']=='1d7c6d13daeb354c1ffdaf3514d79df932a38e8d75ef14236f3fab0d96cff674'
result=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),reviewer='A007',execution='COMPLETED_ACTUAL_PLACE_CLOSED_DIRECTED_CUT_REPLAY',verdict='ACCEPT_COMPLETE_CANDIDATE_DIRECTED_BOUNDARY_AND_LEAF_COVERAGE',applicability='AT004 actual place graph with same-phase native-origin reconciled P; directed contract scope only',review='INDEPENDENT_SUBSTEP_ACCEPTED_NO_NEW_GATE',actual_summary=actual_id,
    validator=identity(SOURCES/'directed_evidence.py'),adapter=identity(SOURCES/'evidence_adapter.py'),replay_program=identity(__file__),replay_output=identity(REPLAY/'candidate_cut_summary_place.json'),
    projection=identity(projection_path),projection_inputs=17,actual_reconciled_P=projection['actual_P'],literal_P_preserved=projection['literal_P_preserved'],
    complete_replay_equals_actual=True,topological_fields_equal_accepted_pre_place=invariant_keys,accepted_pre_place_cut=identity(prior_path),accepted_current_membership=membership_review,accepted_current_index=index_review,
    facts={k:cut[k] for k in invariant_keys},pair_scope=cut['pair_scope'],known_current_cross_SLR_pairs=127,known_cross_by_category=dict(known_cross),unknown_position_pairs=8014,unknown_position_by_category=dict(unknown),unknown_position_actual_driver_evidence=unknown_detail,
    unknown_positions_all_non_candidate_driver_to_SLR2_candidate_load=True,exported_boundary_through_pin_sets=scope_counts,raw_evidence_identities=list(checked.values()),safe_index_checks=safe_checks,
    limits=['127 known logical crossings and 8014 unknown-position logical pairs are neither total SLL usage nor bandwidth/congestion metrics.',
      'All 9491 P are placed in SLR2. Unknown pair positions are non-S/P drivers, with candidate loads in SLR2; unknown reset_set is net-category classification, not unplaced P/reset receivers.',
      'External peer loads are omitted only for qualified external-driver nets; complete external fanout/whole hotspot UNION/full-cut TNS are not measured.',
      'Through-LOAD pin sets may include internal or externally driven paths; not every returned path necessarily crosses the candidate boundary.',
      'No standalone congestion improvement, candidate causality, full timing signoff or route success claim.',
      'DCP identity remains engineering-attributed metadata; no DCP content access, native query/process/lock control or engineering edits.'])
output=OUT/'place_directed_cut_review.json'
with output.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
human=OUT/'place_directed_cut_review.md'
with human.open('x') as f:f.write('''# AT004 place 完整有向cut审核

execution：17项实际投影输入及归档验证器完整重放完成，逐字段等于当前摘要。verdict：接受合同范围内完整候选leaf与有向边界覆盖。applicability：当前place图及同阶段native-origin reconciled P。review：独立子步骤通过，无新增停点。

14,307条网、55,605个候选leaf pins、1,276个断开pins、58,361个保留endpoint、44,054个候选相关driver/load pairs、21,479个boundary pairs。3,087条外部驱动网采用有向范围，11,220条候选驱动网完整枚举；INGRESS3,087/EGRESS55。拓扑统计同本轮已审pre-place。

当前已知跨SLR逻辑pair127：clock6、known-data/select38、mixed53、unknown-semantic30。未知位置pair8,014：clock1,429、constant429、reset_set6,156；逐原始endpoint检查均为非S/P驱动端SLR=UNPLACED、候选负载端SLR2。所有9491个P实际落区结论不受这一外部/常量驱动位置未知混淆。reset_set是net类别，不表示P复位接收器未布局。

这些是逻辑连接pair，不是全SLL数、带宽、拥塞或改善量。完整外部fanout、热点UNION和full-cut TNS未测。through-LOAD查询集INGRESS20,534/EGRESS945，并不保证每条后续时序路径跨候选边界。完整阶段另行组合审核。
''')
print(json.dumps(dict(review=identity(output),human=identity(human),unknown_drivers=unknown_detail),ensure_ascii=False))

