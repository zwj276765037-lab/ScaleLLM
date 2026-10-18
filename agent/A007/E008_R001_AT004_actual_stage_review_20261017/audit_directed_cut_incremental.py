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
from collections import Counter

ROOT = Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
REPORT = ROOT / 'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
ATTEMPT = ROOT / 'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation'
OUT = Path(__file__).resolve().parent
SOURCES = REPORT / 'stage_sources'
REPLAY = OUT / 'directed_cut_pre_place_replay'
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
actual_path = REPORT / 'candidate_cut_summary_pre_place.json'
actual_id = identity(actual_path)
assert actual_id['sha256'] == '5bbf0382094cc2d8f086c8b2ab14f992bac1d05b7e70a22ef7d01d5f34f774a3'
actual = read_json(actual_path)
assert actual['phase'] == 'pre_place'
projection_path = REPORT / 'candidate_directed_validation_pre_place/projection_identity.json'
projection = read_json(projection_path)
assert identity(projection_path) == actual['actual_phase_membership_projection']
assert projection['phase'] == 'pre_place' and projection['P_source'] == 'literal actual pre-place P'
assert projection['actual_P'] == projection['literal_P_preserved'] == identity(REPORT / 'candidate_P_pre_place.tsv')
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
cut = directed.cut('pre_place', REPLAY)
assert cut == {key:value for key,value in actual.items() if key not in {'phase', 'actual_phase_membership_projection'}}
assert cut['directed_boundary_complete'] is True and cut['candidate_leaf_coverage_complete'] is True
assert sum(row['pairs'] for row in cut['unknown_top_or_unplaced_pair_positions']) == cut['candidate_involved_driver_load_pairs'] == 44054
assert all(row['driver_SLR'] == row['load_SLR'] == 'UNPLACED' for row in cut['unknown_top_or_unplaced_pair_positions'])
assert all(row['current_known_cross_SLR_pairs'] == row['hypothetical_all_P_to_SLR2_outside_fixed_known_cross_SLR_pairs'] == 0 for row in cut['pair_scope'])
scope = list(directed.rows(REPORT / 'candidate_boundary_timing_scope_pre_place.tsv'))
scope_counts = dict(Counter(row['cut_direction'] for row in scope))
assert scope_counts == {'INGRESS':20534, 'EGRESS':945}
assert all(row['role'] == 'LOAD' for row in scope)

prior_review_path = ROOT / 'agent/A007/E008_R001_AT003_actual_stage_review_20261017/pre_place_directed_cut_timing_review.json'
prior_review_id = identity(prior_review_path)
assert prior_review_id['sha256'] == '3fd4120659d5d384c551d623ca63d6aaa1a09ff39ecd6c1f74fda46853acffd5'
prior = read_json(prior_review_path)
prior_summary_id = identity(prior['actual_summary']['path'])
assert prior_summary_id == prior['actual_summary']
prior_summary = read_json(prior_summary_id['path'])
identity_fields = {'artifacts', 'schema', 'local_scope', 'native_role_queries', 'native_closed_marker', 'validator', 'phase', 'actual_phase_membership_projection', 'top_port_acquisition'}
assert {key:value for key,value in actual.items() if key not in identity_fields} == {key:value for key,value in prior_summary.items() if key not in identity_fields}
assert {key:value for key,value in actual['top_port_acquisition'].items() if key not in {'index','native_calls'}} == {key:value for key,value in prior_summary['top_port_acquisition'].items() if key not in {'index','native_calls'}}
assert {key:actual[key] for key in prior['facts']} == prior['facts']
assert scope_counts == prior['timing_scope']
assert identity(SOURCES / 'directed_evidence.py')['sha256'] == prior['validator']['sha256']
assert identity(SOURCES / 'evidence_adapter.py')['sha256'] == prior['adapter']['sha256']
artifact_deltas = []
for name, row in actual['artifacts'].items():
    old = prior_summary['artifacts'][name]
    artifact_deltas.append(dict(artifact=name, bytes=row['bytes'], sha256=row['sha256'], byte_identical_to_accepted_AT003=(row['bytes'],row['sha256']) == (old['bytes'],old['sha256'])))
for name in ['schema','local_scope','native_role_queries','native_closed_marker']:
    row, old = actual[name], prior_summary[name]
    artifact_deltas.append(dict(artifact=name, bytes=row['bytes'], sha256=row['sha256'], byte_identical_to_accepted_AT003=(row['bytes'],row['sha256']) == (old['bytes'],old['sha256'])))

result = dict(
    recorded_utc=datetime.now(timezone.utc).isoformat(), reviewer='A007',
    execution='completed_actual_AT004_closed_directed_cut_text_replay',
    verdict='accepted_complete_candidate_directed_boundary_and_leaf_coverage',
    applicability='AT004 pre_place restored input plus C01 Pblock; directed cut and exported query pin sets only',
    review='accepted_no_new_execution_gate', actual_summary=actual_id,
    validator=identity(SOURCES / 'directed_evidence.py'), adapter=identity(SOURCES / 'evidence_adapter.py'),
    replay_program=identity(__file__), replay_output=identity(REPLAY / 'candidate_cut_summary_pre_place.json'),
    membership_prior_review=identity(OUT / 'pre_place_membership_incremental_review.json'),
    native_index_prior_review=identity(OUT / 'pre_place_native_index_alias_review.json'),
    projection=identity(projection_path), projection_input_count=17,
    raw_evidence_identities=list(checked.values()), safe_index_checks=safe_checks,
    complete_replay_equals_actual=True, semantic_fields_equal_accepted_AT003=True,
    prior_accepted_review=prior_review_id, prior_actual_summary=prior_summary_id,
    artifact_deltas=artifact_deltas, facts={key:cut[key] for key in prior['facts']},
    exported_boundary_through_pin_sets=scope_counts,
    limits=[
        'All 44054 candidate-related driver/load pairs have UNPLACED/UNPLACED positions; zero known crossings is not measured cross-SLR improvement.',
        'Full cut TNS is NOT_MEASURED; no timing results were replayed or accepted by this cut-only review.',
        'Through-pin sets may include internal or externally driven paths; not every later returned path necessarily crosses a candidate boundary edge.',
        'Outside peer loads on qualified external-driver nets are omitted under the accepted directed scope; complete external fanout and whole-hotspot UNION are not measured.',
        'Not complete pre_place or place/route signoff; no congestion, timing or candidate benefit claim.',
        'DCP content identity is engineering-provided metadata; no reviewer DCP content read/hash, EDA, signals or lock control.'
    ])
output = OUT / 'pre_place_directed_cut_incremental_review.json'
with output.open('x') as stream:
    stream.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
human = OUT / 'pre_place_directed_cut_incremental_review.md'
with human.open('x') as stream:
    stream.write('# AT004 pre-place 有向 cut 增量审核\n\n'
                 '- execution：17 项实际原始文本投影的身份核对与归档解析器完整重放完成；重放逐字段等于本轮摘要。\n'
                 '- verdict：接受完整候选 leaf 覆盖和合同内有向边界覆盖。14,307 条网、55,605 个候选 leaf pins、1,276 个断开 pins、58,361 个保留端点；44,054 个候选相关 driver/load pairs，其中 21,479 个边界 pairs。\n'
                 '- 3,087 条外部驱动网按定向范围采集，11,220 条候选驱动网完整枚举；方向网数 INGRESS 3,087 / EGRESS 55。导出的 through-pin 集合为 INGRESS 20,534 / EGRESS 945。实际语义统计与已审 AT003 一致。\n'
                 '- applicability：仅 AT004 pre-place cut。所有相关位置均 UNPLACED，known crossing 0 不能说明跨 SLR 或拥塞改善。through-pin 查询不保证逐条路径跨候选边界；未枚举合格外部驱动网的外部 peer loads，非完整外部 fanout、UNION 或 full-cut TNS。\n'
                 '- review：本子步骤接受，无新增执行停点。本记录不验收 timing、完整 pre-place 或 place/route；未读取或哈希 DCP。\n\n'
                 '[机器审核和原始证据身份](pre_place_directed_cut_incremental_review.json)\n')
print(json.dumps(dict(review=identity(output), human=identity(human), native_counts=result['facts'], artifact_deltas=artifact_deltas), ensure_ascii=False))
