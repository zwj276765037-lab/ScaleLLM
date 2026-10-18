from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,csv,tkinter
R=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');O=Path(__file__).resolve().parent
P=R/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
def identity(p):
 p=Path(p).resolve();assert p.suffix.lower()!='.dcp';a=p.stat();h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(4194304),b''):h.update(x)
 b=p.stat();assert (a.st_size,a.st_mtime_ns)==(b.st_size,b.st_mtime_ns)
 return dict(path=str(p),bytes=b.st_size,sha256=h.hexdigest())
def read(p):return json.loads(Path(p).read_text())
prior=R/'agent/A007/E008_R001_AT003_actual_stage_review_20261017/actual_policy_preservation_review.json'
assert identity(prior)['sha256']=='0036165bfd7f2f8f0c2c1e497a9242f3d5334598c03220a8b53ad6bc2459d5bc'
old=read(prior);checks=[]
for row in old['evidence']:
 assert identity(row['path'])==row
 actual=identity(P/Path(row['path']).name);assert (actual['bytes'],actual['sha256'])==(row['bytes'],row['sha256'])
 checks.append(dict(actual=actual,accepted_prior=row,byte_equal=True))
assert len(checks)==11
support=list(csv.DictReader((P/'candidate_policy_support_after.tsv').open(),delimiter='\t'))
schemas=list(csv.DictReader((P/'candidate_policy_schemas_after.tsv').open(),delimiter='\t'))
assert len(support)==len({v['NAME'] for v in support})==9525 and len(schemas)==17
assert {v['support_id'] for v in support}=={v['support_id'] for v in schemas}
assert all(v['schema_source']=='FRESH_NATIVE_LIST_PROPERTY' and v['RLOC_ORIGIN_schema_state']=='UNSUPPORTED_IN_ACTUAL_NATIVE_SCHEMA' and v['RLOC_ORIGIN_native_tcl_code']=='0' and v['RLOC_ORIGIN_native_value']=='{}' for v in support)
tcl=tkinter.Tcl();required=set('NAME REF_NAME IS_PRIMITIVE LOC BEL IS_LOC_FIXED IS_BEL_FIXED USER_SLR_ASSIGNMENT RLOC MACRO_NAME DONT_TOUCH'.split())
assert all(required<=set(tcl.splitlist(v['actual_native_property_names'])) and 'RLOC_ORIGIN' not in set(tcl.splitlist(v['actual_native_property_names'])) for v in schemas)
assert (P/'candidate_policy_before.tcllist').read_bytes()==(P/'candidate_policy_after.tcllist').read_bytes()
assert (P/'candidate_policy_schemas_before.tsv').read_bytes()==(P/'candidate_policy_schemas_after.tsv').read_bytes()
marker=dict(x.split('=',1) for x in (P/'candidate_policy_preservation.txt').read_text().splitlines())
assert marker==old['actual_native_preservation_marker']
keys=['policy_object_count','after_fresh_native_schema_objects','after_schema_count','every_object_schema_equal_before_after','all11required_supported','all_RLOC_ORIGIN_explicit_unsupported_native0_empty','policy_dicts_semantically_equal','policy_files_byte_identical','original_Pblock_count','after_Pblock_count','only_new_Pblock','new_Pblock_members','new_Pblock_members_exact_equal_to_P','hard_nonexclusive_non_routing_contained','readback_range']
value=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),execution='COMPLETED_ACTUAL_AT004_POLICY_PRESERVATION_INCREMENTAL_REVIEW',verdict='ACCEPT_ALL9525_FRESH_AFTER_AND_SINGLE_NEW_HARD_PBLOCK',applicability='AT004 policy substep only; index/cut/timing/global pre-place and physical success pending',review='A007 accepted no new gate',prior_independent_full_review=identity(prior),eleven_actual_policy_artifacts_byte_equal_to_AT003=checks,actual_native_preservation_marker=marker,proven_equal_content_invariants={k:old[k] for k in keys},fresh_current_csv_recount=dict(objects=9525,schemas=17,all_actual_native_schema_source_fresh=True,all11required_supported=True,RLOC_ORIGIN_explicit_unsupported_native0_empty=True),Pblock_member_proof_basis='Current before/after Pblock snapshots and literal P byte-equal to prior fully parsed accepted exact9491/one-Pblock evidence',current_before_region_export_review=identity(O/'actual_before_pblock_export_incremental_review.json'),audit_program=identity(__file__),no_EDA_DCP_signal_or_lock_control=True)
p=O/'actual_policy_preservation_incremental_review.json'
with p.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
md='''# AT004策略保持增量审核

execution：完成；verdict：接受；applicability：仅实际policy子步骤；review：A007。

11份当前策略、支持状态、schema、Pblock、P成员与闭合证据均与已审AT003逐字节一致。独立重数9525个唯一对象、17种schema；本轮after均为fresh native list_property，其余11个必需字段supported，RLOC_ORIGIN保留显式unsupported/native0/空值。

策略前后文件及schema前后文件均字节相同。原Pblock为0，新增仅m002_exact_hotspot_SLR2，9491个唯一成员精确等于实际P，真实范围和hard/nonexclusive/non-routing-contained属性保持。verified1、excluded_macro_partners0、unknown_policy0。

本记录不认定端口索引、有向cut、时序或完整pre-place闭合，也不认定物理迁移成功；流程按原合同继续，无新门、无EDA/DCP内容访问或进程/锁控制。
'''
with (O/'actual_policy_preservation_incremental_review.md').open('x') as f:f.write(md)
print(json.dumps(dict(review=identity(p),human=identity(O/'actual_policy_preservation_incremental_review.md')),ensure_ascii=False))
