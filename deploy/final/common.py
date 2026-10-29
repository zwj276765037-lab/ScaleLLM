"""Standard-library configuration, source identity and request validation."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / 'deploy'
CHECKPOINT_SHA = '8a09c60f3256779c16925f8209c9399ba4a1ee0406caf65bd2637ffd99287d6d'
BIT_SHA = '96df1a5c1bf4174921bc02ccd88df4066dece3d62b491acb3106bb90ac0ffc85'
BIT_BYTES = 80159263
DEPENDENCIES = {'numpy': '1.26.4', 'tokenizers': '0.20.3', 'Jinja2': '3.1.6'}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def source_check():
    manifest = json.loads((DEPLOY / 'vendor_manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 'scalellm_final_runtime_sources_v1':
        raise ValueError('Unsupported final runtime source manifest')
    for relative, entry in manifest['files'].items():
        path = (ROOT / relative).resolve()
        path.relative_to(ROOT)
        if not path.is_file() or path.stat().st_size != entry['bytes'] or sha(path) != entry['sha256']:
            raise ValueError('Runtime source identity mismatch: ' + relative)
    return len(manifest['files'])


def bootstrap():
    # Set before importing NumPy or any numerical runtime module.
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '1'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    for path in reversed((ROOT / 'project/hardware', DEPLOY / 'vendor/runtime')):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def cpu_budget(max_cpus=8):
    """Restrict this process to up to eight CPUs already allowed by its parent."""
    if type(max_cpus) is not int or not 1 <= max_cpus <= 8:
        raise ValueError('max_cpus must be 1..8')
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.GetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
        kernel.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
        process = kernel.GetCurrentProcess()
        allowed, system = ctypes.c_size_t(), ctypes.c_size_t()
        if not kernel.GetProcessAffinityMask(process, ctypes.byref(allowed), ctypes.byref(system)):
            raise ctypes.WinError(ctypes.get_last_error())
        selected = [bit for bit in range(allowed.value.bit_length()) if allowed.value >> bit & 1][:max_cpus]
        mask = sum(1 << bit for bit in selected)
        if not mask or not kernel.SetProcessAffinityMask(process, mask):
            raise ctypes.WinError(ctypes.get_last_error())
        return {'logical_cpus': selected, 'affinity_mask': mask, 'blas_threads': 1}
    if hasattr(os, 'sched_getaffinity'):
        selected = sorted(os.sched_getaffinity(0))[:max_cpus]
        os.sched_setaffinity(0, selected)
        return {'logical_cpus': selected, 'blas_threads': 1}
    return {'logical_cpus': None, 'blas_threads': 1, 'affinity': 'UNAVAILABLE'}


def read_config(path):
    path = Path(path).resolve()
    value = json.loads(path.read_text(encoding='utf-8'))
    if value.get('schema') != 'scalellm_final_deploy_v1':
        raise ValueError('Use the final 80 MHz deployment config schema')
    for key in ('artifacts', 'host_assets', 'output_dir', 'bitstream', 'requests', 'messages'):
        raw = value.get(key)
        if not isinstance(raw, str) or not raw:
            raise ValueError('Missing configured path: ' + key)
        value[key] = str((path.parent / Path(os.path.expandvars(os.path.expanduser(raw)))).resolve())
    if value.get('expected_checkpoint_sha256') != CHECKPOINT_SHA:
        raise ValueError('This release requires the documented verified checkpoint identity')
    for key, maximum in (('command_timeout_seconds', 600), ('wall_seconds', 86400)):
        number = value.get(key)
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or not 0 < number <= maximum:
            raise ValueError('Invalid timeout: ' + key)
    digest = value.get('expected_driver_sha256')
    if digest is not None and (not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest)):
        raise ValueError('expected_driver_sha256 must be null or a lowercase SHA256')
    return value


def validate_requests(requests):
    if not isinstance(requests, list) or not 1 <= len(requests) <= 16:
        raise ValueError('One to sixteen request records required')
    seen = set()
    for request in requests:
        if not isinstance(request, dict) or set(request) != {'slot', 'prompt_token_ids', 'max_new_tokens'}:
            raise ValueError('Request needs exactly slot, prompt_token_ids, max_new_tokens')
        slot, tokens, maximum = request['slot'], request['prompt_token_ids'], request['max_new_tokens']
        if type(slot) is not int or not 0 <= slot < 16 or slot in seen:
            raise ValueError('Request slots must be unique integers 0..15')
        seen.add(slot)
        if not isinstance(tokens, list) or not tokens or any(type(token) is not int or not 0 <= token < 128256 for token in tokens):
            raise ValueError('Prompt token IDs must be nonempty integers in the model vocabulary')
        if type(maximum) is not int or not 1 <= maximum <= 32 or len(tokens) + maximum > 128:
            raise ValueError('max_new_tokens must be 1..32; prompt plus budget must fit 128 positions')
    return requests


def read_requests(path):
    return validate_requests(json.loads(Path(path).read_text(encoding='utf-8')))


def check_bit(path):
    path = Path(path).resolve(strict=True)
    if path.stat().st_size != BIT_BYTES or sha(path) != BIT_SHA:
        raise ValueError('Released final 80 MHz bitstream size/SHA256 mismatch')
    return path
