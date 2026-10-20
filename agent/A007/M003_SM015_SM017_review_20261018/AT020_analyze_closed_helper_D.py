"""A007 bounded closed-helper-D audit. No EDA, DCP or process access."""
import collections,datetime,hashlib,json,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parents[3]
OWN=pathlib.Path(__file__).resolve().parent
AT=ROOT/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT020_fresh_core_state_source_semantics'
REPORT=ROOT/'project/hardware/vivado/reports/m003_E011_R002_AT020_fresh_core_state_source_semantics'
def identity(p, n, digest):
 b=p.read_bytes(); assert len(b)==n and hashlib.sha256(b).hexdigest()==digest,str(p)
 return {'path':str(p.relative_to(ROOT)),'bytes':n,'sha256':digest},b
records=[]
for p,n,h in [(AT/'evidence/AT020_closed_helper_D_observation.json',610728,'4bff6bb3a0e26843b3a05d87070bb19ffa222ca493ec5e01eb577c73eea32b9c'),(REPORT/'helper_D_sources.jsonl',1906402,'3edfa18f93a30cac89d582a1b80e991426996747584e33624681fe9faa2e3890'),(AT/'evidence/closed_helper_D_sources.jsonl',1906402,'3edfa18f93a30cac89d582a1b80e991426996747584e33624681fe9faa2e3890'),(AT/'evidence/actual_native_activation.json',4661,'ee738b22f29be587f75a058724e8f4b79ee653289615e4ed258d5e894d8b4899')]:
 rec,b=identity(p,n,h);records.append(rec)
 if p.name=='helper_D_sources.jsonl':rows=[json.loads(x) for x in b.splitlines()]
issues=[]
def need(test,label):
 if not test:issues.append(label)
base='inst/u_core/u_compute/u_attention/u_meta/g_m003_width_slices.g_slice'
need(len(rows)==34 and {(r['slice'],r['bit']) for r in rows}=={(s,b) for s in (0,1) for b in range(17)},'34 exact unique slice/bit rows')
counts=collections.Counter();refs=collections.Counter();local_counts=collections.Counter();bit_plus_one=True
for r in rows:
 sl,bit=r['slice'],r['bit'];cell=f'{base}[{sl}].u_addr/address_r_reg[{bit}]'
 need(r['cell']==cell and r['D_pin']==cell+'/D' and r['own_Q_pin']==cell+'/Q','exact row identity '+cell)
 cone=set(r['raw_full_fanin']);need(len(cone)==len(r['raw_full_fanin']),'fullcone duplicates '+cell)
 need(r['own_Q_in_full_fanin']==1 and cell+'/Q' in cone,'actual own Q in fullcone '+cell)
 facts=r['actual_source_owner_facts'];need([f['raw_name'] for f in facts]==r['raw_startpoints'],'facts exact ordered raw starts '+cell)
 need(len(set(r['raw_startpoints']))==len(r['raw_startpoints']),'raw starts duplicate '+cell)
 owners={}
 all_names=r['raw_startpoints']+r['raw_full_fanin']+r['raw_startpoint_only_cells']
 for f in facts:
  all_names+=f['owner_names']+f['owner_Q_pins']
  if f['class']=='pin':
   counts['raw_pin_C']+=1
   need(f['raw_name'].endswith('/C') and len(f['owner_names'])==1,'actual pin owner '+cell)
   owner=f['owner_names'][0]
   need(f['raw_name']==owner+'/C' and f['owner_refs'] in (['FDCE'],['FDRE']),'actual owner/ref '+cell)
   need(f['owner_Q_pins']==[owner+'/Q'] and f['owner_Q_in_full_fanin']==['1'],'actual queried Q evidence '+cell)
   need(all(q in cone for q in f['owner_Q_pins']),'independent raw fullcone Q membership '+cell)
   need(owner not in owners,'duplicate actual owner '+cell);owners[owner]=f['owner_refs'][0]
  elif f['class']=='port':
   counts['raw_core_rst_n_ports']+=1
   need(f['raw_name']=='core_rst_n' and all(f[k]==[] for k in ('owner_names','owner_refs','owner_Q_pins','owner_Q_in_full_fanin')),'raw port retained '+cell)
  else:need(False,'unexpected source class '+cell)
 only=r['raw_startpoint_only_cells'];onlyrefs=r['raw_startpoint_only_cell_refs']
 need(len(set(only))==len(only)==len(onlyrefs) and set(only)==set(owners),'only_cells equals actual owners '+cell)
 need(all(owners.get(o)==v for o,v in zip(only,onlyrefs)),'only_cells refs agree '+cell);refs.update(onlyrefs)
 need(all('meta_read_addr_r_reg[' not in x for x in all_names),'old core address absent '+cell)
 other=f'{base}[{1-sl}].u_addr/address_r_reg['
 need(all(other not in x for x in all_names),'opposite slice helper absent '+cell)
 local=sum(x.startswith(f'{base}[{sl}].u_addr/address_r_reg[') for x in owners)
 local_counts[local]+=1;bit_plus_one=bit_plus_one and local==bit+1
need(counts=={'raw_pin_C':2006,'raw_core_rst_n_ports':34},'aggregate source counts')
need(refs=={'FDCE':1428,'FDRE':578},'actual owner ref counts')
review={
 'schema':'A007_AT020_closed_helper_D_review_v1','reviewed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'execution':'completed_bounded_closed_helper_D_audit','verdict':'supported_34_own_state_Q_dependencies_from_actual_owner_queries_and_full_fanin',
 'review':{'status':'accepted_scoped_evidence','no_blocker':not issues,'issues':issues},
 'applicability':'Only the closed 34-row helper_D_sources subtable from the exact AT020 diagnostic package; not terminal or clock evidence, production candidate approval, functional equation proof, complete selected graph, budget, physical closure or G4.',
 'package_sha256':'fa5e333d593048829eee1578afdffeed500c8f54832200c08ea5aecc8ae3baed',
 'evidence_identities':records,
 'independent_checks':{'exact_unique_rows':len(rows),'own_Q_in_raw_full_fanin_rows':34,'raw_source_counts':dict(counts),'actual_owner_refs':dict(refs),'all_2006_queried_owner_Qs_in_raw_full_fanin':True,'only_cells_equals_actual_pin_owner_set_every_row':True,'other_slice_helper_or_oldcore_address_evidence_count':0,'own_slice_helper_owner_count_distribution':dict(sorted(local_counts.items())),'own_slice_helper_owner_count_equals_bit_plus_one':bit_plus_one,'common_control_FFs_and_reset_port_present':True},
 'ordinary_validator_adaptation_bounds':[
  'Preserve raw D_startpoints, port sources and raw fullcone. Never manufacture Q by C-to-Q string replacement.',
  'Record actual source owner/ref/Q queries and independently check Q membership in the actual fullcone; retain only_cells consistency. Use this separate evidence for own-state dependency and other-slice/old-core exclusions.',
  'Common control FFs and core_rst_n are observed legitimate upstream sources; reject forbidden address state by actual identities, not every nonhelper or a slice-name substring.',
  'Serialize empty memory net/driver collections as raw facts. Selected-input legality must follow actual CASCADE_ORDER, IREG_PRE, REG_CAS and associated inversion/config fields; do not introduce generic acceptance of empty collections.',
  'Require exact 80-cell inventory and per-pin completeness, bit-preserving same-slice acyclic nonbranching address chains with valid FIRST/MIDDLE/LAST endpoints, common predecessor for CAS address/RDB_WR/EN and effective A-read/B-write modes. FIRST read low17 must map exact own-slice bit/Q; retain corresponding write-address and actual high-bit/mask checks. Reject unknown config, wrong/missing bit, wrong predecessor, cycles, cross-slice chain, unsupported inversion, missing evidence or native API errors.',
  'Preserve existing payload/clock/reset/CE/constraint/schema coverage and unknown-versus-API-error distinction. CLK evidence remains pending.',
  'Combined serializer/qualifier candidate requires exact source identities, CPU equivalence/negative cases and later native evidence; no native memory or speed claim follows from CPU byte equivalence. Do not edit the active AT020 four-source package.'
 ],
 'existing_chain_analysis_reference':{'script':'agent/A007/M003_SM015_SM017_review_20261018/AT019_analyze_closed_native.py','result':'agent/A007/M003_SM015_SM017_review_20261018/AT019_closed_native_independent_analysis.json','result_sha256':'2241c6de74ac4c80bff9db8c99765d28dcc905103cfd99cf853303231e7986ff','scope':'Reusable observed full-chain checks; diagnostic analysis is not blanket production qualifier approval.'},
 'native_terminal':'not reviewed in this increment','CLK':'not reviewed in this increment','G4':False,
 'review_scope':'Own review files only; raw report and source reads. No EDA, DCP content/hash, process control, lock acquisition, production edits or GPU.',
 'next':'A006 directly follows up actual CLK/terminal evidence and the fixed combined candidate; normal native execution continues.'}
assert not issues,issues
out=OWN/'AT020_closed_helper_D_review.json'
assert not out.exists(),str(out)
out.write_text(json.dumps(review,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'path':str(out.relative_to(ROOT)),'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'counts':dict(counts),'own_local_count_is_bit_plus_one':bit_plus_one,'issues':issues},indent=2))
