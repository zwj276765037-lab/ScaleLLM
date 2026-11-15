#!/usr/bin/env python3
"""Capture final bus-skew evidence with resource protection and cumulative time accounting."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
GIB = 1024 ** 3
spec = importlib.util.spec_from_file_location('audit_board_helpers', ROOT / 'scripts/run_board.py')
board = importlib.util.module_from_spec(spec)
spec.loader.exec_module(board)


def dump(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def read_progress(path):
    for attempt in range(5):
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            if attempt == 4:
                raise
            time.sleep(0.05)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkpoint', type=Path)
    parser.add_argument('--candidate', choices=('dsp_raw_only', 'dsp_all'), required=True)
    parser.add_argument('--attempt', choices=('checkpoint_001', 'backup_all_001'), default='checkpoint_001')
    args = parser.parse_args()
    parent_out = HERE / args.attempt / args.candidate
    source = args.checkpoint.resolve()
    if not source.is_relative_to(parent_out) or source.name != 'routed.dcp':
        raise ValueError('Select the fixed final routed checkpoint from this recovery')
    progress_path = parent_out / 'progress.json'
    progress = read_progress(progress_path)
    if progress['phase'] not in ('route_review', 'hold_review'):
        raise ValueError('Primary native session must be waiting after final route/hold reports')
    category = 'hold' if progress['phase'] == 'hold_review' else 'implementation'
    primary_pid = int(progress['pid'])
    primary_command = (Path('/proc') / str(primary_pid) / 'cmdline').read_bytes()
    native_script = b'resume_checkpoint.tcl' if args.attempt == 'checkpoint_001' else b'resume_all_backup.tcl'
    if native_script not in primary_command:
        raise ValueError('Primary native recovery identity differs')
    route_console_bytes = (parent_out / 'console.log').read_bytes()
    log = route_console_bytes.decode(errors='replace')
    pins = sorted(set(re.findall(r'^\s*(scalellm_final_decode16_bd_i/\S+/dest_hsdata_ff_reg\[\d+\]/D)\s*$', log, re.M)))
    if len(pins) != 9:
        raise ValueError('Expected the nine exact unpopulated bus-skew endpoints')
    out = parent_out / 'final_bus_skew_audit'
    out.mkdir(exist_ok=False)
    console_snapshot = out / 'source_route_console.log'
    console_snapshot.write_bytes(route_console_bytes)
    pin_list = out / 'requested_pins.txt'
    pin_list.write_text('\n'.join(pins) + '\n')
    digest = board.sha(source)
    inputs = dict(candidate=args.candidate, source_checkpoint=str(source), source_sha256=digest,
        source_native_inputs_sha256=board.sha(parent_out / 'stage_inputs.json'),
        original_route_console_sha256=board.sha(console_snapshot),
        original_route_console_size_bytes=len(route_console_bytes), source_console_snapshot=str(console_snapshot),
        audit_tcl_sha256=board.sha(HERE / 'bus_skew_audit.tcl'),
        audit_driver_sha256=board.sha(Path(__file__)), requested_pins=pins,
        shared_accounting_category=category, fixed_wall_time_termination=False,
        starting_cumulative_seconds=progress['cumulative_seconds'], primary_pid=primary_pid)
    authorization_path = parent_out / 'guardian_handoff/user_authorization.json'
    if authorization_path.is_file():
        inputs['effective_wall_time_authorization'] = dict(path=str(authorization_path), sha256=board.sha(authorization_path))
    dump(out / 'stage_inputs.json', inputs)
    config = json.loads((ROOT / 'runs' / args.candidate / 'build.json').read_text())
    env = os.environ.copy()
    env.update(AUDIT_OUT=str(out), AUDIT_DCP=str(source), AUDIT_DCP_SHA256=digest,
        AUDIT_PIN_LIST=str(pin_list), HAP_HW_ROOT=str(ROOT / 'runs' / args.candidate / 'source/project/hardware'),
        HAP_JOBS='32', OMP_NUM_THREADS='32')
    command = [config['vivado'], '-mode', 'batch', '-notrace', '-source', str(HERE / 'bus_skew_audit.tcl'),
               '-log', str(out / 'vivado.log'), '-journal', str(out / 'vivado.jou')]
    if board.mem_available() < 64 * GIB or shutil.disk_usage(out).free < 30 * GIB:
        raise RuntimeError('Insufficient memory or disk for the final audit')
    def setup():
        os.sched_setaffinity(0, set(range(96)))
        os.nice(10)
    started = time.monotonic()
    peak = 0
    stop_reason = None
    with (out / 'console.log').open('w') as console:
        process = subprocess.Popen(command, cwd=out, env=env, stdout=console,
            stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=setup)
        try:
            while process.poll() is None:
                current = read_progress(progress_path)
                rss = board.process_tree(process.pid) + board.process_tree(primary_pid)
                peak = max(peak, rss)
                if rss > 384 * GIB:
                    stop_reason = 'combined recovery and audit RSS limit'
                elif board.mem_available() < 64 * GIB or shutil.disk_usage(out).free < 30 * GIB:
                    stop_reason = 'system memory or disk floor'
                dump(out / 'progress.json', dict(pid=process.pid, guardian_pid=os.getpid(), fixed_wall_time_termination=False, phase='read_only_final_bus_skew',
                    status='RUNNING', combined_rss_bytes=rss, shared_cumulative_seconds=current['cumulative_seconds']))
                if stop_reason:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                    break
                time.sleep(5)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=15)
    text = (out / 'console.log').read_text(errors='replace')
    captured = process.returncode == 0 and stop_reason is None and 'FINAL_BUS_SKEW_AUDIT_CAPTURED' in text
    dump(out / 'progress.json', dict(pid=process.pid, status='CAPTURED' if captured else 'FAIL', result=str(out/'result.json')))
    result = dict(status='CAPTURED' if captured else 'FAIL', returncode=process.returncode,
        stop_reason=stop_reason, elapsed_seconds=time.monotonic()-started,
        peak_combined_rss_bytes=peak, source_checkpoint_sha256=digest,
        source_unchanged=board.sha(source) == digest, stage_inputs_sha256=board.sha(out / 'stage_inputs.json'),
        files={str(p.relative_to(out)): board.sha(p) for p in out.rglob('*') if p.is_file()})
    dump(out / 'result.json', result)
    print(json.dumps(result, indent=2))
    return 0 if captured and result['source_unchanged'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
