"""CPU-only refusal controls for the bounded diagnostic resource guard."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('probe_guard', HERE / 'run_gpu0_performance_probe.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class GuardControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.exp = Path(self.temp.name) / 'exp'
        self.exp.mkdir()
        for name in ['benchmark_bytewise_integrity.py', 'gsm8k_integrity_bytewise.py',
                     'gsm8k_weight_integrity.py', 'gsm8k_protocol.py']:
            (self.exp / name).write_text('# synthetic CPU fixture\n')
        self.output = Path(self.temp.name) / 'receipt'
        self.patches = [mock.patch.object(guard, 'EXP', self.exp),
                        mock.patch.object(guard, 'SCRIPT', self.exp / 'benchmark_bytewise_integrity.py')]
        for patch in self.patches:
            patch.start()
        self.spec = {'kind': 'synthetic_gpu0', 'gpu_uuid': guard.GPU,
                     'shared_diagnostic': True, 'acknowledged_external_client_pids': [1234],
                     'source_hashes': {str(p): guard.digest(p) for p in self.exp.iterdir()},
                     'command': [guard.PYTHON, '-B', str(guard.SCRIPT), '--device', 'cuda:0',
                                 '--gpu-uuid', guard.GPU, '--mib', '64', '--chunk-mib', '16',
                                 '--repeats', '3', '--diagnostic-shared-gpu0',
                                 '--output', str(self.output / 'payload.json')]}

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.temp.cleanup()

    def test_explicit_shared_probe_passes_source_and_budget_checks(self):
        self.assertTrue(guard.validate_spec(self.spec, self.output))

    def test_shared_probe_cannot_claim_exclusive(self):
        self.spec['command'].append('--exclusive-gpu0-slot')
        with self.assertRaises(ValueError):
            guard.validate_spec(self.spec, self.output)

    def test_large_memory_or_repeat_request_refused(self):
        for field, value in [('--mib', '65'), ('--chunk-mib', '17'), ('--repeats', '6')]:
            with self.subTest(field=field):
                candidate = copy.deepcopy(self.spec)
                candidate['command'][candidate['command'].index(field) + 1] = value
                with self.assertRaises(ValueError):
                    guard.validate_spec(candidate, self.output)

    def test_wrong_uuid_entrypoint_and_output_are_refused(self):
        for index, value in [(2, '/tmp/unreviewed.py'),
                             (self.spec['command'].index('--gpu-uuid') + 1, 'GPU-other'),
                             (self.spec['command'].index('--output') + 1, '/tmp/outside.json')]:
            with self.subTest(index=index):
                candidate = copy.deepcopy(self.spec)
                candidate['command'][index] = value
                with self.assertRaises(ValueError):
                    guard.validate_spec(candidate, self.output)

    def test_both_helper_source_identities_are_mandatory(self):
        del self.spec['source_hashes'][str(self.exp / 'gsm8k_weight_integrity.py')]
        with self.assertRaises(ValueError):
            guard.validate_spec(self.spec, self.output)

    def test_post_review_source_mutation_is_refused(self):
        guard.SCRIPT.write_text('# changed after source freeze\n')
        with self.assertRaises(ValueError):
            guard.validate_spec(self.spec, self.output)

    def resources(self, clients, *, uuid=None, free='20000', available='200000000'):
        responses = [clients, '0, ' + (uuid or guard.GPU) + ', ' + free + '\n']
        with mock.patch.object(guard, 'command_read', side_effect=responses), \
             mock.patch.object(guard.Path, 'read_text', return_value='MemAvailable: ' + available + ' kB\n'):
            return guard.resources(self.spec, [])

    def test_acknowledged_external_client_is_recorded_and_never_controlled(self):
        with mock.patch.object(guard.subprocess, 'Popen', side_effect=AssertionError('must not execute')):
            result = self.resources('1234, external_python, 12000\n')
        self.assertEqual(result['external_client_pids'], [1234])
        self.assertTrue(result['shared_diagnostic'])
        self.assertFalse(result['formal_qualification'])

    def test_unacknowledged_client_or_exclusive_occupancy_refused(self):
        with self.assertRaises(RuntimeError):
            self.resources('9999, unknown, 1000\n')
        self.spec['shared_diagnostic'] = False
        with self.assertRaises(RuntimeError):
            self.resources('1234, acknowledged_but_not_exclusive, 1000\n')

    def test_gpu_identity_and_reserves_fail_closed(self):
        for kwargs in [{'uuid': 'GPU-other'}, {'free': '1000'}, {'available': '1000'}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(RuntimeError):
                self.resources('', **kwargs)


if __name__ == '__main__':
    unittest.main(verbosity=2)
