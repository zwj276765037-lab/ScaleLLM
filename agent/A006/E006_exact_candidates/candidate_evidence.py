#!/usr/bin/env python3
"""Closed native R004 full-cut consistency and conservative CPU summaries."""
import collections
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
import tkinter

TCL = tkinter.Tcl()
SLRS = {'SLR0', 'SLR1', 'SLR2'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rows(path):
    with Path(path).open() as stream:
        yield from csv.DictReader(stream, delimiter='\t', quoting=csv.QUOTE_NONE)


def identity(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(data)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest.hexdigest())


def save(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def counts(value):
    fields = TCL.splitlist(value)
    require(len(fields) % 2 == 0, 'Odd native Tcl count dictionary')
    return collections.Counter({fields[i]: int(fields[i + 1]) for i in range(0, len(fields), 2)})


def pin_class(ref, terminal, clock):
    if ref in {'GND', 'VCC'}: return 'CONSTANT'
    if ref.startswith('DSP') and re.fullmatch(r'C(?:\[[0-9]+\])?', terminal): return 'DATA_ARITHMETIC'
    if clock in {'1', 'true', 'TRUE'}: return 'CLOCK_NATIVE_PIN'
    if re.fullmatch(r'FD(RE|CE|PE)', ref):
        if terminal == 'C': return 'CLOCK_REF_PIN'
        if terminal in {'R', 'CLR', 'PRE'}: return 'RESET_SET'
        if terminal == 'CE': return 'ENABLE_WRITE_CONTROL'
        if terminal in {'D', 'Q'}: return 'DATA_REGISTER'
    if ref.startswith('DSP'):
        if terminal == 'CLK': return 'CLOCK_REF_PIN'
        if terminal.startswith('RST'): return 'RESET_SET'
        if terminal.startswith('CE'): return 'ENABLE_WRITE_CONTROL'
        if re.fullmatch(r'(A|B|C|D|P|ACIN|ACOUT|BCIN|BCOUT|PCIN|PCOUT)(\[[0-9]+\])?', terminal): return 'DATA_ARITHMETIC'
        return 'UNKNOWN_DSP_PIN'
    if re.match(r'^BU(FG|FH|FR|FIO|FMR|FCE)', ref) and terminal == 'O': return 'CLOCK_BUFFER_OUTPUT_REF'
    if re.fullmatch(r'LUT[1-6]', ref): return 'LOGIC_PIN_FUNCTION_UNCLASSIFIED'
    if ref in {'MUXF7', 'MUXF8'} and terminal == 'S': return 'SELECT_CONTROL'
    if ref in {'MUXF7', 'MUXF8', 'CARRY8'}: return 'DATA_LOGIC_PRIMITIVE'
    return 'UNKNOWN_REF_PIN'


def category(actual_clocks, classes):
    data = {'DATA_ARITHMETIC', 'DATA_REGISTER', 'DATA_LOGIC_PRIMITIVE', 'SELECT_CONTROL'}
    controls = {'RESET_SET', 'CONSTANT', 'ENABLE_WRITE_CONTROL'}
    unknown = not classes or any(value not in data | controls and not value.startswith('CLOCK') for value in classes)
    if actual_clocks or any(value.startswith('CLOCK') for value in classes): return 'clock', unknown
    if 'RESET_SET' in classes: return 'reset_set', unknown
    if 'CONSTANT' in classes: return 'constant', unknown
    if 'ENABLE_WRITE_CONTROL' in classes: return 'enable_write_control', unknown
    if unknown: return ('mixed_known_unknown' if classes & data else 'unknown_or_unclassified'), True
    return 'known_data_or_select_control', False


def cut(point, report):
    report = Path(report)
    marker = report / f'candidate_cut_{point}_closed.txt'
    require('completed=1' in marker.read_text().splitlines(), 'Native cut not closed')
    paths = {key: report / f'candidate_{key}_{point}.tsv'
             for key in ['nets', 'segments', 'endpoints', 'pins', 'RAW', 'S', 'P']}
    raw = {row['NAME']: row['REF_NAME'] for row in rows(paths['RAW'])}
    semantic = {row['NAME']: row['REF_NAME'] for row in rows(paths['S'])}
    physical = {row['NAME']: row['REF_NAME'] for row in rows(paths['P'])}
    require(semantic == {name: ref for name, ref in raw.items() if ref not in {'GND', 'VCC'}}, 'RAW/S constant exclusion differs')
    native_rows = list(rows(paths['nets']))
    nets = {row['canonical_net']: row for row in native_rows}
    require(len(nets) == len(native_rows) and bool(nets), 'Duplicate or empty canonical net scope')
    endpoint_names = set()
    endpoints = collections.defaultdict(list)
    direction_counts = collections.Counter()
    class_counts = collections.Counter()
    for row in rows(paths['endpoints']):
        name, kind = row['canonical_net'], row['kind']
        key = (name, kind, row['NAME'])
        require(name in nets and key not in endpoint_names, 'Duplicate or foreign canonical endpoint')
        endpoint_names.add(key)
        require(kind in {'LEAF_PIN', 'TOP_PORT'}, 'Unknown endpoint kind')
        role = ({'OUT': 'DRIVER', 'IN': 'LOAD', 'INOUT': 'INOUT'} if kind == 'LEAF_PIN' else
                {'IN': 'DRIVER', 'OUT': 'LOAD', 'INOUT': 'INOUT'}).get(row['DIRECTION'], 'UNKNOWN')
        require(role == row['role'], 'Native endpoint role/direction mismatch')
        if kind == 'LEAF_PIN':
            require(row['pin_class'] == pin_class(row['REF_NAME'], row['REF_PIN_NAME'], row['IS_CLOCK']), 'REF/pin/native-clock classification differs')
            require(int(row['inside_RAW']) == int(row['raw_cell'] in raw), 'RAW endpoint membership differs')
            require(int(row['inside_S']) == int(row['raw_cell'] in semantic), 'S endpoint membership differs')
            require(int(row['inside_P']) == int(row['physical_parent'] in physical), 'P endpoint membership differs')
        else:
            require(all(row[key] == '0' for key in ['inside_RAW', 'inside_S', 'inside_P']), 'Top port marked internal')
        endpoints[name].append(row)
        direction_counts[(kind, row['DIRECTION'])] += 1
        class_counts[row['pin_class']] += 1
    segments = {}
    segment_counts = collections.Counter()
    for row in rows(paths['segments']):
        require(row['canonical_net'] in nets and row['segment'] not in segments, 'Duplicate/foreign canonical segment')
        segments[row['segment']] = row['canonical_net']
        segment_counts[row['canonical_net']] += 1
    fanouts = []
    net_categories = collections.Counter()
    cut_directions = collections.Counter()
    unavailable = 0
    cross_nets = 0
    cross_loads = 0
    unknown_semantics = 0
    edge_pins = collections.Counter()
    edge_nets = collections.Counter()
    for name, row in nets.items():
        records = endpoints[name]
        leaf = [value for value in records if value['kind'] == 'LEAF_PIN']
        ports = [value for value in records if value['kind'] == 'TOP_PORT']
        require(len(leaf) == int(row['leaf_pins']) and len(ports) == int(row['top_ports']) and
                segment_counts[name] == int(row['segments']), 'Native complete cut counts disagree')
        drivers = [value for value in records if value['role'] == 'DRIVER']
        loads = [value for value in records if value['role'] == 'LOAD']
        inside = sum(value['inside_S'] == '1' or value['inside_P'] == '1' for value in records)
        inout = sum(value['role'] == 'INOUT' for value in records)
        unresolved = sum(value['role'] == 'UNKNOWN' for value in records) + sum(not value['physical_parent'] for value in leaf)
        require(len(drivers) == int(row['drivers']) and
                inout == int(row['INOUT_count']) and unresolved == int(row['unknown_endpoints']) and
                inside == int(row['inside_endpoints']) and len(records) - inside == int(row['outside_endpoints']), 'Native driver/interior counters disagree')
        resolution = ('UNKNOWN_RETAINED' if unresolved else 'INOUT_RETAINED' if inout else
                      'SINGLE_DRIVER' if len(drivers) == 1 else 'NO_DRIVER' if not drivers else 'MULTIDRIVER_RETAINED')
        boundary = ('CUT' if inside and len(records) > inside else 'UNRESOLVED' if unresolved else
                    'INTERNAL' if inside else 'RAW_SCOPE_ONLY')
        require(row['resolution'] == resolution and row['boundary'] == boundary, 'Native resolution/boundary differs')
        require(segments.get(name) == name, 'Canonical net absent from its exported alias set')
        require(counts(row['classes']) == collections.Counter(value['pin_class'] for value in leaf), 'Native leaf semantics counts differ')
        classes = {value['pin_class'] for value in records}
        cls, has_unknown = category(row['actual_clocks'], classes)
        if row['boundary'] == 'CUT':
            net_categories[cls] += 1
            unknown_semantics += has_unknown
            inside_driver = any(value['inside_P'] == '1' for value in drivers)
            cut_directions['UNRESOLVED' if row['resolution'] != 'SINGLE_DRIVER' else ('EGRESS' if inside_driver else 'INGRESS')] += 1
        known_cross = None
        if (row['resolution'] == 'SINGLE_DRIVER' and len(drivers) == 1 and drivers[0]['SLR'] in SLRS and
                all(value['SLR'] in SLRS for value in loads)):
            known_cross = sum(value['SLR'] != drivers[0]['SLR'] for value in loads)
            cross_nets += known_cross > 0
            cross_loads += known_cross
        else:
            unavailable += 1
        if len(drivers) == 1:
            driver = drivers[0]
            local = collections.Counter((driver['owner_root'], driver['SLR'], value['owner_root'], value['SLR'], value['pin_class']) for value in loads)
            edge_pins.update(local)
            edge_nets.update(local.keys())
        fanouts.append(dict(canonical_net=name, leaf_load_pins=len(loads), leaf_or_top_drivers=len(drivers),
                            known_cross_SLR_load_pins=known_cross, boundary=row['boundary'], resolution=row['resolution'],
                            primitive_semantics_category=cls, contains_unknown_semantics=has_unknown))
    leaf_names = {name for _, kind, name in endpoint_names if kind == 'LEAF_PIN'}
    pin_rows = list(rows(paths['pins']))
    require(len(pin_rows) == len({row['NAME'] for row in pin_rows}), 'Duplicate candidate pin record')
    result = dict(point=point, native_cut_consistency_verified=True,
                  RAW=len(raw), S=len(semantic), P=len(physical), canonical_nets=len(nets),
                  canonical_segments=len(segments), endpoints=len(endpoint_names), candidate_pin_records=len(pin_rows),
                  candidate_pins_without_exact_leaf_endpoint_match=sum(row['NAME'] not in leaf_names for row in pin_rows),
                  endpoint_direction_counts={f'{a}/{b}': value for (a, b), value in direction_counts.items()},
                  endpoint_REF_and_native_clock_semantic_counts=dict(class_counts),
                  boundary_counts=dict(collections.Counter(row['boundary'] for row in native_rows)),
                  driver_resolution_counts=dict(collections.Counter(row['resolution'] for row in native_rows)),
                  exclusive_cut_categories=dict(net_categories), cut_directions=dict(cut_directions),
                  cut_nets_with_unknown_semantics_nonexclusive=unknown_semantics,
                  known_cross_SLR_nets=cross_nets, known_cross_SLR_load_pins=cross_loads,
                  nets_with_unavailable_cross_SLR_count=unavailable,
                  top_fanout_nets=sorted(fanouts, key=lambda row: (-row['leaf_load_pins'], row['canonical_net']))[:40],
                  owner_SLR_semantic_edges=[dict(source_owner=key[0], source_SLR=key[1], load_owner=key[2], load_SLR=key[3],
                                                 load_pin_class=key[4], leaf_or_top_load_pins=value, unique_canonical_nets=edge_nets[key])
                                            for key, value in edge_pins.most_common()],
                  input_artifacts={key: identity(path) for key, path in paths.items()}, producer=identity(__file__),
                  limits='Full selected group connectivity census only; candidate pins without an exact leaf endpoint remain visible and do not prove disconnection. Unknown REF/clock/SLR, INOUT and top ports retained. No traffic/SLL count, full-cut TNS, placement feasibility or candidate support inferred.',
                  full_cut_TNS='NOT_MEASURED', engineering_candidate_supported='NOT_ASSESSED', formal_signoff=False)
    save(report / f'candidate_cut_summary_{point}.json', result)
    print(json.dumps(dict(point=point, canonical_nets=len(nets), endpoints=len(endpoint_names), native_cut_consistency_verified=True)))


if __name__ == '__main__':
    require(len(sys.argv) == 4 and sys.argv[1] == 'cut', 'Use: candidate_evidence.py cut POINT REPORT')
    cut(sys.argv[2], Path(sys.argv[3]))
