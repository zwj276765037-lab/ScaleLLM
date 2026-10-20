"""CPU-only controls for fixed-scope model diagnostic resource and identity gates."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import run_gpu0_model_speed_probe as guard


class ModelGuardControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.old = root / 'old'
        self.exp = root / 'exp'
        self.e010 = root / 'E010'
        self.diag = self.e010 / 'experiment_results/performance_repair/diag'
        self.output = self.diag / 'execution'
        self.identity = root / 'model_identity.json'
        self.identity.write_text('{}')
        for p in [self.old / 'frozen_inputs', self.old / 'frozen_sources', self.exp, self.diag]:
            p.mkdir(parents=True, exist_ok=True)
        (self.old / 'frozen_inputs/plan.json').write_text(json.dumps({
            'protocol_id': 'original', 'protocol': {'fewshot_schedule_file': 'fewshot.json'},
            'data': {'identity': 'unchanged'}}))
        self.sources = {}
        self.snapshots = {}
        for name in ['run_gsm8k_worker.py', 'gsm8k_protocol.py', 'gsm8k_integrity_bytewise.py']:
            p = self.exp / name
            p.write_text('# source fixture\n')
            snap = self.diag / name
            snap.write_bytes(p.read_bytes())
            self.sources[str(p)] = guard.digest(p)
            self.snapshots[str(p)] = str(snap)
        (self.old / 'frozen_sources/manifest.json').write_text(json.dumps([
            {'path': p} for p in self.sources if not p.endswith('gsm8k_integrity_bytewise.py')]))
        baseline = self.old / 'smoke' / guard.MODEL.name / 'bf16/AT001'
        baseline.mkdir(parents=True)
        (baseline / 'summary.json').write_text(json.dumps({'peak_memory_reserved_bytes': 15 * guard.GIB}))
        (baseline / 'manifest.json').write_text(json.dumps({'state': 'complete',
            'model_load_attach_peak_memory_reserved_bytes': 16 * guard.GIB,
            'verification_peak_memory_reserved_bytes': 17 * guard.GIB}))
        self.patches = [mock.patch.object(guard, 'OLD', self.old), mock.patch.object(guard, 'E010', self.e010),
                        mock.patch.object(guard, 'EXP', self.exp), mock.patch.object(guard, 'IDENTITY', self.identity),
                        mock.patch.object(guard, 'WORKER', self.exp / 'run_gsm8k_worker.py')]
        for p in self.patches:
            p.start()
        self.plan = self.diag / 'plan.json'
        self.plan.write_text(json.dumps(guard.expected_plan()))
        self.spec = {'scope': copy.deepcopy(guard.SCOPE), 'gpu_uuid': guard.GPU, 'case': 'bf16',
                     'plan': str(self.plan), 'plan_sha256': guard.digest(self.plan),
                     'command': guard.expected_command(self.plan, self.output, 'bf16'),
                     'model_identity_sha256': guard.digest(self.identity),
                     'source_hashes': self.sources, 'source_snapshots': self.snapshots,
                     'baseline_summary_sha256': guard.digest(baseline / 'summary.json'),
                     'baseline_manifest_sha256': guard.digest(baseline / 'manifest.json'),
                     'acknowledged_external_client_pids': [23186]}

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def test_fixed_verified_training_command_passes(self):
        self.assertEqual(guard.validate(self.spec, self.output),
                         __import__('math').ceil(17 * guard.GIB * 1.2) + 8 * guard.GIB)

    def test_formal_resume_or_altered_generation_refused(self):
        for old, new in [('smoke', 'formal'), ('64', '4096'), ('--verify-generation', '--resume-from')]:
            spec = copy.deepcopy(self.spec)
            spec['command'][spec['command'].index(old)] = new
            with self.subTest(old=old), self.assertRaises(ValueError):
                guard.validate(spec, self.output)

    def test_false_exclusive_scope_wrong_gpu_and_unsupported_case_refused(self):
        for field, value in [('scope', {**guard.SCOPE, 'exclusive_verified': True}),
                             ('gpu_uuid', 'GPU-other'), ('case', 'reference_qdq')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                guard.validate({**self.spec, field: value}, self.output)

    def test_protocol_change_rejected_even_with_updated_hash(self):
        plan = guard.expected_plan()
        plan['data']['identity'] = 'different'
        self.plan.write_text(json.dumps(plan))
        with self.assertRaises(ValueError):
            guard.validate({**self.spec, 'plan_sha256': guard.digest(self.plan)}, self.output)

    def test_missing_source_refused(self):
        spec = copy.deepcopy(self.spec)
        del spec['source_hashes'][str(self.exp / 'gsm8k_integrity_bytewise.py')]
        with self.assertRaises(ValueError):
            guard.validate(spec, self.output)

    def test_live_and_saved_source_changes_both_refused(self):
        for p in [self.exp / 'run_gsm8k_worker.py', self.diag / 'gsm8k_protocol.py']:
            original = p.read_bytes()
            p.write_text('# mutation')
            with self.subTest(path=p), self.assertRaises(ValueError):
                guard.validate(self.spec, self.output)
            p.write_bytes(original)

    def test_baseline_manifest_tampering_cannot_lower_memory_gate(self):
        baseline = self.old / 'smoke' / guard.MODEL.name / 'bf16/AT001/manifest.json'
        data = json.loads(baseline.read_text())
        data['verification_peak_memory_reserved_bytes'] = 1
        baseline.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            guard.validate(self.spec, self.output)

    def read_resources(self, clients='23186, python, 12146\n', free=36000, host=500000000, uuid=None):
        with mock.patch.object(guard, 'command_read', side_effect=[clients, f'0, {uuid or guard.GPU}, {free}\n']), \
             mock.patch.object(guard.Path, 'read_text', return_value=f'MemAvailable: {host} kB\n'):
            return guard.resources(self.spec, 29 * guard.GIB, [])

    def test_acknowledged_client_is_only_observed(self):
        with mock.patch.object(guard.subprocess, 'Popen', side_effect=AssertionError('no child here')):
            record = self.read_resources()
        self.assertEqual(record['external_client_pids'], [23186])
        self.assertFalse(record['exclusive_verified'])
        self.assertFalse(record['formal_progression_eligible'])

    def test_unacknowledged_client_refused(self):
        with self.assertRaises(RuntimeError):
            self.read_resources(clients='999, other, 1000\n')

    def test_insufficient_free_memory_host_and_wrong_uuid_refused(self):
        for kwargs in [{'free': 25000}, {'host': 1000}, {'uuid': 'GPU-other'}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(RuntimeError):
                self.read_resources(**kwargs)


if __name__ == '__main__':
    unittest.main(verbosity=2)
