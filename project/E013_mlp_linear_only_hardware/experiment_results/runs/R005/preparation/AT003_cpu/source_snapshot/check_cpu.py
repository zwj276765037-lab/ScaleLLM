#!/usr/bin/env python3
"""Freeze and run CPU checks for the read-only evidence entry; no EDA."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PREPARATION = sys.argv[1] if len(sys.argv) == 2 else 'AT001_cpu'
if not re.fullmatch(r'[A-Za-z0-9_-]+', PREPARATION):
    raise ValueError('Unsafe preparation attempt name')
DEST = ROOT / 'project/E013_mlp_linear_only_hardware/experiment_results/runs/R005/preparation' / PREPARATION


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    DEST.mkdir(parents=True, exist_ok=False)
    files = [p for p in HERE.iterdir() if p.suffix in {'.py', '.tcl'}]
    inputs = {str(p): digest(p) for p in sorted(files)}
    (DEST / 'source_snapshot').mkdir()
    for p in files:
        shutil.copy2(p, DEST / 'source_snapshot' / p.name)
    commands = [
        [sys.executable, '-m', 'py_compile', *[str(p) for p in files if p.suffix == '.py']],
        [sys.executable, '-m', 'unittest', 'discover', '-s', str(HERE), '-p', 'test_slr_probe.py', '-v'],
        ['tclsh', str(HERE / 'check_syntax.tcl'), str(HERE / 'inspect_slr.tcl')],
    ]
    results = []
    for index, command in enumerate(commands):
        p = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = DEST / ('check_' + str(index) + '.log')
        log.write_text(p.stdout)
        results.append(dict(command=command, returncode=p.returncode, log=str(log), sha256=digest(log)))
    tcl = (HERE / 'inspect_slr.tcl').read_text()
    prohibited = re.findall(r'(?m)^\s*(?:opt_design|place_design|phys_opt_design|route_design|write_checkpoint|write_bitstream|set_property|read_xdc|create_clock)\b', tcl)
    static = dict(no_design_mutations=not prohibited,
                  max_path_query=100, query_buckets=4, max_returned_path_samples=400,
                  path_samples_are_population=False,
                  native_execution='NOT_EXECUTED')
    stable = all(p.is_file() and digest(p) == expected for name, expected in inputs.items() for p in [Path(name)])
    result = dict(timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  scope='CPU_only_entry_gate_and_source_completeness_not_native_SLR_evidence',
                  commands=results, static=static, input_sha256=inputs, inputs_stable=stable,
                  verdict='PASS' if all(r['returncode'] == 0 for r in results) and not prohibited and stable else 'FAIL')
    (DEST / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0 if result['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
