#!/usr/bin/env python3
"""Launch the reviewed E007 runner only after the real E006 readiness record."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'agent/A006/slr2_input_locality'
MANIFEST = SOURCE / 'prepared_manifest.json'
EXPECTED_MANIFEST = 'b049e0f6897d2c49e3a61154053023c6ca7216ed5d19fe2d89f68c96be7aa059'


def identity(path):
    data = Path(path).read_bytes()
    return dict(path=str(Path(path).resolve()), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--e006-closeout', type=Path, required=True)
    args = parser.parse_args()
    closeout_path = args.e006_closeout.resolve()
    closeout = json.loads(closeout_path.read_text())
    assert closeout.get('phase') == 'E006_attribution_closed'
    assert closeout.get('successor') == 'SM011/E007'
    assert closeout.get('engineering_execution_verified') is True
    assert closeout.get('candidate_scope_supported') is True
    assert closeout.get('evidence')
    for row in [closeout['terminal_status'], *closeout['evidence']]:
        assert identity(row['path']) == row, row['path']
    assert identity(MANIFEST)['sha256'] == EXPECTED_MANIFEST, 'Reviewed preparation manifest changed'
    attempt = ROOT / 'project/E007_m002_slr2_input_locality_implementation/experiment_results/runs/R002/attempts/AT001_pre_place_SLR2_full_implementation'
    report = ROOT / 'project/hardware/vivado/reports/m002_E007_R002_AT001_pre_place_SLR2_full_implementation'
    receipt = ROOT / 'agent/A006/detached_E007_R002_AT001_pre_place_SLR2_full_implementation.json'
    log = ROOT / 'agent/A006/E007_R002_AT001_pre_place_SLR2_full_implementation_supervisor.log'
    assert not any(path.exists() for path in [attempt, report, receipt, log]), 'Never reuse runtime evidence paths'
    argv = ['taskset', '-c', '0-7', 'nice', '-n', '5', '/usr/bin/python3',
            str(SOURCE / 'run_candidate.py'), '--attempt', str(attempt),
            '--report', str(report), '--e006-closeout', str(closeout_path)]
    with log.open('xb') as stream:
        child = subprocess.Popen(argv, cwd=ROOT, start_new_session=True, close_fds=True,
                                 stdin=subprocess.DEVNULL, stdout=stream,
                                 stderr=subprocess.STDOUT)
    time.sleep(0.3)
    try:
        fields = Path('/proc', str(child.pid), 'stat').read_text().rsplit(')', 1)[1].split()
        process = dict(pid=child.pid, start_ticks=int(fields[19]),
                       ppid=int(fields[1]), pgrp=int(fields[2]), nice=int(fields[16]))
    except FileNotFoundError:
        process = None
    result = dict(launched_utc=datetime.now(timezone.utc).isoformat(), argv=argv,
                  cwd=str(ROOT), supervisor_pid=child.pid,
                  supervisor_proc_identity=process, poll=child.poll(),
                  attempt=str(attempt), report=str(report), stdio_log=str(log),
                  prepared_manifest=identity(MANIFEST), E006_readiness=identity(closeout_path),
                  launcher_source=identity(__file__),
                  mechanism='Detached Popen session; DEVNULL stdin; file stdout/stderr; taskset0-7/nice5; reviewed runner performs nonblocking lane/PID/input/native admission',
                  limitation='Launch receipt only; actual started.json/native PID/checkpoint read must be verified separately')
    with receipt.open('x') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(receipt=str(receipt), **result), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
