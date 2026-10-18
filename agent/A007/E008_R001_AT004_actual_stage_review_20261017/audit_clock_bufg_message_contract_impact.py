"""AT004 Phase4.1 message interpretation, text only and no DCP access."""
import sys
sys.dont_write_bytecode=True
def deny_dcp(event,args):
    if event=='open' and args and isinstance(args[0],(str,bytes)):
        path=args[0].decode() if isinstance(args[0],bytes) else args[0]
        if path.lower().endswith('.dcp'):raise RuntimeError('DCP content access forbidden')
sys.addaudithook(deny_dcp)
import json,hashlib,re
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT=Path(__file__).resolve().parent
REPORT=ROOT/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
C01='scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_swiglu/g_row_branch[1].u_branch_leaf'
def read(path):return json.loads(Path(path).read_text())
def identity(path):
    path=Path(path).resolve();assert path.suffix.lower()!='.dcp'
    a=path.stat();h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4194304),b''):h.update(block)
    b=path.stat();assert(a.st_size,a.st_mtime_ns)==(b.st_size,b.st_mtime_ns)
    return dict(path=str(path),bytes=b.st_size,sha256=h.hexdigest())
def save(path,value):
    with path.open('x') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
parent=read(REPORT/'recovery_parent.json');prior_path=Path(parent['child_log']['path'])
assert identity(prior_path)==parent['child_log']
live=REPORT/'vivado.log'
with live.open('rb') as stream:
    size=live.stat().st_size;prefix=stream.read(size)
assert len(prefix)==size
with live.open('rb') as stream:assert stream.read(size)==prefix
observed=datetime.now(timezone.utc).isoformat()

def extract(data):
    phase='';active_outer='';caps=[];skips=[];summaries=[];selected=[];commands=[];completed=[];other=[]
    for number,line in enumerate(data.decode().splitlines(),1):
        row=dict(line=number,text=line)
        if line.startswith('Command: place_design'):
            active_outer='place_design';commands.append(row)
        if line=='place_design completed successfully':
            completed.append(row);active_outer='after_place'
        if line.startswith('Command: phys_opt_design'):
            active_outer='phys_opt_design';commands.append(row)
        if line.startswith('Phase ') and 'Checksum:' not in line:phase=line
        if '[Place 30-1995]' in line:
            match=re.search(r'capped at (\d+) for clock net (\S+) due to (.+)$',line);assert match
            caps.append(dict(row,severity=line.split(':',1)[0],cap=int(match[1]),net=match[2],reason=match[3],phase=phase,active_outer_command=active_outer))
        if '[Place 46-33]' in line:
            match=re.search(r'Processed net (.+), BUFG insertion was skipped due to (.+)\.$',line);assert match
            skips.append(dict(row,severity=line.split(':',1)[0],net=match[1],reason=match[2],phase=phase,active_outer_command=active_outer))
        if '[Place 46-56]' in line:
            match=re.search(r'identified (\d+) candidate nets\. Inserted BUFG: (\d+), Replicated BUFG Driver: (\d+), Skipped due to Placement/Routing Conflicts: (\d+), Skipped due to Timing Degradation: (\d+), Skipped due to netlist editing failed: (\d+)\.',line);assert match
            fields=['candidate_nets','inserted','replicated_driver','conflict_skipped','timing_degradation_skipped','editing_failed_skipped']
            summaries.append(dict(row,**dict(zip(fields,map(int,match.groups()))),active_outer_command=active_outer))
        if '[Place 46-14]' in line:other.append(row)
        if any(tag in line for tag in ['[Place 30-1995]','[Place 46-33]','[Place 46-56]','[Place 46-14]']) or line.startswith('Command: place_design') or line.startswith('Command: phys_opt_design') or line=='place_design completed successfully' or line.startswith('Phase 4') or line.startswith('Starting Physical Synthesis Task') or line.startswith('Ending Physical Synthesis Task'):
            selected.append(row)
    return dict(caps=caps,skips=skips,BUFG_summary=summaries,top_level_commands=commands,place_completed=completed,last_phase=phase,active_outer_command=active_outer,other_congestion_messages=other,selected_lines=selected)

current=extract(prefix);prior=extract(prior_path.read_bytes())
assert current['active_outer_command']=='place_design' and not current['place_completed']
assert len(current['top_level_commands'])==1
assert all(row['active_outer_command']=='place_design' for row in current['caps']+current['skips'])
assert len(current['caps'])==4 and len(prior['caps'])==4
assert all(row['severity']=='WARNING' and row['reason']=='BITSLICE_CONTROL_PLL_RIU MAX_SKEW requirements' for row in current['caps']+prior['caps'])
new_phase4=[row for row in current['caps'] if row['phase'].startswith('Phase 4.1')]
old_phase4=[row for row in prior['caps'] if row['phase'].startswith('Phase 4.1')]
assert len(new_phase4)==2 and len(old_phase4)==4
assert {(row['net'],row['cap'],row['reason']) for row in new_phase4}=={(row['net'],row['cap'],row['reason']) for row in old_phase4}
assert all(row['cap']==3 for row in new_phase4)
assert len(current['skips'])==11 and len(prior['skips'])==22
assert all(row['severity']=='INFO' and row['reason']=='placement/routing conflicts' for row in current['skips']+prior['skips'])
assert len(current['BUFG_summary'])==len(prior['BUFG_summary'])==1
for value in [current,prior]:
    summary=value['BUFG_summary'][0]
    assert summary['candidate_nets']==summary['conflict_skipped']==len(value['skips'])
    assert summary['inserted']==summary['replicated_driver']==summary['timing_degradation_skipped']==summary['editing_failed_skipped']==0
new_names={row['net'] for row in current['skips']};old_names={row['net'] for row in prior['skips']}
assert len(new_names&old_names)==9
assert any(name.endswith('/u_shared_compute/parent_tail_r[0]') for name in new_names&old_names)
assert all(not name.startswith(C01+'/') and name!=C01 for name in new_names)
assert len(prior['place_completed'])==1

excerpt=OUT/'AT004_clock_bufg_observed_excerpt_20261017.json'
save(excerpt,dict(observed_utc=observed,current_log=str(live),current_observed_prefix_bytes=size,
    current_observed_prefix_sha256=hashlib.sha256(prefix).hexdigest(),
    scope='Selected exact lines at this observation only; no immutable whole-live-log claim and no continuing monitor.',
    current_lines=current['selected_lines'],prior_log=parent['child_log'],prior_lines=prior['selected_lines']))
prior_review=identity(OUT/'place_warning_contract_impact_review.json')
assert prior_review['sha256']=='4563192b58d2096f08a3f363403359317a0d986448148fbc134bb61568ac5070'
result=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),reviewer='A007',
    execution='completed_bounded_native_message_and_same_stage_prior_log_review',
    verdict='retain_as_actual_placer_decisions_under_existing_POST_route_acceptance_no_new_gate',
    applicability='AT004 currently inside place_design Phase4.1 post-placement optimization; not external physopt, place completion or POST qualification',
    review='complete_readonly_message_scope',evidence_excerpt=identity(excerpt),prior_warning_review=prior_review,
    actual_stage=dict(last_phase=current['last_phase'],active_outer_command=current['active_outer_command'],top_level_commands=current['top_level_commands'],place_success_observed=False),
    BUFCE_ROW_cap=dict(current_actual_messages=current['caps'],prior_same_stage_messages=old_phase4,
        same_two_phase4_nets_cap_and_reason=True,
        interpretation='The placer caps horizontal BUFCE_ROW programmable delay to honor the named BITSLICE_CONTROL_PLL_RIU MAX_SKEW requirement. This is a reported constraint-handling decision; it is not a measured skew violation or proof of skew closure.',
        numeric_units='No physical time unit is specified. Cap 3 must not be reported as 3 ns, clock frequency or timing slack.',
        early_stage_difference='Current Phase2.1.1.2 reported caps 6 and 5 on the same two nets; later Phase4.1 reports 3 and 3, matching old E005 Phase4.1. Do not treat evolving placer settings or repeated messages as independent failures.',
        scope='Both named DDR0 infrastructure nets are outside literal C01. No measured impact on DDR timing or final clock skew is established.'),
    BUFG_insertion=dict(current_message_count=len(current['skips']),current_actual_messages=current['skips'],current_pass_summary=current['BUFG_summary'][0],
        prior_message_count=len(prior['skips']),prior_pass_summary=prior['BUFG_summary'][0],
        same_exact_net_overlap=9,parent_tail_r0_present_in_both=True,current_targets_inside_literal_C01=0,
        severity='INFO, not WARNING or ERROR',
        interpretation='The internal BUFG-insertion optimization pass considered 11 nets and skipped all 11 due to placement/routing conflicts. It inserted no BUFG and replicated no BUFG driver in this pass. These counters are pass-local, not a count of all design BUFGs or all physical optimization changes.',
        failure_boundary='Skipped optimization does not itself prove a required user clock buffer is missing, a signal is unrouted, or design functionality is broken; it also supplies no timing benefit from this pass.',
        prior_comparison='The prior pass considered/skipped 22 nets, with 9 exact names common, including shared_compute/parent_tail_r[0]. Different candidate sets and evolving placement do not show reduced congestion, resource improvement, or C01 causation.',
        actual_optimization_execution='Physical Synthesis messages and internal Phase1 initialization are nested within place_design Phase4.1; no external phys_opt_design command or place completion exists in the observed current prefix.'),
    contract_effect=dict(
        source_constraints='No input edit, clock-frequency relaxation, MAX_SKEW relaxation or C01 Pblock softening is indicated by these messages. No settings are changed by this review.',
        acceptance='Keep existing fresh complete POST/locality and 80-boundary protection checks; assess complete clocks/DRC/setup/hold/PW and applicable skew evidence, actual per-SLR/connectivity/congestion, and finally legal route status under unchanged requirements.',
        unresolved='Actual DDR skew/timing, final BUFG topology, C01 resolved P landing, complete placement/POST and route remain unestablished by these messages.',
        action='Normal process continues. Retain the bounded messages and pass counters for later same-stage interpretation; no EDA query, new gate, forced stop or new agent.'),
    limits=['Prior E005 place success establishes these message classes were nonfatal then, not that current routing/timing will succeed.',
            'Counts describe the frozen observed prefix and this completed BUFG insertion pass only; later repeat messages require separate bounded observation.',
            'No raw log, production, consumed package or engineering summary changed; no DCP/EDA/process/lock operations.'],audit_program=identity(__file__))
output=OUT/'clock_bufg_message_contract_impact_review.json';save(output,result)
human=OUT/'clock_bufg_message_contract_impact_review.md'
with human.open('x') as stream:
    stream.write('# AT004 Phase 4.1 时钟与 BUFG 提示审核\n\n'
                 'execution：只读核查完成；verdict：纳入现有 POST/route 判断，无新增停点；applicability：仍在 place_design 内部，未完成 place/POST，未启动外层 physopt；review：A007。\n\n'
                 '`Place 30-1995` 为 WARNING。本轮 DDR0 的 c0_riu_clk / u_bufg_divClk_0 早期 Clock Region Placement 报 cap 6/5，Phase 4.1 改为 3/3；旧 E005 在 Phase 4.1 对相同两网也报 3/3。原文是为 BITSLICE_CONTROL_PLL_RIU MAX_SKEW 要求限制水平 BUFCE_ROW 可编程延迟，是工具处理约束的决定，既不是已测 skew 违规，也不是 skew 已通过。日志未给 cap 的时间单位，不能写成 3 ns、频率或 slack；也没有放松时钟/MAX_SKEW 的证据。\n\n'
                 '`Place 46-33` 实际为 INFO。本轮已闭合的 BUFG 插入子过程汇总为候选 11、插入 0、复制 driver 0、因布局/走线冲突跳过 11，其余跳过原因均 0。全部 11 个目标均不在字面 C01 内。旧轮为候选/跳过 22，精确网名交集 9（含 shared_compute/parent_tail_r[0]）。候选集合不同，不能用 11 比 22 判拥塞或优化改善；这也不是全设计 BUFG 数量。跳过这项优化不等于必须时钟缺失、信号未布通或功能失败，本子过程亦无已实现的插入收益。\n\n'
                 '当前日志已到内部 Phase 4.1.1.3 Post Placement Timing Optimization；其中 Physical Synthesis/Phase 1 字样属于 place_design 内部。现有观察没有 place 成功或外层 phys_opt_design 命令。旧轮后来 place 成功，只证明这些类别当时非致命，不保证本轮布线/时序。\n\n'
                 '继续既有 fresh POST/locality、80 个保护边界、全局 clocks/DRC/setup/hold/PW 及适用 skew 证据检查，最终按真实 route 状态验收；不改参数、约束、消费包或工程摘要，不加审批门。后续同类新增消息须另以有界观察记录，不把本次摘录称为持续监控。\n\n'
                 '[机器审核](clock_bufg_message_contract_impact_review.json) · [带原行号摘录](AT004_clock_bufg_observed_excerpt_20261017.json)\n')
print(json.dumps(dict(review=identity(output),human=identity(human),excerpt=identity(excerpt),stage=current['last_phase'],current_skipped=len(current['skips']),prior_skipped=len(prior['skips']),common_nets=9),ensure_ascii=False))
