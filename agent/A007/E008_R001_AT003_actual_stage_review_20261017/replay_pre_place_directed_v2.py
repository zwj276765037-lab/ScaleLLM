#!/usr/bin/env python3
"""A007 closed-artifact replay. Never read/hash DCP or execute EDA/Tcl."""
import sys
sys.dont_write_bytecode = True
import os, json, pathlib, hashlib, csv, re
from collections import Counter, defaultdict
from datetime import datetime, timezone

ROOT = pathlib.Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
REPORT = ROOT/'project/hardware/vivado/reports/m002_E008_R001_AT003_C01_physical_xdc_fix_full_implementation'
ATTEMPT = ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT003_C01_physical_xdc_fix_full_implementation'
OUT = pathlib.Path(__file__).resolve().parent
REPLAY = OUT/'directed_pre_place_replay_v2'
REPLAY.mkdir(exist_ok=False)
SOURCES = REPORT/'stage_sources'

def identity(path):
    p = pathlib.Path(path).resolve()
    assert p.suffix.lower() != '.dcp', 'DCP access forbidden'
    before = p.stat()
    digest = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024), b''): digest.update(block)
    after = p.stat()
    assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    return dict(path=str(p),bytes=after.st_size,sha256=digest.hexdigest())

def read_json(p): return json.loads(pathlib.Path(p).read_text())
def save(p,v):
    with p.open('x') as f: json.dump(v,f,ensure_ascii=False,indent=2); f.write('\n')

bindings=read_json(ATTEMPT/'input_bindings.json')
assert identity(bindings['parent']['path'])==bindings['parent']
parent=read_json(bindings['parent']['path'])
checkpoint=parent['checkpoint']  # Engineering content identity; reviewer never opens DCP.
projections=[]
for p in sorted((REPORT/'candidate_directed_validation_pre_place').glob('projection_identity*.json')):
    value=read_json(p)
    assert value['phase']=='pre_place' and value['P_source']=='literal actual pre-place P'
    assert value['actual_P']==value['literal_P_preserved']==identity(REPORT/'candidate_P_pre_place.tsv')
    for name,bound in value['inputs'].items():
        assert identity(bound['path'])==bound
        target=p.parent/name
        assert target.is_symlink() and target.resolve()==pathlib.Path(bound['path'])
        dest=REPLAY/name
        if not dest.exists(): dest.symlink_to(bound['path'])
        else: assert dest.resolve()==target.resolve()
    projections.append(dict(artifact=identity(p),input_count=len(value['inputs'])))

sys.path.insert(0,str(SOURCES))
import directed_evidence as directed
import top_port_evidence as top
directed.identity=identity
top.identity=identity
original_validate=top.validate
safe_index_checks=[]
def safe_validate(point, report, require_closed=True):
    value=original_validate(point, report, require_closed=False)
    index=top.dictionary((pathlib.Path(report)/f'candidate_top_port_index_{point}.tcllist').read_text())
    closed=read_json(pathlib.Path(report)/f'candidate_top_port_index_closed_{point}.json')
    assert closed['qualified'] is True and closed['issues']==[]
    assert closed['point']==point and closed['epoch_id']==index['epoch_id']
    assert closed['input_identity']==checkpoint
    assert index['input_path']==checkpoint['path'] and top.split(index['epoch_id'])[3]==checkpoint['path']
    assert closed['sources']==[identity(SOURCES/'top_port_index.tcl'),identity(SOURCES/'top_port_evidence.py')]
    assert closed['artifacts']==[identity(REPORT/f'candidate_top_port_index_{point}.tcllist'),identity(REPORT/f'candidate_top_port_native_calls_{point}.tcllist')]
    assert closed['native_port_count']==value['native_port_count']==269
    assert closed['native_group_count']==len(value['groups'])==269
    assert closed['native_call_count']==2170
    safe_index_checks.append(dict(closed_marker=identity(REPORT/f'candidate_top_port_index_closed_{point}.json'),
                                 engineering_checkpoint_identity=checkpoint, reviewer_DCP_access=False,
                                 full_native_reciprocal_replay=True))
    return value
top.validate=safe_validate
os.environ['DIRECTED_REUSE']=str(OUT/'NO_REUSE_MANIFEST')

cut=directed.cut('pre_place',REPLAY)
actual=read_json(REPORT/'candidate_cut_summary_pre_place.json')
assert actual['phase']=='pre_place'
assert actual['actual_phase_membership_projection']==identity(REPORT/'candidate_directed_validation_pre_place/projection_identity.json')
assert cut=={k:v for k,v in actual.items() if k not in {'phase','actual_phase_membership_projection'}}
assert sum(v['pairs'] for v in cut['unknown_top_or_unplaced_pair_positions'])==cut['candidate_involved_driver_load_pairs']==44054
assert all(v['driver_SLR']==v['load_SLR']=='UNPLACED' for v in cut['unknown_top_or_unplaced_pair_positions'])
assert all(v['current_known_cross_SLR_pairs']==v['hypothetical_all_P_to_SLR2_outside_fixed_known_cross_SLR_pairs']==0 for v in cut['pair_scope'])
timing=directed.timing('pre_place',REPLAY)
actual_timing=read_json(REPORT/'candidate_timing_validation_pre_place.json')
assert timing=={k:v for k,v in actual_timing.items() if k!='phase'}
assert actual_timing['phase']=='pre_place'
scope=list(directed.rows(REPORT/'candidate_boundary_timing_scope_pre_place.tsv'))
direction_counts=dict(Counter(v['cut_direction'] for v in scope))
assert direction_counts=={'INGRESS':20534,'EGRESS':945}
assert all(v['role']=='LOAD' for v in scope)
assert {k:len(v) for k,v in timing['query_sets'].items()}==direction_counts
records=list(directed.rows(REPORT/'candidate_scoped_timing_pre_place.tsv'))
by_query=defaultdict(list)
for row in records: by_query[(row['direction'],row['delay_type'])].append(row)
native_timing=[]
for (direction,kind),values in sorted(by_query.items()):
    p=REPORT/f'candidate_cut_timing_pre_place_{direction}_{kind}.rpt'
    parsed=[]; command=None
    with p.open() as f:
        for line in f:
            if re.match(r'^\|\s*Command\s*:',line):
                header=line.split(':',1)[1].strip()
                assert header.startswith('report_timing -of_objects [get_timing_paths ')
                query=header[len('report_timing -of_objects ['):]
                query=query[:query.rindex(']')]
                command=directed.split(query)
            m=re.match(r'^Slack \((?:MET|VIOLATED)\)\s*:\s*([-+0-9.]+)ns',line)
            if m: parsed.append({'SLACK':m.group(1)})
            for label,key in [('Source:','STARTPOINT_PIN'),('Destination:','ENDPOINT_PIN')]:
                if line.lstrip().startswith(label): parsed[-1][key]=line.split(label,1)[1].strip()
            m=re.match(r'\s*Data Path Delay:\s*([-+0-9.]+)ns',line)
            if m: parsed[-1]['DATAPATH_DELAY']=m.group(1)
    assert len(parsed)==len(values)==16
    for raw,table in zip(parsed,values):
        assert raw['STARTPOINT_PIN']==table['STARTPOINT_PIN'] and raw['ENDPOINT_PIN']==table['ENDPOINT_PIN']
        assert float(raw['SLACK'])==float(table['SLACK']) and float(raw['DATAPATH_DELAY'])==float(table['DATAPATH_DELAY'])
    # Native report header must bind the same full through-pin set and cap.
    assert command and command[0]=='get_timing_paths'
    assert set(directed.split(command[command.index('-through')+1]))==set(timing['query_sets'][direction])
    assert command[command.index('-delay_type')+1]==kind
    assert command[command.index('-max_paths')+1]=='16' and command[command.index('-nworst')+1]=='1'
    native_timing.append(dict(direction=direction,delay_type=kind,queried_pins=direction_counts[direction],
        returned_paths=len(values),worst_slack_ns=min(float(v['SLACK']) for v in values),
        negative_slack_paths=sum(float(v['SLACK'])<0 for v in values),native_report=identity(p),
        report_table_all64_identity_slack_datapath_matches=True))

result=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),reviewer='A007',
    execution='INDEPENDENT_CLOSED_ARTIFACT_REPLAY_COMPLETED',verdict='ACCEPT_PRE_PLACE_DIRECTED_CUT_AND_BOUNDED_TIMING_EVIDENCE',
    applicability='Actual AT003 pre_place only; no placed/routed improvement or timing signoff',review='COMPLETE',
    actual_summary=identity(REPORT/'candidate_cut_summary_pre_place.json'),
    actual_timing_validation=identity(REPORT/'candidate_timing_validation_pre_place.json'),
    validator=identity(SOURCES/'directed_evidence.py'),adapter=identity(SOURCES/'evidence_adapter.py'),
    replay_program=identity(__file__),replay_outputs=[identity(REPLAY/'candidate_cut_summary_pre_place.json'),identity(REPLAY/'candidate_timing_validation_pre_place.json')],
    membership_prior_review=identity(OUT/'pre_place_membership_incremental_review.json'),
    native_index_prior_review=identity(OUT/'pre_place_native_index_alias_review.json'),
    projection_revisions=projections,safe_index_checks=safe_index_checks,
    replay_equal_actual=True,full_native_ROLE_JOIN_endpoint_membership_and_directed_timing_sets=True,
    facts={k:cut[k] for k in ['canonical_nets','actual_candidate_native_leaf_pins','actual_local_raw_pin_records','disconnected_candidate_leaf_pins','retained_endpoint_rows','scope_modes','boundary_directions','candidate_involved_driver_load_pairs','candidate_boundary_driver_load_pairs','pair_scope','unknown_top_or_unplaced_pair_positions']},
    timing_scope=direction_counts,bounded_timing=native_timing,
    limits=['All 44054 actual candidate-related driver/load pairs UNPLACED/UNPLACED; known crossings 0 is unknown placement, not congestion reduction.',
      'Complete directional through-pin query sets do not imply each returned timing path traverses a candidate boundary edge. Clock/reset/load membership can include internal or externally driven paths.',
      'Four bounded queries with max_paths16/nworst1; not exhaustive path enumeration or full-cut TNS.',
      'Logic/net delay properties UNKNOWN_UNSUPPORTED_PROPERTY remain unknown; no invented values.',
      'Pre-place estimates must not be compared with prior placed/physopt timings as improvement.',
      'Outside peer loads on qualified external-driver nets not enumerated; complete external fanout and whole-hotspot UNION unmeasured.',
      'DCP content identities attributed to engineering; reviewer opened and hashed no DCP. No EDA/process control.'])
save(OUT/'pre_place_directed_cut_timing_review.json',result)
markdown='''# AT003 pre-place 有向 cut 与有界时序独立审核

- execution：闭合原始文本完整重放完成；verdict：接受；applicability：仅 AT003 pre_place；review：完成。
- 实际归档 validator 完整重放并逐字段等于实际摘要；原始 18 项 cut 投影及新增 timing 投影身份均已核对。DCP 仅核对工程绑定元数据，未读取或哈希 DCP。
- 14,307 条网、55,605 个候选 leaf pins、1,276 个断开 pins、58,361 个保留端点；3,087 个外部驱动定向 ingress、11,220 个候选驱动完整枚举。完整 JOIN、成员、方向、native class/role、别名和 timing scope 均通过。
- 44,054 个候选相关 driver/load pairs，21,479 个边界 pairs；所有位置均 UNPLACED。已知 crossing=0 不能解释为跨 SLR 或拥塞改善。
- 完整方向引脚集 ingress 20,534、egress 945。max/min 各返回16条，64条原生报告与表的起点、终点、slack、datapath delay逐项一致。最差 setup 为 +6.158/+6.859ns，hold 为 −0.074/+0.081ns（入/出）。
- 查询采用 through-pin 集合，可能覆盖内部或其他驱动路径；不保证每条返回路径经过候选边界边。布局前估算不可与旧 physopt 值作改善比较，非 full-cut TNS 或时序签核。物理实现继续。

机器证据见 `pre_place_directed_cut_timing_review.json`；重放脚本及输出单独保全。
'''
(OUT/'pre_place_directed_cut_timing_review.md').write_text(markdown)
print(json.dumps(dict(review=identity(OUT/'pre_place_directed_cut_timing_review.json'),human=identity(OUT/'pre_place_directed_cut_timing_review.md'),timing=native_timing),ensure_ascii=False))
