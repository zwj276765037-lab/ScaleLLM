"""Bounded independent AT026 review. No EDA, DCP bytes, production writes or control."""
from pathlib import Path
import datetime,hashlib,json,os,tkinter
ROOT=Path.cwd();OWN=ROOT/'agent/A007/M003_SM015_SM017_review_20261018';A=ROOT/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT026_fresh_core_reset_provenance';JOB=A/'evidence/jobs/native_reset_provenance';REPORT=ROOT/'project/hardware/vivado/reports/m003_E011_R002_AT026_fresh_core_reset_provenance'
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(p):
 p=Path(p);assert p.suffix!='.dcp' and p.stat().st_size<4*2**20,str(p);return p.read_bytes()
def ident(p):
 p=Path(p);b=read(p);return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def load(p):return json.loads(read(p))
def check(row):
 d=ident(row['path']);assert (d['bytes'],d['sha256'])==(row['bytes'],row['sha256']),d;return d
start=load(JOB/'started.json');pkg=load(A/'evidence/reset_diagnostic_package.json');act=load(A/'evidence/actual_native_activation.json');arc=load(JOB/'source_archive.json');chain=load(A/'evidence/fresh_core_AT025_consumption_chain.json');terminal=load(JOB/'status.json')
checks=[];metadata=[]
for bind in arc['bindings']+act['additional_frozen_inputs']:
 for side in ('original','preserved'):
  row=bind[side]
  if row['bytes']<4*2**20:checks.append(check(row))
  else:assert Path(row['path']).stat().st_size==row['bytes'];metadata.append(dict(**row,verification='metadata only; owner hash retained'))
for row in pkg['sources']+pkg['unchanged_inputs']:checks.append(check(row))
manifest=load(pkg['unchanged_inputs'][0]['path']);production=[check(x) for x in manifest['sources']];assert len(production)==48
for row in (chain['original_producer'],chain['original_consumed'],pkg['AT025_complete_snapshot']):
 assert Path(row['path']).stat().st_size==row['bytes'];metadata.append(dict(**row,verification='stat only; producer SHA binding, no independent DCP/whole snapshot hash'))
assert chain['original_producer']==pkg['fresh_core'];assert chain['original_consumed']['sha256']==pkg['fresh_core']['sha256']
readlog=check(chain['actual_AT025_read_log']);assert chain['actual_AT025_read_line'] in read(readlog['path']).decode()
lineage=load(pkg['original_lineage']['path']);rec=next(x for x in lineage['run_records'] if x['run']=='scalellm_vcu118_f05_bd_core_0_synth_1');assert rec['checkpoint']==pkg['fresh_core']
assert start['timeout_seconds'] is None and start['no_output_timeout_seconds'] is None
assert [start[x] for x in ['rss_limit_bytes','mem_available_floor_bytes','mem_low_grace_seconds','disk_floor_bytes']]==[192*2**30,48*2**30,30,30*2**30]
assert terminal['native_exit_code']==0 and terminal['stop_reason'] is None and not terminal['owned_survivors']
identities=dict(terminal['tracked_PID_start_identities']);identities.update({'356106':8420094,'360402':8447751});closed=[]
for pid,expected in identities.items():
 p=Path('/proc')/pid/'stat'
 if p.exists():
  s=p.read_text().rsplit(')',1)[1].split();assert int(s[19])!=expected or s[0]=='Z';closed.append(dict(pid=int(pid),old_start=expected,current_start=int(s[19]),state=s[0],original_identity_absent=True))
 else:closed.append(dict(pid=int(pid),old_start=expected,proc_absent=True))
locks=[x for x in Path('/proc/locks').read_text().splitlines() if x.split()[5].split(':')[-1]=='169247080'];assert not locks,locks
resources=[json.loads(x) for x in read(JOB/'resources.jsonl').splitlines()];assert resources and all(x['rss_bytes']<192*2**30 and x['disk_free_bytes']>30*2**30 and x['mem_available_bytes']>48*2**30 for x in resources)
resource_summary=dict(samples=len(resources),peak_RSS=max(x['rss_bytes'] for x in resources),minimum_MemAvailable=min(x['mem_available_bytes'] for x in resources),minimum_disk_free=min(x['disk_free_bytes'] for x in resources));assert resource_summary['peak_RSS']==terminal['max_RSS_bytes']
owner_cpu=load(ROOT/'agent/A006/M003_SM015_SM018_20261018/boundary_repair/reset_provenance_CPU_receipt.json');cpu=[check(owner_cpu[x]) for x in ('source','test','log')];assert 'Ran 4 tests in 0.255s' in read(cpu[-1]['path']).decode()
rows=[json.loads(x) for x in read(REPORT/'reset_provenance.jsonl').splitlines()];tcl=tkinter.Tcl();words=lambda x:list(tcl.splitlist(x))
groups={r['id']:r for r in rows if r['kind']=='group'};endpoints=[r for r in rows if r['kind']=='endpoint'];nodes=[r for r in rows if r['kind']=='node'];inputs=[r for r in rows if r['kind']=='input'];root=next(r for r in rows if r['kind']=='root');complete=rows[-1]
assert complete==dict(kind='complete',endpoints='51',nodes='3',input_pins='3',groups='4')
assert len(groups)==4 and len(endpoints)==51 and len(nodes)==3 and len(inputs)==3
expected={(f,str(s),str(b)) for f,s in [('core',-1),('helper',0),('helper',1)] for b in range(17)}
assert {(x['family'],x['slice'],x['bit']) for x in endpoints}==expected
all_names=set();group_summary=[]
for gid,g in groups.items():
 names=words(g['nets']);assert len(names)==int(g['actual_segment_count'])==len(set(names));assert all(names) and not(set(names)&all_names);all_names.update(names)
 assert g['direct_net'] in names
 drivers=words(g['leaf_drivers']);ports=words(g['primary_ports']);assert len(drivers)+len(ports)==1
 assert words(g['source_directions'])==(['OUT'] if drivers else ['IN'])
 group_summary.append(dict(id=gid,count=len(names),sorted_NAME_sha256=hashlib.sha256('\n'.join(sorted(names)).encode()).hexdigest(),driver=drivers,ports=ports))
assert root==dict(kind='root',group='R1',port='core_rst_n',direction='IN')
assert words(groups['R1']['primary_ports'])==['core_rst_n'] and words(groups['R1']['leaf_drivers'])==[]
for n in nodes:
 assert n['REF_NAME']=='LUT1' and n['INIT']=="2'h1" and n['output_direction']=='OUT'
 assert words(groups[n['output_group']]['leaf_drivers'])==[n['output_pin']]
 ins=[x for x in inputs if x['cell']==n['cell']];assert len(ins)==1
 assert ins[0]['pin']=='I0' and ins[0]['direction']=='IN' and ins[0]['actual_pin']==n['cell']+'/I0' and ins[0]['group']=='R1'
for e in endpoints:
 assert e['REF_NAME']=='FDCE' and e['INIT']=="1'b0" and e['IS_CLR_INVERTED']=='' and e['pin_IS_INVERTED']=='0'
 assert e['CLR_pin']==e['cell']+'/CLR'
 assert e['group']==('R2' if e['family']=='core' else 'R'+str(3+int(e['slice'])))
projection_path=ROOT/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT025_boundary_sources_postreport_recovery/evidence/AT025_actual_reset_comparison_projection.json';projection=load(projection_path);prefix='scalellm_vcu118_f05_bd_i/core/';mapping=[]
assert projection['snapshot']['sha256']==pkg['AT025_complete_snapshot']['sha256']
for gid,fg in [('R2','RESET_NET_0'),('R3','RESET_NET_1'),('R4','RESET_NET_2')]:
 a={prefix+x for x in words(groups[gid]['nets'])};b=set(projection['unique_native_NAME_groups'][fg]['names']);assert a==b;mapping.append(dict(core_group=gid,fulltop_group=fg,exact_prefix_mapped_NAME_count=len(a)))
actual_endpoint={x['NAME']:x for x in projection['core_address_FF']+projection['helper_address_FF']}
for e in endpoints:
 x=actual_endpoint[prefix+e['cell']];assert x['REF_NAME']==e['REF_NAME'];assert x['CLR_group']=={'R2':'RESET_NET_0','R3':'RESET_NET_1','R4':'RESET_NET_2'}[e['group']]
fullroot=set(projection['unique_native_NAME_groups']['RESET_NET_3']['names']);coreroot=set(words(groups['R1']['nets']));inside={x for x in fullroot if x.startswith(prefix+'inst/')};mapped_inside={prefix+x for x in coreroot if x.startswith('inst/')};assert inside==mapped_inside and len(inside)==803 and len(coreroot)==804 and len(fullroot)==807
assert coreroot-{x for x in coreroot if x.startswith('inst/')}=={'core_rst_n'}
helper_comparison=[]
for n in nodes:
 if n['output_group']=='R2':continue
 full=next(x for x in projection['actual_local_reset_logic'] if x['NAME']==prefix+n['cell']);assert (full['REF_NAME'],full['INIT'])==(n['REF_NAME'],n['INIT']);assert len(full['inputs'])==1 and full['inputs'][0]['pin']=='I0' and full['inputs'][0]['group']=='RESET_NET_3';helper_comparison.append(dict(standalone=n,fulltop=full))
watcher=load(OWN/'AT026_readonly_watcher_start.json');watcher.update(own_exec_session=74409,actual_proc_verified=True,actual_verification_basis='A007 exec output immediately before event002: PID360402 start8447751 stateS nice5 cpus0-7; no current-live claim',retired=True,session_exit_code=0,terminal_event='AT026_dependency_event_003.json',script=str(OWN/'AT026_readonly_dependency_watcher.py'))
review=dict(observed_utc=utc(),execution='AT026 naturally completed0; A007 terminal and bounded semantic evidence review completed',verdict='Native standalone CLR truth functions agree across51; exact fulltop-relative alias/endpoint mapping accepted; fulltop reset semantic qualification remains incomplete',applicability='Original e51 freshcore consumed by AT025; standalone core_rst_n boundary; not fulltop G4',review='Independent source, terminal, resource,51 endpoints,3 cones,4 groups and fulltop-relative map verified',small_hash_checks=checks,production48=production,metadata_only=metadata,actual_AT025_read_log=readlog,owner_activation=ident(A/'evidence/actual_native_activation.json'),live_A007_verification_before_terminal=dict(source='Actual A007 tools.exec_command output preceding observer event002',identities=[dict(pid=p,start_ticks=s,nice=5,cpus=list(range(8)),state='S') for p,s in [(356106,8420094),(356111,8420118),(356123,8420175),(356145,8420178),(356228,8420188),(360402,8447751)]],native_env_independently_read=False),terminal=terminal,closed_identities=closed,locks_after_terminal=locks,resources=resource_summary,protections={k:start[k] for k in ('timeout_seconds','no_output_timeout_seconds','rss_limit_bytes','mem_available_floor_bytes','mem_low_grace_seconds','disk_floor_bytes')},owner_CPU=cpu,owner_CPU_functions=4,owner_CPU_negative_scenarios=13,owner_CPU_runtime_seconds=.255,owner_CPU_rerun=False,actual_provenance=ident(REPORT/'reset_provenance.jsonl'),complete=complete,endpoint_rows=endpoints,group_summaries=group_summary,node_rows=nodes,input_rows=inputs,boolean_derivation=dict(inputs=[0,1],three_CLR_outputs=[1,0],reason="Each of3 native single-input LUT1 has INIT2'h1 and I0 on same actual core_rst_n group; raw CLR pin IS_INVERTED0 on all51",cell_IS_CLR_INVERTED='Empty native values on all51; kept empty, not treated as 0 or NOT_SUPPORTED',FF_INIT="All51 FDCE INIT1'b0",limitation='Raw pin0 is an independent inversion fact; do not coerce empty cell property or claim fulltop polarity exported'),AT025_projection=ident(projection_path),fulltop_relative_mapping=mapping,root_mapping=dict(standalone804=len(coreroot),matching_inst_aliases803=len(inside),fulltop807=len(fullroot),standalone_root_port='core_rst_n',fulltop_external_aliases=sorted(fullroot-inside)),helper_native_fulltop_cone_comparison=helper_comparison,unresolved=['AT025 fulltop original core CLR driver REF/INIT/input cone absent','AT025 fulltop both51 FF INIT/inversion/CLR pin property facts absent; standalone evidence must not silently overwrite fulltop qualifier','Cell-level IS_CLR_INVERTED returned empty; explicit property interpretation/provenance acceptance must preserve this','G4 actual qualified structure/all80/protection/budget/INIT-OPT-restore obligations remain'],observer=watcher,review_harness_correction='First non-writing review command rejected2.616MB locality spec under1MB bound; corrected4MiB bound only for known nonDCP sources. Not an AT026 native error.',G4=False,no_DCP_content_read=True)
for name,data in [('AT026_readonly_watcher_actual_identity.json',watcher),('AT026_terminal_reset_semantics_and_mapping_independent_review.json',review)]:
 with (OWN/name).open('x') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')
p=OWN/'AT026_terminal_reset_semantics_and_mapping_independent_review.json';statefile=ROOT/'agent/A007/state.json';state=load(statefile);state.update(current_task='AT026限定freshcore复位诊断终态及相对全图映射独审',stage='51端点/3反相器/4组完整，终态0与映射通过；全图reset语义资格待',next_step='已实际followup A006终态；继续普通复位资格修复及全图适用性证据独审',reported_at=review['observed_utc'],latest_review=str(p.relative_to(ROOT)),review_execution='AT026_terminal_reset_semantics_and_mapping_review',current_turn_state='active_offline_review',watcher=watcher);statefile.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
status=ROOT/'agent/A007/status.md';old=status.read_text();status.write_text('# A007：AT026复位诊断自然成功，51端点及相对全图映射独审通过\n\nexecution_state: running\nreview_execution: AT026_terminal_reset_semantics_and_mapping_review\n\n[终态及复位映射独审](M003_SM015_SM017_review_20261018/AT026_terminal_reset_semantics_and_mapping_independent_review.json)：07:28:49.796570Z native0/stopnull/survivors空；5tracked+supervisor+observer7原身份退出、独锁空，48生产源保持。169168B实际51端点/3LUT1/4groups全审：三INIT2\'h1且I0同root804，51FDCE/INIT0、CLR pin_IS_INVERTED0；cell IS_CLR_INVERTED全空值保留，不代填0。原17与helper34、CLR361/1/1逐相对映射AT025，root803内部别名完全对应，standalone804/fulltop807边界分开。\n\n11小源归档对与4额外输入逐hash，Python仅metadata；freshcore177MB只stat及producer链绑定，实际AT025读取log核实。4CPU函数/13负例原0.255s日志接受，不重复。observer360402/start8447751/自有session74409于event003后自然退出0；三个事件均先实际followup A006。当前A007离线审核常规reset资格修复，不声称活动AT026观察。全图原core驱动锥与双方极性/INIT仍缺独立原生导出，G4=false。\n\n## 历史阶段（保留）\n\n'+old)
print(json.dumps(dict(review=ident(p),observer=ident(OWN/'AT026_readonly_watcher_actual_identity.json'),small_hash_checks=len(checks),sources=len(production),closed_identities=len(closed),resource_summary=resource_summary,groups=group_summary,root_external=sorted(fullroot-inside)),ensure_ascii=False))
