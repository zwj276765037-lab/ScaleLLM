#!/usr/bin/env python3
"""A007 combine closed place substeps and confirm actual outer physopt start."""
import sys
sys.dont_write_bytecode=True
def guard(event,args):
    if event=='open' and args and isinstance(args[0],(str,bytes)):
        p=args[0].decode() if isinstance(args[0],bytes) else args[0]
        if p.lower().endswith('.dcp'):raise RuntimeError('A007 DCP content access forbidden')
sys.addaudithook(guard)
import ast,collections,csv,hashlib,json,math,re,tkinter
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timezone
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
RPT=ROOT/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
AT=ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation'
OLD=ROOT/'project/hardware/vivado/reports/m002_E005_R004_AT003_current_CDC_bound_OPT_place_physopt'
OUT=Path(__file__).resolve().parent
checks={}
def require(c,m):assert c,m
def identity(p):
    p=Path(p).resolve();assert p.suffix.lower()!='.dcp';before=p.stat();h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4194304),b''):h.update(b)
    after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    v=dict(path=str(p),bytes=after.st_size,sha256=h.hexdigest());checks[str(p)]=v;return v
def verify(v):assert identity(v['path'])==v;return v
def read(p):return json.loads(Path(p).read_text())
def kv(p):return dict(x.split('=',1) for x in Path(p).read_text().splitlines() if '=' in x)
def rows(p):
    identity(p)
    with Path(p).open() as f:rs=list(csv.DictReader(f,delimiter='\t',quoting=csv.QUOTE_NONE))
    assert all(None not in r and all(v is not None for v in r.values()) for r in rs);return rs
def saveout(path,data):
    with path.open('x') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')
reviews={}
for name,digest in [('place_global_POST_review','36befc29e56b5f44bb60cdbd72c4129ff861794ac86d4c30345b87e4ab3cffaa'),('place_membership_reconciliation_review','cfbb3047dac1dda52562d17ac38da8245d4299ce06f7eab223e76afb1bdc59c2'),('place_native_index_alias_review','1d7c6d13daeb354c1ffdaf3514d79df932a38e8d75ef14236f3fab0d96cff674'),('place_directed_cut_review','d50899bf2ef990f730d458f8a74a61cad585b06393e2798d28a6c0160a465f02'),('place_bounded_timing_review','433e5e3f90a13a0c2756f936a20daea1aa21a537e4e31a841fb3dd40ab27c321'),('place_full_timing_report_review','386dced9df9391fb485a45d1f0847247683f7afb4e3910a4563eecc3861219b4'),('place_fresh80_structure_review','6d65874583f952cbb619f6cc865da1433c8108af117cd80618b293e4c0c2834a'),('place_congestion_scope_review','4a2e0c1236c58fb5ce345e12d447f1dcec3dd76dac81849c037be0f1443b151c')]:
    ident=identity(OUT/(name+'.json'));assert ident['sha256']==digest;reviews[name]=dict(identity=ident,value=read(ident['path']))
global_review=reviews['place_global_POST_review']['value'];source_checks={v['path']:v for v in global_review['all_identity_checks']}
factpath=AT/'place_closed_stage_facts.json';factid=identity(factpath)
assert factid['bytes']==3634643 and factid['sha256']=='1f7fec1359c57a0ec221016501814a9c615e9bfe429175b2024e96a3835c233c'
facts=read(factpath)
for v in facts['artifacts']:verify(v)
for k in ['input_bindings','producer','metric_parser','SLR_parser']:verify(facts[k])
assert facts['stage']=='place' and facts['execution']=='closed_qualified_physical_stage'
assert facts['native_stage_qualification_zero'] is True and facts['legal_routed_timing_signoff'] is False
assert facts['formal_reset_CDC_IO_safety']=='OPEN' and facts['final_input_PID_lane_closure']=='PENDING_ACTUAL_TERMINAL'
binding=read(facts['input_bindings']['path']);assert facts['selected_candidate']==binding['attribution']['selected_candidate']
verify(binding['preparation_manifest'])
started=read(AT/'started.json');identity(AT/'started.json');assert started['inputs']==facts['input_bindings']
receipt=kv(RPT/'candidate_phase_place_status.txt');assert receipt==facts['actual_closed_phase_receipt']
assert receipt==dict(post_code='0',locality_code='0',started_epoch='1792239478',ended_epoch='1792243426')
tcl=tkinter.Tcl()
def tdict(value):
    parts=tcl.splitlist(value);assert len(parts)%2==0 and len(set(parts[::2]))==len(parts)//2;return dict(zip(parts[::2],parts[1::2]))
native_receipt=tdict((RPT/'candidate_phase_place_receipt.tcllist').read_text())
assert native_receipt=={'post_code':'0','post_result':'','post_options':'-code 0 -level 0','locality_code':'0','locality_result':'','locality_options':'-code 0 -level 0'}
command=kv(RPT/'place_command_result.txt');assert command['native_tcl_code']=='0' and command['ended_epoch']==receipt['started_epoch']
assert global_review['global_native_result']==facts['native_POST_result']==kv(RPT/'place_result.txt')
assert facts['integrity_gate_issues']==[]

# Pure current compliance replay; replacing save with memory does not touch evidence.
adapter=RPT/'stage_sources/evidence_adapter.py';assert identity(adapter)==source_checks[str(adapter)]
captured={}
def capture(path,value):assert Path(path)==RPT/'candidate_compliance_place.json';captured[str(path)]=value
defs=[n for n in ast.parse(adapter.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in {'rows','compliance'}]
assert {n.name for n in defs}=={'rows','compliance'}
ns=dict(Path=Path,csv=csv,json=json,collections=collections,e=SimpleNamespace(require=require,file_id=identity,key_values=kv),directed=SimpleNamespace(VERSION='candidate_directed_cut_v1'),save=capture)
exec(compile(ast.Module(body=defs,type_ignores=[]),str(adapter),'exec'),ns)
compliance=ns['compliance']('place',RPT)
assert compliance==read(RPT/'candidate_compliance_place.json')==facts['actual_candidate_compliance']==captured[str(RPT/'candidate_compliance_place.json')]
assert compliance['compliance_established'] and compliance['selected_SLR_counts']=={'SLR2':9491}
assert all(compliance[k]==[] for k in ['original_missing','new_pblock_objects','surviving_or_new_selected_non_SLR2','actual_pblock_non_SLR2'])

# Sites contain primitive rows; DSP children normalize to the actual physical parent.
site_rows=rows(RPT/'candidate_site_members_place.tsv');assert len(site_rows)==len({r['NAME'] for r in site_rows})==16772
members={r['NAME']:r for r in rows(RPT/'candidate_membership_place.tsv')}
parents={r['NAME']:r for r in rows(RPT/'candidate_physical_members_place.tsv')}
groups=collections.defaultdict(set);normalized_selected=set();selected_primitives=0
for r in site_rows:
    assert r['SLR']=='SLR2' and r['LOC'] and r['selected_P'] in {'0','1'}
    member=members.get(r['NAME']);parent=member['physical_parent'] if member else r['NAME']
    assert (r['selected_P']=='1')==(parent in parents)
    if r['selected_P']=='1':
        selected_primitives+=1;normalized_selected.add(parent)
        assert (r['SLR'],r['LOC'])==(parents[parent]['SLR'],parents[parent]['LOC'])
    groups[(r['SLR'],r['LOC'])].add('candidate' if r['selected_P']=='1' else 'other')
assert normalized_selected==set(parents) and selected_primitives==9505
assert set(groups)=={(r['SLR'],r['LOC']) for r in parents.values()} and all('candidate' in v for v in groups.values())
assert len(groups)==compliance['candidate_touched_sites']==979
assert sum(v=={'candidate','other'} for v in groups.values())==compliance['shared_candidate_sites']==801

cut=read(RPT/'candidate_cut_summary_place.json');timing=read(RPT/'candidate_timing_validation_place.json')
assert facts['candidate_cut_coverage_version']==cut['coverage_version']=='candidate_directed_cut_v1'
assert facts['candidate_directed_scope']=={k:cut[k] for k in facts['candidate_directed_scope']}
assert facts['actual_bounded_timing_validation']==timing
assert timing['full_cut_TNS']=='NOT_MEASURED' and timing['signoff'] is False
assert facts['full_net_endpoint_coverage']=='NOT_CLAIMED_ON_QUALIFIED_REDUCED_NETS' and facts['complete_external_fanout']=='NOT_MEASURED'
bounded=reviews['place_bounded_timing_review']['value']
assert bounded['overlapping_start_end_clock_signatures_between_directions']=={'max':16,'min':0}

# Replay the producer's actual metric parsers only, without imports or producer execution.
parserpath=Path(facts['metric_parser']['path']);parsertext=parserpath.read_text()
functions=[n for n in ast.parse(parsertext).body if isinstance(n,ast.FunctionDef) and n.name in {'timing_metrics','timing_verdict','utilization_metrics'}]
assert len(functions)==3
pn=dict(Path=Path,math=math,re=re,require=require)
exec(compile(ast.Module(body=functions,type_ignores=[]),str(parserpath),'exec'),pn)
slrpath=Path(facts['SLR_parser']['path']);slrnodes=[n for n in ast.parse(slrpath.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='native_slr'];assert len(slrnodes)==1
exec(compile(ast.Module(body=slrnodes,type_ignores=[]),str(slrpath),'exec'),pn)
current_timing=pn['timing_metrics'](RPT/'timing_place.rpt');current_resources=pn['utilization_metrics'](RPT/'utilization_place.rpt')
assert current_timing==facts['timing_metrics_ns_and_endpoint_counts']==reviews['place_full_timing_report_review']['value']['current']['metrics']
assert pn['timing_verdict'](current_timing)==facts['timing_summary_verdict']=='FAIL'
assert current_resources==facts['device_resources']==global_review['resources']
base=facts['same_phase_E005_comparison']
for v in base['original_artifacts']:verify(v)
old_timing=pn['timing_metrics'](OLD/'timing_place.rpt');old_resources=pn['utilization_metrics'](OLD/'utilization_place.rpt')
assert old_timing==base['timing']==reviews['place_full_timing_report_review']['value']['baseline']['metrics']
assert old_resources==base['resources']
assert {k:current_timing[k]-old_timing[k] for k in current_timing}==base['timing_delta']
assert {k:current_resources[k]['used']-old_resources[k]['used'] for k in current_resources}==base['resource_used_delta']
for path,value in [(RPT/'utilization_slr_place.rpt',facts['SLR_resources']),(OLD/'utilization_slr_place.rpt',base['SLR_resources']),(RPT/'utilization_candidate_place_SLR.rpt',facts['exact_candidate_native_resources'])]:
    assert pn['native_slr'](path)==value
unique_metrics=['CLB LUTs','CLB Registers','Block RAM Tile','URAM','DSPs']
def unique_slr_rows(path):
    found=collections.defaultdict(list)
    for line_number,line in enumerate(path.read_text().splitlines(),1):
        cells=[v.strip() for v in line.split('|')[1:-1]]
        if len(cells)==7 and all(re.fullmatch(r'[0-9.]+',v) for v in cells[1:4]):
            found[cells[0]].append(dict(native_line=line_number,SLR0=float(cells[1]),SLR1=float(cells[2]),SLR2=float(cells[3])))
    assert all(len(found[k])==1 for k in unique_metrics)
    return {k:found[k][0] for k in unique_metrics},{k:len(v) for k,v in found.items() if len(v)>1}
current_slr,duplicates=unique_slr_rows(RPT/'utilization_slr_place.rpt');old_slr,old_duplicates=unique_slr_rows(OLD/'utilization_slr_place.rpt');candidate_slr,candidate_duplicates=unique_slr_rows(RPT/'utilization_candidate_place_SLR.rpt')
assert current_slr=={k:facts['SLR_resources'][k] for k in unique_metrics}
assert old_slr=={k:base['SLR_resources'][k] for k in unique_metrics}
assert candidate_slr=={k:facts['exact_candidate_native_resources'][k] for k in unique_metrics}
assert all(sum(row[s] for s in ['SLR0','SLR1','SLR2'])==current_resources[k]['used'] for k,row in current_slr.items())
slr_delta={k:{s:current_slr[k][s]-old_slr[k][s] for s in ['SLR0','SLR1','SLR2']} for k in unique_metrics}

# Bind actual consumed hook order and actual native physopt invocation, not a plan.
for filename in ['candidate_hooks.tcl','runtime_hooks.tcl','implementation.tcl']:
    path=RPT/'stage_sources'/filename;assert identity(path)==source_checks[str(path)]
hook=(RPT/'stage_sources/candidate_hooks.tcl').read_text();impl=(RPT/'stage_sources/implementation.tcl').read_text()
assert 'set post_code [catch {m002_post $point} post_result post_options]' in hook
assert 'set locality_code [catch {phase $point} locality_result locality_options]' in hook
assert 'if {$post_code} {return -options $post_options $post_result}' in hook and 'if {$locality_code} {return -options $locality_options $locality_result}' in hook
assert impl.index('slr2::post_phase place')<impl.index('m002_command physopt {phys_opt_design -directive Default}')<impl.index('slr2::post_phase physopt')
loglines=[];capture=False
with (RPT/'vivado.log').open() as f:
    for line_number,line in enumerate(f,1):
        if line.startswith('DIRECTED_CUT_COMPLETED point=place '):capture=True
        if capture:loglines.append(dict(line=line_number,text=line.rstrip()))
        if capture and line.startswith('Starting Initial Update Timing Task'):break
assert loglines and loglines[-1]['text']=='Starting Initial Update Timing Task'
locality=[r for r in loglines if r['text']=='E008_STAGE_COMPLETED locality_place']
physopt=[r for r in loglines if r['text']=='Command: phys_opt_design -directive Default']
license_rows=[r for r in loglines if "Got license for feature 'Implementation' and/or device 'xcvu9p'" in r['text']]
assert len(locality)==len(physopt)==len(license_rows)==1 and locality[0]['line']<physopt[0]['line']<license_rows[0]['line']<loglines[-1]['line']
bounded_events=[r for r in loglines if r['text'].startswith('DIRECTED_API operation BOUNDED_TIMING ')]
assert len(bounded_events)==8
assert max(int(tdict(r['text'].removeprefix('DIRECTED_API '))['epoch_ms']) for r in bounded_events)//1000<=int(receipt['ended_epoch'])
format_warnings=[r for r in loglines if '[Vivado 12-1569]' in r['text'] or '[Vivado 12-1072]' in r['text']]
assert len(format_warnings)==8
snapshot=OUT/'place_to_physopt_native_closed_excerpt.json'
saveout(snapshot,dict(recorded_utc=datetime.now(timezone.utc).isoformat(),source_path=str(RPT/'vivado.log'),scope='Frozen exact completed place-to-physopt-start excerpt; not whole live-log identity',lines=loglines))
out=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),reviewer='A007',execution='ACTUAL_PLACE_COMMAND_AND_COMPLETE_GLOBAL_POST_PLUS_CANDIDATE_LOCALITY_CLOSED_SUCCESSFULLY',
    verdict='ACCEPT_FULL_PLACE_DIAGNOSTIC_PHASE_AND_C01_ACTUAL_SLR2_COMPLIANCE; GLOBAL_HOLD_TIMING_FAIL; FORMAL_RESET_CDC_IO_OPEN',
    applicability='AT004 C01 only; actual place completion and actual outer physopt start; no completed physopt/route or legal routed signoff',review='COMBINED_PLACE_INDEPENDENT_REVIEW_COMPLETE_NO_NEW_GATE',
    actual_closed_stage_facts=factid,actual_native_receipt=native_receipt,actual_status_receipt=receipt,POST_locality_elapsed_seconds=int(receipt['ended_epoch'])-int(receipt['started_epoch']),phase_closed_utc=datetime.fromtimestamp(int(receipt['ended_epoch']),timezone.utc).isoformat(),
    accepted_substeps={name:dict(identity=v['identity'],verdict=v['value']['verdict'],applicability=v['value']['applicability']) for name,v in reviews.items()},
    complete_current_compliance_replay_equals_facts=True,candidate_compliance=compliance,current_site_inventory=dict(primitive_rows=16772,selected_primitive_rows=9505,normalized_selected_P=9491,touched_sites=979,shared_sites=801,all_P_site_coverage=True,scope='Current shared occupancy only; not freed capacity'),
    cut_logical_pairs=dict(known_cross=127,unknown_position_pairs=8014,unknown_pair_drivers='All seven GND/VCC RAW members excluded from S/P; loads are SLR2',unknown_class_counts={'clock':1429,'constant':429,'reset_set':6156},not_total_SLL_or_bandwidth=True),
    bounded_timing_metrics=[{k:r[k] for k in ['direction','delay_type','queried_pins','returned_paths','worst_slack_ns','negative_slack_paths']} for r in bounded['native_timing']],bounded_setup_directions_share_all16_path_signatures=True,
    current_global_timing=current_timing,global_timing_verdict='FAIL',same_phase_global_timing_delta=base['timing_delta'],current_device_resources=current_resources,same_phase_resource_used_delta=base['resource_used_delta'],
    current_unique_top_SLR_rows=current_slr,old_same_phase_unique_top_SLR_rows=old_slr,same_phase_unique_top_SLR_deltas=slr_delta,candidate_unique_top_SLR_rows=candidate_slr,
    native_SLR_parser_duplicate_labels=dict(current=duplicates,old=old_duplicates,candidate=candidate_duplicates,limitation='Parser dictionaries overwrite repeated subrow labels; only independently verified unique top rows are used numerically here'),
    fact_producer=facts['producer'],fact_metric_parser=facts['metric_parser'],fact_SLR_parser=facts['SLR_parser'],producer_not_executed_by_reviewer=True,
    actual_outer_physopt_start=dict(native_command=physopt[0],native_license=license_rows[0],native_initial_update=loglines[-1],frozen_excerpt=identity(snapshot),completion_not_claimed=True),native_timing_format_warnings=format_warnings,
    all_identity_checks=list(checks.values()),audit_program=identity(__file__),
    limits=['Complete place diagnostic/locality acceptance is separate from global hold FAIL, formal CDC/reset/IO OPEN and route success.',
      'High congestion and all48 changed adaptive windows remain; fixed original hotspot relief and C01 causality are not established.',
      'Global same-phase SLR relocation and LUT/register deltas affect many modules; do not attribute all to C01 or convert current site sharing to released capacity.',
      '127 known logical crossings and 8014 constant-driver unknown-position pairs are not SLL demand/bandwidth.',
      'All16 setup paths repeat across ingress/egress through-LOAD queries; four capped queries are not independent complete cut timing or full-cut TNS.',
      'Native report_timing -nets deprecated and -of_objects incompatible formatting options ignored; actual returned path fields checked, unsupported logic/net split retained UNKNOWN.',
      'RTSTAT-13 Critical Warning/15917 Warning and exception coverage gaps remain; no formal routed DRC signoff.',
      'Final input/PID/lane closure remains pending actual terminal; this reviewer performs no process/lock control.',
      'No EDA/native query, DCP content read/hash, engineering/consumed-package edit, new agent or approval gate.'])
output=OUT/'place_combined_stage_review.json';saveout(output,out)
human=OUT/'place_combined_stage_review.md'
with human.open('x') as f:f.write('''# AT004 完整place阶段独立审核

execution：实际place命令、全局POST与候选locality全部闭合成功。verdict：接受完整place诊断阶段及C01实际SLR2符合性；全局hold时序FAIL、正式reset/CDC/IO安全OPEN保持。applicability：AT004/C01当前place图与外层physopt实际启动。review：独立组合审核完成，不新增停点。

原生post_code/locality_code均0，13:23:46Z闭合；复用8份已审子步骤，补核当前compliance纯函数重放与工程完整facts逐字段一致。C01原始9491个P全部SLR2、无缺失/替换；完整有向cut与4组有界时序均有当前图真实证据。原生日志169756行为phys_opt_design -directive Default，169758行真实许可成功，169761行Starting Initial Update Timing Task，确认进入外层physopt；不声称physopt完成。

INGRESS setup/hold最差+0.603/−0.221ns，EGRESS+0.603/+0.057ns；两方向setup的16条起终点/时钟签名全部重合，不能算独立32条setup路径或每条跨cut。8,014个未知位置pair全由7个S/P排除的GND/VCC驱动；127个已知跨SLR只是逻辑pair，不是全SLL。979个touched sites中801个shared是当前占用，不是释放容量。

全局setup WNS+0.147ns，但hold WHS−0.562ns、THS−1879.853ns、34,042违例endpoint，时序仍FAIL。SLR1同place LUT336,107→282,659、register435,367→352,889；其他SLR发生大规模重排，不能将全局delta归因C01。SLR数字只使用独立验证的唯一顶层LUT/register/BRAM/URAM/DSP行；重复using-O5/O6子行字典覆盖限制保留。

高拥塞、自适应窗口不可直接比、固定原热点改善未证、RTSTAT-13及exception覆盖限制、正式安全OPEN均保持。未证明route成功、full-cut TNS、拥塞因果改善或物理签核；最终输入/进程/资源收尾待真实terminal。审核未运行EDA、读取/hash DCP、控制进程/锁或改工程消费包。
''')
print(json.dumps(dict(review=identity(output),human=identity(human),execution=out['execution'],physopt=out['actual_outer_physopt_start'],unique_SLR_deltas=slr_delta),ensure_ascii=False))
