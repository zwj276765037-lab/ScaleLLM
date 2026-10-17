#!/usr/bin/env python3
"""Actual new collector ledgers through the complete E008 same-phase P view."""
import argparse
import ast
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evidence_adapter as a
import directed_evidence as d


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    assert Path(args.tag).name == args.tag
    out = HERE / 'CPU_checks' / args.tag
    out.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, set(range(8)))
    os.setpriority(os.PRIO_PROCESS, 0, 5)
    checks = {}
    for name in ['directed_exporter.tcl', 'directed_evidence.py', 'top_port_index.tcl', 'top_port_evidence.py']:
        assert (HERE / name).read_bytes() == (HERE.parent / name).read_bytes()
    checks['same_actual_shared_acquisition_sources'] = True
    replays = []
    for point in ['pre_place', 'place']:
        fixtures = out / point
        result = subprocess.run(['tclsh', str(HERE.parent/'check_native_index_phase_mock.tcl'), str(HERE), str(fixtures), point], capture_output=True, text=True)
        (out / (point + '.stdout.txt')).write_text(result.stdout)
        (out / (point + '.stderr.txt')).write_text(result.stderr)
        cases = [line.split('\t') for line in result.stdout.splitlines() if line.startswith('CASE\t')]
        assert result.returncode == 0 and len(cases) == 19 and all(row[2] == 'PASS' for row in cases), (cases, result.stderr)
        for row in cases:
            if row[1] in {'bad_schema', 'no_local_pins', 'duplicate_top_driver'}:
                continue
            report = fixtures / row[1]
            literal = report / f'candidate_P_{point}.tsv'
            if point != 'pre_place':
                actual = report / f'candidate_reconciled_P_{point}.tsv'
                actual.write_bytes(literal.read_bytes())
                resolved = {member['NAME']:member['REF_NAME'] for member in a.rows(actual)}
                (report / f'candidate_reconciliation_{point}.json').write_text(json.dumps(dict(qualified=True, resolved=resolved)))
                if row[1] == 'dsp_copy':
                    literal.write_text('NAME\tREF_NAME\ncandidate\tFDRE\n')
            before = d.identity(literal)
            value = a.cut_summary(point, report)
            assert value['directed_boundary_complete'] and d.identity(literal) == before
            assert value['top_port_acquisition']['exhaustive_native_reciprocal_qualification']
            if point != 'pre_place':
                assert value['artifacts']['P'] == d.identity(actual)
            replays.append(dict(point=point, case=row[1], actual_P_rows=len(resolved) if point != 'pre_place' else None,
                                directed_cut=True, actual_P_and_literal_P_identities_preserved=True))
    checks['32_actual_collector_phase_view_replays'] = len(replays) == 32
    # A later literal/raw/index change must not be silently admitted by the
    # symlink view even when the reconciled physical set remains the same.
    report = out / 'place/ingress'
    raw = report / 'candidate_top_port_index_place.tcllist'
    raw.write_text(raw.read_text() + '\n')
    try:
        a.directed_validation_projection('place', report)
    except ValueError as error:
        assert 'input changed' in str(error)
    else:
        raise AssertionError('Changed bound index accepted by phase projection')
    checks['later_raw_index_identity_change_rejected'] = True
    baseline = HERE.parents[1] / 'directed_candidate_cut_system_python/E008_entry'
    def function(path, name):
        return ast.dump(next(node for node in ast.parse(path.read_text()).body if isinstance(node, ast.FunctionDef) and node.name == name), include_attributes=False)
    for name in ['successful_pre_place_parent', 'constraint_chain', 'membership', 'reconcile_objects', 'require_origin_query', 'reconcile']:
        assert function(HERE/'evidence_adapter.py', name) == function(baseline/'evidence_adapter.py', name)
    checks['parent_constraints_membership_actual_origin_qualifications_unchanged'] = True
    for path in HERE.glob('*.py'):
        ast.parse(path.read_text(), filename=str(path))
    checks['Python_AST'] = True
    assert all(checks.values())
    value = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), EDA_executed=False, candidate_selected=None,
                 checks=checks, replays=replays, sources=[d.identity(path) for path in sorted(HERE.glob('*.py')) + sorted(HERE.glob('*.tcl'))],
                 original_da34_manifest=d.identity(baseline/'prepared_manifest.json'),
                 limitations=['Actual collector/helper/adapter runs with finite native mocks; no actual E008 native or physical run',
                              'New index must independently qualify each actual phase; no timing or speed signoff'])
    d.save(out/'results.json', value)
    print(json.dumps(dict(path=str(out/'results.json'), checks=checks)))


if __name__ == '__main__':
    main()
