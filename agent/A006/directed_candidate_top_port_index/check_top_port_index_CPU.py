#!/usr/bin/env python3
"""Run actual collector/validator on finite native mocks and distinguishing faults."""
import argparse
import ast
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tkinter

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import directed_evidence as evidence
import top_port_evidence as top

T = tkinter.Tcl()


def tl(values):
    return T.call('format', '%s', T.call('list', *values))


def td(value):
    return tl([part for pair in value.items() for part in pair])


def run(argv, report, tag):
    result = subprocess.run(argv, cwd=HERE.parents[2], capture_output=True, text=True)
    (report / (tag + '.stdout.txt')).write_text(result.stdout)
    (report / (tag + '.stderr.txt')).write_text(result.stderr)
    return result


def edit_index(report, change):
    path = report / 'candidate_top_port_index_test.tcllist'
    value = top.dictionary(path.read_text())
    change(value)
    path.write_text(td(value) + '\n')


def edit_calls(report, change):
    path = report / 'candidate_top_port_native_calls_test.tcllist'
    rows = evidence.ledger(path)
    rows = change(rows)
    for ordinal, row in enumerate(rows, 1):
        row['call_id'] = str(ordinal)
    path.write_text(''.join(td(row) + '\n' for row in rows))
    edit_index(report, lambda value: value.update(native_call_count=str(len(rows))))


def edit_join(report, change):
    path = report / 'candidate_native_role_queries_test.tcllist'
    rows = evidence.ledger(path)
    for row in rows:
        if row['query_kind'] == 'TOP_PORT_INDEX_JOIN':
            change(row)
    path.write_text(''.join(td(row) + '\n' for row in rows))


def missing_port(report):
    def mutate(index):
        ports = top.dictionary(index['ports'])
        del ports['data[0]']
        index['ports'] = td(ports)
    edit_index(report, mutate)


def missing_adjacency(report):
    edit_calls(report, lambda rows: [row for row in rows if top.split(row['command']) != ['get_nets', '-of_objects', 'data[0]']])


def missing_alias(report):
    def mutate(index):
        groups = top.dictionary(index['groups'])
        group = top.dictionary(groups['q0'])
        group['aliases'] = 'q0'
        groups['q0'] = td(group)
        index['groups'] = td(groups)
    edit_index(report, mutate)


def vector_misalignment(report):
    def mutate(rows):
        for row in rows:
            command = top.split(row['command'])
            if command[:2] == ['get_property', 'DIRECTION'] and len(top.split(command[2])) > 1:
                row['result'] = 'IN'
                break
        return rows
    edit_calls(report, mutate)


def duplicate_universe(report):
    def mutate(rows):
        for row in rows:
            if top.split(row['command']) == ['get_ports']:
                row['result'] = tl(top.split(row['result']) + ['data[0]'])
        return rows
    edit_calls(report, mutate)


def overlapping_closure(report):
    def mutate(rows):
        for row in rows:
            if top.split(row['command']) == ['get_nets', '-segments', 'n1']:
                row['result'] = tl(['n0', 'n1', 'q1'])
        return rows
    edit_calls(report, mutate)


def reciprocal_fault(report, extra):
    def mutate(rows):
        for row in rows:
            command = top.split(row['command'])
            if command[:2] == ['get_ports', '-of_objects']:
                values = top.split(row['result'])
                row['result'] = tl(values + ['DISCONNECTED'] if extra else values[1:])
                break
        return rows
    edit_calls(report, mutate)


def disconnected_contradiction(report):
    def mutate(index):
        ports = top.dictionary(index['ports'])
        port = top.dictionary(ports['DISCONNECTED'])
        metadata = top.dictionary(port['metadata'])
        metadata['UNCONNECTED'] = '0'
        port['metadata'] = td(metadata)
        ports['DISCONNECTED'] = td(port)
        index['ports'] = td(ports)
    edit_index(report, mutate)


def unknown_dropped(report):
    def mutate(query):
        names, directions = top.split(query['actual_NAMES']), top.split(query['actual_DIRECTIONS'])
        pairs = [(name, direction) for name, direction in zip(names, directions) if name != 'UNKNOWN_PORT']
        query['actual_NAMES'] = tl([name for name, _ in pairs])
        query['actual_DIRECTIONS'] = tl([direction for _, direction in pairs])
        query['raw_objects'] = str(len(pairs))
    edit_join(report, mutate)


def stale_epoch(report):
    edit_join(report, lambda query: query.update(epoch_id='STALE_OTHER_NATIVE_GRAPH'))


def candidate_expansion(report):
    path = report / 'candidate_segments_test.tsv'
    with path.open('a') as stream:
        stream.write('q0\tq0\nq0\tq1\n')


def fake_legacy(report):
    edit_join(report, lambda query: query.update(query_kind='ALL_TOP_PORTS', command=tl(['get_ports', '-of_objects', 'n0 n1']), native_tcl_code='0'))


def single_join_alias(report):
    def mutate(query):
        command = top.split(query['command'])
        command[3] = 'n0'
        query['command'] = tl(command)
    edit_join(report, mutate)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    assert Path(args.tag).name == args.tag
    out = HERE / 'CPU_checks' / args.tag
    out.mkdir(exist_ok=False)
    os.sched_setaffinity(0, set(range(8)))
    os.setpriority(os.PRIO_PROCESS, 0, 5)
    for path in HERE.glob('*.py'):
        ast.parse(path.read_text(), filename=str(path))
    native = run(['tclsh', str(HERE/'check_native_index_mock.tcl'), str(HERE), str(out/'collector')], out, 'collector')
    cases = [line.split('\t') for line in native.stdout.splitlines() if line.startswith('CASE\t')]
    assert native.returncode == 0 and len(cases) == 19 and all(row[2] == 'PASS' for row in cases), (cases, native.stderr)
    timing = run(['tclsh', str(HERE/'check_timing_index_mock.tcl'), str(HERE), str(out/'collector')], out, 'timing')
    assert timing.returncode == 0, timing.stderr
    positives = []
    for row in cases:
        if row[1] in {'bad_schema', 'no_local_pins', 'duplicate_top_driver'}:
            continue
        report = out / 'collector' / row[1]
        cut = run(['/usr/bin/python3', str(HERE/'directed_evidence.py'), 'cut', 'test', str(report)], report, 'cut_validator')
        clock = run(['/usr/bin/python3', str(HERE/'directed_evidence.py'), 'timing', 'test', str(report)], report, 'timing_validator')
        assert cut.returncode == clock.returncode == 0, (row[1], cut.stderr, clock.stderr)
        positives.append(row[1])
    source = out / 'collector/index_universe'
    faults = [('omitted_bus_port', missing_port), ('omitted_attached_net_response', missing_adjacency),
              ('missing_alias', missing_alias), ('misaligned_direction_vector', vector_misalignment),
              ('duplicate_native_universe', duplicate_universe), ('overlapping_unequal_closure', overlapping_closure),
              ('reciprocal_missing_port', lambda report: reciprocal_fault(report, False)),
              ('reciprocal_extra_port', lambda report: reciprocal_fault(report, True)),
              ('disconnected_contradiction', disconnected_contradiction), ('UNKNOWN_dropped', unknown_dropped),
              ('stale_epoch', stale_epoch), ('port_nets_expanded_candidate_scope', candidate_expansion),
              ('fabricated_ALL_TOP_PORTS', fake_legacy), ('single_alias_join_command_F01', single_join_alias)]
    negatives = []
    for name, mutate in faults:
        report = out / 'mutations' / name
        shutil.copytree(source, report, ignore=shutil.ignore_patterns('candidate_cut_summary_test.json', 'candidate_top_port_index_closed_test.json'))
        mutate(report)
        try:
            top.close('test', report)
            evidence.cut('test', report)
        except (ValueError, KeyError) as error:
            negatives.append(dict(case=name, rejected=True, error=str(error)))
        else:
            raise AssertionError('Mutation accepted: ' + name)
    # Mutate only the published identity bindings after a valid complete close.
    # These must fail at replay even though all raw native ledgers remain valid.
    for name in ['omitted_closed_sources', 'unrelated_closed_input_identity']:
        report = out / 'mutations' / name
        shutil.copytree(source, report, ignore=shutil.ignore_patterns('candidate_cut_summary_test.json'))
        receipt = report / 'candidate_top_port_index_closed_test.json'
        record = json.loads(receipt.read_text())
        if name == 'omitted_closed_sources':
            record['sources'] = []
        else:
            record['input_identity'] = evidence.identity(report/'candidate_top_port_index_test.tcllist')
        receipt.write_text(json.dumps(record, indent=2)+'\n')
        try:
            evidence.cut('test', report)
        except ValueError as error:
            negatives.append(dict(case=name, rejected=True, error=str(error)))
        else:
            raise AssertionError('Closed provenance mutation accepted: ' + name)
    summary = json.loads((out/'collector/egress_top_load/candidate_timing_validation_test.json').read_text())
    assert 'TOP_OUT' in summary['query_sets']['EGRESS']
    results = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), EDA_executed=False,
                   actual_collector_positive_cases=positives, expected_native_mock_rejections=[row[1] for row in cases if len(row)>3 and row[3]=='EXPECTED_UNQUALIFIED'],
                   mutation_cases=negatives, top_OUT_EGRESS_preserved=True, original_max_min_cap16_preserved=True,
                   actual_CPU_affinity=sorted(os.sched_getaffinity(0)), actual_nice=os.getpriority(os.PRIO_PROCESS, 0),
                   sources=[evidence.identity(path) for path in sorted(HERE.glob('*.tcl')) + sorted(HERE.glob('*.py'))],
                   fixture_input=evidence.identity(out/'collector/CPU_INPUT_NOT_DCP.txt'),
                   limitations=['Finite Tcl native graph mocks only; no new Vivado/DCP/native qualification or speed claim',
                                'Actual collector/validator/helper sources run; finite native APIs and spatial clock lookups are mocked',
                                'No EDA launch, stop, lock or production design modification'])
    evidence.save(out/'results.json', results)
    print(json.dumps(dict(path=str(out/'results.json'), positives=len(positives), rejections=len(negatives))))


if __name__ == '__main__':
    main()
