"""CPU-only final deployment checks. No driver or FPGA is opened."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'deploy'))
import scalellm
from final import common, preflight
from final.prepare_chat_requests import prepare
import export_model
common.bootstrap()


class DeploymentTests(unittest.TestCase):
    def test_final_config_and_requests(self):
        config = common.read_config(ROOT / 'deploy/config.example.json')
        requests = common.read_requests(config['requests'])
        self.assertEqual(len(requests), 16)
        self.assertEqual({row['max_new_tokens'] for row in requests}, {32})
        self.assertEqual(max(len(row['prompt_token_ids']) for row in requests), 19)
        self.assertEqual(Path(config['bitstream']).name, 'ScaleLLM_Final_Decode16_80MHz.bit')
        with tempfile.TemporaryDirectory(prefix='final config with spaces ') as folder:
            path = Path(folder) / 'config.json'
            source = json.loads((ROOT / 'deploy/config.example.json').read_text())
            source['output_dir'] = '${SCALELLM_TEST_OUTPUT}/out'
            path.write_text(json.dumps(source))
            with mock.patch.dict(os.environ, SCALELLM_TEST_OUTPUT=folder):
                self.assertEqual(common.read_config(path)['output_dir'], str(Path(folder) / 'out'))
            source['schema'] = 'scalellm_deploy_v1'
            path.write_text(json.dumps(source))
            with self.assertRaises(ValueError):
                common.read_config(path)

    def test_remaining_rounds_include_unconsumed_prompt(self):
        from final.run import remaining_full_rounds
        from host.scalellm_final_runtime import RequestSlot
        slot = RequestSlot(epoch=1, prompt=(10,) * 19, max_new_tokens=32, finished=False)
        self.assertEqual(remaining_full_rounds([slot]), 50)
        slot.position = 18
        self.assertEqual(remaining_full_rounds([slot]), 32)
        slot.position = 19
        slot.generated = [100]
        self.assertEqual(remaining_full_rounds([slot]), 31)
        slot.finished = True
        self.assertEqual(remaining_full_rounds([slot]), 0)

    def test_request_rejection_before_device(self):
        original = json.loads((ROOT / 'examples/requests16.json').read_text())
        for change in ('duplicate', 'boolean_slot', 'vocabulary', 'context', 'budget', 'extra'):
            requests = copy.deepcopy(original)
            if change == 'duplicate': requests[1]['slot'] = requests[0]['slot']
            if change == 'boolean_slot': requests[0]['slot'] = True
            if change == 'vocabulary': requests[0]['prompt_token_ids'] = [128256]
            if change == 'context': requests[0]['prompt_token_ids'] = [1] * 97
            if change == 'budget': requests[0]['max_new_tokens'] = 33
            if change == 'extra': requests[0]['ignore_eos'] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                common.validate_requests(requests)

    def test_identity_before_import(self):
        with mock.patch.object(preflight, 'source_check', side_effect=ValueError('bad source')), \
             mock.patch.object(preflight, 'bootstrap') as boot:
            with self.assertRaisesRegex(ValueError, 'bad source'):
                preflight.preflight({})
            boot.assert_not_called()

    def test_read_only_final_abi_and_old_clock_rejection(self):
        from host.scalellm_final_abi import CSR, IDS
        values = {CSR[key.upper()]: value for key, value in IDS.items()}
        class Fake:
            def read32(self, address): return values.get(address, 0)
            def write32(self, *args): raise AssertionError('Read-only preflight wrote a CSR')
        snapshot = preflight.inspect_device(Fake())
        self.assertEqual(snapshot['CORE_HZ'], 80000000)
        values[CSR['CORE_HZ']] = 100000000
        with self.assertRaisesRegex(RuntimeError, 'CORE_HZ'):
            preflight.inspect_device(Fake())

    def test_program_plan_preserves_arguments(self):
        output = io.StringIO()
        with mock.patch.object(scalellm, 'check_bit', return_value=Path('/tmp/final image.bit')), \
             mock.patch.object(subprocess, 'run') as launch, contextlib.redirect_stdout(output):
            scalellm.main(['program', '--vivado', 'C:/AMD tools/vivado.bat', '--server', 'localhost:3121',
                           '--target', 'target with spaces', '--device', 'xcvu9p_0', '--dry-run'])
        command = json.loads(output.getvalue())['command']
        self.assertIn('target with spaces', command)
        self.assertEqual(command[-1], '/tmp/final image.bit')
        launch.assert_not_called()

    def test_run_dispatch_with_external_power_log(self):
        with mock.patch.object(preflight, 'preflight'), mock.patch.object(preflight, 'driver_identity'), \
             mock.patch.object(scalellm, 'check_bit'), mock.patch('final.run.main') as run:
            scalellm.main(['run', '--requests', str(ROOT / 'examples/requests16.json'),
                           '--result', '/tmp/final output', '--power-log', '/tmp/sampler log.csv'])
        arguments = run.call_args.args[0]
        self.assertEqual(arguments[arguments.index('--result') + 1], '/tmp/final output')
        self.assertEqual(arguments[arguments.index('--power-log') + 1], '/tmp/sampler log.csv')
        self.assertEqual(run.call_args.kwargs['config']['wall_seconds'], 7200)

    def test_bounded_exact_bf16_conversion(self):
        import numpy as np
        original = export_model.load()
        with tempfile.TemporaryDirectory(prefix='BF16 export ') as folder:
            root = Path(folder)
            bits = np.array([0, 0x3f80, 0xbf80, 0x4000, 0x3e80, 0xc100, 0x3fc0, 0x80,
                             0x3f00, 0xbf00, 0x4040, 0x4080, 0x3e00, 0xbe00, 0x4100], dtype='<u2').reshape(5, 3)
            header = json.dumps({'weight': {'dtype': 'BF16', 'shape': [5, 3],
                                           'data_offsets': [0, bits.nbytes]}}).encode()
            source = root / 'source.safetensors'
            source.write_bytes(struct.pack('<Q', len(header)) + header + bits.tobytes())
            reader = original.SafeTensorNumpy(source)
            calls = []
            class Checkpoint:
                def float32(self, name, rows):
                    calls.append((rows.start, rows.stop))
                    return reader.float32(name, rows=rows)
            target = root / 'out.f32'
            export_model.stream_fp32_matrix(Checkpoint(), 'weight', target, 5, 3, 2)
            self.assertEqual(calls, [(0, 2), (2, 4), (4, 5)])
            np.testing.assert_array_equal(np.fromfile(target, dtype='<u4').reshape(5, 3), bits.astype('<u4') << 16)
            with self.assertRaises(FileExistsError):
                export_model.stream_fp32_matrix(Checkpoint(), 'weight', target, 5, 3, 2)

    def test_chunked_lm_head_ties(self):
        import numpy as np
        from host.scalellm_final_lm_head import streaming_lm_head
        hidden = np.array([[1, 2], [-1, 1]], dtype=np.float32)
        weights = np.array([[1, 1], [2, 2], [2, 2], [1, -1], [-1, 1]], dtype=np.float32)
        result = streaming_lm_head(hidden, [1, 4], 5, lambda a, b: weights[a:b], 2, 1)
        self.assertEqual(result['top_token_ids'], [[1], [4]])
        self.assertEqual(result['top_logits'], [[6.0], [2.0]])
        self.assertEqual(result['target_logits'], [6.0, 2.0])

    def test_synthetic_chat_fixture_and_hash_rejection(self):
        # This small tokenizer is test data, not a model tokenizer or board result.
        from tokenizers import Tokenizer, AddedToken
        from tokenizers.models import WordLevel
        from tokenizers.pre_tokenizers import Whitespace
        with tempfile.TemporaryDirectory(prefix='chat fixture with spaces ') as folder:
            root = Path(folder)
            tokenizer = Tokenizer(WordLevel({'<BOS>': 0, '<UNK>': 1, 'hello': 2}, unk_token='<UNK>'))
            tokenizer.pre_tokenizer = Whitespace()
            tokenizer.add_special_tokens([AddedToken('<BOS>', special=True)])
            tokenizer.save(str(root / 'tokenizer.json'))
            template = "{{bos_token}}<|start_header_id|>user<|end_header_id|>\n\n{{messages[0].content}}<|eot_id|>{{ '<|start_header_id|>assistant<|end_header_id|>\n\n' }}"
            payloads = {'config': {'bos_token_id': 0, 'eos_token_id': [1]},
                        'generation_config': {'eos_token_id': [1]},
                        'tokenizer_config': {'bos_token': '<BOS>', 'eos_token': '<UNK>', 'chat_template': template}}
            for name, value in payloads.items():
                (root / (name + '.json')).write_text(json.dumps(value))
            manifest = dict(schema='scalellm_llama31_host_assets_v1', state='COMPLETE',
                            checkpoint_sha256=common.CHECKPOINT_SHA,
                            model_id='meta-llama/Llama-3.1-8B-Instruct', files={})
            for name in (*payloads, 'tokenizer'):
                path = root / (name + '.json')
                manifest['files'][name] = dict(path=path.name, size=path.stat().st_size, sha256=common.sha(path))
            assets = root / 'manifest.json'; assets.write_text(json.dumps(manifest))
            messages = root / 'messages.json'
            messages.write_text(json.dumps([dict(slot=0, messages=[dict(role='user', content='hello')], max_new_tokens=32)]))
            result = prepare(assets, messages, root / 'prepared')
            self.assertEqual(result['count'], 1)
            request = common.read_requests(result['requests'])[0]
            self.assertEqual(request['prompt_token_ids'][0], 0)
            self.assertEqual(request['prompt_token_ids'].count(0), 1)
            (root / 'tokenizer_config.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'differs'):
                prepare(assets, messages, root / 'tampered')

    def test_move_release_without_original_tree(self):
        with tempfile.TemporaryDirectory(prefix='moved release ') as folder:
            moved = Path(folder) / 'final release with spaces'
            manifest = json.loads((ROOT / 'deploy/vendor_manifest.json').read_text())
            for relative in (*manifest['files'], 'deploy/vendor_manifest.json'):
                source = ROOT / relative
                target = moved / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            for command in ('dry-run', 'preflight'):
                result = subprocess.run([sys.executable, str(moved / 'deploy/scalellm.py'), command],
                                        cwd=folder, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                report = json.loads(result.stdout)
                self.assertFalse(report['device_opened'])
                self.assertGreater(report['source_files_verified'], 20)
                if command == 'dry-run':
                    self.assertEqual(report['core_hz'], 80000000)
                    self.assertTrue(report['resolved_config']['artifacts'].startswith(str(moved)))
            (moved / 'deploy/vendor/runtime/host_math.py').write_text('tampered')
            result = subprocess.run([sys.executable, str(moved / 'deploy/scalellm.py'), 'preflight'],
                                    cwd=folder, capture_output=True, text=True, timeout=60)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('identity mismatch', result.stderr)


if __name__ == '__main__':
    unittest.main()
