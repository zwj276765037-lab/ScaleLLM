#!/usr/bin/env python3
"""Bounded, read-only E008 source verification; writes only this A007 directory."""
import ast
import datetime as dt
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tkinter

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NEW = ROOT / 'agent/A006/directed_candidate_cut/E008_entry'
BASE = ROOT / 'agent/A006/exact_hotspot_offload'


def identity(path):
    path = Path(path).resolve()
    assert path.stat().st_size < 2_000_000, f'Outside bounded review: {path}'
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def check(row, path=None):
    actual = identity(path or row['path'])
    assert all(actual[key] == row[key] for key in ('bytes', 'sha256')), (row, actual)
    return actual


def dump(name, value):
    path = HERE / name
    assert not path.exists(), path
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


manifest_path = NEW / 'prepared_manifest.json'
manifest = json.loads(manifest_path.read_text())
checks = {}
for group in ['own_sources', 'reused_sources', 'CPU_checks', 'documentation']:
    checks[group] = [check(row) for row in manifest[group]]
for key in ['contract', 'scope_revision', 'selector_reference', 'original_target_authority',
            'source_reuse_manifest', 'shared_collector', 'shared_validator']:
    checks[key] = check(manifest[key])
reuse = json.loads((NEW / 'source_reuse_manifest.json').read_text())
checks['reuse_bindings'] = [check(row) for row in reuse.values()
                          if isinstance(row, dict) and 'sha256' in row]

bridge_path = NEW / 'projection_input_identity_fix_bridge_20261017.json'
bridge = json.loads(bridge_path.read_text())
checks['bridge'] = identity(bridge_path)
checks['old_manifest'] = check(bridge['old_manifest'])
checks['new_manifest'] = check(bridge['new_manifest'])
checks['old_preserved'] = []
for row in bridge['original_bytes_preserved']:
    actual = check(row['archive'])
    assert all(actual[k] == row['original'][k] for k in ('bytes', 'sha256'))
    checks['old_preserved'].append(actual)

checks['CPU_records'] = []
for row in manifest['CPU_checks']:
    cpu = json.loads(Path(row['path']).read_text())
    detail = dict(record=check(row), source_identities=[], other_identities=[], historical_sources=[])
    for source in cpu['source_identities']:
        actual = identity(source['path'])
        if actual == source:
            detail['source_identities'].append(actual)
        else:
            # CT001 predates the two projection repairs and remains historical.
            archive = NEW / 'review_before_projection_input_identity_fix' / Path(source['path']).name
            detail['historical_sources'].append(dict(original=source, preserved=check(source, archive)))
    for key in ['producer', 'shared_R005_manifest', 'b59_manifest', 'fixture_snapshot']:
        if key in cpu:
            detail['other_identities'].append(check(cpu[key]))
    detail['other_identities'] += [check(x) for x in cpu.get('input_artifacts', [])]
    detail['checks'] = cpu['checks']
    detail['mock_phase_replays'] = cpu.get('actual_mock_phase_replays', [])
    checks['CPU_records'].append(detail)

snapshot = HERE / 'original_9f267_snapshot'
snapshot_manifest = identity(snapshot / 'prepared_manifest.json')
assert snapshot_manifest['sha256'] == identity(manifest_path)['sha256']
for row in manifest['own_sources']:
    check(row, snapshot / Path(row['path']).name)
dump('snapshot_name_identity_clarification.json', dict(
    recorded_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
    directory_label_is_historical_misnomer=True,
    directory=str(snapshot), actual_manifest=snapshot_manifest,
    intended_initial_manifest_sha256='9f267cc481ebec37a087d3cd9456212b3f33cd1841b9b78304c42c2e461d01bc',
    explanation='The copy occurred after A006 finalized the repaired package. All 13 copied sources match saved final 1d612 manifest. Existing directory and test-result names are preserved; they do not establish old-source identity.',
    actual_old_package=bridge['old_manifest'],
    affected_results=identity(HERE / 'projection_original_9f267/results.json')))

def python_funcs(path):
    tree = ast.parse(path.read_text(), filename=str(path))
    return {node.name: ast.dump(node, include_attributes=False) for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


tcl = tkinter.Tcl()
def tcl_procs(path):
    source = path.read_text()
    assert tcl.call('info', 'complete', source) == 1
    output = {}
    lines = source.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        if lines[i].startswith('proc '):
            name = lines[i].split()[1]
            body = lines[i]
            while not tcl.call('info', 'complete', body):
                i += 1
                body += lines[i]
            output[name] = body
        i += 1
    return output


comparison = {}
diffs = []
for name in ['evidence_adapter.py', 'run_candidate.py', 'launch_detached.py',
             'candidate_hooks.tcl', 'runtime_hooks.tcl', 'implementation.tcl', 'property_alignment.tcl']:
    old = BASE / name
    new = NEW / name
    funcs = python_funcs if name.endswith('.py') else tcl_procs
    old_f, new_f = funcs(old), funcs(new)
    comparison[name] = dict(
        original=identity(old), revised=identity(new),
        unchanged=sorted(k for k in old_f.keys() & new_f.keys() if old_f[k] == new_f[k]),
        changed=sorted(k for k in old_f.keys() & new_f.keys() if old_f[k] != new_f[k]),
        added=sorted(new_f.keys() - old_f.keys()), removed=sorted(old_f.keys() - new_f.keys()))
    diffs.extend(difflib.unified_diff(old.read_text().splitlines(True), new.read_text().splitlines(True),
                                   fromfile=str(old), tofile=str(new)))
diff_path = HERE / 'b59_to_final_source.diff'
assert not diff_path.exists()
diff_path.write_text(''.join(diffs))

expected_unchanged = {
    'evidence_adapter.py': ['successful_pre_place_parent', 'constraint_chain', 'membership',
                            'reconcile_objects', 'require_origin_query', 'reconcile', 'selected',
                            'bindable', 'accepted_raw_resource'],
    'candidate_hooks.tcl': ['slr2::resolve', 'slr2::physical', 'slr2::objects', 'slr2::post_phase'],
    'runtime_hooks.tcl': ['slr2::resource_admissibility', 'slr2::placement_policy',
                          'slr2::constrain', 'slr2::reconcile'],
    'run_candidate.py': ['require_fresh_or_planned', 'final_evidence'],
}
for name, funcs in expected_unchanged.items():
    assert set(funcs) <= set(comparison[name]['unchanged']), (name, funcs, comparison[name])
assert identity(BASE / 'launch_detached.py')['sha256'] == identity(NEW / 'launch_detached.py')['sha256']
assert identity(BASE / 'property_alignment.tcl')['sha256'] == identity(NEW / 'property_alignment.tcl')['sha256']
checks['baseline_function_comparison'] = comparison
checks['diff'] = identity(diff_path)

# Import and call only the source-identity verifier. No launcher, lock, EDA or
# process-control functions are invoked, and no Python bytecode is written.
os.environ['SLR2_WORKSPACE_ROOT'] = str(ROOT)
sys.path.insert(0, str(NEW))
spec = importlib.util.spec_from_file_location('a007_e008_final_manifest_verifier', NEW / 'run_candidate.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.verify_manifest(manifest_path) == manifest
checks['actual_verify_manifest_returned_final_manifest'] = True
checks['execution_limits'] = dict(EDA=False, production_source_writes=False,
                                process_signals=False, lock_control=False, DCP_read=False)
checks['manifest'] = identity(manifest_path)
checks['projection_test_results'] = identity(HERE / 'projection_original_9f267/results.json')
checks['all_seven_projection_cases_expected'] = json.loads((HERE / 'projection_original_9f267/results.json').read_text())['all_expected']
checks['recorded_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
dump('final_package_verification.json', checks)
print(json.dumps(dict(manifest=checks['manifest'], groups={k:len(checks[k]) for k in ['own_sources','reused_sources','CPU_checks','documentation','old_preserved']}, comparison={k:{a:v for a,v in x.items() if a in ['changed','added','removed']} for k,x in comparison.items()}, verify_manifest=True),ensure_ascii=False))
