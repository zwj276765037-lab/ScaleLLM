"""Two original16doc qualification segments, one actual cached model assembly."""
from pathlib import Path
import argparse,json,os,time
from run_numerical_fidelity import identity,write_json,timestamp

def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);a=p.parse_args();plan=json.loads(a.plan.read_text());session=Path(plan['session_directory'])
    import capture_real_inputs as loader
    from numerical_reference import model_compat as compat
    import softmax_tv_extension_v2 as head
    import run_softmax_tv_numerical_v2 as entry
    from extended_session_cache import ExtendedSessionCache
    from run_formal_numerical_queue import process_identity
    deadline=time.monotonic()+5
    while not (session/'gpu_worker.json').exists():
        if time.monotonic()>deadline:raise RuntimeError('actual shared qualification identity unavailable')
        time.sleep(.01)
    proof=json.loads((session/'gpu_worker.json').read_text())['shared_worker_identity']
    if proof!=process_identity(os.getpid()):raise ValueError('actual qualification worker identity mismatch')
    cache=ExtendedSessionCache(session,plan['model_dir']);results=[]
    with cache.context(loader,compat,head):
        for index,group in enumerate(plan['groups']):
            directory=Path(group['attempt_path']);argv=['--worker','--model-dir',plan['model_dir'],'--formal-batch-plan',plan['formal_batch_plan']['path'],'--formal-storage-plan',plan['formal_storage_plan']['path'],'--batch-ids',','.join(group['logical_batch_ids']),'--tokens','128','--raw-value-audit-layers','0,15,31','--witness-max-doc-mib','64','--witness-max-at-mib','96','--mlp-module','mlp_numerical_extension','--logit-module','softmax_tv_extension_v2','--output-dir',str(directory)]
            started=timestamp();begin=time.monotonic();native=entry.worker(entry.parser().parse_args(argv))
            if native:raise ValueError('actual qualification segment failed')
            value=dict(schema='m005_r006_qualification_segment_v4',runtime_kind='segment_of_one_shared_qualification_worker',shared_worker_identity=proof,session_path=str(session),attempt_path=str(directory),group_index=index,logical_batch_ids=group['logical_batch_ids'],doc_ids=group['doc_ids'],started_at=started,ended_at=timestamp(),wall_seconds=time.monotonic()-begin,native_exit_code=native,scope='Cost qualification segment only; not formal1024 completion')
            write_json(directory/'qualification_segment_receipt.json',value);results.append(value)
    write_json(session/'qualification_worker_result.json',dict(execution_state='completed',shared_worker_identity=proof,groups=results,actual_loads=cache.loads,assembly_loaded_once=cache.loads==dict(base=1,attach=1,head=1),scope='Actual originalB001+B00232doc qualification only; all data retained, no formal full count'))
    if cache.loads!=dict(base=1,attach=1,head=1):raise ValueError('model not assembled exactly once')
    return 0

if __name__=='__main__':raise SystemExit(main())
