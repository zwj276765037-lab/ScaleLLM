"""Explicit E003 authorization and cumulative physical wall budgets (legacy opt-in)."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
from pathlib import Path

PROFILE = 'm002_full_implementation'
CONTRACT = 'mission/M002_ddr_separation_and_timing_recovery/full_implementation_contract_2026-10-15.md'
CONTRACT_SHA = '8461a1ff702b33f95cd03100086d2c1bb58ae590430598adb59818ffa2c0794b'
EXPERIMENT = 'project/E003_m002_full_implementation'
STAGE_SECONDS = 43200
GLOBAL_SECONDS = 86400


def check(condition, message):
    if not condition:
        raise ValueError(message)


def stamp(value):
    return dt.datetime.fromisoformat(value)


def now():
    return dt.datetime.now(dt.timezone.utc)


def save(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(path)


def identity(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size}


def authorization(workspace, stage, attempt, report):
    check(stage in {'place','route'}, 'E003 authorizes only physical stages')
    expected = workspace / EXPERIMENT / 'experiment_results/runs' / ('R002' if stage == 'place' else 'R003') / 'attempts'
    check(attempt.parent == expected and attempt.name.startswith('AT'), 'E003 stage/attempt root mismatch')
    contract = identity(workspace / CONTRACT)
    check(contract['sha256'] == CONTRACT_SHA, 'E003 authorization contract identity changed')
    return {'profile': PROFILE, 'contract': contract, 'user_instruction': '进行一次完整的implementation',
            'stage': stage, 'managed_attempt': str(attempt), 'report': str(report),
            'stage_cumulative_seconds': STAGE_SECONDS, 'global_wall_seconds': GLOBAL_SECONDS,
            'single_bounded_restart': False, 'workspace': str(workspace)}


def budget(workspace, stage, current_time=None):
    """Called under the exclusive EDA lane lock; no unfinished attempt is free."""
    current_time = current_time or now()
    base = workspace / EXPERIMENT / 'experiment_results'
    used = 0.0
    launches = []
    for run in ('R002','R003'):
        for command in sorted((base / 'runs' / run / 'attempts').glob('AT*/command.json')):
            meta = json.loads(command.read_text())
            check(meta.get('execution_profile') == PROFILE, 'foreign command in E003 physical ledger')
            status_path = command.parent / 'status.json'
            check(status_path.is_file(), 'unclosed E003 attempt; account its actual cost before restart')
            status = json.loads(status_path.read_text())
            check(status.get('execution_state') == 'completed' and not status.get('owned_survivors'), 'unclosed E003 process ownership')
            elapsed = (stamp(status['ended_utc']) - stamp(meta['started_utc'])).total_seconds()
            check(elapsed >= 0 and status['stage'] == meta['stage'], 'invalid E003 stage cost')
            if meta['stage'] == stage:
                used += elapsed
            launch = command.parent / 'actual_eda_started.json'
            if launch.exists():
                launches.append(json.loads(launch.read_text()))
    anchor_path = base / 'physical_budget_anchor.json'
    anchor = json.loads(anchor_path.read_text()) if anchor_path.exists() else None
    if launches:
        earliest = min(launches, key=lambda row: stamp(row['launched_utc']))
        check(anchor == earliest, 'E003 first actual EDA anchor missing/changed')
    elif anchor:
        raise ValueError('E003 budget anchor without actual launch receipt')
    stage_remaining = STAGE_SECONDS - used
    deadline = stamp(anchor['launched_utc']) + dt.timedelta(seconds=GLOBAL_SECONDS) if anchor else None
    global_remaining = (deadline-current_time).total_seconds() if deadline else GLOBAL_SECONDS
    effective = min(stage_remaining, global_remaining)
    check(effective > 0, 'E003 cumulative/global physical budget exhausted')
    return {'stage_used_seconds': used, 'stage_remaining_seconds': stage_remaining,
            'global_anchor': anchor, 'global_deadline_utc': deadline.isoformat() if deadline else None,
            'global_remaining_seconds': global_remaining, 'effective_timeout_seconds': effective}


def report_authorization(report):
    path = report / 'execution_authorization.json'
    if not path.exists():
        return None
    value = json.loads(path.read_text())
    expected = authorization(Path(value['workspace']), value['stage'], Path(value['managed_attempt']), report)
    check(value == expected, 'E003 report authorization changed')
    attempt = Path(value['managed_attempt'])
    check(json.loads((attempt/'execution_authorization.json').read_text()) == expected, 'E003 manager authorization mismatch')
    command = json.loads((attempt/'command.json').read_text())
    check(command.get('execution_profile') == PROFILE and command.get('stage') == value['stage'] and
          command.get('report') == str(report) and command.get('authorization') == identity(attempt/'execution_authorization.json'),
          'E003 manager command/profile binding mismatch')
    return value


def record_launch(report, pid):
    auth = report_authorization(report)
    check(auth is not None, 'actual launch needs E003 authorization')
    attempt = Path(auth['managed_attempt'])
    receipt = {'profile': PROFILE, 'managed_attempt': str(attempt), 'report': str(report),
               'pid': pid, 'launched_utc': now().isoformat(), 'contract_sha256': CONTRACT_SHA}
    anchor = Path(auth['workspace']) / EXPERIMENT / 'experiment_results/physical_budget_anchor.json'
    if not anchor.exists():
        save(anchor, receipt)
    save(report/'actual_eda_started.json', receipt)
    # Publish the manager-visible receipt last, after its required anchor exists.
    save(attempt/'actual_eda_started.json', receipt)
    return receipt


def require_complete_route(counts):
    check(counts['routable'] > 0 and counts['fully_routed'] == counts['routable'] and
          all(counts[k] == 0 for k in ('unrouted','partially_routed','routing_errors')), 'E003 route is not fully routed')
