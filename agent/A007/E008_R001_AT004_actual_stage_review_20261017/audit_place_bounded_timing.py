"""AT004 archived bounded timing replay; DCP and EDA access forbidden."""
import sys
sys.dont_write_bytecode = True
def guard(event, args):
    if event == 'open' and args and isinstance(args[0], (str, bytes)):
        value = args[0].decode() if isinstance(args[0], bytes) else args[0]
        if value.lower().endswith('.dcp'):
            raise RuntimeError('DCP content access forbidden')
sys.addaudithook(guard)
import hashlib, json, re
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone, timedelta

ROOT = Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
REPORT = ROOT / 'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
OUT = Path(__file__).resolve().parent
REPLAY = OUT / 'bounded_timing_place_replay'
REPLAY.mkdir(exist_ok=False)
SOURCES = REPORT / 'stage_sources'
checked = {}
def identity(path):
    path = Path(path).resolve()
    assert path.suffix.lower() != '.dcp'
    before = path.stat(); digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024), b''): digest.update(block)
    after = path.stat()
    assert (before.st_size,before.st_mtime_ns) == (after.st_size,after.st_mtime_ns)
    row = dict(path=str(path),bytes=after.st_size,sha256=digest.hexdigest())
    checked[str(path)] = row
    return row
def read(path): return json.loads(Path(path).read_text())

cut_review = read(OUT / 'place_directed_cut_review.json')
projection_path = REPORT / 'candidate_directed_validation_place/projection_identity_1.json'
projection = read(projection_path)
first = read(REPORT / 'candidate_directed_validation_place/projection_identity.json')
assert len(projection['inputs']) == 24 and len(first['inputs']) == 17
assert projection['phase'] == 'place' and projection['actual_P'] == first['actual_P']
assert projection['literal_P_preserved']==first['literal_P_preserved']
assert projection['actual_P']==identity(REPORT/'candidate_reconciled_P_place.tsv')
assert projection['literal_P_preserved']==identity(REPORT/'candidate_P_place.tsv')
assert projection['P_source'] == 'same-phase native-origin reconciled actual P'
assert all(projection['inputs'][key] == value for key,value in first['inputs'].items())
new_inputs = {key:value for key,value in projection['inputs'].items() if key not in first['inputs']}
assert len(new_inputs) == 7
for name,row in new_inputs.items():
    assert identity(row['path']) == row
    target = projection_path.parent/name
    assert target.is_symlink() and target.resolve() == Path(row['path'])
    (REPLAY/name).symlink_to(row['path'])
scope = 'candidate_boundary_timing_scope_place.tsv'
assert identity(first['inputs'][scope]['path']) == first['inputs'][scope]
(REPLAY/scope).symlink_to(first['inputs'][scope]['path'])

sys.path.insert(0,str(SOURCES))
import directed_evidence as directed
directed.identity = identity
timing = directed.timing('place',REPLAY)
actual_path = REPORT/'candidate_timing_validation_place.json'
actual_id = identity(actual_path)
assert actual_id['sha256'] == '9954c7cb87766e1456f963db035caadb74a47704918975819a6fde351771d056'
actual = read(actual_path)
assert actual['phase'] == 'place' and timing == {key:value for key,value in actual.items() if key!='phase'}
scope_counts = {key:len(value) for key,value in timing['query_sets'].items()}
assert scope_counts == cut_review['exported_boundary_through_pin_sets'] == {'INGRESS':20534,'EGRESS':945}

log_path = REPORT/'vivado.log'
log_events = []; cut_line = None
with log_path.open() as stream:
    for number,line in enumerate(stream,1):
        if line.startswith('DIRECTED_CUT_COMPLETED point=place '): cut_line=number
        if line.startswith('DIRECTED_API operation BOUNDED_TIMING '):
            parts = directed.split(line)
            event = dict(zip(parts[1::2],parts[2::2]))
            if event['point']=='place': log_events.append(dict(line_number=number,text=line.rstrip(),fields=event))
assert len(log_events) == 8 and cut_line < log_events[0]['line_number']
index_epoch = read(REPORT/'candidate_top_port_index_closed_place.json')['epoch_id']
epoch_ms = int(directed.split(index_epoch)[1])//1000
assert all(int(row['fields']['epoch_ms']) > epoch_ms for row in log_events)
events_by_query = defaultdict(dict)
for row in log_events:
    value=row['fields']; key=(value['direction'],value['delay_type'])
    assert value['event'] not in events_by_query[key]
    events_by_query[key][value['event']]=row

records=list(directed.rows(REPORT/'candidate_scoped_timing_place.tsv'))
by_query=defaultdict(list)
for row in records: by_query[(row['direction'],row['delay_type'])].append(row)
raw_reviews=[]
for key, values in sorted(by_query.items()):
    direction,kind=key
    events=events_by_query[key]
    assert set(events)=={'BEGIN','END'} and events['END']['fields']['returned_paths']=='16'
    begin=int(events['BEGIN']['fields']['epoch_ms']); end=int(events['END']['fields']['epoch_ms'])
    assert begin<=end
    report=REPORT/f'candidate_cut_timing_place_{direction}_{kind}.rpt'
    parsed=[]; command=None; header={}; clock_target=None
    with report.open() as stream:
        for line in stream:
            if re.match(r'^\|\s*Command\s*:',line):
                value=line.split(':',1)[1].strip()
                assert value.startswith('report_timing -of_objects [get_timing_paths ')
                query=value[len('report_timing -of_objects ['):]
                command=directed.split(query[:query.rindex(']')])
            elif line.startswith('|') and ':' in line:
                name,value=line[1:].split(':',1);header[name.strip()]=value.strip()
            match=re.match(r'^Slack \((?:MET|VIOLATED)\)\s*:\s*([-+0-9.]+)ns',line)
            if match: parsed.append({'SLACK':match.group(1)})
            for label,name,clock in [('Source:','STARTPOINT_PIN','STARTPOINT_CLOCK'),('Destination:','ENDPOINT_PIN','ENDPOINT_CLOCK')]:
                if line.lstrip().startswith(label):
                    parsed[-1][name]=line.split(label,1)[1].strip();clock_target=clock
            if clock_target and 'clocked by ' in line:
                parsed[-1][clock_target]=line.split('clocked by ',1)[1].split()[0];clock_target=None
            match=re.match(r'\s*Data Path Delay:\s*([-+0-9.]+)ns',line)
            if match: parsed[-1]['DATAPATH_DELAY']=match.group(1)
    assert len(parsed)==len(values)==16
    for native,table in zip(parsed,values):
        for field in ['STARTPOINT_PIN','ENDPOINT_PIN','STARTPOINT_CLOCK','ENDPOINT_CLOCK']:
            assert native[field]==table[field]
        for field in ['SLACK','DATAPATH_DELAY']: assert float(native[field])==float(table[field])
        assert table['LOGIC_DELAY']==table['NET_DELAY']=='UNKNOWN_UNSUPPORTED_PROPERTY'
    assert command[0]=='get_timing_paths'
    assert set(directed.split(command[command.index('-through')+1]))==set(timing['query_sets'][direction])
    assert command[command.index('-delay_type')+1]==kind
    assert command[command.index('-max_paths')+1]=='16' and command[command.index('-nworst')+1]=='1'
    assert header['Design State']=='Fully Placed' and header['Design']=='scalellm_vcu118_f05_bd_wrapper'
    assert 'Vivado v.2025.2' in header['Tool Version'] and 'Build 6299465' in header['Tool Version']
    stamp=datetime.strptime(header['Date'],'%a %b %d %H:%M:%S %Y').replace(tzinfo=timezone(timedelta(hours=8)))
    assert begin//1000<=int(stamp.timestamp())<=end//1000+5
    raw_reviews.append(dict(direction=direction,delay_type=kind,queried_pins=scope_counts[direction],returned_paths=len(values),worst_slack_ns=min(float(v['SLACK']) for v in values),negative_slack_paths=sum(float(v['SLACK'])<0 for v in values),native_report=identity(report),header=header,actual_log_events=events,all16_raw_identity_clocks_slack_datapath_matches=True))

assert {(r['direction'],r['delay_type']):r['worst_slack_ns'] for r in raw_reviews}=={('INGRESS','max'):0.603,('INGRESS','min'):-0.221,('EGRESS','max'):0.603,('EGRESS','min'):0.057}
prior_path=OUT/'pre_place_bounded_timing_incremental_review.json';prior_id=identity(prior_path)
assert prior_id['sha256']=='29bb951a65d7c1086ac7edb7b1f4e4dbdbc91f700e0da660d2c37d18302ccb70'
prior=read(prior_path)
prior_checks={r['path']:r for r in prior['identities']}
assert identity(SOURCES/'directed_evidence.py')==prior_checks[str(SOURCES/'directed_evidence.py')]
signatures=defaultdict(set)
for r in records:signatures[(r['direction'],r['delay_type'])].add((r['STARTPOINT_PIN'],r['ENDPOINT_PIN'],r['STARTPOINT_CLOCK'],r['ENDPOINT_CLOCK']))
overlap={k:len(signatures[('INGRESS',k)] & signatures[('EGRESS',k)]) for k in ['max','min']}
metrics=['direction','delay_type','queried_pins','returned_paths','worst_slack_ns','negative_slack_paths']
result=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),reviewer='A007',execution='COMPLETED_CURRENT_PLACE_BOUNDED_TIMING_REPLAY_AND_64_NATIVE_ROWS',
    verdict='ACCEPT_COMPLETE_DIRECTIONAL_QUERY_SETS_AND_BOUNDED_NATIVE_RESULTS; INGRESS_HOLD_HAS_NEGATIVE_SLACK',
    applicability='AT004 actual Fully Placed graph; four max_paths16/nworst1 through-LOAD queries only',review='INDEPENDENT_SUBSTEP_ACCEPTED_NO_NEW_GATE',
    actual_timing_validation=actual_id,projection_revision=identity(projection_path),projection_inputs=24,new_timing_inputs=7,unchanged_cut_projection_inputs=17,
    complete_replay_equal_actual=True,native64_start_end_clocks_slack_datapath_match=True,cut_review=identity(OUT/'place_directed_cut_review.json'),prior_parser_qualification=prior_id,
    current_index_epoch=index_epoch,current_log_path=str(log_path),cut_completion_line=cut_line,
    log_scope='Only actual closed events with line numbers; no whole mutable log hash. Ledger has no per-row epoch; current projection, index/cut lineage, native report dates and completed events bind actual phase.',
    query_sets=scope_counts,native_timing=raw_reviews,overlapping_start_end_clock_signatures_between_directions=overlap,
    identities=list(checked.values()),replay_program=identity(__file__),replay_output=identity(REPLAY/'candidate_timing_validation_place.json'),
    limits=['64 returned report rows are four capped queries, not an exhaustive unique-path count.',
      'Through-LOAD sets may return internal or externally driven paths; no assertion every result crosses the candidate boundary.',
      'Full-cut TNS not measured; LOGIC_DELAY and NET_DELAY remain UNKNOWN_UNSUPPORTED_PROPERTY.',
      'Bounded setup/hold observations do not replace global hold FAIL or routed timing signoff, and no causal improvement is inferred across stages.',
      'No DCP content reads/hashes, native queries, process/lock control or engineering writes.'])
output=OUT/'place_bounded_timing_review.json'
with output.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
human=OUT/'place_bounded_timing_review.md'
with human.open('x') as f:f.write('''# AT004 place 有界时序审核

execution：24项投影中新增7项时序输入独立核对，归档验证器完整重放；4组共64条原生报告行的起终点、时钟、slack、data path delay逐项匹配。verdict：接受完整方向查询集合及有界结果，INGRESS hold存在负slack。applicability：当前Fully Placed图。review：独立子步骤通过，无新增停点。

INGRESS20,534/EGRESS945个through-LOAD引脚，max/min各16条、nworst1。最差INGRESS setup/hold为+0.603/−0.221ns；EGRESS为+0.603/+0.057ns。本轮投影、index/cut lineage、报告日期和8条闭合BEGIN/END事件完成阶段绑定。

64是返回报告行数，不是穷举唯一path数；方向之间可返回重合路径。through-pin查询不保证每条路径跨候选边界，非full-cut TNS或正式时序签核。LOGIC_DELAY/NET_DELAY仍为UNKNOWN_UNSUPPORTED_PROPERTY，不补造数值；全局hold FAIL及正式reset/CDC/IO OPEN保持。不作跨阶段因果改善判断。
''')
print(json.dumps(dict(review=identity(output),human=identity(human),metrics=[{k:r[k] for k in metrics} for r in raw_reviews],overlap=overlap),ensure_ascii=False))

