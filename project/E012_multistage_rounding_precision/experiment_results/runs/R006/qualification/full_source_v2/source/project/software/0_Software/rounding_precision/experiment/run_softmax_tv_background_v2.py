"""Finite R006 background driver; one bounded supervisor and terminal reporting.

No polling of the GPU worker here: the bounded supervisor owns resource limits
and finalizers. Terminal bookkeeping runs only after its actual return.
"""
from pathlib import Path
import argparse,json,os,subprocess,sys,time
from run_numerical_fidelity import identity,timestamp,write_json

def terminal_report(plan_path,directory,native):
    plan=json.loads(Path(plan_path).read_text());root=Path(plan['project_root']);directory=Path(directory)
    receipt_path=directory/'session_receipt.json';receipt=json.loads(receipt_path.read_text()) if receipt_path.exists() else None
    completed=native==0 and receipt is not None and receipt.get('model_execution_state')=='completed' and receipt.get('analysis_state')=='completed'
    analysis=Path(plan['tv_aggregate_directory']);png=Path(plan['tv_png_directory'])/'final_precision.png'
    tv=json.loads((analysis/'tv_aggregate.json').read_text()) if completed else None
    if completed and (not png.is_file() or not tv['target_complete'] or tv['measured_documents']!=1024 or tv['real_positions']!=103700):raise ValueError('terminal reports cannot mark partial/missing output complete')
    run_directory=directory.parent
    total_evidence_bytes=sum(item.stat().st_size for item in run_directory.rglob('*') if item.is_file())
    if total_evidence_bytes>plan['limits']['total_evidence_mib']*(1<<20):raise ValueError('R006 whole-run evidence storage exceeds frozen cap')
    evidence=dict(total_evidence_bytes=total_evidence_bytes,driver_source=identity(__file__),plan=identity(plan_path),session_receipt=identity(receipt_path) if receipt_path.exists() else None,native_exit_code=native,completed=completed,ended_at=timestamp(),png=identity(png) if completed else None)
    write_json(directory/'background_driver_receipt.json',evidence)
    if completed:
        summary=tv['distributions']['fixed_quota_pool'];m=summary['document_mean_tv'];x=summary['document_max_tv']
        state='completed';stage='R006 full1024 TV, independent checks, CSV/JSON and integrated PNG complete'
        metrics=f"每篇平均TV（概率质量%）：中位{100*m['p50']:.9g}，P95 {100*m['p95']:.9g}，P99 {100*m['p99']:.9g}，最大{100*m['max']:.9g}。每篇最大TV的P95 {100*x['p95']:.9g}%，观测最大{100*x['max']:.9g}%。两路概率质量最大缺陷{tv['max_probability_mass_defect']:.9g}。"
        result='1024/1024篇、64/64组、103700真实位置×128256词表、温度1已实际测量。全部1024篇原head数值/数组及final-hidden SHA与R005精确相等；64核心+64扩展独审完成；15篇45行完整词表独立TV重算完成。'+metrics
        next_step='Root终态独立审核与最终PNG目视检查；不宣称普遍精度保持'
    else:
        state='failed';stage='R006 finite pipeline stopped with preserved actual receipt';result='有限pipeline未完整交付；具体执行/分析状态见原生session回执。保留全部已写结果，不将部分数据计成完整1024，不自动重试或改变预算。';next_step='Root据实际失败证据诊断与决定合同内后续修复'
    runprefix='project/E012_multistage_rounding_precision/experiment_results/runs/R006'
    links=f"[真实终态](../experiment_results/runs/R006/session_S001/session_receipt.json) · [后台驱动回执](../experiment_results/runs/R006/session_S001/background_driver_receipt.json)"
    if completed:links+=' · [TV汇总](../experiment_results/runs/R006/analysis/aggregate_v2/tv_aggregate.json) · [最终PNG](../experiment_results/runs/R006/analysis/png_v2/final_precision.png)'
    for kind in ['source','results','status']:
        path=root/f'project/E012_multistage_rounding_precision/experiment_{kind}/summary.md';old=path.read_text();parts=old.split('---\n\n以下为R005及更早',1);history=parts[1] if len(parts)==2 else old
        header=f'# E012 R006 Softmax后TV：实际终态\n\nexecution_state: {state}\nverdict: inconclusive（无预设保真阈值，不作普遍精度保持断言）\napplicability: 单模型、32层prefill、最多128真实token、固定配额1024文本、相同输入前缀\n\n'+result+'\n\n'+links+'\n\nTV百分比表示100×概率质量变化，与相对L2%不同。文档为统计单位；全位置统计另列为长度加权描述，固定配额合池仅描述；无ACC/PPL或自由生成结论。\n\n'+next_step+'。\n\n'
        path.write_text(header+'---\n\n以下为R005及更早'+history)
    agent=root/'agent/A017';(agent/'result.md').write_text('# A017 R006 delivery\n\n'+result+'\n\nEvidence: '+runprefix+'/session_S001/background_driver_receipt.json\n\n'+next_step+'。\n')
    report=dict(execution_state=state,current_task='M005/SM021+SM023/E012/R006标准输出Softmax TV补测',stage=stage,blocker=None if completed else 'See actual terminal receipts',next_step=next_step,runtime_id='/root/softmax_tv_runner',thread_id=None,actual_model='gpt-6.1-sol',actual_effort='xhigh',configuration_evidence='agent/A017/configuration_evidence.json')
    if completed:report['progress']=dict(completed=1024,total=1024,unit='documents measured and finalized')
    report_path=directory/'terminal_agent_report.json';write_json(report_path,report)
    command=[sys.executable,'-B',str(plan['console_script']['path']),'report','--root',str(root),'--agent','A017','--input',str(report_path)]
    with (directory/'terminal_console_stdout.log').open('x') as stdout,(directory/'terminal_console_stderr.log').open('x') as stderr:
        result=subprocess.run(command,stdout=stdout,stderr=stderr,timeout=15)
    write_json(directory/'terminal_console_receipt.json',dict(argv=command,native_exit_code=result.returncode,ended_at=timestamp()))
    return 0 if completed else 1

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
    a.output_dir.mkdir(parents=True,exist_ok=True);argv=[sys.executable,'-B',str(Path(__file__).with_name('bounded_softmax_tv_session_v2.py')),'--plan',str(a.plan.resolve()),'--output-dir',str(a.output_dir.resolve())]
    with (a.output_dir/'background_supervisor_stdout.log').open('x') as stdout,(a.output_dir/'background_supervisor_stderr.log').open('x') as stderr:
        result=subprocess.run(argv,stdout=stdout,stderr=stderr)
    return terminal_report(a.plan,a.output_dir,result.returncode)

if __name__=='__main__':raise SystemExit(main())
