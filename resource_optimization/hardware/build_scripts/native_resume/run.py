#!/usr/bin/env python3
"""Traceable native-project recovery with cumulative physical-stage resource limits."""
import datetime
import hashlib
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
NAMES = ('dsp_raw_only', 'dsp_all')
CPUS = {'dsp_raw_only': list(range(24)) + list(range(48, 72)),
        'dsp_all': list(range(24, 48)) + list(range(72, 96))}


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    sys.modules[name] = result
    return result


board = module('run_board', 'run_board.py')
qualification = module('requalify_place', 'requalify_place.py')
selector = module('select_candidate', 'select_candidate.py')


def dump(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def elapsed_log(path):
    text = path.read_text(errors='replace')
    begin = re.search(r'Start of session at: (.+)', text)
    end = re.search(r'Exiting Vivado at (.+?)\.\.\.', text)
    if not begin or not end:
        raise ValueError('Incomplete prior physical probe timing: ' + str(path))
    fmt = '%a %b %d %H:%M:%S %Y'
    return (datetime.datetime.strptime(end[1].strip(), fmt) -
            datetime.datetime.strptime(begin[1].strip(), fmt)).total_seconds()


def prior_seconds(work):
    total = 0.0
    evidence = {}
    for folder in sorted(work.iterdir()):
        if not folder.is_dir() or not folder.name.startswith(('place', 'post_place')):
            continue
        receipt = folder / 'result.json'
        if receipt.is_file():
            seconds = float(json.loads(receipt.read_text())['elapsed_seconds'])
            evidence[str(receipt)] = dict(sha256=board.sha(receipt), elapsed_seconds=seconds)
        elif (folder / 'vivado.log').is_file():
            log = folder / 'vivado.log'
            seconds = elapsed_log(log)
            evidence[str(log)] = dict(sha256=board.sha(log), elapsed_seconds=seconds)
        else:
            continue
        total += seconds
    return total, evidence


def load_candidate(name):
    work = ROOT / 'runs' / name
    config = json.loads((work / 'build.json').read_text())
    board.verify_candidate(work, config)
    original = qualification.preserved_place(work)
    for relative, digest in config['source_inputs'].items():
        if relative.startswith('project/hardware/') and board.sha(work / 'source' / relative) != digest:
            raise ValueError('Candidate source changed: ' + relative)
    for filename, digest in config['board_inputs'].items():
        if board.sha(Path(config['board_files']) / filename) != digest:
            raise ValueError('Board input changed: ' + filename)
    run = work / 'create/project/scalellm_final_decode16.runs/impl_1'
    native = run / 'scalellm_final_decode16_bd_wrapper_physopt.dcp'
    previous, prior_evidence = prior_seconds(work)
    files = [work / 'build.json', work / 'candidate_manifest.json',
             work / 'place/result.json', work / 'place/stage_inputs.json',
             work / 'place/reports/phys_opt_design.dcp', native,
             work / 'source/project/hardware/vivado/scripts/release_reports.tcl',
             ROOT / 'scripts/run_board.py', ROOT / 'scripts/build_board.tcl',
             ROOT / 'source/design.md', HERE / 'resume.tcl', Path(__file__)]
    probe = ROOT / 'runs/dsp_raw_only/place_identity_probe/vivado.log'
    files.append(probe)
    inputs = dict(candidate=name, schema='native_project_resume_v1',
                  original_place_failure=original,
                  files={str(path): board.sha(path) for path in files},
                  source_inputs=config['source_inputs'], board_inputs=config['board_inputs'],
                  original_implementation_seconds=previous, previous_time_evidence=prior_evidence,
                  identity_evidence='Native read-only probe shows loaded TOP=scalellm_final_decode16_bd_wrapper, NAME=checkpoint_place_design, PART=xcvu9p-flga2104-2L-e. New guard checks loaded TOP, part, tool and all three original clocks. Original guard and manifests remain frozen.')
    return dict(name=name, work=work, config=config, inputs=inputs,
                seconds={'implementation': previous, 'hold': 0.0, 'bitstream': 0.0},
                peak_rss=0, min_mem=board.mem_available(), min_disk=shutil.disk_usage(HERE).free,
                stop_reason=None, phase='placement_report', last_tick=time.monotonic())


def snapshot_processes():
    rows = {}
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():
            continue
        try:
            text = (path / 'stat').read_text()
            fields = text[text.rindex(')') + 2:].split()
            rows[int(path.name)] = (int(fields[1]), int(fields[21]) * os.sysconf('SC_PAGE_SIZE'))
        except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError):
            continue
    return rows


def descendants(pid, rows):
    selected = {pid}
    while True:
        following = {child for child, (parent, _) in rows.items() if parent in selected}
        if following <= selected:
            return selected
        selected.update(following)


def launch(candidate):
    out = HERE / candidate['name']
    out.mkdir(exist_ok=False)
    candidate['out'] = out
    dump(out / 'stage_inputs.json', candidate['inputs'])
    env = os.environ.copy()
    env.update(NATIVE_OUT=str(out), NATIVE_CONTROL=str(HERE),
               NATIVE_CANDIDATE=candidate['name'],
               NATIVE_PROJECT=str(candidate['work'] / 'create/project/scalellm_final_decode16.xpr'),
               HAP_HW_ROOT=str(candidate['work'] / 'source/project/hardware'),
               HAP_JOBS='32', OMP_NUM_THREADS='32')
    command = [candidate['config']['vivado'], '-mode', 'batch', '-notrace',
               '-source', str(HERE / 'resume.tcl'), '-log', str(out / 'vivado.log'),
               '-journal', str(out / 'vivado.jou')]
    def setup():
        os.sched_setaffinity(0, CPUS[candidate['name']])
        os.nice(10)
    console = (out / 'console.log').open('w')
    candidate['console'] = console
    candidate['proc'] = subprocess.Popen(command, cwd=out, env=env, stdout=console,
        stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=setup)
    candidate['started'] = time.monotonic()
    candidate['last_tick'] = candidate['started']
    candidate['command'] = command
    print('STARTED', candidate['name'], candidate['proc'].pid, flush=True)


def physical_metrics(candidate):
    folder = candidate['out'] / 'post_physopt'
    reports = {key: folder / filename for key, filename in {
        'utilization': 'utilization.rpt', 'slr': 'utilization_slr.rpt',
        'timing': 'timing_summary.rpt', 'hierarchy': 'utilization_hierarchical.rpt',
        'mapping': 'recovery_mapping.tsv', 'inventory': 'dsp_inventory.tsv',
        'blackboxes': 'blackboxes.txt', 'identity': 'loaded_identity.txt'}.items()}
    top = selector.parse_top(reports['utilization'].read_text())
    slr = selector.parse_slr(reports['slr'].read_text(), top)
    timing = selector.parse_timing(reports['timing'].read_text())
    leaves = selector.parse_recovery_hierarchy(reports['hierarchy'].read_text())
    counts, inventory_total, mapping_total = selector.count_recovery_primitives(
        reports['mapping'].read_text(), reports['inventory'].read_text())
    expected = 2 if candidate['name'] == 'dsp_raw_only' else 4
    reasons = []
    if reports['blackboxes'].read_text().strip():
        reasons.append('unresolved blackboxes')
    if len(leaves) != 96 or sum(row['dsp'] for row in leaves) != 96 * expected:
        reasons.append('recovery hierarchical DSP mapping differs')
    if len(counts) != 96 or any(count != expected for count in counts.values()):
        reasons.append('recovery primitive mapping differs')
    if mapping_total != 96 * expected or inventory_total != top['dsp']['used']:
        reasons.append('DSP inventory totals differ')
    for key in ('clb', 'dsp'):
        if top[key]['used'] > top[key]['available']:
            reasons.append('whole-board capacity exceeded: ' + key)
        for index, values in slr.items():
            if values[key]['used'] > values[key]['available']:
                reasons.append('SLR' + index + ' capacity exceeded: ' + key)
    return dict(candidate=candidate['name'], feasible=not reasons, reasons=reasons,
        top=top, slr=slr, timing=timing,
        setup_pass=timing['wns'] >= 0 and timing['tns'] == 0 and timing['setup_fail'] == 0,
        hold_pass=timing['whs'] >= 0 and timing['ths'] == 0 and timing['hold_fail'] == 0,
        maximum_slr_clb_percent=max(value['clb']['percent'] for value in slr.values()),
        maximum_slr_dsp_percent=max(value['dsp']['percent'] for value in slr.values()),
        recovery_leaf_count=len(leaves), recovery_dsp=sum(counts.values()),
        reports={key: dict(path=str(path), sha256=board.sha(path)) for key, path in reports.items()})


def stop(candidate, reason):
    candidate['stop_reason'] = reason
    process = candidate['proc']
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def progress(candidate, rss, selected):
    dump(candidate['out'] / 'progress.json', dict(candidate=candidate['name'],
        pid=candidate['proc'].pid, phase=candidate['phase'],
        status='RUNNING' if candidate['proc'].poll() is None else 'EXITED',
        cumulative_seconds=candidate['seconds'], tree_rss_bytes=rss,
        peak_tree_rss_bytes=candidate['peak_rss'], stop_reason=candidate['stop_reason'],
        cpus=list(range(96)) if selected == candidate['name'] else CPUS[candidate['name']],
        native_threads=32, command=candidate['command']))


def main():
    candidates = [load_candidate(name) for name in NAMES]
    if board.mem_available() < 64 * GIB or shutil.disk_usage(HERE).free < 30 * GIB:
        raise RuntimeError('Memory or disk admission floor')
    selected = None
    route_started = False
    for candidate in candidates:
        launch(candidate)
    try:
        while any(candidate['proc'].poll() is None for candidate in candidates):
            now = time.monotonic()
            rows = snapshot_processes()
            all_pids = set()
            rss_values = {}
            for candidate in candidates:
                pids = descendants(candidate['proc'].pid, rows)
                all_pids.update(pids)
                rss_values[candidate['name']] = sum(rows.get(pid, (0, 0))[1] for pid in pids)
            combined_rss = sum(rows.get(pid, (0, 0))[1] for pid in all_pids)
            mem = board.mem_available()
            disk = shutil.disk_usage(HERE).free
            for candidate in candidates:
                if candidate['proc'].poll() is not None:
                    continue
                phase_file = candidate['out'] / 'phase.txt'
                phase = phase_file.read_text().strip() if phase_file.is_file() else candidate['phase']
                category = ('bitstream' if phase == 'bitstream' else
                            'hold' if phase in ('hold-sll', 'hold', 'hold_review') else 'implementation')
                candidate['seconds'][category] += now - candidate['last_tick']
                candidate['last_tick'] = now
                candidate['phase'] = phase
                rss = rss_values[candidate['name']]
                candidate['peak_rss'] = max(candidate['peak_rss'], rss)
                candidate['min_mem'] = min(candidate['min_mem'], mem)
                candidate['min_disk'] = min(candidate['min_disk'], disk)
                limit = 384 if selected == candidate['name'] and route_started else 192
                reason = None
                if candidate['seconds']['implementation'] > 28800:
                    reason = 'cumulative implementation wall time limit'
                elif candidate['seconds']['hold'] > 7200:
                    reason = 'cumulative hold wall time limit'
                elif candidate['seconds']['bitstream'] > 2400:
                    reason = 'bitstream wall time limit'
                elif rss > limit * GIB or combined_rss > 384 * GIB:
                    reason = 'candidate or combined RSS limit'
                elif mem < 64 * GIB or disk < 30 * GIB:
                    reason = 'available memory or disk floor'
                if reason:
                    stop(candidate, reason)
                progress(candidate, rss, selected)
            if selected is None and all((c['out'] / 'reports_ready.txt').is_file() for c in candidates):
                metrics = [physical_metrics(c) for c in candidates]
                selected, reason = selector.choose(*metrics)
                dump(HERE / 'selection.json', dict(candidate=selected, reason=reason,
                    candidates={row['candidate']: row for row in metrics},
                    selector_sha256=board.sha(ROOT / 'scripts/select_candidate.py'),
                    recovery_runner_sha256=board.sha(Path(__file__))))
                (HERE / 'selected.txt').write_text(selected + '\n')
                print('SELECTED', selected, reason, flush=True)
            if selected and not route_started:
                others = [c for c in candidates if c['name'] != selected]
                if all(c['proc'].poll() is not None for c in others):
                    candidate = next(c for c in candidates if c['name'] == selected)
                    for pid in descendants(candidate['proc'].pid, snapshot_processes()):
                        try:
                            os.sched_setaffinity(pid, set(range(96)))
                        except ProcessLookupError:
                            pass
                    (HERE / 'route_go.txt').write_text('RESUME_NATIVE_ROUTE\n')
                    route_started = True
                    print('ROUTE_STARTED', selected, flush=True)
            if selected is None and any(c['proc'].poll() is not None and not (c['out'] / 'reports_ready.txt').is_file() for c in candidates):
                raise RuntimeError('A candidate exited before complete native physical reports')
            time.sleep(5)
    except BaseException:
        for candidate in candidates:
            stop(candidate, candidate['stop_reason'] or 'recovery controller stopped')
        raise
    finally:
        for candidate in candidates:
            candidate['console'].close()
            out = candidate['out']
            files = {str(p.relative_to(out)): board.sha(p) for p in out.rglob('*') if p.is_file() and p.name != 'result.json'}
            log = (out / 'console.log').read_text(errors='replace')
            marker = 'NATIVE_RESUME_BITSTREAM_PASS' if candidate['name'] == selected else 'NATIVE_PLACEMENT_REPORT_PASS NOT_SELECTED'
            result = dict(candidate=candidate['name'], returncode=candidate['proc'].returncode,
                stop_reason=candidate['stop_reason'], native_pass_marker=marker in log,
                cumulative_seconds=candidate['seconds'], peak_tree_rss_bytes=candidate['peak_rss'],
                minimum_mem_available_bytes=candidate['min_mem'], minimum_disk_free_bytes=candidate['min_disk'],
                stage_inputs_sha256=board.sha(out / 'stage_inputs.json'), files=files)
            dump(out / 'result.json', result)
    if selected is None or any(c['proc'].returncode != 0 or c['stop_reason'] for c in candidates):
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
