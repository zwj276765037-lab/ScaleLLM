"""Finite conditional continuation: actual cost qualification -> exact frozen full.

No user approval is inferred. Root's pre-existing12 scientific conditions are
checked against actual evidence; any false condition preserves evidence and
prevents full launch. The actual GPU worker remains owned by its supervisor.
"""
from pathlib import Path
import argparse,json,os,shutil,subprocess,sys,time,traceback
from run_numerical_fidelity import identity,timestamp,write_json
from run_formal_numerical_queue import launched_identity,process_identity

def read(path):return json.loads(Path(path).read_text())
def require(value,message):
    if not value:raise ValueError(message)
def verify(item):
    require(identity(item['path'])['sha256']==item['sha256'],'identity changed: '+item['path']);return Path(item['path'])
def write_new(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')

def freeze(root,run):
    here=Path(__file__).parent;q=run/'qualification/full_source_v2';p=read(q/'session_plan_candidate.json')
    p['stage_contract']=identity(root/'.research-agent/decision_inputs/M005_R006_softmax_tv_contract.json')
    p['baseline_aggregate']=identity(root/'project/E012_multistage_rounding_precision/experiment_results/runs/R005/analysis/final_precision_png/aggregate_v1/final_aggregate.json')
    p['source_identities']=[identity(x['path']) for x in p['source_identities']]
    declared={x['path'] for x in p['source_identities']}
    for path in [Path('/home/zwj/.codex/skills/research-agent/scripts/console.py'),Path(p['organize_script']['path']),Path(__file__)]:
        if str(path.resolve()) not in declared:p['source_identities'].append(identity(path))
    plan=q/'session_plan_final.json'
    for command in p['finalize_commands']:
        command['argv']=[str(plan) if value==str(q/'session_plan_candidate.json') else value for value in command['argv']]
        command['source_identities']=[identity(x['path']) for x in command['source_identities']]
        if command['argv'][2]==str(here/'render_softmax_tv_integrated_v2.py'):
            command['source_identities'].append(identity(root/'project/E012_multistage_rounding_precision/experiment_results/runs/R005/analysis/final_precision_png/render_final_v2.py'))
    write_new(plan,p)
    all_sources={x['path']:x for x in p['source_identities']}
    for command in p['finalize_commands']:
        for item in command['source_identities']:all_sources[item['path']]=item
    copies=[]
    for item in list(all_sources.values())+[p['stage_contract'],p['formal_batch_plan'],p['formal_storage_plan'],p['baseline_plan'],p['baseline_aggregate']]:
        source=verify(item);destination=q/'source'/source.relative_to(root) if source.is_relative_to(root) else q/'source/external'/str(source).lstrip('/')
        destination.parent.mkdir(parents=True,exist_ok=True)
        require(not destination.exists(),'source copy cannot be overwritten')
        shutil.copy2(source,destination);require(identity(destination)['sha256']==item['sha256'],'source copy mismatch');copies.append(dict(original=item,copy=identity(destination)))
    argv=[sys.executable,'-B',str(here/'run_softmax_tv_background_v2.py'),'--plan',str(plan),'--output-dir',p['session_directory']]
    write_new(q/'launch_command_final.json',dict(argv=argv,cwd=str(root),plan=identity(plan)))
    write_new(q/'source_ready.json',dict(plan=identity(plan),sources=list(all_sources.values()),copies=copies,stage_contract=p['stage_contract'],argv=argv,cwd=str(root),worker_sources=len(p['source_identities']),finalizers=len(p['finalize_commands'])))
    return p,plan,argv

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--wait-seconds',type=int,default=1100);a=parser.parse_args();require(1<=a.wait_seconds<=1100,'finite qualification wait<=1100s')
    root=a.root.resolve();run=root/'project/E012_multistage_rounding_precision/experiment_results/runs/R006';q=run/'qualification';begin=time.monotonic();started=timestamp();here=Path(__file__).parent
    try:
        cost_driver=None
        while cost_driver is None:
            require(time.monotonic()-begin<a.wait_seconds,'finite cost qualification wait elapsed')
            try:
                if (q/'two_group_cost_driver_receipt_v4.json').is_file():cost_driver=read(q/'two_group_cost_driver_receipt_v4.json')
            except (OSError,json.JSONDecodeError):pass
            if cost_driver is None:time.sleep(5)
        require(cost_driver['gpu_supervisor_native_exit_code']==cost_driver['postcheck_native_exit_code']==0,'actual finite cost qualification did not qualify full budget')
        acceptance=read(q/'pilot_acceptance.json');cost=read(q/'two_group_cost_acceptance_v4.json');require(acceptance['qualification_passed'] and acceptance['full_budget_qualified'] and cost['full_budget_qualified'],'actual numerical and conservative cost qualification')
        root_review=read(q/'root_full_conditional_review.json');require(len(root_review['conditions'])==12 and root_review['decision']=='conditional_launch_authorized_not_yet_satisfied','explicit Root conditional authorization')
        for item in root_review['reviewed_sources']:verify(item)
        review=read(run/'independent_review/prelaunch_review.json');require(review['execution_state']=='completed' and review['blocking_issues']==[],'independent four-source no-blocking review')
        for item in review['reviewed_sources']:verify(item)
        test_results=[]
        for name,count in [('unit',9),('session_unit',8)]:
            test=read(q/'cpu_v2'/(name+'_receipt.json'));require(test['native_exit_code']==0,'actual CPU '+name+' native0')
            log=(q/'cpu_v2'/(name+'_stderr.log')).read_text();require('Ran '+str(count)+' tests' in log and '\nOK\n' in log,'actual required CPU test count');test_results.append(test['native_exit_code']==0 and 'Ran '+str(count)+' tests' in log)
        p,plan,argv=freeze(root,run);baseline=read(verify(p['baseline_plan']))
        require(p['expected_doc_ids']==baseline['expected_doc_ids'] and len(set(p['expected_doc_ids']))==1024,'same full1024 ordered docs')
        require(len(p['groups'])==64 and all(len(g['doc_ids'])==16 for g in p['groups']),'same64x16 partition')
        require(sum(sum(g['actual_token_lengths']) for g in p['groups'])==103700 and sum(len(g['audit_doc_ids']) for g in p['groups'])==15,'actual token/audit totals')
        validation=[sys.executable,'-B',str(here/'bounded_softmax_tv_session_v2.py'),'--plan',str(plan),'--output-dir',p['session_directory'],'--validate-only']
        with (q/'full_source_v2/final_plan_validation_stdout.log').open('x') as stdout,(q/'full_source_v2/final_plan_validation_stderr.log').open('x') as stderr:
            native=subprocess.run(validation,stdout=stdout,stderr=stderr,env=dict(os.environ,CUDA_VISIBLE_DEVICES=''),timeout=180)
        write_new(q/'full_source_v2/final_plan_validation.json',dict(argv=validation,native_exit_code=native.returncode,plan=identity(plan),gpu_started=False,ended_at=timestamp()))
        require(native.returncode==0,'exact frozen full-plan validate-only failed')
        pilot=read(run/'attempts/AT001_softmax_tv_dev_qualification/gpu_receipt.json');independent=read(q/'pilot_independent_v2/pilot_independent_tv_and_baseline.json')
        source_ready=read(q/'full_source_v2/source_ready.json')
        source_copies_verified=all(verify(item['original']).is_file() and verify(item['copy']).is_file() and item['original']['sha256']==item['copy']['sha256'] for item in source_ready['copies'])
        roster_complete=len(p['groups'])==64 and len(p['expected_doc_ids'])==1024 and sum(sum(g['actual_token_lengths']) for g in p['groups'])==103700 and sum(len(g['audit_doc_ids']) for g in p['groups'])==15
        finalizer_complete=len(p['finalize_commands'])==66 and sum('audit_softmax_tv_numerical_v2.py' in command['argv'][2] for command in p['finalize_commands'])==64 and p['finalize_commands'][-2]['argv'][2]==str(here/'aggregate_softmax_tv_v2.py') and p['finalize_commands'][-1]['argv'][2]==str(here/'render_softmax_tv_integrated_v2.py')
        fresh_stage=not (run/'session_S001/root_launch.json').exists() and not (q/'formal_launch_gate.json').exists()
        conditions=[
            pilot['native_exit_code']==pilot['exit_code']==0 and pilot['worker_reaped'] and pilot['source_unchanged'] and pilot['stop_reason'] is None,
            acceptance['actual_documents']==4 and acceptance['actual_real_positions']==398 and acceptance['all_positions_measured'] and acceptance['max_probability_mass_defect']<=1e-10,
            acceptance['all_old_numeric_head_fields_and_final_hidden_sha_equal'] and acceptance['old_raw_all7arrays_dtype_shape_bytes_equal'],
            acceptance['independent_full_vocab_rows']==3 and acceptance['max_independent_tv_abs_difference']<=acceptance['independent_tv_comparison_atol'],
            acceptance['full_budget_qualified'] and cost['model']['conservative_full_estimate_seconds']<=14400 and cost['model']['estimated_evidence_bytes']<=6144*(1<<20),
            review['blocking_issues']==[],all(test_results),roster_complete,source_copies_verified,finalizer_complete,native.returncode==0,fresh_stage]
        require(len(conditions)==12 and all(conditions),'all12 actual conditions must be true')
        evidence=[identity(q/'pilot_acceptance.json'),identity(q/'two_group_cost_acceptance_v4.json'),identity(run/'independent_review/prelaunch_review.json'),identity(q/'full_source_v2/source_ready.json'),identity(q/'full_source_v2/final_plan_validation.json')]
        gate=dict(schema='m005_r006_actual_formal_launch_gate_v3',execution_state='conditions_satisfied',all_conditions_passed=True,full_gpu_started=False,conditions=[dict(number=i+1,condition=text,passed=passed,evidence=evidence) for i,(text,passed) in enumerate(zip(root_review['conditions'],conditions))],root_authorization=identity(q/'root_full_conditional_review.json'),exact_plan=identity(plan),decided_at=timestamp(),continuation_source=identity(__file__),cost_qualification_scope='Additional originalB001+B002 two16doc qualification was not counted as formal completion or reused by full stage')
        write_new(q/'formal_launch_gate.json',gate)
        directory=Path(p['session_directory']);directory.mkdir(parents=True,exist_ok=True)
        with (directory/'driver_stdout.log').open('x') as stdout,(directory/'driver_stderr.log').open('x') as stderr:
            child=subprocess.Popen(argv,cwd=str(root),stdout=stdout,stderr=stderr,start_new_session=True,env=os.environ.copy());proof=launched_identity(child,argv)
            write_new(directory/'root_launch.json',dict(started_at=timestamp(),driver_identity=proof,continuation_identity=process_identity(os.getpid()),argv=argv,cwd=str(root),plan=identity(plan),gate=identity(q/'formal_launch_gate.json'),scope='Actual one full1024 finite background pipeline; all qualification docs rerun in new shared GPU session'))
            report=dict(execution_state='running',current_task='R006完整1024篇Softmax后TV正式后台流水线',stage='Full finite stage actually launched after all12 actual gates; GPU launch details in session_launch_manifest',blocker=None,next_step='单worker64组后自动独审、全部TV/旧值对照、聚合、PNG及终态三摘要',runtime_id='/root/softmax_tv_runner',thread_id=None,actual_model='gpt-6.1-sol',actual_effort='xhigh',configuration_evidence='agent/A017/configuration_evidence.json')
            write_new(directory/'launch_agent_report.json',report)
            console=[sys.executable,'-B',p['console_script']['path'],'report','--root',str(root),'--agent','A017','--input',str(directory/'launch_agent_report.json')]
            with (directory/'launch_console_stdout.log').open('x') as stream,(directory/'launch_console_stderr.log').open('x') as error:subprocess.run(console,stdout=stream,stderr=error,timeout=15)
            for kind in ['source','results','status']:
                path=root/f'project/E012_multistage_rounding_precision/experiment_{kind}/summary.md';old=path.read_text();split=old.split('---\n\n以下为R005及更早',1);history=split[1] if len(split)==2 else old
                path.write_text('# E012 R006：完整1024篇TV有限后台流程已实际启动\n\nexecution_state: running\nverdict: inconclusive（完整TV和最终图尚待真实终态）\napplicability: 固定1024文档/103700位置/64组；资格样本不复用，全部正式重跑\n\n全部12项真实条件已满足：4dev数值资格、原B00116篇成本补证、两种独立CPU检查、严格旧head/hidden/raw一致性、源冻结及精确plan CPU核验。实际单次完整driver启动见root_launch，GPU原生进程/保护见session_launch_manifest；不估算实时完成数。完整14400s/6144MiB、单组900s/256MiB、CPU1/RSS8/GPU24及free30/8保护保持。\n\n[真实启动](../experiment_results/runs/R006/session_S001/root_launch.json) · [12项门禁](../experiment_results/runs/R006/qualification/formal_launch_gate.json) · [成本补证](../experiment_results/runs/R006/qualification/two_group_cost_acceptance_v4.json) · [冻结源与计划](../experiment_results/runs/R006/qualification/full_source_v2/source_ready.json)。\n\n64组结束后自动完成64核心+64扩展独审、全部1024旧head/hidden SHA和45raw TV重算、CSV/JSON及整合Python PNG。TV百分比是概率质量变化，不是相对L2%；原13列/覆盖/Top1保留。完成与方法判断分开，原生终态前不称完成。\n\n---\n\n以下为R005及更早'+history)
            native=child.wait()
        write_new(q/'continuation_receipt_v4.json',dict(started_at=started,ended_at=timestamp(),full_driver_native_exit_code=native,full_launch=identity(directory/'root_launch.json'),scope='Finite conditional continuation completed; see actual session and driver terminal receipts'))
        return native
    except BaseException as error:
        traceback.print_exc();write_new(q/'continuation_failure_v4.json',dict(started_at=started,ended_at=timestamp(),error=repr(error),full_gpu_started=(run/'session_S001/root_launch.json').exists(),source=identity(__file__),scope='No unmet gate is silently overridden; no automatic retry/budget increase'))
        launched=(run/'session_S001/root_launch.json').exists()
        state='running' if launched else 'failed'
        report=dict(execution_state=state,current_task='R006有限条件续行已结束；详见实际failure回执',stage='Full driver remains independently bounded' if launched else 'Formal launch prevented by unmet actual evidence or budget condition',blocker=repr(error),next_step='Read continuation_failure and actual cost/session receipts; no automatic retry or budget growth',runtime_id='/root/softmax_tv_runner',thread_id=None,actual_model='gpt-6.1-sol',actual_effort='xhigh',configuration_evidence='agent/A017/configuration_evidence.json')
        write_new(q/'continuation_terminal_v4_agent_report.json',report)
        for kind in ['source','results','status']:
            path=root/f'project/E012_multistage_rounding_precision/experiment_{kind}/summary.md';old=path.read_text();parts=old.split('---\n\n以下为R005及更早',1);history=parts[1] if len(parts)==2 else old
            path.write_text('# E012 R006：有限条件续行回执\n\nexecution_state: '+state+'\nverdict: inconclusive\n\n'+('完整driver已实际启动并保有独立有界监督；续行控制的后置记录遇到异常。' if launched else '正式1024未启动：实际证据/成本条件尚未全部满足。原生资格结果保留，不把不满足成本准入解释为数值方法无效。')+'\n\n实际原因：'+repr(error)+'。未重试、未扩大预算或删除样本。\n\n[续行失败原始回执](../experiment_results/runs/R006/qualification/continuation_failure_v4.json) · [实际成本资格](../experiment_results/runs/R006/qualification/two_group_cost_acceptance_v4.json)。\n\n---\n\n以下为R005及更早'+history)
        console=[sys.executable,'-B','/home/zwj/.codex/skills/research-agent/scripts/console.py','report','--root',str(root),'--agent','A017','--input',str(q/'continuation_terminal_v4_agent_report.json')]
        with (q/'continuation_terminal_v4_console_stdout.log').open('x') as output,(q/'continuation_terminal_v4_console_stderr.log').open('x') as failure:subprocess.run(console,stdout=output,stderr=failure,timeout=15)
        return 1

if __name__=='__main__':raise SystemExit(main())
