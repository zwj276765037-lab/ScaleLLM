"""Bounded independent text/AST/identity review; does not execute engineering code."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import copy
import hashlib
import json
import re

ROOT = Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT = Path(__file__).parent
FIXED = ROOT / 'agent/A006/new_worst_window_supplement/fixed_preparation_v2'
checks = []


def ident(path, expected=None):
    path = Path(path)
    assert path.suffix != '.dcp'
    data = path.read_bytes()
    value = dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    if expected:
        assert value == expected, (value, expected)
    checks.append(value)
    return value


ident(FIXED / 'manifest.json', dict(path=str(FIXED / 'manifest.json'), bytes=4461,
      sha256='a73ce3317d064cdca7fb2f42fd48399943d4e441eb3d44aba802b458924d0f97'))
snapshot = json.loads((FIXED / 'manifest.json').read_text())
for record in snapshot['current_sources'] + snapshot['fixed_sources']:
    ident(record['path'], record)
manifest = json.loads((FIXED / 'new_worst_targets_manifest.json').read_text())
ident(manifest['independent_targets']['path'], manifest['independent_targets'])
ident(manifest['coverage_review']['path'], manifest['coverage_review'])
independent = json.loads(Path(manifest['independent_targets']['path']).read_text())
targets_text = (FIXED / 'targets.tcl').read_text()
phase_checks = []
for phase, spec in manifest['phases'].items():
    report = spec['source_report']
    ident(report['path'], report)
    actual_rows = []
    for line_number, line in enumerate(Path(report['path']).read_text().splitlines(), 1):
        values = [value.strip() for value in line.split('|')[1:-1]]
        if len(values) < 4 or values[0] not in {'North', 'South', 'East', 'West'}:
            continue
        assert values[1] in {'Global', 'Long', 'Short'} and values[2].isdigit()
        pair = re.fullmatch(r'\(([^,]+),([^,]+)\)', values[3])
        assert pair
        actual_rows.append(dict(native_line=line_number, direction=values[0], type=values[1],
            level=int(values[2]), endpoints=list(pair.groups()), source_row_index=len(actual_rows)))
    assert len(actual_rows) == 48
    regions = spec['unique_regions']
    assert regions == [dict(region_id=r['unique_region_id'], endpoints=[r['first_tile'], r['last_tile']])
                       for r in independent['unique_regions']]
    region_by_endpoints = {tuple(r['endpoints']): r['region_id'] for r in regions}
    for actual in actual_rows:
        selected = actual['level'] == max(r['level'] for r in actual_rows
            if (r['direction'], r['type']) == (actual['direction'], actual['type']))
        actual.update(selected_peak=selected,
            region_id=region_by_endpoints[tuple(actual['endpoints'])] if selected else 'NOT_SELECTED')
    assert actual_rows == spec['source_rows']
    peaks = [row for row in actual_rows if row['selected_peak']]
    ref = next(p for p in independent['phases'] if p['phase'] == phase)
    assert report == ref['source_report_identity']
    selected_normalized = [dict(phase=phase, source_report_identity=report,
        native_line=r['native_line'], source_row_index=r['source_row_index'], direction=r['direction'],
        type=r['type'], level=r['level'], first_tile=r['endpoints'][0], last_tile=r['endpoints'][1],
        unique_region_id=r['region_id']) for r in peaks]
    assert selected_normalized == ref['selected_rows']
    assert len(peaks) == 12 and len(regions) == 10
    lines = {line.split(' [list ', 1)[0]: line for line in targets_text.splitlines() if line.startswith('set ')}
    region_line = lines[f'set new_worst_windows({phase})']
    tcl_regions = [re.findall(r'\{([^{}]*)\}', part) for part in re.findall(r'\[list ((?:\{[^{}]*\} ?)+)\]', region_line)]
    assert tcl_regions == [[r['region_id'], *r['endpoints']] for r in regions]
    row_line = lines[f'set source_rows({phase})']
    tcl_rows = [re.findall(r'\{([^{}]*)\}', part) for part in re.findall(r'\[list ((?:\{[^{}]*\} ?)+)\]', row_line)]
    assert tcl_rows == [[str(r['native_line']), r['direction'], r['type'], str(r['level']),
        *r['endpoints'], str(int(r['selected_peak'])), r['region_id']] for r in actual_rows]
    assert re.findall(r'\{([^{}]*)\}', lines[f'set source_report({phase})']) == [report['path'], str(report['bytes']), report['sha256']]
    phase_checks.append(dict(phase=phase, original_report_rows=len(actual_rows),
        all48_exact_native_rows_manifest_and_Tcl_match=True, independent_selected_rows_match=True,
        selected_rows=len(peaks), unique_regions=len(regions), unique_region_IDs=[r['region_id'] for r in regions]))

old_path = ROOT / 'agent/A006/physical_supplement/run_closed_comparison.py'
old_id = ident(old_path)
assert old_id['sha256'] == '4cfa040041ee497e0e56d4406e0ab0342e4f43e3e0550d25e5dc8b1f322ca639'
old = ast.parse(old_path.read_text())
new = ast.parse((FIXED / 'run_closed_comparison.py').read_text())
old_funcs = {n.name: n for n in old.body if isinstance(n, ast.FunctionDef)}
new_funcs = {n.name: n for n in new.body if isinstance(n, ast.FunctionDef)}
unchanged_functions = {name: ast.dump(node) == ast.dump(new_funcs[name]) for name, node in old_funcs.items() if name != 'main'}
assert all(unchanged_functions.values())
assert set(new_funcs) - set(old_funcs) == {'new_peak_target_check'}

# Remove only the reviewed target additions; the remaining full main AST must
# match the already reviewed wrapper, including every resource/terminal guard.
main = copy.deepcopy(new_funcs['main'])
removed = []
class NormalizeTargetAdditions(ast.NodeTransformer):
    def visit_Assign(self, node):
        if any(isinstance(t, ast.Name) and t.id == 'new_peak_sources' for t in node.targets):
            removed.append(ast.unparse(node)); return None
        if any(isinstance(t, ast.Name) and t.id == 'names' for t in node.targets):
            node.value.elts = [e for e in node.value.elts if not (isinstance(e, ast.Constant) and e.value == 'new_worst_targets_manifest.json')]
        return self.generic_visit(node)
    def visit_Call(self, node):
        node.keywords = [k for k in node.keywords if k.arg != 'new_peak_source_reports']
        return self.generic_visit(node)
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call) and any(isinstance(a, ast.Constant) and a.value == 'new peak source report changed' for a in node.value.args):
            removed.append(ast.unparse(node)); return None
        return self.generic_visit(node)
main = NormalizeTargetAdditions().visit(main)
for i, statement in enumerate(main.body):
    if isinstance(statement, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'source_dir' for t in statement.targets):
        removed.append(ast.unparse(statement)); del main.body[i]; break
assert ast.dump(main) == ast.dump(old_funcs['main'])
assert (FIXED / 'readonly_two_phase_driver.tcl').read_bytes() == (ROOT / 'agent/A006/physical_supplement/readonly_two_phase_driver.tcl').read_bytes()
core = (FIXED / 'readonly_physical_supplement.tcl').read_text()
assert not re.search(r'(?m)^\s*(?:opt_design|place_design|phys_opt_design|route_design|write_checkpoint|report_utilization|write_bitstream)\b', core)
assert 'get_pins -quiet -of_objects $cells' in core and 'get_nets -quiet -of_objects [concat $inputs $outputs]' in core
assert 'GRID_POINT_X >= %d && GRID_POINT_X <= %d && GRID_POINT_Y >= %d && GRID_POINT_Y <= %d' in core
assert 'query region_$region_id' in core and 'UNAVAILABLE_NO_VALIDATED_FIXED_WINDOW_CONGESTION_API' in core
assert not any(name in core for name in ['boundary_drivers.tsv', 'target_net_loads.tsv', 'utilization_hierarchy'])
facts = json.loads((FIXED / 'cpu_guard_facts.json').read_text())
assert facts['new_wrapper_sha256'] == next(r['sha256'] for r in snapshot['fixed_sources'] if r['path'].endswith('/run_closed_comparison.py'))
assert facts['producer_sha256'] == next(r['sha256'] for r in snapshot['fixed_sources'] if r['path'].endswith('/verify_preparation.py'))
assert len(facts['cases']) == 9 and all(r['PASS'] for r in facts['cases'])
log = (FIXED / 'cpu_preparation_verification.log').read_text()
assert sum(line.startswith('PASS ') for line in log.splitlines()) == 9 and log.endswith('CPU_PREPARATION_VERIFICATION_PASS 9\n')
assert facts['Tcl_exit'] == 0 and facts['Tcl_structure_stderr'] == ''
record = dict(reviewed_utc=datetime.now(timezone.utc).isoformat(), scope='A007 static bounded AT003 preparation review only',
    source_identity_checks=checks, phase_target_checks=phase_checks,
    preexisting_functions_AST_unchanged=unchanged_functions,
    main_AST_identical_after_only_target_additions_removed=True, removed_main_statements=removed,
    two_phase_driver_unchanged=True,
    CPU_evidence=dict(executed_by='A006', cases=9, facts_bound_to_fixed_wrapper=True, rerun_by_A007=False),
    manual_core_review=dict(actual_device_GRID_rectangle=True, actual_site_SLR_mapping=True,
        capacity_and_distinct_occupied_sites=True, primitive_REF_histogram=True,
        primitive_pin_attached_hierarchical_segments_not_crossing_nets=True,
        each_own_closed_DCP=True, all48_source_rows_preserved=True, query_scope='12 peaks / 10 unique regions per phase',
        per_region_catch=True, physical_commands=False, checkpoint_writes=False,
        repeat_80_boundary_94net_hierarchy_queries=False, fixed_congestion_explicitly_unavailable=True),
    execution='static preparation review completed; actual AT003 not inferred',
    verdict='No material static blocker in this fixed preparation. New peak mapping gap still pending actual per-phase outputs.',
    applicability='Fixed preparation V2 a73ce331; wrapper a4178f45; each own closed original AT003 DCP',
    review='Independent text/hash/AST parsing only; no engineering test rerun, EDA, process control, DCP read or production edit.')
destination = OUT / 'R006_AT003_new_peak_preparation_review_evidence.json'
with destination.open('x') as handle:
    json.dump(record, handle, ensure_ascii=False, indent=2); handle.write('\n')
print(json.dumps(dict(evidence=str(destination), identity_checks=len(checks), phases=phase_checks,
    unchanged_function_count=len(unchanged_functions)), ensure_ascii=False, indent=2))
