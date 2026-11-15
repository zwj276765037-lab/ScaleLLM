#!/usr/bin/env python3
"""Adopt an active Vivado session with resource-only protection and accurate elapsed accounting."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import time

GIB = 1024 ** 3
HERE = Path(__file__).resolve().parent


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    temporary.replace(path)


def read_json(path):
    for attempt in range(5):
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            if attempt == 4:
                raise
            time.sleep(0.05)


def processes():
    rows = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            text = (entry / 'stat').read_text()
            fields = text[text.rindex(')') + 2:].split()
            rows[int(entry.name)] = dict(state=fields[0], parent=int(fields[1]),
                group=int(fields[2]), start=int(fields[19]),
                rss=int(fields[21]) * os.sysconf('SC_PAGE_SIZE'))
        except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError):
            continue
    return rows


def command(pid):
    return (Path('/proc') / str(pid) / 'cmdline').read_bytes().replace(b'\0', b' ').decode()


def available_memory():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):
            return int(line.split()[1]) * 1024
    raise RuntimeError('Linux MemAvailable unavailable')


def category(phase):
    if phase in ('bitstream', 'complete'):
        return 'bitstream'
    if phase in ('hold-sll', 'hold', 'hold_review'):
        return 'hold'
    return 'implementation'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--controller', type=int, required=True)
    parser.add_argument('--native', type=int, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to(HERE):
        raise ValueError('Recovery output must be inside native_resume')
    policy = out / 'guardian_handoff'
    policy.mkdir(exist_ok=False)
    lease = (policy / 'owner.lock').open('a')
    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    rows = processes()
    old = rows[args.controller]
    native = rows[args.native]
    old_command = command(args.controller)
    native_command = command(args.native)
    if 'run_all_backup.py' not in old_command or 'resume_all_backup.tcl' not in native_command:
        raise ValueError('Controller/native command identity mismatch')
    if native['parent'] != args.controller or native['group'] != args.native or old['group'] == args.native:
        raise ValueError('Expected independent native process group')
    if (Path('/proc') / str(args.controller)).stat().st_uid != os.getuid():
        raise ValueError('Controller owner mismatch')
    if not (out.parent / 'route_go.txt').is_file() or (out / 'phase.txt').read_text().strip() != 'route':
        raise ValueError('Transfer requires the already-started normal route')
    authorization = dict(user_instruction='已因累计8小时实现时限而停止，不要设置强行停止',
        scope='Current all-DSP implementation and subsequent reports, hold repair and bitstream',
        fixed_wall_time_termination=False,
        retained_guards=dict(combined_rss_gib=384, minimum_mem_available_gib=64, minimum_disk_free_gib=30,
                             native_tool_failures='preserved and handled by the existing physical acceptance rules'),
        historical_raw_stop_receipt=str(HERE / 'checkpoint_001/dsp_raw_only/result.json'),
        historical_raw_stop_sha256=sha(HERE / 'checkpoint_001/dsp_raw_only/result.json'),
        utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    atomic_json(policy / 'user_authorization.json', authorization)
    # Sample resources before suspending the old owner. The successor is already running.
    initial_memory = available_memory()
    initial_disk = shutil.disk_usage(out).free
    os.kill(args.controller, signal.SIGSTOP)
    while True:
        current = processes().get(args.controller)
        if current is None or current['start'] != old['start']:
            raise RuntimeError('Original controller identity disappeared during transfer')
        if current['state'] in ('T', 't'):
            break
        time.sleep(0.01)
    # Only this Python PID was suspended. Vivado remains in its separate process group.
    prior_bytes = (out / 'progress.json').read_bytes()
    (policy / 'prior_progress.json').write_bytes(prior_bytes)
    prior = json.loads(prior_bytes)
    cumulative = dict(prior['cumulative_seconds'])
    phase = (out / 'phase.txt').read_text().strip()
    cumulative[category(phase)] += max(0.0, time.time() - (out / 'progress.json').stat().st_mtime)
    last_tick = time.monotonic()
    owner = dict(active=True, owner_pid=os.getpid(), owner_start=processes()[os.getpid()]['start'],
        old_controller_pid=args.controller, old_controller_start=old['start'], old_controller_state='T',
        native_root_pid=args.native, native_group=args.native, fixed_wall_time_termination=False)
    atomic_json(policy / 'owner.json', owner)
    atomic_json(policy / 'stage_inputs.json', dict(controller_pid=args.controller,
        controller_start=old['start'], controller_command=old_command,
        native_pid=args.native, native_start=native['start'], native_command=native_command,
        original_stage_inputs_sha256=sha(out / 'stage_inputs.json'),
        original_controller_sha256=sha(HERE / 'run_all_backup.py'),
        successor_guardian_sha256=sha(Path(__file__)),
        authorization_sha256=sha(policy / 'user_authorization.json'),
        prior_progress_sha256=sha(policy / 'prior_progress.json'),
        initial_mem_available_bytes=initial_memory, initial_disk_free_bytes=initial_disk))
    print('RESOURCE_ONLY_GUARDIAN_ACTIVE', os.getpid(), 'OLD_CONTROLLER_STOPPED', args.controller,
          'NATIVE_GROUP_UNINTERRUPTED', args.native, flush=True)
    peak = 0
    minimum_memory = initial_memory
    minimum_disk = initial_disk
    stop_reason = None
    termination_started = None
    events = []
    while True:
        now = time.monotonic()
        cumulative[category(phase)] += now - last_tick
        last_tick = now
        phase = (out / 'phase.txt').read_text().strip()
        rows = processes()
        old_now = rows.get(args.controller)
        if old_now is None or old_now['start'] != old['start']:
            raise RuntimeError('Suspended controller identity changed')
        if old_now['state'] not in ('T', 't'):
            os.kill(args.controller, signal.SIGSTOP)
            events.append(dict(event='reassert_suspended_old_controller', utc=time.time()))
        active_native = {pid for pid, row in rows.items()
                         if row['group'] == args.native and row['state'] not in ('Z', 'X')}
        selected = {args.controller, os.getpid()} | active_native
        audit_progress = out / 'final_bus_skew_audit/progress.json'
        if audit_progress.is_file():
            audit = read_json(audit_progress)
            if audit.get('status') == 'RUNNING':
                for key in ('pid', 'guardian_pid'):
                    pid = audit.get(key)
                    if pid in rows:
                        selected.add(pid)
        while True:
            children = {pid for pid, row in rows.items() if row['parent'] in selected}
            if children <= selected:
                break
            selected.update(children)
        rss = sum(rows.get(pid, {}).get('rss', 0) for pid in selected)
        memory = available_memory()
        disk = shutil.disk_usage(out).free
        peak = max(peak, rss)
        minimum_memory = min(minimum_memory, memory)
        minimum_disk = min(minimum_disk, disk)
        state = dict(prior, phase=phase, status='RUNNING' if active_native else 'TOOL_EXITED_PENDING_REAP',
            cumulative_seconds=cumulative, tree_rss_bytes=rss, peak_tree_rss_bytes=peak,
            stop_reason=stop_reason, fixed_wall_time_termination=False,
            effective_guardian_pid=os.getpid(), effective_guardian=str(Path(__file__)),
            old_controller_pid=args.controller, old_controller_state='T',
            minimum_mem_available_bytes=minimum_memory, minimum_disk_free_bytes=minimum_disk)
        atomic_json(policy / 'progress.json', state)
        atomic_json(out / 'progress.json', state)
        if not active_native:
            break
        if stop_reason is None:
            if rss > 384 * GIB:
                stop_reason = 'combined task RSS limit'
            elif memory < 64 * GIB:
                stop_reason = 'available memory floor'
            elif disk < 30 * GIB:
                stop_reason = 'free disk floor'
            if stop_reason:
                events.append(dict(event='resource_protection_stop', reason=stop_reason, utc=time.time()))
                os.killpg(args.native, signal.SIGTERM)
                termination_started = time.monotonic()
        if termination_started is not None and time.monotonic() - termination_started > 15:
            os.killpg(args.native, signal.SIGKILL)
        atomic_json(policy / 'events.json', events)
        time.sleep(1)
    # Freeze all successor evidence before the legacy owner scans final files.
    atomic_json(policy / 'before_reap_snapshot.json', dict(cumulative_seconds=cumulative,
        phase=phase, stop_reason=stop_reason, peak_combined_rss_bytes=peak,
        minimum_mem_available_bytes=minimum_memory, minimum_disk_free_bytes=minimum_disk,
        native_group_active=False))
    owner['active'] = False
    owner['state'] = 'native_group_finished_legacy_reap_only'
    atomic_json(policy / 'owner.json', owner)
    atomic_json(policy / 'events.json', events)
    os.kill(args.controller, signal.SIGCONT)
    while True:
        old_now = processes().get(args.controller)
        if (out / 'result.json').is_file() and (old_now is None or old_now['state'] in ('Z', 'X')):
            break
        time.sleep(1)
    legacy = read_json(out / 'result.json')
    success = legacy['returncode'] == 0 and legacy['native_pass_marker'] and stop_reason is None
    final = dict(status='PASS' if success else 'FAIL', native_returncode=legacy['returncode'],
        native_pass_marker=legacy['native_pass_marker'], stop_reason=stop_reason,
        fixed_wall_time_termination=False, accurate_cumulative_seconds=cumulative,
        peak_combined_rss_bytes=peak, minimum_mem_available_bytes=minimum_memory,
        minimum_disk_free_bytes=minimum_disk, legacy_result_sha256=sha(out / 'result.json'),
        legacy_cumulative_seconds=legacy['cumulative_seconds'],
        legacy_time_interpretation='Legacy controller was suspended after handoff and resumed solely to reap the real child exit code; its final elapsed counters retain the pre-handoff accounting.',
        authorization_sha256=sha(policy / 'user_authorization.json'),
        effective_guardian_sha256=sha(Path(__file__)), frozen_before_reap_sha256=sha(policy / 'before_reap_snapshot.json'))
    atomic_json(policy / 'final_result.json', final)
    print('RESOURCE_ONLY_GUARDIAN_FINISHED', json.dumps(final, ensure_ascii=False), flush=True)
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
