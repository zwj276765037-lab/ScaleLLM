"""One-pass final AT020 CLK evidence audit. Never read partial files or DCP.

Run only after the final CLK file and diagnostic completion marker exist.
The resulting verdict covers source records, not the missing original exit code.
"""
from pathlib import Path
import datetime
import hashlib
import json

ROOT = Path(__file__).resolve().parents[3]
OWN = Path(__file__).resolve().parent
REPORT = ROOT / 'project/hardware/vivado/reports/m003_E011_R002_AT020_fresh_core_state_source_semantics'
PREFIX = 'inst/u_core/u_compute/u_attention/u_meta/g_m003_width_slices.g_slice'
EXPECTED = {f'{PREFIX}[{s}].meta_mem_reg_uram_{i}' for s in range(2) for i in range(40)}
ALIAS_SHA = '59bb9a9e03dc4da54708e9be3180d169da6d079718a045d54104ca255a174261'
FIRST_ROW_SHA = '36f4514828ec1149c946daf3e3d748af28579e88d4682f43e6461637e2175007'


def stamp(stat):
    return dict(device=stat.st_dev, inode=stat.st_ino, bytes=stat.st_size, mtime_ns=stat.st_mtime_ns)


def validate_row(row, seen):
    problems = []
    cell = row.get('cell')
    if cell not in EXPECTED:
        problems.append('unexpected_cell')
    if cell in seen:
        problems.append('duplicate_cell')
    seen.add(cell)
    if row.get('CLK_pin') != str(cell) + '/CLK':
        problems.append('CLK_pin_identity')
    nets = row.get('nets')
    digest, count, unique = None, None, None
    if not isinstance(nets, list) or any(not isinstance(x, str) for x in nets):
        problems.append('nets_not_string_array')
    else:
        count, unique = len(nets), len(set(nets))
        digest = hashlib.sha256(json.dumps(nets, separators=(',', ':')).encode()).hexdigest()
        if count != 12062 or unique != count:
            problems.append('net_alias_cardinality_or_duplicate')
        if digest != ALIAS_SHA:
            problems.append('net_alias_array_differs_from_reviewed_baseline')
    if row.get('leaf_drivers') != []:
        problems.append('nonempty_or_missing_actual_leaf_drivers')
    if row.get('primary_ports') != ['core_clk']:
        problems.append('actual_primary_ports_differ')
    if row.get('primary_port_directions') != ['IN']:
        problems.append('actual_primary_port_directions_differ')
    compact = dict(cell=cell, CLK_pin=row.get('CLK_pin'), net_count=count, unique_net_count=unique, net_array_sha256=digest, leaf_drivers=row.get('leaf_drivers'), primary_ports=row.get('primary_ports'), primary_port_directions=row.get('primary_port_directions'), issues=problems)
    return compact


def main():
    target = REPORT / 'uram_clock_sources.jsonl'
    marker = REPORT / 'diagnostic_complete.json'
    output = OWN / 'AT020_closed_clock_independent_analysis.json'
    if output.exists():
        raise RuntimeError('Preserve prior one-pass analysis; do not rerun the large table.')
    if not target.is_file() or not marker.is_file():
        raise RuntimeError('Final CLK file and diagnostic completion marker required.')
    with marker.open('rb') as f:
        marker_bytes = f.read(131073)
    if len(marker_bytes) > 131072:
        raise RuntimeError('Completion marker exceeds bounded review size.')
    complete = json.loads(marker_bytes)
    before = stamp(target.stat())
    raw_hash, seen, rows, issues, total = hashlib.sha256(), set(), [], [], 0
    with target.open('rb') as f:
        for index, line in enumerate(f, 1):
            total += len(line)
            raw_hash.update(line)
            if not line.endswith(b'\n'):
                issues.append(dict(row=index, issue='row_not_newline_closed'))
            if index == 1 and hashlib.sha256(line).hexdigest() != FIRST_ROW_SHA:
                issues.append(dict(row=index, issue='first_row_bytes_differ_from_preserved_actual_row'))
            try:
                row = json.loads(line)
                value = validate_row(row, seen)
            except (ValueError, TypeError, AttributeError) as exc:
                issues.append(dict(row=index, issue='row_parse_or_type_error', error=str(exc)))
                continue
            value['row'] = index
            rows.append(value)
            if value['issues']:
                issues.append(dict(row=index, cell=value['cell'], issues=value['issues']))
    after = stamp(target.stat())
    if before != after or total != after['bytes']:
        issues.append(dict(issue='final_file_changed_during_one_pass'))
    missing = sorted(EXPECTED - seen)
    if missing or len(rows) != 80 or len(seen) != 80:
        issues.append(dict(issue='exact_80_cell_coverage_not_met', missing=missing, parsed_rows=len(rows), unique_cells=len(seen)))
    required = dict(execution='completed', helper_D_rows=34, URAM_clock_rows=80, constraint_apply_requested=False, new_synthesis_launched=False, raw_values_rewritten=False, G4=False)
    for key, value in required.items():
        if complete.get(key) != value or type(complete.get(key)) is not type(value):
            issues.append(dict(issue='completion_marker_field_differs', field=key, expected=value, actual=complete.get(key)))
    if (REPORT / 'diagnostic_error_info.txt').exists():
        issues.append(dict(issue='diagnostic_error_marker_present'))
    result = dict(schema='A007_AT020_closed_CLK_one_pass_analysis_v1', utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), execution='completed_single_stream_of_final_clock_file', verdict='all_80_actual_primary_CLK_sources_accepted' if not issues else 'issues_require_owner_review', review=dict(no_blocker_for_CLK_source_records=not issues), applicability='Exact AT020 source records only; no G4, adopted-tree-drain or original native exit-code acceptance.', final_file=dict(path=str(target.relative_to(ROOT)), before=before, after=after, sha256=raw_hash.hexdigest()), completion_marker=dict(path=str(marker.relative_to(ROOT)), bytes=len(marker_bytes), sha256=hashlib.sha256(marker_bytes).hexdigest(), content=complete), rows=rows, issues=issues, G4=False, original_native_exit_code=None, original_exit_code_unavailable=True, script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with output.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps(dict(output=str(output.relative_to(ROOT)), bytes=output.stat().st_size, sha256=hashlib.sha256(output.read_bytes()).hexdigest(), rows=len(rows), issues=issues, G4=False)))
    return 0 if not issues else 1


if __name__ == '__main__':
    raise SystemExit(main())
