"""Deployment profiles, execution policy and failure receipts without a board."""
import contextlib
import copy
import dataclasses
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'deploy'))
import scalellm
from final import common, execution
common.bootstrap()
from final import run
from host import scalellm_final_runtime as runtime_module
from host.scalellm_final_layout import HIDDEN


class Backend:
    def __init__(self, session=None, timeout=120):
        self.session = session
        self.recovery_generation = 1
        self.pending = None
        self.receipts = []
        self.fail_command = None

    def require_quiescent(self):
        if self.pending is not None:
            raise RuntimeError('pending command')

    def run(self, descriptor, payload, validate_output=None):
        if descriptor.command_id == self.fail_command:
            self.pending = descriptor
            raise RuntimeError('injected final command failure')
        self.receipts.append(dict(command_id=descriptor.command_id, active_mask=descriptor.active_mask,
                                  layer=descriptor.layer, opcode=descriptor.opcode, cycles=1))
        return bytes(descriptor.output_bytes) if descriptor.opcode == 1 else b''


class Model:
    def __init__(self, *args):
        pass

    def embed(self, tokens):
        import numpy as np
        return np.zeros((16, HIDDEN), dtype=np.float32)

    def attention_input(self, hidden, layer):
        return hidden

    def after_attention(self, hidden, attention, layer, mask):
        return hidden, hidden

    def after_mlp(self, residual, product, layer, mask):
        return residual

    def predict(self, hidden, mask):
        return [1000] * 16


class Assets:
    def __init__(self, *args):
        self.receipts = []

    def load_resident(self):
        pass

    def prepare_layer(self, layer, rows):
        return layer + 1


class DeploymentProfileTests(unittest.TestCase):
    def test_program_receipt_rejects_foreign_host_and_previous_boot(self):
        identity = dict(hostname='reproduction-host', platform='win32', boot_id='boot-A',
                        boot_source='test-fixture')
        receipt = dict(schema='scalellm_sram_program_receipt_v1', execution='COMPLETE',
                       returncode=0, deployment_profile=common.profile_identity(),
                       volatile_sram=True, host_identity=identity)
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
                common, 'current_host_identity', return_value=identity):
            path = Path(directory) / 'program.json'
            path.write_text(json.dumps(receipt))
            self.assertEqual(common.read_program_receipt(path)['receipt'], receipt)
            for altered in (None, dict(identity, hostname='another-host'), dict(identity, boot_id='boot-B')):
                path.write_text(json.dumps(dict(receipt, host_identity=altered)))
                with self.assertRaisesRegex(ValueError, 'different host/boot'):
                    common.read_program_receipt(path)

    def test_exact_released_bit_profiles(self):
        optimized = ROOT / 'resource_optimization/hardware/bitstream/ScaleLLM_Final_Decode16_80MHz.bit'
        legacy = ROOT / 'bitstream/ScaleLLM_Final_Decode16_80MHz.bit'
        self.assertEqual(common.check_bit(optimized), optimized)
        self.assertEqual(common.check_bit(legacy, 'legacy'), legacy)
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            common.check_bit(legacy)
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            common.check_bit(optimized, 'legacy')
        with self.assertRaisesRegex(ValueError, 'deployment_profile'):
            common.check_bit(optimized, 'arbitrary')
        with tempfile.TemporaryDirectory() as directory:
            wrong = Path(directory) / 'wrong.bit'
            with wrong.open('wb') as stream:
                stream.truncate(common.BIT_BYTES)
            with self.assertRaisesRegex(ValueError, 'SHA256'):
                common.check_bit(wrong)

    def test_config_relative_paths_profiles_and_optional_wall(self):
        with tempfile.TemporaryDirectory(prefix='deployment paths ') as directory:
            folder = Path(directory)
            source = json.loads((ROOT / 'deploy/config.example.json').read_text())
            source.update(deployment_profile='legacy', bitstream='legacy image.bit', wall_seconds=None)
            path = folder / 'config.json'
            path.write_text(json.dumps(source))
            config = common.read_config(path)
            self.assertEqual(config['bitstream'], str(folder / 'legacy image.bit'))
            self.assertEqual(config['deployment_profile'], 'legacy')
            for value in (None, 1, 7200, 86400):
                source['wall_seconds'] = value
                path.write_text(json.dumps(source))
                self.assertEqual(common.read_config(path)['wall_seconds'], value)
            del source['wall_seconds']
            path.write_text(json.dumps(source))
            self.assertIsNone(common.read_config(path)['wall_seconds'])
            for value in (0, -1, True, float('inf'), float('nan'), 86401, '7200'):
                source['wall_seconds'] = value
                path.write_text(json.dumps(source))
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'wall_seconds'):
                    common.read_config(path)
            source['wall_seconds'] = None
            source['deployment_profile'] = 'custom'
            path.write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError, 'deployment_profile'):
                common.read_config(path)
        for value in (None, 0, True, float('inf'), 601):
            with self.subTest(command_timeout=value), self.assertRaisesRegex(ValueError, 'command_timeout'):
                common.validate_timeouts(value)

    def test_dry_runs_do_not_bootstrap_or_launch_devices(self):
        for command in (['dry-run'], ['benchmark-kv128', '--dry-run']):
            output = io.StringIO()
            with mock.patch.object(scalellm, 'bootstrap') as boot, \
                 mock.patch.object(subprocess, 'run') as launch, contextlib.redirect_stdout(output):
                scalellm.main(command)
            report = json.loads(output.getvalue())
            self.assertFalse(report['device_opened'])
            self.assertEqual(report['deployment_profile']['name'], 'all-dsp')
            boot.assert_not_called()
            launch.assert_not_called()
            if command[0] == 'benchmark-kv128':
                self.assertEqual(report['execution_policy']['hardware_commands'], 8192)
                self.assertTrue(report['missing_prerequisites'])
                self.assertEqual(sum(r['max_new_tokens'] for r in report['requests']), 1784)
        with mock.patch.object(scalellm, 'bootstrap') as boot, self.assertRaisesRegex(ValueError, 'program-receipt'):
            scalellm.main(['benchmark-kv128'])
        boot.assert_not_called()
        with tempfile.TemporaryDirectory() as directory:
            absent = str(Path(directory) / 'absent receipt.json')
            with mock.patch.object(scalellm, 'bootstrap') as boot, self.assertRaises(FileNotFoundError):
                scalellm.main(['benchmark-kv128', '--dry-run', '--program-receipt', absent])
            boot.assert_not_called()

    @unittest.skipUnless(shutil.which('tclsh'), 'Tcl interpreter unavailable')
    def test_tcl_profile_parity_and_independent_hash_check(self):
        script = 'source {' + str(ROOT / 'deploy/final/program_common.tcl') + '}\n'
        for name, identity in common.PROFILES.items():
            script += 'puts [dict get [deployment_profile {' + name + '}] sha256]\n'
            self.assertEqual(common.profile_identity(name)['bit_bytes'], 80159263)
        optimized = ROOT / 'resource_optimization/hardware/bitstream/ScaleLLM_Final_Decode16_80MHz.bit'
        legacy = ROOT / 'bitstream/ScaleLLM_Final_Decode16_80MHz.bit'
        script += 'puts [verify_final_bit {' + str(optimized) + '}]\n'
        script += 'puts [verify_final_bit {' + str(legacy) + '} legacy]\n'
        script += 'puts [catch {verify_final_bit {' + str(legacy) + '}}]\n'
        script += 'puts [catch {deployment_profile custom}]\n'
        result = subprocess.run(['tclsh'], input=script, capture_output=True, text=True, check=True)
        lines = result.stdout.splitlines()
        self.assertFalse(result.stderr)
        self.assertEqual(lines[:2], [identity['bit_sha256'] for identity in common.PROFILES.values()])
        self.assertEqual(lines[2:4], [str(optimized), str(legacy)])
        self.assertEqual(lines[4:], ['1', '1'])

    @unittest.skipUnless(shutil.which('tclsh'), 'Tcl interpreter unavailable')
    def test_tcl_certutil_parses_the_digest_line(self):
        digest = common.BIT_SHA
        bit = ROOT / 'resource_optimization/hardware/bitstream/ScaleLLM_Final_Decode16_80MHz.bit'
        script = 'source {' + str(ROOT / 'deploy/final/program_common.tcl') + '}\n'
        script += 'set ::tcl_platform(platform) windows\nrename exec original_exec\n'
        script += 'proc exec {args} {return $::hash_output}\n'
        script += 'set ::hash_output {SHA256 hash of ' + digest + '.bit:\n' + '0' * 64 + '\ncomplete}\n'
        script += 'puts [catch {verify_final_bit {' + str(bit) + '}}]\n'
        spaced = ' '.join(digest[index:index + 2].upper() for index in range(0, 64, 2))
        script += 'set ::hash_output {SHA256 hash of image.bit:\n' + spaced + '\ncomplete}\n'
        script += 'puts [verify_final_bit {' + str(bit) + '}]\n'
        result = subprocess.run(['tclsh'], input=script, capture_output=True, text=True, check=True)
        self.assertFalse(result.stderr)
        self.assertEqual(result.stdout.splitlines(), ['1', str(bit)])

    def test_program_receipt_records_native_success_and_failure(self):
        for returncode in (0, 7):
            with self.subTest(returncode=returncode), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'program.json'
                result = subprocess.CompletedProcess([], returncode, 'Vivado v2022.2\n', 'tool diagnostics')
                output = io.StringIO()
                with mock.patch.object(subprocess, 'run', return_value=result), contextlib.redirect_stdout(output):
                    arguments = ['program', '--vivado', 'Vivado path', '--server', 'localhost:3121',
                                 '--target', 'exact target', '--device', 'xcvu9p_0', '--receipt', str(path)]
                    if returncode:
                        with self.assertRaises(subprocess.CalledProcessError):
                            scalellm.main(arguments)
                    else:
                        scalellm.main(arguments)
                receipt = json.loads(path.read_text())
                self.assertEqual(receipt['returncode'], returncode)
                self.assertEqual(receipt['execution'], 'FAIL' if returncode else 'COMPLETE')
                self.assertEqual(receipt['deployment_profile'], common.profile_identity())
                self.assertEqual(receipt['tool']['version_output'], ['Vivado v2022.2'])
                self.assertGreaterEqual(receipt['finished_unix'], receipt['started_unix'])
                if returncode:
                    with self.assertRaises(ValueError):
                        common.read_program_receipt(path)
                else:
                    self.assertEqual(common.read_program_receipt(path)['receipt'], receipt)
                    with self.assertRaises(ValueError):
                        common.read_program_receipt(path, 'legacy')

    def test_explicit_wall_limit_is_forwarded(self):
        from final import preflight
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            config = json.loads((ROOT / 'deploy/config.example.json').read_text())
            config['wall_seconds'] = 86400
            config['bitstream'] = str(ROOT / 'resource_optimization/hardware/bitstream/ScaleLLM_Final_Decode16_80MHz.bit')
            path.write_text(json.dumps(config))
            with mock.patch.object(preflight, 'preflight'), mock.patch.object(preflight, 'driver_identity'), \
                 mock.patch.object(run, 'main') as launch:
                scalellm.main(['--config', str(path), 'run', '--result', str(Path(directory) / 'result')])
            arguments = launch.call_args.args[0]
            self.assertEqual(arguments[arguments.index('--wall-seconds') + 1], '86400')


class ExecutionPolicyTests(unittest.TestCase):
    def test_normal_request_contract_and_eos_retirement(self):
        runtime = execution.create_runtime(Backend(), Model(), Assets(), [1000])
        execution.allocate_requests(runtime, [dict(slot=0, prompt_token_ids=[10], max_new_tokens=32)])
        runtime.step()
        self.assertTrue(runtime.slots[0].finished)
        self.assertEqual(runtime.slots[0].generated, [1000])
        with self.assertRaisesRegex(ValueError, '1..32'):
            execution.allocate_requests(runtime, execution.benchmark_requests())
        with self.assertRaisesRegex(ValueError, 'policy'):
            execution.create_runtime(Backend(), Model(), Assets(), execution_policy='custom')

    def test_fixed128_full_commit_8192_commands_and_eos_observation(self):
        requests = execution.benchmark_requests()
        runtime = execution.create_runtime(Backend(), Model(), Assets(), [1000],
                                           execution_policy=execution.BENCHMARK_KV128)
        execution.allocate_requests(runtime, requests, execution_policy=execution.BENCHMARK_KV128)
        steps = []
        for index in range(128):
            positions = [state.position for state in runtime.slots]
            mask = sum(int(not state.finished) << slot for slot, state in enumerate(runtime.slots))
            emitted = runtime.step()
            steps.append(dict(index=index, active_mask=mask, positions_before=positions,
                              slots=[dataclasses.asdict(state) for state in runtime.slots]))
            if index == 126:
                self.assertTrue(all(not state.finished and state.position == 127 for state in runtime.slots))
                self.assertTrue(all(len(state.generated) == state.max_new_tokens - 1 for state in runtime.slots))
        self.assertEqual(set(emitted), set(range(16)))
        self.assertTrue(all(state.finished and state.position == 128 for state in runtime.slots))
        self.assertEqual(len(runtime.backend.receipts), 8192)
        self.assertEqual(runtime.command_id, 8192)
        report = dict(requests=requests, steps=steps, receipts=runtime.backend.receipts,
                      outputs={str(slot): state.generated for slot, state in enumerate(runtime.slots)},
                      numerical_verification='NOT_RUN')
        accepted = execution.validate_benchmark_report(report, [1000])
        self.assertEqual(accepted['verdict'], 'PASS')
        self.assertEqual(accepted['first_eos_by_slot']['0']['generated_index_one_based'], 1)
        self.assertEqual(sum(accepted['generated_token_counts'].values()), 1784)
        self.assertEqual(runtime.step(), {})
        self.assertEqual(len(runtime.backend.receipts), 8192)
        report['receipts'][-1]['active_mask'] = 0x7fff
        with self.assertRaisesRegex(ValueError, 'command identity'):
            execution.validate_benchmark_report(report)

    def test_fixed128_final_command_failure_preserves_position127(self):
        runtime = execution.create_runtime(Backend(), Model(), Assets(), [1000],
                                           execution_policy=execution.BENCHMARK_KV128)
        execution.allocate_requests(runtime, execution.benchmark_requests(),
                                    execution_policy=execution.BENCHMARK_KV128)
        for _ in range(127):
            runtime.step()
        before = copy.deepcopy(runtime.slots)
        runtime.backend.fail_command = 8192
        with self.assertRaisesRegex(RuntimeError, 'final command failure'):
            runtime.step()
        self.assertEqual(runtime.slots, before)
        self.assertEqual(len(runtime.backend.receipts), 8191)
        self.assertTrue(runtime.step_pending)

    def test_benchmark_rejects_changed_prompts_budget_and_types(self):
        original = execution.benchmark_requests()
        for field, value in (('max_new_tokens', 128 - len(original[0]['prompt_token_ids'])),
                             ('prompt_token_ids', [1]), ('slot', False)):
            changed = copy.deepcopy(original)
            changed[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                execution.validate_execution_requests(changed, execution.BENCHMARK_KV128)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'requests.json'
            path.write_text(json.dumps(json.loads((ROOT / 'examples/requests16.json').read_text())))
            with self.assertRaisesRegex(ValueError, 'published original'):
                execution.benchmark_requests(path)
        with self.assertRaisesRegex(ValueError, 'callable'):
            execution.RunHooks(after_step=True)

    def run_with_fake_board(self, directory, hooks, wall=None, close_handles=True):
        folder = Path(directory)
        for name in ('artifacts.json', 'assets.json'):
            (folder / name).write_text('{}')
        requests = folder / 'requests.json'
        requests.write_text(json.dumps([dict(slot=0, prompt_token_ids=[10], max_new_tokens=2)]))
        class Session:
            def __init__(self, **kwargs):
                self.handles = {'fake': True}
                self.quarantine = []
            def __enter__(self):
                return self
            def __exit__(self, *args):
                if close_handles:
                    self.handles.clear()
            def read32(self, address):
                return 0
        class Guard:
            def __init__(self, **kwargs):
                pass
            def __call__(self):
                return {}
            def summary(self):
                return {}
        assets = types.SimpleNamespace(manifest={'checkpoint_sha256': common.CHECKPOINT_SHA},
                                      config={'eos_token_id': [1000]}, generation_config={'eos_token_id': [1000]},
                                      file=lambda name: folder / name)
        artifacts = types.SimpleNamespace(original=types.SimpleNamespace(checkpoint_sha256=common.CHECKPOINT_SHA))
        arguments = ['--artifacts', str(folder / 'artifacts.json'), '--assets', str(folder / 'assets.json'),
                     '--requests', str(requests), '--result', str(folder / 'result')]
        if wall is not None:
            arguments.extend(['--wall-seconds', str(wall)])
        from final import preflight
        import host_math
        import resource_guard
        import scalellm_windows_xdma
        import host.scalellm_final_assets as asset_module
        from host.scalellm_mlp_gu_only_artifacts import GuOnlyArtifactManifest
        import tokenizers
        with mock.patch.object(run, 'os', types.SimpleNamespace(name='nt', environ=os.environ)), \
             mock.patch.object(run, 'cpu_budget', return_value={}), \
             mock.patch.object(preflight, 'driver_identity', return_value={}), \
             mock.patch.object(host_math, 'HostAssets', return_value=assets), \
             mock.patch.object(GuOnlyArtifactManifest, 'load', return_value=artifacts), \
             mock.patch.object(scalellm_windows_xdma, 'WindowsXdmaSession', Session), \
             mock.patch.object(resource_guard, 'ResourceGuard', Guard), \
             mock.patch.object(asset_module, 'FinalAssetStore', Assets), \
             mock.patch.object(asset_module, 'FinalHostAssetsModel', return_value=object()), \
             mock.patch.object(runtime_module, 'FinalBoardBackend', Backend), \
             mock.patch.object(runtime_module, 'HostModelAdapter', Model), \
             mock.patch.object(tokenizers.Tokenizer, 'from_file', return_value=types.SimpleNamespace(decode=lambda *a, **kw: 'fake')), \
             contextlib.redirect_stdout(io.StringIO()):
            return run.main(arguments, config=common.read_config(ROOT / 'deploy/config.example.json'), hooks=hooks)

    def test_runner_hooks_and_disabled_wall_limit(self):
        calls = []
        hooks = execution.RunHooks(before_command=lambda backend, descriptor, payload: calls.append(('before', descriptor.command_id)),
                                   after_command=lambda backend, descriptor, payload, output: calls.append(('after', descriptor.command_id)),
                                   before_step=lambda runtime, index: calls.append(('step_begin', index)),
                                   after_step=lambda runtime, index, emitted: calls.append(('step_commit', index)),
                                   finalize=lambda report: calls.append(('finalize', report['handles_closed'])))
        with tempfile.TemporaryDirectory() as directory:
            report = self.run_with_fake_board(directory, hooks)
        self.assertEqual(report['execution'], 'COMPLETE')
        self.assertIsNone(report['wall_limit_seconds'])
        self.assertEqual(report['deployment_acceptance'], 'IMAGE_PROVENANCE_UNVERIFIED')
        self.assertEqual(calls[:3], [('step_begin', 0), ('before', 1), ('after', 1)])
        self.assertEqual(calls[-2:], [('step_commit', 0), ('finalize', True)])

    def test_after_step_and_finalize_failure_save_fail_after_close(self):
        def fail(*args):
            raise RuntimeError('injected capture failure')
        for hook in ('after_step', 'finalize'):
            with self.subTest(hook=hook), tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(RuntimeError, 'injected capture failure'):
                    self.run_with_fake_board(directory, execution.RunHooks(**{hook: fail}))
                report = json.loads((Path(directory) / 'result/run.json').read_text())
                self.assertEqual(report['execution'], 'FAIL')
                self.assertEqual(report['deployment_acceptance'], 'FAIL')
                self.assertTrue(report['handles_closed'])
                self.assertEqual(report['steps'][0]['slots'][0]['position'], 1)

    def test_explicit_wall_limit_still_terminates(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(TimeoutError, 'wall limit'):
                self.run_with_fake_board(directory, execution.RunHooks(), wall=1e-12)
            report = json.loads((Path(directory) / 'result/run.json').read_text())
            self.assertEqual(report['execution'], 'FAIL')
            self.assertTrue(report['handles_closed'])
            self.assertEqual(report['receipts'], [])

    def test_native_handle_close_failure_saves_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, 'Native device handles'):
                self.run_with_fake_board(directory, execution.RunHooks(), close_handles=False)
            report = json.loads((Path(directory) / 'result/run.json').read_text())
            self.assertEqual(report['execution'], 'FAIL')
            self.assertEqual(report['deployment_acceptance'], 'FAIL')
            self.assertFalse(report['handles_closed'])

    def test_output_write_failure_saves_fail_after_close(self):
        write_text = Path.write_text
        def fail_output(path, *args, **kwargs):
            if path.name == 'outputs.txt':
                raise OSError('injected output write failure')
            return write_text(path, *args, **kwargs)
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(Path, 'write_text', fail_output), self.assertRaisesRegex(OSError, 'output write failure'):
                self.run_with_fake_board(directory, execution.RunHooks())
            report = json.loads((Path(directory) / 'result/run.json').read_text())
            self.assertEqual(report['execution'], 'FAIL')
            self.assertEqual(report['deployment_acceptance'], 'FAIL')
            self.assertTrue(report['handles_closed'])


if __name__ == '__main__':
    unittest.main()
