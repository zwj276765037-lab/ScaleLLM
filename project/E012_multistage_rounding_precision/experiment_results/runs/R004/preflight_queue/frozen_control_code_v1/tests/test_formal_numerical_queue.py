import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import threading
import unittest
from unittest.mock import patch
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment'))
import run_formal_numerical_queue as queue
from formal_numerical_inputs import build_plan,load_batch_group
from formal_storage_plan import create_storage_policy


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value));return path


def successful_group(group):
    attempt=Path(group['attempt_path']);rows=[]
    for index,doc in enumerate(group['documents']):
        row=dict(doc_id=doc['doc_id'],tokens=doc['tokens'],coverage=dict(complete=True,
            hidden_unique_layers=32,local_unique_coordinates=384,dynamic_unique_coordinates_per_arm=192,
            per_layer_dynamic_activation_calls=4,per_layer_dynamic_kv_calls=2))
        rows.append(row);put(attempt/'documents'/f'doc{index:04d}'/'document_result.json',row)
    put(attempt/'gpu_receipt.json',dict(execution_state='completed',exit_code=0,worker_reaped=True,source_unchanged=True))
    put(attempt/'paired_result.json',dict(execution_state='completed',formal_batch_ids=group['batch_ids'],documents=rows,
                                        formal_eval_documents=len(rows),source_unchanged=True))


class QueueTests(unittest.TestCase):
    def fixture(self,root):
        counts={'web':4,'news':2,'reviews':2};docs=[]
        for index,domain in enumerate(['web']*4+['news']*2+['reviews']*2):
            artifact=root/f'token{index}.npz'
            np.savez(artifact,input_ids=np.array([1,index+2],np.int64),attention_mask=np.ones(2,np.int64),position_ids=np.arange(2,dtype=np.int64))
            docs.append(dict(doc_id=f'd{index}',duplicate_cluster=f'c{index}',domain=domain,split='eval',evidence_role='formal_eval',
                             tokens=2,token_artifact=queue.identity(artifact),raw_tensor_audit_selected=index in [0,4,6]))
        stream=put(root/'stream.json',dict(schema='m005_numerical_document_stream_v1',documents=docs,tokenizer_files=[],audit_selection={}))
        formal=put(root/'formal_batch_plan.json',build_plan(stream,2,expected_counts=counts))
        storage=put(root/'formal_storage_plan.json',create_storage_policy(formal))
        sources=[]
        for index in range(22):
            path=root/f'source{index}.py';path.write_text('# frozen\n');sources.append(queue.identity(path))
        supervisor=root/'bounded.py';supervisor.write_text('# never executed in tests\n')
        organizer=root/'organize.py';organizer.write_text('# never executed in tests\n')
        before=root/queue.ATTEMPTS/'AT002_precompleted';before.mkdir(parents=True)
        prior=load_batch_group(formal,'B001',expected_counts=counts,storage_plan=storage)
        successful_group({**prior,'attempt_path':str(before)})
        ready=put(root/'source_ready.json',dict(code_identities=sources,input_identities=[queue.identity(formal),queue.identity(storage)],
            worker_command=[sys.executable,'-B',str(root/'fake_worker.py'),'--worker','--batch-ids','B001','--output-dir',str(before)]))
        batches=json.loads(formal.read_text())['batches'];groups=[]
        for index,batch in enumerate(batches[1:],3):
            selected=load_batch_group(formal,[batch['batch_id']],expected_counts=counts,storage_plan=storage)
            contract=put(root/f'contract{index}.json',dict(kind='m005_bounded_gpu_stage',gpu_uuid=queue.GPU_UUID,max_wall_seconds=1,
                cpu_threads=1,max_rss_gib=8,max_gpu_gib=24,evidence_mib=256,
                input=dict(logical_batch_ids=[batch['batch_id']],doc_ids=[doc['doc_id'] for doc in selected['documents']]),
                audit=dict(doc_ids=selected['audit_doc_ids'])))
            groups.append(dict(group_id=f'G{index:03d}',batch_ids=[batch['batch_id']],attempt_id=f'AT{index:03d}',title='fixed',
                               attempt_path=str(root/queue.ATTEMPTS/f'AT{index:03d}_fixed'),wall_seconds=1,stage_contract=queue.identity(contract)))
        path=put(root/'queue_plan.json',dict(schema='m005_formal_numerical_queue_v1',project_root=str(root),experiment='E012',run='R004',
            register_attempts=False,total_wall_seconds=300,group_count=len(groups),groups=groups,source_ready=queue.identity(ready),
            queue_source=queue.identity(queue.__file__),bounded_supervisor=queue.identity(supervisor),organize_script=queue.identity(organizer),
            precompleted=[dict(batch_ids=['B001'],attempt_path=str(before),gpu_receipt=queue.identity(before/'gpu_receipt.json'),paired_result=queue.identity(before/'paired_result.json'))]))
        validated=queue.validate_plan(path,project_root=root,expected_counts=counts)
        output=root/'project/E012_multistage_rounding_precision/experiment_results/runs/R004/queues/Q001'
        return path,validated,output

    def fake_success(self,argv,group,logdir,deadline,emit):
        successful_group(group);return dict(exit_code=0,stop_reason=None)

    def test_partition_precompleted_and_all_document_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,validated,output=self.fixture(Path(tmp))
            receipt=queue.execute(validated,output,supervise=self.fake_success)
            self.assertEqual(receipt['execution_state'],'completed')
            self.assertEqual(len(receipt['completed_document_ids']),8)
            self.assertTrue(receipt['full_target_execution_coverage_verified'])
            self.assertEqual(receipt['numerical_verdict'],'not_evaluated')
            self.assertFalse(receipt['not_completed_document_ids'])

    def test_failed_preflight_and_cost_stop_do_not_advance(self):
        for preflight in [True,False]:
            with self.subTest(preflight=preflight),tempfile.TemporaryDirectory() as tmp:
                path,validated,output=self.fixture(Path(tmp));calls=[]
                def fail(argv,group,*args):
                    calls.append(group['group_id']);put(Path(group['attempt_path'])/'gpu_receipt.json',dict(execution_state='cost_stop',worker_launched=not preflight))
                    return dict(exit_code=75 if preflight else 124,stop_reason='resource admission' if preflight else 'wall budget')
                receipt=queue.execute(validated,output,supervise=fail)
                self.assertEqual(len(calls),1);self.assertEqual(receipt['execution_state'],'stopped')
                self.assertEqual(receipt['groups'][0]['execution_state'],'cost_stop')
                self.assertEqual(len(receipt['not_completed_document_ids']),6)

    def test_source_mutation_and_child_failure_stop_queue(self):
        for mutation in [True,False]:
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                path,validated,output=self.fixture(Path(tmp));calls=[]
                def fail(argv,group,*args):
                    calls.append(1)
                    if mutation:
                        successful_group(group);Path(validated['frozen'][4]['path']).write_text('# changed\n')
                    return dict(exit_code=0 if mutation else 1,stop_reason=None)
                receipt=queue.execute(validated,output,supervise=fail)
                self.assertEqual(len(calls),1);self.assertEqual(receipt['execution_state'],'stopped')
                self.assertFalse(receipt['full_target_execution_coverage_verified'])

    def test_exit_zero_with_missing_document_or_coverage_is_not_complete(self):
        for missing in [True,False]:
            with self.subTest(missing=missing),tempfile.TemporaryDirectory() as tmp:
                path,validated,output=self.fixture(Path(tmp))
                def incomplete(argv,group,*args):
                    successful_group(group);doc=Path(group['attempt_path'])/'documents/doc0000/document_result.json'
                    if missing:doc.unlink()
                    else:
                        row=json.loads(doc.read_text());row['coverage']['hidden_unique_layers']=31;put(doc,row)
                    return dict(exit_code=0,stop_reason=None)
                receipt=queue.execute(validated,output,supervise=incomplete)
                self.assertEqual(receipt['execution_state'],'stopped');self.assertFalse(receipt['full_target_execution_coverage_verified'])

    def test_registration_failure_and_total_deadline_never_launch_next_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,validated,output=self.fixture(Path(tmp));calls=[]
            with patch.object(queue,'register',side_effect=RuntimeError('registration failed')):
                receipt=queue.execute(validated,output,supervise=lambda *args:calls.append(1))
            self.assertEqual(calls,[]);self.assertIn('registration failed',receipt['stop_reason'])
        with tempfile.TemporaryDirectory() as tmp:
            path,validated,output=self.fixture(Path(tmp));validated['plan']['total_wall_seconds']=31;calls=[]
            receipt=queue.execute(validated,output,supervise=lambda *args:calls.append(1),clock=lambda:0)
            self.assertEqual(calls,[]);self.assertIn('insufficient total queue time',receipt['stop_reason'])

    def test_overlap_or_missing_precompleted_identity_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,validated,output=self.fixture(Path(tmp));plan=json.loads(path.read_text())
            plan['precompleted'][0]['gpu_receipt']['sha256']='0'*64;put(path,plan)
            with self.assertRaises(ValueError):queue.validate_plan(path,Path(tmp),expected_counts={'web':4,'news':2,'reviews':2})
        with tempfile.TemporaryDirectory() as tmp:
            path,validated,output=self.fixture(Path(tmp));plan=json.loads(path.read_text())
            plan['groups'].append(plan['groups'][0]);plan['group_count']+=1;put(path,plan)
            with self.assertRaises(ValueError):queue.validate_plan(path,Path(tmp),expected_counts={'web':4,'news':2,'reviews':2})

    def test_finalize_failure_preserves_completed_model_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,validated,output=self.fixture(Path(tmp));validated['plan']['finalize_commands']=[{}]
            with patch.object(queue,'finalize',side_effect=RuntimeError('analysis failure')):
                receipt=queue.execute(validated,output,supervise=self.fake_success)
            self.assertEqual(receipt['execution_state'],'analysis_failed');self.assertTrue(receipt['model_execution_completed'])
            self.assertEqual(receipt['numerical_verdict'],'not_evaluated')

    def test_partial_progress_line_is_reread_without_losing_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'events.jsonl';line=json.dumps(dict(stage='document_completed',doc_id='fixed'))+'\n'
            path.write_text(line[:10]);self.assertEqual(queue.read_progress(path,0),([],0))
            with path.open('a') as stream:stream.write(line[10:])
            rows,cursor=queue.read_progress(path,0)
            self.assertEqual(rows,[dict(stage='document_completed',doc_id='fixed')])
            self.assertEqual(queue.read_progress(path,cursor),([],cursor))

    def test_keyboard_interrupt_stops_and_writes_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,validated,output=self.fixture(Path(tmp))
            with patch.object(queue,'run_supervisor'):
                def interrupted(*args):raise KeyboardInterrupt('requested')
                receipt=queue.execute(validated,output,supervise=interrupted)
            self.assertEqual(receipt['execution_state'],'stopped');self.assertTrue((output/'queue_receipt.json').exists())


class OwnershipTests(unittest.TestCase):
    def test_finalize_exec_identity_race_and_bounded_timeout_or_stop(self):
        for stop in [False,True]:
            with self.subTest(stop=stop),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);source=root/'analysis.py';source.write_text('import time\ntime.sleep(30)\n')
                command=dict(argv=[sys.executable,str(source)],wall_seconds=1,source_identities=[queue.identity(source)])
                original=queue.process_identity;calls=[]
                def transient(pid):
                    result=original(pid);calls.append(1)
                    return {**result,'argv':['']} if result and len(calls)<=2 else result
                timer=threading.Timer(.05,lambda:setattr(queue,'STOP_REQUESTED','requested stop')) if stop else None
                try:
                    if timer:timer.start()
                    with patch.object(queue,'process_identity',side_effect=transient),self.assertRaises(RuntimeError):
                        queue.finalize(command,root/'finalize',time.monotonic()+100)
                    receipt=json.loads((root/'finalize/receipt.json').read_text())
                    self.assertTrue(receipt['worker_reaped']);self.assertIsNone(original(receipt['worker_pid']))
                    self.assertIn('stop' if stop else 'wall',receipt['stop_reason'])
                finally:
                    if timer:timer.join()
                    queue.STOP_REQUESTED=None
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'analysis.py';source.write_text('import time\ntime.sleep(30)\n')
            command=dict(argv=[sys.executable,str(source)],wall_seconds=1,source_identities=[queue.identity(source)])
            with patch.object(queue,'launched_identity',side_effect=RuntimeError('identity unavailable')),self.assertRaises(RuntimeError):
                queue.finalize(command,root/'finalize',time.monotonic()+100)
            receipt=json.loads((root/'finalize/receipt.json').read_text())
            self.assertTrue(receipt['worker_reaped']);self.assertIsNone(queue.process_identity(receipt['worker_pid']))

    def test_cpu_dummy_cleanup_leaves_unrelated_process_alive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);child_argv=[sys.executable,'-c','import time; time.sleep(30)']
            script=root/'supervisor.py'
            script.write_text('import json,subprocess,sys\nfrom pathlib import Path\np=subprocess.Popen(json.loads(sys.argv[2]),start_new_session=True)\nPath(sys.argv[1]).write_text(json.dumps({"pid":p.pid}))\np.wait()\n')
            argv=[sys.executable,str(script),str(root/'gpu_worker.json'),json.dumps(child_argv)]
            parent=subprocess.Popen(argv,start_new_session=True);other=subprocess.Popen(child_argv,start_new_session=True)
            try:
                end=time.monotonic()+3
                while not (root/'gpu_worker.json').exists() and time.monotonic()<end:time.sleep(.01)
                proof=queue.process_identity(parent.pid)
                worker=queue.discover_worker(proof,child_argv,root);self.assertIsNotNone(worker)
                (root/'gpu_worker.json').write_text('{"pid":')
                self.assertEqual(queue.discover_worker(proof,child_argv,root)['pid'],worker['pid'])
                group=dict(worker_command=child_argv,attempt_path=str(root))
                queue.stop_owned(parent,proof,worker,group)
                self.assertIsNotNone(parent.poll());self.assertFalse(queue.same_process(worker));self.assertIsNone(other.poll())
                self.assertFalse(queue.same_process({**proof,'starttime':proof['starttime']+1}))
            finally:
                for process in [parent,other]:
                    if process.poll() is None:os.killpg(process.pid,signal.SIGTERM)
                    process.wait()

    def test_sigterm_and_sigint_stop_real_cpu_fake_queue_without_survivors(self):
        for signum in [signal.SIGTERM,signal.SIGINT]:
            with self.subTest(signum=signum),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);path,validated,output=QueueTests().fixture(root)
                worker=root/'fake_worker.py';worker.write_text('import time\ntime.sleep(30)\n')
                bounded=root/'bounded.py'
                bounded.write_text('import json,subprocess,sys\nfrom pathlib import Path\na=sys.argv[1:];out=Path(a[a.index("--output-dir")+1]);out.mkdir(parents=True,exist_ok=True)\np=subprocess.Popen(a[a.index("--")+1:],start_new_session=True)\n(out/"gpu_worker.json").write_text(json.dumps({"pid":p.pid}))\np.wait()\n(out/"gpu_receipt.json").write_text(json.dumps({"execution_state":"failed","exit_code":p.returncode,"worker_reaped":True}))\n')
                plan=json.loads(path.read_text());plan['bounded_supervisor']=queue.identity(bounded);put(path,plan)
                shim=root/'cpu_queue.py'
                shim.write_text('import signal,sys\nfrom pathlib import Path\nsys.path.insert(0,'+repr(str(Path(queue.__file__).parent))+')\nimport run_formal_numerical_queue as q\nsignal.signal(signal.SIGTERM,q.request_stop);signal.signal(signal.SIGINT,q.request_stop)\nv=q.validate_plan(Path(sys.argv[1]),project_root=Path(sys.argv[2]),expected_counts={"web":4,"news":2,"reviews":2})\nq.execute(v,Path(sys.argv[3]))\n')
                with (root/'outer.log').open('w') as log:
                    outer=subprocess.Popen([sys.executable,'-B',str(shim),str(path),str(root),str(output)],stdout=log,stderr=log,start_new_session=True)
                    try:
                        proof_file=output/'G003/owned_worker.json';end=time.monotonic()+4
                        while not proof_file.exists() and outer.poll() is None and time.monotonic()<end:time.sleep(.01)
                        self.assertTrue(proof_file.exists(),(root/'outer.log').read_text()+
                            ((output/'G003/supervisor_stderr.log').read_text() if (output/'G003/supervisor_stderr.log').exists() else ''))
                        worker_proof=json.loads(proof_file.read_text());supervisor_proof=json.loads((output/'G003/owned_supervisor.json').read_text())
                        os.kill(outer.pid,signum);outer.wait(timeout=6)
                        self.assertFalse(queue.same_process(worker_proof));self.assertFalse(queue.same_process(supervisor_proof))
                        receipt=json.loads((output/'queue_receipt.json').read_text())
                        self.assertEqual(receipt['execution_state'],'stopped');self.assertEqual(receipt['finished_groups'],1)
                    finally:
                        if outer.poll() is None:os.killpg(outer.pid,signal.SIGTERM)
                        outer.wait(timeout=5)


if __name__=='__main__':unittest.main()
