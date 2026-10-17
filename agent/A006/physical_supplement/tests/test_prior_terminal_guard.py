"""CPU-only admission checks; no Vivado or physical commands are invoked."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'run_closed_comparison.py'
SPEC = importlib.util.spec_from_file_location('closed_supplement_guard', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PriorTerminalGuardTests(unittest.TestCase):
    def setUp(self):
        self.original = {'started_utc': '2026-10-16T01:00:00+00:00',
                         'leader_pid': 1073741823, 'leader_start_ticks': 1}
        self.status = dict(self.original, execution_state='completed', ended_utc='2026-10-16T01:00:01+00:00',
                           native_exit_code=0, exit_code=0, owned_survivors=[])
        self.status_path = Path('/tmp/ordinary_prior_attempt/status.json')
        self.started_path = self.status_path.with_name('started.json')

    def qualify(self):
        return MODULE.prior_terminal_kind(self.status, self.original, self.status_path, self.started_path)

    def test_completed_receipt_is_terminal(self):
        self.assertEqual(self.qualify(), 'explicit_terminal_completed')

    def test_failed_receipt_preserves_failure_and_is_terminal(self):
        self.status.update(execution_state='failed', exit_code=1, native_exit_code=1)
        before = copy.deepcopy(self.status)
        self.assertEqual(self.qualify(), 'explicit_terminal_failed')
        self.assertEqual(MODULE.require_registered_closed(
            MODULE.prior_registered_identities(self.status, self.original)), [])
        self.assertEqual(self.status, before)

    def test_completed_nonzero_receipt_is_closed_not_success(self):
        self.status.update(exit_code=1, native_exit_code=1)
        self.assertEqual(self.qualify(), 'explicit_terminal_completed')
        self.assertEqual(self.status['exit_code'], 1)

    def test_missing_end_is_rejected(self):
        del self.status['ended_utc']
        with self.assertRaises(ValueError): self.qualify()

    def test_missing_exit_is_rejected(self):
        del self.status['exit_code']
        with self.assertRaises(ValueError): self.qualify()

    def test_missing_native_exit_is_rejected(self):
        del self.status['native_exit_code']
        with self.assertRaises(ValueError): self.qualify()

    def test_boolean_exit_is_rejected(self):
        self.status['exit_code'] = True
        with self.assertRaises(ValueError): self.qualify()

    def test_survivors_are_rejected(self):
        self.status['owned_survivors'] = [{'pid': 1}]
        with self.assertRaises(ValueError): self.qualify()

    def test_absent_survivor_receipt_is_rejected(self):
        del self.status['owned_survivors']
        with self.assertRaises(ValueError): self.qualify()

    def test_end_before_start_is_rejected(self):
        self.status['ended_utc'] = '2026-10-16T00:59:59+00:00'
        with self.assertRaises(ValueError): self.qualify()

    def test_inconsistent_start_is_rejected(self):
        self.status['started_utc'] = '2026-10-16T00:00:00+00:00'
        with self.assertRaises(ValueError): self.qualify()

    def test_running_even_with_end_is_rejected(self):
        self.status['execution_state'] = 'running'
        with self.assertRaises(ValueError): self.qualify()

    def test_unknown_even_with_end_is_rejected(self):
        self.status['execution_state'] = 'UNKNOWN'
        with self.assertRaises(ValueError): self.qualify()

    def test_arbitrary_missing_state_is_rejected(self):
        del self.status['execution_state']
        with self.assertRaises(ValueError): self.qualify()

    def test_null_state_is_rejected(self):
        self.status['execution_state'] = None
        with self.assertRaises(ValueError): self.qualify()

    def test_actual_legacy_cpu_receipts_are_bound_and_closed(self):
        for name in MODULE.LEGACY_CPU_RECEIPTS:
            with self.subTest(name=name):
                directory = MODULE.RUNS / 'R002/attempts' / name
                sp, bp = directory / 'status.json', directory / 'started.json'
                status, original = json.loads(sp.read_text()), json.loads(bp.read_text())
                self.assertNotIn('execution_state', status)
                self.assertEqual(MODULE.prior_terminal_kind(status, original, sp, bp),
                                 'explicit_closed_legacy_CPU_receipt_missing_state_field')
                registered = MODULE.prior_registered_identities(status, original)
                self.assertIn(str(original['leader_pid']), registered)
                self.assertEqual(MODULE.require_registered_closed(registered), [])

    def test_legacy_binding_change_is_rejected(self):
        directory = MODULE.RUNS / 'R002/attempts/AT007_supervision_recovery_cpu'
        sp, bp = directory / 'status.json', directory / 'started.json'
        status, original = json.loads(sp.read_text()), json.loads(bp.read_text())
        with patch.object(MODULE, 'identity', return_value={'sha256': 'changed'}):
            with self.assertRaises(ValueError): MODULE.prior_terminal_kind(status, original, sp, bp)

    def test_live_started_leader_is_rejected(self):
        pid = os.getpid()
        start = int(Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19])
        registered = MODULE.prior_registered_identities({}, {'leader_pid': pid, 'leader_start_ticks': start})
        with self.assertRaises(ValueError): MODULE.require_registered_closed(registered)

    def test_missing_ownership_identity_is_rejected(self):
        with self.assertRaises(ValueError): MODULE.require_registered_closed({})

    def test_reused_pid_different_start_is_not_original_owner(self):
        pid = os.getpid()
        start = int(Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19])
        self.assertEqual(MODULE.require_registered_closed({str(pid): start - 1}), [])

    def test_conflicting_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.prior_registered_identities({'tracked_identities': {'12345': 1}},
                                              {'leader_pid': 12345, 'leader_start_ticks': 2})

    def test_started_supervisor_is_included(self):
        self.assertEqual(MODULE.prior_registered_identities({}, {'supervisor_pid': 12345, 'supervisor_start_ticks': 6}),
                         {'12345': 6})

    def test_extra_receipt_identity_is_included(self):
        self.assertEqual(MODULE.prior_registered_identities({}, {}, {'12345': 6}), {'12345': 6})


if __name__ == '__main__':
    unittest.main()
