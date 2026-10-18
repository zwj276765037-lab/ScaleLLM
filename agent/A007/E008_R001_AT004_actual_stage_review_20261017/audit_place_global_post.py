#!/usr/bin/env python3
"""A007 actual global place POST: text replay only; DCP content denied."""
import sys
sys.dont_write_bytecode=True
def guard(event,args):
    if event=='open' and args and isinstance(args[0],(str,bytes)):
        p=args[0].decode() if isinstance(args[0],bytes) else args[0]
        if p.lower().endswith('.dcp'):raise RuntimeError('A007 DCP content access forbidden')
sys.addaudithook(guard)
import ast,csv,hashlib,json,math,re
from pathlib import Path
from functools import cache
from collections import Counter
from datetime import datetime,timezone
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
RPT=ROOT/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
AT=ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation'
OUT=Path(__file__).resolve().parent
checks={}
def require(c,m):assert c,m
def identity(path):
    p=Path(path).resolve();assert p.suffix.lower()!='.dcp'
    before=p.stat();h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    v=dict(path=str(p),bytes=after.st_size,sha256=h.hexdigest());checks[str(p)]=v;return v
def verify(v):
    actual=identity(v['path']);assert actual['bytes']==v['bytes'] and actual['sha256']==v['sha256'],v['path'];return actual
def sha256(p):return identity(p)['sha256']
def read(p):return json.loads(Path(p).read_text())
def kv(p):return dict(x.split('=',1) for x in Path(p).read_text().splitlines() if '=' in x)
def save(p,v):
    with p.open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def canonical(v):
    if isinstance(v,dict):return {k:canonical(x) for k,x in v.items()}
    if isinstance(v,list):return sorted((canonical(x) for x in v),key=lambda x:json.dumps(x,sort_keys=True))
    return v

priorpath=OUT/'restored_pre_place_global_incremental_review.json'
priorid=identity(priorpath);assert priorid['sha256']=='2b5963a1f6489077b9644a2d8cc0a38b592e9c67f6a32a2820251c774c0f0587'
prior=read(priorpath);previous={v['path']:v for v in prior['all_identity_checks']}
factpath=AT/'place_global_POST_closed_facts.json';factid=identity(factpath)
assert factid['sha256']=='51ce8a5201ac96fc6e6b7ba869c48130f4ec30e084126e89757127ee8b457623'
facts=read(factpath)
for v in facts['artifacts']:verify(v)
for k in ['checkpoint_saved_identity','input_bindings','source_manifest']:verify(facts[k])
integrity=read(RPT/'integrity_place.json');assert integrity['phase']=='place' and integrity['gate_issues']==[]
result=kv(RPT/'place_result.txt')
assert result==dict(completed='1',diagnostic_eligible='1',debug_materialization_eligible='0',phase='place',blackboxes='0',clock_coverage='COMPLETE_INTERNAL',physical_signoff='false',reset_io_review='OPEN',cdc_review='OPEN')
assert result==facts['actual_native_global_POST_result']
binding=read(AT/'input_bindings.json');verify(binding['parent']);parent=read(binding['parent']['path'])
assert integrity['synthesis']==parent['synthesis']
for v in integrity['synthesis'].values():
    if isinstance(v,dict) and set(v)=={'path','bytes','sha256'}:verify(v)
for v in binding['source_bindings']:
    verify(v);archive=identity(RPT/'stage_sources'/Path(v['path']).name)
    assert (archive['bytes'],archive['sha256'])==(v['bytes'],v['sha256'])
assert len(binding['source_bindings'])==39
verify(binding['frozen_inputs']['freeze']);production=read(binding['frozen_inputs']['freeze']['path'])['files'];assert len(production)==144
for v in production:verify(v)

# Fresh phase constraints compared with accepted original-source and overlay qualification.
verify(integrity['constraints']);constraints=read(RPT/'constraints_place.json')
verify(constraints['parent']);pre=read(constraints['parent']['path'])
assert Path(constraints['parent']['path']).name=='constraints_pre_place_restore.json'
assert constraints['phase']=='place' and constraints['mode']=='embedded_checkpoint_inherited'
for k in ['hashes','metadata','candidate_metadata','source_archives','generated_source_candidates','tool_debug_metadata','candidate_physical_overlay']:
    assert constraints[k]==pre[k],k
assert len(constraints['hashes'])==175 and len(constraints['metadata'])==162 and len(constraints['source_archives'])==13
for path,digest in constraints['hashes'].items():
    p=Path(path)
    if not p.is_file():v=constraints['source_archives'][path];verify(v);p=Path(v['path'])
    assert sha256(p)==digest
verify(constraints['registry']);verify(constraints['actual_reads'])
registry=list(csv.DictReader(Path(constraints['registry']['path']).open(),delimiter='\t'))
fields=['USED_IN','USED_IN_SYNTHESIS','USED_IN_IMPLEMENTATION','IS_ENABLED','SCOPED_TO_REF','SCOPED_TO_CELLS','PROCESSING_ORDER']
assert len(registry)==162 and len({v['path'] for v in registry})==162
assert {v['path']:[v[k] for k in fields] for v in registry}==constraints['metadata']==constraints['candidate_metadata']
assert all(v['SHA256']==constraints['hashes'][v['path']] for v in registry)
reads=read(constraints['actual_reads']['path'])
assert reads==dict(mode='embedded_checkpoint_inherited',inherited_from=binding['parent'],new_actual_reads=[])
for v in constraints['candidate_physical_overlay']['artifacts'].values():verify(v)

# AST selects inspected pure functions only; no module import/hook/recovery/checkpoint code.
src=RPT/'stage_sources/m002_physical_evidence.py';srcid=identity(src);assert srcid==previous[str(src)]
functions={'bram_write_clock','auxiliary_cdc_limits','reset_fanout','primitive_defaults','primitive_overrides','reset_structure','verify_reset_proof','cdc_critical_records','opt_reset_cdc_rows','qualified_aux_representatives','critical_coverage','verify_cdc_proof','check_timing_counts','timing_objects','reset_io_coverage','placement_coverage','utilization_metrics'}
constants={'PRIMITIVE_MODEL_ROOT','PRIMITIVE_MODEL_HASHES','BRAM_MODEL_HASHES','TARGETED_OPT_REPORT_HASHES'}
body=[n for n in ast.parse(src.read_text()).body if (isinstance(n,ast.FunctionDef) and n.name in functions) or (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in constants for t in n.targets))]
assert {n.name for n in body if isinstance(n,ast.FunctionDef)}==functions
namespace=dict(Path=Path,re=re,math=math,json=json,cache=cache,ROOT=ROOT/'project/hardware',file_id=identity,sha256=sha256,verify_identity=verify,require=require)
exec(compile(ast.Module(body=body,type_ignores=[]),str(src),'exec'),namespace)
assert 'TARGETED_CDC_VIOLATIONS_UNKNOWN' not in (RPT/'cdc_changed_reset_place.tsv').read_text()
structure=namespace['reset_structure'](RPT/'reset_graph_place.tsv')
assert structure==integrity['reset_structure'] and structure['qualified'] and structure['issues']==[]
fanout=namespace['reset_fanout'](RPT/'cdc_changed_reset_place.tsv',RPT/'bram_port_clocks_place.tsv')
assert canonical(fanout)==canonical(integrity['reset_fanout_observation']) and fanout['qualified'] and fanout['issues']==[]
original=Path(integrity['synthesis']['manifest']['path']).parent/'cdc_post_synth.rpt';identity(original)
cdc=namespace['critical_coverage'](RPT/'cdc_place.rpt',original,structure,fanout)
assert cdc==integrity['cdc_classification'];namespace['verify_cdc_proof'](cdc)
assert cdc['formal_reset_cdc_safety']=='OPEN' and cdc['new_critical']==0 and len(cdc['actual_aux_representative_sources'])==4
counts=namespace['check_timing_counts'](RPT/'check_timing_place.rpt')
assert namespace['placement_coverage'](counts,0) and counts['constant_clock']==0
io=namespace['reset_io_coverage'](RPT/'check_timing_place.rpt');assert io==integrity['reset_io_classification']
resources=namespace['utilization_metrics'](RPT/'utilization_place.rpt');assert resources==integrity['resources']==facts['actual_resources']

# Reuse accepted current timing/fresh80/congestion without reinterpreting their scope.
reuse={}
for name,digest in [('place_full_timing_report_review.json','386dced9df9391fb485a45d1f0847247683f7afb4e3910a4563eecc3861219b4'),('place_fresh80_structure_review.json','6d65874583f952cbb619f6cc865da1433c8108af117cd80618b293e4c0c2834a'),('place_congestion_scope_review.json','4a2e0c1236c58fb5ce345e12d447f1dcec3dd76dac81849c037be0f1443b151c')]:
    v=identity(OUT/name);assert v['sha256']==digest;review=read(OUT/name);reuse[name]=dict(identity=v,verdict=review['verdict'],applicability=review['applicability'])
    if 'actual_report' in review:verify(review['actual_report'])
    for artifact in review.get('actual_artifacts',[]):verify(artifact)
timing=read(OUT/'place_full_timing_report_review.json')['current']
clockrows=re.findall(r'^(\S+)\s+([\d.]+)\s+(\{[\d.]+ [\d.]+\})\s+([A-Z,]+)\s+(.+)$',(RPT/'clocks_place.rpt').read_text(),re.M)
clocks={n:dict(period_ns=float(p),waveform=w,attributes=a,sources=s) for n,p,w,a,s in clockrows}
assert len(clocks)==len(clockrows)==len(timing['clocks'])==50
assert {x['name']:(x['period_ns'],x['waveform']) for x in timing['clocks']}=={n:(x['period_ns'],x['waveform']) for n,x in clocks.items()}
assert clocks['clk_out1_scalellm_vcu118_f05_bd_clk_core_0']['period_ns']==10.0
assert clocks['mmcm_clkout0']['period_ns']==clocks['mmcm_clkout0_1']['period_ns']==5.0

# DRC severity and detail counts; RTSTAT-13 is retained, not silently waived.
drctext=(RPT/'drc_place.rpt').read_text()
drcrows=re.findall(r'^\|\s*([A-Z]+-\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|$',drctext,re.M)
declared={rule:(severity,int(n)) for rule,severity,description,n in drcrows}
observed=Counter(re.findall(r'^(\S+)#\d+ (Warning|Critical Warning|Error)$',drctext,re.M))
assert len(declared)==len(drcrows)==8 and {k:(s,observed[(k,s)]) for k,(s,n) in declared.items()}==declared
assert sum(n for s,n in declared.values())==15918==int(re.search(r'Checks found:\s+(\d+)',drctext)[1])
assert declared['RTSTAT-13']==('Critical Warning',1) and sum(n for s,n in declared.values() if s=='Warning')==15917
assert not any(s=='Error' for s,n in declared.values())
assert 'A signficant portion of the design is not routed.' in drctext and 'DRC checks will not be run.' in drctext
drc=dict(rules=[dict(rule=r,severity=s,description=d,checks=int(n)) for r,s,d,n in drcrows],error=0,critical_warning=1,warning=15917,design_state='Partially Routed',route_check_limitation='RTSTAT-13: significant portion not routed; routed-net status checks not run',formal_route_DRC_signoff=False)

# Bus-skew summary and every per-constraint worst slack must agree.
bus=(RPT/'bus_skew_place.rpt').read_text();summary=bus[:bus.rfind('2. Bus Skew Report Per Constraint')]
busrows=re.findall(r'^\s+(Slow|Fast)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s*$',summary,re.M)
detail=re.findall(r'Slack \((MET|VIOLATED)\)\s*:\s*([\d.-]+)ns',bus)
assert len(busrows)==len(detail)==94
assert [float(x[-1]) for x in busrows]==[float(x[1]) for x in detail]
assert all(abs(float(req)-float(actual)-float(slack))<=0.0011 for _,req,actual,slack in busrows)
assert all(status=='MET' and float(slack)>=0 for status,slack in detail)
busfacts=dict(constraints=94,reported_violated=0,worst_reported_slack_ns=min(float(v[1]) for v in detail),summary_and_each_detail_agree=True,scope='Current place report only; no safety/routed signoff')
pulse=(RPT/'pulse_width_place.rpt').read_text();assert pulse.split('Pulse Width Report',1)[1].strip()==''
exceptiontext=(RPT/'exceptions_place.rpt').read_text()
exceptionrows=[x for x in exceptiontext.splitlines() if re.match(r'^\d+\s{2,}',x)]
exceptiontypes=Counter(re.match(r'^\d+\s{2,}(.+?)\s{2,}',x)[1] for x in exceptionrows)
assert dict(exceptiontypes)=={'False Path':334,'Multicycle Path':12,'Max Delay Datapath Only':238}
exheaders=next(x for x in exceptiontext.splitlines() if x.startswith('Position  Type'))
starts=[exheaders.index(x) for x in ['Position','Type','Setup','Hold','From','Through','To','Endpoints','From (%)','Through (%)','To (%)']]
exparsed=[]
for line in exceptionrows:
    fields=[line[starts[i]:(starts[i+1] if i+1<len(starts) else None)].strip() for i in range(len(starts))]
    exparsed.append(dict(position=int(fields[0]),type=fields[1],endpoints=int(fields[7]),percentages=[float(x) for x in fields[8:] if x]))
assert len({x['position'] for x in exparsed})==len(exparsed)==584
exceptions=dict(rows=584,types=dict(exceptiontypes),zero_endpoint_rows=sum(x['endpoints']==0 for x in exparsed),rows_with_less_than_100_percent_coverage=sum(any(p<100 for p in x['percentages']) for x in exparsed),scope='Report percentages mean coverage relative to specified pins; unchanged source constraints do not imply all exceptions effective or formally safe')
interactionlines=[re.split(r'\s{2,}',l.strip()) for l in (RPT/'clock_interaction_place.rpt').read_text().splitlines() if l and not l[0].isspace()]
interaction=Counter(' / '.join(v[-2:]) for v in interactionlines if len(v)>=8 and v[-2] in {'Clean','Ignored','Unsafe','Unknown'})
assert sum(interaction.values())==81

# Command/saved-checkpoint engineering receipt plus native text and size metadata only.
command=kv(RPT/'place_command_result.txt');identity(RPT/'place_command_result.txt')
assert command['native_tcl_code']=='0' and int(command['ended_epoch'])-int(command['started_epoch'])==7858
saved=read(AT/'place_checkpoint_saved_identity.json');dcp=saved['actual_checkpoint'];dcppath=ROOT/dcp['path']
assert dcppath.name=='place.dcp' and dcppath.stat().st_size==dcp['bytes']==580662986 and saved['command_code']==0
native=[]
with (RPT/'vivado.log').open() as f:
    for line_number,line in enumerate(f,1):
        if 'place_design completed successfully' in line or saved['actual_native_checkpoint_generated_message'] in line:
            native.append(dict(line=line_number,text=line.rstrip()))
assert len(native)==2 and native[0]['line']<native[1]['line']
assert native[1]['text']==saved['actual_native_checkpoint_generated_message']
assert facts['formal_reset_CDC_IO_safety']=='OPEN' and facts['formal_timing']=='FAIL_HOLD'
assert facts['complete_phase_qualification']=='NOT_CLAIMED_BY_THIS_GLOBAL_POST_FACTS'
out=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),reviewer='A007',execution='COMPLETED_ACTUAL_GLOBAL_PLACE_POST_TEXT_REVIEW',
 verdict='ACCEPT_GLOBAL_PLACE_DIAGNOSTIC_QUALIFICATION_ONLY; HOLD_TIMING_FAIL; FORMAL_RESET_CDC_IO_OPEN',
 applicability='AT004 C01 actual closed global place POST; combined candidate locality/reconciliation/compliance/cut/timing/phase qualification separate',review='ACCEPTED_INDEPENDENT_SUBSTEP_NO_NEW_GATE',
 global_facts=factid,global_native_result=result,integrity=identity(RPT/'integrity_place.json'),native_place_command=command,native_closed_lines=native,
 current_source_archives=39,current_production_inputs=144,accepted_pre_place_review=priorid,
 constraints=dict(identity=integrity['constraints'],sources=175,metadata_registry_rows=162,retained_originals=13,new_actual_reads=[],source_metadata_overlay_equal_accepted_pre_place=True),
 reset_structure=dict(qualified=True,issues=[],async_chains=len(structure['async_reset_chains']),aux_chains=len(structure['aux_chains']),host_split_chains=len(structure['host_split_reset_chains']),critical_targets=len(structure['critical_targets']),explicit_exports=len(structure['explicit_primitive_exports']),launch_clock_to_Q_normalizations=len(structure['launch_clock_to_data_q']),pcie_receivers=len(structure['pcie_reset_receivers']),ddr_reset_outputs=len(structure['ddr_reset_output_startpoints']),source=structure['source'],scope=structure['assumptions']),
 reset_fanout=fanout,CDC=cdc,clock_coverage=counts,clocks=clocks,reset_IO=io,resources=resources,DRC=drc,bus_skew=busfacts,
 pulse_width_all_violators_report=dict(no_reported_rows=True,scope='Agrees with accepted zero PW/skew summary; not full timing pass'),exceptions=exceptions,clock_interaction_categories=dict(interaction),
 reused_reviews=reuse,global_timing_verdict='FAIL_HOLD',engineering_saved_DCP_identity=dcp,engineering_saved_DCP_record=identity(AT/'place_checkpoint_saved_identity.json'),reviewer_DCP_metadata_bytes=dcppath.stat().st_size,reviewer_DCP_read_or_hash=False,DCP_sha_provenance='A006 saved checkpoint identity record; not independently content hashed by A007',
 pure_parser_source=srcid,parser_replay_equals_integrity=True,all_identity_checks=list(checks.values()),
 limits=['Global diagnostic qualification is not combined candidate phase acceptance.',
 'Hold WHS -0.562 ns / THS -1879.853 ns / 34042 violating endpoints remains FAIL; setup WNS +0.147 ns is separate.',
 'Reset/CDC/IO formal safety OPEN; proven same-cone representative normalization is not a safety waiver.',
 'DRC RTSTAT-13 Critical Warning retained; current graph is not fully routed and route DRC checks are incomplete.',
 '94 reported bus-skew constraints MET and empty pulse-width all-violators report apply only to this place graph.',
 'Exception coverage gaps and ignored/partially false-path clock interactions remain; report_methodology was not run.',
 'Congestion comparison uses different adaptive windows; no fixed-hotspot relief or C01 causality established.',
 'No native tool, DCP content read/hash, process/lock control, consumed package/production edit, approval gate or new agent.'],audit_program=identity(__file__))
save(OUT/'place_global_POST_review.json',out)
with (OUT/'place_global_POST_review.md').open('x') as f:
    f.write('''# AT004 全局 place POST 独立审核

execution：实际闭合文本证据审核完成。verdict：接受全局 place 诊断资格；hold 时序 FAIL；正式 reset/CDC/IO 安全 OPEN。applicability：AT004/C01 当前 place 图，全候选 locality/compliance/cut/timing/阶段回执另审。review：独立子步骤通过，不新增停点。

原生 place 返回0，耗时7858秒，实际保存580,662,986字节 place.dcp。独立核对保存回执、native生成文本与文件大小；DCP SHA仅引用A006记录，未读取或哈希DCP。

39项运行源及归档、144项生产输入身份核对；175个约束来源、162项registry/metadata、13个保留原来源与恢复pre-place一致，new_actual_reads=[]，候选overlay保持。50个时钟的周期/波形与已审当前完整时序报告一致；内部时钟覆盖完整，外部input1/output2未设delay继续OPEN。

从归档纯函数独立重放当前reset graph、14个primitive导出、fanout及CDC，结果与integrity一致且issues=[]：7 async、4 AUX、3 HostSplit链，6目标，14项launch-C到data-Q归一化，688个实际BRAM端口时钟、10组consumer。CDC原始6、当前分类8、新未分类critical0；4项AUX代表源归一化只证明同一已核逻辑锥，正式安全仍OPEN。

当前DRC为15,917 Warning、1 RTSTAT-13 Critical Warning、0 Error；RTSTAT明确尚未充分布线，路由状态检查未运行，不记为正式DRC通过。94项报告bus-skew约束均MET，最差slack3.262ns；pulse-width all-violators没有条目。584条exception包含覆盖不足/零endpoint条目，clock-interaction有Ignored及Partial False Path；不推导安全或完整时序通过。

复用同身份已审timing、fresh80与congestion：setup WNS+0.147ns，但hold WHS−0.562ns、THS−1879.853ns、34,042个违例endpoint，时序仍FAIL。80个保护边界通过；拥塞为不同自适应窗口，尚无固定热点改善或C01因果结论。完整候选成员、全P落区、cut/timing/compliance与阶段回执另行核验。

详见 place_global_POST_review.json；未调用EDA、控制进程或锁、改生产/消费包或增加审批。
''')
print(json.dumps(dict(review=identity(OUT/'place_global_POST_review.json'),human=identity(OUT/'place_global_POST_review.md'),verdict=out['verdict'],identity_checks=len(checks),DRC=drc,bus_skew=busfacts,exceptions=exceptions),ensure_ascii=False))
