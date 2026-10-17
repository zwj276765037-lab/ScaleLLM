#!/usr/bin/env python3
"""CPU-only narrow identity bridge; never imports or starts an EDA runner."""
import ast
import datetime as dt
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD_MANIFEST = HERE / 'review_before_lean_scaffold_dependency_bridge/prepared_manifest.json'
OLD_SOURCE = HERE.parent / 'E006_lean_candidate/review_before_planned_scaffold_20261017/run_attribution_lean.py'
CURRENT_SOURCE = HERE.parent / 'E006_lean_candidate/run_attribution_lean.py'
MANIFEST = HERE / 'prepared_manifest.json'
BRIDGE = HERE / 'lean_helper_identity_bridge_20261017.json'
HELPERS = ['identity', 'freeze_check', 'require_registered_closed',
           'prior_registered_identities', 'require']


def identity(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def helper_ast(tree, name):
    found = [node for node in tree.body
             if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(found) == 1, name
    return ast.dump(found[0], include_attributes=False)


def main():
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    old = json.loads(OLD_MANIFEST.read_text())
    assert identity(OLD_MANIFEST)['sha256'] == '236718abd0577d12c64369da9c8d1ed13ed3050b4473a8a4486d47e9cb47eca6'
    assert MANIFEST.read_bytes() == OLD_MANIFEST.read_bytes(), 'Current manifest already changed'
    assert not BRIDGE.exists(), 'Never overwrite an existing bridge'
    old_ref = next(row for row in old['reused_sources'] if row['path'] == str(CURRENT_SOURCE))
    old_source_id = identity(OLD_SOURCE)
    assert (old_source_id['bytes'], old_source_id['sha256']) == (old_ref['bytes'], old_ref['sha256'])
    own = [identity(row['path']) for row in old['own_sources']]
    assert own == old['own_sources'], 'E007 own runtime/validation source changed'
    other_reused = [row for row in old['reused_sources'] if row is not old_ref]
    assert [identity(row['path']) for row in other_reused] == other_reused
    old_tree = ast.parse(OLD_SOURCE.read_text())
    new_tree = ast.parse(CURRENT_SOURCE.read_text())
    checks = []
    for name in HELPERS:
        before, after = helper_ast(old_tree, name), helper_ast(new_tree, name)
        assert before == after, name
        checks.append(dict(name=name, AST_identical=True,
                           canonical_AST_sha256=hashlib.sha256(before.encode()).hexdigest()))
    new_ref = identity(CURRENT_SOURCE)
    result = dict(phase='E007_dependency_identity_bridge_CPU_only',
                  started_utc=started, ended_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  status='PASS_CPU_ONLY', EDA_executed=False, launcher_executed=False,
                  producer=identity(__file__), prior_prepared_manifest=identity(OLD_MANIFEST),
                  archived_old_helper_source=old_source_id,
                  prior_dependency_identity=old_ref, current_dependency_identity=new_ref,
                  imported_helpers=checks, E007_own_sources_unchanged=own,
                  other_reused_sources_unchanged=other_reused,
                  scope='Only five imported function ASTs and complete unchanged E007 source identities; no rerun of native qualification or 59 selector cases',
                  native_qualification='NOT_RUN', physical_validation='NOT_RUN')
    BRIDGE.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    revised = json.loads(OLD_MANIFEST.read_text())
    revised['reused_sources'] = [new_ref if row['path'] == str(CURRENT_SOURCE) else row
                                 for row in revised['reused_sources']]
    revised['CPU_checks'].append(identity(BRIDGE))
    revised['dependency_identity_bridge'] = dict(prior_manifest=identity(OLD_MANIFEST),
                                                bridge=identity(BRIDGE),
                                                changed_scope='One reused source file identity only; five imported helpers AST-identical; eight own sources unchanged')
    tmp = MANIFEST.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(revised, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(MANIFEST)
    print(json.dumps(dict(bridge=identity(BRIDGE), prepared_manifest=identity(MANIFEST),
                          own_sources_unchanged=True, helper_count=len(checks)), ensure_ascii=False))


if __name__ == '__main__':
    main()
