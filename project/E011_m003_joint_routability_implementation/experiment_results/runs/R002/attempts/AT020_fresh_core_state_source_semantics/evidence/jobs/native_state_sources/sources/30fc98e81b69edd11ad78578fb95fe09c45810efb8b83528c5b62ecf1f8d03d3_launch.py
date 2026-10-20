"""Pin reviewed standalone diagnostic and original fresh core before native read."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys


def identity(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest.hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--review-sha256', required=True)
    parser.add_argument('--tcl', type=Path, required=True)
    parser.add_argument('--lineage', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[5]
    package_id = identity(args.package)
    package = json.loads(args.package.read_text())
    review_id = identity(args.review)
    assert review_id['sha256'] == args.review_sha256, 'Review identity mismatch'
    review = json.loads(args.review.read_text())
    assert review['no_blocker'] is True, 'Actual A007 diagnostic no-blocker required'
    assert review['package_sha256'] == package_id['sha256'], 'Review package mismatch'
    assert package['schema'] == 'M003_readonly_address_startpoint_semantics_v1'
    for source in package['sources']:
        assert identity(source['path']) == source, 'Diagnostic source changed'
    assert any(row == identity(args.tcl) for row in package['sources'])
    for key in ('previous_terminal', 'entry_manifest', 'G2', 'original_raw_lineage'):
        assert identity(package[key]['path']) == package[key], key + ' changed'
    assert identity(args.lineage) == package['original_raw_lineage']
    sys.path.insert(0, str(root / 'project/hardware/vivado/scripts'))
    import m003_entry
    assert len(m003_entry.check_sources()['sources']) == 45
    raw = json.loads(args.lineage.read_text())
    rows = [r for r in raw['run_records'] if r['run'] == 'scalellm_vcu118_f05_bd_core_0_synth_1']
    assert len(rows) == 1
    row = rows[0]
    checkpoint = Path(row['checkpoint']['path'])
    assert identity(checkpoint) == row['checkpoint'] == package['fresh_core']
    assert identity(row['end']['path']) == row['end']
    assert not (checkpoint.parent / '.vivado.error.rst').exists()
    report = Path(os.environ['HAP_REPORT_DIR'])
    report.mkdir()
    binding = dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   diagnostic_package=package_id, independent_review=review_id,
                   previous_terminal=package['previous_terminal'], entry_manifest=package['entry_manifest'],
                   raw_original_lineage=identity(args.lineage),
                   core_original_produced_checkpoint=identity(checkpoint),
                   core_original_native_completion=identity(row['end']['path']),
                   scope='Read-only same-version fresh core34helperD rawfanin/sourceowner/Q-in-cone and80URAMCLK primaryport; no constraint apply/new synthesis/G4')
    (report / 'state_source_core_consumption_binding.json').write_text(json.dumps(binding, indent=2) + '\n')
    command = ['/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado',
               '-mode', 'batch', '-notrace', '-source', str(args.tcl),
               '-log', str(report / 'vivado.log'), '-journal', str(report / 'vivado.jou'),
               '-tclargs', str(checkpoint)]
    return subprocess.run(command, cwd=report).returncode


if __name__ == '__main__':
    sys.exit(main())
