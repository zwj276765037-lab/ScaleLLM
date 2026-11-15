#!/usr/bin/env python3
"""Verify this version's source, bitstream, evidence and optional release assets."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

ROOT = Path(__file__).resolve().parent

def digest(stream):
    value = hashlib.sha256()
    for block in iter(lambda: stream.read(4 << 20), b''):
        value.update(block)
    return value.hexdigest()

def file_digest(path):
    with path.open('rb') as stream:
        return digest(stream)

def safe_relative(value):
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or '\\' in value or ':' in value:
        raise ValueError('Unsafe manifest path: ' + value)
    return path

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--checkpoint', type=Path)
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    for name, expected in manifest['files'].items():
        path = ROOT / safe_relative(name)
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError('Unsafe local path: ' + name)
        if path.stat().st_size != expected['bytes'] or file_digest(path) != expected['sha256']:
            raise ValueError('Published file mismatch: ' + name)
    candidate = json.loads((ROOT / 'hardware/provenance/candidate_manifest.json').read_text())
    if len(candidate['source_inputs']) != 106:
        raise ValueError('Expected the exact 106-input closure')
    for name, expected in candidate['source_inputs'].items():
        if file_digest(ROOT / 'hardware/source' / safe_relative(name)) != expected:
            raise ValueError('Frozen source mismatch: ' + name)
    bit = ROOT / 'hardware/bitstream/ScaleLLM_Final_Decode16_80MHz.bit'
    if bit.stat().st_size != 80159263 or file_digest(bit) != '5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7':
        raise ValueError('The tested bitstream identity differs')
    regression = json.loads((ROOT / 'results/board/inference/regression.json').read_text())
    if (regression['status'], regression['generated_tokens'], regression['complete_rounds'], regression['hardware_commands']) != ('PASS', 512, 50, 3200):
        raise ValueError('Published board coverage differs')
    downloads = json.loads((ROOT / 'downloads.json').read_text())
    assets = {item['name']: item for item in downloads['assets']}
    for path, suffix in [(args.archive, '.zip'), (args.checkpoint, '.dcp')]:
        if path is None:
            continue
        expected = next(item for name, item in assets.items() if name.endswith(suffix))
        if path.stat().st_size != expected['bytes'] or file_digest(path) != expected['sha256']:
            raise ValueError('Release asset size/SHA mismatch: ' + str(path))
    archive_files = None
    if args.archive:
        with zipfile.ZipFile(args.archive) as bundle:
            names = bundle.namelist()
            if len(names) != len(set(names)):
                raise ValueError('Duplicate archive member')
            original = json.loads(bundle.read('MANIFEST.json'))
            expected_names = {'MANIFEST.json'} | {'mlp_scalecode_dsp_board/' + name for name in original['files']}
            if set(names) != expected_names:
                raise ValueError('Archive member inventory differs')
            for name, expected in original['files'].items():
                safe_relative(name)
                member = 'mlp_scalecode_dsp_board/' + name
                if bundle.getinfo(member).file_size != expected['bytes']:
                    raise ValueError('Archive member length differs: ' + name)
                with bundle.open(member) as stream:
                    if digest(stream) != expected['sha256']:
                        raise ValueError('Archive member SHA differs: ' + name)
            archive_files = len(original['files'])
    print(json.dumps({'status': 'PASS', 'version_files': len(manifest['files']), 'source_inputs': 106,
                      'tested_bitstream': 'PASS', 'archive_members_verified': archive_files,
                      'checkpoint_verified': args.checkpoint is not None}, indent=2))

if __name__ == '__main__':
    main()
