#!/usr/bin/env python3
"""A007 bounded restored-stage audit; no DCP access, native tools or process control."""
import sys
sys.dont_write_bytecode=True
import pathlib,json,hashlib,csv,ast,re,math,tkinter
from collections import Counter
from datetime import datetime,timezone
ROOT=pathlib.Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
REPORT=ROOT/'project/hardware/vivado/reports/m002_E008_R001_AT003_C01_physical_xdc_fix_full_implementation'
ATTEMPT=ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT003_C01_physical_xdc_fix_full_implementation'
OUT=pathlib.Path(__file__).resolve().parent
SOURCES=REPORT/'stage_sources'
checks={}
def identity(path):
    p=pathlib.Path(path).resolve()
    assert p.suffix.lower()!='.dcp','Reviewer must never read/hash DCP'
    before=p.stat(); h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    value=dict(path=str(p),bytes=after.st_size,sha256=h.hexdigest());checks[str(p)]=value;return value
def verify(v): assert identity(v['path'])==v;return v
def read(p):return json.loads(pathlib.Path(p).read_text())
def kv(p):return dict(x.split('=',1) for x in pathlib.Path(p).read_text().splitlines() if '=' in x)
def require(c,m):assert c,m
def rows(p):return list(csv.DictReader(pathlib.Path(p).open(),delimiter='\t'))
def save(p,v):
    with pathlib.Path(p).open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')

binding=read(ATTEMPT/'input_bindings.json');verify(binding['parent'])
parent=read(binding['parent']['path']);checkpoint=parent['checkpoint']
actual=read(REPORT/'pre_place_evidence.json');identity(REPORT/'pre_place_evidence.json')
assert actual['phase']=='restored_completed_pre_place' and actual['checkpoint']==checkpoint
assert actual['diagnostic_eligible'] is True and actual['physical_signoff'] is False and actual['formal_reset_cdc_safety']=='OPEN'
assert actual['inherited_measurements']=='original complete POST; not newly measured in this restart'
assert actual['recovery_parent']==binding['parent']
for k,v in actual.items():
    if isinstance(v,dict) and set(v)=={'path','bytes','sha256'} and k!='checkpoint':verify(v)
for v in actual['historical_command_receipts'].values():verify(v)
old=read(actual['inherited_integrity']['path']);old_pre=read(actual['inherited_pre_place']['path'])
assert old_pre['checkpoint']==checkpoint and old_pre['integrity']==actual['inherited_integrity']
assert old['gate_issues']==[] and old['reset_structure']['qualified'] and old['reset_structure']['issues']==[]
assert old['reset_fanout_observation']['qualified'] and old['debug_clock_observation']['relationship_qualified']
prior=ROOT/'project/E005_m002_optimized_implementation/experiment_results/runs/R005/AT003_completed_debug_pre_place_review_evidence.json'
identity(prior)
for k,v in parent['synthesis'].items():
    if isinstance(v,dict) and set(v)=={'path','bytes','sha256'}:verify(v)

# Reuse accepted startup source qualification; independently confirm all current bytes again.
verify(binding['frozen_inputs']['freeze'])
production=read(binding['frozen_inputs']['freeze']['path'])['files'];assert len(production)==144
for value in production:verify(value)
for value in binding['source_bindings']:
    verify(value)
    archive=SOURCES/pathlib.Path(value['path']).name
    actual_id=identity(archive)
    assert (actual_id['bytes'],actual_id['sha256'])==(value['bytes'],value['sha256'])

# Actual inherited constraints, registry metadata and retained bytes.
constraints=read(REPORT/'constraints_pre_place_restore.json');verify(actual['live_constraints'])
assert constraints['phase']=='pre_place_restore' and constraints['mode']=='embedded_checkpoint_inherited'
assert len(constraints['hashes'])==175 and constraints['hashes']==parent['hashes']
assert len(constraints['candidate_metadata'])==162
assert constraints['metadata']==constraints['candidate_metadata']==parent['source_metadata']
assert constraints['source_archives']==parent['source_archives'] and len(constraints['source_archives'])==13
assert constraints['generated_source_candidates']==parent['generated_source_candidates']
assert constraints['tool_debug_metadata']==parent['tool_debug_metadata']=={}
resolved=[]
for name,digest in constraints['hashes'].items():
    path=pathlib.Path(name)
    source='original'
    if not path.is_file():
        v=constraints['source_archives'][name];verify(v);path=pathlib.Path(v['path']);source='retained_original_bytes'
    value=identity(path);assert value['sha256']==digest
    resolved.append(dict(original_path=name,source=source,actual=value))
verify(constraints['registry']);registry=rows(constraints['registry']['path'])
assert len(registry)==162 and len({r['path'] for r in registry})==162
fields=['USED_IN','USED_IN_SYNTHESIS','USED_IN_IMPLEMENTATION','IS_ENABLED','SCOPED_TO_REF','SCOPED_TO_CELLS','PROCESSING_ORDER']
assert {r['path']:[r[k] for k in fields] for r in registry}==constraints['metadata']
assert all(r['SHA256']==constraints['hashes'][r['path']] for r in registry)
verify(constraints['actual_reads']);reads=read(constraints['actual_reads']['path'])
assert reads==dict(mode='embedded_checkpoint_inherited',inherited_from=binding['parent'],new_actual_reads=[])
overlay=constraints['candidate_physical_overlay'];assert overlay['unchanged_embedded_source_count']==175
for v in overlay['artifacts'].values():verify(v)

# Only compile these previously inspected, pure text parsers from actual archived source.
source_path=SOURCES/'m002_physical_evidence.py';source=source_path.read_text();identity(source_path)
selected={'check_timing_counts','timing_objects','reset_io_coverage','placement_coverage','debug_clock_facts'}
functions=[v for v in ast.parse(source).body if isinstance(v,ast.FunctionDef) and v.name in selected]
assert {v.name for v in functions}==selected
namespace=dict(Path=pathlib.Path,re=re,math=math,file_id=identity,require=require)
exec(compile(ast.Module(body=functions,type_ignores=[]),str(source_path),'exec'),namespace)
coverage=namespace['check_timing_counts'](REPORT/'check_timing_pre_place_restore.rpt')
assert coverage==actual['live_clock_coverage'] and namespace['placement_coverage'](coverage,0)
assert coverage['constant_clock']==0
io=namespace['reset_io_coverage'](REPORT/'check_timing_pre_place_restore.rpt')
assert io==dict(known_async_reset_inputs=['pcie_perstn'],known_ddr_reset_outputs=['ddr4_sdram_c1_reset_n','ddr4_sdram_c2_reset_n'])
debug=namespace['debug_clock_facts'](REPORT/'debug_restore.tsv',effective_path=pathlib.Path(old['debug_clock_observation']['effective_hub_constraints']['path']))
assert debug==actual['live_debug_clock_observation'] and debug['relationship_qualified']
for k in ['input_clocks','outputs','clocks','actual_output_drivers','actual_output_startpoints','fanout_endpoint_count','fanout_by_output','fanout_clock_names','actual_input_hz','divider']:
    assert debug[k]==old['debug_clock_observation'][k]
def endpoints(path):return {s for s in pathlib.Path(path).read_text().splitlines() if s.startswith('DEBUG_ENDPOINT_CLOCKS\t')}
assert endpoints(REPORT/'debug_restore.tsv')==endpoints(old['debug_clock_observation']['source']['path'])
assert debug['fanout_endpoint_count']==530 and not debug['declared_matches_actual_input']

preflight=(REPORT/'restored_preflight.tsv').read_text().splitlines()
assert preflight[-1]=='PREFLIGHT_ISSUES\t' and sum(x.startswith('PREFLIGHT_ISSUES\t') for x in preflight)==1
assert any(x.startswith('BLACKBOX_COUNT\t0\t') for x in preflight)
reset_counts={}
for label,key in [('ASYNC_SEQUENTIAL_COUNT','async_reset_chains'),('AUX_SEQUENTIAL_COUNT','aux_chains')]:
    values=[x.split('\t') for x in preflight if x.startswith(label+'\t')]
    assert len({v[1] for v in values})==len(values)
    assert {v[1]:int(v[2]) for v in values}=={r['root']:4 for r in old['reset_structure'][key]}
    reset_counts[label]=dict(chains=len(values),sequential_per_chain=4)
assert reset_counts['ASYNC_SEQUENTIAL_COUNT']['chains']==7 and reset_counts['AUX_SEQUENTIAL_COUNT']['chains']==4
targets=[x.split('\t') for x in preflight if x.startswith('TARGET\t')]
assert len(targets)==6 and all(v[2]=='EXACT_NAME_MATCHES=1' and v[1]==v[3] for v in targets)
tcl=tkinter.Tcl()
families={v[1]:list(tcl.splitlist(v[2])) for v in (x.split('\t') for x in preflight) if v[0]=='CLOCK_FAMILY'}
periods={(v[1],v[2]):float(v[3]) for v in (x.split('\t') for x in preflight) if v[0]=='CLOCK_PERIOD'}
assert len(families)==3 and len(set(sum(families.values(),[])))==sum(len(v) for v in families.values())
for port,primary,period,generated in [('pcie_refclk_p','pcie_refclk',10.,10.),('default_250mhz_clk1_clk_p','default_250mhz_clk1_clk_p',4.,5.),('default_250mhz_clk2_clk_p','default_250mhz_clk2_clk_p',4.,5.)]:
    assert primary in families[port] and periods[(port,primary)]==period
    assert any(c!=primary and periods[(port,c)]==generated for c in families[port])

guard=kv(REPORT/'pre_place_restore_guard.txt');receipt=kv(REPORT/'pre_place_restore_command_result.txt')
assert guard==dict(completed='1',blackboxes='0',drc_blockers='0',clock_groups_verified='1')
assert receipt['phase']=='pre_place_restore' and receipt['command']=='m002_live_pre_place_restore' and receipt['native_tcl_code']=='0'
assert int(receipt['ended_epoch'])>=int(receipt['started_epoch'])
drctext=(REPORT/'drc_pre_place_restore.rpt').read_text()
drcrows=re.findall(r'^\|\s*([A-Z]+-\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|$',drctext,re.M)
assert len(drcrows)==6 and all(v[1]=='Warning' for v in drcrows) and sum(int(v[3]) for v in drcrows)==15914
assert len(re.findall(r'^\S+#\d+ Warning$',drctext,re.M))==15914
assert not re.search(r'^\S+#\d+ (Error|Critical Warning)$',drctext,re.M)
runtime=kv(REPORT/'restored_runtime_settings.txt');assert runtime['threads']=='8' and runtime['ip_cache_after']=='disable'
mode=kv(REPORT/'restored_checkpoint_mode.txt');assert mode['checkpoint']==checkpoint['path'] and mode['execution_mode']=='checkpoint_restored_commands'
policy=dict(v.split('\t',1) for v in (REPORT/'candidate_runtime_policy.tsv').read_text().splitlines())
assert policy['threads']=='8' and policy['ip_cache']=='disable'
assert [policy[k] for k in ['place_directive','physopt_directive','route_directive']]==['SSI_SpreadSLLs','Default','Default']
command=read(REPORT/'command.json');identity(REPORT/'command.json')
assert command['execution_mode']=='checkpoint_restored_commands' and command['synthesis']==parent['synthesis']
assert command['environment']['HAP_RECOVERY_CHECKPOINT']==checkpoint['path']

# Existing 80 boundaries are inherited evidence, not a fresh AT003 pre-place census.
protected=[];synth_dir=pathlib.Path(parent['synthesis']['manifest']['path']).parent
for directory,phase in [(synth_dir,'synth'),(pathlib.Path(parent['source_report']),'place'),(pathlib.Path(parent['source_report']),'physopt')]:
    path=directory/f'optimized_boundaries_{phase}.tsv';values=rows(path);assert len(values)==len({v['cell'] for v in values})==80
    assert Counter(v['scope'] for v in values)==dict(input=48,gate=16,down=16)
    for row in values:
        assert row['DONT_TOUCH']=='1'
        expected={'input':('LUT6',256,'FDCE'),'gate':('LUT1',384,'FDRE'),'down':('LUT1',512,'FDRE')}[row['scope']]
        assert row['REF_NAME']==expected[0] and int(row['leaf_input_pins'])==expected[1]
        assert row['load_REF_counts']==f'{expected[2]} {expected[1]}' and row['load_pin_counts']==f'CE {expected[1]}'
    result_path=directory/f'optimized_structure_{phase}_result.txt';result=kv(result_path)
    assert result['issues']=='' and result['boundary_contract']=='48input_16gate_16down'
    protected.append(dict(phase=phase,source_scope='inherited same successful E005 lineage; not current fresh measurement',ledger=identity(path),result=identity(result_path),boundaries=80,all_DONT_TOUCH_1=True))
identity(synth_dir/'optimized_control_sources_synth.tsv')
original_source=pathlib.Path(parent['source_report'])/'stage_sources/m002_optimized_structure.tcl'
assert identity(original_source)['sha256']==identity(SOURCES/'m002_optimized_structure.tcl')['sha256']
common=(SOURCES/'m002_diagnostic_common.tcl').read_text()
assert 'm002_optimized_structure $point $::m002_report_dir' in common

# Freeze-qualified log prefix chronology, never hash a still-growing whole log as immutable.
prefix=(REPORT/'pre_place_restore_log_snapshot.txt').read_bytes()
frozen=ATTEMPT/'pre_place_and_place_invocation_log_snapshot.txt';later=frozen.read_bytes();identity(frozen)
assert later.startswith(prefix)
with (REPORT/'vivado.log').open('rb') as stream:assert stream.read(len(later))==later
assert f"Command: open_checkpoint {checkpoint['path']}" in prefix.decode(errors='replace')
assert b'Command: place_design' not in prefix
place_rows=[dict(line=i,text=s) for i,s in enumerate(later.decode(errors='replace').splitlines(),1) if s.startswith('Command: place_design')]
assert len(place_rows)==1 and place_rows[0]['text']=='Command: place_design -directive SSI_SpreadSLLs'
assert b'Phase 1.2' in later and b'place_design completed successfully' not in later
facts=read(ATTEMPT/'pre_place_closed_stage_facts.json');identity(ATTEMPT/'pre_place_closed_stage_facts.json')
for v in facts['artifacts']:verify(v)
verify(facts['producer'])

result=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),reviewer='A007',execution='CLOSED_PRE_PLACE_EVIDENCE_REVIEW_COMPLETED',
 verdict='ACCEPT_RESTORED_PRE_PLACE_DIAGNOSTIC_QUALIFICATION_AND_ACTUAL_PLACE_INVOCATION',
 applicability='AT003 C01 only; source full POST inherited, current bounded live restoration checks fresh; place completion not established',review='COMPLETE',
 actual_pre_place=identity(REPORT/'pre_place_evidence.json'),actual_engineering_facts=identity(ATTEMPT/'pre_place_closed_stage_facts.json'),
 parent=actual['recovery_parent'],engineering_DCP_content_identity=checkpoint,reviewer_DCP_read_or_hash=False,
 inherited_full_POST=dict(integrity=actual['inherited_integrity'],pre_place=actual['inherited_pre_place'],accepted_independent_prior_review=identity(prior),
    reset_structure_and_fanout_qualified=True,classified_reset_CDC=8,new_critical=0,scope='Accepted historical complete source POST reused; no new AT003 full reset graph/CDC/BRAM proof asserted'),
 production_input_count=144,archived_runtime_source_count=len(binding['source_bindings']),all_identity_checks=list(checks.values()),
 constraints=dict(mode='embedded_checkpoint_inherited',source_count=175,metadata_count=162,retained_source_count=13,source_resolution=resolved,new_actual_reads=[],overlay_artifacts=overlay['artifacts']),
 fresh_live=dict(clock_coverage=coverage,reset_IO=io,reset_sanity=reset_counts,target_count=6,clock_family_counts={k:len(v) for k,v in families.items()},
    debug_clock=debug,DRC=dict(blockers=0,warning_checks=15914,rules=[dict(rule=v[0],severity=v[1],checks=int(v[3])) for v in drcrows]),
    native_guard=guard,native_receipt=receipt,runtime=runtime,policy=policy),
 protected_80_inherited=protected,protected_80_fresh_pre_place='NOT_NEWLY_MEASURED',fresh_80_POST_check_preserved=True,
 native_place_invocation=place_rows,place_completion='PENDING_ACTUAL_COMMAND_RECEIPT_FULL_POST_AND_LOCALITY',
 candidate_reviews=[identity(OUT/n) for n in ['pre_place_membership_incremental_review.json','actual_before_pblock_export_review.json','actual_policy_preservation_review.json','pre_place_native_index_alias_review.json','pre_place_directed_cut_timing_review.json']],
 limits=['No fresh full 80-boundary table at restored pre-place; inherited synth and later successful source place/physopt are distinguished; current stage fresh tables required at natural POST.',
   'Original full source POST and its hold/pulse-width failures, vendor exception limitations, formal CDC/reset/IO OPEN remain; current live DRC has warnings despite zero blockers.',
   'Debug input declared300MHz versus actual50MHz mismatch and divider=false retained; 530 actual endpoints are clocked but this is diagnostic relationship only.',
   'Synthesis supervision observation gap and UNKNOWN original waits remain inherited history.',
   'No place/physopt/route success, congestion improvement, full timing signoff or bitstream claim.',
   'No native tool, DCP read/hash, process signal, lock acquisition/control, production edit or new approval gate.'],
 audit_program=identity(__file__))
save(OUT/'restored_pre_place_global_review.json',result)
text='''# AT003 恢复 pre-place 与真实布局启动独立审核

execution：独立证据核查完成；verdict：接受恢复后的诊断资格与真实 place 调用；applicability：AT003/C01，本轮有限 live 检查与父完整 POST 分列；review：完成。

144 项生产输入、39 项原归档运行源身份保持。175 个继承约束来源全部核对实际或保留原字节，162 项 metadata 与真实 registry 一致、13 个来源归档保持；本轮 new_actual_reads=[]。候选 overlay 与已审 membership/Pblock/policy/cut/timing 身份一致。

本轮 native restore 回执0，blackbox0、DRC blockers0，6类合计15,914条 Warning 保留。内部 no_clock/constant_clock/pulse_width_clock/unconstrained 均0；三时钟族互不相交；7 async 与4 AUX复位链各4级，6个精确目标存在。外部 reset input1/output2未设delay继续OPEN。debug实际50MHz、2×265端点与父证据一致；声明300MHz差异保留。

完整 reset/CDC/BRAM/原pre-place POST 按同身份旧证据复用，不写成本轮新测。80个保护边界的旧 synth/place/physopt 三表独立核得48/16/16、CE负载及DONT_TOUCH全1；当前恢复pre-place没有新80全表，已归档原生POST检查保持，后续当前place/physopt/route各自再核。

两份冻结日志前缀与当前日志前缀一致，先完成恢复检查，随后真实 `place_design -directive SSI_SpreadSLLs` 并进入Phase1.2。place完整回执、POST/locality、physopt/route及正式时序仍待实测。正常实现继续；无新增审批门。

机器证据：`restored_pre_place_global_review.json`。审核未读取或哈希DCP、未执行EDA或控制进程/锁。
'''
with (OUT/'restored_pre_place_global_review.md').open('x') as f:f.write(text)
print(json.dumps(dict(review=identity(OUT/'restored_pre_place_global_review.json'),human=identity(OUT/'restored_pre_place_global_review.md'),checks=len(checks),constraint_sources=Counter(v['source'] for v in resolved)),ensure_ascii=False))
