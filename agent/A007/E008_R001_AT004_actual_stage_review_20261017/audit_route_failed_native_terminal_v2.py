#!/usr/bin/env python3
"""A007 review actual failed route and saved diagnostic text, without EDA/DCP access."""
import sys
sys.dont_write_bytecode=True
def guard(event,args):
    if event=='open' and args and isinstance(args[0],(str,bytes)):
        p=args[0].decode() if isinstance(args[0],bytes) else args[0]
        if p.lower().endswith('.dcp'):raise RuntimeError('A007 DCP content access forbidden')
sys.addaudithook(guard)
import ast,collections,csv,hashlib,json,math,re,tkinter
from pathlib import Path
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT=Path(__file__).resolve().parent
AT=ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation'
RPT=ROOT/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
OLD=ROOT/'project/hardware/vivado/reports/m002_E005_R004_AT004_default_route'
checks={}
def require(c,m):assert c,m
def identity(p):
    p=Path(p).resolve();assert p.suffix.lower()!='.dcp';a=p.stat();h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4194304),b''):h.update(b)
    z=p.stat();assert (a.st_size,a.st_mtime_ns)==(z.st_size,z.st_mtime_ns)
    v=dict(path=str(p),bytes=z.st_size,sha256=h.hexdigest());checks[str(p)]=v;return v
def verify(v):assert identity(v['path'])==v
def read(p):identity(p);return json.loads(Path(p).read_text())
def kv(p):identity(p);return dict(l.split('=',1) for l in Path(p).read_text().splitlines() if '=' in l)
def rows(p):
    identity(p)
    with Path(p).open() as f:r=list(csv.DictReader(f,delimiter='\t',quoting=csv.QUOTE_NONE))
    assert all(None not in v and all(x is not None for x in v.values()) for v in r);return r
def save(p,v):
    with p.open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
tcl=tkinter.Tcl()
def td(v):
    p=tcl.splitlist(v);assert len(p)%2==0;return dict(zip(p[::2],p[1::2]))
def utc(e):return datetime.fromtimestamp(int(e),timezone.utc).isoformat()
status=read(AT/'status.json');assert status['native_exit_code']==status['exit_code']==1
assert status['execution_state']=='completed' and status['native_natural_terminal_observed'] and status['stop_reason'] is None
assert not status['cleanup_was_required'] and status['owned_survivors']==[] and status['post_integrity_error'] is None
assert status['ended_utc']=='2026-10-17T21:18:30.695127+00:00'
physical=read(RPT/'E008_physical_evidence.json');assert physical['execution_state']=='failed' and physical['physical_signoff'] is False and physical['formal_reset_cdc_IO_safety']=='OPEN'
for v in physical['failed_route_artifacts']:
    if Path(v['path']).suffix.lower()=='.dcp':
        assert Path(v['path']).stat().st_size==v['bytes']==765705446
        dcp=dict(**v,reviewer_content_read_or_hash=False,identity_attribution='Engineering runtime evidence; reviewer verifies metadata size and native save message only')
    else:verify(v)
errpath=RPT/'route_failed_original_error.tcllist';identity(errpath);err=td(errpath.read_text())
assert err['code']=='1' and err['command']=='route_design -directive Default' and err['disposition']=='diagnostic_failed_route'
assert err['epoch']=='1792264165' and td(err['options'])['-code']=='1'
command=kv(RPT/'route_command_result.txt');assert command==dict(phase='route',command='route_design -directive Default',started_epoch='1792250294',ended_epoch='1792265317',native_tcl_code='1')
receipt=rows(RPT/'route_failed_capture_receipts.tsv');assert [r['label'] for r in receipt]==['checkpoint','route_status','timing','congestion','drc']
assert all(r['code']=='0' for r in receipt) and receipt[0]['started_epoch']==err['epoch'] and receipt[-1]['ended_epoch']==command['ended_epoch']
assert all(a['ended_epoch']==b['started_epoch'] for a,b in zip(receipt,receipt[1:]))
cap=RPT/'candidate_failed_route_capture.txt';identity(cap);assert td(cap.read_text())=={'code':'0','result':'','options':'-code 0 -level 0'}

def native(path):
    logid=identity(path);text=path.read_text();ls=text.splitlines()
    begin=next(i for i,l in enumerate(ls) if l=='Phase 8 Route finalize')
    phase9=next(i for i,l in enumerate(ls) if l=='Phase 9 Verifying routed nets')
    error=next(i for i,l in enumerate(ls) if l.startswith('ERROR: [Route 35-2]'))
    section='\n'.join(ls[begin:phase9]);final='\n'.join(ls[phase9:error+1])
    overlaps=int(re.search(r'There are (\d+) node overlaps',final)[1]);signals=int(re.search(r'\[Route 35-162\] (\d+) signals failed to route due to routing congestion',final)[1])
    assert int(re.search(r'Number of Node Overlaps\s*=\s*(\d+)',section)[1])==overlaps
    init={k:int(re.search(r'Number of '+k+r'\s*=\s*(\d+)',section)[1]) for k in ['Failed Nets','Unrouted Nets','Partially Routed Nets']};assert set(init.values())=={0}
    congestion=[]
    for m in re.finditer(r'(North|South|East|West) Dir (\d+x\d+) Area, Max Cong = ([\d.]+)%,[^\n]*\n((?:   INT_[^\n]+\n)+)',section+'\n'):
        congestion.append(dict(direction=m[1],window=m[2],percent=float(m[3]),tiles=m[4].splitlines()))
    assert len(congestion)==4 and 'computation: 0.85' in section
    return dict(identity=logid,phase8_first_line=begin+1,phase9_first_line=phase9+1,illegal_route_error_line=error+1,node_overlaps=overlaps,congestion_failed_signals=signals,phase8_zero_unrouted_counts=init,congestion_threshold=.85,final_adaptive_congestion=congestion),text,ls
current,log,ls=native(RPT/'vivado.log');old,oldlog,oldls=native(OLD/'vivado.log')
assert (current['node_overlaps'],current['congestion_failed_signals'])==(702396,547548)
assert (old['node_overlaps'],old['congestion_failed_signals'])==(1148579,758463)
for txt in [log,oldlog]:assert 'Vivado v2025.2 (64-bit)' in txt and 'SW Build 6299465' in txt and 'Command: route_design -directive Default' in txt
assert 'has been generated.' in next(l for l in ls if "checkpoint '" in l and '/route_failed.dcp' in l)
localityline=next(i+1 for i,l in enumerate(ls) if l=='E008_STAGE_COMPLETED locality_route_failed')
propagated=next(i+1 for i,l in enumerate(ls) if i+1>localityline and l.startswith('ERROR: [Common 17-39]'))
assert propagated==localityline+1 and "Exiting Vivado at Sun Oct 18 05:18:17 2026" in log
excerpt=OUT/'route_failed_native_terminal_excerpt_v2.json'
save(excerpt,dict(source=current['identity'],ranges=[dict(first=current['phase8_first_line'],last=current['illegal_route_error_line'],lines=ls[current['phase8_first_line']-1:current['illegal_route_error_line']]),dict(first=254727,last=254759,lines=ls[254726:254759]),dict(first=339097,last=len(ls),lines=ls[339096:])]))
def route_status(p):
    identity(p);text=p.read_text();d={}
    for name,value in re.findall(r'# of ([^\n]+?)\.+\s*:\s*(\d+)',text):d[name]=int(value)
    assert d['routable nets']==d['fully routed nets']+d['nets with routing errors']
    assert d['nets with routing errors']==d['nets with resource conflicts'];return d
current_status=route_status(RPT/'route_failed_status.rpt');old_status=route_status(OLD/'route_failed_status.rpt')
assert current_status['nets with resource conflicts']==current['congestion_failed_signals'] and old_status['nets with resource conflicts']==old['congestion_failed_signals']
deltas={k:dict(old=old[k],current=current[k],difference=current[k]-old[k],decrease_percent=(old[k]-current[k])/old[k]*100) for k in ['node_overlaps','congestion_failed_signals']}

parser=ROOT/'project/hardware/vivado/scripts/m002_physical_evidence.py';assert identity(parser)['sha256']=='9444d1a5127ec5e7c0174df1f70dc72f5bf77df124a307b939defcb25207dac9'
ns=dict(Path=Path,re=re,math=math,require=require)
defs=[n for n in ast.parse(parser.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in {'timing_metrics','timing_verdict'}]
assert len(defs)==2;exec(compile(ast.Module(body=defs,type_ignores=[]),str(parser),'exec'),ns)
timings={}
for name,folder in [('current',RPT),('old',OLD)]:
    p=folder/'route_failed_timing.rpt';identity(p);timings[name]=ns['timing_metrics'](p);assert ns['timing_verdict'](timings[name])=='FAIL'
assert timings['current']['wns']==-12.413 and timings['current']['whs']==-.125 and timings['current']['wpws']==-.664
drc=(RPT/'route_failed_drc.rpt').read_text();drcrows=[]
for rule,severity,desc,count in re.findall(r'^\|\s*(\S+)\s*\|\s*(Critical Warning|Warning|Error)\s*\|([^|]+)\|\s*(\d+)\s*\|',drc,re.M):drcrows.append(dict(rule=rule,severity=severity,description=desc.strip(),checks=int(count)))
assert sum(r['checks'] for r in drcrows)==15918 and sum(r['checks'] for r in drcrows if r['severity']=='Critical Warning')==1
assert sum(r['checks'] for r in drcrows if r['severity']=='Warning')==15917 and not any(r['severity']=='Error' for r in drcrows)
assert 'Routed nets status (RTSTAT-*) DRC checks will not be run' in drc

# Current failed-route C01 correspondence and actual placement, independent of route legality.
original={r['NAME']:r['REF_NAME'] for r in rows(RPT/'candidate_P_pre_place.tsv')}
literal={r['NAME']:r for r in rows(RPT/'candidate_physical_members_route_failed.tsv')}
pb={r['NAME']:r for r in rows(RPT/'candidate_pblock_actual_route_failed.tsv')}
lineage=rows(RPT/'candidate_reconciliation_route_failed.tsv');rec=read(RPT/'candidate_reconciliation_route_failed.json')
assert len(original)==len(literal)==len(pb)==len(lineage)==9491 and set(original)==set(literal)==set(pb)=={r['NAME'] for r in lineage}
assert rec['qualified'] and not rec['issues'] and not rec['explained_replacements'] and rec['resolved']==original and [{k:r[k] for k in lineage[0]} for r in rec['lineage']]==lineage
assert all(r['REF_NAME']==original[n] and r['SLR']=='SLR2' and r['LOC'] for n,r in literal.items())
assert all(r['SLR']=='SLR2' and r['LOC']==literal[n]['LOC'] for n,r in pb.items())
assert all(r['lineage']=='ORIGINAL_SURVIVING' and r['SLR']=='SLR2' and r['LOC']==literal[r['NAME']]['LOC'] for r in lineage)
adapter=RPT/'stage_sources/evidence_adapter.py';assert identity(adapter)['sha256']=='a6c0a4d9402f7806824405dd63a46cbdba86a761efe48f7ac5ee73affce1b21c'
saved={}
def capture(path,v):assert Path(path)==RPT/'candidate_compliance_route_failed.json';saved[str(path)]=v
defs=[n for n in ast.parse(adapter.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in {'rows','compliance'}]
cns=dict(Path=Path,csv=csv,json=json,collections=collections,e=SimpleNamespace(require=require,file_id=identity,key_values=kv),directed=SimpleNamespace(VERSION='candidate_directed_cut_v1'),save=capture)
exec(compile(ast.Module(body=defs,type_ignores=[]),str(adapter),'exec'),cns)
compliance=cns['compliance']('route_failed',RPT);assert compliance==read(RPT/'candidate_compliance_route_failed.json')==saved[str(RPT/'candidate_compliance_route_failed.json')]
assert compliance['compliance_established'] and compliance['selected_SLR_counts']=={'SLR2':9491}
effective=kv(RPT/'candidate_effective_pblock_route_failed.txt');assert all(effective[k]=='0' for k in ['IS_SOFT','EXCLUDE_PLACEMENT','CONTAIN_ROUTING'])
absence={name:not (RPT/name).exists() for name in ['route.dcp','route_result.txt','candidate_phase_route_status.txt','bus_skew_route.rpt','bus_skew_route_failed.rpt','pulse_width_route.rpt']};assert all(absence.values())
accepted={}
for name,digest in [('place_combined_stage_review','d360c153a9f8d97d12398394cc0538fa24fefc13c6e97feed5e7285e73f0f362'),('physopt_combined_stage_review','205b56d13bcccd61490888629aef8f2c31bae2e3962c94504fabb58893342505'),('route_initial_global_warnings_review','102647cbf5bd2b6554abae89d91409001167ece69cba46c919f3ba6dc4075d96')]:
    v=identity(OUT/(name+'.json'));assert v['sha256']==digest;accepted[name]=v
times=dict(route_start_utc=utc(command['started_epoch']),native_error_caught_utc=utc(err['epoch']),five_failure_captures_completed_and_route_wrapper_returned_utc=utc(command['ended_epoch']),native_tool_exit_utc='2026-10-17T21:18:17+00:00',supervisor_terminal_utc=status['ended_utc'],native_route_through_error_capture_seconds=int(err['epoch'])-int(command['started_epoch']),failure_capture_seconds=int(command['ended_epoch'])-int(err['epoch']),full_attempt_seconds=(datetime.fromisoformat(status['ended_utc'])-datetime.fromisoformat(status['started_utc'])).total_seconds(),note='Original-error catch is the first recorded epoch after native route failure, not an exact timestamp for the earlier Phase9 error. Wrapper includes five diagnostic captures; supervisor terminal additionally includes candidate failed-route locality and cleanup verification.')
out=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),reviewer='A007',execution='NATIVE_ROUTE_FAILED_NATURALLY; FIVE_FAILURE_CAPTURES_AND_FAILED_ROUTE_LOCALITY_COMPLETED; SUPERVISOR_TERMINAL_1',verdict='LEGAL_ROUTING_FAIL; FAILED_GRAPH_SETUP_HOLD_PW_FAIL_DIAGNOSTIC_ONLY; C01_ACTUAL_SLR2_PLACEMENT_COMPLIANCE_RETAINED; FORMAL_RESET_CDC_IO_OPEN',applicability='AT004 C01 current failed route; native final legality compared only with E005 R004 AT004 final legality; no generalized method verdict or physical signoff',review='INDEPENDENT_NATIVE_FAILURE_AND_SAVED_DIAGNOSTIC_REVIEW_COMPLETE; TERMINAL_OWNERSHIP_INPUT_CLOSURE_SEPARATE',status=identity(AT/'status.json'),current_native=current,old_native=old,same_stage_final_count_comparison=deltas,current_route_status=current_status,old_route_status=old_status,time_boundaries=times,original_error=err,native_capture_receipts=receipt,candidate_failure_capture_code_zero=True,locality_completion_native_line=localityline,propagated_original_error_native_line=propagated,failed_DCP=dcp,diagnostic_timing=timings,timing_deltas_diagnostic_only={k:timings['current'][k]-timings['old'][k] for k in timings['current']},DRC=dict(rows=drcrows,total=15918,critical_warnings=1,warnings=15917,errors=0,route_status_checks_not_run=True,not_legal_routing_pass=True),candidate_compliance=compliance,independent_candidate_correspondence=dict(original=9491,current=9491,actual_Pblock=9491,all_original_surviving_SLR2=True,missing_or_replaced=0,pure_compliance_replay_exact=True),absent_success_and_full_route_reports=absence,accepted_prior_reviews_preserved=accepted,native_excerpt=identity(excerpt),limits=[
    'Phase8 zero unrouted/partial counters and timing header Routed do not supersede Phase9 illegal-routing error and547548 resource-conflict nets.',
    'Final count reductions38.8465%/27.8082% are global outcomes of different physical solutions, not C01 causal proof, fixed-hotspot relief, near-success or a legal-route result.',
    'Final adaptive N/S windows are64x64 in both runs but selected coordinates differ; E/W changed64x64 to32x32. Do not present all four maxima as a fixed-window improvement.',
    'Saved congestion report contains placer-final/router-initial diagnostics; actual end-of-route congestion above is from the Phase8 native log, not inferred from filename.',
    'Concrete C01 configuration failed routability acceptance. Actual C01 migration remains supported. This is native design congestion/legality failure, not a model-capacity interruption or evidence that all targeted offload methods are invalid.',
    'Five diagnostic capture commands code0 and locality code0 preserve evidence; they do not turn native route1 into successful implementation or complete global route POST.',
    'Fresh failed-route full bus-skew report absent; six unpopulated paths and one ignored group from accepted route warning review remain unresolved. Earlier94 MET is not final coverage or safety.',
    'Failed-route candidate cut and four timing artifacts are saved and bound by compliance; this bounded review does not replay every cut endpoint, native index alias or full timing report row.',
    'No EDA/native queries, DCP content reads/hash, process/lock control, new implementation or production edits.'
],all_identity_checks=list(checks.values()),audit_program=identity(__file__))
out['reviewer_harness_correction']='Preserved v1 asserted full JSON lineage rows equal TSV rows; JSON legitimately adds physical_NAME. v2 compares all actual TSV fields and separately verifies exact physical NAME correspondence. This is a reviewer projection correction, not design/tool failure.'
dest=OUT/'route_failed_native_terminal_review.json';save(dest,out)
human=OUT/'route_failed_native_terminal_review.md'
with human.open('x') as f:f.write('''# AT004 最终布线失败独立审核

execution：原生 route 自然失败，五项失败诊断及 locality_route_failed 成功保存，监督进程自然结束。verdict：合法布线 FAIL；失败图 setup/hold/脉宽诊断均 FAIL；C01 实际 SLR2 符合性保持；正式 reset/CDC/IO 安全 OPEN。review：本记录完成原生失败与保存诊断审核，输入/进程/资源收尾单列。

| 同阶段最终指标 | 旧 E005 | 本次 E008 | 变化 |
| --- | ---: | ---: | ---: |
| node overlaps | 1,148,579 | 702,396 | −38.8465% |
| 拥塞失败信号/资源冲突 nets | 758,463 | 547,548 | −27.8082% |

本次原生日志 254584 行 Route35-162、254702 行 Route35-2 和失败 route-status 报告相互一致。2,031,733 个 routable nets 中，1,484,185 fully routed、547,548 resource conflicts。Phase8 的 unrouted/partial=0 及 timing 报告标题 Routed 不推翻最终非法布线。计数下降是不同全局物理解的结果，不能归因 C01、声称固定热点改善或接近布通。

时间分层：北京时间 10/18 03:09:25 捕获原生 route 错误；03:28:37 完成失败 DCP/status/timing/congestion/DRC 五项诊断并从 route wrapper 返回；05:18:17 Vivado 在 locality_route_failed 完成后重抛原错误退出；05:18:30.695127 监督终态。native/监督均 1，stop_reason=null、natural=true、无 cleanup。这些时间不能全部计作纯 route 耗时，也不能把模型容量错误当作本次布线失败原因。

失败图 WNS −12.413 ns、TNS −915,419.312 ns、418,798 setup 违例端点；WHS −0.125 ns、THS −41.550 ns、3,264 hold 违例端点；WPWS −0.664 ns、TPWS −2.171 ns、8 个脉宽/偏斜违例端点。均为非法路由图诊断，不能签核。DRC 为 1 个 RTSTAT-13 Critical Warning、15,917 Warning、0 Error；RTSTAT-13 明确未运行完整 routed-net 状态检查，0 Error 不等于布通。

当前实际 C01 原始 9,491 个物理成员逐名对应、全部存活于 SLR2，无缺失/替换；Pblock 和位置数据相互一致，compliance 纯函数重放与产物完全一致。该迁移事实保持，但本次配置未通过完整物理验收；不能由一次失败推断所有定向卸载方法无效。

五项失败诊断原生回执均 0。失败 DCP 为 765,705,446 字节，SHA 由工程证据提供；本审核只核文件大小和原生保存消息，没有读取或 hash DCP。无成功 route.dcp、成功 route POST 回执、最终 bus-skew 报告；此前 6 条未 populate 路径和 1 个 ignored 组仍是覆盖缺口。locality 成功仅说明失败图采证完成。

最终自适应拥塞 N/S 为 64×64、E/W 为 32×32，旧 E005 四方向均为 64×64，坐标也有变化；不能将四方向最大值直接解释为固定窗口改善。完整 cut/有界时序文件已保存并绑定，本次有界审核未重放其中所有端点或 native alias。

详见 [JSON 审核记录](route_failed_native_terminal_review.json)。未启动 EDA、新 implementation，未控制进程或锁，未改生产文件。
''')
print(json.dumps(dict(review=identity(dest),human=identity(human),comparison=deltas,time_boundaries=times),ensure_ascii=False))
