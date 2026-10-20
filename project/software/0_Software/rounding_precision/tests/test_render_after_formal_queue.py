"""CPU dependency-control qualification; no model data, GPU, or real rendering."""
from datetime import timedelta
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment'))
import render_after_formal_queue as driver


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value));return path


class DependencyTests(unittest.TestCase):
    def fixture(self,root,alive=True):
        base=root/'R004';source=root/'frozen.py';source.write_text('# CPU fixture\n')
        receipt=base/'queues/Q001/queue_receipt.json';aggregate=put(base/'analysis/Q001/aggregate.json',dict(kind='synthetic_CPU_control_fixture'))
        report=put(base/'analysis/Q001/report_manifest.json',dict(kind='synthetic_CPU_control_fixture'))
        output=base/'analysis/figure_six_columns_final';calls=[]
        def fake_finalize(command,directory,deadline):
            calls.append(command);directory.mkdir();output.mkdir(parents=True)
            for name in ['numerical_six_columns.png','numerical_six_columns.pdf','source_data.json']:
                (output/name).write_text('CPU-control fixture; no numerical figure')
            return dict(exit_code=0,stop_reason=None,worker_reaped=True)
        plan=dict(queue_receipt=str(receipt),queue_process={},renderer=driver.identity(source),renderer_source_identities=[driver.identity(source)],
                  aggregate=str(aggregate),final_report_manifest=str(report),output_dir=str(output),render_wall_seconds=60,poll_seconds=5,
                  utc_deadline=(driver.now()+timedelta(seconds=200)).isoformat())
        plan_file=put(root/'dependency.json',plan)
        validated=dict(plan=plan,plan_source=driver.identity(plan_file),sources=[driver.identity(source),driver.identity(plan_file)],
            queue_plan=dict(groups=[dict(group_id='G001')],finalize_commands=[dict(argv=['synthetic_analysis'])]),
            helper=SimpleNamespace(same_process=lambda proof:alive,finalize=fake_finalize,STOP_RESERVE=30),
            deadline=driver.utc(plan['utc_deadline']),base=base)
        return validated,base/'control',calls,source

    def test_failed_queue_or_missing1024_never_renders(self):
        for state in ['cost_stop','analysis_failed','completed']:
            with self.subTest(state=state),tempfile.TemporaryDirectory() as tmp:
                v,control,calls,source=self.fixture(Path(tmp))
                put(Path(v['plan']['queue_receipt']),dict(execution_state=state,stop_reason=None,
                    full_target_execution_coverage_verified=True,model_execution_completed=True,
                    completed_document_ids=['synthetic_single_id'],not_completed_document_ids=[]))
                result=driver.execute(v,control)
                self.assertEqual(result['execution_state'],'stopped');self.assertEqual(calls,[])

    def test_changed_source_while_waiting_never_renders(self):
        with tempfile.TemporaryDirectory() as tmp:
            v,control,calls,source=self.fixture(Path(tmp))
            def fake_wait(seconds):source.write_text('# changed\n')
            result=driver.execute(v,control,sleep=fake_wait)
            self.assertIn('identity changed',result['stop_reason']);self.assertEqual(calls,[])

    def test_abnormal_queue_exit_or_deadline_never_renders(self):
        for expired in [False,True]:
            with self.subTest(expired=expired),tempfile.TemporaryDirectory() as tmp:
                v,control,calls,source=self.fixture(Path(tmp),alive=False)
                if expired:v['deadline']=driver.now()-timedelta(seconds=1)
                result=driver.execute(v,control)
                self.assertEqual(result['execution_state'],'stopped');self.assertEqual(calls,[])

    def test_success_uses_only_fake_bounded_cpu_helper(self):
        with tempfile.TemporaryDirectory() as tmp:
            v,control,calls,source=self.fixture(Path(tmp),alive=False)
            put(Path(v['plan']['queue_receipt']),dict(kind='synthetic control fixture, not a numerical completion receipt'))
            def fake_completed_inputs(validated,receipt):
                return {key:driver.identity(validated['plan'][path]) for key,path in
                    [('queue_receipt','queue_receipt'),('aggregate','aggregate'),('original_report_manifest','final_report_manifest')]}
            result=driver.execute(v,control,completion_check=fake_completed_inputs)
            self.assertEqual(result['execution_state'],'completed');self.assertEqual(len(calls),1)
            self.assertEqual(calls[0]['wall_seconds'],60);self.assertFalse(result['gpu_started'])
            self.assertEqual(result['numerical_verdict'],'not_assigned');self.assertTrue((control/'output_manifest.json').exists())

    def test_analysis_count_or_failure_is_not_success(self):
        plan=dict(groups=[dict(group_id='G')],finalize_commands=[dict(argv=['synthetic'])])
        receipt=dict(execution_state='completed',stop_reason=None,full_target_execution_coverage_verified=True,model_execution_completed=True,
            completed_document_ids=[f'synthetic_schema_id_{i}' for i in range(1024)],not_completed_document_ids=[],planned_groups=1,finished_groups=1,
            groups=[dict(group_id='G',execution_state='completed')],analysis_results=[])
        with self.assertRaisesRegex(ValueError,'analysis'):driver.require_completed_receipt(receipt,plan)
        receipt['analysis_results']=[dict(argv=['synthetic'],exit_code=1,stop_reason=None,worker_reaped=True)]
        with self.assertRaisesRegex(ValueError,'analysis'):driver.require_completed_receipt(receipt,plan)


if __name__=='__main__':unittest.main()
