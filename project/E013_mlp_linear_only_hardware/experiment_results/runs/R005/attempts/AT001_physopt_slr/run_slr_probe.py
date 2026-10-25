#!/usr/bin/env python3
"""Collect read-only SLR evidence from an immutable, terminal M006 attempt."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[4]
HW = ROOT / 'project/hardware'
E013 = ROOT / 'project/E013_mlp_linear_only_hardware'
VIVADO = Path('/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado')
GIB = 1024 ** 3


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def terminal_gate(result, owned, launch):
    if result.get('execution_state') not in {'completed', 'failed'}:
        raise ValueError('Parent attempt is not terminal')
    rc = result.get('native_returncode')
    if type(rc) is not int or rc not in {0, 1}:
        raise ValueError('Parent has no ordinary Vivado 0/1 exit; signal/unknown termination is ineligible')
    expected = 'NATIVE_STAGE_COMPLETED' if result['execution_state'] == 'completed' else 'FAIL'
    if result.get('verdict') != expected or (expected == 'NATIVE_STAGE_COMPLETED' and rc != 0):
        raise ValueError('Parent native exit/execution/verdict disagree')
    if result.get('stop_reason') is not None or result.get('changed_inputs') != []:
        raise ValueError('Parent did not terminate naturally with stable inputs')
    if owned.get('survivors') != [] or owned.get('session') != launch.get('session'):
        raise ValueError('Parent ownership has not retired')
    if launch.get('stage') != 'impl':
        raise ValueError('Only an actual M006 implementation attempt is accepted')
    # A natural FAIL remains FAIL. This gate licenses diagnostics, never reuse
    # as a successful synthesis/implementation producer.


def proc_snapshot():
    rows = {}
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            f = path.read_text().rpartition(')')[2].split()
            if f[0] == 'Z':
                continue
            rss = next((int(x.split()[1]) * 1024 for x in
                        (path.parent / 'status').read_text().splitlines()
                        if x.startswith('VmRSS:')), 0)
            rows[int(path.parent.name)] = dict(ppid=int(f[1]), sid=int(f[3]),
                                               birth=f[19], rss=rss)
        except (OSError, ValueError, IndexError):
            pass
    return rows


def discover_owned(rows, owned, sid, minimum_birth):
    live = {pid for pid, birth in owned.items()
            if pid in rows and rows[pid]['birth'] == birth}
    live |= {pid for pid, row in rows.items()
             if row['sid'] == sid and int(row['birth']) >= minimum_birth}
    while True:
        extra = {pid for pid, row in rows.items() if row['ppid'] in live}
        if extra <= live:
            break
        live |= extra
    for pid in live:
        # A reused PID is adopted only when its *current* session/ancestry
        # independently proved ownership above, never from the old PID alone.
        owned[pid] = rows[pid]['birth']
    live = {pid for pid in live if rows[pid]['birth'] == owned[pid]}
    return live, sum(rows[pid]['rss'] for pid in live)


def assess_collection(report, rc, stop, survivors, changed):
    report = Path(report)
    sections_file = report / 'sections.tsv'
    sections = []
    if sections_file.is_file():
        for line in sections_file.read_text().splitlines()[1:]:
            parts = line.split('\t', 2)
            if len(parts) < 2:
                raise ValueError('Malformed native section record')
            sections.append(dict(section=parts[0], status=parts[1],
                                 detail=parts[2] if len(parts) > 2 else ''))
    required = ['design_identity.txt', 'scopes.tsv', 'path_samples.tsv', 'sections.tsv']
    missing = [name for name in required if not (report / name).is_file()]
    native_log = (report / 'vivado.log').read_text(errors='replace') if (report / 'vivado.log').is_file() else ''
    ended = 'M006_SLR_DIAGNOSTIC_COLLECTION_DONE' in native_log
    success = (rc == 0 and stop is None and not survivors and not changed and ended
               and not missing and bool(sections))
    required_sections = {'route_status', 'utilization_slr', 'crossing_global',
                         'slice_sites', 'congestion', 'old_windows'}
    absent_sections = sorted(required_sections - {x['section'] for x in sections})
    partial = bool(absent_sections) or any(x['status'] not in {'COLLECTED', 'NO_MATCH'} for x in sections)
    verdict = ('DIAGNOSTICS_PARTIAL' if partial else 'DIAGNOSTICS_COLLECTED') if success else 'FAIL'
    return success, verdict, sections, missing, absent_sections


def select_new_windows(data):
    """At most four deduplicated windows from the last native congestion table.

    Tile coordinates remain names. Only native Vivado device queries may map
    them to SLRs; the CPU parser makes no geometry/module inference.
    """
    # The failed-route witness preamble says "see ... Congestion Report."
    # That reference is not a table header. Match standalone native headers.
    headers = list(re.finditer(rb'(?m)^Congestion Report[ \t]*\r?$', data))
    if not headers:
        return dict(windows=[], table_sha256=None, scope='no_native_congestion_table')
    start = headers[-1].start()
    tail = data[start:]
    end_match = re.search(rb'(?m)^(?:INFO:|WARNING:|Phase [0-9])', tail)
    block = tail[:end_match.start()] if end_match else tail
    preceding = data[max(0, start - 200):start].decode(errors='replace')
    categories = re.findall(r'--(GLOBAL|LONG|SHORT) Congestion:', preceding)
    category = categories[-1] if categories else None
    direction, candidates, detail = None, {}, {}
    for raw in block.decode(errors='replace').splitlines():
        line = raw.strip()
        m = re.match(r'^(GLOBAL|LONG|SHORT) Congestion', line)
        if m:
            category, direction = m.group(1), None
        elif line in {'NORTH', 'SOUTH', 'EAST', 'WEST'}:
            direction = line
        else:
            terminal_direction = re.match(r'^(North|South|East|West) Dir ([0-9]+x[0-9]+) Area, Max Cong = ([0-9.]+)%', line)
            if terminal_direction:
                direction = terminal_direction[1].upper()
                if category:
                    detail[(category, direction)] = dict(native_area=terminal_direction[2],
                                                        native_max_congestion_percent=float(terminal_direction[3]))
                continue
            m = re.match(r'^(INT_X[0-9]+Y[0-9]+)\s*->\s*(INT_X[0-9]+Y[0-9]+)', line)
            if m and category and direction:
                candidates.setdefault((category, direction), (m.group(1), m.group(2)))
    windows, used = [], set()
    order = [('GLOBAL', 'EAST'), ('SHORT', 'NORTH'), ('GLOBAL', 'NORTH'), ('GLOBAL', 'SOUTH')]
    for key in order + [k for k in candidates if k not in order]:
        pair = candidates.get(key)
        if pair and pair not in used:
            windows.append(dict(label='latest_' + '_'.join(key).lower(), lower_left=pair[0],
                                upper_right=pair[1], **detail.get(key, {})))
            used.add(pair)
        if len(windows) == 4:
            break
    return dict(windows=windows, table_sha256=hashlib.sha256(block).hexdigest(),
                parent_log_byte_offset=start, table_bytes=len(block),
                scope='last_native_report_representative_sample_max4_not_all_hotspots')


def validate_parent(parent, stage):
    parent = Path(parent).resolve()
    if not parent.is_relative_to(E013 / 'experiment_results/runs/R004/attempts'):
        raise ValueError('Parent must be an M006 R004 attempt in the new root')
    needed = ['result.json', 'launch.json', 'owned_processes.json', 'input_manifest.json']
    if any(not (parent / n).is_file() for n in needed):
        raise ValueError('Parent attempt has no complete terminal record')
    result, launch, owned, identity = [json.loads((parent / n).read_text())
                                      for n in needed]
    terminal_gate(result, owned, launch)
    rows = proc_snapshot()
    if any(int(pid) in rows and rows[int(pid)]['birth'] == birth
           for pid, birth in owned.get('pids', {}).items()):
        raise ValueError('A recorded parent-owned process is still live')
    report = (parent / 'native_reports').resolve(strict=True)
    if (not report.is_relative_to(HW / 'vivado/reports') or
            str(report) != launch.get('report')):
        raise ValueError('Parent report identity/root mismatch')
    if sha(parent / 'input_manifest.json') != launch['input_manifest_sha256']:
        raise ValueError('Parent frozen manifest changed')
    files = {str(parent / n): sha(parent / n) for n in needed}
    for rel, expected in identity['files'].items():
        src = (parent / 'source_snapshot' / rel).resolve()
        if not src.is_relative_to(parent / 'source_snapshot') or sha(src) != expected:
            raise ValueError('Parent source snapshot mismatch: ' + rel)
        files[str(src)] = expected
    synth_dcp = Path(launch['synth_dcp']['path']).resolve()
    if not synth_dcp.is_relative_to(HW / 'vivado/reports'):
        raise ValueError('Qualification checkpoint is outside the new root')
    receipt = synth_dcp.parent / 'm006_synth_identity.json'
    if sha(receipt) != launch['synth_receipt_sha256']:
        raise ValueError('Original successful qualification receipt changed')
    receipt_data = json.loads(receipt.read_text())
    if receipt_data.get('verdict') != 'NATIVE_STAGE_COMPLETED':
        raise ValueError('Parent did not originate from successful qualification')
    if (receipt_data.get('dcp') != str(synth_dcp) or
            receipt_data.get('dcp_sha256') != launch['synth_dcp']['sha256'] or
            sha(synth_dcp) != launch['synth_dcp']['sha256'] or
            receipt_data.get('project') != launch.get('project') or
            receipt_data.get('input_manifest_sha256') != launch['input_manifest_sha256']):
        raise ValueError('Qualification checkpoint/project/source identity mismatch')
    files[str(receipt)] = sha(receipt)
    files[str(synth_dcp)] = launch['synth_dcp']['sha256']
    dcp = report / (stage + '.dcp')
    if not dcp.is_file():
        raise ValueError('Selected saved stage DCP is unavailable')
    log = report / 'vivado.log'
    data = log.read_bytes()
    command = {'placed': 'place_design', 'physopt': 'phys_opt_design',
               'routed': 'route_design'}[stage]
    completed = (command + ' completed successfully').encode()
    exported = ("The checkpoint '" + str(dcp) + "' has been generated.").encode()
    if completed not in data or exported not in data or data.index(completed) > data.index(exported):
        raise ValueError('Native completed-stage/export proof missing')
    dcp_sha = sha(dcp)
    name, key = {'placed': ('place_completion_observation.json', 'placed_dcp'),
                 'physopt': ('physopt_completion_route_launch.json', 'physopt_dcp'),
                 'routed': ('route_completion_observation.json', 'routed_dcp')}[stage]
    observation = parent / name
    if not observation.is_file():
        raise ValueError('Saved checkpoint has no historical hash observation')
    o = json.loads(observation.read_text())
    if o[key]['path'] != str(dcp) or o[key]['sha256'] != dcp_sha:
        raise ValueError('Saved checkpoint observation mismatch')
    prefix = o['log_prefix']
    if hashlib.sha256(data[:prefix['bytes']]).hexdigest() != prefix['sha256']:
        raise ValueError('Native log prefix changed after checkpoint observation')
    if stage == 'routed' and (o.get('observed_before_parent_terminal') is not True or
                             o.get('input_manifest_sha256') != launch['input_manifest_sha256'] or
                             o.get('parent_root_birth') != launch['root_birth']):
        raise ValueError('Routed checkpoint observation lacks generation-time parent identity')
    files[str(observation)] = sha(observation)
    files[str(log)] = sha(log)
    files[str(dcp)] = dcp_sha
    return dict(parent=str(parent), original_parent_verdict=result['verdict'],
                original_parent_native_returncode=result['native_returncode'],
                source_stage=stage, dcp=str(dcp), dcp_sha256=dcp_sha,
                parent_input_manifest_sha256=launch['input_manifest_sha256'],
                new_hotspot_selection=select_new_windows(data),
                scope='read_only_saved_stage_diagnostic_not_successful_parent_requalification',
                files=files)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('attempt')
    ap.add_argument('--parent', required=True, type=Path)
    ap.add_argument('--stage', required=True, choices=['placed', 'physopt', 'routed'])
    ap.add_argument('--check-only', action='store_true')
    args = ap.parse_args()
    if not args.attempt or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in args.attempt):
        raise ValueError('Unsafe attempt name')
    origin = validate_parent(args.parent, args.stage)
    if args.check_only:
        print(json.dumps(origin, indent=2))
        return 0
    lock = (HW / 'vivado/.m006_linear_eda.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    evidence = E013 / 'experiment_results/runs/R005/attempts' / args.attempt
    report = HW / 'vivado/reports' / ('m006_slr_' + args.attempt)
    evidence.mkdir(parents=True, exist_ok=False)
    report.mkdir(parents=True, exist_ok=False)
    (evidence / 'native_reports').symlink_to(report, target_is_directory=True)
    script = HERE / 'inspect_slr.tcl'
    frozen = dict(origin['files'])
    for p in [Path(__file__).resolve(), script]:
        frozen[str(p)] = sha(p)
        shutil.copy2(p, evidence / p.name)
    window_input = evidence / 'selected_new_windows.tsv'
    window_input.write_text('label\tlower_left\tupper_right\n' + ''.join(
        '{label}\t{lower_left}\t{upper_right}\n'.format(**w)
        for w in origin['new_hotspot_selection']['windows']))
    frozen[str(window_input)] = sha(window_input)
    write_json(evidence / 'input_manifest.json', dict(origin=origin, files=frozen))
    cpus = sorted(os.sched_getaffinity(0))[:32]
    command = [str(VIVADO), '-mode', 'batch', '-notrace', '-source', str(script),
               '-log', str(report / 'vivado.log'), '-journal', str(report / 'vivado.jou')]
    env = {**os.environ, 'M006_SLR_DCP': origin['dcp'], 'M006_SLR_DCP_SHA': origin['dcp_sha256'],
           'M006_SLR_STAGE': args.stage, 'M006_SLR_REPORT': str(report),
           'M006_SLR_WINDOWS': str(window_input), 'OMP_NUM_THREADS': '8'}
    def setup():
        os.sched_setaffinity(0, cpus)
        os.nice(5)
    meta = dict(started=now(), command=command, cwd=str(HW / 'vivado'), cpus=cpus,
                profile='board_read_only', rss_limit_bytes=192 * GIB,
                mem_available_floor_bytes=64 * GIB, mem_low_grace_seconds=30,
                disk_floor_bytes=30 * GIB, max_threads=8, wall_timeout=None,
                silence_timeout=None, path_sample_cap=400, physical_acceptance='NOT_ASSIGNED')
    owned, peak, low_since, stop = {}, 0, None, None
    with (report / 'console.log').open('w') as log:
        p = subprocess.Popen(command, cwd=HW / 'vivado', env=env, stdout=log,
                             stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=setup)
        sid = p.pid
        f = Path('/proc', str(p.pid), 'stat').read_text().rpartition(')')[2].split()
        minimum_birth = int(f[19]); owned[p.pid] = f[19]
        meta.update(pid=p.pid, session=sid, root_birth=f[19], actual_affinity=sorted(os.sched_getaffinity(p.pid)))
        write_json(evidence / 'launch.json', meta)
        def discover():
            return discover_owned(proc_snapshot(), owned, sid, minimum_birth)
        def terminate_owned():
            deadline = time.monotonic() + 30
            live, _ = discover()
            while live:
                for pid in live:
                    try:
                        os.kill(pid, signal.SIGTERM if time.monotonic() < deadline else signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                time.sleep(.5)
                live, _ = discover()
        try:
            if meta['actual_affinity'] != cpus:
                raise RuntimeError('CPU affinity setup mismatch')
            while True:
                live, rss = discover(); peak = max(peak, rss)
                if p.poll() is not None and not live:
                    break
                mem = next(int(x.split()[1]) * 1024 for x in Path('/proc/meminfo').read_text().splitlines()
                           if x.startswith('MemAvailable:'))
                low_since = (low_since or time.monotonic()) if mem < 64 * GIB else None
                disk = os.statvfs(report)
                if rss > 192 * GIB or disk.f_bavail * disk.f_frsize < 30 * GIB or (low_since and time.monotonic() - low_since >= 30):
                    stop = 'resource_protection'; terminate_owned(); break
                time.sleep(2)
        except BaseException as ex:
            stop = 'monitor_exception:' + repr(ex)
            terminate_owned()
        rc = p.wait()
    survivors, _ = discover()
    write_json(evidence / 'owned_processes.json', dict(pids=owned, survivors=sorted(survivors), session=sid))
    changed = [path for path, expected in frozen.items()
               if not Path(path).is_file() or sha(path) != expected]
    success, verdict, sections, missing, absent_sections = assess_collection(report, rc, stop, survivors, changed)
    result = dict(ended=now(), native_returncode=rc, stop_reason=stop,
                  peak_tree_rss_bytes=peak, changed_inputs=changed,
                  execution_state='completed' if success else 'failed',
                  verdict=verdict, missing_required_artifacts=missing,
                  absent_required_sections=absent_sections,
                  parent_original_verdict=origin['original_parent_verdict'], source_stage=args.stage,
                  physical_acceptance='NOT_ASSIGNED', sections=sections,
                  path_sample_cap=400, path_samples_are_full_population=False)
    write_json(evidence / 'artifact_hashes.json', {str(p): sha(p) for p in report.rglob('*') if p.is_file()})
    write_json(evidence / 'result.json', result)
    print(json.dumps(result))
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
