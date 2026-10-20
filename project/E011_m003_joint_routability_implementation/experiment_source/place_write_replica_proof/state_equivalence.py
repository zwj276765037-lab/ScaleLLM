"""Fail-closed same-state proof from exact native FF, clock and root-pin facts."""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'project/hardware/vivado/scripts'))
from m003_snapshot_decode import decode

def identity(path):
    path = Path(path)
    return dict(path=str(path), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())

def words(value):
    assert isinstance(value, str)
    return [part.strip('{}') for part in value.split()]

def flag(value):
    assert isinstance(value, str)
    known = {'0': 0, '1': 1, "1'b0": 0, "1'b1": 1, 'false': 0, 'true': 1}
    assert value.lower() in known, ('unknown boolean/one-bit literal', value)
    return known[value.lower()]

def inventory(rows, kind, key):
    found = [row for row in rows if row.get('kind') == kind]
    result = {key(row): row for row in found}
    assert len(found) == len(result), ('duplicate native observation', kind)
    return result

def actual_signal(row):
    nets = words(row['nets'])
    drivers = words(row['drivers'])
    owners = words(row['driver_cells'])
    refs = words(row['driver_refs'])
    ports = words(row['primary_ports'])
    directions = words(row['primary_port_directions'])
    assert nets and len(nets) == len(set(nets))
    assert len(drivers) == len(owners) == len(refs)
    assert all(pin.rsplit('/', 1)[0] == owner for pin, owner in zip(drivers, owners))
    assert (len(drivers) == 1 and not ports and not directions) or (
        not drivers and len(ports) == len(directions) == 1 and directions == ['IN'])
    return dict(nets=set(nets), drivers=drivers, owners=owners, refs=refs,
                ports=ports, directions=directions)

def prove(raw_path, snapshot_path, package_path, *, verify_bindings=True):
    package = json.loads(package_path.read_text())
    if verify_bindings:
        for row in package['bindings']:
            assert identity(row['path']) == row, ('input identity changed', row['path'])
    rows = [json.loads(line) for line in raw_path.read_text().splitlines()]
    assert all(isinstance(row, dict) for row in rows)
    assert {row.get('kind') for row in rows} == {'cell', 'parent', 'state_pin', 'state_clock', 'memory_root_pin'}
    cells = inventory(rows, 'cell', lambda row: row['NAME'])
    parents = inventory(rows, 'parent', lambda row: row['cell'])
    pins = inventory(rows, 'state_pin', lambda row: (row['cell'], row['terminal']))
    clocks = inventory(rows, 'state_clock', lambda row: row['cell'])
    roots = inventory(rows, 'memory_root_pin', lambda row: (row['cell'], row['terminal']))
    selected = set(package['selection_cells'])
    selected_roots = {tuple(value) for value in package['selection_root_pins']}
    assert len(selected) == len(cells) == len(parents) == len(clocks) == 12
    assert set(cells) == set(parents) == set(clocks) == selected
    assert set(pins) == {(cell, pin) for cell in selected for pin in ['D', 'C', 'CE', 'CLR']}
    assert len(pins) == 48 and set(roots) == selected_roots and len(roots) == 24
    snapshot = decode(json.loads(snapshot_path.read_text()))
    memory_pins = {(row['cell'], row['pin']): row for row in snapshot['memory_pins']}
    configs = {row['NAME']: row for row in snapshot['uram_configs']}
    originals = {cell for cell in selected if re.fullmatch(r'.*/artifact_index_r_reg\[(10|11|12)\]', cell)}
    assert len(originals) == 3
    pairs = []
    for cell in sorted(selected):
        row = cells[cell]
        assert row['REF_NAME'] == 'FDCE' and flag(row['IS_PRIMITIVE']) == flag(row['IS_SEQUENTIAL']) == 1
        # Empty supported cell metadata stays unset; never invent a boolean.
        # A3 protection is independently checked by the full frozen validator.
        assert row['DONT_TOUCH'] == '' or flag(row['DONT_TOUCH']) == 0, 'counter/replica is unexpectedly protected'
        assert flag(row['INIT']) == 0
        assert parents[cell]['NAME'] == cell.rsplit('/', 1)[0]
        assert parents[cell]['REF_NAME'] != 'NOT_SUPPORTED'
        for terminal in ['D', 'C', 'CE', 'CLR']:
            pin = pins[(cell, terminal)]
            assert pin['pin'] == cell + '/' + terminal
            assert pin['REF_PIN_NAME'] == terminal and pin['DIRECTION'] == 'IN'
            actual_signal(pin)
            if terminal in ['C', 'CLR']:
                observed_pin_polarity = flag(pin['IS_INVERTED'])
                observed_cell_polarity = row['IS_' + terminal + '_INVERTED']
                if observed_cell_polarity not in ['', 'NOT_SUPPORTED']:
                    assert observed_pin_polarity == flag(observed_cell_polarity)
            else:
                assert flag(pin['IS_INVERTED']) == 0
                property_value = row['IS_' + terminal + '_INVERTED']
                assert property_value in ['', 'NOT_SUPPORTED'] or flag(property_value) == 0
        clock = clocks[cell]
        assert clock['NAME'] == clock['clock'] and clock['PERIOD'] != 'NOT_SUPPORTED'
        assert float(clock['PERIOD']) > 0 and len(words(clock['WAVEFORM'])) == 2
        assert 0 <= float(words(clock['WAVEFORM'])[0]) < float(words(clock['WAVEFORM'])[1]) <= float(clock['PERIOD'])
        if cell in originals:
            continue
        match = [original for original in originals if re.fullmatch(re.escape(original) + r'_replica_[1-9][0-9]*', cell)]
        assert len(match) == 1, ('unmapped actual state source', cell)
        original = match[0]
        for prop in ['REF_NAME', 'INIT', 'IS_C_INVERTED', 'IS_CLR_INVERTED', 'IS_D_INVERTED', 'IS_CE_INVERTED']:
            assert row[prop] == cells[original][prop], ('state property differs', cell, prop)
        assert parents[cell] == {**parents[original], 'cell': cell}
        clock_a = {key: value for key, value in clocks[cell].items() if key != 'cell'}
        clock_b = {key: value for key, value in clocks[original].items() if key != 'cell'}
        assert clock_a == clock_b, ('actual clock/period/edge differs', cell)
        for terminal in ['D', 'C', 'CE', 'CLR']:
            a, b = pins[(cell, terminal)], pins[(original, terminal)]
            assert actual_signal(a) == actual_signal(b), ('actual state input group differs', cell, terminal)
            assert a['IS_INVERTED'] == b['IS_INVERTED'], ('pin polarity differs', cell, terminal)
        pairs.append(dict(original=original, replica=cell, actual_REF_NAME=row['REF_NAME'],
                          same_D_C_CE_CLR_actual_groups=True, same_INIT_and_polarity=True,
                          same_clock_period_waveform=True, same_cycle_state_transition=True))
    assert len(pairs) == 9
    source_by_replica = {pair['replica']: pair['original'] for pair in pairs}
    root_bindings = []
    bit_counts = collections.Counter()
    for key, row in roots.items():
        cell, terminal = key
        assert configs[cell]['CASCADE_ORDER_A'] == configs[cell]['CASCADE_ORDER_B'] == 'FIRST'
        assert row['pin'] == cell + '/' + terminal and row['DIRECTION'] == 'IN'
        assert row['REF_PIN_NAME'] == terminal
        signal = actual_signal(row)
        raw = memory_pins[key]
        assert signal == actual_signal(raw), ('current root differs from failed snapshot', key)
        assert len(signal['drivers']) == 1 and signal['refs'] == ['FDCE']
        replica, output = signal['drivers'][0].rsplit('/', 1)
        assert output == 'Q' and replica in source_by_replica
        bit = int(re.fullmatch(r'ADDR_B\[(10|11|12)\]', terminal)[1])
        original = source_by_replica[replica]
        assert original.endswith(f'/artifact_index_r_reg[{bit}]')
        assert words(raw['startpoints']) == [replica + '/C']
        root_bindings.append(dict(cell=cell, pin=terminal, bit=bit,
                                  actual_driver=replica + '/Q', original_state=original + '/Q'))
        bit_counts[bit] += 1
    assert bit_counts == {10: 8, 11: 8, 12: 8}
    return dict(passed=True, raw_native_source=identity(raw_path), actual_snapshot=identity(snapshot_path),
                query_package=identity(package_path), checkpoint=package['checkpoint'],
                identity_bindings_verified=verify_bindings,
                state_pairs=pairs, affected_root_bindings=root_bindings,
                raw_scalar_metadata_observations=[dict(cell=name, raw_cell=cells[name], raw_parent=parents[name]) for name in sorted(cells)],
                effective_polarity_requires_actual_pin=True,
                empty_cell_properties_not_defaulted=True,
                only_exact_direct_input_group_equivalence=True,
                no_name_only_acceptance=True, raw_snapshot_not_rewritten=True,
                no_alias_set_expansion=True, no_new_functional_cycle=True,
                does_not_prove_timing_or_formal_safety=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = prove(args.raw, args.snapshot, args.package)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True, actual_state_pairs=len(result['state_pairs']),
                          actual_root_pins=len(result['affected_root_bindings']))))

if __name__ == '__main__':
    main()
