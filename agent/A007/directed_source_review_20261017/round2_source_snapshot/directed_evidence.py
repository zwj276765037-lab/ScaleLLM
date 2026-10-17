#!/usr/bin/env python3
"""Strict directed-cut ledger validator; CPU summaries never claim whole-net scope."""
from collections import Counter, defaultdict
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tkinter

sys.dont_write_bytecode = True
TCL = tkinter.Tcl()
VERSION = 'candidate_directed_cut_v1'
SLRS = {'SLR0', 'SLR1', 'SLR2'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity(path):
    path = Path(path).resolve()
    before = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), f'Input changed while reading {path}')
    return dict(path=str(path), bytes=after.st_size, sha256=digest.hexdigest())


def save(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def rows(path, legacy_space=False, short_no_path=False):
    with Path(path).open() as stream:
        header = stream.readline().rstrip('\n').split('\t')
        require(len(header) == len(set(header)), f'Duplicate header {path}')
        for number, raw in enumerate(stream, 2):
            fields = raw.rstrip('\n').split('\t')
            if legacy_space and len(fields) == 1:
                fields = raw.rstrip('\n').split(' ')
            if short_no_path and len(fields) == 6 and fields[4:] == ['0', 'NO_PATH']:
                fields += [''] * (len(header) - len(fields))
            require(len(fields) == len(header), f'Wrong field count {path}:{number}, {len(fields)} != {len(header)}')
            yield dict(zip(header, fields))


def unique(path, key='NAME', **kwargs):
    data = list(rows(path, **kwargs))
    result = {row[key]: row for row in data}
    require(len(data) == len(result), f'Duplicate native identity {path}')
    return result


def split(value):
    return list(TCL.splitlist(value))


def tdict(value):
    fields = split(value)
    require(len(fields) % 2 == 0, 'Odd Tcl dictionary')
    require(len(fields[::2]) == len(set(fields[::2])), 'Duplicate Tcl dictionary key')
    return dict(zip(fields[::2], fields[1::2]))


def ledger(path):
    return [tdict(line.rstrip('\n')) for line in Path(path).read_text().splitlines() if line]


def marker(path):
    return dict(line.split('=', 1) for line in Path(path).read_text().splitlines() if '=' in line)


def inside(row):
    return row['inside_S'] == '1' or row['inside_P'] == '1'


def role(kind, direction):
    if direction == 'INOUT':
        return 'INOUT'
    return ({'OUT': 'DRIVER', 'IN': 'LOAD'} if kind == 'LEAF_PIN' else {'IN': 'DRIVER', 'OUT': 'LOAD'}).get(direction, 'UNKNOWN')


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


def qualify_membership(point, report):
    output = report / f'candidate_membership_qualification_{point}.json'
    require(not output.exists(), 'Never overwrite membership qualification')
    reuse = json.loads(Path(os.environ.get('DIRECTED_REUSE', Path(__file__).with_name('reuse_manifest.json'))).read_text())
    evidence = reuse['candidates'][point]
    artifacts = reuse['artifacts']
    bound = {}
    for key in evidence['artifact_keys']:
        row = artifacts[key]
        require(identity(row['path']) == row, f'Reused closed input changed: {key}')
        bound[key] = row
    facts = json.loads(Path(artifacts[evidence['facts_key']]['path']).read_text())
    require(facts['native_stage_zero'] is True and facts['physical_normalization_and_literal_membership_consistent'] is True,
            'Original member/resource stage not closed/consistent')
    current = {}
    for tag in ['RAW', 'S', 'P']:
        path = report / f'candidate_{tag}_{point}.tsv'
        new = unique(path)
        old = unique(artifacts[evidence[tag + '_key']]['path'])
        require(new == old, f'Actual same-DCP {tag} membership changed')
        current[tag] = dict(count=len(new), artifact=identity(path))
    for tag in ['membership', 'physical_members', 'site_members']:
        path = report / f'candidate_{tag}_{point}.tsv'
        require(unique(path) == unique(artifacts[evidence[tag + '_key']]['path'], legacy_space=True), f'Actual same-DCP {tag} changed')
        current[tag] = identity(path)
    closed = marker(report / f'candidate_membership_{point}_closed.txt')
    require(closed['completed'] == '1' and closed['root'] == evidence['root'] and closed['actual_exact_root'] == evidence['root'], 'Exact native root differs')
    result = dict(coverage_version=VERSION, point=point, actual_same_DCP_membership_qualified=True,
                  root=evidence['root'], current=current, original_closed_member_resource_evidence=bound,
                  native_resources='REUSED_FROM_R004_NOT_NEWLY_QUERIED', native_resource_values=facts['native_exact_hierarchy_SLR_resources'],
                  hotspot_intersection=facts['hotspot_intersection'], site_sharing=facts['P_touched_shared_exclusive_sites'],
                  formal_signoff=False, candidate_supported='NOT_ASSESSED')
    save(output, result)
    return result


def cut(point, report):
    output = report / f'candidate_cut_summary_{point}.json'
    require(not output.exists(), 'Never overwrite directed cut summary')
    paths = {tag: report / f'candidate_{tag}_{point}.tsv' for tag in ['RAW', 'S', 'P', 'pins', 'segments', 'local_pin_net', 'nets', 'endpoints', 'boundary_timing_scope']}
    closed = marker(report / f'candidate_cut_{point}_closed.txt')
    require(closed.get('completed') == '1' and closed.get('coverage_version') == VERSION, 'Wrong/unclosed cut scope')
    for key in ['directed_boundary_complete', 'candidate_leaf_coverage_complete', 'native_pin_class_schema_qualified']:
        require(closed.get(key) == 'true', 'Native directed closure missing ' + key)
    schema_path = report / f'candidate_directed_class_schema_{point}.tcllist'
    schema = tdict(schema_path.read_text())
    require(schema['coverage_version'] == VERSION and schema['native_tool'] == '2025.2' and schema['qualified'] == '1', 'Native class schema unqualified')
    responses = [tdict(value) for value in split(schema['responses'])]
    require(len(responses) == 2 and all(row['native_tcl_code'] == '0' for row in responses), 'Native class query failed')
    require(split(responses[0]['command']) == ['list_property', '-class', 'pin'] and
            split(responses[1]['command']) == ['list_property_value', 'DIRECTION', '-class', 'pin'], 'Wrong class proof command')
    require({'NAME', 'DIRECTION', 'IS_LEAF'} <= set(split(responses[0]['result'])) and
            {'IN', 'OUT', 'INOUT'} <= set(split(responses[1]['result'])), 'Incomplete built-in class evidence')
    members = {tag: unique(paths[tag]) for tag in ['RAW', 'S', 'P']}
    require(members['S'] == {name: row for name, row in members['RAW'].items() if row['REF_NAME'] not in {'GND', 'VCC'}}, 'Constant exclusion changed')
    local = unique(paths['pins'])
    scope_path = report / f'candidate_local_scope_{point}.tcllist'
    local_scope = tdict(scope_path.read_text())
    require(local_scope['coverage_version'] == VERSION and not split(local_scope['issues']), 'Local graph not qualified')
    I = {name for name, row in local.items() if row['inside_candidate_leaf'] == '1'}
    require(I and I == set(split(local_scope['candidate_leaf_pins'])) and len(local) == int(local_scope['raw_pin_records']), 'Actual local leaf ledger differs')
    p_seen = set()
    for name, row in local.items():
        require(row['raw_cell'] == name.rsplit('/', 1)[0], 'Actual local pin owner mismatch')
        require(row['IS_LEAF'] in {'1', 'true', 'TRUE', '0', 'false', 'FALSE'}, 'Unknown local IS_LEAF')
        for flag, tag, key in [('inside_RAW', 'RAW', 'raw_cell'), ('inside_S', 'S', 'raw_cell'), ('inside_P', 'P', 'physical_parent')]:
            require(row[flag] == str(int(row[key] in members[tag])), 'Local membership flag differs')
        require((name in I) == (row['IS_LEAF'] in {'1', 'true', 'TRUE'} and inside(row)), 'Local actual I/physical owner differs')
        if name in I: p_seen.add(row['physical_parent'])
    require(p_seen == set(members['P']), 'Actual P missing native leaf coverage')
    nets = unique(paths['nets'], 'canonical_net')
    require(nets and len(nets) == int(closed['canonical_nets']) == int(local_scope['canonical_nets']), 'Canonical universe differs')
    aliases = {}
    by_alias = defaultdict(set)
    for row in rows(paths['segments']):
        canonical, segment = row['canonical_net'], row['segment']
        require(canonical in nets and segment not in aliases, 'Duplicate/foreign alias')
        aliases[segment] = canonical; by_alias[canonical].add(segment)
    require(all(name in by_alias[name] and name == min(by_alias[name]) for name in nets), 'Canonical/complete alias export mismatch')
    mapped = defaultdict(set)
    for row in rows(paths['local_pin_net']):
        require(row['pin'] in local and aliases.get(row['native_net_segment']) == row['canonical_net'], 'Local pin/native segment mapping differs')
        mapped[row['pin']].add(row['canonical_net'])
    local_by_net = defaultdict(set)
    for name, row in local.items():
        groups = set(split(row['canonical_net']))
        require(groups == mapped[name] and len(groups) <= 1, 'Local pin canonical mapping not complete')
        require(row['connection_status'] == ('CONNECTED' if groups else 'DISCONNECTED'), 'Disconnected pin ledger differs')
        if row['IS_LEAF'] in {'1', 'true', 'TRUE'}:
            for net in groups: local_by_net[net].add(name)
    require(set(aliases.values()) == set(nets), 'Alias net scope missing')
    endpoints = defaultdict(list); endpoint_keys = set()
    retained_classes = Counter()
    for row in rows(paths['endpoints']):
        canonical, kind, name = row['canonical_net'], row['kind'], row['NAME']
        key = (canonical, kind, name)
        require(canonical in nets and kind in {'LEAF_PIN', 'TOP_PORT'} and key not in endpoint_keys, 'Duplicate/foreign endpoint')
        endpoint_keys.add(key)
        require(role(kind, row['DIRECTION']) == row['role'], 'Direction/role mismatch')
        if kind == 'LEAF_PIN':
            require(row['raw_cell'] == name.rsplit('/', 1)[0], 'Endpoint actual owner differs')
            for flag, tag, field in [('inside_RAW', 'RAW', 'raw_cell'), ('inside_S', 'S', 'raw_cell'), ('inside_P', 'P', 'physical_parent')]:
                require(row[flag] == str(int(row[field] in members[tag])), 'Endpoint physical/logical membership differs')
            require(inside(row) == (name in I), 'Actual candidate leaf I differs from endpoint physical membership')
            require(row['pin_class'] == pin_class(row['REF_NAME'], row['REF_PIN_NAME'], row['IS_CLOCK']), 'Retained pin semantics differ')
            expected_reason = ('CANDIDATE_NATIVE_LEAF' if name in I else 'RAW_ONLY_NATIVE_LEAF' if row['raw_cell'] in members['RAW'] else
                               'ACTUAL_NATIVE_DRIVER' if row['role'] == 'DRIVER' else nets[canonical]['scope_mode'])
            require(row['retained_reason'] == expected_reason, 'Retained reason differs')
        else:
            require(all(row[flag] == '0' for flag in ['inside_RAW', 'inside_S', 'inside_P']) and row['retained_reason'] == 'ALL_NATIVE_TOP_PORTS', 'Top port membership/reason differs')
        endpoints[canonical].append(row); retained_classes[row['pin_class']] += 1
    role_path = report / f'candidate_native_role_queries_{point}.tcllist'
    queries = defaultdict(dict)
    for query in ledger(role_path):
        canonical, kind = query['canonical_net'], query['query_kind']
        require(canonical in nets and kind not in queries[canonical], 'Duplicate/foreign native query')
        require(set(split(query['actual_segment_NAMES'])) == by_alias[canonical], 'Role query did not use complete alias closure')
        command = split(query['command'])
        if kind == 'NONLOAD_LEAF':
            require(command[:3] == ['get_pins', '-leaf', '-of_objects'] and command[4:] == ['-filter', 'DIRECTION != IN'], 'Not direct native non-IN filter')
        elif kind == 'FULL_LEAF':
            require(command[:3] == ['get_pins', '-leaf', '-of_objects'] and len(command) == 4 and query['native_tcl_code'] == '0', 'Wrong complete fallback command')
        elif kind == 'ALL_TOP_PORTS':
            require(command[:2] == ['get_ports', '-of_objects'] and len(command) == 3 and query['native_tcl_code'] == '0', 'Incomplete native top scope')
        else: require(False, 'Unknown native query kind')
        queries[canonical][kind] = query
    timing_expected = set(); pair_counts = Counter(); cross_current = Counter(); cross_hypothetical = Counter(); unknown_pairs = Counter()
    scope_counts = Counter(); boundary_counts = Counter(); category_counts = Counter(); reduced = 0
    directed_edges = 0; boundary_edges = 0
    for canonical, net in nets.items():
        require(net['coverage_version'] == VERSION, 'Mixed coverage versions')
        require(not {'leaf_pins', 'drivers', 'top_ports', 'endpoint_total', 'classes', 'outside_endpoints'} & set(net), 'Legacy full-net field reused')
        q = queries[canonical]
        require({'NONLOAD_LEAF', 'ALL_TOP_PORTS'} <= set(q), 'Native role/top inventory missing')
        records = endpoints[canonical]
        leaf = {row['NAME']: row for row in records if row['kind'] == 'LEAF_PIN'}
        top = {row['NAME']: row for row in records if row['kind'] == 'TOP_PORT'}
        require(local_by_net[canonical] <= set(leaf), 'Connected candidate/RAW leaf omitted')
        for name in local_by_net[canonical]:
            require(leaf[name]['DIRECTION'] == local[name]['DIRECTION'], 'Local/retained direction differs')
        rq = q['NONLOAD_LEAF']; tq = q['ALL_TOP_PORTS']
        names, directions = split(rq['actual_NAMES']), split(rq['actual_DIRECTIONS'])
        require(len(names) == len(directions) == int(rq['raw_objects']), 'Native role vector alignment differs')
        role_map = {}
        for name, direction in zip(names, directions):
            require(name not in role_map or role_map[name] == direction, 'Conflicting native role identity')
            role_map[name] = direction
            require(name in leaf and leaf[name]['DIRECTION'] == direction, 'Native role inventory not retained')
        tnames, tdirs = split(tq['actual_NAMES']), split(tq['actual_DIRECTIONS'])
        require(len(tnames) == len(tdirs) == int(tq['raw_objects']) == len(top), 'Native top vector/count differs')
        require(dict(zip(tnames, tdirs)) == {name: row['DIRECTION'] for name, row in top.items()}, 'Complete top port inventory not retained')
        reasons = []
        if rq['native_tcl_code'] != '0': reasons.append('NATIVE_NONLOAD_ROLE_QUERY_FAILED')
        if any(value == 'IN' for value in directions): reasons.append('NATIVE_NONLOAD_FILTER_RETURNED_IN')
        if any(role('LEAF_PIN', value) in {'UNKNOWN', 'INOUT'} for value in directions): reasons.append('UNRESOLVED_LEAF_DIRECTION')
        if any(role('TOP_PORT', value) in {'UNKNOWN', 'INOUT'} for value in tdirs): reasons.append('UNRESOLVED_TOP_DIRECTION')
        for name in local_by_net[canonical]:
            direction = local[name]['DIRECTION']
            if direction != 'IN' and role_map.get(name) != direction: reasons.append('LOCAL_NONLOAD_MISSING_FROM_NATIVE_ROLE_CENSUS')
            if role('LEAF_PIN', direction) in {'UNKNOWN', 'INOUT'}: reasons.append('LOCAL_UNKNOWN_DIRECTION')
        native_drivers = {('LEAF_PIN', name) for name, direction in role_map.items() if direction == 'OUT'} | {('TOP_PORT', name) for name, direction in zip(tnames, tdirs) if direction == 'IN'}
        if len(native_drivers) != 1: reasons.append('NO_OR_MULTIPLE_NATIVE_DRIVERS')
        driver_inside = len(native_drivers) == 1 and next(iter(native_drivers))[0] == 'LEAF_PIN' and next(iter(native_drivers))[1] in I
        mode = 'FULL_ENUMERATION_FALLBACK' if reasons else 'FULL_ENUMERATION_CANDIDATE_DRIVER' if driver_inside else 'RESOLVED_EXTERNAL_DRIVER_DIRECTED_CUT'
        require(net['scope_mode'] == mode, 'Native scope selector does not match actual receipts')
        require(net['native_role_gate_qualified'] == str(int(not reasons)), 'Native role qualification flag differs')
        require(net['directed_boundary_complete'] == 'true' and net['candidate_leaf_coverage_complete'] == 'true', 'Directed scope flag missing')
        if mode == 'RESOLVED_EXTERNAL_DRIVER_DIRECTED_CUT':
            reduced += 1
            require('FULL_LEAF' not in q, 'Qualified ingress performed forbidden all-leaf query')
            require(set(leaf) == local_by_net[canonical] | set(role_map), 'Reduced retained leaf set differs')
            require(net['outside_peer_leaf_loads'] == 'NOT_ENUMERATED' and net['full_native_leaf_count'] == 'NOT_MEASURED' and net['full_net_endpoint_coverage'] == 'false', 'Reduced net claims full coverage/count')
        else:
            require('FULL_LEAF' in q, 'Full fallback native response absent')
            fq = q['FULL_LEAF']; full_names = split(fq['actual_NAMES'])
            require(len(full_names) == int(fq['raw_objects']) and len(set(full_names)) == int(fq['unique_objects']) == len(leaf) and set(full_names) == set(leaf), 'Complete fallback response/count differs')
            require(net['outside_peer_leaf_loads'] == 'ENUMERATED_IN_FULL_NATIVE_SCOPE' and net['full_net_endpoint_coverage'] == 'true' and int(net['full_native_leaf_count']) == len(leaf), 'Full native coverage declaration differs')
        drivers = [row for row in records if row['role'] == 'DRIVER']; loads = [row for row in records if row['role'] == 'LOAD']
        inouts = sum(row['role'] == 'INOUT' for row in records); role_unknown = sum(row['role'] == 'UNKNOWN' for row in records)
        unknown_observations = role_unknown + sum(not row['physical_parent'] for row in leaf.values())
        ninside = sum(inside(row) for row in records)
        resolution = 'UNKNOWN_RETAINED' if role_unknown else 'INOUT_RETAINED' if inouts else 'SINGLE_DRIVER' if len(drivers) == 1 else 'NO_DRIVER' if not drivers else 'MULTIDRIVER_RETAINED'
        boundary = 'CUT' if ninside and len(records) > ninside else 'UNRESOLVED' if unknown_observations else 'INTERNAL' if ninside else 'RAW_SCOPE_ONLY'
        require(net['resolution'] == resolution and net['boundary'] == boundary, 'Resolution/boundary differs')
        expected_counts = dict(segments=len(by_alias[canonical]), exported_leaf_pin_rows=len(leaf), exported_top_port_rows=len(top), retained_drivers=len(drivers), retained_INOUT=inouts,
                               retained_inside_endpoints=ninside, retained_outside_endpoints=len(records)-ninside, retained_unknown_observations=unknown_observations, exported_endpoint_rows=len(records))
        require(all(int(net[key]) == value for key, value in expected_counts.items()), 'Native retained counts differ')
        require({key: int(value) for key, value in tdict(net['retained_classes']).items()} == dict(Counter(row['pin_class'] for row in leaf.values())), 'Retained class counts differ')
        cls, unknown_semantic = category(net['actual_clocks'], {row['pin_class'] for row in records})
        scope_counts[mode] += 1; category_counts[cls] += 1
        if boundary == 'CUT':
            direction = 'UNRESOLVED' if resolution != 'SINGLE_DRIVER' else 'EGRESS' if inside(drivers[0]) else 'INGRESS'
            boundary_counts[direction] += 1
            selected = [row for row in records if inside(row)] if direction == 'UNRESOLVED' else [row for row in loads if inside(row) == (direction == 'INGRESS')]
            basis = {'UNRESOLVED': 'UNRESOLVED_INSIDE_BOUNDARY_PINS', 'INGRESS': 'INGRESS_INSIDE_LOAD_ONLY', 'EGRESS': 'EGRESS_OUTSIDE_LOAD_ONLY'}[direction]
            for row in selected:
                timing_expected.add((canonical, direction, row['kind'], row['NAME'], row['DIRECTION'], row['role'], row['pin_class'], row['native_clock_group'], basis))
        if resolution == 'SINGLE_DRIVER':
            driver = drivers[0]
            for load in loads:
                if not (inside(driver) or inside(load)): continue
                directed_edges += 1
                is_cut = inside(driver) != inside(load)
                boundary_edges += is_cut
                key = (cls, 'boundary' if is_cut else 'internal')
                pair_counts[key] += 1
                if driver['SLR'] in SLRS and load['SLR'] in SLRS:
                    cross_current[key] += driver['SLR'] != load['SLR']
                    d = 'SLR2' if inside(driver) else driver['SLR']; l = 'SLR2' if inside(load) else load['SLR']
                    cross_hypothetical[key] += d != l
                else: unknown_pairs[(cls, driver['SLR'], load['SLR'])] += 1
    require(int(closed['reduced_ingress_nets']) == reduced and int(closed['full_enumeration_nets']) == len(nets)-reduced, 'Native mode totals differ')
    timing_actual = set()
    for row in rows(paths['boundary_timing_scope']):
        value = tuple(row[key] for key in ['canonical_net', 'cut_direction', 'query_endpoint_kind', 'query_endpoint_NAME', 'DIRECTION', 'role', 'pin_class', 'clock_group', 'selection_basis'])
        require(value not in timing_actual, 'Duplicate timing scope row'); timing_actual.add(value)
    require(timing_actual == timing_expected, 'Expected complete ingress/egress/unresolved timing sets differ')
    failure_relation = None
    reuse_path = Path(os.environ.get('DIRECTED_REUSE', Path(__file__).with_name('reuse_manifest.json')))
    if reuse_path.is_file():
        reuse = json.loads(reuse_path.read_text())
        if 'failure_resolution_key' in reuse:
            source = reuse['artifacts'][reuse['failure_resolution_key']]
            require(identity(source['path']) == source, 'Original failure sample changed')
            matching = []
            for row in rows(source['path']):
                values = {value for value in row.values() if value in aliases}
                if values: matching.append(dict(original=row, actual_candidate_canonical_nets=sorted({aliases[value] for value in values})))
            failure_relation = dict(source=source, matched_original_sample_rows=matching, semantics='Actual native net alias intersection; not whole hotspot UNION recovery')
    result = dict(coverage_version=VERSION, point=point, directed_boundary_complete=True, candidate_leaf_coverage_complete=True,
                  native_pin_class_schema_qualified=True, native_role_qualified_nets=sum(row['native_role_gate_qualified']=='1' for row in nets.values()),
                  canonical_nets=len(nets), actual_candidate_native_leaf_pins=len(I), actual_local_raw_pin_records=len(local),
                  disconnected_candidate_leaf_pins=sum(name in I and row['connection_status']=='DISCONNECTED' for name,row in local.items()),
                  retained_endpoint_rows=len(endpoint_keys), retained_class_counts=dict(retained_classes),
                  scope_modes=dict(scope_counts), boundary_directions=dict(boundary_counts), retained_net_categories=dict(category_counts),
                  candidate_involved_driver_load_pairs=directed_edges, candidate_boundary_driver_load_pairs=boundary_edges,
                  pair_scope=[dict(category=k[0], relation=k[1], candidate_related_pairs=pair_counts[k], current_known_cross_SLR_pairs=cross_current[k],
                                   hypothetical_all_P_to_SLR2_outside_fixed_known_cross_SLR_pairs=cross_hypothetical[k]) for k in sorted(pair_counts)],
                  unknown_top_or_unplaced_pair_positions=[dict(category=k[0], driver_SLR=k[1], load_SLR=k[2], pairs=v) for k,v in sorted(unknown_pairs.items())],
                  original_failure_sample_alias_relation=failure_relation, timing_scope_rows=len(timing_expected),
                  full_net_endpoint_coverage='MIXED_DECLARED_PER_NET', outside_peer_leaf_loads='NOT_ENUMERATED_ON_QUALIFIED_EXTERNAL_DRIVER_NETS',
                  complete_external_fanout='NOT_MEASURED', whole_hotspot_UNION_recovery='NOT_IN_SCOPE_OLD_UNFINISHED_EVIDENCE_PRESERVED',
                  full_cut_TNS='NOT_MEASURED', timing_signoff=False, candidate_supported='NOT_ASSESSED',
                  limitations=['Native-filter cost/performance not inferred from CPU checks', 'Unknown semantics and top/unplaced SLR retained',
                               'Hypothetical pairs are logical connections, not SLL usage, bandwidth or routed success',
                               'Full physical implementation and formal timing remain required'],
                  artifacts={key:identity(path) for key,path in paths.items()},
                  schema=identity(schema_path), local_scope=identity(scope_path), native_role_queries=identity(role_path), native_closed_marker=identity(report / f'candidate_cut_{point}_closed.txt'), validator=identity(__file__))
    save(output, result)
    return result


def timing(point, report):
    output = report / f'candidate_timing_validation_{point}.json'
    require(not output.exists(), 'Never overwrite timing validation')
    expected = defaultdict(set)
    for row in rows(report / f'candidate_boundary_timing_scope_{point}.tsv'):
        expected[row['cut_direction']].add(row['query_endpoint_NAME'])
    query_path = report / f'candidate_timing_queries_{point}.tcllist'
    queries = ledger(query_path); actual = set()
    for row in queries:
        key = (row['direction'], row['delay_type'])
        require(key not in actual and row['direction'] in expected and row['delay_type'] in {'max','min'}, 'Duplicate/foreign timing query')
        command = split(row['command'])
        require(command[:3] == ['get_timing_paths','-quiet','-through'] and set(split(command[3])) == expected[row['direction']] and
                command[4:] == ['-delay_type',row['delay_type'],'-max_paths','16','-nworst','1'], 'Bounded timing native command/scope differs')
        actual.add(key)
    require(actual == {(direction, kind) for direction in expected for kind in ['max','min']}, 'Expected max/min query absent')
    records = list(rows(report / f'candidate_scoped_timing_{point}.tsv', short_no_path=True)); by_query = defaultdict(list)
    for row in records:
        key = (row['direction'], row['delay_type']); require(key in actual, 'Foreign timing result')
        require(row['max_paths']=='16' and int(row['queried_boundary_pins'])==len(expected[key[0]]) and 0<=int(row['returned_paths'])<=16, 'Timing cap/native scope mismatch')
        by_query[key].append(row)
    require(set(by_query) == actual, 'Native timing result missing')
    for key, values in by_query.items():
        counts = {int(row['returned_paths']) for row in values}; require(len(counts)==1, 'Inconsistent native path count')
        count = counts.pop(); require(len(values)==max(1,count), 'Native returned rows differ')
        if not count: require(values[0]['STARTPOINT_PIN']=='NO_PATH', 'Missing no-path marker')
        else: require((report / f'candidate_cut_timing_{point}_{key[0]}_{key[1]}.rpt').is_file(), 'Native timing report missing')
    result=dict(coverage_version=VERSION,point=point,complete_directional_query_sets=True,max_paths=16,nworst=1,
                query_sets={key:sorted(value) for key,value in expected.items()},native_query_count=len(actual),full_cut_TNS='NOT_MEASURED',signoff=False,
                artifacts=[identity(query_path),identity(report/f'candidate_scoped_timing_{point}.tsv'),identity(report/f'candidate_scoped_timing_{point}_coverage.txt')])
    save(output,result);return result


if __name__ == '__main__':
    require(len(sys.argv)==4 and sys.argv[1] in {'qualify-membership','cut','timing'}, 'Use directed_evidence.py qualify-membership|cut|timing POINT REPORT')
    result={'qualify-membership':qualify_membership,'cut':cut,'timing':timing}[sys.argv[1]](sys.argv[2],Path(sys.argv[3]))
    print(json.dumps(dict(validated=True,point=sys.argv[2],coverage_version=VERSION)))
