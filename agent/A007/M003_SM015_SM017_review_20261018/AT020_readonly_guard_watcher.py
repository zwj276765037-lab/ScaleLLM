"""Observe adopted AT020 protection; never signal, acquire a lock, or run EDA.

This emits evidence only. The active A007 agent must actually wake A006.
The original final-CLK/complete/error watcher remains separately active.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[3]
OWN = Path(__file__).resolve().parent
GUARD = ROOT / 'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT020_fresh_core_state_source_semantics/evidence/adopted_supervision_v1'
LOCK = ROOT / 'project/hardware/vivado/.m002_eda.lock'
PID, START = 137896, 5431142
LOCK_DEVICE, LOCK_INODE = 66306, 169247080
INTERVAL, STALE = 15, 120
LIMIT = 131072


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def process(pid):
    try:
        text = Path(f'/proc/{pid}/stat').read_text()
        f = text[text.rfind(')') + 2:].split()
        return dict(exists=True, state=f[0], ppid=int(f[1]), pgrp=int(f[2]), session=int(f[3]), start_ticks=int(f[19]))
    except FileNotFoundError:
        return dict(exists=False)


def small(path):
    try:
        with path.open('rb') as f:
            b = f.read(LIMIT + 1)
        result = dict(exists=True, bytes=len(b), truncated=len(b) > LIMIT, sha256_bounded=hashlib.sha256(b[:LIMIT]).hexdigest())
        if not result['truncated']:
            try:
                result['json'] = json.loads(b)
            except (ValueError, UnicodeError) as exc:
                result['parse_error'] = str(exc)
        return result
    except FileNotFoundError:
        return dict(exists=False)


def snapshot():
    s = dict(utc=utc(), guard=process(PID), heartbeat=small(GUARD / 'heartbeat.json'), monitor_error=small(GUARD / 'monitor_error.json'), status=small(GUARD / 'status.json'), lock_released=small(GUARD / 'lock_released.json'))
    st = LOCK.stat()
    key = f'{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x}:{st.st_ino}'
    lines = [line for line in Path('/proc/locks').read_text().splitlines() if key in line.split()]
    s['lock'] = dict(device=st.st_dev, inode=st.st_ino, lines=lines, owned=any(line.split()[1:6] == ['FLOCK', 'ADVISORY', 'WRITE', str(PID), key] for line in lines))
    return s


def triggers(s, unchanged_seconds):
    out = []
    p = s['guard']
    if not p.get('exists') or p.get('start_ticks') != START or p.get('state') in {'Z', 'X'}:
        out.append('guard_missing_mismatched_or_dead')
    if s['lock'].get('device') != LOCK_DEVICE or s['lock'].get('inode') != LOCK_INODE or not s['lock'].get('owned'):
        out.append('guard_lock_missing_or_replaced')
    for name in ['monitor_error', 'status', 'lock_released']:
        if s[name].get('exists'):
            out.append(name)
    hb = s['heartbeat']
    if not hb.get('exists') or hb.get('truncated') or 'json' not in hb:
        out.append('heartbeat_missing_or_invalid')
    else:
        try:
            j = hb['json']
            age = (datetime.datetime.fromisoformat(s['utc']) - datetime.datetime.fromisoformat(j['utc'])).total_seconds()
            if j.get('guard_pid') != PID or j.get('lock_held') is not True:
                out.append('heartbeat_identity_or_lock_invalid')
            if age > STALE or age < -30 or unchanged_seconds > STALE:
                out.append('guard_heartbeat_stale_or_clock_invalid')
        except (KeyError, TypeError, ValueError):
            out.append('heartbeat_invalid_fields')
    return out


def publish(name, value):
    p = OWN / name
    with p.open('x') as f:
        json.dump(value, f, indent=2)
        f.write('\n')
    return dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def main():
    own = process(os.getpid())
    start = dict(schema='A007_AT020_guard_readonly_watcher_start_v1', utc=utc(), pid=os.getpid(), start_ticks=own['start_ticks'], nice=os.getpriority(os.PRIO_PROCESS, 0), cpus=sorted(os.sched_getaffinity(0)), script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), expected_guard_pid=PID, expected_guard_start_ticks=START, interval_seconds=INTERVAL, heartbeat_alert_after_seconds=STALE, heartbeat_timeout_is_alert_only=True, no_native_wall_or_quiet_stop=True, no_process_control_or_EDA_lock=True, small_read_limit_bytes=LIMIT)
    receipt = publish('AT020_guard_readonly_watcher_start.json', start)
    print(json.dumps(dict(event='guard_observer_started', receipt=receipt, pid=os.getpid(), start_ticks=own['start_ticks'])), flush=True)
    last_digest, last_change = None, time.monotonic()
    while True:
        try:
            s = snapshot()
            digest = s['heartbeat'].get('sha256_bounded')
            if digest != last_digest:
                last_digest, last_change = digest, time.monotonic()
            changes = triggers(s, time.monotonic() - last_change)
        except Exception as exc:
            s = dict(utc=utc(), observer_error_type=type(exc).__name__, observer_error=str(exc))
            changes = ['observer_error_requires_owner_attention']
        if changes:
            event = dict(schema='A007_AT020_guard_dependency_change_v1', observed_utc=utc(), watcher_pid=os.getpid(), watcher_start_ticks=own['start_ticks'], triggers=changes, snapshot=s, owner_action='Active A007 must call collaboration.followup_task to A006; no signal or automatic stop is authorized by this alert.', G4=False)
            receipt = publish('AT020_guard_dependency_change_event.json', event)
            print(json.dumps(dict(event='guard_dependency_changed', receipt=receipt, triggers=changes)), flush=True)
            return 0
        time.sleep(INTERVAL)


if __name__ == '__main__':
    raise SystemExit(main())
