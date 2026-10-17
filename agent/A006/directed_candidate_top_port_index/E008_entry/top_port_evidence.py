"""Reconstruct a complete port transpose from actual native call receipts."""
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import sys
import tkinter

_TCL = tkinter.Tcl()
MODE = 'complete_native_port_incidence_transpose_v1'
OPTIONAL = {'BUS_NAME', 'BUS_WIDTH', 'BUS_START', 'BUS_STOP', 'BUS_DIRECTION', 'UNCONNECTED'}


def split(value):
    return list(_TCL.splitlist(value))


def require(condition, message):
    if not condition:
        raise ValueError('Top-port index: ' + message)


def dictionary(value):
    parts = split(value)
    require(len(parts) % 2 == 0 and len(set(parts[::2])) == len(parts[::2]), 'invalid Tcl dictionary')
    return dict(zip(parts[::2], parts[1::2]))


def identity(path):
    path = Path(path).resolve()
    before = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), 'identity changed while reading')
    return dict(path=str(path), bytes=after.st_size, sha256=digest.hexdigest())


def validate(point, report, require_closed=True):
    report = Path(report)
    path = report / f'candidate_top_port_index_{point}.tcllist'
    index = dictionary(path.read_text())
    require(index['schema_version'] == 'top_port_reverse_index_v1' and index['acquisition_mode'] == 'NATIVE_PORT_REVERSE_INDEX_V1', 'wrong acquisition schema')
    epoch = split(index['epoch_id'])
    require(len(epoch) == 4 and epoch[0] == point and epoch[2] == index['design_handle'] and Path(epoch[3]).resolve() == Path(index['input_path']), 'epoch/input identity differs')
    require(index['stage'] == ('E006_readonly_attribution' if point in {'C01', 'C02'} else 'E008_' + point), 'stage/point differs')
    source_paths = split(index['source_paths'])
    require(len(source_paths) == 1 and Path(source_paths[0]).name == 'top_port_index.tcl' and str(Path(source_paths[0]).resolve()) == source_paths[0], 'mandatory native collector source binding absent/ambiguous')
    source_identity = identity(source_paths[0])
    local_identity = identity(Path(__file__).with_name('top_port_index.tcl'))
    require((source_identity['bytes'], source_identity['sha256']) == (local_identity['bytes'], local_identity['sha256']), 'native collector differs from this validated protocol')
    if require_closed:
        closed = json.loads((report / f'candidate_top_port_index_closed_{point}.json').read_text())
        require(closed['qualified'] is True and closed['epoch_id'] == index['epoch_id'] and closed['point'] == point, 'missing/stale INDEX_CLOSED')
        require(closed['sources'] == [source_identity, identity(__file__)], 'closed index omitted/misbound mandatory collector/validator sources')
        require(closed['input_identity'] == identity(index['input_path']), 'closed index input is not actual bound graph input')
        for row in closed['artifacts'] + closed['sources'] + [closed['input_identity']]:
            require(identity(row['path']) == row, 'closed index/source/input identity changed')
        require(closed['artifacts'] == [identity(path), identity(report / index['native_calls'])], 'closed index omitted native evidence')
    require(index['mode'] == MODE and index['point'] == point and index['qualified'] == '1', 'mode/stage/qualification differs')
    require(index['native_reciprocal_all_groups_qualified'] == '1' and index['current_instance'] == '', 'unqualified reciprocity or nonroot context')
    call_name = f'candidate_top_port_native_calls_{point}.tcllist'
    require(index['native_calls'] == call_name, 'foreign native-call artifact')
    calls = [dictionary(line) for line in (report / call_name).read_text().splitlines() if line]
    require(len(calls) == int(index['native_call_count']) and bool(calls), 'native call count differs')
    properties = {}
    attached = {}
    raw_groups = []
    forwards = []
    schemas = []
    universes = []
    designs = []
    contexts = []
    enums = []
    tools = []
    for ordinal, call in enumerate(calls, 1):
        require(call['call_id'] == str(ordinal) and call['native_tcl_code'] == '0', 'missing/failed native call')
        require(int(call['started_epoch_ms']) <= int(call['ended_epoch_ms']), 'invalid native call timing')
        command = split(call['command'])
        result = split(call['result'])
        if command == ['current_design']:
            designs.append(call['result'])
        elif command == ['current_instance', '.']:
            contexts.append(call['result'])
        elif command == ['list_property', '-class', 'port']:
            schemas.append(set(result))
        elif command == ['list_property_value', 'DIRECTION', '-class', 'port']:
            enums.append(result)
        elif command == ['version', '-short']:
            tools.append(call['result'])
        elif command == ['get_ports']:
            universes.append(result)
        elif len(command) == 3 and command[0] == 'get_property':
            prop, objects = command[1], split(command[2])
            # Successful scalar empty is an observed empty value. Misaligned
            # vectors require the collector's individual native scalar calls.
            values = [call['result']] if call['operation'].startswith('TOP_SCALAR_') else ([''] if len(objects) == 1 and call['result'] == '' else result)
            if len(values) == len(objects):
                for name, value in zip(objects, values):
                    key = (name, prop)
                    require(key not in properties or properties[key] == value, 'same native object/property changed')
                    properties[key] = value
        elif len(command) == 3 and command[:2] == ['get_nets', '-of_objects']:
            objects = split(command[2])
            require(len(objects) == 1 and objects[0] not in attached and len(result) == len(set(result)), 'direct per-port adjacency omitted/duplicated')
            attached[objects[0]] = result
        elif len(command) == 3 and command[:2] == ['get_nets', '-segments']:
            objects = split(command[2])
            require(len(objects) == 1 and result and len(result) == len(set(result)) and objects[0] in result, 'invalid native alias closure')
            raw_groups.append((objects[0], set(result)))
        elif len(command) == 3 and command[:2] == ['get_ports', '-of_objects']:
            aliases = split(command[2])
            require(len(aliases) == len(set(aliases)) and len(result) == len(set(result)), 'duplicate reciprocal identity')
            forwards.append((set(aliases), result))
        else:
            require(False, 'unexpected/nonreadonly native command: ' + repr(command))
    require(len(schemas) == len(universes) == 1, 'complete unfiltered native universe/schema absent')
    require(len(enums) == 1 and enums[0] == split(index['direction_enum']) and {'IN', 'OUT', 'INOUT'} <= set(enums[0]), 'native port direction enum absent/differs')
    require(tools == ['2025.2'] and index['native_tool'] == '2025.2', 'native tool differs')
    require(len(designs) == len(contexts) == 2 and designs[0] == designs[1] == index['design_handle'] and contexts == ['', ''], 'design/context epoch changed')
    require(properties.get((designs[0], 'NAME')) == index['design_NAME'], 'native design NAME differs')
    schema = schemas[0]
    require({'NAME', 'CLASS', 'DIRECTION'} <= schema and set(split(index['schema'])) == schema, 'native schema differs')
    optional = schema & OPTIONAL
    require(set(split(index['metadata_supported'])) == optional, 'supported metadata coverage differs')
    ports = universes[0]
    require(len(ports) == len(set(ports)) and ports == split(index['native_port_handles']) == split(index['native_port_NAMES']), 'native port universe omitted/duplicated/changed')
    require(set(attached) == set(ports), 'not every enumerated native port has its own complete direct query')
    parsed_ports = dictionary(index['ports'])
    require(set(parsed_ports) == set(ports), 'port ledger universe differs')
    aliases = {}
    groups = {}
    for source, members in raw_groups:
        canonical = min(members)
        require(canonical not in groups or groups[canonical] == members, 'intersecting unequal native aliases')
        for name in members:
            require(properties.get((name, 'NAME')) == name, 'native alias identity missing')
            require(name not in aliases or aliases[name] == canonical, 'native alias groups overlap unequally')
            aliases[name] = canonical
        groups[canonical] = members
    expected_ports = defaultdict(set)
    directions = {}
    for name in ports:
        row = dictionary(parsed_ports[name])
        require(properties.get((name, 'NAME')) == name and properties.get((name, 'CLASS')) == 'port', 'native port identity/class unavailable')
        require((name, 'DIRECTION') in properties, 'native direction query absent')
        direction = properties[(name, 'DIRECTION')]
        directions[name] = direction
        require(row['handle'] == row['NAME'] == name and row['CLASS'] == 'port' and row['DIRECTION'] == direction, 'port metadata changed')
        extra = dictionary(row['metadata'])
        require(set(extra) == optional and all((name, prop) in properties and extra[prop] == properties[(name, prop)] for prop in optional), 'supported BUS/UNCONNECTED metadata missing')
        expected_status = {prop: 'UNSUPPORTED' if prop not in optional else 'EMPTY' if extra[prop] == '' else 'VALUE' for prop in OPTIONAL}
        require(dictionary(row['metadata_status']) == expected_status, 'VALUE/EMPTY/UNSUPPORTED status differs')
        nets = attached[name]
        require(nets == split(row['direct_net_handles']) == split(row['direct_net_NAMES']), 'complete direct adjacency differs')
        require(all(net in aliases and properties.get((net, 'NAME')) == net for net in nets), 'direct native net closure absent')
        member_groups = {aliases[net] for net in nets}
        require(set(split(row['canonical_groups'])) == member_groups, 'multigroup port association omitted')
        status = 'DISCONNECTED' if not nets else 'MULTIPLE_CANONICAL_GROUPS' if len(member_groups) > 1 else 'CONNECTED'
        require(row['connection_status'] == status, 'disconnected/multigroup ledger differs')
        if 'UNCONNECTED' in extra:
            flag = extra['UNCONNECTED']
            require(flag in {'', '0', '1', 'false', 'true', 'FALSE', 'TRUE'}, 'unknown UNCONNECTED encoding')
            if flag:
                require((flag in {'1', 'true', 'TRUE'}) == (not nets), 'UNCONNECTED/native adjacency contradiction')
        for canonical in member_groups:
            expected_ports[canonical].add(name)
    require(set(expected_ports) == set(groups), 'unrelated/missing port alias group')
    parsed_groups = dictionary(index['groups'])
    require(set(parsed_groups) == set(groups), 'exported complete group universe differs')
    require(dictionary(index['alias_to_group']) == aliases, 'complete reverse alias map differs')
    reciprocal = {}
    for members, result in forwards:
        require(bool(members), 'empty reciprocal group')
        canonical = min(members)
        require(canonical in groups and groups[canonical] == members and canonical not in reciprocal, 'reciprocity did not use every complete alias group exactly once')
        require(set(result) == expected_ports[canonical], 'native forward/reverse port universe mismatch')
        reciprocal[canonical] = result
    require(set(reciprocal) == set(groups), 'native all-group reciprocal qualification missing')
    for canonical, members in groups.items():
        row = dictionary(parsed_groups[canonical])
        require(set(split(row['handles'])) == set(split(row['aliases'])) == members, 'exported full native alias members changed')
        port_handles = dictionary(row['ports'])
        require(set(port_handles) == expected_ports[canonical] and all(key == value for key, value in port_handles.items()), 'exported port membership changed')
        require(split(row['native_forward_port_handles']) == split(row['native_forward_port_NAMES']) == reciprocal[canonical], 'native reciprocal result changed')
    return dict(path=path, calls_path=report / call_name, groups=groups, aliases=aliases, epoch_id=index['epoch_id'],
                input_path=index['input_path'], source_paths=split(index['source_paths']), native_calls=len(calls),
                ports_by_group=dict(expected_ports), directions=directions, native_port_count=len(ports),
                disconnected_ports=[name for name in ports if not attached[name]],
                multigroup_ports=[name for name in ports if len({aliases[net] for net in attached[name]}) > 1],
                unknown_direction_ports=[name for name in ports if directions[name] not in {'IN', 'OUT', 'INOUT'}])


def validate_join(point, canonical, candidate_aliases, query, index):
    require(query['query_kind'] == 'TOP_PORT_INDEX_JOIN' and query['execution_tcl_code'] == '0' and 'native_tcl_code' not in query and query['execution_kind'] == 'PURE_PROJECTION', 'join masquerades as native query or failed')
    require(query['acquisition_mode'] == 'NATIVE_PORT_REVERSE_INDEX_V1' and query['epoch_id'] == index['epoch_id'] and query['index_closed_artifact'] == f'candidate_top_port_index_closed_{point}.json', 'join epoch/closed-index binding differs')
    require(query['index_artifact'] == f'candidate_top_port_index_{point}.tcllist' and query['index_mode'] == MODE, 'foreign index binding')
    require(query['segment_NAME_source'] == 'CACHED_COMPLETE_NATIVE_ALIAS_CLOSURE', 'unknown alias metadata provenance')
    command = split(query['command'])
    require(len(command) == 4 and command[:3] == ['slr2::top_index_join', point, canonical] and set(split(command[3])) == candidate_aliases, 'join omitted actual candidate aliases')
    matches = {index['aliases'][name] for name in candidate_aliases if name in index['aliases']}
    require(len(matches) <= 1, 'candidate intersects inconsistent port alias groups')
    if matches:
        group = next(iter(matches))
        require(group == canonical and index['groups'][group] == candidate_aliases and query['intersected_group'] == group, 'candidate/port alias closure differs')
        names = index['ports_by_group'][group]
    else:
        require(query['intersected_group'] == 'NONE', 'empty intersection mislabeled')
        names = set()
    actual_names, actual_directions = split(query['actual_NAMES']), split(query['actual_DIRECTIONS'])
    require(len(actual_names) == len(set(actual_names)) == len(actual_directions) == int(query['raw_objects']), 'join vectors/count differ')
    require(set(actual_names) == names and dict(zip(actual_names, actual_directions)) == {name: index['directions'][name] for name in names}, 'complete top-port join inventory differs')


def close(point, report):
    report = Path(report)
    value = validate(point, report, require_closed=False)
    record = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), schema_version='top_port_reverse_index_v1',
                  acquisition_mode='NATIVE_PORT_REVERSE_INDEX_V1', point=point, epoch_id=value['epoch_id'], qualified=True,
                  issues=[], native_port_count=value['native_port_count'], native_group_count=len(value['groups']),
                  native_call_count=value['native_calls'], disconnected_ports=value['disconnected_ports'],
                  multigroup_ports=value['multigroup_ports'], unknown_direction_ports=value['unknown_direction_ports'],
                  input_identity=identity(value['input_path']),
                  sources=[identity(path) for path in value['source_paths']] + [identity(__file__)],
                  artifacts=[identity(value['path']), identity(value['calls_path'])],
                  claim='Complete native port universe, all per-port adjacency and complete aliases, exhaustive native reciprocal groups; no timing or performance signoff')
    with (report / f'candidate_top_port_index_closed_{point}.json').open('x') as stream:
        stream.write(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    return record


if __name__ == '__main__':
    require(len(sys.argv) == 4 and sys.argv[1] == 'close', 'Use top_port_evidence.py close POINT REPORT')
    value = close(sys.argv[2], sys.argv[3])
    print(json.dumps(dict(qualified=value['qualified'], point=value['point'], epoch_id=value['epoch_id'])))
