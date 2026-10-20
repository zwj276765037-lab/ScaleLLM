"""Validate frozen identities, then one read-only native checkpoint load."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / '.research-agent/project.json').is_file())
HW = ROOT / 'project/hardware'
sys.path.insert(0, str(HW / 'vivado/scripts'))
import m003_entry


def identity(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest.hexdigest())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--archive-source', action='append', default=[])
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    package = json.loads(args.package.read_text())
    assert package['scope'] == 'R004_final_failed_route_read_only_localization'
    for item in package['bindings']:
        assert identity(item['path']) == item, item['path']
    core = m003_entry.check_sources()['sources']
    expected = {item['path'] for item in core} | set(package['runtime_sources'])
    assert len(args.archive_source) == len(expected) and set(args.archive_source) == expected
    assert not package['physical_commands_allowed']
    if args.prepare_only:
        print(json.dumps(dict(prepared=True, native_executed=False,
                              runtime_source_count=len(expected), checkpoint=package['checkpoint'])))
        return 0
    review = ROOT / package['independent_gate']
    gate = json.loads(review.read_text())
    assert gate['no_substantive_blocker'] is True
    assert gate['package'] == identity(args.package)
    assert identity(gate['review_evidence']['path']) == gate['review_evidence']
    report = Path(os.environ['HAP_REPORT_DIR'])
    assert report.is_relative_to(HW / 'vivado/reports') and not report.exists()
    report.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith('M003_')}
    env.update(M003_DCP=package['checkpoint']['path'], M003_OUT=str(report),
               M003_TARGETS=str(HERE / 'targets.tcl'),
               M003_AGGREGATE=str(HERE / 'aggregate.py'),
               M003_PLAN=str(HERE / 'query_plan.json'))
    command = ['/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado',
               '-mode', 'batch', '-notrace', '-source', str(HERE / 'attribution.tcl'),
               '-log', str(report / 'vivado.log'), '-journal', str(report / 'vivado.jou')]
    result = subprocess.run(command, cwd=report, env=env)
    (report / 'launcher_status.json').write_text(json.dumps(dict(
        native_exit_code=result.returncode, read_only=True, checkpoint=package['checkpoint'],
        package=identity(args.package)), indent=2) + '\n')
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
