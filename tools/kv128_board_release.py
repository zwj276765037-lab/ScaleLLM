#!/usr/bin/env python3
"""Verify, unpack and optionally recompute the published KV128 board evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import zipfile


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(path):
    return json.dumps(json.loads(path.read_text(encoding='utf-8-sig')),
                      sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=Path(__file__).resolve().parents[1]
                        / 'docs/evidence/kv128_chat16/package.json')
    parser.add_argument('--output', type=Path, required=True,
                        help='New or empty extraction directory; existing evidence is never overwritten')
    parser.add_argument('--recompute', action='store_true',
                        help='Recompute board counters, tokens, capture hashes and VCCINT observations offline')
    args = parser.parse_args()
    package_path = args.package.resolve(strict=True)
    package = json.loads(package_path.read_text())
    check(package['schema'] == 'scalellm_kv128_board_package_v1', 'Unexpected package schema')
    output = args.output.resolve()
    check(not output.exists() or (output.is_dir() and not any(output.iterdir())),
          'Output directory must be new or empty')
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='scalellm-kv128-') as tmp:
        archive = Path(tmp) / 'evidence.zip'
        with archive.open('wb') as assembled:
            for part in package['parts']:
                name = part['file']
                check(PurePosixPath(name).name == name, 'Unsafe package part name')
                path = package_path.parent / name
                check(path.is_file() and path.stat().st_size == part['bytes']
                      and digest(path) == part['sha256'], f'Package part mismatch: {name}')
                with path.open('rb') as source:
                    shutil.copyfileobj(source, assembled)
        check(archive.stat().st_size == package['archive_bytes']
              and digest(archive) == package['archive_sha256'], 'Assembled archive mismatch')
        with zipfile.ZipFile(archive) as z:
            names = z.namelist()
            check(len(names) == len(set(names)), 'Duplicate archive members')
            for name in names:
                relative = PurePosixPath(name)
                check(not relative.is_absolute() and '..' not in relative.parts
                      and '\\' not in name, f'Unsafe archive member: {name}')
                check((z.getinfo(name).external_attr >> 16) & 0o170000 != 0o120000,
                      f'Symlink archive member: {name}')
            check(z.testzip() is None, 'ZIP CRC mismatch')
            z.extractall(output)
    manifest_path = output / 'MANIFEST.json'
    check(digest(manifest_path) == package['manifest_sha256'], 'Manifest identity mismatch')
    manifest = json.loads(manifest_path.read_text())
    listed = set()
    for item in manifest['files']:
        path = output / item['path']
        check(path.is_file() and path.stat().st_size == item['bytes']
              and digest(path) == item['sha256'], f'Extracted file mismatch: {item["path"]}')
        listed.add(item['path'])
    actual = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}
    check(actual == listed | {'MANIFEST.json'}, 'Extracted file set mismatch')
    result = {'status': 'PASS', 'archive_sha256': package['archive_sha256'],
              'verified_files': len(listed), 'verified_bytes': sum(x['bytes'] for x in manifest['files']),
              'recomputation': 'NOT_RUN'}
    if args.recompute:
        native = output / 'board/native/run_002'
        recomputed = output / 'recomputed'
        subprocess.run([sys.executable, str(output / 'tools/operator_timing/kv128_transfer_verify.py'),
                        '--native', str(native), '--output', str(recomputed / 'transfer_verification.json')], check=True)
        subprocess.run([sys.executable, str(output / 'tools/operator_timing/kv128_board_analyze.py'),
                        '--native', str(native), '--output', str(recomputed)], check=True)
        files = ['summary.json', 'tokens.json', 'capture_verification.json', 'power_summary.json',
                 'transfer_verification.json', 'commands.csv', 'outputs.txt', 'power_kv32.csv',
                 'power_kv128.csv', 'power_kv32_strata.csv', 'power_kv128_strata.csv']
        for name in files:
            original, new = output / 'board/results' / name, recomputed / name
            equal = canonical(original) == canonical(new) if name.endswith('.json') else digest(original) == digest(new)
            check(equal, f'Recomputed result differs: {name}')
        result.update(recomputation='PASS', recomputed_files=files)
    (output / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
