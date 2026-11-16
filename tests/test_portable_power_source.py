"""Fresh-source integrity boundaries. Synthetic board state is never board evidence."""
import copy
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
POWER = ROOT / 'resource_optimization/deployment/power'
sys.path.insert(0, str(POWER))
import portable_source as source
from deploy.final.execution import benchmark_requests, policy_description, BENCHMARK_KV128
from host.scalellm_decode16 import DecodeRow
from host.scalellm_final_abi import FinalDescriptor


def write_json(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')


def file_entry(path):
    return dict(file=path.name, bytes=path.stat().st_size, sha256=source.sha_file(path))


class PortablePowerSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='portable power source ')
        cls.root = Path(cls.temporary.name)
        captures = cls.root / 'captures'
        captures.mkdir()
        requests = benchmark_requests()
        tokens = source.load(ROOT / next(iter(source.REFERENCES)))['slots']
        profile = source.profile_identity('all-dsp')
        policy = policy_description(BENCHMARK_KV128)
        run = dict(execution='COMPLETE', handles_closed=True, final_quiescent=True,
                   checkpoint_sha256=source.CHECKPOINT_SHA, deployment_profile=profile,
                   execution_policy=policy, bitstream_file=dict(sha256=source.BIT_SHA, bytes=80159263),
                   requests=requests, outputs={slot: row['generated_token_ids'] for slot, row in tokens.items()},
                   numerical_verification='TEST_FIXTURE', steps=[], receipts=[])
        run['programming_receipt']=dict(sha256='4'*64,receipt=dict(schema='scalellm_sram_program_receipt_v1',
            execution='COMPLETE',returncode=0,deployment_profile=profile,volatile_sram=True,
            host_identity=dict(hostname='synthetic-host',platform='win32',boot_id='2026-11-16T01:00:00.0000000Z',
                               boot_source='Win32_OperatingSystem.LastBootUpTime.UTC')))
        write_json(cls.root / 'requests.json', requests)
        run['requests_sha256'] = source.sha_file(cls.root / 'requests.json')
        for name in ('source_manifest_sha256', 'artifact_manifest_sha256', 'host_manifest_sha256'):
            run[name] = '1' * 64
        run['source_manifest_sha256'] = source.sha_file(ROOT / 'deploy/vendor_manifest.json')
        for index in range(128):
            states = []
            emitted = {}
            for slot, request in enumerate(requests):
                count = max(0, index + 2 - len(request['prompt_token_ids']))
                generated = tokens[str(slot)]['generated_token_ids'][:count]
                states.append(dict(epoch=1, prompt=request['prompt_token_ids'], max_new_tokens=request['max_new_tokens'],
                                   position=index + 1, generated=generated, finished=index == 127))
                if count:
                    emitted[str(slot)] = generated[-1]
            run['steps'].append(dict(index=index, active_mask=65535, positions_before=[index] * 16,
                                     slots=states, emitted=emitted))
        for name, size in (('input.bin',196608),('rope.bin',8192),('kv_before.bin',source.LAYER_BYTES),
                           ('kv_snapshot.bin',source.KV_BYTES)):
            with (captures / name).open('wb') as stream:
                stream.truncate(size)
        before, after = [], []
        with (cls.root / 'benchmark_commands.jsonl').open('w') as journal:
            for cid in range(1,8193):
                position, offset = divmod(cid - 1,64)
                descriptor = FinalDescriptor.create(cid, position, 1 + offset % 2, offset // 2,
                    tuple(DecodeRow(True,1,position) for _ in range(16)), cid, cid)
                receipt = dict(command_id=cid,layer=offset // 2,opcode=1 + offset % 2,active_mask=65535,cycles=1)
                run['receipts'].append(receipt)
                record = dict(command_id=cid, descriptor_words=list(descriptor.words()),
                              begin_monotonic_ns=cid * 2,completed_monotonic_ns=cid * 2 + 1,
                              completion_receipt=receipt,acknowledged=True,input_sha256='2'*64,output_sha256='3'*64)
                if cid in source.TARGET_IDS:
                    path = captures / f'cmd_{cid:04d}_descriptor.bin'
                    path.write_bytes(descriptor.pack())
                    files = dict(input=file_entry(captures / 'input.bin'),descriptor=file_entry(path))
                    if descriptor.opcode == 1:
                        files.update(kv_before=file_entry(captures / 'kv_before.bin'),rope=file_entry(captures / 'rope.bin'))
                    output = captures / f'cmd_{cid:04d}_output.bin'
                    shutil.copyfile(ROOT / f'resource_optimization/results/board/replay/cmd_{cid:04d}_output.bin',output)
                    before.append(dict(command_id=cid,round=position+1,layer=offset//2,opcode=descriptor.opcode,files=files))
                    after.append(dict(command_id=cid,output=file_entry(output),reference_match=True))
                    record.update(input_sha256=files['input']['sha256'],output_sha256=source.sha_file(output))
                journal.write(json.dumps(record)+'\n')
        snapshot = file_entry(captures / 'kv_snapshot.bin')
        cls.synthetic_snapshot_sha = snapshot['sha256']
        snapshot.update(generated_from_this_run=True,reference_match=True,
            layers=[dict(layer=layer,bytes=source.LAYER_BYTES,sha256=source.sha_file(captures/'kv_before.bin')) for layer in range(32)])
        capture = dict(schema='scalellm_portable_kv128_capture_v1',status='PASS',run_bitstream_sha256=source.BIT_SHA,
                       commands_completed=8192,native_runner_execution='COMPLETE',handles_closed=True,final_quiescent=True,
                       source_references={relative:dict(sha256=expected,bytes=(ROOT/relative).stat().st_size)
                                          for relative,expected in source.REFERENCES.items()},
                       targets_before=before,targets_after=after,host_before_last_step=run['steps'][126]['slots'],
                       host_after_last_step=run['steps'][127]['slots'],last_descriptor=record['descriptor_words'],
                       last_completion=run['receipts'][-1],snapshot=snapshot,
                       command_journal_sha256=source.sha_file(cls.root/'benchmark_commands.jsonl'))
        origin=dict(schema='scalellm_portable_kv128_source_v1',deployment_profile=profile,execution_policy=policy,
                    original_requests_sha256=source.ORIGINAL_REQUESTS_SHA,benchmark_requests_sha256=run['requests_sha256'],
                    **{name:run[name] for name in ('source_manifest_sha256','artifact_manifest_sha256','host_manifest_sha256')})
        cls.values={'run.json':run,'benchmark_capture.json':capture,'benchmark_source.json':origin}

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        for name,value in self.values.items():
            write_json(self.root/name,value)
        # Only the full-snapshot known digest is replaced for this synthetic
        # fixture. Real public token/operator identities remain fully checked.
        patch = mock.patch.object(source,'SNAPSHOT_SHA',self.synthetic_snapshot_sha)
        patch.start()
        self.addCleanup(patch.stop)

    def change(self,name,change):
        value=copy.deepcopy(self.values[name]);change(value);write_json(self.root/name,value)

    def test_complete_fresh_schema_passes_offline(self):
        with mock.patch.dict(sys.modules,{'scalellm_windows_xdma':None}), mock.patch(
                'deploy.final.common.current_host_identity',side_effect=AssertionError('offline host access')):
            result=source.verify_portable_source(self.root)
        self.assertEqual(result['capture']['run_bitstream_sha256'],source.BIT_SHA)
        self.assertEqual(result['capture']['schema'],'scalellm_portable_kv128_capture_v1')
        self.assertNotIn('receipt',result)
        self.assertEqual(len(result['targets']),12)

    def test_real_snapshot_pin_rejects_synthetic_image(self):
        with mock.patch.object(source,'SNAPSHOT_SHA','fa610d68fab6045573a355313f78808c93b7273dbf1edc2e8f61bc3ea1ad81c8'):
            with self.assertRaisesRegex(RuntimeError,'snapshot provenance'):
                source.verify_portable_source(self.root)

    def test_changed_host_token_or_bit_rejected(self):
        for name,change in (
            ('benchmark_capture.json',lambda c:c['host_before_last_step'][0]['generated'].__setitem__(0,1)),
            ('benchmark_source.json',lambda c:c['deployment_profile'].__setitem__('bit_sha256','0'*64)),
            ('run.json',lambda c:c['outputs']['0'].__setitem__(0,1)),
            ('run.json',lambda c:c.__setitem__('handles_closed',False)),
            ('run.json',lambda c:c['programming_receipt']['receipt'].__setitem__('host_identity',{}))):
            with self.subTest(name=name):
                self.setUp()
                self.change(name,change)
                with self.assertRaises((RuntimeError,ValueError)):
                    source.verify_portable_source(self.root)

    def test_matching_fake_capture_and_run_host_prefix_rejected(self):
        run=copy.deepcopy(self.values['run.json'])
        capture=copy.deepcopy(self.values['benchmark_capture.json'])
        run['steps'][126]['slots'][0]['generated'][0]=1
        capture['host_before_last_step']=run['steps'][126]['slots']
        write_json(self.root/'run.json',run)
        write_json(self.root/'benchmark_capture.json',capture)
        with self.assertRaisesRegex(RuntimeError,'host prompt/budget/token prefix'):
            source.verify_portable_source(self.root)

    def test_duplicate_target_and_traversal_rejected(self):
        self.change('benchmark_capture.json',lambda c:c['targets_before'].append(c['targets_before'][0]))
        with self.assertRaisesRegex(RuntimeError,'capture set'):
            source.verify_portable_source(self.root)
        self.setUp()
        self.change('benchmark_capture.json',lambda c:c['targets_before'][0]['files']['input'].__setitem__('file','../outside.bin'))
        with self.assertRaisesRegex(RuntimeError,'filename'):
            source.verify_portable_source(self.root)

    def test_missing_or_changed_journal_rejected(self):
        self.change('benchmark_capture.json',lambda c:c.__setitem__('command_journal_sha256','0'*64))
        with self.assertRaisesRegex(RuntimeError,'journal changed'):
            source.verify_portable_source(self.root)

    def test_self_consistent_journal_hash_cannot_hide_missing_ack(self):
        path=self.root/'benchmark_commands.jsonl'
        original=path.read_bytes()
        rows=original.splitlines()
        row=json.loads(rows[-1]);row['acknowledged']=False
        rows[-1]=json.dumps(row).encode()
        path.write_bytes(b'\n'.join(rows)+b'\n')
        try:
            self.change('benchmark_capture.json',lambda c:c.__setitem__('command_journal_sha256',source.sha_file(path)))
            with self.assertRaisesRegex(RuntimeError,'ordering/ACK'):
                source.verify_portable_source(self.root)
        finally:
            path.write_bytes(original)

    def test_snapshot_layer_hash_cannot_hide_behind_full_snapshot_hash(self):
        self.change('benchmark_capture.json',lambda c:c['snapshot']['layers'][31].__setitem__('sha256','0'*64))
        with self.assertRaisesRegex(RuntimeError,'snapshot layer hash'):
            source.verify_portable_source(self.root)

    def test_capture_bytes_rejected(self):
        path=self.root/'captures/input.bin'
        with path.open('r+b') as stream:stream.write(b'X')
        try:
            with self.assertRaisesRegex(RuntimeError,'capture bytes/identity'):
                source.verify_portable_source(self.root)
        finally:
            with path.open('r+b') as stream:stream.write(b'\0')

    def test_invalid_descriptor_reserved_word_rejected(self):
        words=copy.deepcopy(self.values['benchmark_capture.json']['last_descriptor'])
        words[20]=1
        with self.assertRaisesRegex(ValueError,'reserved'):
            source.descriptor_check(words,8192)

    def test_no_private_runtime_or_evidence_dependency(self):
        for path in POWER.glob('*'):
            if path.suffix in ('.py','.ps1'):
                text=path.read_text()
                for private in ('D:/ScaleLLM_final_model','C:/Users/dell','run_002','readonly_inspection_002'):
                    self.assertNotIn(private,text,path.name)


if __name__=='__main__':
    unittest.main()
