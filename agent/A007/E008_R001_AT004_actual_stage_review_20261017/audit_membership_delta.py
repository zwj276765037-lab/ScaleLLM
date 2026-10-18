from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,re
R=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
O=Path(__file__).resolve().parent
P=R/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
def identity(p):
 p=Path(p).resolve();assert p.suffix.lower()!='.dcp';b=p.stat();h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(4194304),b''):h.update(x)
 a=p.stat();assert (b.st_size,b.st_mtime_ns)==(a.st_size,a.st_mtime_ns)
 return dict(path=str(p),bytes=a.st_size,sha256=h.hexdigest())
def read(p):return json.loads(Path(p).read_text())
prior_path=R/'agent/A007/E008_R001_AT003_actual_stage_review_20261017/pre_place_membership_incremental_review.json'
assert identity(prior_path)['sha256']=='dd7722475983fa6484729db2b89a9ccf472d19ce8f98e0b7b86ef0406a1df1e5'
prior=read(prior_path);checks=[]
for row in prior['ten_actual_ledgers_and_closure_byte_equal_to_reviewed_AT002']:
 expected=row['actual'];assert identity(expected['path'])==expected
 actual=identity(P/row['name']);assert (actual['bytes'],actual['sha256'])==(expected['bytes'],expected['sha256'])
 checks.append(dict(name=row['name'],actual=actual,accepted_prior=expected,byte_equal=True))
assert len(checks)==10
summary_path=P/'candidate_membership_pre_place.json';actual=read(summary_path);old=prior['actual_summary']
rebound=['P_parent_policy','native_exact_hierarchy_resources','actual_membership']
for key in rebound:assert identity(actual[key]['path'])==actual[key]
assert {k:v for k,v in actual.items() if k not in rebound}=={k:v for k,v in old.items() if k not in rebound}
for key in ['P_parent_policy','actual_membership']:
 assert actual[key]['bytes']==old[key]['bytes'] and actual[key]['sha256']==old[key]['sha256']
old_report=Path(old['native_exact_hierarchy_resources']['path']).read_text();new_report=Path(actual['native_exact_hierarchy_resources']['path']).read_text()
def normalize(s,report_dir):
 return '\n'.join(x.replace(str(report_dir),'<ACTUAL_REPORT_DIR>') for x in s.splitlines() if not x.startswith('| Date') and not re.fullmatch('-+',x))
assert normalize(old_report,Path(old['native_exact_hierarchy_resources']['path']).parent)==normalize(new_report,P)
assert '| Design State : Optimized' in new_report
marker=dict(x.split('=',1) for x in (P/'candidate_membership_pre_place_closed.txt').read_text().splitlines())
assert marker==prior['actual_closed_marker']
result=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),execution='COMPLETED_ACTUAL_AT004_MEMBERSHIP_INCREMENTAL_REVIEW',verdict='ACCEPT_SAME_EXACT_C01_MEMBERSHIP_AND_PHYSICAL_PARENT_MAPPING',applicability='AT004 actual pre_place members only; resource_admissibility/policy/Pblock/fullpreplace not established by this review',review='A007 accepted no new gate',prior_accepted_review=identity(prior_path),original_full_recomputation=prior['original_full_recomputation'],ten_actual_ledgers_and_closure_byte_equal_to_reviewed_AT003=checks,actual_membership_summary=identity(summary_path),actual_summary=actual,all_summary_fields_equal_after_actual_artifact_rebinding=True,actual_closed_marker=marker,proven_equal_content_invariants=prior['proven_equal_content_invariants'],native_report=actual['native_exact_hierarchy_resources'],native_report_normalized_equal=True,native_report_normalization_scope='Only Date header, actual report directory in Command, and full-hyphen header separators removed; all remaining content compared literally',native_report_scope=prior['native_report_scope'],start_review=identity(O/'start_delta_review.json'),audit_program=identity(__file__),no_EDA_DCP_signal_or_lock_control=True)
p=O/'pre_place_membership_incremental_review.json'
with p.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
md='''# AT004 pre-place成员增量审核

execution：完成；verdict：接受精确C01成员及物理父映射；applicability：仅当前成员子阶段；review：A007完成。

10份实际账本和闭合标记与已审AT003逐字节一致：RAW9514/S9507/P9491，字面branch[1]不变。4 GND与3 VCC排除，16个DSP内部对象归一到2个实际DSP48E2父；P父完整覆盖，所有P仍未布局。

摘要除三项本轮artifact重新绑定外逐字段相同。当前原生SLR报告仅日期、输出目录和页眉横线变化，其他内容一致；Optimized未布局图中的SLL0不代表迁移代价改善，P primitive对象数不是packed资源利用率。

资源资格、策略保持、Pblock及完整pre-place尚不由本审核成立。正常流程继续，无新审批门；未运行EDA、读取/hash DCP或控制进程/锁。
'''
with (O/'pre_place_membership_incremental_review.md').open('x') as f:f.write(md)
print(json.dumps(dict(review=identity(p),human=identity(O/'pre_place_membership_incremental_review.md')),ensure_ascii=False))
