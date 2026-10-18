#!/usr/bin/env python3
"""Fresh physopt global POST replay, with accepted place semantic comparison."""
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
from datetime import datetime,timezone
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
RPT=ROOT/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
AT=ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation'
OUT=Path(__file__).resolve().parent
checks={}
def require(c,m):assert c,m
def identity(path):
    p=Path(path).resolve();assert p.suffix.lower()!='.dcp';before=p.stat();h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4194304),b''):h.update(b)
    after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    v=dict(path=str(p),bytes=after.st_size,sha256=h.hexdigest());checks[str(p)]=v;return v
def verify(v):
    x=identity(v['path']);assert (x['bytes'],x['sha256'])==(v['bytes'],v['sha256']);return x
def sha256(p):return identity(p)['sha256']
def read(p):return json.loads(Path(p).read_text())
def kv(p):return dict(x.split('=',1) for x in Path(p).read_text().splitlines() if '=' in x)
def canonical(v):
    if isinstance(v,dict):return {k:canonical(x) for k,x in v.items()}
    if isinstance(v,list):return sorted((canonical(x) for x in v),key=lambda x:json.dumps(x,sort_keys=True))
    return v
def save(p,v):
    with p.open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
priorid=identity(OUT/'place_global_POST_review.json');assert priorid['sha256']=='36befc29e56b5f44bb60cdbd72c4129ff861794ac86d4c30345b87e4ab3cffaa'
prior=read(priorid['path']);priorchecks={x['path']:x for x in prior['all_identity_checks']}
factid=identity(AT/'physopt_global_POST_closed_facts.json');assert factid['sha256']=='1114065322159f41ea73777d36493efd99a34f907de967751d8996aaf4fa8117'
facts=read(factid['path'])
for v in facts['artifacts']:verify(v)
for k in ['checkpoint_saved_identity','input_bindings','source_manifest']:verify(facts[k])
result=kv(RPT/'physopt_result.txt');assert result==facts['actual_native_global_POST_result']=={**prior['global_native_result'],'phase':'physopt'}
integrity=read(RPT/'integrity_physopt.json');assert integrity['phase']=='physopt' and integrity['gate_issues']==[] and integrity['debug_clock_observation'] is None
binding=read(AT/'input_bindings.json');assert identity(AT/'input_bindings.json')==priorchecks[str(AT/'input_bindings.json')]
verify(binding['parent']);parent=read(binding['parent']['path']);assert integrity['synthesis']==parent['synthesis']
for v in binding['source_bindings']:
    verify(v);a=identity(RPT/'stage_sources'/Path(v['path']).name);assert (a['bytes'],a['sha256'])==(v['bytes'],v['sha256'])
assert len(binding['source_bindings'])==39
verify(binding['frozen_inputs']['freeze']);production=read(binding['frozen_inputs']['freeze']['path'])['files'];assert len(production)==144
for v in production:verify(v)
constraints=read(RPT/'constraints_physopt.json');verify(integrity['constraints']);verify(constraints['parent'])
assert Path(constraints['parent']['path'])==RPT/'constraints_place.json'
pre=read(constraints['parent']['path']);assert constraints['phase']=='physopt' and constraints['mode']=='embedded_checkpoint_inherited'
for k in ['hashes','metadata','candidate_metadata','source_archives','generated_source_candidates','tool_debug_metadata','candidate_physical_overlay']:assert constraints[k]==pre[k]
assert len(constraints['hashes'])==175 and len(constraints['metadata'])==162 and len(constraints['source_archives'])==13
for name,digest in constraints['hashes'].items():
    p=Path(name)
    if not p.is_file():v=constraints['source_archives'][name];verify(v);p=Path(v['path'])
    assert sha256(p)==digest
verify(constraints['registry']);verify(constraints['actual_reads'])
registry=list(csv.DictReader(Path(constraints['registry']['path']).open(),delimiter='\t'))
fields=['USED_IN','USED_IN_SYNTHESIS','USED_IN_IMPLEMENTATION','IS_ENABLED','SCOPED_TO_REF','SCOPED_TO_CELLS','PROCESSING_ORDER']
assert len(registry)==len({r['path'] for r in registry})==162
assert {r['path']:[r[k] for k in fields] for r in registry}==constraints['metadata']==constraints['candidate_metadata']
assert all(r['SHA256']==constraints['hashes'][r['path']] for r in registry)
assert read(constraints['actual_reads']['path'])==dict(mode='embedded_checkpoint_inherited',inherited_from=binding['parent'],new_actual_reads=[])
for v in constraints['candidate_physical_overlay']['artifacts'].values():verify(v)

src=RPT/'stage_sources/m002_physical_evidence.py';assert identity(src)==prior['pure_parser_source']
functions={'bram_write_clock','auxiliary_cdc_limits','reset_fanout','primitive_defaults','primitive_overrides','reset_structure','verify_reset_proof','cdc_critical_records','opt_reset_cdc_rows','qualified_aux_representatives','critical_coverage','verify_cdc_proof','check_timing_counts','timing_objects','reset_io_coverage','placement_coverage','utilization_metrics'}
constants={'PRIMITIVE_MODEL_ROOT','PRIMITIVE_MODEL_HASHES','BRAM_MODEL_HASHES','TARGETED_OPT_REPORT_HASHES'}
body=[n for n in ast.parse(src.read_text()).body if (isinstance(n,ast.FunctionDef) and n.name in functions) or (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in constants for t in n.targets))]
assert {n.name for n in body if isinstance(n,ast.FunctionDef)}==functions
ns=dict(Path=Path,re=re,math=math,json=json,cache=cache,ROOT=ROOT/'project/hardware',file_id=identity,sha256=sha256,verify_identity=verify,require=require)
exec(compile(ast.Module(body=body,type_ignores=[]),str(src),'exec'),ns)
assert 'TARGETED_CDC_VIOLATIONS_UNKNOWN' not in (RPT/'cdc_changed_reset_physopt.tsv').read_text()
structure=ns['reset_structure'](RPT/'reset_graph_physopt.tsv');assert structure==integrity['reset_structure'] and structure['qualified'] and structure['issues']==[]
fanout=ns['reset_fanout'](RPT/'cdc_changed_reset_physopt.tsv',RPT/'bram_port_clocks_physopt.tsv');assert canonical(fanout)==canonical(integrity['reset_fanout_observation']) and fanout['qualified'] and fanout['issues']==[]
original=Path(integrity['synthesis']['manifest']['path']).parent/'cdc_post_synth.rpt';identity(original)
cdc=ns['critical_coverage'](RPT/'cdc_physopt.rpt',original,structure,fanout);assert cdc==integrity['cdc_classification'];ns['verify_cdc_proof'](cdc)
assert cdc['classified_opt_reset']==8 and cdc['new_critical']==0 and cdc['formal_reset_cdc_safety']=='OPEN' and len(cdc['actual_aux_representative_sources'])==4
counts=ns['check_timing_counts'](RPT/'check_timing_physopt.rpt');assert ns['placement_coverage'](counts,0) and counts==prior['clock_coverage']
io=ns['reset_io_coverage'](RPT/'check_timing_physopt.rpt');assert io==integrity['reset_io_classification']==prior['reset_IO']
resources=ns['utilization_metrics'](RPT/'utilization_physopt.rpt');assert resources==integrity['resources']==facts['actual_resources']==prior['resources']

# Complete text bodies match accepted actual place; only first-page Date,
# Command, Design State and all-hyphen header separators are excluded.
body_matches=[]
for label in ['utilization','utilization_slr','congestion','check_timing','clocks','drc','cdc','clock_interaction','exceptions','pulse_width','bus_skew','slr_crossing']:
    old=RPT/f'{label}_place.rpt';new=RPT/f'{label}_physopt.rpt'
    assert identity(old)==priorchecks[str(old)]
    def normalized(p):return [v for i,v in enumerate(p.read_text().splitlines()) if not(i<14 and (re.match(r'^\|\s*(Date|Command|Design State)\s*:',v) or re.fullmatch('-+',v)))]
    assert normalized(old)==normalized(new)
    body_matches.append(dict(kind=label,place=identity(old),physopt=identity(new),normalized_body_equal=True))
reused={}
for name,digest in [('physopt_command_and_full_timing_review.json','7105a1c0f74b275248fc24808b01e75405ca394f90c8dd4fde64f57d6db8e3f0'),('physopt_fresh80_structure_review.json','2fa032cc4bb47325c9c9001821acab62f3f3c0d44ff9440057ee4d53415df04b')]:
    ident=identity(OUT/name);assert ident['sha256']==digest;r=read(ident['path']);reused[name]=dict(identity=ident,verdict=r['verdict'])
saved=read(facts['checkpoint_saved_identity']['path']);dcp=saved['actual_checkpoint'];assert (ROOT/dcp['path']).stat().st_size==dcp['bytes']==580691314
markers=[]
with (RPT/'vivado.log').open() as f:
    for number,line in enumerate(f,1):
        if line.startswith('M002_DIAGNOSTIC_STEP_COMPLETED physopt'):markers.append(dict(line=number,text=line.rstrip()))
assert markers==[dict(line=169820,text='M002_DIAGNOSTIC_STEP_COMPLETED physopt coverage=COMPLETE_INTERNAL physical_signoff=false')]
assert facts['formal_timing']=='FAIL_HOLD' and facts['formal_reset_CDC_IO_safety']=='OPEN'
out=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),reviewer='A007',execution='COMPLETED_FRESH_PHYSOPT_GLOBAL_POST_INDEPENDENT_REVIEW',verdict='ACCEPT_CURRENT_GLOBAL_PHYSOPT_DIAGNOSTIC_QUALIFICATION_ONLY; HOLD_FAIL_AND_FORMAL_SAFETY_OPEN_RETAINED',applicability='AT004 physopt global POST; candidate members/index/cut/bounded timing/combined phase separate',review='INDEPENDENT_SUBSTEP_ACCEPTED_NO_NEW_GATE',
    current_engineering_facts=factid,current_integrity=identity(RPT/'integrity_physopt.json'),current_native_result=result,current_native_closed_marker=markers[0],prior_accepted_place_POST=priorid,reused_current_substeps=reused,
    current_source_archive_count=39,current_production_input_count=144,constraints=dict(sources=175,registry_metadata_rows=162,retained_originals=13,new_actual_reads=[],same_as_accepted_place=True,identity=integrity['constraints']),
    fresh_reset_structure=dict(qualified=True,issues=[],async_chains=len(structure['async_reset_chains']),aux_chains=len(structure['aux_chains']),host_split_chains=len(structure['host_split_reset_chains']),critical_targets=len(structure['critical_targets']),exports=len(structure['explicit_primitive_exports']),launch_C_to_Q=len(structure['launch_clock_to_data_q']),source=structure['source']),fresh_reset_fanout=fanout,fresh_CDC=cdc,pure_fresh_replay_equals_integrity=True,
    clock_coverage=counts,reset_IO=io,resources=resources,normalized_report_body_comparison=body_matches,normalization='Only first14 lines Date/Command/Design State and horizontal header separators removed; full remaining report text exactly equal',
    DRC=prior['DRC'],bus_skew=prior['bus_skew'],exceptions=prior['exceptions'],clock_interaction_categories=prior['clock_interaction_categories'],congestion_interpretation='Current full report body equals accepted place including same48 adaptive windows; high congestion/no fixed-hotspot-relief/no C01 causality limits retained',
    additional_reports_identity_only=['control_sets_physopt.rpt','paths_setup_physopt.rpt','paths_hold_physopt.rpt','worst_per_clock_physopt.tsv'],saved_DCP_engineering_identity=dcp,reviewer_DCP_read_or_hash=False,
    all_identity_checks=list(checks.values()),audit_program=identity(__file__),limits=['Fresh reset/CDC/BRAM structure is diagnostic; formal reset/CDC/IO OPEN.',
      'Hold WHS-0.562/THS-1879.853/34042 violations remains FAIL; full timing body unchanged.',
      'DRC retains1 RTSTAT-13 Critical Warning and15917 Warning; full routing DRC has not run.',
      '94 bus-skew MET/worst3.262 and no pulse-width violator rows are current place-like diagnostics, not timing/safety signoff.',
      'Exception gaps,6 unconstrained groups,external input1/output2 and report_methodology not run remain.',
      'No complete physopt candidate locality/phase or route acceptance here; no new EDA/native query/DCP content/process-lock control/engineering edits/gate/agent.'])
output=OUT/'physopt_global_POST_review.json';save(output,out)
human=OUT/'physopt_global_POST_review.md'
with human.open('x') as f:f.write('''# AT004 fresh physopt全局POST审核

execution：当前全局POST独立核验完成。verdict：接受physopt全局诊断资格；hold FAIL与正式安全OPEN保持。applicability：仅global POST，候选完整locality/阶段另审。review：独立子步骤通过，无新增停点。

completed1/diagnostic1/blackboxes0/COMPLETE_INTERNAL与日志169820完成标记一致。39运行源/144生产输入身份核对；175约束来源、162registry/metadata、13保留原来源和overlay保持，new_actual_reads=[]。

当前reset graph、14 primitive exports、fanout/BRAM与CDC纯逻辑重放等于integrity且issues=[]：7 async、4 AUX、3 HostSplit链、6目标，688个BRAM端口时钟，8分类CDC/新未分类0；4个AUX代表源归一化仍是诊断证明，正式安全OPEN。

12类当前报告去除页眉日期/命令/阶段/横线后，全部正文与已审place相同，包括时钟、DRC、CDC、约束exception、pulse-width、bus-skew与拥塞。DRC保留1 RTSTAT-13 Critical Warning/15,917 Warning，94项bus-skew均MET最差3.262ns，exception覆盖缺口保留。高拥塞与未证明固定热点缓解保持。

复用本轮已审physopt命令、新完整timing与fresh80；hold仍34,042违例，WHS−0.562/THS−1879.853ns。DCP仅核工程保存身份记录与大小，未读/hash内容。额外control_sets/paths_setup/paths_hold/worst_per_clock只核身份，不扩展为穷举或时序签核。完整候选phase与route未由本审核成立。
''')
print(json.dumps(dict(review=identity(output),human=identity(human),verdict=out['verdict']),ensure_ascii=False))
