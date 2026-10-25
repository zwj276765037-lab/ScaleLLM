"""Independent CPU audit of recorded inference; never opens the FPGA.

The immutable run summary remains unchanged. A separate receipt binds its SHA,
the executed source snapshot, model manifests, and all numerical boundaries.
No prior prompt or baseline output is needed.
"""
import argparse
import datetime as dt
import gc
import hashlib
import json
import os
import platform
from pathlib import Path, PureWindowsPath
import time
import traceback

import numpy as np
from host_math import HostAssets, actual_requests, file_sha, stream_logits
from reference import ReferenceLayer, REFERENCE_SOURCES
from host.scalellm_hostops import rms_norm, pack_s24_q16, unpack_s24_q16
from host.scalellm_mlp_linear import prepare_gate_up_input_from_normalized_fp32
from host.scalellm_mlp_gu_only import prepare_down_arrays, down_blocked_int64
from host.scalellm_mlp_gu_only_artifacts import GuOnlyArtifactManifest

BIT_SHA = '66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def contained(root, name):
    require(isinstance(name, str) and name and '\\' not in name
            and not PureWindowsPath(name).drive and not Path(name).is_absolute()
            and '..' not in Path(name).parts, 'Unsafe evidence path')
    root = Path(root).resolve()
    path = (root / name).resolve(strict=True)
    require(path.is_relative_to(root) and path.is_file(), 'Evidence path escapes root')
    return path


def payload(root, record, role=None):
    prefix = '' if role is None else role + '_'
    path = contained(root, record[prefix + 'path'])
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == record[prefix + 'sha256'],
            'Recorded payload SHA mismatch: ' + str(path))
    return data


def coverage(summary):
    require(summary.get('schema') == 'scalellm_llama_host_fpga_run_v1', 'Unsupported run schema')
    require(summary['execution_state'] in ('completed', 'executed', 'EXECUTION_COMPLETE')
            and summary['first_error'] is None, 'Cannot certify an incomplete or failed run')
    require(summary.get('software_mode') in ('resident_interleaved_v1', 'resident_interleaved_post_ack_metadata_v2'),
            'Unsupported inference mode')
    pilot = summary['mode'] == 'pilot'
    require(pilot or summary['mode'] == 'full', 'Unknown run mode')
    layers = summary.get('pilot_layers', 1) if pilot else 32
    require(type(layers) is int and layers in ((1, 2) if pilot else (32,)), 'Invalid layer coverage')
    steps = summary['steps']
    require(1 <= len(steps) <= (1 if pilot else 2), 'Invalid generation step coverage')
    for i, step in enumerate(steps):
        require(step['step'] == i and [r['layer'] for r in step['layers']] == list(range(layers)),
                'Missing, repeated or reordered decoder layer')
        require(all(r['epoch_released'] is True for r in step['layers']), 'Unreleased epoch')
    n = len(steps) * layers
    require(summary['counts'] == dict(attention_commands=2*n, gu_commands=2*n,
                                     host_down_tasks=2*n, epoch_releases=n), 'Count coverage mismatch')
    final = summary['final']
    require(final.get('pending') is None and not final.get('fpga_lease') and not final.get('host_leases')
            and final.get('handles_closed') is True and final.get('owned_processes_exited') is True,
            'Run has not retired its resources')
    return pilot, layers


def bind_sources(summary, source_root):
    root = Path(source_root).resolve(strict=True)
    if root.name == 'deploy' and (root / 'vendor_manifest.json').is_file():
        root = root.parent
    identity = summary['identity']
    manifest = contained(root, 'deploy/vendor_manifest.json')
    require(file_sha(manifest) == identity['vendor_manifest_sha256'], 'Executed vendor manifest mismatch')
    for name, item in json.loads(manifest.read_text())['files'].items():
        path = contained(root / 'deploy', name)
        require(path.stat().st_size == item['bytes'] and file_sha(path) == item['sha256'],
                'Executed frozen dependency changed: ' + name)
    bound = {}
    for name, expected in identity['source_sha256'].items():
        normalized = name.replace('\\', '/')
        require('/deploy/' in normalized, 'Unmappable executed source identity')
        relative = 'deploy/' + normalized.rsplit('/deploy/', 1)[1]
        require(relative not in bound, 'Duplicate executed source mapping')
        path = contained(root, relative)
        require(file_sha(path) == expected, 'Executed source changed: ' + relative)
        bound[relative] = expected
    require(all('deploy/optimized/' + name + '.py' in bound for name in
                ('run', 'backends', 'down', 'store', 'session', 'layout', 'verification')),
            'Missing executed source identities')
    # The oracle comes from this installed release, not executable files in the
    # supplied historical snapshot. Check its frozen dependencies separately.
    deployed = Path(__file__).resolve().parents[1]
    current_manifest = deployed / 'vendor_manifest.json'
    require(file_sha(current_manifest) == file_sha(manifest), 'Auditor frozen reference differs')
    for name, item in json.loads(current_manifest.read_text())['files'].items():
        require(file_sha(contained(deployed, name)) == item['sha256'], 'Auditor dependency changed: ' + name)
    return bound


def cpu_budget():
    require(all(os.environ.get(k) == '1' for k in
                ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')),
            'Use single-thread BLAS through the deployment CLI')
    if hasattr(os, 'sched_getaffinity'):
        os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:8])
    if os.name == 'nt':
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        require(kernel.SetProcessAffinityMask(kernel.GetCurrentProcess(), 0xff), 'CPU affinity failed')
        from resource_guard import ResourceGuard
        guard = ResourceGuard()
        guard()
        return guard
    def guard():
        status = Path('/proc/self/status').read_text().splitlines()
        rss = next(int(s.split()[1])*1024 for s in status if s.startswith('VmRSS:'))
        memory = Path('/proc/meminfo').read_text().splitlines()
        available = next(int(s.split()[1])*1024 for s in memory if s.startswith('MemAvailable:'))
        require(rss <= 6 << 30 and available >= 2 << 30, 'Offline audit memory budget exceeded')
    guard()
    return guard


def _evaluate(root, summary, artifacts_path, assets_path, source_root, result):
    pilot, layers = coverage(summary)
    require(summary['identity']['bit_sha256'] == BIT_SHA, 'Unexpected bit identity')
    result['executed_sources'] = bind_sources(summary, source_root)
    guard = cpu_budget()
    artifacts = GuOnlyArtifactManifest.load(artifacts_path, verify_hashes=True)
    assets = HostAssets(assets_path, verify=True)
    ident = summary['identity']
    require(artifacts.manifest_sha256 == ident['artifact_manifest_sha256']
            and file_sha(assets.path) == ident['host_assets_manifest_sha256']
            and artifacts.original.checkpoint_sha256 == assets.manifest['checkpoint_sha256'] == ident['checkpoint_sha256'],
            'Audit model identity differs from executed model')
    result['model_identity'] = {k: ident[k] for k in
                               ('bit_sha256', 'checkpoint_sha256', 'artifact_manifest_sha256', 'host_assets_manifest_sha256')}
    requests = summary['requests']
    require(len(requests) == 2 and requests[0]['max_new_tokens'] == requests[1]['max_new_tokens'], 'Invalid request set')
    tokenizer, expected_requests = actual_requests(assets, [r['prompt_text'] for r in requests], requests[0]['max_new_tokens'])
    for got, want in zip(requests, expected_requests):
        for key in ('prompt_text', 'rendered_chat', 'initial_token_ids', 'max_new_tokens',
                    'padding_token_id', 'eos_token_ids', 'external_request_id'):
            require(got[key] == want[key], 'Tokenizer/request identity mismatch: ' + key)
    rope = artifacts.original.rope.read_verified()
    seen = {'attention': set(), 'gu': set(), 'epoch': set()}
    counts = dict(attention_outputs=0, gu_outputs=0, down_outputs=0, host_boundaries=0, logits=0)
    result['verified'] = counts
    result['records'] = []

    def same(actual, expected, label):
        require(bytes(actual) == bytes(expected), 'Independent numerical mismatch: ' + label)

    def host(record, value, role=None):
        same(payload(root, record, role), np.asarray(value, dtype='<f4').tobytes(), 'Host ' + str(role))
        counts['host_boundaries'] += 1

    for step in summary['steps']:
        require(not all(r['stop_reason'] is not None for r in expected_requests), 'Unexpected step after EOS/limit')
        states = step['request_states']
        require([s['cohort'] for s in states] == [0, 1], 'Invalid request state order')
        hidden = []
        for state, request in zip(states, expected_requests):
            ids = request['initial_token_ids'] + request['generated_ids']
            padded = ids + [request['padding_token_id']]*(16-len(ids))
            require(0 < len(ids) <= 16 and state['prefix_token_ids'] == ids
                    and state['prefix_length'] == len(ids) and state['padded_token_ids'] == padded
                    and state['last_valid_row'] == len(ids)-1
                    and state['external_request_id'] == request['external_request_id']
                    and state['companion_only'] == (request['stop_reason'] is not None), 'Token feedback/padding mismatch')
            hidden.append(assets.embed(padded))
        for layer_record in step['layers']:
            layer = layer_record['layer']
            guard()
            epoch = layer_record['epoch_id']
            require(epoch not in seen['epoch'], 'Reused epoch')
            seen['epoch'].add(epoch)
            mapping = artifacts.original.layers[layer].artifacts
            reference = ReferenceLayer({name: r.path for name, r in mapping.items()})
            weights = artifacts.down_weights(layer)
            require([r['cohort'] for r in layer_record['cohorts']] == [0, 1], 'Invalid cohort coverage')
            for cr in layer_record['cohorts']:
                c = cr['cohort']; guard()
                host(cr['hidden_before'], hidden[c])
                ai = payload(root, cr['attention'], 'input')
                same(ai, pack_s24_q16(rms_norm(hidden[c], assets.weights.input_layernorm[layer], 1e-5)), 'Attention input')
                ao = payload(root, cr['attention'], 'output')
                agold, aaudit = reference.attention(ai, rope)
                same(ao, agold, 'Attention output')
                counts['attention_outputs'] += 1
                residual = np.add(hidden[c], unpack_s24_q16(ao), dtype=np.float32)
                host(cr['after_attention_residual'], residual)
                gi = payload(root, cr['gu'], 'input')
                same(gi, prepare_gate_up_input_from_normalized_fp32(rms_norm(residual, assets.weights.post_attention_layernorm[layer], 1e-5)), 'GU input')
                go = payload(root, cr['gu'], 'output')
                ggold, gaudit = reference.gu(gi)
                same(go, ggold, 'GU output')
                counts['gu_outputs'] += 1
                q, meta = prepare_down_arrays(go)
                down = down_blocked_int64(q, meta, weights)
                same(payload(root, cr['down'], 'output'), np.asarray(down, dtype='<i4').tobytes(), 'Original integer Down')
                counts['down_outputs'] += 1
                for engine, retired, names in (
                        ('attention', 'sticky_cleared', ('attention_c0', 'attention_c1', 'attention_meta')),
                        ('gu', 'acked', ('mlp_gate_up_c0', 'mlp_gate_up_c1', 'mlp_gate_meta')),
                        ('down', None, ('mlp_down_c0', 'mlp_down_c1', 'mlp_down_meta'))):
                    rec = cr[engine]
                    require(rec['weights_sha256'] == {n: mapping[n].sha256 for n in names}, 'Per-layer weight identity differs')
                    if retired:
                        command = rec['command_id']
                        require(type(command) is int and 0 < command < 2**32 and command not in seen[engine]
                                and rec['copied'] is True and rec[retired] is True, 'Command identity/copy/retirement mismatch')
                        seen[engine].add(command)
                hidden[c] = np.add(residual, np.asarray(down, dtype=np.float32)/np.float32(65536), dtype=np.float32)
                host(cr['hidden_after'], hidden[c])
                result['records'].append(dict(step=step['step'], layer=layer, cohort=c,
                                               attention_sha256=aaudit['output_sha256'], gu_sha256=gaudit['output_sha256'],
                                               down_sha256=hashlib.sha256(np.asarray(down, dtype='<i4').tobytes()).hexdigest()))
            del reference, weights, agold, ggold, aaudit, gaudit
            gc.collect()
            print(json.dumps({'event': 'offline_layer_verified', 'step': step['step'], 'layer': layer}), flush=True)
        if pilot:
            continue
        for c, (state, request) in enumerate(zip(states, expected_requests)):
            final = assets.final_normalized(hidden[c])
            host(state, hidden[c], 'final_hidden'); host(state, final, 'final_normalized')
            logits, token = stream_logits(final, state['last_valid_row'], assets.lm_head, 2048)
            actual_logits = payload(root, state, 'logits')
            require(actual_logits == np.asarray(logits, dtype='<f4').tobytes(),
                    'Strict FP32 LM-head byte mismatch: use the same CPU/NumPy/BLAS environment as the run; '
                    'cross-platform FP32 rounding equivalence is not certified by this mode')
            counts['host_boundaries'] += 1; counts['logits'] += 1
            require(state['argmax_token_id'] == token and state['eos'] == (token in request['eos_token_ids'])
                    and state['decoded_new_text'] == tokenizer.decode([token], skip_special_tokens=False), 'Token selection mismatch')
            if not state['companion_only']:
                request['generated_ids'].append(token)
                request['decoded_generated_text'] = tokenizer.decode(request['generated_ids'], skip_special_tokens=False)
                if state['eos']: request['stop_reason'] = 'eos'
                elif len(request['generated_ids']) >= request['max_new_tokens']: request['stop_reason'] = 'max_new_tokens'
                elif state['prefix_length']+1 >= 16: request['stop_reason'] = 'context_limit'
    for got, want in zip(requests, expected_requests):
        for key in ('generated_ids', 'decoded_generated_text', 'stop_reason'):
            require(got[key] == want[key], 'Final generation mismatch: ' + key)
    require(pilot or all(r['stop_reason'] is not None for r in expected_requests), 'Incomplete generation budget')
    result['scope'] = ('PILOT_NUMERICAL_PASS_%d_LAYERS' % layers if pilot else 'FULL_INFERENCE_NUMERICAL_PASS')
    result['generated_ids'] = [r['generated_ids'] for r in expected_requests]


def audit(run_root, artifacts, assets, source_root, receipt):
    root = Path(run_root).resolve(strict=True)
    receipt = Path(receipt).resolve()
    require(not receipt.exists() and receipt != root/'run_summary.json', 'Receipt must be a new file')
    summary_path = contained(root, 'run_summary.json')
    original = summary_path.read_bytes()
    result = dict(schema='scalellm_offline_numerical_audit_v1', verdict='RUNNING',
                  started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  run_summary_sha256=hashlib.sha256(original).hexdigest(),
                  auditor_sha256=file_sha(__file__), reference_sources=REFERENCE_SOURCES,
                  device_opened=False, baseline_required=False, summary_modified=False,
                  host_fp32_policy='Strict bytewise; use the original CPU/NumPy/BLAS environment for full LM-head audit',
                  audit_environment=dict(platform=platform.platform(), machine=platform.machine(),
                                         numpy=np.__version__, blas=str(getattr(np.__config__, 'CONFIG', {}))),
                  protocol_scope='Numerical audit only; CSR/physical completion acceptance is separate')
    started = time.perf_counter()
    try:
        _evaluate(root, json.loads(original), artifacts, assets, source_root, result)
        require(summary_path.read_bytes() == original, 'Run summary changed during audit')
        result['verdict'] = 'PASS'
    except BaseException as error:
        result.update(verdict='FAIL', first_error={'type': type(error).__name__, 'message': str(error),
                                                 'traceback': traceback.format_exc()})
        raise
    finally:
        result['seconds'] = time.perf_counter()-started
        result['finished_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
        receipt.parent.mkdir(parents=True, exist_ok=True)
        with receipt.open('x') as stream:
            json.dump(result, stream, indent=2); stream.write('\n')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True); parser.add_argument('--artifacts', required=True)
    parser.add_argument('--assets', required=True); parser.add_argument('--source-root', required=True)
    parser.add_argument('--receipt', required=True)
    args = parser.parse_args(argv)
    result = audit(args.run, args.artifacts, args.assets, args.source_root, args.receipt)
    print(json.dumps({k: v for k, v in result.items() if k not in ('records', 'executed_sources', 'reference_sources')}, indent=2))


if __name__ == '__main__':
    main()
