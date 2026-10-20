"""Clearly labelled CPU mutations of complete actual native data through full CLI."""
from pathlib import Path
import copy
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REPORT = ROOT / 'project/hardware/vivado/reports/m003_E011_R003_AT001_fixed_complete_physical'
RAW = ROOT / 'project/hardware/vivado/reports/m003_E011_R003_AT004_cached_place_write_replica_proof/selected_state_and_root_pins.jsonl'
EVIDENCE = ROOT / 'project/E011_m003_joint_routability_implementation/experiment_results/runs/R003/attempts/AT004_cached_place_write_replica_proof/evidence'
snapshot = json.loads((REPORT / 'm003_native_place.json').read_text())
raw = [json.loads(line) for line in RAW.read_text().splitlines()]

def state(rows, kind, terminal=None):
    return next(row for row in rows if row['kind'] == kind
                and '_replica_' in row.get('cell', row.get('NAME', ''))
                and (terminal is None or row.get('terminal') == terminal))

def masked_decode(rows, snap):
    snap['uram_configs'][0]['SELF_MASK_B'] = "11'h7E1"

def bad_read_address(rows, snap):
    roots = {row['NAME'] for row in snap['uram_configs'] if row['CASCADE_ORDER_A'] == 'FIRST'}
    row = next(row for row in snap['memory_pins'] if row['cell'] in roots and row['pin'] == 'ADDR_A[0]')
    row.update(drivers='CPU_wrong_read_state/Q', driver_cells='CPU_wrong_read_state',
               driver_refs='FDCE', startpoints='CPU_wrong_read_state/C')

cases = {
    'wrong_replica_D': lambda rows, snap: state(rows, 'state_pin', 'D').update(nets='CPU_mutation/foreign'),
    'wrong_replica_CE': lambda rows, snap: state(rows, 'state_pin', 'CE').update(nets='CPU_mutation/foreign'),
    'unknown_effective_clock_polarity': lambda rows, snap: state(rows, 'state_pin', 'C').update(IS_INVERTED='NOT_SUPPORTED'),
    'wrong_replica_INIT': lambda rows, snap: state(rows, 'cell').update(INIT="1'b1"),
    'wrong_actual_clock_edge': lambda rows, snap: state(rows, 'state_clock').update(WAVEFORM='1.000 6.000'),
    'original_full_guard_read_Q': bad_read_address,
    'original_full_guard_URAM_mask': masked_decode,
    'original_full_guard_80_boundary_coverage': lambda rows, snap: snap['boundaries'].pop(),
}
summary = []
for name, mutate in cases.items():
    rows, snap = copy.deepcopy(raw), copy.deepcopy(snapshot)
    mutate(rows, snap)
    target = EVIDENCE / ('CPU_actual_data_negative_' + name)
    target.mkdir()
    raw_path, snap_path = target / 'CPU_mutated_rows.jsonl', target / 'CPU_mutated_snapshot.json'
    raw_path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    snap_path.write_text(json.dumps(snap))
    origin = dict(CPU_mutation_only=True, native_executed=False, mutation=name,
                  original_raw=str(RAW), original_snapshot=str(REPORT / 'm003_native_place.json'),
                  does_not_replace_actual_native_or_failed_reports=True)
    (target / 'CPU_origin.json').write_text(json.dumps(origin, indent=2) + '\n')
    output = target / 'CPU_qualification_result.json'
    command = [sys.executable, str(HERE / 'qualify_placed_sources.py'),
               '--snapshot', str(snap_path),
               '--spec', str(ROOT / 'project/hardware/vivado/constraints/m003_joint_locality_spec.json'),
               '--raw', str(raw_path), '--package', str(HERE / 'query_package_AT004_cached.json'),
               '--output', str(output)]
    with (target / 'CLI.log').open('x') as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
    assert result.returncode == 1, (name, (target / 'CLI.log').read_text())
    if output.exists():
        verdict = json.loads(output.read_text())
        assert verdict['passed'] is False and verdict['errors']
    summary.append(dict(case=name, rejected=True, exit_code=result.returncode,
                        full_original_validator_reached=output.exists(),
                        native_executed=False, log=str(target / 'CLI.log')))
with (EVIDENCE / 'actual_full_CLI_negative_receipt.json').open('x') as stream:
    json.dump(dict(passed=True, CPU_actual_data_mutations=True, native_executed=False,
                   cases=summary), stream, indent=2)
    stream.write('\n')
print(json.dumps(dict(passed=True, full_CLI_rejected=len(summary), native_executed=False)))
