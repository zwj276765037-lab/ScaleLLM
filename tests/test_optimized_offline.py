"""Offline audit must reject tampering, incomplete coverage and false PASS."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'deploy'))
import scalellm
scalellm.bootstrap()
from optimized import offline_audit as audit


class OfflineAuditTests(unittest.TestCase):
    def test_payload_is_rehashed_and_paths_are_contained(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root/'actual.bin'; path.write_bytes(b'actual')
            record = dict(output_path='actual.bin', output_sha256=hashlib.sha256(b'actual').hexdigest())
            self.assertEqual(audit.payload(root, record, 'output'), b'actual')
            path.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'SHA mismatch'):
                audit.payload(root, record, 'output')
            for name in ('../actual.bin', '/etc/passwd', 'C:/temp/input', 'a\\b'):
                with self.assertRaises(ValueError):
                    audit.contained(root, name)

    def summary(self, layers=2):
        return dict(schema='scalellm_llama_host_fpga_run_v1', execution_state='completed', first_error=None, software_mode='resident_interleaved_v1',
                    mode='pilot', pilot_layers=layers,
                    steps=[dict(step=0, layers=[dict(layer=i, epoch_released=True) for i in range(layers)])],
                    counts=dict(attention_commands=2*layers, gu_commands=2*layers, host_down_tasks=2*layers, epoch_releases=layers),
                    final=dict(pending=None, fpga_lease=None, host_leases=[], handles_closed=True, owned_processes_exited=True))

    def test_two_layer_pilot_has_exact_coverage(self):
        summary = self.summary()
        self.assertEqual(audit.coverage(summary), (True, 2))
        for mutate in (lambda s: s['steps'][0]['layers'].pop(),
                       lambda s: s['steps'][0]['layers'][1].update(layer=0),
                       lambda s: s['counts'].update(gu_commands=3),
                       lambda s: s['final'].update(host_leases=['pending'])):
            broken = copy.deepcopy(summary); mutate(broken)
            with self.assertRaises(ValueError):
                audit.coverage(broken)

    def test_failed_run_cannot_be_certified(self):
        summary = self.summary(); summary['execution_state'] = 'failed'
        summary['first_error'] = {'message': 'watchdog'}
        with self.assertRaisesRegex(ValueError, 'failed run'):
            audit.coverage(summary)

    def test_deferred_v2_execution_requires_complete_coverage(self):
        summary = self.summary()
        summary.update(execution_state='EXECUTION_COMPLETE', verdict='NUMERICAL_VERIFICATION_PENDING',
                       software_mode='resident_interleaved_post_ack_metadata_v2')
        self.assertEqual(audit.coverage(summary), (True, 2))
        summary['final']['pending'] = {'command': 42}
        with self.assertRaisesRegex(ValueError, 'retired'):
            audit.coverage(summary)

    def test_failure_receipt_preserves_summary_and_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); summary = root/'run_summary.json'; original = b'{"verdict":"NUMERICAL_VERIFICATION_PENDING"}'
            summary.write_bytes(original); receipt = root/'audit.json'
            with patch.object(audit, '_evaluate', side_effect=ValueError('actual output mismatch')):
                with self.assertRaisesRegex(ValueError, 'actual output mismatch'):
                    audit.audit(root, 'unused', 'unused', 'unused', receipt)
            result = json.loads(receipt.read_text())
            self.assertEqual(result['verdict'], 'FAIL')
            self.assertEqual(result['run_summary_sha256'], hashlib.sha256(original).hexdigest())
            self.assertFalse(result['device_opened']); self.assertFalse(result['baseline_required'])
            self.assertEqual(summary.read_bytes(), original)
            with self.assertRaisesRegex(ValueError, 'new file'):
                audit.audit(root, 'unused', 'unused', 'unused', receipt)

    def test_summary_mutation_during_audit_is_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); summary = root/'run_summary.json'; summary.write_text('{}')
            def mutate(*args): summary.write_text('{"changed":true}')
            with patch.object(audit, '_evaluate', side_effect=mutate):
                with self.assertRaisesRegex(ValueError, 'changed during audit'):
                    audit.audit(root, 'unused', 'unused', 'unused', root/'audit.json')
            self.assertEqual(json.loads((root/'audit.json').read_text())['verdict'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
