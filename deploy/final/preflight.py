"""Read-only dependency, model and final 80 MHz ABI checks."""
from __future__ import annotations

import importlib
import importlib.metadata
import os
from pathlib import Path
import platform
import sys

from .common import CHECKPOINT_SHA, DEPENDENCIES, bootstrap, read_requests, sha, source_check


def driver_identity(expected=None):
    if os.name != 'nt':
        raise RuntimeError('Local XDMA device checks require Windows')
    path = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/drivers/XDMA.sys'
    if not path.is_file():
        raise FileNotFoundError('Install the documented locally signed XDMA driver: ' + str(path))
    actual = sha(path)
    if expected is not None and actual != expected:
        raise ValueError('Installed XDMA.sys differs from expected_driver_sha256')
    return dict(path=str(path), sha256=actual, expected_sha256=expected,
                comparison='PASS' if expected else 'RECORDED; no expected digest configured')


def inspect_device(session):
    from host.scalellm_final_abi import CSR
    from host.scalellm_final_runtime import FinalBoardBackend
    backend = FinalBoardBackend(session)
    backend.require_quiescent()
    snapshot = {name: session.read32(address) for name, address in CSR.items()
                if name not in ('DESCRIPTOR', 'COMPLETION_DESCRIPTOR')}
    if snapshot['ADMISSION_ERROR'] or snapshot['DONE_ERROR']:
        raise RuntimeError('Final board retains an error; inspect it and recover manually')
    return snapshot


def preflight(config, *, models=False, device=False, requests_path=None):
    checked = source_check()
    if sys.version_info < (3, 10) or sys.maxsize <= 2**32:
        raise RuntimeError('64-bit CPython 3.10+ required; tested with 3.12')
    try:
        versions = {name: importlib.metadata.version(name) for name in DEPENDENCIES}
    except importlib.metadata.PackageNotFoundError as error:
        raise RuntimeError('Install deploy/requirements.txt in your Python environment') from error
    if versions != DEPENDENCIES:
        raise RuntimeError('Pinned deployment dependency versions required: ' + repr(versions))
    bootstrap()
    for name in ('host_math', 'resource_guard', 'scalellm_windows_xdma',
                 'host.scalellm_final_runtime', 'host.scalellm_final_assets',
                 'host.scalellm_mlp_gu_only_artifacts', 'host.scalellm_final_lm_head'):
        importlib.import_module(name)
    from host.scalellm_final_abi import IDS
    if IDS['core_hz'] != 80000000:
        raise ValueError('Final ABI must use 80 MHz')
    requests = read_requests(requests_path or config['requests'])
    report = dict(verdict='PASS', python=platform.python_version(), dependencies=versions,
                  source_files_verified=checked, imports='PASS', abi=IDS,
                  requests=len(requests), device_opened=False, device_writes=False,
                  gpu_used=False, model_hashes='NOT_RUN')
    if models:
        import host_math
        from host.scalellm_mlp_gu_only_artifacts import GuOnlyArtifactManifest
        host_math.CHECKPOINT_SHA = CHECKPOINT_SHA
        assets = host_math.HostAssets(config['host_assets'], verify=True)
        artifacts = GuOnlyArtifactManifest.load(config['artifacts'], verify_hashes=True)
        if assets.manifest['checkpoint_sha256'] != artifacts.original.checkpoint_sha256:
            raise ValueError('CPU/FPGA checkpoint identities differ')
        report.update(model_hashes='ALL_SHA_PASS', checkpoint_sha256=CHECKPOINT_SHA,
                      artifact_manifest_sha256=sha(config['artifacts']),
                      host_manifest_sha256=sha(config['host_assets']))
    if device:
        report['driver'] = driver_identity(config.get('expected_driver_sha256'))
        from scalellm_windows_xdma import WindowsXdmaSession
        with WindowsXdmaSession(open_dma=False) as session:
            report['readonly_csrs'] = inspect_device(session)
        report.update(device_opened=True, handles_closed=not session.handles and not session.quarantine)
    return report
