"""Freeze bounded actual placement congestion and provisional timing evidence."""
import sys
sys.dont_write_bytecode=True
def guard(event,args):
    if event=='open' and args and isinstance(args[0],(str,bytes)):
        name=args[0].decode() if isinstance(args[0],bytes) else args[0]
        if name.lower().endswith('.dcp'):raise RuntimeError('DCP content access forbidden')
sys.addaudithook(guard)
import json,hashlib,re
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT=Path(__file__).resolve().parent
REPORT=ROOT/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
def identity(path):
    path=Path(path).resolve();assert path.suffix.lower()!='.dcp'
    a=path.stat();h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4194304),b''):h.update(block)
    b=path.stat();assert(a.st_size,a.st_mtime_ns)==(b.st_size,b.st_mtime_ns)
    return dict(path=str(path),bytes=b.st_size,sha256=h.hexdigest())
def read(path):return json.loads(Path(path).read_text())
def save(path,value):
    with path.open('x') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

parent=read(REPORT/'recovery_parent.json')
old_path=Path(parent['child_log']['path']);assert identity(old_path)==parent['child_log']
live=REPORT/'vivado.log'
with live.open('rb') as stream:size=live.stat().st_size;prefix=stream.read(size)
assert len(prefix)==size
with live.open('rb') as stream:assert stream.read(size)==prefix
observed=datetime.now(timezone.utc).isoformat()
def extract(data):
    lines=data.decode().splitlines();keep=set();congestion=[];timing=[];caps=[];stages=[];outer=[];complete=[]
    phase='';command=''
    for index,line in enumerate(lines):
        row=dict(line=index+1,text=line)
        if line.startswith('Command: place_design'):command='place_design';outer.append(row)
        if line=='place_design completed successfully':complete.append(row);command='after_place'
        if line.startswith('Command: phys_opt_design'):command='phys_opt_design';outer.append(row)
        if line.startswith('Phase 4'):stages.append(row)
        if line.startswith('Phase ') and 'Checksum:' not in line:phase=line
        if '[Place 46-14]' in line:congestion.append(dict(row,phase=phase,outer_command=command))
        if '[Place 30-746]' in line or '[Place 46-19]' in line:
            match=re.search(r'WNS=([-+0-9.]+)\.',line);assert match
            timing.append(dict(row,WNS=float(match[1]),phase=phase,outer_command=command))
        if '[Place 30-1995]' in line:caps.append(row)
        if any(tag in line for tag in ['[Place 46-14]','[Place 30-746]','[Place 46-19]']):
            keep.update(range(max(0,index-3),min(len(lines),index+5)))
        if line.startswith('Phase 4') or line=='place_design completed successfully' or line.startswith('Command: phys_opt_design'):
            keep.add(index)
    return dict(congestion=congestion,timing=timing,cap_messages=caps,stages=stages,outer_commands=outer,place_completion=complete,current_outer=command,excerpt=[dict(line=i+1,text=lines[i]) for i in sorted(keep)])
current=extract(prefix);old=extract(old_path.read_bytes())
assert len(current['congestion'])==len(old['congestion'])==1
assert current['congestion'][0]['text']==old['congestion'][0]['text']
assert current['congestion'][0]['outer_command']==old['congestion'][0]['outer_command']=='place_design'
assert len(current['timing'])==len(old['timing'])==2
assert all(row['WNS']==0.147 for row in current['timing']) and all(row['WNS']==0.103 for row in old['timing'])
assert all(row['outer_command']=='place_design' and 'For the most accurate timing information please run report_timing.' in row['text'] for row in current['timing']+old['timing'])
assert current['current_outer']=='place_design' and not current['place_completion'] and len(current['outer_commands'])==1
assert any(row['text'].startswith('Phase 4.1 Post Commit Optimization | Checksum:') for row in current['stages'])
assert len(current['cap_messages'])==6

source=REPORT/'stage_sources/m002_diagnostic_common.tcl'
source_id=identity(source)
global_review=read(OUT/'restored_pre_place_global_incremental_review.json')
assert source_id in global_review['all_identity_checks']
source_lines=source.read_text().splitlines()
congestion_hook=[dict(line=i+1,text=line) for i,line in enumerate(source_lines) if 'report_design_analysis -congestion -min_congestion_level 3' in line]
timing_hook=[dict(line=i+1,text=line) for i,line in enumerate(source_lines) if 'report_timing_summary -delay_type min_max -report_unconstrained' in line]
assert len(congestion_hook)==len(timing_hook)==1
excerpt=OUT/'AT004_congestion_timing_observed_excerpt_20261017.json'
save(excerpt,dict(observed_utc=observed,current_log=str(live),current_observed_prefix_bytes=size,current_observed_prefix_sha256=hashlib.sha256(prefix).hexdigest(),
    scope='Bounded selected lines of the observed prefix, not an immutable whole-log identity or a continuing monitor.',
    current_lines=current['excerpt'],prior_log=parent['child_log'],prior_lines=old['excerpt']))
result=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),reviewer='A007',execution='completed_bounded_congestion_warning_and_provisional_WNS_review',
    verdict='global_congestion_risk_reported_by_placer_no_failure_or_candidate_effect_established',
    applicability='AT004 place_design Phase4.1 end observed; native place completion/full POST/locality still unestablished at this prefix',review='complete_no_new_execution_gate',
    evidence_excerpt=identity(excerpt),current_congestion=current['congestion'][0],prior_same_stage_congestion=old['congestion'][0],
    exact_warning_text_matches_prior=True,
    congestion_interpretation='The placer explicitly reports high global congestion and possible routing difficulty. This is material risk for subsequent routing; it is neither a route attempt result nor a place failure or quantified per-SLR/candidate pressure measurement.',
    comparison_limit='The same warning occurred in old E005 after Phase4.1. Repetition of the warning class neither proves equal severity nor a benefit/regression/causal impact of C01; completed comparable congestion/SLR/locality reports are required.',
    provisional_timing=dict(current=current['timing'],prior=old['timing'],
        scope='Internal post-placement and post-replication timing summaries; both explicitly recommend full report_timing for accuracy.',
        current_raw_WNS=0.147,prior_raw_WNS=0.103,
        limitations='No full setup path coverage, TNS, hold, pulse-width, IO/reset/CDC closure or final routed timing is established. Do not report convergence or interpret the raw numerical difference as validated C01 improvement.'),
    stage=dict(observed_phase4_markers=current['stages'],outer_command=current['current_outer'],place_completion_observed=False,external_physopt_invocation_observed=False),
    repeat_clock_messages=dict(total_in_observed_prefix=6,new_since_previous_review=2,last_two=current['cap_messages'][-2:],
        interpretation='The same two DDR0 cap3 messages recur after Phase4.1; no changed cap or newly established skew failure. Prior review remains applicable.'),
    original_hooks=dict(source=source_id,congestion=congestion_hook,timing_summary=timing_hook,
        scope='Existing normal m002_post after native place command; source inspection only, no report command was executed by reviewer.'),
    disposition='Continue existing authorized native run. Wait for actual native command closure and fresh POST/locality/80-boundary checks, complete same-stage congestion/timing evidence and route status. Do not add EDA, a stop, a new approval gate, or claim success/failure from these messages.',
    prior_warning_reviews=[identity(OUT/'place_warning_contract_impact_review.json'),identity(OUT/'clock_bufg_message_contract_impact_review.json')],
    no_EDA_DCP_process_control_production_edits=True,audit_program=identity(__file__))
output=OUT/'congestion_provisional_timing_review.json';save(output,result)
human=OUT/'congestion_provisional_timing_review.md'
with human.open('x') as stream:
    stream.write('# AT004 高拥塞提示与临时 WNS 审核\n\n'
                 'execution：有界只读审核完成；verdict：确认 placer 报告高拥塞风险，未建立失败或候选效果；applicability：place_design Phase 4.1 结束后的观察，完整 place/POST/locality 尚未闭合；review：A007，无新增停点。\n\n'
                 '本轮日志 85273 的 `Place 46-14` 明确提示 highly congested / may have difficulty routing，与旧 E005 同阶段 1005 行原文完全相同。该风险需保留供布线结果解释；它不是已发生的布线失败、place 失败，也不提供候选或 SLR1 的定量压力变化。旧轮也有该提示不代表本轮风险相等或已消除，更不能据此判 C01 有效/无效。\n\n'
                 '`Place 30-746` 和 `Place 46-19` 的内部 WNS 均为 +0.147，旧轮均为 +0.103；原文都要求完整 report_timing 获取更准确结果。仅保留临时原值，不把差值解释为候选改善，不宣称 setup/hold/PW、TNS、CDC/reset/IO 或 routed timing 收敛。\n\n'
                 '日志确认内部 Phase 4.1 结束，但仍无 place 成功及外层 phys_opt_design 命令。两条 DDR0 cap3 提示在该阶段后再次出现，本前缀共 6 条；数值未变，不据重复计数新增 skew 失败。已归档 m002_post 原有 congestion（min level 3）与完整 timing summary 入口保持，将在既有流程执行；本审核没有新跑任何报告。\n\n'
                 '正常流程继续，后续按真实阶段 facts 独立核完整 POST/locality、80 个保护边界、同阶段拥塞与时序、最终 route 状态。\n\n'
                 '[机器审核](congestion_provisional_timing_review.json) · [前后阶段及原行号摘录](AT004_congestion_timing_observed_excerpt_20261017.json)\n')
print(json.dumps(dict(review=identity(output),human=identity(human),excerpt=identity(excerpt),congestion_line=current['congestion'][0]['line'],provisional_WNS=0.147),ensure_ascii=False))
