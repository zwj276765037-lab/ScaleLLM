"""Analytic, CPU-only checks for the power integration convention."""
import unittest
import copy
import tempfile
import contextlib
import io
import hashlib
from unittest.mock import patch
import json
from pathlib import Path

from analyze_model_power import integrate, validate_model, validate_sample, RAILS, open_telemetry, write_public_telemetry, main, qualify_completion


class IntegrationTests(unittest.TestCase):
    def test_clipped_affine_signal(self):
        points = [dict(time_s=t, power_w=10+2*t) for t in (0, 1, 2)]
        result = integrate(points, .25, 1.75, 3)
        self.assertAlmostEqual(result['integrated_joules'], 18)
        self.assertEqual(result['coverage_fraction'], 1)

    def test_long_gap_is_missing(self):
        result = integrate([dict(time_s=0, power_w=10), dict(time_s=2, power_w=14)], 0, 2, 1)
        self.assertEqual(result['covered_seconds'], 0)
        self.assertEqual(result['missing_seconds'], 2)
        self.assertIsNone(result['time_weighted_mean_w'])

    def test_unobserved_boundaries_not_extrapolated(self):
        result = integrate([dict(time_s=0, power_w=10), dict(time_s=2, power_w=14)], -1, 3, 3)
        self.assertEqual(result['integrated_joules'], 24)
        self.assertEqual(result['coverage_fraction'], .5)

    def test_duplicate_clock_is_rejected(self):
        with self.assertRaises(ValueError):
            integrate([dict(time_s=0, power_w=10), dict(time_s=0, power_w=10)], 0, 1, 3)


class CompressionTests(unittest.TestCase):
    def test_deterministic_gzip_and_both_input_formats(self):
        with tempfile.TemporaryDirectory() as temporary:
            a, b = Path(temporary)/'a', Path(temporary)/'b'
            a.mkdir(); b.mkdir()
            line = json.dumps({'index': 0, 'power_w': 12.5})
            self.assertEqual(write_public_telemetry(a, [line]), write_public_telemetry(b, [line]))
            with open_telemetry(a) as stream:
                self.assertEqual(stream.read(), line+'\n')
            (a/'telemetry.jsonl.gz').unlink()
            (a/'telemetry.jsonl').write_text(line+'\n')
            with open_telemetry(a) as stream:
                self.assertEqual(stream.read(), line+'\n')
            write_public_telemetry(a, [line])
            with self.assertRaises(ValueError):
                open_telemetry(a)


class PublicReplayTests(unittest.TestCase):
    def test_public_gzip_dataset_reproduces_all_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, first, second = [root/name for name in ('source', 'nested/first', 'nested/again/second')]
            (source/'device').mkdir(parents=True)
            receipt, run = InputTests().model_fixture()
            for index, phase in enumerate(receipt['phases']):
                phase.update(ticks=10*index, utc='2026-01-01T00:00:%02dZ' % index)
            receipt.update(state='FAIL', error='Sampler stop timeout', bit_sha256='test-bit',
                           sampler={'native_exit': None}, survivors=[], lease_released=True)
            run.update(execution='COMPLETE', handles_closed=True,
                       final_status={'STATUS': 0, 'ADMISSION_ERROR': 0, 'DONE_ERROR': 0},
                       checkpoint_sha256='test-model', outputs={'0': [123]},
                       slots=[{'generated': [123]}])
            run['steps'][0]['seconds'] = 1.0
            (source/'receipt.json').write_text(json.dumps(receipt))
            (source/'device/run.json').write_text(json.dumps(run))
            reference = root/'reference.json'
            reference.write_text(json.dumps({'outputs': run['outputs']}))
            (source/'device/progress.jsonl').write_text(json.dumps(
                {'event': 'position_committed', 'utc': 1767225603.0})+'\n')
            samples = []
            for index in range(7):
                start = -5+10*index
                samples.append(dict(index=index, sweep_started_ticks=start,
                    sweep_ended_ticks=start+1, monitored_power_w=7,
                    rails=[dict(address=address, name=address, regulator='synthetic',
                        gate_pass=True, power_w=1, current_a=1, voltage_v=1,
                        power_source='CPU_TEST', voltage_source='CPU_TEST', quantization={},
                        read_started_ticks=start+.1, read_finished_ticks=start+.2)
                        for address in RAILS]))
            (source/'telemetry.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in samples))
            for measurement, ref, output in ((source, reference, first),
                    (first, first/'reference_run.json', second)):
                with patch('sys.argv', ['analyzer', '--measurement', str(measurement),
                    '--reference-run', str(ref), '--public-dir', str(output),
                    '--allow-sampler-finalization-timeout']), contextlib.redirect_stdout(io.StringIO()):
                    main()
            def identities(directory):
                return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in directory.rglob('*') if p.is_file()}
            self.assertEqual(identities(first), identities(second))


class InputTests(unittest.TestCase):
    def model_fixture(self):
        names = ('idle_before_begin', 'idle_before_end', 'model_begin', 'model_end',
                 'idle_after_begin', 'idle_after_end')
        receipt = dict(qpc_frequency=10, operations=[dict(name='inference', exit_code=0)],
                       phases=[dict(name=name, ticks=index) for index, name in enumerate(names)])
        run = dict(abi={'core_hz': 80000000},
                   receipts=[dict(command_id=index+1, layer=index//2,
                                  opcode=index % 2+1, cycles=100, active_mask=65535)
                             for index in range(64)], steps=[dict(fpga_cycles=6400)])
        return receipt, run

    def test_real_schema_prerequisites_and_integer_sum(self):
        receipt, run = self.model_fixture()
        self.assertEqual(validate_model(receipt, run), (10, 6400))

    def test_invalid_clock_native_exit_cycles_and_rounds_rejected(self):
        mutations = (
            lambda r, m: r.update(qpc_frequency=0),
            lambda r, m: m['abi'].update(core_hz=100000000),
            lambda r, m: r['operations'][0].update(exit_code=1),
            lambda r, m: r['phases'][3].update(ticks=1),
            lambda r, m: m['receipts'][0].update(cycles=0xffffffff),
            lambda r, m: m['receipts'][0].update(command_id=2),
            lambda r, m: m['steps'][0].update(fpga_cycles=6401),
        )
        for change in mutations:
            receipt, run = self.model_fixture()
            change(receipt, run)
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    validate_model(receipt, run)

    def test_only_explicit_exact_finalization_failure_is_accepted(self):
        receipt, run = self.model_fixture()
        receipt.update(state='FAIL', error='Sampler stop timeout', sampler={'native_exit': None},
                       survivors=[], lease_released=True)
        run.update(execution='COMPLETE', handles_closed=True, final_status={'STATUS': 0})
        self.assertTrue(qualify_completion(receipt, run, True))
        with self.assertRaises(ValueError):
            qualify_completion(receipt, run)
        changes = (
            lambda r, m: r.update(error='Other failure'),
            lambda r, m: r.update(survivors=[123]),
            lambda r, m: r.update(lease_released=False),
            lambda r, m: m.update(handles_closed=False),
            lambda r, m: m['final_status'].update(STATUS=1),
            lambda r, m: r['sampler'].update(native_exit=1),
        )
        for change in changes:
            bad_receipt, bad_run = copy.deepcopy(receipt), copy.deepcopy(run)
            change(bad_receipt, bad_run)
            with self.assertRaises(ValueError):
                qualify_completion(bad_receipt, bad_run, True)

    def test_sensor_sum_and_finite_times(self):
        sample = dict(index=0, sweep_started_ticks=0, sweep_ended_ticks=10,
                      monitored_power_w=7,
                      rails=[dict(address=rail, gate_pass=True, power_w=1,
                                  current_a=1, voltage_v=None,
                                  read_started_ticks=1, read_finished_ticks=2)
                             for rail in RAILS])
        validate_sample(sample, 0)
        for field, value in (('monitored_power_w', 8), ('sweep_ended_ticks', float('nan'))):
            bad = copy.deepcopy(sample)
            bad[field] = value
            with self.assertRaises(ValueError):
                validate_sample(bad, 0)


if __name__ == '__main__':
    unittest.main()
