#!/usr/bin/env python3
"""Bounded readback/semantic counterexamples; no native success is simulated."""
import ast
import contextlib
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import subprocess
import tempfile

import candidate_evidence as adapter

HERE = Path(__file__).resolve().parent


def write(path, columns, records):
    with path.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(records)


def main():
    started = datetime.now(timezone.utc).isoformat()
    for path in HERE.glob('*.py'):
        ast.parse(path.read_text())
    script = 'source {' + str(HERE / 'candidate_inspector.tcl') + '}\n'
    cases = [('DSP_C_DATA', 'C', '0'), ('DSP48E2', 'C[47]', '1'), ('FDRE', 'C', '0'),
             ('FDCE', 'CLR', '0'), ('MUXF7', 'S', '0'), ('UNKNOWN', 'C', '0'),
             ('RAMD64E', 'I0', ''), ('LUT6', 'I0', '0'), ('UNKNOWN', 'X', 'true')]
    for ref, terminal, clock in cases:
        script += 'puts [slr2::pin_class {' + ref + '} {' + terminal + '} {' + clock + '}]\n'
    script += 'set root {x/g_row_branch[1].u_branch_leaf}\n'
    for name in ['x/g_row_branch[1].u_branch_leaf/ff', 'x/g_row_branch[0].u_branch_leaf/ff',
                 'x/g_row_branch1.u_branch_leaf/ff', 'x/g_row_branch[10].u_branch_leaf/ff']:
        script += 'puts [expr {[string first ${root}/ {' + name + '}] == 0}]\n'
    script += '''set internalDriver [list LEAF_PIN inside/Q OUT DRIVER DATA_REGISTER clk]
set internalLoad [list LEAF_PIN inside/D IN LOAD DATA_REGISTER clk]
set externalLoad [list LEAF_PIN outside/D IN LOAD DATA_REGISTER clk]
set externalPort [list TOP_PORT top_out OUT LOAD TOP_PORT {}]
set insideLoads [list $internalLoad];set outsideLoads [list $externalLoad $externalPort]
set unresolved [list $internalDriver $internalLoad]
lassign [slr2::timing_boundary_selection SINGLE_DRIVER 1 $insideLoads $outsideLoads $unresolved] direction selected basis
if {$direction ne "EGRESS" || $selected ne $outsideLoads || [lsearch -exact $selected $internalLoad] >= 0 || [lsearch -exact $selected $internalDriver] >= 0} {error EGRESS_SELECTED_INTERNAL_ONLY_PIN}
lassign [slr2::timing_boundary_selection SINGLE_DRIVER 0 $insideLoads $outsideLoads $unresolved] direction selected basis
if {$direction ne "INGRESS" || $selected ne $insideLoads} {error INGRESS_NOT_INSIDE_LOADS}
lassign [slr2::timing_boundary_selection INOUT_RETAINED 1 $insideLoads $outsideLoads $unresolved] direction selected basis
if {$direction ne "UNRESOLVED" || $selected ne $unresolved} {error INOUT_GIVEN_FALSE_DIRECTION}
puts DIRECTIONAL_SELECTION_CPU_PASS
'''
    result = subprocess.run(['tclsh'], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [adapter.pin_class(*case) for case in cases] + ['1', '0', '0', '0', 'DIRECTIONAL_SELECTION_CPU_PASS']
    for path in HERE.glob('*.tcl'):
        check = subprocess.run(['tclsh'], input='set h [open {' + str(path) + '}];set body [read $h];close $h;puts [info complete $body]\n', text=True, capture_output=True)
        assert check.returncode == 0 and check.stdout.strip() == '1', path
    with tempfile.TemporaryDirectory(prefix='R004_cut_readback_CPU_') as directory:
        report = Path(directory)
        for tag, values in [('RAW', {'group/ff': 'FDRE', 'group/memory': 'RAMD64E', 'group/vcc': 'VCC'}),
                            ('S', {'group/ff': 'FDRE', 'group/memory': 'RAMD64E'}),
                            ('P', {'group/ff': 'FDRE', 'group/memory': 'RAMD64E'})]:
            write(report / f'candidate_{tag}_FIX.tsv', ['NAME', 'REF_NAME'],
                  [dict(NAME=name, REF_NAME=ref) for name, ref in values.items()])
        columns = ['canonical_net', 'kind', 'NAME', 'DIRECTION', 'role', 'raw_cell', 'REF_NAME',
                   'physical_parent', 'inside_RAW', 'inside_S', 'inside_P', 'LOC', 'SLR',
                   'pin_class', 'REF_PIN_NAME', 'IS_CLOCK', 'owner_root']
        def leaf(net, cell, ref, terminal, direction, inside, slr, constant=False):
            return dict(zip(columns, [net, 'LEAF_PIN', cell + '/' + terminal, direction,
                        {'IN': 'LOAD', 'OUT': 'DRIVER', 'INOUT': 'INOUT'}[direction], cell, ref, cell,
                        '1' if inside or constant else '0', '1' if inside else '0', '1' if inside else '0',
                        'SITE', slr, adapter.pin_class(ref, terminal, '0'), terminal, '0', 'group' if inside or constant else 'other']))
        port = dict(zip(columns, ['N1', 'TOP_PORT', 'top_in', 'IN', 'DRIVER', 'TOP_PORT', 'TOP_PORT',
                                 'TOP_PORT', '0', '0', '0', '', 'TOP_PORT', 'TOP_PORT', '', 'NOT_APPLICABLE_TOP_PORT', 'TOP_PORT']))
        endpoints = [port, leaf('N1', 'group/ff', 'FDRE', 'D', 'IN', True, 'SLR1'),
                     leaf('N2', 'group/memory', 'RAMD64E', 'I0', 'INOUT', True, 'SLR1'),
                     leaf('N2', 'other/ff', 'FDRE', 'Q', 'OUT', False, 'SLR2'),
                     leaf('N2', 'group/vcc', 'VCC', 'P', 'OUT', False, 'UNPLACED', True)]
        endpoint_path = report / 'candidate_endpoints_FIX.tsv'
        write(endpoint_path, columns, endpoints)
        net_cols = ['canonical_net', 'segments', 'leaf_pins', 'top_ports', 'drivers', 'INOUT_count',
                    'inside_endpoints', 'outside_endpoints', 'unknown_endpoints', 'resolution', 'boundary', 'classes', 'actual_clocks']
        write(report / 'candidate_nets_FIX.tsv', net_cols,
              [dict(zip(net_cols, ['N1', 2, 1, 1, 1, 0, 1, 1, 0, 'SINGLE_DRIVER', 'CUT', 'DATA_REGISTER 1', ''])),
               dict(zip(net_cols, ['N2', 1, 3, 0, 2, 1, 1, 2, 0, 'INOUT_RETAINED', 'CUT', 'UNKNOWN_REF_PIN 1 DATA_REGISTER 1 CONSTANT 1', '']))])
        segments = [dict(canonical_net='N1', segment='N1'), dict(canonical_net='N1', segment='N1_alias'), dict(canonical_net='N2', segment='N2')]
        segment_path = report / 'candidate_segments_FIX.tsv'
        write(segment_path, ['canonical_net', 'segment'], segments)
        write(report / 'candidate_pins_FIX.tsv', ['NAME'], [dict(NAME=row['NAME']) for row in endpoints if row['raw_cell'].startswith('group/')])
        (report / 'candidate_cut_FIX_closed.txt').write_text('completed=1\n')
        with contextlib.redirect_stdout(io.StringIO()): adapter.cut('FIX', report)
        summary = json.loads((report / 'candidate_cut_summary_FIX.json').read_text())
        assert summary['RAW'] == 3 and summary['S'] == 2 and summary['P'] == 2
        assert summary['endpoints'] == 5 and summary['canonical_segments'] == 3
        assert summary['endpoint_direction_counts']['LEAF_PIN/INOUT'] == 1
        assert summary['endpoint_direction_counts']['TOP_PORT/IN'] == 1
        failures = []
        for label, records in [('duplicate_endpoint', endpoints + [endpoints[1]]),
                               ('missing_top_port', endpoints[1:]),
                               ('missing_INOUT', [row for row in endpoints if row['DIRECTION'] != 'INOUT'])]:
            write(endpoint_path, columns, records)
            try: adapter.cut('FIX', report)
            except ValueError as error: failures.append(dict(case=label, actual_rejection=str(error)))
            else: raise AssertionError(label)
        write(endpoint_path, columns, endpoints)
        write(segment_path, ['canonical_net', 'segment'], segments + [segments[0]])
        try: adapter.cut('FIX', report)
        except ValueError as error: failures.append(dict(case='duplicate_alias_segment', actual_rejection=str(error)))
        else: raise AssertionError('duplicate_alias_segment')
    receipt = dict(started_utc=started, ended_utc=datetime.now(timezone.utc).isoformat(), exit_code=0,
                   status='PASS_CPU_READBACK_AND_PURE_TCL_ONLY', EDA_executed=False,
                   native_API_or_candidate_qualification='NOT_RUN',
                   Tcl_semantics_and_literal_selector=dict(argv=['tclsh'], stdin=script, stdout=result.stdout, stderr=result.stderr, exit_code=result.returncode),
                   closed_cut_fixture_positive=['RAW constants separate from S/P', 'memory retained', 'all-direction INOUT', 'top-port driver', 'canonical segment aliases', 'unknown memory semantics retained'],
                   closed_cut_fixture_negative=failures,
                   directional_timing_counterexample='Inside DRIVER with both inside and outside LOADs: EGRESS exact selection contains only all outside leaf/top LOADs; INGRESS selects inside LOADs; INOUT stays UNRESOLVED',
                   source_files=[adapter.identity(path) for path in sorted(HERE.glob('*.py')) + sorted(HERE.glob('*.tcl'))])
    adapter.save(HERE / 'bounded_CPU_validation_CT003.json', receipt)
    print(json.dumps(dict(receipt=str(HERE / 'bounded_CPU_validation_CT003.json'), exit_code=0, EDA_executed=False)))


if __name__ == '__main__':
    main()
