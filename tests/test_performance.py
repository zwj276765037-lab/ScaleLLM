"""Standard-library analysis checks, with explicit synthetic CPU-only records."""
import copy
import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('final_performance', ROOT / 'tools/analyze_performance.py')
performance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(performance)


def synthetic_run(eos=False):
    """Create small protocol observations, never claimed as FPGA measurements."""
    requests = [dict(slot=0, prompt_token_ids=[10], max_new_tokens=2),
                dict(slot=3, prompt_token_ids=[20, 21], max_new_tokens=3)]
    states = [dict(epoch=0, prompt=[], max_new_tokens=0, position=0,
                   generated=[], finished=True) for _ in range(16)]
    for request in requests:
        states[request['slot']].update(epoch=1, prompt=request['prompt_token_ids'],
                                      max_new_tokens=request['max_new_tokens'], finished=False)
    steps, receipts = [], []
    while any(not state['finished'] for state in states):
        index = len(steps)
        active = [slot for slot, state in enumerate(states) if not state['finished']]
        mask = sum(1 << slot for slot in active)
        group = [dict(command_id=index * 64 + j + 1, layer=j // 2, opcode=j % 2 + 1,
                      active_mask=mask, cycles=1000 + index * 64 + j) for j in range(64)]
        receipts.extend(group)
        emitted = {}
        for slot in active:
            state = states[slot]
            state['position'] += 1
            if state['position'] >= len(state['prompt']):
                token = 128009 if eos and slot == 3 else 100 + 10 * index + slot
                state['generated'].append(token)
                emitted[str(slot)] = token
                state['finished'] = (len(state['generated']) == state['max_new_tokens'] or token == 128009)
        steps.append(dict(index=index, fpga_cycles=sum(r['cycles'] for r in group),
                          emitted=emitted, slots=copy.deepcopy(states),
                          phase='generation' if emitted else 'prefill'))
    outputs = {str(request['slot']): states[request['slot']]['generated'] for request in requests}
    return dict(schema='scalellm_final_decode16_execution_v1', execution='COMPLETE',
                abi={'core_hz': 80000000}, checkpoint_sha256=performance.CHECKPOINT_SHA,
                final_quiescent=True, handles_closed=True,
                final_status={'STATUS': 0, 'ADMISSION_ERROR': 0, 'DONE_ERROR': 0},
                numerical_verification='NOT_RUN', requests=requests, receipts=receipts,
                steps=steps, slots=copy.deepcopy(states), outputs=copy.deepcopy(outputs),
                decoded={slot: dict(eos=tokens[-1] == 128009) for slot, tokens in outputs.items()})


class PerformanceTests(unittest.TestCase):
    def reject(self, run):
        with self.assertRaises(ValueError):
            performance.analyze(run)

    def test_actual_metrics_and_every_csv_row_unchanged(self):
        directory = ROOT / 'docs/evidence/inference_chat16'
        summary, commands, rounds = performance.analyze(json.loads((directory / 'run.json').read_text()))
        expected = json.loads((directory / 'fpga_metrics.json').read_text())
        expected.pop('source_sha256')
        self.assertEqual(summary, expected)
        for filename, rows in (('fpga_commands.csv', commands), ('fpga_rounds.csv', rounds)):
            with (directory / filename).open(newline='') as stream:
                published = list(csv.DictReader(stream))
            self.assertEqual([{key: str(value) for key, value in row.items()} for row in rows], published)

    def test_positive_sparse_slots_and_natural_eos(self):
        full, _, rounds = performance.analyze(synthetic_run())
        stopped, _, short_rounds = performance.analyze(synthetic_run(eos=True))
        self.assertEqual((full['requests'], full['rounds'], full['generated_tokens']), (2, 4, 5))
        self.assertEqual([r['active_mask'] for r in rounds], [9, 9, 8, 8])
        self.assertEqual((stopped['rounds'], stopped['generated_tokens']), (2, 3))
        self.assertEqual(short_rounds[-1]['phase'], 'prompt_or_mixed')

    def test_request_identity_slot_budget_and_context_rejection(self):
        for change in ('duplicate', 'boolean_slot', 'slot_range', 'token_type', 'token_range', 'budget', 'context'):
            run = synthetic_run()
            if change == 'duplicate': run['requests'].append(copy.deepcopy(run['requests'][0]))
            if change == 'boolean_slot': run['requests'][0]['slot'] = True
            if change == 'slot_range': run['requests'][0]['slot'] = 16
            if change == 'token_type': run['requests'][0]['prompt_token_ids'] = [True]
            if change == 'token_range': run['requests'][0]['prompt_token_ids'] = [128256]
            if change == 'budget': run['requests'][0]['max_new_tokens'] = 33
            if change == 'context': run['requests'][0]['prompt_token_ids'] = [1] * 128
            with self.subTest(change=change): self.reject(run)

    def test_early_missing_and_bad_token_emission_rejection(self):
        for change in ('early', 'missing', 'unknown_slot', 'boolean_token', 'vocabulary', 'duplicate_normalized_slot'):
            run = synthetic_run()
            emitted = run['steps'][0]['emitted']
            if change == 'early': emitted['3'] = 123
            if change == 'missing': emitted.clear()
            if change == 'unknown_slot': emitted['7'] = 123
            if change == 'boolean_token': emitted['0'] = True
            if change == 'vocabulary': emitted['0'] = 128256
            if change == 'duplicate_normalized_slot': emitted[0] = emitted['0']
            with self.subTest(change=change): self.reject(run)

    def test_all_snapshot_fields_and_inactive_rows_rejection(self):
        for key, value in (('epoch', 2), ('prompt', [999]), ('max_new_tokens', 1),
                           ('position', 2), ('generated', [999]), ('finished', True), ('epoch', True)):
            run = synthetic_run()
            run['steps'][0]['slots'][0][key] = value
            with self.subTest(key=key, value=value): self.reject(run)
        run = synthetic_run(); run['steps'][0]['slots'][15]['position'] = 1
        self.reject(run)
        run = synthetic_run(); run['slots'][0]['generated'] = []
        self.reject(run)

    def test_command_active_mask_and_cycle_rejection(self):
        for key, value in (('command_id', 2), ('layer', 1), ('opcode', 2),
                           ('active_mask', 1), ('cycles', True), ('cycles', 0), ('cycles', 2**32 - 1)):
            run = synthetic_run(); run['receipts'][0][key] = value
            with self.subTest(key=key, value=value): self.reject(run)
        run = synthetic_run(); run['steps'][0]['fpga_cycles'] += 1
        self.reject(run)
        run = synthetic_run(); run['steps'][1]['index'] = 0
        self.reject(run)

    def test_finished_slot_reuse_and_over_budget_rejection(self):
        run = synthetic_run(); run['requests'][0]['max_new_tokens'] = 1
        self.reject(run)
        run = synthetic_run()
        for receipt in run['receipts'][128:192]: receipt['active_mask'] |= 1
        self.reject(run)
        run = synthetic_run(eos=True)
        run['steps'][-1]['slots'][3]['finished'] = False
        self.reject(run)

    def test_outputs_and_eos_metadata_rejection(self):
        for change in ('unknown_output', 'different_output', 'eos_flag', 'stop_reason'):
            run = synthetic_run()
            if change == 'unknown_output': run['outputs']['15'] = [123]
            if change == 'different_output': run['outputs']['0'][0] += 1
            if change == 'eos_flag': run['decoded']['0']['eos'] = True
            if change == 'stop_reason': run['decoded']['0']['stop_reason'] = 'eos'
            with self.subTest(change=change): self.reject(run)

    def test_incomplete_or_unknown_run_rejection(self):
        for change in ('clock', 'checkpoint', 'schema', 'empty', 'partial', 'device_error'):
            run = synthetic_run()
            if change == 'clock': run['abi']['core_hz'] = 100000000
            if change == 'checkpoint': run['checkpoint_sha256'] = '0' * 64
            if change == 'schema': run['schema'] = 'old'
            if change == 'empty': run['steps'] = []; run['receipts'] = []
            if change == 'partial': run['steps'].pop(); del run['receipts'][-64:]
            if change == 'device_error': run['final_status']['DONE_ERROR'] = 1
            with self.subTest(change=change): self.reject(run)

    def test_cli_without_site_packages(self):
        with tempfile.TemporaryDirectory(prefix='performance standard library ') as folder:
            result = subprocess.run([sys.executable, '-S', str(ROOT / 'tools/analyze_performance.py'),
                                     str(ROOT / 'docs/evidence/inference_chat16/run.json'),
                                     '--output', str(Path(folder) / 'analysis with spaces')],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)['generated_tokens'], 512)


if __name__ == '__main__':
    unittest.main()
