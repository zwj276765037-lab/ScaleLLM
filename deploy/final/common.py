"""Standard-library configuration, source identity and request validation."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / 'deploy'
CHECKPOINT_SHA = '8a09c60f3256779c16925f8209c9399ba4a1ee0406caf65bd2637ffd99287d6d'
DEFAULT_PROFILE = 'all-dsp'
BIT_BYTES = 80159263
PROFILES = {
    'all-dsp': {
        'bit_sha256': '5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7',
        'hardware_source_manifest': 'resource_optimization/hardware/provenance/candidate_manifest.json',
        'hardware_source_manifest_sha256': '5f98985a906d55abdabe8ab2d75a636970c0f5275ef04ba6572edb91763bd7bb',
    },
    'legacy': {
        'bit_sha256': '96df1a5c1bf4174921bc02ccd88df4066dece3d62b491acb3106bb90ac0ffc85',
        'hardware_source_manifest': 'deploy/final/hardware_source_manifest.json',
        'hardware_source_manifest_sha256': '10795824a738727afadaf55941d7c51dc4e36ff3e1819df2ab0ab9b23160f3c9',
    },
}
BIT_SHA = PROFILES[DEFAULT_PROFILE]['bit_sha256']
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
    for path in reversed((ROOT / 'project/hardware', DEPLOY / 'vendor/runtime', ROOT)):
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
    value.setdefault('deployment_profile', DEFAULT_PROFILE)
    profile_identity(value['deployment_profile'])
    for key in ('artifacts', 'host_assets', 'output_dir', 'bitstream', 'requests', 'messages'):
        raw = value.get(key)
        if not isinstance(raw, str) or not raw:
            raise ValueError('Missing configured path: ' + key)
        value[key] = str((path.parent / Path(os.path.expandvars(os.path.expanduser(raw)))).resolve())
    if value.get('expected_checkpoint_sha256') != CHECKPOINT_SHA:
        raise ValueError('This release requires the documented verified checkpoint identity')
    value.setdefault('wall_seconds', None)
    validate_timeouts(value.get('command_timeout_seconds'), value['wall_seconds'])
    digest = value.get('expected_driver_sha256')
    if digest is not None and (not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest)):
        raise ValueError('expected_driver_sha256 must be null or a lowercase SHA256')
    return value


def validate_timeouts(command_seconds, wall_seconds=None):
    for key, number, maximum in (('command_timeout_seconds', command_seconds, 600),
                                 ('wall_seconds', wall_seconds, 86400)):
        if key == 'wall_seconds' and number is None:
            continue
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or not 0 < number <= maximum:
            raise ValueError('Invalid timeout: ' + key)


def profile_identity(name=DEFAULT_PROFILE):
    if not isinstance(name, str) or name not in PROFILES:
        raise ValueError('deployment_profile must be one of: ' + ', '.join(PROFILES))
    return dict(name=name, board='VCU118', part='xcvu9p', core_hz=80000000,
                bit_bytes=BIT_BYTES, **PROFILES[name])


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


def check_bit(path, profile=DEFAULT_PROFILE):
    identity = profile_identity(profile)
    path = Path(path).resolve(strict=True)
    if not path.is_file() or path.stat().st_size != identity['bit_bytes'] or sha(path) != identity['bit_sha256']:
        raise ValueError('Released ' + profile + ' 80 MHz bitstream size/SHA256 mismatch')
    return path


def current_host_identity():
    """Identify the execution host and boot without touching PCIe or JTAG."""
    hostname = socket.gethostname().casefold()
    if not hostname:
        raise RuntimeError('Cannot establish the programming host identity')
    if sys.platform == 'win32':
        powershell = (Path(os.environ.get('SystemRoot', r'C:\Windows')) /
                      'System32/WindowsPowerShell/v1.0/powershell.exe')
        script = ("$ErrorActionPreference='Stop'; "
                  "$boot=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime; "
                  "if ($null -eq $boot) { throw 'Missing OS boot identity' }; "
                  "$boot.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffffffZ')")
        result = subprocess.run([str(powershell), '-NoProfile', '-NonInteractive',
                                 '-Command', script], capture_output=True, text=True,
                                check=True, timeout=30)
        boot = result.stdout.strip()
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{7}Z', boot):
            raise RuntimeError('Unexpected Windows boot identity response')
        source = 'Win32_OperatingSystem.LastBootUpTime.UTC'
    elif sys.platform.startswith('linux'):
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        if not re.fullmatch(r'[0-9a-f-]{36}', boot):
            raise RuntimeError('Unexpected Linux boot identity response')
        source = 'procfs.boot_id'
    else:
        raise RuntimeError('Programming receipt host/boot identity is supported on Windows and Linux')
    return dict(hostname=hostname, platform=sys.platform, boot_id=boot, boot_source=source)


def read_program_receipt(path, profile=DEFAULT_PROFILE):
    path = Path(path).resolve(strict=True)
    receipt = json.loads(path.read_text(encoding='utf-8'))
    identity = profile_identity(profile)
    if (receipt.get('schema') != 'scalellm_sram_program_receipt_v1'
            or receipt.get('execution') != 'COMPLETE'
            or type(receipt.get('returncode')) is not int or receipt['returncode'] != 0
            or receipt.get('deployment_profile') != identity
            or receipt.get('volatile_sram') is not True):
        raise ValueError('Programming receipt must record successful programming of the selected released profile')
    if receipt.get('host_identity') != current_host_identity():
        raise ValueError('Programming receipt belongs to a different host/boot or lacks host identity; program again on this execution host')
    return dict(path=str(path), sha256=sha(path), receipt=receipt,
                relationship='Successful programming record from this host and boot; CSR validates ABI and cannot detect an intervening external reprogram')
