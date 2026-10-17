#!/usr/bin/env python3
"""One-time actual closed native-index audit using the consumed archived validator."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('point', choices=['C01', 'C02'])
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    attempt, report, point = args.attempt.resolve(), args.report.resolve(), args.point
    assert attempt.parent == ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R006/attempts'
    assert report.parent == ROOT/'project/hardware/vivado/reports' and report.name.startswith('m002_E006_R006_')
    os.sched_setaffinity(0, set(range(8)))
    os.setpriority(os.PRIO_PROCESS, 0, 5)
    module_path = attempt/'sources/top_port_evidence.py'
    spec = importlib.util.spec_from_file_location('actual_archived_top_port_evidence', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    identity = module.identity
    output = attempt/f'candidate_{point}_native_port_index_closed_facts.json'
    short = attempt/f'candidate_{point}_native_port_index_closed_summary.json'
    producer = attempt/f'capture_candidate_{point}_native_port_index_producer.py'
    assert not any(path.exists() for path in [output, short, producer])
    inputs = json.loads((attempt/'input_bindings.json').read_text())
    assert identity(module_path) in inputs['sources']
    assert all(identity(row['path']) == row for row in inputs['sources'])
    assert identity(inputs['preparation_manifest']['path']) == inputs['preparation_manifest']
    value = module.validate(point, report)
    closed_path = report/f'candidate_top_port_index_closed_{point}.json'
    closed = json.loads(closed_path.read_text())
    assert closed['input_identity'] == inputs['checkpoint']
    shutil.copy2(Path(__file__), producer)
    facts = dict(observed_utc=datetime.now(timezone.utc).isoformat(), point=point,
                 native_index_qualification_closed=True, coverage_version='candidate_directed_cut_v1',
                 acquisition_mode='NATIVE_PORT_REVERSE_INDEX_V1', native_index=closed,
                 complete_native_universe=True, complete_each_port_adjacency=True,
                 complete_native_alias_closures=True, exhaustive_native_reciprocal_groups=True,
                 native_call_count=value['native_calls'], native_port_count=value['native_port_count'],
                 native_group_count=len(value['groups']), disconnected_ports=value['disconnected_ports'],
                 multigroup_ports=value['multigroup_ports'], unknown_direction_ports=value['unknown_direction_ports'],
                 input_bindings=identity(attempt/'input_bindings.json'), preparation_manifest=inputs['preparation_manifest'],
                 archived_validator=identity(module_path), native_index_artifacts=[identity(value['path']),identity(value['calls_path']),identity(closed_path)],
                 full_candidate_cut='NOT_CLAIMED_BY_INDEX_SUBSTEP', timing_signoff=False,
                 actual_supervisor_terminal='PENDING', producer=identity(producer))
    with output.open('x') as stream:
        stream.write(json.dumps(facts, ensure_ascii=False, indent=2)+'\n')
    summary = {key:facts[key] for key in ['observed_utc','point','native_index_qualification_closed','coverage_version','acquisition_mode',
                                            'native_call_count','native_port_count','native_group_count','disconnected_ports','multigroup_ports',
                                            'unknown_direction_ports','full_candidate_cut','timing_signoff','actual_supervisor_terminal']}
    summary['full_facts'] = identity(output)
    with short.open('x') as stream:
        stream.write(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(facts=identity(output),summary=identity(short))))


if __name__ == '__main__':
    main()
