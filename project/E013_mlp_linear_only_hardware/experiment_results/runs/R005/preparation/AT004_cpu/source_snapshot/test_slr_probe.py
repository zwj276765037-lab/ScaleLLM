"""CPU-only evidence-gate checks; never imports or launches an EDA process."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('slr_probe', HERE / 'run_slr_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
observer_spec = importlib.util.spec_from_file_location('slr_observer', HERE / 'observe_routed_checkpoint.py')
observer = importlib.util.module_from_spec(observer_spec)
observer_spec.loader.exec_module(observer)
observer.probe = probe


class TerminalGateTests(unittest.TestCase):
    def setUp(self):
        self.result = dict(execution_state='failed', verdict='FAIL', native_returncode=1,
                           stop_reason=None, changed_inputs=[])
        self.owned = dict(session=12, survivors=[])
        self.launch = dict(stage='impl', session=12)

    def test_natural_failure_is_eligible_only_for_diagnostics(self):
        before = copy.deepcopy(self.result)
        probe.terminal_gate(self.result, self.owned, self.launch)
        self.assertEqual(self.result, before)
        self.assertEqual(self.result['verdict'], 'FAIL')

    def test_active_protected_drift_or_survivors_are_rejected(self):
        for key, value in [('execution_state', 'running'),
                           ('stop_reason', 'resource_protection'),
                           ('changed_inputs', ['rtl'])]:
            r = dict(self.result, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                probe.terminal_gate(r, self.owned, self.launch)
        with self.assertRaises(ValueError):
            probe.terminal_gate(self.result, dict(self.owned, survivors=[99]), self.launch)
        with self.assertRaises(ValueError):
            probe.terminal_gate(self.result, dict(self.owned, session=13), self.launch)
        with self.assertRaises(ValueError):
            probe.terminal_gate(self.result, self.owned, dict(self.launch, stage='synth'))

    def test_signal_unknown_codes_and_inconsistent_success_are_rejected(self):
        for rc in [-9, -15, 137, 143, None, '1', True, 2]:
            with self.subTest(rc=rc), self.assertRaisesRegex(ValueError, 'ordinary Vivado'):
                probe.terminal_gate(dict(self.result, native_returncode=rc), self.owned, self.launch)
        with self.assertRaisesRegex(ValueError, 'disagree'):
            probe.terminal_gate(dict(self.result, verdict='NATIVE_STAGE_COMPLETED'), self.owned, self.launch)
        with self.assertRaisesRegex(ValueError, 'disagree'):
            probe.terminal_gate(dict(self.result, execution_state='completed', verdict='NATIVE_STAGE_COMPLETED'), self.owned, self.launch)


class OwnershipTests(unittest.TestCase):
    def row(self, ppid, sid, birth, rss=10):
        return dict(ppid=ppid, sid=sid, birth=str(birth), rss=rss)

    def test_reparented_session_members_and_new_descendants_are_owned(self):
        rows = {10: self.row(1, 10, 100), 11: self.row(1, 10, 101),
                12: self.row(11, 12, 102), 13: self.row(12, 12, 103),
                50: self.row(1, 50, 105), 51: self.row(1, 10, 90)}
        owned = {10: '100'}
        live, rss = probe.discover_owned(rows, owned, 10, 100)
        self.assertEqual(live, {10, 11, 12, 13})
        self.assertEqual(rss, 40)
        self.assertEqual(set(owned), live)

    def test_old_pid_reuse_is_not_mistaken_for_the_old_owner(self):
        rows = {10: self.row(1, 99, 200), 11: self.row(10, 99, 201)}
        live, rss = probe.discover_owned(rows, {10: '100'}, 10, 100)
        self.assertEqual((live, rss), (set(), 0))

    def test_independently_owned_reused_pid_gets_current_birth(self):
        rows = {10: self.row(1, 10, 100), 11: self.row(10, 10, 201)}
        owned = {10: '100', 11: '101'}
        live, _ = probe.discover_owned(rows, owned, 10, 100)
        self.assertEqual(live, {10, 11})
        self.assertEqual(owned[11], '201')


class OriginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.hw = self.root / 'project/hardware'
        self.e013 = self.root / 'project/E013_mlp_linear_only_hardware'
        self.parent = self.e013 / 'experiment_results/runs/R004/attempts/AT_fixture'
        self.parent.mkdir(parents=True)
        self.report = self.hw / 'vivado/reports/m006_linear_fixture'
        self.report.mkdir(parents=True)
        (self.parent / 'native_reports').symlink_to(self.report, target_is_directory=True)
        snapshot = self.parent / 'source_snapshot/rtl/x.sv'
        snapshot.parent.mkdir(parents=True)
        snapshot.write_text('module x; endmodule\n')
        probe.write_json(self.parent / 'input_manifest.json',
                         {'files': {'rtl/x.sv': probe.sha(snapshot)}})
        self.synth = self.hw / 'vivado/reports/m006_linear_fixture_qual/synthesized.dcp'
        self.synth.parent.mkdir(parents=True)
        self.synth.write_bytes(b'fixture immutable synthesized checkpoint')
        self.receipt = self.synth.parent / 'm006_synth_identity.json'
        manifest_sha = probe.sha(self.parent / 'input_manifest.json')
        probe.write_json(self.receipt, dict(verdict='NATIVE_STAGE_COMPLETED',
                         dcp=str(self.synth), dcp_sha256=probe.sha(self.synth),
                         project='fixture-project', input_manifest_sha256=manifest_sha))
        self.launch = dict(stage='impl', session=12, pid=12, root_birth='100', report=str(self.report),
                           input_manifest_sha256=manifest_sha,
                           synth_dcp=dict(path=str(self.synth), sha256=probe.sha(self.synth)),
                           synth_receipt_sha256=probe.sha(self.receipt), project='fixture-project')
        probe.write_json(self.parent / 'launch.json', self.launch)
        probe.write_json(self.parent / 'result.json', dict(execution_state='failed',
                         verdict='FAIL', native_returncode=1, stop_reason=None, changed_inputs=[]))
        probe.write_json(self.parent / 'owned_processes.json', dict(session=12, survivors=[], pids={'12': '100'}))
        self.dcp = self.report / 'physopt.dcp'
        self.dcp.write_bytes(b'fixture immutable pre-route checkpoint')
        log = self.report / 'vivado.log'
        log.write_text("phys_opt_design completed successfully\nThe checkpoint '" + str(self.dcp) + "' has been generated.\nroute_design\nERROR route failed\n")
        probe.write_json(self.parent / 'physopt_completion_route_launch.json',
                         dict(physopt_dcp=dict(path=str(self.dcp), sha256=probe.sha(self.dcp)),
                              log_prefix=dict(bytes=log.stat().st_size, sha256=probe.sha(log))))
        self.patchers = [patch.object(probe, 'HW', self.hw), patch.object(probe, 'E013', self.e013),
                         patch.object(probe, 'proc_snapshot', return_value={})]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in reversed(self.patchers):
            p.stop()
        self.temp.cleanup()

    def test_failed_route_parent_is_preserved_and_physopt_is_not_routed(self):
        origin = probe.validate_parent(self.parent, 'physopt')
        self.assertEqual(origin['original_parent_verdict'], 'FAIL')
        self.assertEqual(origin['original_parent_native_returncode'], 1)
        self.assertEqual(origin['source_stage'], 'physopt')
        self.assertIn('not_successful_parent', origin['scope'])
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            probe.validate_parent(self.parent, 'routed')

    def routed_fixture(self):
        routed = self.report / 'routed.dcp'
        routed.write_bytes(b'fixture real exported routed checkpoint')
        log = self.report / 'vivado.log'
        log.write_text("route_design completed successfully\nThe checkpoint '" + str(routed) + "' has been generated.\npost-route report ERROR\n")
        probe.write_json(self.parent / 'route_completion_observation.json',
                         dict(routed_dcp=dict(path=str(routed), sha256=probe.sha(routed)),
                              log_prefix=dict(bytes=log.stat().st_size, sha256=probe.sha(log)),
                              observed_before_parent_terminal=True,
                              input_manifest_sha256=self.launch['input_manifest_sha256'],
                              parent_root_birth=self.launch['root_birth']))
        return routed

    def test_routed_stage_requires_recorded_hash_and_rejects_later_replacement(self):
        routed = self.routed_fixture()
        origin = probe.validate_parent(self.parent, 'routed')
        self.assertEqual(origin['source_stage'], 'routed')
        self.assertEqual(origin['original_parent_verdict'], 'FAIL')
        routed.write_bytes(b'different checkpoint with the original export log unchanged')
        with self.assertRaisesRegex(ValueError, 'observation mismatch'):
            probe.validate_parent(self.parent, 'routed')

    def test_routed_stage_without_historical_anchor_is_rejected(self):
        self.routed_fixture()
        (self.parent / 'route_completion_observation.json').unlink()
        with self.assertRaisesRegex(ValueError, 'historical hash'):
            probe.validate_parent(self.parent, 'routed')

    def test_routed_stage_cannot_anchor_a_post_terminal_or_wrong_parent_observation(self):
        for key, value in [('observed_before_parent_terminal', False),
                           ('input_manifest_sha256', 'wrong'), ('parent_root_birth', 'wrong')]:
            self.routed_fixture()
            path = self.parent / 'route_completion_observation.json'
            data = json.loads(path.read_text()); data[key] = value
            probe.write_json(path, data)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'generation-time'):
                probe.validate_parent(self.parent, 'routed')

    def test_observer_captures_before_terminal_and_never_overwrites(self):
        self.routed_fixture()
        (self.parent / 'route_completion_observation.json').unlink()
        (self.parent / 'result.json').unlink()
        live = {12: dict(birth='100', sid=12)}
        with patch.object(probe, 'proc_snapshot', return_value=live):
            record = observer.observe(self.parent)
            self.assertTrue(record['observed_before_parent_terminal'])
            self.assertEqual(record['routed_dcp']['sha256'], probe.sha(self.report / 'routed.dcp'))
            with self.assertRaisesRegex(ValueError, 'new and precede'):
                observer.observe(self.parent)

    def test_observer_rejects_already_terminal_or_dead_original_root(self):
        with self.assertRaisesRegex(ValueError, 'new and precede'):
            observer.observe(self.parent)
        (self.parent / 'result.json').unlink()
        with self.assertRaisesRegex(ValueError, 'no longer live'):
            observer.observe(self.parent)

    def test_observer_cannot_anchor_an_incomplete_native_export(self):
        (self.parent / 'result.json').unlink()
        with patch.object(probe, 'proc_snapshot', return_value={12: dict(birth='100', sid=12)}):
            with self.assertRaisesRegex(ValueError, 'not yet natively completed'):
                observer.observe(self.parent)

    def test_source_checkpoint_and_log_prefix_corruption_are_rejected(self):
        for path in [self.parent / 'source_snapshot/rtl/x.sv', self.dcp, self.report / 'vivado.log']:
            data = path.read_bytes()
            path.write_bytes(b'X' + data[1:])
            with self.subTest(path=path.name), self.assertRaises(ValueError):
                probe.validate_parent(self.parent, 'physopt')
            path.write_bytes(data)

    def test_missing_native_completion_or_export_is_rejected(self):
        log = self.report / 'vivado.log'
        for data in ['route_design ERROR', 'phys_opt_design completed successfully']:
            log.write_text(data)
            with self.subTest(data=data), self.assertRaises(ValueError):
                probe.validate_parent(self.parent, 'physopt')

    def test_live_original_owner_is_rejected(self):
        with patch.object(probe, 'proc_snapshot', return_value={12: dict(birth='100')}):
            with self.assertRaisesRegex(ValueError, 'still live'):
                probe.validate_parent(self.parent, 'physopt')

    def test_failure_receipt_or_project_mismatch_is_rejected(self):
        original = self.receipt.read_text()
        for key, value in [('verdict', 'FAIL'), ('project', 'other-project')]:
            data = json.loads(original)
            data[key] = value
            probe.write_json(self.receipt, data)
            self.launch['synth_receipt_sha256'] = probe.sha(self.receipt)
            probe.write_json(self.parent / 'launch.json', self.launch)
            with self.subTest(key=key), self.assertRaises(ValueError):
                probe.validate_parent(self.parent, 'physopt')

    def test_no_terminal_record_rejected_without_output_mutations(self):
        (self.parent / 'result.json').unlink()
        before = set(self.root.rglob('*'))
        with self.assertRaisesRegex(ValueError, 'terminal record'):
            probe.validate_parent(self.parent, 'physopt')
        self.assertEqual(before, set(self.root.rglob('*')))


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.report = Path(self.temp.name)
        for name in ['design_identity.txt', 'scopes.tsv', 'path_samples.tsv']:
            (self.report / name).write_text('native fixture\n')
        self.names = ['route_status', 'utilization_slr', 'crossing_global', 'slice_sites', 'congestion', 'old_windows']
        (self.report / 'sections.tsv').write_text('section\tstatus\tdetail\n' + ''.join(n + '\tCOLLECTED\t\n' for n in self.names))
        (self.report / 'vivado.log').write_text('M006_SLR_DIAGNOSTIC_COLLECTION_DONE\n')

    def tearDown(self):
        self.temp.cleanup()

    def test_native_collection_is_not_physical_acceptance(self):
        success, verdict, _, _, _ = probe.assess_collection(self.report, 0, None, [], [])
        self.assertTrue(success)
        self.assertEqual(verdict, 'DIAGNOSTICS_COLLECTED')
        self.assertNotEqual(verdict, 'NATIVE_STAGE_COMPLETED')

    def test_report_error_is_explicitly_partial(self):
        with (self.report / 'sections.tsv').open('a') as f:
            f.write('scope_metadata\tERROR\tnative error\n')
        success, verdict, _, _, _ = probe.assess_collection(self.report, 0, None, [], [])
        self.assertTrue(success)
        self.assertEqual(verdict, 'DIAGNOSTICS_PARTIAL')

    def test_zero_sections_or_missing_identity_cannot_be_complete(self):
        (self.report / 'sections.tsv').write_text('section\tstatus\tdetail\n')
        self.assertFalse(probe.assess_collection(self.report, 0, None, [], [])[0])
        (self.report / 'design_identity.txt').unlink()
        self.assertFalse(probe.assess_collection(self.report, 0, None, [], [])[0])

    def test_stop_drift_survivors_and_native_failure_all_fail(self):
        for args in [(1, None, [], []), (0, 'resource_protection', [], []),
                     (0, None, [12], []), (0, None, [], ['rtl'])]:
            with self.subTest(args=args):
                self.assertEqual(probe.assess_collection(self.report, *args)[1], 'FAIL')


class NewWindowTests(unittest.TestCase):
    def test_latest_native_table_priority_dedup_and_four_window_bound(self):
        old = b'Congestion Report\nGLOBAL Congestion bounded by tiles:\nEAST\nINT_X1Y1->INT_X2Y2\nINFO: old\n'
        latest = (b'Congestion Report\nGLOBAL Congestion bounded by tiles:\n'
                  b'NORTH\nINT_X54Y648->INT_X85Y823 (native)\n'
                  b'SOUTH\nINT_X34Y75->INT_X97Y138\n'
                  b'EAST\nINT_X17Y465->INT_X80Y560\nINT_X4Y485->INT_X67Y548\n'
                  b'WEST\nINT_X11Y463->INT_X74Y590\n'
                  b'SHORT Congestion bounded by tiles:\nNORTH\nINT_X80Y387->INT_X95Y402\n'
                  b'INFO: end\n')
        result = probe.select_new_windows(old + latest)
        self.assertEqual(len(result['windows']), 4)
        self.assertEqual(result['windows'][0]['lower_left'], 'INT_X17Y465')
        self.assertEqual(result['windows'][1]['lower_left'], 'INT_X80Y387')
        self.assertNotIn('INT_X1Y1', json.dumps(result['windows']))
        self.assertEqual(result['parent_log_byte_offset'], len(old))
        self.assertNotIn('slr', json.dumps(result['windows']).lower())

    def test_missing_or_duplicate_windows_do_not_create_inferred_hotspots(self):
        self.assertEqual(probe.select_new_windows(b'no table')['windows'], [])
        same = (b'Congestion Report\nGLOBAL Congestion:\nNORTH\nINT_X1Y1->INT_X2Y2\n'
                b'EAST\nINT_X1Y1->INT_X2Y2\nINFO: end')
        self.assertEqual(len(probe.select_new_windows(same)['windows']), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
