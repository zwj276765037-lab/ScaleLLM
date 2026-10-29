#!/usr/bin/env python3
"""Seal, verify, and package the explicitly selected Decode16 release."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = 'ScaleLLM_Final_Decode16_80MHz'
BIT_NAME = PROJECT + '.bit'
BIT_SHA256 = '96df1a5c1bf4174921bc02ccd88df4066dece3d62b491acb3106bb90ac0ffc85'
BIT_SIZE = 80159263
MANIFEST = 'RELEASE_MANIFEST.json'
SKIP_PARTS = {'.git', '__pycache__', '.pytest_cache', '.Xil', '.venv'}
LOCAL_ROOTS = {'build', 'dist', 'runs', 'outputs', 'models', 'artifacts', 'release-check'}
FORBIDDEN_SUFFIXES = {'.pem', '.key', '.pfx', '.p12', '.cer', '.crt', '.sys', '.cat',
                      '.safetensors', '.npy', '.npz', '.pt', '.pth', '.f32', '.dcp', '.exe', '.dll'}
SOURCE_MANIFESTS = {'deploy/vendor_manifest.json': ('files',),
                    'deploy/final/hardware_source_manifest.json': ('files', 'portable_build_files')}
SECRET_PATTERNS = [re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
                   re.compile(rb'\bgh[pousr]_[A-Za-z0-9]{30,}\b'),
                   re.compile(rb'\bhf_[A-Za-z0-9]{30,}\b')]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def safe_relative(value: str) -> str:
    p = PurePosixPath(value)
    if (not value or value == '.' or p.is_absolute() or '..' in p.parts
            or '\\' in value or ':' in value or p.as_posix() != value):
        raise ValueError(f'Unsafe release path: {value}')
    return value


def check_file(root: Path, name: str) -> Path:
    name = safe_relative(name)
    path = root / name
    if (any(p.is_symlink() for p in [path, *path.parents] if p != root.parent)
            or not path.resolve().is_relative_to(root.resolve())):
        raise ValueError(f'Unsafe installed file: {name}')
    if not path.is_file():
        raise ValueError(f'Missing release file: {name}')
    rel = PurePosixPath(name)
    if (set(rel.parts) & SKIP_PARTS or rel.parts[0] in LOCAL_ROOTS
            or path.suffix.lower() in FORBIDDEN_SUFFIXES or path.name.startswith('.env')
            or (path.suffix == '.bit' and name != 'bitstream/' + BIT_NAME)):
        raise ValueError(f'Excluded data type selected: {name}')
    return path


def check_sources(root: Path, names: set[str]) -> None:
    for manifest_name, sections in SOURCE_MANIFESTS.items():
        if manifest_name not in names:
            raise ValueError(f'Required source manifest omitted: {manifest_name}')
        manifest = json.loads((root / manifest_name).read_text())
        for section in sections:
            for name, entry in manifest[section].items():
                name = safe_relative(name)
                if name not in names:
                    raise ValueError(f'Required dependency omitted: {name}')
                path = check_file(root, name)
                digest = entry if isinstance(entry, str) else entry['sha256']
                if sha256(path) != digest or (isinstance(entry, dict) and 'bytes' in entry
                                              and path.stat().st_size != entry['bytes']):
                    raise ValueError(f'Frozen dependency mismatch: {name}')
    name = 'bitstream/' + BIT_NAME
    if name not in names:
        raise ValueError('Board-tested bitstream omitted')
    bit = root / name
    if bit.stat().st_size != BIT_SIZE or sha256(bit) != BIT_SHA256:
        raise ValueError('Released bitstream differs from the board-tested identity')


def selected_files(config: dict, root: Path | None = None) -> dict[str, Path]:
    root = ROOT if root is None else root
    selected = {}
    for name in config['files']:
        if name == MANIFEST or name in selected:
            raise ValueError(f'Duplicate or self-referential selection: {name}')
        selected[name] = check_file(root, name)
    check_sources(root, set(selected))
    return selected


def seal(root: Path, config: dict) -> dict:
    selected = selected_files(config, root)
    files = []
    for name, path in sorted(selected.items()):
        if path.suffix.lower() not in {'.bit', '.png', '.pdf'}:
            if any(pattern.search(path.read_bytes()) for pattern in SECRET_PATTERNS):
                raise ValueError(f'Potential credential detected in {name}')
        files.append({'path': name, 'bytes': path.stat().st_size, 'sha256': sha256(path)})
    manifest = {'schema': 'scalellm_final_release_v1', 'project': PROJECT,
                'release_date': '2026-10-29', 'bitstream_sha256': BIT_SHA256, 'files': files}
    (root / MANIFEST).write_text(json.dumps(manifest, indent=2) + '\n')
    return verify(root)


def verify(directory: Path) -> dict:
    directory = directory.resolve()
    manifest = json.loads((directory / MANIFEST).read_text())
    if manifest.get('project') != PROJECT:
        raise ValueError('Not a ScaleLLM Decode16 release')
    expected = set()
    for entry in manifest['files']:
        name = safe_relative(entry['path'])
        if name in expected or name == MANIFEST:
            raise ValueError(f'Duplicate manifest entry: {name}')
        expected.add(name)
        path = check_file(directory, name)
        if path.stat().st_size != entry['bytes'] or sha256(path) != entry['sha256']:
            raise ValueError(f'Release verification failed: {name}')
    actual = set()
    # Prune local build/model directories: verification never traverses weights.
    import os
    for parent, directories, filenames in os.walk(directory, followlinks=False):
        relative = Path(parent).relative_to(directory)
        directories[:] = [d for d in directories if d not in SKIP_PARTS
                           and not (relative == Path('.') and d in LOCAL_ROOTS)]
        for dirname in directories:
            if (Path(parent) / dirname).is_symlink():
                raise ValueError(f'Unsafe installed file: {relative / dirname}')
        actual.update((relative / name).as_posix() for name in filenames if name not in SKIP_PARTS)
    extra = actual - expected - {MANIFEST}
    if extra:
        raise ValueError(f'Unlisted files in release: {sorted(extra)[:10]}')
    check_sources(directory, expected)
    return {'status': 'PASS', 'file_count': len(expected),
            'bytes': sum(p['bytes'] for p in manifest['files']), 'bitstream_sha256': BIT_SHA256}


def build(root: Path, output: Path) -> dict:
    verified = verify(root)
    output = output.resolve()
    if output == root or output in root.parents or output.exists():
        raise ValueError('Output must be a new directory outside source inputs')
    manifest = json.loads((root / MANIFEST).read_text())
    names = [e['path'] for e in manifest['files']] + [MANIFEST]
    if any((root / name).is_relative_to(output) for name in names):
        raise ValueError('Output overlaps source inputs')
    output.mkdir(parents=True)
    for name in names:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, target)
        target.chmod(0o644)
    verify(output)
    archive = output.with_suffix('.tar.gz')
    if archive.exists():
        raise ValueError(f'Archive already exists: {archive}')
    with archive.open('wb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode='w') as tar:
            for name in sorted(names):
                path = output / name
                info = tar.gettarinfo(str(path), arcname=output.name + '/' + name)
                info.uid = info.gid = 0
                info.uname = info.gname = ''
                info.mtime = 0
                info.mode = 0o644
                with path.open('rb') as f:
                    tar.addfile(info, f)
    digest = sha256(archive)
    archive.with_suffix('.gz.sha256').write_text(f'{digest}  {archive.name}\n')
    return {**verified, 'archive': str(archive), 'archive_sha256': digest,
            'archive_bytes': archive.stat().st_size}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    sealing = commands.add_parser('seal', help='Maintainer: refresh the checked-in integrity manifest')
    sealing.add_argument('--config', type=Path, default=ROOT / 'deploy/release_files.json')
    verification = commands.add_parser('verify', help='Verify a clone or an extracted release')
    verification.add_argument('directory', type=Path, nargs='?', default=ROOT)
    packaging = commands.add_parser('build', help='Create a verified directory and deterministic archive')
    packaging.add_argument('--output', type=Path, default=ROOT / 'dist' / PROJECT)
    args = parser.parse_args()
    if args.command == 'seal':
        result = seal(ROOT, json.loads(args.config.read_text()))
    elif args.command == 'verify':
        result = verify(args.directory)
    else:
        result = build(ROOT, args.output)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
