"""Explicit CPU schema fixtures; never create a native qualification/gate."""
from pathlib import Path
import copy
import json
import tempfile
import state_equivalence as subject

HERE = Path(__file__).resolve().parent
package = json.loads((HERE / 'query_package_AT004_cached.json').read_text())
originals = [cell for cell in package['selection_cells'] if '_replica_' not in cell]
rows = []
for cell in package['selection_cells']:
    original = cell.split('_replica_')[0]
    rows.append(dict(kind='cell', NAME=cell, REF_NAME='FDCE', INIT="1'b0",
                     IS_C_INVERTED="1'b0", IS_CLR_INVERTED="1'b0",
                     IS_D_INVERTED='NOT_SUPPORTED', IS_CE_INVERTED='NOT_SUPPORTED',
                     IS_PRIMITIVE='1', IS_SEQUENTIAL='1', DONT_TOUCH='0'))
    rows.append(dict(kind='parent', cell=cell, NAME=cell.rsplit('/', 1)[0],
                     REF_NAME='CPU_fixture_only', DONT_TOUCH='0'))
    for pin in ['D', 'C', 'CE', 'CLR']:
        source = 'CPU_only/' + (original.rsplit('/', 1)[1] if pin == 'D' else pin)
        rows.append(dict(kind='state_pin', cell=cell, terminal=pin, pin=cell + '/' + pin,
                         REF_PIN_NAME=pin, DIRECTION='IN', IS_INVERTED='0',
                         nets=source + '_net', drivers=source + '/O',
                         driver_cells=source, driver_refs='CPU_fixture_source',
                         primary_ports='', primary_port_directions=''))
    rows.append(dict(kind='state_clock', cell=cell, clock='CPU_only/core', NAME='CPU_only/core',
                     PERIOD='10.000', WAVEFORM='0.000 5.000', IS_GENERATED='0',
                     MASTER_CLOCK='', SOURCE_PINS='CPU_only/C/O'))
delta = json.loads((HERE.parents[1] / 'experiment_results/runs/R003/attempts/AT001_fixed_complete_physical/evidence/place_write_address_source_delta.json').read_text())
snapshot = dict(schema='M003_native_grouped_stream_v1',
                meta=dict(fixture=True, kind='native', native_observation=False, evidence_origin='CPU_fixture_only'),
                memory_pins=[], uram_configs=[], cells=[], helper_pins=[],
                connection_groups=[dict(id='CPU_G0', nets=['CPU_only/clock_net'],
                                        canonical_top_net='CPU_only/clock_net',
                                        leaf_drivers=['CPU_only/clock/O'], driver_cells=['CPU_only/clock'],
                                        driver_refs=['BUFG'], primary_ports=[], primary_port_directions=[])],
                connection_endpoints=[dict(pin='CPU_only/clock_anchor', group='CPU_G0', direct_nets=['CPU_only/clock_net'])],
                connection_counts=dict(endpoints=1, groups=1),
                control_sources=dict(clock_group='CPU_G0', clock_pin='CPU_only/clock_anchor'))
for index, row in enumerate(delta['failed_root_pins']):
    driver = row['actual']['drivers']
    root = dict(kind='memory_root_pin', cell=row['cell'], terminal=row['pin'],
                pin=row['cell'] + '/' + row['pin'], REF_PIN_NAME=row['pin'],
                DIRECTION='IN', IS_INVERTED='0', nets=f'CPU_only/Q_net_{index}',
                drivers=driver, driver_cells=driver.rsplit('/', 1)[0],
                driver_refs='FDCE', primary_ports='', primary_port_directions='')
    rows.append(root)
    snapshot['memory_pins'].append({**root, 'pin': row['pin'], 'startpoints': driver.rsplit('/', 1)[0] + '/C'})
    if not any(cfg['NAME'] == row['cell'] for cfg in snapshot['uram_configs']):
        snapshot['uram_configs'].append(dict(NAME=row['cell'], CASCADE_ORDER_A='FIRST', CASCADE_ORDER_B='FIRST'))

def select(values, kind, replica=True, pin=None):
    return next(row for row in values if row['kind'] == kind
                and ('_replica_' in row.get('cell', row.get('NAME', ''))) == replica
                and (pin is None or row.get('terminal') == pin))

def evaluate(values, state):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        raw, snap, pkg = root / 'CPU_only_rows.jsonl', root / 'CPU_only_snapshot.json', root / 'CPU_only_package.json'
        raw.write_text(''.join(json.dumps(row) + '\n' for row in values))
        snap.write_text(json.dumps(state))
        pkg.write_text(json.dumps(package))
        return subject.prove(raw, snap, pkg, verify_bindings=False)

positive = evaluate(rows, snapshot)
assert positive['passed'] is True and positive['identity_bindings_verified'] is False
assert len(positive['state_pairs']) == 9 and len(positive['affected_root_bindings']) == 24
empty_metadata = copy.deepcopy(rows)
for row in empty_metadata:
    if row['kind'] == 'cell':
        row.update(IS_C_INVERTED='', IS_D_INVERTED='', DONT_TOUCH='')
    if row['kind'] == 'parent':
        row['DONT_TOUCH'] = ''
assert evaluate(empty_metadata, snapshot)['empty_cell_properties_not_defaulted'] is True
mutations = {
    'missing_cell': lambda r, s: r.remove(select(r, 'cell')),
    'missing_state_input': lambda r, s: r.remove(select(r, 'state_pin', pin='D')),
    'duplicate_root': lambda r, s: r.append(copy.deepcopy(select(r, 'memory_root_pin', replica=False))),
    'different_D': lambda r, s: select(r, 'state_pin', pin='D').update(nets='CPU_only/foreign'),
    'different_CE': lambda r, s: select(r, 'state_pin', pin='CE').update(nets='CPU_only/foreign'),
    'different_clock_group': lambda r, s: select(r, 'state_pin', pin='C').update(nets='CPU_only/foreign'),
    'different_async_reset': lambda r, s: select(r, 'state_pin', pin='CLR').update(nets='CPU_only/foreign'),
    'wrong_INIT': lambda r, s: select(r, 'cell').update(INIT="1'b1"),
    'unknown_INIT': lambda r, s: select(r, 'cell').update(INIT='NOT_SUPPORTED'),
    'wrong_clock_period': lambda r, s: select(r, 'state_clock').update(PERIOD='20.000'),
    'wrong_clock_edge': lambda r, s: select(r, 'state_clock').update(WAVEFORM='1.000 6.000'),
    'missing_clock': lambda r, s: r.remove(select(r, 'state_clock')),
    'wrong_primitive': lambda r, s: select(r, 'cell').update(REF_NAME='FDRE'),
    'wrong_pin_polarity': lambda r, s: select(r, 'state_pin', pin='CLR').update(IS_INVERTED='1'),
    'unknown_pin_polarity': lambda r, s: select(r, 'state_pin', pin='C').update(IS_INVERTED='NOT_SUPPORTED'),
    'unknown_cell_polarity': lambda r, s: select(r, 'cell').update(IS_CLR_INVERTED='NOT_SUPPORTED'),
    'required_driver_missing': lambda r, s: select(r, 'state_pin', pin='D').update(drivers='', driver_cells='', driver_refs=''),
    'simultaneous_primary_and_leaf': lambda r, s: select(r, 'state_pin', pin='C').update(primary_ports='CPU_only/port', primary_port_directions='IN'),
    'protected_counter': lambda r, s: select(r, 'cell').update(DONT_TOUCH='1'),
    'wrong_parent': lambda r, s: select(r, 'parent').update(NAME='CPU_only/foreign'),
    'wrong_cascade_root': lambda r, s: s['uram_configs'][0].update(CASCADE_ORDER_B='MIDDLE'),
    'root_snapshot_disagrees': lambda r, s: s['memory_pins'][0].update(drivers='CPU_only/foreign/Q', driver_cells='CPU_only/foreign'),
}
result = []
for name, mutate in mutations.items():
    changed, state = copy.deepcopy(rows), copy.deepcopy(snapshot)
    mutate(changed, state)
    try:
        evaluate(changed, state)
    except (AssertionError, KeyError, ValueError, TypeError):
        result.append(dict(case=name, rejected=True))
    else:
        raise AssertionError('CPU fixture mutation accepted: ' + name)
print(json.dumps(dict(passed=True, CPU_fixture_only=True, native_observation=False,
                      complete_schema_rows=len(rows), state_pairs=9, root_bindings=24,
                      negatives=result), indent=2))
