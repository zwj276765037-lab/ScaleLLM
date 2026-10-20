"""A007 bounded post-place diagnosis from existing small/selected raw exports."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import json,re,hashlib
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT=ROOT/'agent/A007/M003_SM015_SM017_review_20261018'
DBG=ROOT/'project/hardware/vivado/reports/m003_E011_R002_AT035_qualified_OPT_POST_to_actual_debug'
NOW=ROOT/'project/hardware/vivado/reports/m003_E011_R003_AT001_fixed_complete_physical'
ATT=ROOT/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R003/attempts/AT001_fixed_complete_physical'
CORE='scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_attention'
ids=[]
def ident(p):
 p=p.resolve();h=hashlib.sha256()
 assert p.suffix!='.dcp' and p.stat().st_size<25_000_000
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())
def bind(p):
 i=ident(p);ids.append(i);return i
def load(p):return json.loads(p.read_text())
def stream(p):
 h=hashlib.sha256();rows=[]
 with p.open('rb') as f:
  for line in f:h.update(line);rows.append(json.loads(line))
 ids.append(dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=h.hexdigest()))
 return rows
def words(x):return [z.strip('{}') for z in x.split()]
data={}
for tag,p,phase in [('debug',DBG,'debug_materialized'),('place',NOW,'place')]:
 cfg={x['NAME']:x for x in stream(p/f'm003_stream_{phase}_uram_configs.jsonl')}
 rr=stream(p/f'm003_stream_{phase}_memory_pins.jsonl');mem={(x['cell'],x['pin']):x for x in rr};assert len(rr)==len(mem)==34480
 data[tag]=(cfg,mem)
old_cfg,old=data['debug'];cfg,mem=data['place'];assert cfg==old_cfg and len(cfg)==80 and set(mem)==set(old)
roots=[n for n,x in cfg.items() if x['CASCADE_ORDER_A']=='FIRST'];assert len(roots)==12
changed=[]
for k,x in mem.items():
 y=old[k]
 if x.get('drivers')!=y.get('drivers'):
  c=cfg[x['cell']];assert x['cell'] in roots and x['pin'] in ['ADDR_B[10]','ADDR_B[11]','ADDR_B[12]']
  bit=int(re.search(r'\[(\d+)\]',x['pin'])[1]);assert words(y['drivers'])==[CORE+f'/artifact_index_r_reg[{bit}]/Q']
  assert words(x['driver_refs'])==['FDCE'] and words(x['startpoints'])==[words(x['drivers'])[0].rsplit('/',1)[0]+'/C']
  changed.append(dict(cell=x['cell'],pin=x['pin'],slice=x['slice'],bit=bit,root_decode=c['SELF_ADDR_B'],root_mask=c['SELF_MASK_B'],root_data_bits=[int(c['MEM.PORTB.DATA_LSB']),int(c['MEM.PORTB.DATA_MSB'])],prior=y,actual=x))
assert len(changed)==24 and Counter(x['bit'] for x in changed)=={10:8,11:8,12:8}
assert len({x['cell'] for x in changed})==8
replicas=sorted({words(x['actual']['drivers'])[0].rsplit('/',1)[0] for x in changed});assert len(replicas)==9
originals=[CORE+f'/artifact_index_r_reg[{b}]' for b in [10,11,12]]
assert all('/u_addr/' not in n for n in originals+replicas)
# Check the full effective cascade/address origin on existing per-pin native tables.
pred={n:(None if n in roots else words(mem[n,'CAS_IN_ADDR_B[0]']['driver_cells'])[0]) for n in cfg}
children={n:[] for n in cfg}
for n,parent in pred.items():
 if parent is not None:assert parent in cfg;children[parent].append(n)
assert all(len(x)<=1 for x in children.values())
chains=[];covered=set();changed_roots={x['cell'] for x in changed}
for root in roots:
 chain=[];n=root
 while n is not None:
  assert n not in chain;chain.append(n);covered.add(n);n=children[n][0] if children[n] else None
 assert cfg[chain[-1]]['CASCADE_ORDER_B']=='LAST'
 for n in chain[1:]:
  parent=pred[n]
  for bit in range(23):
   for port in ['A','B']:
    x=mem[n,f'CAS_IN_ADDR_{port}[{bit}]']
    assert words(x['drivers'])==[parent+f'/CAS_OUT_ADDR_{port}[{bit}]'] and words(x['driver_refs'])==['URAM288']
    want=words(mem[root,f'ADDR_{port}[{bit}]']['startpoints']) if bit<17 else [root+f'/CAS_OUT_ADDR_{port}[{bit}]']
    assert words(x['startpoints'])==want
 chains.append(dict(root=root,slice=cfg[root]['slice'],length=len(chain),members=chain,decode=[int(cfg[n]['SELF_ADDR_B'].split('h')[1],16) for n in chain],write_bits_changed=[10,11,12] if root in changed_roots else []))
assert covered==set(cfg)
assert all(sorted(x['length'] for x in chains if x['slice']==str(i))==[4,4,8,8,8,8] for i in [0,1])
start_changes=[dict(cell=k[0],pin=k[1],prior=old[k].get('startpoints'),actual=x.get('startpoints')) for k,x in mem.items() if old[k].get('startpoints')!=x.get('startpoints')]
assert len(start_changes)==168
assert sum(x['length'] for x in chains if x['root'] in changed_roots)==56
# No actual source changes elsewhere in the 34480 selected-pin records.
owner=load(ATT/'evidence/place_write_address_source_delta.json')
assert {(x['cell'],x['pin'],x['actual']['drivers']) for x in owner['failed_root_pins']}=={(x['cell'],x['pin'],x['actual']['drivers']) for x in changed}
assert sorted(owner['unique_drivers'])==[n+'/Q' for n in replicas]
q=load(NOW/'m003_qualification_place.json');assert q['errors']==['URAM root write-address bit source changed']*24 and not q['passed']
restore=load(NOW/'m003_qualification_restore.json');assert restore['passed'] and not restore['errors']
validator=bind(ROOT/'project/hardware/vivado/scripts/m003_joint_evidence.py');assert validator['sha256']=='7f8a7186558e566d4f6fdd11460b30fc68936e9218a0e0d5d38c63ece10bee05'
for i in [q['original_frozen_validator'],q['explicit_adapter']]:assert ident(Path(i['path']))==i
missing_scope=[]
for name in ['m003_stream_place_helper_pins.jsonl','m003_stream_place_meta_ref_cells.jsonl','m003_connection_place_endpoints.jsonl','m003_stream_place_reset_provenance.jsonl']:
 p=NOW/name
 with p.open() as f:count=sum('artifact_index_r_reg' in line for line in f)
 assert count==0;missing_scope.append(dict(path=str(p),artifact_index_rows=count));bind(p)
closure=load(ATT/'evidence/owner_terminal_and_source_closure.json')
assert closure['terminal']['native_exit_code']==1 and closure['terminal']['stop_reason'] is None and not closure['terminal']['owned_survivors']
assert closure['lock_free'] and closure['archive_bindings']==198 and len(closure['processes'])==17
assert all(x['current_matches'] and x['archive_matches'] for x in closure['source_checks'])
command=(NOW/'place_command_result.txt').read_text();assert 'native_tcl_code=0' in command
assert 'completed=0' in (NOW/'place_result.txt').read_text()
for n in ['physopt_command_result.txt','route_command_result.txt']:assert not (NOW/n).exists()
for p in [NOW/'m003_qualification_place.json',NOW/'m003_qualification_restore.json',NOW/'place_command_result.txt',NOW/'place_result.txt',ATT/'evidence/place_write_address_source_delta.json',ATT/'evidence/owner_terminal_and_source_closure.json',NOW/'vivado.log',NOW/'utilization_place.rpt',DBG/'utilization_debug_materialized.rpt',NOW/'clocks_place.rpt',NOW/'timing_place.rpt',ROOT/'project/hardware/rtl/attention/hap_attention_board_cohort16_core.sv',ROOT/'project/hardware/rtl/attention/hap_weight_meta_resident.sv',ROOT/'mission/M003_joint_routability_closure/g2_joint_design_freeze_2026-10-18.md',ROOT/'project/hardware/vivado/scripts/m003_joint_checks.tcl',Path('/home/user/EDA-202/vivado/vivado_2025.2/2025.2/data/verilog/src/unisims/URAM288.v')]:bind(p)
probe=dict(schema='A007_minimal_place_FF_replica_equivalence_scope_v1',new_EDA_by_A007=False,query_checkpoint=str(NOW/'place.dcp'),checkpoint_bytes=(NOW/'place.dcp').stat().st_size,checkpoint_identity='Owner binds current saved actual place DCP SHA; A007 has not read or hashed DCP.',max_seed_FFs=12,original_cells=originals,actual_replica_cells=replicas,
 required_cell_properties=['NAME','REF_NAME','ORIG_CELL_NAME (corroboration only)','INIT effective value with explicit export or bound primitive default model','DONT_TOUCH','LOC','BEL','PBLOCKS','IS_C_INVERTED','IS_D_INVERTED','IS_CLR_INVERTED'],
 required_pin_evidence=dict(pins=['D','CE','CLR','C','Q'],fields=['native pin identity/REF_PIN_NAME','actual IS_INVERTED; preserve unsupported/empty distinctly','direct net object and actual canonical hierarchical segment identity','unique leaf source pin/owner/ref or actual constant primitive','C clock names, 10ns core period, waveform and effective active edge']),
 output_binding='Keep actual replica Q, expected original-bit Q and exact 24 destination rows as separate fields. Bind existing memory-pin streams and actual place snapshot identity. Do not rewrite raw driver names or pretend original Q directly drives those roots.',
 sufficient_proof='For each replica versus its designated same-bit original FDCE in the same frozen place checkpoint: equal effective INIT, identical effective D, CE, asynchronous CLR and C active edge. Shared actual net/leaf-source identities plus equal pin/model inversion suffice; matching aliases or ORIG_CELL_NAME alone do not. Equal initial state and equal state transition imply Q equivalence at each sampling edge, with no new latency.',
 if_direct_inputs_differ='Only expand the differing D/CE/CLR/C combinational cone for these 12 FFs: actual LUT INIT/input map, invert/buffer truth function, constants and exact source boundary/state bit identities. Reuse existing actual RTL/proof anchors. Reject unknown/multiple sources, new sequential boundaries, different bit/state/clock/reset/enable/INIT. No broad fanout, full graph export, alternate checkpoint or implementation run is required merely to conduct this first probe.',
 protection_scope='34 protected A3 address FFs + four protected local CE/INC LUTs remain a separate existing complete qualification; do not treat unselected artifact_index as an A3 helper or grant it a blanket name-based exemption. Read actual DONT_TOUCH properties for all12; inherited hierarchy constraints only if needed to explain a conflict.',
 validation_after_proof=['Full original real place-data qualifier/entry replay with the explicit new same-state proof dependency; raw originals and failed AT001 receipt preserved.','Negative mutations: wrong bit/original association; changed D or CE; different reset source/polarity; clock/edge mismatch; INIT mismatch; new state/retiming; missing or multi-driver proof; changed checkpoint/exports/models; attempts to apply proof to an A3 helper or unknown replica.'],
 resource_scope='The observed nine FFs are distinct used write-source cells outside the frozen two17-bit read helpers; account them in physical tool resource observations. Do not silently enlarge the architecture-state budget or claim nine is the full replication count. Existing global placed register total increased342 relative to debug; this is a cross-stage net change, not same-stage synthesis budget evidence.')
probe_path=OUT/'R003_AT001_minimal12FF_equivalence_probe_scope_20261020.json';assert not probe_path.exists();probe_path.write_text(json.dumps(probe,ensure_ascii=False,indent=2)+'\n')
review=dict(schema='A007_R003_AT001_actual_write_address_delta_independent_review_v1',observed_utc=datetime.now(timezone.utc).isoformat(),execution='completed_one_shot_readonly_diagnosis',
 verdict='CURRENT_REPLICA_STATE_EQUIVALENCE_UNPROVEN_MINIMAL12FF_SCOPE_SUFFICIENT',
 applicability=dict(actual_place_POST_passed=False,prior_AT035_G4_admission_unchanged=True,no_physical_continuation_admission_from_this_review=True,whole_attempt='Natural native1/nullstop/survivors empty preserved; original place command Tcl0 and saved place.dcp are valid partial artifacts. No physopt or route command started.'),
 review=dict(independent_reconstruction='Read two existing selected memory-pin streams34480rows each and current/prior80configuration rows, not the107MB snapshot or61MBcell stream. Exact24changes and9driver identities match owner delta independently.',changed_rows=changed,unique_replica_cells=replicas,original_reference_cells=originals,changed_root_count=8,changed_bits=[10,11,12],changed_destination_counts=dict(Counter(x['bit'] for x in changed)),all_80_native_URAM_configurations_identical=True,all_other_selected_memory_driver_identities_unchanged=True,read_address_driver_changes=0,cascade_chains=chains,cascade_validation='Full existing address CAS edges and raw ancestry checked for A/B all23bits; all80cells covered by12same-slice chains. Root24source changes propagate to144descendant raw-startpoint rows; 168 raw-startpoint changes total and56memorycells downstream. No cascade wiring, mode, mask or register-configuration change observed.',
 bit_significance=dict(bits10_11='Actual row-address bits: URAM288.v line3312 ram_addr_b <= ADDR_B_int[11:0].',bit12='Actual bank/decode bit0 of ADDR_B[22:12]. SELF_MASK_B=11h7E0 has bit0 zero; compare expression at lines3217/3233 uses ~(ADDR^SELF_ADDR)|SELF_MASK. This bit is compared, not masked out.',decision='Cannot waive any of the24 changes as inactive or constant address bits.'),
 checker_cause=dict(source=validator,line=140,comparison='Hardcoded direct Q name artifact_index_r_reg[bit](_rep forbit<9) against actual first-root driver.',judgment='A name-exact check rejects the actual replicas. This explains the failure trigger but does not establish that the rejection is a false alarm. None of these replica D/CE/CLR/C/INIT functions is in the current selected exports.'),
 absent_state_exports=missing_scope,
 frozen_A3_protection=dict(address_FF=34,control_LUT=4,actual_helper_LUT=40,actual_helper_CARRY8=4,current_qualifier_only_errors='The24write-source mismatches; unchanged original qualifier checks each protected helper FF and controls, native pools and read-state cone separately.',write_counter_scope='Plain17-bit production artifact_index_r drives wr_addr atRTLline282; the two u_addr/address_r17-bit read-state helpers and their minimum protection are distinct. Current artifact FF actual protection properties await12FFprobe.',budget='G2 freezes new architectural state34FF and same-stage new synthesis totals; no budget change is approved here. A same-state tool replica adds physical FF resource but not an independent state variable or pipeline stage if the required proof passes.'),
 resources=dict(debug_registers=1021400,placed_registers=1021742,physical_cross_stage_delta=342,debug_flip_flops=1021398,placed_flip_flops=1021740,used_new_URAM_write_source_replica_cells=9,claim='These9are only the unique replica drivers observed at the24changed roots, not a complete design replication inventory. Physical resource deltas remain visible; neither9nor342is a demonstrated new synthesis architectural-budget increase.',RAM_and_DSP='BRAM941/URAM752/DSP5451 unchanged in the existing reports'),
 core_clock=dict(existing_global_clock='clk_out1_scalellm_vcu118_f05_bd_clk_core_0',period_ns=10,waveform_ns=[0,5],replica_clock_connectivity='Unproven until12FFpin/clock probe; a global100MHz clock alone is insufficient.'),
 actual_place_timing=dict(WNS_ns=-2.797,TNS_ns=-31090.396,WHS_ns=-0.565,THS_ns=-2157.578,WPWS_ns=0.0,signoff=False),
 owner_closure=dict(source_bindings=198,identities=17,lock_free=True,terminal_ended_utc=closure['terminal']['ended_utc'],native_exit=1,independent_live_process_polling=False)),
 recommendation=dict(minimal_probe=ident(probe_path),next='Owner performs one exact12FFactual-place read-only probe, binds raw FF state/control/model evidence, implements only a strict proven-equivalence validator adapter if established, and replays the full real place entry plus negatives. Reuse savedplace; no redundant new place. If semantic/protection/pool/budget changes are found, report toRoot for central decision.',ordinary_repair_scope='No new user approval gate is added by this review. The missing state-equivalence evidence is an existing technical dependency, not a requirement to redesign or await another preliminary A007 signoff.'),
 bounds=dict(no_EDA=True,no_process_control=True,no_polling=True,no_observer=True,no_wait=True,no_descendants=True,no_DCP_content_read=True,no_whole_snapshot_or_cell_stream_read=True,no_project_evidence_modified=True),evidence_identities=ids,delivery='Real message toRoot immediately after writing; A007 exits after this bounded diagnosis.')
review_path=OUT/'R003_AT001_write_address_delta_independent_review_20261020.json';assert not review_path.exists();review_path.write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
state_path=ROOT/'agent/A007/state.json';s=load(state_path);s.update(execution_state='completed',current_task='R003 AT001 write-address post-place delta independent diagnosis completed',stage='Exact24changes/9FDCE traced; semantic equivalence requires bounded12FFstateproof',blocker='Current place POST source equivalence not yet proven; no claim of design behavior failure',next_step='Sole owner performs exact12FFplaceDCPprobe and ordinary strict proof/adapter/full-real-entry replay; no A007 polling or wait',reported_at=review['observed_utc'],latest_review=str(review_path.relative_to(ROOT)),review_execution='R003_AT001_bounded_write_source_diagnosis_completed',current_turn_state='completed_no_observer_no_wait',delivery='Actual Root message pending',current_place_POST_passed=False,formal_reset_cdc_safety='OPEN');state_path.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n')
(ROOT/'agent/A007/status.md').write_text('''# A007：R003/AT001 写地址差异独立诊断完成

execution_state: completed

[独审](M003_SM015_SM017_review_20261018/R003_AT001_write_address_delta_independent_review_20261020.json)从两份原生 memory_pins 流独立确认：24项为 bits10/11/12 各8个FIRST根，驱动变为9个FDCE副本；80URAM配置逐字段相同，read地址、模式和级联连接未变。变化涉及的10/11行内位与12译码位均有效，不能按掩码忽略。

新副本D/CE/CLR/C/INIT不在当前完整选定导出范围内，故不能凭命名认定等价或误报。[最小12FF补采范围](M003_SM015_SM017_review_20261018/R003_AT001_minimal12FF_equivalence_probe_scope_20261020.json)为3原FF+9实际副本；同状态转移、同沿、同初值/复位证明后，owner可按常规严格适配与全真实place入口+反例重验继续，不增加用户审批。

两17位A3 helper仍34FF，另4控制LUT保护独立；artifact_index是不同写地址状态。已见9副本只代表这24端点用到的副本，非全设计复制总量。现全局place寄存器1021742较debug1021400增加342，须保留物理资源实态，不能直接改写为综合架构预算超出或自动豁免。

原place命令Tcl0、place.dcp保存；完整place POST失败、AT001自然native1原样保留，未运行后续physopt/route。先前AT035 G4限定审核不被改写为本次POST或route通过。WNS−2.797ns等最终时序仍未收敛。

本轮无EDA、进程控制、观察器、轮询、等待或后代；未读DCP/107MB快照/61MBcell流。实际通知Root后结束，由sole owner继续。
''')
print(json.dumps(dict(review=ident(review_path),minimal_probe=ident(probe_path),actual_changes=len(changed),replicas=len(replicas),current_equivalence='unproven'),ensure_ascii=False))
