from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,csv
R=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
P=R/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
O=Path(__file__).resolve().parent
def identity(p):
 p=Path(p).resolve();assert p.suffix.lower()!='.dcp';b=p.stat();h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(4194304),b''):h.update(block)
 a=p.stat();assert (b.st_size,b.st_mtime_ns)==(a.st_size,a.st_mtime_ns)
 return dict(path=str(p),bytes=a.st_size,sha256=h.hexdigest())
def read(p):return json.loads(Path(p).read_text())
old_path=R/'agent/A007/E008_R001_AT003_actual_stage_review_20261017/actual_before_pblock_export_review.json'
assert identity(old_path)['sha256']=='6bf82c5790780a01cb8223ccec0186bcf330ec2f834be65c9eb0d4253ab9c6a6'
old=read(old_path);checks=[]
for v in [x['actual'] for x in old['seven_actual_resource_before_ledgers_byte_equal_to_prior']]+old['evidence']:
 if Path(v['path']).name=='candidate_effective_physical.xdc':continue
 assert identity(v['path'])==v
 target=P/('stage_sources/' if '/stage_sources/' in v['path'] else '')/Path(v['path']).name
 actual=identity(target);assert (actual['bytes'],actual['sha256'])==(v['bytes'],v['sha256'])
 checks.append(dict(actual=actual,accepted_prior=v,byte_equal=True))
assert len(checks)==13
old_xdc=Path(old['exported_XDC']['path']);assert identity(old_xdc)==old['exported_XDC']
new_xdc=P/'candidate_effective_physical.xdc';a=old_xdc.read_text().splitlines();b=new_xdc.read_text().splitlines()
assert len(a)==len(b)
changed=[i for i,(x,y) in enumerate(zip(a,b),1) if x!=y]
assert changed==[4]
assert a[3]=='# Command Used: write_xdc -type physical '+str(old_xdc)
assert b[3]=='# Command Used: write_xdc -type physical '+str(new_xdc)
# Every executable line and membership string is exactly preserved, and actual P is byte-equal.
assert a[:3]+a[4:]==b[:3]+b[4:]
readback=dict(x.split('=',1) for x in (P/'candidate_pblock_readback.txt').read_text().splitlines())
assert readback==old['Pblock_native_readback']
regions=list(csv.DictReader((P/'candidate_actual_SLR2_ranges.tsv').open(),delimiter='\t'))
assert regions==old['thirty_actual_SLR2_regions']
assert {x['actual_clock_region'] for x in regions}=={f'X{x}Y{y}' for x in range(6) for y in range(10,15)}
assert not (P/'candidate_constraint_conflicts.txt').read_text().strip()
marker=[]
with (P/'vivado.log').open() as f:
 for i,line in enumerate(f,1):
  if line.rstrip()=='E008_QUERY_COMPLETED hard_SLR2_pblock members=9491':
   marker.append(dict(source_path=str(P/'vivado.log'),line_number=i,text=line.rstrip()));break
assert len(marker)==1
result=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),execution='COMPLETED_ACTUAL_RESOURCE_BEFORE_PBLOCK_EXPORT_DELTA',verdict='ACCEPT_SAME_RESOURCE_BEFORE_POLICY_AND_NATIVE_HARD_SLR2_EXPORT',applicability='AT004 pre-place substeps only; after preservation/fullpreplace and physical success not established',review='A007 accepted no new gate',prior_independent_review=identity(old_path),thirteen_resource_before_and_geometry_source_artifacts_byte_equal_to_AT003=checks,proven_equal_before_scope=old['proven_equal_before_scope'],Pblock_native_readback=readback,thirty_actual_SLR2_regions=regions,all_P_existing_constraint_rows=9491,existing_LOC_relative_macro_or_Pblock_conflicts=False,exported_XDC=identity(new_xdc),export_delta=dict(changed_lines=[4],change='Native command comment output directory only; every other byte-equivalent line, including every executable command/member, preserved',Tcl_executed_by_reviewer=False),exported_candidate_members=9491,exported_member_names_exactly_equal_actual_P=True,exported_member_equality_basis='Actual P byte-equal and all prior independently parsed XDC executable member commands byte-equal',exported_member_duplicates=0,exported_geometry_equals_native_readback=True,exported_hard_policy_explicit=True,other_policy_defaults=old['other_policy_defaults'],native_closed_event=marker[0],after_preservation_exists_at_observation=(P/'candidate_policy_preservation.txt').exists(),after_preservation_not_reviewed_in_this_record=True,native_site_count_provenance=old['native_site_count_provenance'],live_log_identity='Observed closed event only, not immutable whole growing logfile',membership_review=identity(O/'pre_place_membership_incremental_review.json'),audit_program=identity(__file__),no_EDA_DCP_signal_or_lock_control=True)
p=O/'actual_before_pblock_export_incremental_review.json'
with p.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
md='''# AT004 资源、约束前状态、Pblock及物理XDC增量审核

execution：闭合子步骤核查完成；verdict：接受；applicability：本轮before/资源/实际Pblock-export；review：A007。

7份资源与before账本和6份几何/约束/成员/源码证据均与已审AT003逐字节一致。9514资源对象、9525 policy对象（9514缓存、10个根/祖先与1个内部层级fresh）保持；RLOC_ORIGIN显式unsupported，其余11字段supported。

真实SLR2范围30个clock regions（X0–5/Y10–14），hard/nonexclusive/non-routing-contained三属性全0，9491个P成员、原生site78266，既有冲突为空。当前物理XDC1598540字节，仅第4行命令注释中的输出目录变化；全部可执行约束和9491个成员字符串与已审导出相同，实际P账本也相同。工具日志实际记录完成事件。

约束后fresh schema/policy preservation不在本记录通过范围，完整pre-place与物理实现仍待后续实际结果。站点清单不是空闲容量；约束设置不是已成功迁移。无EDA/DCP内容访问/进程或锁控制，无新审批门。
'''
with (O/'actual_before_pblock_export_incremental_review.md').open('x') as f:f.write(md)
print(json.dumps(dict(review=identity(p),human=identity(O/'actual_before_pblock_export_incremental_review.md'),actual_XDC=identity(new_xdc),after_preservation_exists=result['after_preservation_exists_at_observation']),ensure_ascii=False))
