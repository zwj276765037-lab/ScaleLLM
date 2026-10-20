"""Owned, bounded read-only source query on the actual successful place DCP."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
HW = ROOT / 'project/hardware'
sys.path.insert(0, str(HW / 'vivado/scripts'))
import m003_entry as entry

def identity(path):
    path = Path(path)
    return dict(path=str(path), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--archive-source', action='append', default=[])
    args = parser.parse_args()
    package = json.loads(args.package.read_text())
    assert package['scope'] == '12_selected_FDCE_48_state_pins_24_URAM_root_pins_read_only'
    for row in package['bindings']:
        assert identity(row['path']) == row
    core = entry.check_sources()['sources']
    expected = {row['path'] for row in core} | {str(HERE / name) for name in ['run_query.py', 'query.tcl', 'targets.tcl']}
    assert set(args.archive_source) == expected and len(args.archive_source) == len(expected)
    report = Path(os.environ['HAP_REPORT_DIR'])
    assert report.is_relative_to(HW / 'vivado/reports') and not report.exists()
    report.mkdir()
    env = {**os.environ, 'HAP_QUERY_CHECKPOINT': package['checkpoint']['path'],
           'HAP_M003_RESTORE_VERIFY_ONLY': '1', 'HAP_M003_SCRIPTS_DIR': str(HW / 'vivado/scripts')}
    command = ['/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado',
               '-mode', 'batch', '-notrace', '-source', str(HERE / 'query.tcl'),
               '-log', str(report / 'vivado.log'), '-journal', str(report / 'vivado.jou')]
    result = subprocess.run(command, cwd=HW / 'vivado', env=env)
    status = dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  native_exit_code=result.returncode, command=command,
                  checkpoint=package['checkpoint'], package=identity(args.package),
                  read_only=True, place_reexecuted=False)
    with (report / 'launcher_status.json').open('x') as stream:
        json.dump(status, stream, indent=2)
        stream.write('\n')
    return result.returncode

if __name__ == '__main__':
    sys.exit(main())
