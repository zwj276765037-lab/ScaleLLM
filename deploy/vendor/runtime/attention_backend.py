"""Real Attention ABI2 transactions on the owner's existing XDMA session.

No model arithmetic or device-session creation occurs here. A command's full
output and independent gold must be durable and equal before its sticky DONE
is identity-checked again and cleared. The first failure permanently poisons
this instance and retains its pending identity; there is no reset/retry path.
"""
import hashlib
import time

PAYLOAD = 196608
CHUNK = 1 << 20
STAGED = {
    'attention_c0': (20971520, 0),
    'attention_c1': (20971520, 0x01400000),
    'attention_meta': (2621440, 0x56800000),
}
ROPE_BASE = 0x57000000
ROPE_BYTES = 8192
SNAPSHOT = (0x00c, 0x038, 0x03c, 0x040, 0x044, 0x048, 0x04c,
            0x050, 0x054, 0x058, 0x05c, 0x060, 0x064, 0x068, 0x06c,
            0x078, 0x07c, 0x080, 0x084, 0x088)
# Epoch-active is intentionally absent: an acknowledged first GU cohort may
# retain its epoch while the second cohort's Attention runs on DDR0.
GUARDS = {0x000: 0x48384103, 0x004: 0x00020000,
          0x100: 0x48384605, 0x104: 0x00070000,
          0x2b8: 0x4d303032, 0x300: 0x4d4c0002, 0x304: 0x1d,
          0x308: 1, 0x10c: 0x7b, 0x260: 0x23, 0x324: 8,
          0x350: 0, 0x370: 0, 0x178: 0, 0x2a8: 0}


def sha(data):
    return hashlib.sha256(data).hexdigest()


class AttentionBackend:
    def __init__(self, session, artifacts, reference_for_layer, evidence, trace,
                 resource_guard=lambda: None, *, poll_s=.001, wait_s=10):
        if poll_s != .001 or not 0 < wait_s <= 10:
            raise ValueError('Attention requires1ms polling and a bounded wait<=10s')
        self.session = session
        self.artifacts = artifacts
        self.reference_for_layer = reference_for_layer
        self.evidence = evidence
        self.trace = trace
        self.resource_guard = resource_guard
        self.poll_s, self.wait_s = poll_s, wait_s
        self.pending = None
        self.failed = None
        self.copied = False
        self.command_count = 0
        self.completed_commands = set()
        self.staged_layer = None
        self.staging_record = None
        self.rope_staged = False
        self.rope_bytes = None
        self.successful_seen = False

    def snapshot(self):
        return {'0x%03x' % address: self.session.read32(address)
                for address in SNAPSHOT}

    def idle_guard(self):
        values = {address: self.session.read32(address) for address in GUARDS}
        status, error = self.session.read32(0x00c), self.session.read32(0x04c)
        if values != GUARDS or status & 0x27 or error:
            raise RuntimeError('Attention/global idle dependency mismatch: ' + repr((values, status, error)))
        if self.successful_seen and status & 0x18 != 0x18:
            raise RuntimeError('Previously resident Attention metadata/RoPE disappeared')
        return status

    @staticmethod
    def completion_guard(snapshot, command, request, cohort, buffer, layer):
        expected = {'0x078': request, '0x07c': command,
                    '0x080': (buffer << 16) | cohort,
                    '0x084': layer, '0x088': buffer}
        if not snapshot['0x00c'] & 2 or snapshot['0x00c'] & 5 or snapshot['0x04c']:
            raise RuntimeError('Attention completion is not successful: ' + repr(snapshot))
        if any(snapshot[address] != value for address, value in expected.items()):
            raise RuntimeError('Attention completed identity mismatch')
        if tuple(snapshot['0x%03x' % address] for address in (0x03c, 0x040, 0x044, 0x048)) != (81920, 640, 512, 256):
            raise RuntimeError('Attention completed work-count mismatch')
        if sum(snapshot['0x%03x' % address] for address in range(0x050, 0x070, 4)) != snapshot['0x038']:
            raise RuntimeError('Attention phase sum differs from compute counter')
        if snapshot['0x00c'] & 0x18 != 0x18:
            raise RuntimeError('Attention completion lost loaded metadata/RoPE')

    def _stage(self, layer, job_dir):
        records, identities = [], {}
        reload_metadata = layer != self.staged_layer
        for name, (size, address) in STAGED.items():
            artifact = self.artifacts.original.layer_artifact(layer, name)
            identities[name] = artifact.sha256
            if not reload_metadata:
                continue
            self.resource_guard()
            payload = artifact.read_verified()
            if len(payload) != size:
                raise ValueError('Attention weight artifact shape mismatch: ' + name)
            self.session.h2c_write_local(0, payload, address, CHUNK)
            actual = self.session.c2h_read_local(0, size, address, CHUNK)
            records.append({'artifact': name, 'ddr_channel': 0,
                            'local_offset': address, 'bytes': len(actual),
                            'expected_sha256': artifact.sha256,
                            'actual_sha256': sha(actual)})
            if actual != payload:
                self.evidence.write_json(job_dir + '/staging_failed.json', records)
                raise RuntimeError('Attention DDR0 readback mismatch: ' + name)
        reload_rope = not self.rope_staged
        rope_record = self.artifacts.original.rope
        if reload_rope:
            self.resource_guard()
            self.rope_bytes = rope_record.read_verified()
            if len(self.rope_bytes) != ROPE_BYTES:
                raise ValueError('Attention real RoPE artifact must be8192B')
            self.session.h2c_write_local(0, self.rope_bytes, ROPE_BASE, CHUNK)
            actual = self.session.c2h_read_local(0, ROPE_BYTES, ROPE_BASE, CHUNK)
            records.append({'artifact': 'rope', 'ddr_channel': 0,
                            'local_offset': ROPE_BASE, 'bytes': len(actual),
                            'expected_sha256': rope_record.sha256, 'actual_sha256': sha(actual)})
            if actual != self.rope_bytes:
                self.evidence.write_json(job_dir + '/staging_failed.json', records)
                raise RuntimeError('Attention DDR0 real RoPE readback mismatch')
            self.rope_staged = True
        elif sha(self.rope_bytes) != rope_record.sha256:
            raise RuntimeError('Attention real RoPE identity changed')
        if records:
            self.staging_record = self.evidence.write_json(job_dir + '/staging.json', records)
        if reload_metadata:
            self.staged_layer = layer
        return identities, reload_metadata, reload_rope

    def run(self, cohort, layer, input_s24, command_id, request_id, job_dir):
        if self.failed is not None or self.pending is not None:
            raise RuntimeError('Attention owner is poisoned or already pending')
        if type(cohort) is not int or cohort not in (0, 1) or type(layer) is not int or not 0 <= layer < 32:
            raise ValueError('Attention cohort/layer mismatch')
        if any(type(value) is not int or not 0 < value < 2**32 for value in (command_id, request_id)) or command_id in self.completed_commands:
            raise ValueError('Attention command/request identity is invalid or reused')
        input_s24 = bytes(input_s24)
        if len(input_s24) != PAYLOAD:
            raise ValueError('Attention input must be full16x4096 S24')
        job_dir = str(job_dir).replace('\\', '/').rstrip('/')
        buffer = cohort * 3
        input_base, output_base = 0x56000000 + buffer * 0x100000, 0x56080000 + buffer * 0x100000
        record = {'command_id': command_id, 'request_id': request_id,
                  'cohort': cohort, 'layer': layer, 'buffer_id': buffer,
                  'query_start': 0, 'query_count': 16, 'valid_key_count': 16,
                  'preserve_historical_kv': False, 'comparison': 'NOT_RUN',
                  'sticky_cleared': False, 'started': False, 'copied': False,
                  'input_base': input_base, 'output_base': output_base}
        self.pending, self.copied = dict(record), False
        try:
            self.resource_guard()
            self.idle_guard()
            weights, reload_metadata, reload_rope = self._stage(layer, job_dir)
            record.update(weights_sha256=weights, rope_sha256=sha(self.rope_bytes),
                          reload_metadata=reload_metadata, reload_rope=reload_rope,
                          staging=self.staging_record)
            stored = self.evidence.write_bytes(job_dir + '/input_s24.bin', input_s24)
            record.update(input_path=stored['path'], input_sha256=stored['sha256'])
            self.resource_guard()
            gold, audit = self.reference_for_layer(layer).attention(input_s24, self.rope_bytes)
            gold = bytes(gold)
            if len(gold) != PAYLOAD:
                raise ValueError('Independent Attention gold has wrong shape')
            stored = self.evidence.write_bytes(job_dir + '/gold_s24.bin', gold)
            record.update(gold_path=stored['path'], gold_sha256=stored['sha256'])
            record['gold_audit'] = self.evidence.write_json(job_dir + '/gold_audit.json', audit)
            self.resource_guard()
            self.idle_guard()
            self.session.h2c_write_local(0, input_s24, input_base, CHUNK)
            actual_input = self.session.c2h_read_local(0, PAYLOAD, input_base, CHUNK)
            record['input_readback_sha256'] = sha(actual_input)
            if actual_input != input_s24:
                self.evidence.write_bytes(job_dir + '/input_readback_failed.bin', actual_input)
                raise RuntimeError('Attention input DDR0 readback mismatch')
            config = ((0x010, command_id), (0x014, layer), (0x018, 0x00101000),
                      (0x01c, 0x48384103), (0x020, input_base), (0x024, output_base),
                      (0x028, 0), (0x02c, 0x01400000), (0x030, 0x56800000),
                      (0x034, ROPE_BASE), (0x070, request_id), (0x074, (buffer << 16) | cohort))
            for address, value in config:
                self.session.write32(address, value)
            self.evidence.write_json(job_dir + '/descriptor.json', {'0x%03x' % a: v for a, v in config})
            self.resource_guard()
            self.idle_guard()
            self.evidence.journal('attention.before_start', record)
            record['start_before_monotonic_s'] = time.perf_counter()
            self.pending.update(record)
            # Pending is established before the irreversible START write.
            self.session.write32(0x008, 1 | (4 if reload_metadata else 0) | (8 if reload_rope else 0))
            record['started'] = True
            self.pending['started'] = True
            deadline = time.perf_counter() + self.wait_s
            polls = 0
            while True:
                status = self.session.read32(0x00c)
                polls += 1
                if status & 6:
                    break
                if time.perf_counter() >= deadline:
                    raise TimeoutError('Attention wait expired; retained pending, no clear/reset/retry')
                time.sleep(self.poll_s)
            record['done_observed_monotonic_s'], record['polls'] = time.perf_counter(), polls
            snapshot = self.snapshot()
            stored = self.evidence.write_json(job_dir + '/done.json', snapshot)
            record['done_path'] = stored['path']
            self.completion_guard(snapshot, command_id, request_id, cohort, buffer, layer)
            self.resource_guard()
            output = self.session.c2h_read_local(0, PAYLOAD, output_base, CHUNK)
            self.copied = True
            record['copied'] = True
            stored = self.evidence.write_bytes(job_dir + '/output_s24.bin', output)
            record.update(output_path=stored['path'], output_sha256=stored['sha256'],
                          copied_bytes=len(output), comparison='PASS' if output == gold else 'FAIL')
            self.evidence.write_json(job_dir + '/copied_comparison.json', record)
            self.evidence.journal('attention.copied_and_compared', record)
            if output != gold:
                if len(output) == len(gold):
                    record['first_mismatch_byte'] = next(i for i, (a, b) in enumerate(zip(output, gold)) if a != b)
                raise AssertionError('Attention actual full output differs from independent gold')
            recheck = self.snapshot()
            self.evidence.write_json(job_dir + '/done_recheck.json', recheck)
            self.completion_guard(recheck, command_id, request_id, cohort, buffer, layer)
            if recheck != snapshot:
                raise RuntimeError('Attention DONE changed before legacy sticky clear')
            self.evidence.journal('attention.before_sticky_clear', record)
            if self.trace is not None:
                self.trace.record('before', 'owner.attention_sticky_clear', {'command': command_id, 'identity_rechecked': True, 'full_gold_pass': True})
            self.session.write32(0x008, 2)
            deadline = time.perf_counter() + self.wait_s
            while self.session.read32(0x00c) & 0x27:
                if time.perf_counter() >= deadline:
                    raise TimeoutError('Attention sticky clear did not retire; no retry')
                time.sleep(self.poll_s)
            self.idle_guard()
            self.successful_seen = True
            record['sticky_cleared'] = True
            self.evidence.write_json(job_dir + '/completed.json', record)
            self.evidence.journal('attention.completed', record)
            if self.trace is not None:
                self.trace.record('after', 'owner.attention_sticky_clear', {'command': command_id})
            self.completed_commands.add(command_id)
            self.command_count += 1
            self.pending = None
            return output, record
        except BaseException as error:
            self.failed = repr(error)
            record['error'] = self.failed
            self.pending.update(record)
            try:
                self.evidence.write_json(job_dir + '/failed.json', record)
                self.evidence.journal('attention.failed', record)
            except BaseException:
                pass  # Keep the original failure and retained identity.
            raise
