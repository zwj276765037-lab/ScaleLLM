#!/usr/bin/env python3
"""CPU-only capture of the current run's completed routed DCP, before terminal.

This observes files and an existing process only. It cannot launch Vivado,
generate/rewrite a DCP, or make a failed implementation successful.
"""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('slr_probe', HERE / 'run_slr_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def observe(parent):
    parent = Path(parent).resolve()
    if not parent.is_relative_to(probe.E013 / 'experiment_results/runs/R004/attempts'):
        raise ValueError('Outside current M006 implementation evidence')
    destination = parent / 'route_completion_observation.json'
    if destination.exists() or (parent / 'result.json').exists():
        raise ValueError('Observation must be new and precede the parent terminal record')
    launch = json.loads((parent / 'launch.json').read_text())
    if launch.get('stage') != 'impl':
        raise ValueError('Only the actual implementation run can be observed')
    rows = probe.proc_snapshot()
    if (launch['pid'] not in rows or rows[launch['pid']]['birth'] != launch['root_birth'] or
            rows[launch['pid']]['sid'] != launch['session']):
        raise ValueError('Original implementation root process is no longer live')
    if probe.sha(parent / 'input_manifest.json') != launch['input_manifest_sha256']:
        raise ValueError('Parent input manifest changed')
    report = (parent / 'native_reports').resolve(strict=True)
    if not report.is_relative_to(probe.HW / 'vivado/reports') or str(report) != launch['report']:
        raise ValueError('Report root identity mismatch')
    dcp = report / 'routed.dcp'
    log = report / 'vivado.log'
    data = log.read_bytes()
    completed = b'route_design completed successfully'
    exported = ("The checkpoint '" + str(dcp) + "' has been generated.").encode()
    if completed not in data or exported not in data or data.index(completed) > data.index(exported):
        raise ValueError('Routed checkpoint is not yet natively completed and exported')
    stat_before = dcp.stat()
    digest = probe.sha(dcp)
    stat_after = dcp.stat()
    if (stat_before.st_size, stat_before.st_mtime_ns) != (stat_after.st_size, stat_after.st_mtime_ns):
        raise ValueError('Checkpoint changed during observation')
    if (parent / 'result.json').exists():
        raise ValueError('Parent became terminal before this observation was captured')
    record = dict(observed_at=probe.now(), observed_before_parent_terminal=True,
                  source_stage='routed', parent_root_birth=launch['root_birth'],
                  parent_session=launch['session'], input_manifest_sha256=launch['input_manifest_sha256'],
                  routed_dcp=dict(path=str(dcp), bytes=stat_after.st_size, sha256=digest),
                  log_prefix=dict(path=str(log), bytes=len(data), sha256=__import__('hashlib').sha256(data).hexdigest()),
                  observer_source_sha256=probe.sha(Path(__file__)),
                  scope='generation_time_observation_not_physical_acceptance')
    with destination.open('x') as f:
        json.dump(record, f, indent=2)
        f.write('\n')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('parent', type=Path)
    print(json.dumps(observe(parser.parse_args().parent), indent=2))
