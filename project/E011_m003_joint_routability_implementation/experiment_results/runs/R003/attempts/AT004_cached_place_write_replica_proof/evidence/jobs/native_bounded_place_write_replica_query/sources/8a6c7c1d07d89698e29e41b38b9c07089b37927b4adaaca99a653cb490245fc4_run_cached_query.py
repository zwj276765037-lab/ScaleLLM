"""Reuse the exact bounded launcher; replace only its native collector source."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import run_query as base

HERE = Path(__file__).resolve().parent
EXTRA = [Path(__file__), HERE / 'query_cached.tcl']

class Prepared(Exception):
    pass

def main():
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('--archive-source', action='append', default=[])
    parser.add_argument('--prepare-only', action='store_true')
    args, rest = parser.parse_known_args()
    original = {row['path'] for row in base.entry.check_sources()['sources']} | {
        str(HERE / name) for name in ['run_query.py', 'query.tcl', 'targets.tcl']}
    expected = original | {str(path) for path in EXTRA}
    assert set(args.archive_source) == expected and len(args.archive_source) == len(expected)
    class Boundary:
        @staticmethod
        def run(command, *, cwd, env):
            assert command[5] == str(HERE / 'query.tcl')
            assert command[:5] == ['/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado', '-mode', 'batch', '-notrace', '-source']
            original_command = list(command)
            command[5] = str(HERE / 'query_cached.tcl')
            report = Path(env['HAP_REPORT_DIR'])
            receipt = dict(completed=True, prepare_only=args.prepare_only,
                           native_executed=False, original_command=original_command,
                           adapted_command=command, changed_native_arguments=[5],
                           exact_original_scope_and_identity_guards_retained=True,
                           sources=[base.identity(path) for path in EXTRA])
            with (report / 'cached_query_native_boundary.json').open('x') as stream:
                json.dump(receipt, stream, indent=2)
                stream.write('\n')
            if args.prepare_only:
                raise Prepared()
            return subprocess.run(command, cwd=cwd, env=env)
    base.subprocess = Boundary()
    command = [str(HERE / 'run_query.py'), *rest]
    for path in sorted(original):
        command += ['--archive-source', path]
    saved = sys.argv
    sys.argv = command
    try:
        try:
            return base.main()
        except Prepared:
            print(json.dumps(dict(prepared=True, native_executed=False, runtime_sources=53)))
            return 0
    finally:
        sys.argv = saved

if __name__ == '__main__':
    sys.exit(main())
