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
REPLAY = OUT / 'bounded_timing_pre_place_replay'
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

cut_review = read(OUT / 'pre_place_directed_cut_incremental_review.json')
projection_path = REPORT / 'candidate_directed_validation_pre_place/projection_identity_1.json'
projection = read(projection_path)
first = read(REPORT / 'candidate_directed_validation_pre_place/projection_identity.json')
assert len(projection['inputs']) == 24 and len(first['inputs']) == 17
assert projection['phase'] == 'pre_place' and projection['actual_P'] == projection['literal_P_preserved'] == first['actual_P']
assert projection['P_source'] == 'literal actual pre-place P'
assert all(projection['inputs'][key] == value for key,value in first['inputs'].items())
new_inputs = {key:value for key,value in projection['inputs'].items() if key not in first['inputs']}
assert len(new_inputs) == 7
for name,row in new_inputs.items():
    assert identity(row['path']) == row
    target = projection_path.parent/name
    assert target.is_symlink() and target.resolve() == Path(row['path'])
    (REPLAY/name).symlink_to(row['path'])
scope = 'candidate_boundary_timing_scope_pre_place.tsv'
assert identity(first['inputs'][scope]['path']) == first['inputs'][scope]
(REPLAY/scope).symlink_to(first['inputs'][scope]['path'])

sys.path.insert(0,str(SOURCES))
import directed_evidence as directed
directed.identity = identity
timing = directed.timing('pre_place',REPLAY)
actual_path = REPORT/'candidate_timing_validation_pre_place.json'
actual_id = identity(actual_path)
assert actual_id['sha256'] == '98d95826f0bf0e133f654976cdcaf441ddd72969fb03615af6bcf483c5ab0b54'
actual = read(actual_path)
assert actual['phase'] == 'pre_place' and timing == {key:value for key,value in actual.items() if key!='phase'}
scope_counts = {key:len(value) for key,value in timing['query_sets'].items()}
assert scope_counts == cut_review['exported_boundary_through_pin_sets'] == {'INGRESS':20534,'EGRESS':945}

log_path = REPORT/'vivado.log'
log_events = []; cut_line = None
with log_path.open() as stream:
    for number,line in enumerate(stream,1):
        if line.startswith('DIRECTED_CUT_COMPLETED point=pre_place '): cut_line=number
        if line.startswith('DIRECTED_API operation BOUNDED_TIMING '):
            parts = directed.split(line)
            event = dict(zip(parts[1::2],parts[2::2]))
            if event['point']=='pre_place': log_events.append(dict(line_number=number,text=line.rstrip(),fields=event))
assert len(log_events) == 8 and cut_line < log_events[0]['line_number']
index_epoch = read(REPORT/'candidate_top_port_index_closed_pre_place.json')['epoch_id']
epoch_ms = int(directed.split(index_epoch)[1])//1000
assert all(int(row['fields']['epoch_ms']) > epoch_ms for row in log_events)
events_by_query = defaultdict(dict)
for row in log_events:
    value=row['fields']; key=(value['direction'],value['delay_type'])
    assert value['event'] not in events_by_query[key]
    events_by_query[key][value['event']]=row

records=list(directed.rows(REPORT/'candidate_scoped_timing_pre_place.tsv'))
by_query=defaultdict(list)
for row in records: by_query[(row['direction'],row['delay_type'])].append(row)
raw_reviews=[]
for key, values in sorted(by_query.items()):
    direction,kind=key
    events=events_by_query[key]
    assert set(events)=={'BEGIN','END'} and events['END']['fields']['returned_paths']=='16'
    begin=int(events['BEGIN']['fields']['epoch_ms']); end=int(events['END']['fields']['epoch_ms'])
    assert begin<=end
    report=REPORT/f'candidate_cut_timing_pre_place_{direction}_{kind}.rpt'
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
    assert header['Design State']=='Optimized' and header['Design']=='scalellm_vcu118_f05_bd_wrapper'
    assert 'Vivado v.2025.2' in header['Tool Version'] and 'Build 6299465' in header['Tool Version']
    stamp=datetime.strptime(header['Date'],'%a %b %d %H:%M:%S %Y').replace(tzinfo=timezone(timedelta(hours=8)))
    assert begin//1000<=int(stamp.timestamp())<=end//1000+5
    raw_reviews.append(dict(direction=direction,delay_type=kind,queried_pins=scope_counts[direction],returned_paths=len(values),worst_slack_ns=min(float(v['SLACK']) for v in values),negative_slack_paths=sum(float(v['SLACK'])<0 for v in values),native_report=identity(report),header=header,actual_log_events=events,all16_raw_identity_clocks_slack_datapath_matches=True))

prior_path=ROOT/'agent/A007/E008_R001_AT003_actual_stage_review_20261017/pre_place_directed_cut_timing_review.json'
prior=read(prior_path)
assert identity(prior_path)['sha256']=='3fd4120659d5d384c551d623ca63d6aaa1a09ff39ecd6c1f74fda46853acffd5'
assert identity(prior['actual_timing_validation']['path'])==prior['actual_timing_validation']
old=read(prior['actual_timing_validation']['path'])
assert {k:v for k,v in actual.items() if k!='artifacts'}=={k:v for k,v in old.items() if k!='artifacts'}
metrics=['direction','delay_type','queried_pins','returned_paths','worst_slack_ns','negative_slack_paths']
assert [{k:r[k] for k in metrics} for r in raw_reviews]==[{k:r[k] for k in metrics} for r in prior['bounded_timing']]
assert identity(SOURCES/'directed_evidence.py')['sha256']==prior['validator']['sha256']

result=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),reviewer='A007',
    execution='completed_actual_AT004_bounded_timing_text_replay_and_all64_native_path_checks',
    verdict='accepted_complete_directional_query_sets_and_bounded_native_results',
    applicability='AT004 pre_place restored optimized graph; four max_paths16/nworst1 through-LOAD queries only',
    review='accepted_no_new_gate',actual_timing_validation=actual_id,projection_revision=identity(projection_path),
    projection_inputs=24,new_timing_inputs=7,unchanged_cut_projection_inputs=17,
    complete_replay_equal_actual=True,native64_start_end_clocks_slack_datapath_match=True,
    cut_review=identity(OUT/'pre_place_directed_cut_incremental_review.json'),prior_AT003_review=identity(prior_path),
    current_index_epoch=index_epoch,current_log_path=str(log_path),cut_completion_line=cut_line,
    live_log_note='Only completed bounded timing lines observed and embedded with line numbers; no immutable whole-log hash claim. Timing query ledger has no per-row epoch field; current-stage binding uses projection, current index/cut lineage, native report dates and completed log events.',
    query_sets=scope_counts,native_timing=raw_reviews,semantic_validation_and_metrics_equal_AT003=True,
    identities=list(checked.values()),replay_program=identity(__file__),replay_output=identity(REPLAY/'candidate_timing_validation_pre_place.json'),
    limits=['All associated cut positions are UNPLACED; layout estimates do not demonstrate physical improvement.',
            'Through-pin LOAD queries may return internal or externally driven paths; no claim every returned path crosses candidate boundary.',
            'Four capped queries, not exhaustive path enumeration, full-cut TNS or formal timing signoff.',
            'LOGIC_DELAY/NET_DELAY properties remain UNKNOWN_UNSUPPORTED_PROPERTY; no substitute invented.',
            'No full pre_place/place/route acceptance in this record; no DCP content read/hash or EDA/process control.'])
output=OUT/'pre_place_bounded_timing_incremental_review.json'
with output.open('x') as stream:stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
human=OUT/'pre_place_bounded_timing_incremental_review.md'
with human.open('x') as stream:
    stream.write('# AT004 pre-place 有界时序增量审核\n\n'
                 '- execution：实际归档验证器重放完成；四组共 64 条原生路径的起点、终点、起终时钟、slack 和 data path delay 与表逐项一致。当前报告日期及原生日志的完成事件绑定通过。\n'
                 '- verdict：接受完整方向查询集合及有界结果。INGRESS 20,534 / EGRESS 945 个 LOAD 引脚，max/min 各 16 条、nworst 1。最差 setup 入/出为 +6.158 / +6.859 ns；最差 hold 为 −0.074 / +0.081 ns。语义及统计与已审 AT003 一致。\n'
                 '- applicability：仅本轮未布局的 Optimized 图。through-pin 查询可能返回内部或外部驱动路径，并不保证逐路径跨候选边界；非 full-cut TNS、时序签核或迁移改善。查询 ledger 无逐行 epoch，绑定依据为本轮投影、index/cut、报告日期及已完成日志事件。\n'
                 '- review：本子步骤接受，无新增执行停点。完整 pre-place 与 place/route 另行审核；未读取或哈希 DCP。\n\n'
                 '[机器审核与 64 条路径核对结果](pre_place_bounded_timing_incremental_review.json)\n')
print(json.dumps(dict(review=identity(output),human=identity(human),metrics=[{k:r[k] for k in metrics} for r in raw_reviews]),ensure_ascii=False))
