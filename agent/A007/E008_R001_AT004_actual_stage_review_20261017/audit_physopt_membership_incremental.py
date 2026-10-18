#!/usr/bin/env python3
"""A007 incremental current physopt membership/origin/position audit."""
import sys
sys.dont_write_bytecode=True
def guard(event,args):
    if event=='open' and args and isinstance(args[0],(str,bytes)):
        p=args[0].decode() if isinstance(args[0],bytes) else args[0]
        if p.lower().endswith('.dcp'):raise RuntimeError('A007 DCP content access forbidden')
sys.addaudithook(guard)
import hashlib,json,re
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
RPT=ROOT/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
AT=ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation'
OUT=Path(__file__).resolve().parent
checks={}
def identity(path):
    p=Path(path).resolve();assert p.suffix.lower()!='.dcp';before=p.stat();h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4194304),b''):h.update(b)
    after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    v=dict(path=str(p),bytes=after.st_size,sha256=h.hexdigest());checks[str(p)]=v;return v
def verify(v):
    a=identity(v['path']);assert (a['bytes'],a['sha256'])==(v['bytes'],v['sha256']);return a
def read(p):return json.loads(Path(p).read_text())
priorid=identity(OUT/'place_membership_reconciliation_review.json');assert priorid['sha256']=='cfbb3047dac1dda52562d17ac38da8245d4299ce06f7eab223e76afb1bdc59c2'
prior=read(priorid['path']);priorchecks={v['path']:v for v in prior['all_identity_checks']}
globalid=identity(OUT/'physopt_global_POST_review.json');assert globalid['sha256']=='e5dacc52b15e8e7a55d488bf4b110b1c73e630639d5612884ef97052b1b6a600'
currentchecks={v['path']:v for v in read(globalid['path'])['all_identity_checks']}
factpath=AT/'physopt_membership_reconciliation_closed_facts.json';factid=identity(factpath)
assert factid['bytes']==4374 and factid['sha256']=='5d35ccbb032fb0acdd4c1b454831893b22041a9205ca104a80e5ba5a71a95499'
facts=read(factpath);equal_artifacts=[]
for v in facts['artifacts']:
    current=verify(v);p=Path(current['path']);old=p.with_name(p.name.replace('_physopt','_place'))
    assert identity(old)==priorchecks[str(old)]
    assert not p.is_symlink() and p.stat().st_ino!=old.stat().st_ino
    if p.name!='candidate_reconciliation_physopt.json':
        assert p.read_bytes()==old.read_bytes();equal_artifacts.append(dict(current=current,accepted_place=identity(old)))
assert len(equal_artifacts)==12
for basename in ['candidate_membership','candidate_physical_mapping','candidate_pblock_actual','candidate_property_support']:
    p=RPT/f'{basename}_physopt.tsv';old=RPT/f'{basename}_place.tsv'
    assert identity(old)==priorchecks[str(old)]
    assert p.read_bytes()==old.read_bytes();equal_artifacts.append(dict(current=identity(p),accepted_place=identity(old)))
current=read(RPT/'candidate_membership_physopt.json');old=read(RPT/'candidate_membership_place.json');assert identity(RPT/'candidate_membership_place.json')==priorchecks[str(RPT/'candidate_membership_place.json')]
rebound=['phase','P_parent_policy','native_exact_hierarchy_resources','actual_membership']
assert {k:v for k,v in current.items() if k not in rebound}=={k:v for k,v in old.items() if k not in rebound}
assert current['phase']=='physopt'
for k in rebound[1:]:verify(current[k])
def normalized(path):return [line for i,line in enumerate(Path(path).read_text().splitlines()) if not (i<14 and (re.match(r'^\|\s*(Date|Command|Design State)\s*:',line) or re.fullmatch('-+',line)))]
assert normalized(current['native_exact_hierarchy_resources']['path'])==normalized(old['native_exact_hierarchy_resources']['path'])
assert re.search(r'^\| Design State\s+: Physopt postPlace$',Path(current['native_exact_hierarchy_resources']['path']).read_text(),re.M)
recon=read(RPT/'candidate_reconciliation_physopt.json');oldrecon=read(RPT/'candidate_reconciliation_place.json')
assert {k:v for k,v in recon.items() if k!='native_origin_query'}=={k:v for k,v in oldrecon.items() if k!='native_origin_query'}
verify(recon['native_origin_query']);assert Path(recon['native_origin_query']['path'])==RPT/'candidate_native_origin_query_physopt.txt'
assert recon['qualified'] and recon['issues']==[] and recon['explained_replacements']=={}
assert recon['original_count']==recon['literal_count']==recon['actual_physical_Pblock_count']==len(recon['resolved'])==len(recon['lineage'])==9491
assert all(r['lineage']=='ORIGINAL_SURVIVING' and r['SLR']=='SLR2' and r['LOC'] for r in recon['lineage'])
assert facts['actual_counts']=={k:recon[k] for k in ['original_count','literal_count','actual_physical_Pblock_count']}
assert facts['resolved_P']==facts['lineage_rows']==9491 and facts['all_original_surviving'] and facts['all_resolved_P_in_SLR2'] and facts['replacements']==0 and facts['issues']==[]
assert facts['native_origin_query']==(RPT/'candidate_native_origin_query_physopt.txt').read_text()
assert facts['effective_pblock']==(RPT/'candidate_effective_pblock_physopt.txt').read_text()
for name in ['runtime_hooks.tcl','candidate_hooks.tcl','evidence_adapter.py']:
    p=RPT/'stage_sources'/name;assert identity(p)==currentchecks[str(p)]
out=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),reviewer='A007',execution='COMPLETED_CURRENT_PHYSOPT_MEMBERSHIP_NATIVE_ORIGIN_POSITION_INCREMENTAL_REVIEW',verdict='ACCEPT_FRESH_PHYSOPT_EXACT_C01_9491_ORIGINAL_P_ALL_IN_SLR2_SUBSTEP',applicability='AT004 actual physopt member/origin/position evidence; index/cut/bounded timing/combined phase separate',review='INDEPENDENT_SUBSTEP_ACCEPTED_NO_NEW_GATE',current_engineering_facts=factid,accepted_place_full_replay=priorid,accepted_current_global_POST=globalid,
    same_byte_current_artifacts=equal_artifacts,current_membership_summary=identity(RPT/'candidate_membership_physopt.json'),membership_only_phase_and_artifact_bindings_changed=True,current_reconciliation=identity(RPT/'candidate_reconciliation_physopt.json'),reconciliation_only_current_origin_receipt_binding_changed=True,
    RAW=9514,S=9507,P=9491,all_original_surviving=True,replacements=0,all_LOC_BEL_nonempty=True,all_P_in_SLR2=True,all_positions_and_policy_fields_byte_equal_accepted_place=True,current_effective_Pblock=prior['current_effective_Pblock'],current_native_origin_query=prior['native_origin_query'],native_origin_list_empty_with_successful_supported_query=True,
    native_candidate_resource_body_equal_accepted_place=True,actual_phase='Physopt postPlace',native_candidate_packed_utilization_by_SLR=prior['native_candidate_packed_utilization_by_SLR'],all_identity_checks=list(checks.values()),audit_program=identity(__file__),
    limits=['Current phase native output files and current successful origin receipt are reviewed; unchanged content does not infer future route behavior.',
      '9491 P is physical-object count; native packed resource counts and routing demand are separate.',
      'No complete physopt candidate phase, fresh native index/cut/timing or route acceptance from this record.',
      'Global hold FAIL/high congestion/formal reset-CDC-IO OPEN remain.',
      'No EDA/native queries, DCP content access, process/lock control, engineering edits or new gate/agent.'])
output=OUT/'physopt_membership_reconciliation_review.json'
with output.open('x') as f:json.dump(out,f,ensure_ascii=False,indent=2);f.write('\n')
human=OUT/'physopt_membership_reconciliation_review.md'
with human.open('x') as f:f.write('''# AT004 physopt成员与SLR2落区增量审核

execution：当前phase成员、原生origin与实际位置增量审核完成。verdict：接受C01原始9491个P全部SLR2这一子步骤。applicability：physopt成员/位置证据；完整候选phase另审。review：独立接受，无新增停点。

16份当前原始表/回执同已完整重放的actual place证据逐字节相同，且为独立当前输出文件。RAW9514/S9507/P9491；完整membership仅phase与artifact重新绑定，reconciliation仅当前origin回执路径重新绑定。9491个original/literal/actualPblock/resolved一一对应，ORIGINAL_SURVIVING全量，无缺失或替换；LOC/BEL、SLR2、native区域与物理policy保持。

当前native ORIG查询code0/executed1/property-supported1，空origin表有成功证据。有效Pblock范围CLOCKREGION_X0Y10:X5Y14、三policy全0、physical_members9491。原生资源报告为Physopt postPlace，正文同place；P对象数不等于packed资源或路由需求。

本次不验收尚未闭合的current index/cut/bounded timing或完整阶段。hold FAIL、高拥塞、正式安全OPEN保持；未调用EDA、读取/hash DCP、控制进程/锁或改工程。
''')
print(json.dumps(dict(review=identity(output),human=identity(human),same_byte_artifacts=len(equal_artifacts)),ensure_ascii=False))
